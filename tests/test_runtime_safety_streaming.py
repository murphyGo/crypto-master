"""Exact streaming safety aggregation and its bounded ownership contract."""

from __future__ import annotations

import gc
import sys
import weakref
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest

from src.runtime.activity_events import ActivityEvent, ActivityEventType
from src.runtime.gate_reason import GateReason
from src.runtime.safety_score import (
    DEFAULT_MAX_SAFETY_KEYS,
    DEFAULT_MAX_SAFETY_STATE_BYTES,
    RuntimeSafetyInputs,
    SafetyAccumulator,
    SafetyAggregationError,
    compute_runtime_safety_score,
    inputs_from_activity_events,
    inputs_from_recent_activity_events,
    recent_activity_events,
)
from src.utils.time import ensure_utc

NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


def event(
    kind: ActivityEventType = ActivityEventType.RISK_KILL_SWITCH_TRIPPED,
    *,
    timestamp: datetime = NOW,
    cycle_id: str | None = None,
    message: str = "",
    **details: Any,
) -> ActivityEvent:
    return ActivityEvent(
        event_type=kind,
        timestamp=timestamp,
        cycle_id=cycle_id,
        message=message,
        details=details,
    )


class OneShot:
    def __init__(self, events: Iterable[ActivityEvent]) -> None:
        self.events = iter(events)
        self.iterations = 0

    def __iter__(self) -> Iterator[ActivityEvent]:
        self.iterations += 1
        assert self.iterations == 1, "source iterated more than once"
        yield from self.events


def old_inputs_oracle(
    events: list[ActivityEvent],
    *,
    lookback_hours: int = 0,
    drawdown: float = 0.0,
) -> dict[str, int | float]:
    """Literal pre-streaming list/count/set semantics, independent of helpers."""
    if lookback_hours > 0:
        cutoff = NOW - timedelta(hours=lookback_hours)
        events = [row for row in events if ensure_utc(row.timestamp) >= cutoff]
    conditions = set()
    for row in events:
        if row.event_type != "risk_kill_switch_tripped" or row.details.get("advisory"):
            continue
        cycle = row.cycle_id
        if cycle is None:
            cycle = row.details.get("cycle_id")
        conditions.add(
            (
                cycle,
                row.details.get("gate_reason"),
                row.details.get("sub_account_id") or "__global__",
            )
        )
    return {
        "recent_cycle_errors": sum(row.event_type == "cycle_errored" for row in events),
        "recent_notification_failures": sum(
            row.event_type == "notification_failed" for row in events
        ),
        "recent_llm_timeouts": sum(row.event_type == "llm_timeout" for row in events),
        "stale_quote_warnings": sum(
            "stale_quote" in str(row.details.get("reason", ""))
            or "stale-quote" in row.message
            for row in events
        ),
        "correlation_warnings": sum(
            row.event_type == "correlation_warning" for row in events
        ),
        "liquidation_events": sum(row.event_type == "liquidated" for row in events),
        "cold_start_blocks": sum(
            row.event_type == "cold_start_blocked" for row in events
        ),
        "kill_switch_conditions": len(conditions),
        "open_drawdown_percent": drawdown,
    }


def old_score_oracle(inputs: dict[str, int | float]) -> dict[str, Any]:
    """Pinned score/factor order and band thresholds before streaming."""
    rules = [
        ("recent_cycle_errors", "cycle errors", 15, 45),
        ("recent_notification_failures", "notification failures", 10, 30),
        ("recent_llm_timeouts", "llm timeouts", 5, 20),
        ("stale_quote_warnings", "stale quote warnings", 10, 30),
        ("correlation_warnings", "correlation warnings", 10, 30),
        ("liquidation_events", "liquidations", 40, 80),
        ("kill_switch_conditions", "kill-switch conditions", 25, 60),
        ("cold_start_blocks", "cold-start blocks", 5, 15),
    ]
    score, factors = 100, []
    for field, label, multiplier, cap in rules:
        count = inputs[field]
        penalty = min(int(count) * multiplier, cap)
        if penalty:
            score -= penalty
            factors.append(f"{label}={count} (-{penalty})")
    drawdown = inputs["open_drawdown_percent"]
    penalty = min(int(drawdown), 30)
    if penalty:
        score -= penalty
        factors.append(f"open drawdown={drawdown:.2f}% (-{penalty})")
    score = max(0, min(100, score))
    band = (
        "safe"
        if score >= 85
        else (
            "degraded"
            if score >= 65
            else "risky" if score >= 40 else "pause_recommended"
        )
    )
    return {
        "score": score,
        "band": band,
        "inputs": inputs,
        "factors": factors or ["no recent safety penalties"],
    }


@pytest.mark.parametrize("lookback", [0, -24, 24])
def test_one_pass_matches_fixed_time_oracle_for_all_events(lookback: int) -> None:
    rows = [
        event(kind, timestamp=timestamp, reason=reason, cycle_id=f"cycle-{i % 3}")
        for i, kind in enumerate(ActivityEventType)
        for timestamp in (
            NOW - timedelta(hours=24, microseconds=1),
            NOW - timedelta(hours=24),
            NOW + timedelta(days=3),
        )
        for reason in (None, "stale_quote_crossed")
    ]
    rows += [rows[-1], rows[-1]]
    expected = old_inputs_oracle(rows, lookback_hours=lookback, drawdown=12.75)
    source = OneShot(reversed(rows))
    actual = inputs_from_recent_activity_events(
        source, lookback_hours=lookback, now=NOW, open_drawdown_percent=12.75
    )
    assert source.iterations == 1
    assert actual.model_dump() == expected
    assert compute_runtime_safety_score(actual).model_dump(
        mode="json"
    ) == old_score_oracle(expected)
    unwindowed = inputs_from_activity_events(OneShot(rows), open_drawdown_percent=12.75)
    assert unwindowed.model_dump() == old_inputs_oracle(rows, drawdown=12.75)


@pytest.mark.parametrize("lookback", [0, -1, 24])
def test_list_compatibility_and_inclusive_timezone_boundary(lookback: int) -> None:
    boundary = (NOW - timedelta(hours=24)).astimezone(timezone(timedelta(hours=9)))
    rows = [
        event(timestamp=boundary - timedelta(microseconds=1)),
        event(timestamp=boundary),
        event(timestamp=NOW + timedelta(days=1)),
        event(timestamp=boundary.replace(tzinfo=None) - timedelta(hours=9)),
    ]
    expected = rows if lookback <= 0 else rows[1:]
    result = recent_activity_events(OneShot(rows), lookback_hours=lookback, now=NOW)
    assert isinstance(result, list)
    assert result == expected
    assert inputs_from_recent_activity_events(
        OneShot(rows), lookback_hours=lookback, now=NOW
    ).model_dump() == old_inputs_oracle(rows, lookback_hours=lookback)


def test_stale_reason_or_message_and_duplicate_rows_remain_exact() -> None:
    rows = [
        event(
            ActivityEventType.CYCLE_ERRORED, reason="stale_quote", message="stale-quote"
        ),
        event(ActivityEventType.STARTUP, message="stale-quote warnings"),
        event(ActivityEventType.STARTUP, reason={"stale_quote": "한글"}),
        event(ActivityEventType.STARTUP, reason=None, message="Stale-quote"),
        event(ActivityEventType.STARTUP, reason="STALE_QUOTE"),
    ]
    rows.append(rows[0])
    actual = inputs_from_activity_events(OneShot(rows))
    assert actual.model_dump() == old_inputs_oracle(rows)
    assert actual.stale_quote_warnings == 4
    assert actual.recent_cycle_errors == 2


def test_raw_scalar_fallback_enum_and_nan_key_parity() -> None:
    shared_nan = float("nan")
    rows = [
        event(gate_reason=value, sub_account_id="alpha")
        for value in (
            True,
            1,
            1.0,
            False,
            0,
            -0.0,
            None,
            "",
            "1",
            float("inf"),
            float("-inf"),
            shared_nan,
            shared_nan,
            float("nan"),
            float("nan"),
            GateReason.DAILY_LOSS_KILL_SWITCH,
            GateReason.DAILY_LOSS_KILL_SWITCH.value,
            ActivityEventType.CYCLE_STARTED,
            ActivityEventType.CYCLE_STARTED.value,
        )
    ]
    rows.extend(event(sub_account_id=value) for value in (None, False, 0, "", [], {}))
    rows += [
        event(cycle_id="", gate_reason="fallback"),
        event(gate_reason="fallback"),
        event(cycle_id="top", gate_reason="fallback"),
        event(cycle_id="top", gate_reason="fallback", advisory="false"),
    ]
    rows[-4].details["cycle_id"] = "detail"
    rows[-3].details["cycle_id"] = "detail"
    rows[-2].details["cycle_id"] = "ignored"
    actual = inputs_from_activity_events(OneShot(rows))
    assert actual.model_dump() == old_inputs_oracle(rows)
    assert actual.kill_switch_conditions == 16
    # A single NaN object deduplicates through tuple identity; two independently
    # decoded NaNs remain distinct. Neither may be stringified or canonicalized.
    assert rows[11].details["gate_reason"] is rows[12].details["gate_reason"]


@pytest.mark.parametrize("reverse", [False, True])
def test_gate_reason_enum_and_string_deduplicate_in_both_orders(reverse: bool) -> None:
    rows = [
        event(gate_reason=GateReason.DAILY_LOSS_KILL_SWITCH),
        event(gate_reason=GateReason.DAILY_LOSS_KILL_SWITCH.value),
    ]
    if reverse:
        rows.reverse()
    accumulator = SafetyAccumulator()
    accumulator.add(rows[0])
    charged = accumulator.state_bytes
    accumulator.add(rows[1])
    assert accumulator.finish().kill_switch_conditions == 1
    assert accumulator.state_bytes == charged


class CustomString(str):
    pass


@pytest.mark.parametrize("key_field", ["cycle_id", "gate_reason", "sub_account_id"])
@pytest.mark.parametrize(
    "key", [("secret",), ["secret"], {"secret": 1}, b"secret", CustomString("secret")]
)
def test_unsupported_key_fails_without_normalization_or_partial_result(
    key: Any, key_field: str
) -> None:
    accumulator = SafetyAccumulator()
    accumulator.add(event(ActivityEventType.CYCLE_ERRORED))
    before = accumulator.state_bytes
    row = event()
    row.details[key_field] = key
    with pytest.raises(SafetyAggregationError) as failure:
        accumulator.add(row)
    assert failure.value.reason == "safety_key_unsupported"
    assert str(failure.value) == "safety_key_unsupported"
    assert accumulator.state_bytes == before
    assert accumulator.distinct_keys == 0
    with pytest.raises(SafetyAggregationError, match="^safety_key_unsupported$"):
        accumulator.finish()
    with pytest.raises(SafetyAggregationError, match="^safety_key_unsupported$"):
        accumulator.add(event())


def test_unprocessed_advisory_old_and_nonkill_keys_do_not_fail() -> None:
    rows = [
        event(gate_reason=["unsupported"], advisory="yes"),
        event(gate_reason=["unsupported"], timestamp=NOW - timedelta(days=2)),
        event(ActivityEventType.STARTUP, gate_reason=["unsupported"]),
    ]
    assert (
        inputs_from_recent_activity_events(OneShot(rows), now=NOW)
        == RuntimeSafetyInputs()
    )


def test_distinct_cap_checks_before_retaining_but_allows_duplicates() -> None:
    accumulator = SafetyAccumulator(max_distinct_keys=2)
    accumulator.add(event(cycle_id="a"))
    accumulator.add(event(cycle_id="b"))
    charged = accumulator.state_bytes
    for _ in range(20):
        accumulator.add(event(cycle_id="a"))
    assert accumulator.state_bytes == charged
    assert accumulator.finish().kill_switch_conditions == 2
    with pytest.raises(SafetyAggregationError, match="^safety_key_limit$"):
        accumulator.add(event(cycle_id="c"))
    assert accumulator.state_bytes == charged
    assert accumulator.distinct_keys == 2
    with pytest.raises(SafetyAggregationError, match="^safety_key_limit$"):
        accumulator.finish()


def test_byte_charge_and_reserved_extras_fail_before_retaining() -> None:
    row = event(cycle_id="large", gate_reason="x" * 4096)
    probe = SafetyAccumulator()
    probe.add(row)
    exact = probe.state_bytes
    accumulator = SafetyAccumulator(
        max_state_bytes=exact + 123, reserved_extra_bytes=123
    )
    accumulator.add(row)
    assert accumulator.state_bytes == exact + 123
    accumulator.add(row)
    assert accumulator.finish().kill_switch_conditions == 1
    rejected = SafetyAccumulator(max_state_bytes=exact + 122, reserved_extra_bytes=123)
    before = rejected.state_bytes
    with pytest.raises(SafetyAggregationError, match="^safety_state_limit$"):
        rejected.add(row)
    assert rejected.state_bytes == before
    assert rejected.distinct_keys == 0
    with pytest.raises(SafetyAggregationError, match="^safety_state_limit$"):
        rejected.finish()
    with pytest.raises(SafetyAggregationError, match="^safety_state_limit$"):
        SafetyAccumulator(reserved_extra_bytes=DEFAULT_MAX_SAFETY_STATE_BYTES)


def test_incremental_extra_reservation_is_bounded_and_poisoned_on_failure() -> None:
    accumulator = SafetyAccumulator()
    accumulator.reserve_extra_bytes(
        DEFAULT_MAX_SAFETY_STATE_BYTES - accumulator.state_bytes
    )
    assert accumulator.state_bytes == DEFAULT_MAX_SAFETY_STATE_BYTES
    assert accumulator.finish() == RuntimeSafetyInputs()
    with pytest.raises(SafetyAggregationError, match="^safety_state_limit$"):
        accumulator.reserve_extra_bytes(1)
    with pytest.raises(SafetyAggregationError, match="^safety_state_limit$"):
        accumulator.finish()


@pytest.mark.parametrize("extra", [-1, 0.5, True])
def test_unsupported_extra_size_fails_explicitly(extra: Any) -> None:
    with pytest.raises(SafetyAggregationError, match="^safety_state_unsupported$"):
        SafetyAccumulator(reserved_extra_bytes=extra)


def test_hard_limits_cannot_be_disabled_by_constructor() -> None:
    with pytest.raises(SafetyAggregationError, match="^safety_key_limit$"):
        SafetyAccumulator(max_distinct_keys=DEFAULT_MAX_SAFETY_KEYS + 1)
    with pytest.raises(SafetyAggregationError, match="^safety_state_limit$"):
        SafetyAccumulator(max_state_bytes=DEFAULT_MAX_SAFETY_STATE_BYTES + 1)


def test_default_key_limit_retains_exactly_50000_scalar_conditions() -> None:
    accumulator = SafetyAccumulator()
    row = event()
    for value in range(DEFAULT_MAX_SAFETY_KEYS):
        row.details["cycle_id"] = value
        accumulator.add(row)
    assert accumulator.finish().kill_switch_conditions == DEFAULT_MAX_SAFETY_KEYS
    assert accumulator.state_bytes <= DEFAULT_MAX_SAFETY_STATE_BYTES
    row.details["cycle_id"] = DEFAULT_MAX_SAFETY_KEYS
    with pytest.raises(SafetyAggregationError, match="^safety_key_limit$"):
        accumulator.add(row)


@pytest.mark.parametrize("recent", [False, True])
def test_public_helpers_preserve_legacy_counts_above_runtime_key_cap(
    recent: bool,
) -> None:
    rows = [event() for _ in range(DEFAULT_MAX_SAFETY_KEYS + 1)]
    for value, row in enumerate(rows):
        row.details["cycle_id"] = value
    expected = old_inputs_oracle(rows, lookback_hours=24 if recent else 0)
    source = OneShot(rows)
    actual = (
        inputs_from_recent_activity_events(source, now=NOW)
        if recent
        else inputs_from_activity_events(source)
    )
    assert source.iterations == 1
    assert actual.model_dump() == expected
    assert actual.kill_switch_conditions == 50_001
    # Public compatibility cannot relax the runtime worker's strict reducer.
    bounded = SafetyAccumulator()
    for row in rows[:-1]:
        bounded.add(row)
    with pytest.raises(SafetyAggregationError, match="^safety_key_limit$"):
        bounded.add(rows[-1])


class LegacyHashable:
    def __hash__(self) -> int:
        return 17

    def __eq__(self, other: object) -> bool:
        return isinstance(other, LegacyHashable)


@pytest.mark.parametrize("recent", [False, True])
@pytest.mark.parametrize("key_field", ["cycle_id", "gate_reason", "sub_account_id"])
@pytest.mark.parametrize(
    "key",
    [
        (("nested", 1),),
        b"legacy",
        Decimal("1.25"),
        CustomString("legacy"),
        LegacyHashable(),
    ],
)
def test_public_helpers_keep_legacy_hashable_keys_and_bounded_reducer_rejects(
    recent: bool, key_field: str, key: Any
) -> None:
    rows = [event(), event(), event(ActivityEventType.CYCLE_ERRORED)]
    rows[0].details[key_field] = key
    rows[1].details[key_field] = (
        LegacyHashable() if isinstance(key, LegacyHashable) else key
    )
    expected = old_inputs_oracle(rows, lookback_hours=24 if recent else 0)
    actual = (
        inputs_from_recent_activity_events(OneShot(rows), now=NOW)
        if recent
        else inputs_from_activity_events(OneShot(rows))
    )
    assert actual.model_dump() == expected
    assert actual.kill_switch_conditions == 1
    with pytest.raises(SafetyAggregationError, match="^safety_key_unsupported$"):
        SafetyAccumulator().add(rows[0])


@pytest.mark.parametrize("recent", [False, True])
@pytest.mark.parametrize("key_field", ["cycle_id", "gate_reason", "sub_account_id"])
@pytest.mark.parametrize("key", [["legacy"], {"legacy": 1}])
def test_public_helpers_keep_legacy_type_error_for_unhashable_conditions(
    recent: bool, key_field: str, key: Any
) -> None:
    row = event()
    row.details[key_field] = key
    with pytest.raises(TypeError):
        old_inputs_oracle([row])
    with pytest.raises(TypeError):
        if recent:
            inputs_from_recent_activity_events(OneShot([row]), now=NOW)
        else:
            inputs_from_activity_events(OneShot([row]))


def test_state_charge_covers_actual_key_storage_and_set_resize_overlap() -> None:
    accumulator = SafetyAccumulator()
    keys = set()
    previous_set_bytes = sys.getsizeof(keys)
    key_bytes = 0
    for value in range(10_000):
        key = (str(value), None, "__global__")
        keys.add(key)
        key_bytes += sys.getsizeof(key) + sum(sys.getsizeof(item) for item in key)
        accumulator.add(event(cycle_id=key[0]))
        table_bytes = sys.getsizeof(keys)
        # During resize both old and new set tables may coexist temporarily.
        resize_overlap = previous_set_bytes if table_bytes != previous_set_bytes else 0
        assert accumulator.state_bytes >= key_bytes + table_bytes + resize_overlap
        previous_set_bytes = table_bytes


def test_events_and_irrelevant_payloads_are_not_retained() -> None:
    live = weakref.WeakValueDictionary()
    peak_live = 0

    def generate() -> Iterator[ActivityEvent]:
        nonlocal peak_live
        for index in range(10_000):
            row = event(ActivityEventType.CYCLE_ERRORED, ignored_payload="x" * 8192)
            live[index] = row
            peak_live = max(peak_live, len(live))
            yield row

    actual = inputs_from_activity_events(OneShot(generate()))
    gc.collect()
    assert not live
    assert peak_live <= 2
    assert actual.recent_cycle_errors == 10_000
    score = compute_runtime_safety_score(actual)
    assert score.score == 55
    assert score.factors == ["cycle errors=10000 (-45)"]


@pytest.mark.parametrize("count", range(10))
def test_scores_and_factors_keep_old_bands_at_small_and_saturated_counts(
    count: int,
) -> None:
    rows = [event(ActivityEventType.LLM_TIMEOUT)] * count
    expected = old_inputs_oracle(rows, drawdown=count * 3.25)
    actual = inputs_from_activity_events(
        OneShot(rows), open_drawdown_percent=count * 3.25
    )
    assert compute_runtime_safety_score(actual).model_dump(
        mode="json"
    ) == old_score_oracle(expected)

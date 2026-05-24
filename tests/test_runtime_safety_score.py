"""Tests for runtime safety score models."""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from src.runtime.activity_log import ActivityEvent, ActivityEventType
from src.runtime.safety_score import (
    RuntimeSafetyBand,
    RuntimeSafetyInputs,
    RuntimeSafetyPolicy,
    RuntimeSafetyScore,
    compute_runtime_safety_score,
    format_runtime_safety_summary,
    inputs_from_activity_events,
    inputs_from_recent_activity_events,
    recent_activity_events,
)
from src.utils.time import now_utc


def test_runtime_safety_inputs_defaults_are_zero() -> None:
    inputs = RuntimeSafetyInputs()

    assert inputs.recent_cycle_errors == 0
    assert inputs.recent_notification_failures == 0
    assert inputs.recent_llm_timeouts == 0
    assert inputs.stale_quote_warnings == 0
    assert inputs.correlation_warnings == 0
    assert inputs.liquidation_events == 0
    assert inputs.cold_start_blocks == 0
    assert inputs.open_drawdown_percent == 0.0


def test_runtime_safety_inputs_reject_negative_counts() -> None:
    with pytest.raises(ValidationError, match="recent_cycle_errors"):
        RuntimeSafetyInputs(recent_cycle_errors=-1)


def test_runtime_safety_policy_maps_score_bands() -> None:
    policy = RuntimeSafetyPolicy()

    assert policy.band_for_score(100) == RuntimeSafetyBand.SAFE
    assert policy.band_for_score(85) == RuntimeSafetyBand.SAFE
    assert policy.band_for_score(70) == RuntimeSafetyBand.DEGRADED
    assert policy.band_for_score(45) == RuntimeSafetyBand.RISKY
    assert policy.band_for_score(10) == RuntimeSafetyBand.PAUSE_RECOMMENDED


def test_runtime_safety_policy_rejects_non_descending_thresholds() -> None:
    with pytest.raises(ValidationError, match="safe > degraded > risky"):
        RuntimeSafetyPolicy(safe_score=70, degraded_score=80, risky_score=40)


def test_runtime_safety_score_requires_bounded_score() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 100"):
        RuntimeSafetyScore(
            score=101,
            band=RuntimeSafetyBand.SAFE,
            inputs=RuntimeSafetyInputs(),
        )


def test_inputs_from_activity_events_counts_safety_signals() -> None:
    events = [
        ActivityEvent(event_type=ActivityEventType.CYCLE_ERRORED),
        ActivityEvent(event_type=ActivityEventType.NOTIFICATION_FAILED),
        ActivityEvent(event_type=ActivityEventType.LLM_TIMEOUT),
        ActivityEvent(event_type=ActivityEventType.LIQUIDATED),
        ActivityEvent(event_type=ActivityEventType.COLD_START_BLOCKED),
        ActivityEvent(event_type=ActivityEventType.CORRELATION_WARNING),
        ActivityEvent(
            event_type=ActivityEventType.PROPOSAL_REJECTED,
            message="Stale-quote rejected BTC/USDT long",
            details={"reason": "stale_quote_past_sl"},
        ),
    ]

    inputs = inputs_from_activity_events(events, open_drawdown_percent=12.5)

    assert inputs.recent_cycle_errors == 1
    assert inputs.recent_notification_failures == 1
    assert inputs.recent_llm_timeouts == 1
    assert inputs.liquidation_events == 1
    assert inputs.cold_start_blocks == 1
    assert inputs.stale_quote_warnings == 1
    assert inputs.correlation_warnings == 1
    assert inputs.open_drawdown_percent == 12.5


def test_inputs_from_recent_activity_events_ignores_old_incidents() -> None:
    now = now_utc()
    events = [
        ActivityEvent(
            event_type=ActivityEventType.LIQUIDATED,
            timestamp=now - timedelta(hours=25),
        ),
        ActivityEvent(
            event_type=ActivityEventType.CORRELATION_WARNING,
            timestamp=now - timedelta(minutes=5),
        ),
    ]

    inputs = inputs_from_recent_activity_events(events, now=now, lookback_hours=24)

    assert inputs.liquidation_events == 0
    assert inputs.correlation_warnings == 1


def test_recent_activity_events_can_disable_window() -> None:
    now = now_utc()
    old = ActivityEvent(
        event_type=ActivityEventType.CYCLE_ERRORED,
        timestamp=now - timedelta(days=7),
    )

    assert recent_activity_events([old], now=now, lookback_hours=0) == [old]


def test_compute_runtime_safety_score_safe_when_no_penalties() -> None:
    safety = compute_runtime_safety_score(RuntimeSafetyInputs())

    assert safety.score == 100
    assert safety.band == RuntimeSafetyBand.SAFE
    assert safety.factors == ["no recent safety penalties"]


def test_compute_runtime_safety_score_applies_penalties() -> None:
    safety = compute_runtime_safety_score(
        RuntimeSafetyInputs(
            recent_cycle_errors=1,
            recent_notification_failures=1,
            recent_llm_timeouts=2,
            stale_quote_warnings=1,
            correlation_warnings=1,
            open_drawdown_percent=5.5,
        )
    )

    assert safety.score == 40
    assert safety.band == RuntimeSafetyBand.RISKY
    assert any("cycle errors=1" in factor for factor in safety.factors)


def test_compute_runtime_safety_score_recommends_pause_on_liquidation() -> None:
    safety = compute_runtime_safety_score(
        RuntimeSafetyInputs(liquidation_events=2),
    )

    assert safety.score == 20
    assert safety.band == RuntimeSafetyBand.PAUSE_RECOMMENDED


def test_format_runtime_safety_summary_is_compact() -> None:
    safety = compute_runtime_safety_score(
        RuntimeSafetyInputs(recent_cycle_errors=1),
    )

    assert format_runtime_safety_summary(safety) == "runtime_safety: 85/100 safe"


# DEBT-068(h): kill-switch trips feed the runtime-safety-score. The
# extractor counts DISTINCT (cycle_id, gate_reason, sub_account_id)
# tuples among non-advisory RISK_KILL_SWITCH_TRIPPED events.


def _kill_switch_event(
    *,
    cycle_id: str | None = "cycle-1",
    gate_reason: str = "daily_loss_kill_switch",
    sub_account_id: str | None = "sub-a",
    advisory: bool = False,
    **details: object,
) -> ActivityEvent:
    payload: dict[str, object] = {"gate_reason": gate_reason, **details}
    if sub_account_id is not None:
        payload["sub_account_id"] = sub_account_id
    if advisory:
        payload["advisory"] = True
    return ActivityEvent(
        event_type=ActivityEventType.RISK_KILL_SWITCH_TRIPPED,
        message="kill switch tripped",
        details=payload,
        cycle_id=cycle_id,
    )


def test_kill_switch_conditions_dedup_same_tuple() -> None:
    events = [_kill_switch_event() for _ in range(10)]

    inputs = inputs_from_activity_events(events)

    assert inputs.kill_switch_conditions == 1


def test_kill_switch_conditions_distinct_sub_accounts() -> None:
    events = [
        _kill_switch_event(sub_account_id="sub-a"),
        _kill_switch_event(sub_account_id="sub-b"),
    ]

    inputs = inputs_from_activity_events(events)

    assert inputs.kill_switch_conditions == 2


def test_kill_switch_conditions_distinct_gate_reasons() -> None:
    events = [
        _kill_switch_event(gate_reason="daily_loss_kill_switch"),
        _kill_switch_event(gate_reason="open_drawdown_kill_switch"),
    ]

    inputs = inputs_from_activity_events(events)

    assert inputs.kill_switch_conditions == 2


def test_kill_switch_conditions_accrue_across_cycles() -> None:
    events = [
        _kill_switch_event(cycle_id="cycle-1"),
        _kill_switch_event(cycle_id="cycle-2"),
        _kill_switch_event(cycle_id="cycle-3"),
    ]

    inputs = inputs_from_activity_events(events)

    assert inputs.kill_switch_conditions == 3


def test_kill_switch_conditions_exclude_paper_advisories() -> None:
    advisory_only = [_kill_switch_event(advisory=True) for _ in range(3)]
    assert inputs_from_activity_events(advisory_only).kill_switch_conditions == 0

    mixed = [
        _kill_switch_event(advisory=True),
        _kill_switch_event(advisory=False),
    ]
    assert inputs_from_activity_events(mixed).kill_switch_conditions == 1


def test_kill_switch_conditions_normalize_missing_sub_account() -> None:
    events = [
        _kill_switch_event(
            gate_reason="portfolio_daily_loss_kill_switch",
            sub_account_id=None,
        ),
        ActivityEvent(
            event_type=ActivityEventType.RISK_KILL_SWITCH_TRIPPED,
            details={
                "gate_reason": "portfolio_daily_loss_kill_switch",
                "sub_account_id": None,
            },
            cycle_id="cycle-1",
        ),
    ]

    inputs = inputs_from_activity_events(events)

    assert inputs.kill_switch_conditions == 1


def test_kill_switch_global_trip_collapses_across_proposers() -> None:
    """DEBT-068(h) regression: one PORTFOLIO trip != N conditions.

    A global kill-switch (``portfolio_*``) runs per-proposal within a
    cycle. The engine now DROPS the proposer ``sub_account_id`` from the
    emitted event (see ``_global_kill_switch_gate`` /
    ``_portfolio_daily_loss_check``), so each emit normalizes to
    ``"__global__"``. Two proposers tripping the SAME portfolio condition
    in the SAME cycle must collapse to ONE condition (DEGRADED, score 75),
    not N (which 3 accounts would have scored 75 = RISKY pre-fix).
    """
    events = [
        # Proposer "sub-a" tripped the portfolio gate -> emit carries no
        # owning account (sub_account_id dropped at the engine emit site).
        _kill_switch_event(
            gate_reason="portfolio_daily_loss_kill_switch",
            sub_account_id=None,
        ),
        # Proposer "sub-b" hit the same global condition, same cycle ->
        # also carries no owning account.
        _kill_switch_event(
            gate_reason="portfolio_daily_loss_kill_switch",
            sub_account_id=None,
        ),
    ]

    inputs = inputs_from_activity_events(events)

    assert inputs.kill_switch_conditions == 1


def test_kill_switch_distinct_account_gates_not_collapsed() -> None:
    """DEBT-068(h): account-level gates carry a stable real account id.

    Two DISTINCT account-level conditions (different real account ids,
    same gate_reason) must still count as 2 — the fix must not
    over-collapse account gates onto the global bucket.
    """
    events = [
        _kill_switch_event(
            gate_reason="daily_loss_kill_switch",
            sub_account_id="acct_a",
        ),
        _kill_switch_event(
            gate_reason="daily_loss_kill_switch",
            sub_account_id="acct_b",
        ),
    ]

    inputs = inputs_from_activity_events(events)

    assert inputs.kill_switch_conditions == 2


def test_kill_switch_single_condition_degrades_band() -> None:
    safety = compute_runtime_safety_score(
        RuntimeSafetyInputs(kill_switch_conditions=1),
    )

    assert safety.score == 75
    assert safety.band == RuntimeSafetyBand.DEGRADED
    assert any("kill-switch conditions=1" in factor for factor in safety.factors)


def test_kill_switch_penalty_caps_at_sixty() -> None:
    safety = compute_runtime_safety_score(
        RuntimeSafetyInputs(kill_switch_conditions=5),
    )

    assert safety.score == 40
    assert safety.band == RuntimeSafetyBand.RISKY


def test_kill_switch_conditions_respect_lookback_window() -> None:
    now = now_utc()
    events = [
        _kill_switch_event(cycle_id="old"),
        _kill_switch_event(cycle_id="recent"),
    ]
    events[0].timestamp = now - timedelta(hours=25)
    events[1].timestamp = now - timedelta(minutes=5)

    inputs = inputs_from_recent_activity_events(events, now=now, lookback_hours=24)

    assert inputs.kill_switch_conditions == 1


def test_kill_switch_scope_excludes_stale_and_freeze_events() -> None:
    events = [
        ActivityEvent(
            event_type=ActivityEventType.STALE_POSITION_AUTO_CLOSED,
            details={"sub_account_id": "sub-a"},
            cycle_id="cycle-1",
        ),
        ActivityEvent(
            event_type=ActivityEventType.OPERATOR_FREEZE_ENGAGED,
            details={"reason": "operator_freeze"},
            cycle_id="cycle-1",
        ),
    ]

    inputs = inputs_from_activity_events(events)
    safety = compute_runtime_safety_score(inputs)

    assert inputs.kill_switch_conditions == 0
    assert safety.score == 100
    assert safety.band == RuntimeSafetyBand.SAFE

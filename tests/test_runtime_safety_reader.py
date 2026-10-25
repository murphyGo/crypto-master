"""Independent safety oracle, bounded legacy IO and worker failure ownership."""

from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.runtime.activity_events import ActivityEvent, ActivityEventType
from src.runtime.safety_reader import (
    ReadControl,
    SafetyCycleBudget,
    SafetyReadLimits,
    SafetyReadService,
    SafetyReadUnavailable,
    capture_sources,
)
from src.runtime.safety_score import inputs_from_recent_activity_events
from src.utils.bounded_read import Generation, legacy_text_rows
from src.utils.time import now_utc


def control(limits: SafetyReadLimits | None = None) -> ReadControl:
    import time

    at = time.monotonic()
    return ReadControl(limits or SafetyReadLimits(), SafetyCycleBudget(), at, at + 30)


def event(kind: ActivityEventType, at: datetime, **details: object) -> ActivityEvent:
    return ActivityEvent(timestamp=at, event_type=kind, details=details)


def test_one_shot_matches_independent_legacy_counts() -> None:
    at = datetime(2026, 10, 25, tzinfo=timezone.utc)
    events = [event(k, at) for k in ActivityEventType]
    events += [
        event(ActivityEventType.CYCLE_ERRORED, at - timedelta(hours=24)),
        event(
            ActivityEventType.CYCLE_ERRORED, at - timedelta(hours=24, microseconds=1)
        ),
        event(ActivityEventType.LLM_TIMEOUT, at + timedelta(days=2)),
        ActivityEvent(timestamp=at, event_type="startup", message="stale-quote"),
        event(ActivityEventType.STARTUP, at, reason="stale_quote"),
        event(ActivityEventType.RISK_KILL_SWITCH_TRIPPED, at, advisory="yes"),
    ]
    for gate in [None, "", 0, False, 1, True, "x", float("nan")]:
        events.extend(
            [
                event(
                    ActivityEventType.RISK_KILL_SWITCH_TRIPPED,
                    at,
                    gate_reason=gate,
                    cycle_id="c",
                )
            ]
            * 2
        )
    recent = [e for e in events if e.timestamp >= at - timedelta(hours=24)]
    # Independent original multipass formula (not the new accumulator).
    expected = {
        "recent_cycle_errors": sum(e.event_type == "cycle_errored" for e in recent),
        "recent_notification_failures": sum(
            e.event_type == "notification_failed" for e in recent
        ),
        "recent_llm_timeouts": sum(e.event_type == "llm_timeout" for e in recent),
        "stale_quote_warnings": sum(
            "stale_quote" in str(e.details.get("reason", ""))
            or "stale-quote" in e.message
            for e in recent
        ),
        "correlation_warnings": sum(
            e.event_type == "correlation_warning" for e in recent
        ),
        "liquidation_events": sum(e.event_type == "liquidated" for e in recent),
        "cold_start_blocks": sum(e.event_type == "cold_start_blocked" for e in recent),
        "kill_switch_conditions": len(
            {
                (
                    e.cycle_id if e.cycle_id is not None else e.details.get("cycle_id"),
                    e.details.get("gate_reason"),
                    e.details.get("sub_account_id") or "__global__",
                )
                for e in recent
                if e.event_type == "risk_kill_switch_tripped"
                and not e.details.get("advisory")
            }
        ),
        "open_drawdown_percent": 0.0,
    }
    assert (
        inputs_from_recent_activity_events(iter(events), now=at).model_dump()
        == expected
    )
    assert (
        inputs_from_recent_activity_events(
            iter(events), now=at, lookback_hours=0
        ).recent_cycle_errors
        == 3
    )


@pytest.mark.parametrize("ending", [b"\n", b"\r", b"\r\n"])
def test_legacy_rows_accept_unicode_strip_and_final_row(
    tmp_path: Path, ending: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    import src.utils.bounded_read as bounded

    monkeypatch.setattr(bounded, "BLOCK_BYTES", 7)
    path = tmp_path / "rows"
    path.write_bytes(ending.join(['\u2003 {"a":1} \u2003'.encode(), b"", b'{"a":2}']))
    rows = [row for row in legacy_text_rows(path, Generation.capture(path)) if row]
    assert rows == ['{"a":1}', '{"a":2}']


def test_exact_retained_selection_without_materializing_all_archives(
    tmp_path: Path,
) -> None:
    base = tmp_path / "activity"
    for name in [
        "activity.jsonl",
        "activity.2020-01.jsonl",
        "activity.2020-02.jsonl",
        "activity.2020-03.jsonl",
        "activity.bad.jsonl",
    ]:
        (tmp_path / name).write_text("")
    assert [s.path.name for s in capture_sources(base, 2, control())] == [
        "activity.jsonl",
        "activity.2020-02.jsonl",
        "activity.2020-03.jsonl",
    ]
    with pytest.raises(SafetyReadUnavailable, match="manifest_limit"):
        capture_sources(
            base, 2, control(replace(SafetyReadLimits(), manifest_bytes=32))
        )


async def test_service_legacy_skips_default_timestamp_and_no_raw_materialization(
    tmp_path: Path,
) -> None:
    at = now_utc()
    path = tmp_path / "activity.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    event(ActivityEventType.CYCLE_ERRORED, at).model_dump(mode="json")
                ),
                "bad json",
                '{"event_type":"bad"}',
                '{"event_type":"llm_timeout"}',
            ]
        )
    )
    service = SafetyReadService()
    try:
        score = await service.score(tmp_path / "activity", 12, [], SafetyCycleBudget())
        assert score.inputs.recent_cycle_errors == 1
        assert score.inputs.recent_llm_timeouts == 1
        assert next(iter(service._reader.summaries.values())).dynamic
    finally:
        service.close()


@pytest.mark.parametrize(
    "content",
    [
        b"[]",
        b"null",
        b'"secret row"',
        b"\xff",
        b'{"details":"secret","event_type":"startup"}\n\xff',
    ],
)
async def test_hard_input_failure_is_fresh_stable_error(
    tmp_path: Path, content: bytes
) -> None:
    (tmp_path / "activity.jsonl").write_bytes(content)
    service = SafetyReadService()
    try:
        with pytest.raises(SafetyReadUnavailable) as raised:
            await service.score(tmp_path / "activity", 12, [], SafetyCycleBudget())
        assert "secret" not in str(raised.value)
        assert raised.value.__cause__ is None
    finally:
        service.close()


async def test_old_summary_requires_readability_generation_and_no_dynamic_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    at = now_utc() - timedelta(days=2)
    path = tmp_path / "activity.jsonl"
    path.write_text(event(ActivityEventType.CYCLE_ERRORED, at).model_dump_json() + "\n")
    service = SafetyReadService()
    try:
        assert (
            await service.score(tmp_path / "activity", 12, [], SafetyCycleBudget())
        ).score == 100
        import src.runtime.safety_reader as reader

        original = reader.legacy_text_rows

        def forbidden(*args: object, **kwargs: object) -> object:
            raise AssertionError("unchanged old archive re-read")

        monkeypatch.setattr(reader, "legacy_text_rows", forbidden)
        assert (
            await service.score(tmp_path / "activity", 12, [], SafetyCycleBudget())
        ).score == 100
        monkeypatch.setattr(reader, "legacy_text_rows", original)
        path.write_text(
            event(ActivityEventType.CYCLE_ERRORED, now_utc()).model_dump_json() + "\n"
        )
        assert (
            await service.score(tmp_path / "activity", 12, [], SafetyCycleBudget())
        ).score == 85
    finally:
        service.close()


async def test_timeout_quarantines_slot_and_keeps_event_loop_responsive(
    tmp_path: Path,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    service = SafetyReadService(replace(SafetyReadLimits(), read_seconds=0.02))
    original = service._reader.evaluate

    def blocked(*args: object, **kwargs: object) -> object:
        entered.set()
        release.wait(2)
        return original(*args, **kwargs)

    service._reader.evaluate = blocked  # type: ignore[method-assign]
    try:
        with pytest.raises(SafetyReadUnavailable, match="deadline"):
            await service.score(tmp_path / "activity", 12, [], SafetyCycleBudget())
        assert entered.is_set()
        assert service._thread is not None and service._thread.daemon
        with pytest.raises(SafetyReadUnavailable, match="reader_busy"):
            await service.score(tmp_path / "activity", 12, [], SafetyCycleBudget())
        release.set()
    finally:
        release.set()
        service.close()


async def test_cancellation_does_not_admit_a_second_worker(tmp_path: Path) -> None:
    release = threading.Event()
    entered = threading.Event()
    service = SafetyReadService()
    original = service._reader.evaluate

    def blocked(*args: object, **kwargs: object) -> object:
        entered.set()
        release.wait(2)
        return original(*args, **kwargs)

    service._reader.evaluate = blocked  # type: ignore[method-assign]
    task = asyncio.create_task(
        service.score(tmp_path / "activity", 12, [], SafetyCycleBudget())
    )
    try:
        for _ in range(100):
            if entered.is_set():
                break
            await asyncio.sleep(0.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(SafetyReadUnavailable, match="reader_busy"):
            await service.score(tmp_path / "activity", 12, [], SafetyCycleBudget())
    finally:
        release.set()
        service.close()


@pytest.mark.parametrize(
    "limits,content,extras",
    [
        (replace(SafetyReadLimits(), row_bytes=4), b"1234567", []),
        (replace(SafetyReadLimits(), read_bytes=2), b'{"event_type":"startup"}', []),
        (
            replace(SafetyReadLimits(), extra_count=0),
            b"",
            [event(ActivityEventType.CYCLE_ERRORED, now_utc())],
        ),
        (
            replace(SafetyReadLimits(), conditions=0),
            b'{"event_type":"risk_kill_switch_tripped"}',
            [],
        ),
    ],
)
async def test_caps_never_produce_healthy_score(
    tmp_path: Path,
    limits: SafetyReadLimits,
    content: bytes,
    extras: list[ActivityEvent],
) -> None:
    (tmp_path / "activity.jsonl").write_bytes(content)
    service = SafetyReadService(limits)
    try:
        with pytest.raises(SafetyReadUnavailable):
            await service.score(tmp_path / "activity", 12, extras, SafetyCycleBudget())
    finally:
        service.close()


def test_close_is_idempotent_without_creating_a_worker() -> None:
    service = SafetyReadService()
    service.close()
    service.close()
    assert service._thread is None


def test_streaming_helper_preserves_drawdown_input_validation() -> None:
    from pydantic import ValidationError

    from src.runtime.safety_score import inputs_from_activity_events

    with pytest.raises(ValidationError):
        inputs_from_activity_events(iter(()), open_drawdown_percent=-1)
    assert (
        inputs_from_activity_events(
            iter(()), open_drawdown_percent=12.5
        ).open_drawdown_percent
        == 12.5
    )

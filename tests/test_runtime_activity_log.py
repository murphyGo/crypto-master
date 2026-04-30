"""Tests for the runtime activity log (Phase 8.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.config import reload_settings
from src.runtime import activity_log, jsonl_rotator
from src.runtime.activity_log import (
    ActivityEvent,
    ActivityEventType,
    ActivityLog,
)


def _set_clock(monkeypatch: pytest.MonkeyPatch, when: datetime) -> None:
    """Pin ``now_utc()`` for both the rotator and the activity-log models.

    Phase 21.2: write-time wall-clock comes from ``now_utc()`` in two
    spots — the rotator's active-month token and ``ActivityEvent``'s
    default ``timestamp`` factory. Patching both keeps tests
    deterministic across the boundary.
    """
    fixed = when if when.tzinfo is not None else when.replace(tzinfo=timezone.utc)
    monkeypatch.setattr(jsonl_rotator, "now_utc", lambda: fixed)
    monkeypatch.setattr(activity_log, "now_utc", lambda: fixed)


# =============================================================================
# Append + read round-trip
# =============================================================================


def test_constructor_respects_settings_data_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default activity path is rooted under Settings.data_dir (Phase 10.5)."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    reload_settings()
    try:
        log = ActivityLog()
    finally:
        # Reset the module-level singleton so other tests aren't affected.
        monkeypatch.delenv("DATA_DIR", raising=False)
        reload_settings()

    assert log.path == tmp_path / "runtime" / "activity.jsonl"
    assert tmp_path in log.path.parents


def test_append_creates_parent_directory(tmp_path: Path) -> None:
    log = ActivityLog(path=tmp_path / "nested" / "activity.jsonl")

    log.append(ActivityEventType.STARTUP, "engine up")

    # Phase 10.4 routes writes through the monthly rotator. The active
    # file lives next to ``log.path`` with a ``YYYY-MM`` token; the
    # parent directory must still exist.
    assert log.path.parent.is_dir()
    rotated = list(log.path.parent.glob("activity.*.jsonl"))
    assert len(rotated) == 1


def test_append_returns_event(tmp_path: Path) -> None:
    log = ActivityLog(path=tmp_path / "activity.jsonl")

    event = log.append(
        ActivityEventType.CYCLE_STARTED,
        "cycle 1",
        details={"cycle_index": 1},
        cycle_id="abc",
    )

    assert isinstance(event, ActivityEvent)
    assert event.event_type == ActivityEventType.CYCLE_STARTED.value
    assert event.cycle_id == "abc"
    assert event.details == {"cycle_index": 1}


def test_append_then_read_all_round_trip(tmp_path: Path) -> None:
    log = ActivityLog(path=tmp_path / "activity.jsonl")
    log.append(ActivityEventType.STARTUP, "up")
    log.append(
        ActivityEventType.CYCLE_STARTED,
        "cycle 1",
        details={"cycle_index": 1},
        cycle_id="c1",
    )
    log.append(
        ActivityEventType.CYCLE_COMPLETED,
        "cycle 1 done",
        cycle_id="c1",
    )

    events = log.read_all()

    assert [e.event_type for e in events] == [
        ActivityEventType.STARTUP.value,
        ActivityEventType.CYCLE_STARTED.value,
        ActivityEventType.CYCLE_COMPLETED.value,
    ]
    assert events[1].details == {"cycle_index": 1}
    assert events[1].cycle_id == "c1"


def test_read_all_missing_file_returns_empty(tmp_path: Path) -> None:
    log = ActivityLog(path=tmp_path / "never_written.jsonl")

    assert log.read_all() == []


def test_read_all_skips_malformed_lines(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    log = ActivityLog(path=tmp_path / "activity.jsonl")
    log.append(ActivityEventType.STARTUP, "up")
    # Append a corrupt trailing line directly to the rotated file.
    rotated = next(tmp_path.glob("activity.*.jsonl"))
    with rotated.open("a", encoding="utf-8") as fh:
        fh.write("{not json\n")

    events = log.read_all()

    assert len(events) == 1
    assert events[0].event_type == ActivityEventType.STARTUP.value


# =============================================================================
# tail
# =============================================================================


def test_tail_returns_last_n(tmp_path: Path) -> None:
    log = ActivityLog(path=tmp_path / "activity.jsonl")
    for i in range(10):
        log.append(ActivityEventType.CYCLE_STARTED, f"cycle {i}")

    tail = log.tail(n=3)

    assert len(tail) == 3
    assert [e.message for e in tail] == ["cycle 7", "cycle 8", "cycle 9"]


def test_tail_returns_all_when_n_exceeds_count(tmp_path: Path) -> None:
    log = ActivityLog(path=tmp_path / "activity.jsonl")
    log.append(ActivityEventType.STARTUP, "a")
    log.append(ActivityEventType.SHUTDOWN, "b")

    tail = log.tail(n=100)

    assert len(tail) == 2


def test_tail_n_zero_returns_empty(tmp_path: Path) -> None:
    log = ActivityLog(path=tmp_path / "activity.jsonl")
    log.append(ActivityEventType.STARTUP, "a")

    assert log.tail(n=0) == []


def test_tail_negative_n_returns_empty(tmp_path: Path) -> None:
    log = ActivityLog(path=tmp_path / "activity.jsonl")
    log.append(ActivityEventType.STARTUP, "a")

    assert log.tail(n=-5) == []


# =============================================================================
# filter
# =============================================================================


def test_filter_by_cycle_id(tmp_path: Path) -> None:
    log = ActivityLog(path=tmp_path / "activity.jsonl")
    log.append(ActivityEventType.CYCLE_STARTED, "c1", cycle_id="c1")
    log.append(ActivityEventType.PROPOSAL_GENERATED, "p", cycle_id="c1")
    log.append(ActivityEventType.CYCLE_STARTED, "c2", cycle_id="c2")

    events = log.filter(cycle_id="c1")

    assert len(events) == 2
    assert all(e.cycle_id == "c1" for e in events)


def test_filter_by_event_type_enum(tmp_path: Path) -> None:
    log = ActivityLog(path=tmp_path / "activity.jsonl")
    log.append(ActivityEventType.STARTUP, "up")
    log.append(ActivityEventType.CYCLE_STARTED, "cycle")
    log.append(ActivityEventType.SHUTDOWN, "down")

    events = log.filter(event_type=ActivityEventType.CYCLE_STARTED)

    assert len(events) == 1
    assert events[0].event_type == ActivityEventType.CYCLE_STARTED.value


def test_filter_by_event_type_string(tmp_path: Path) -> None:
    """Filter accepts the raw string value for dashboard convenience."""
    log = ActivityLog(path=tmp_path / "activity.jsonl")
    log.append(ActivityEventType.STARTUP, "up")
    log.append(ActivityEventType.CYCLE_STARTED, "cycle")

    events = log.filter(event_type="startup")

    assert len(events) == 1
    assert events[0].event_type == "startup"


# =============================================================================
# Phase 10.4 — monthly rotation + retention
# =============================================================================


def test_rotator_integration_merges_across_months(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Writes spanning two months produce two files; reads see them merged."""
    log = ActivityLog(path=tmp_path / "activity.jsonl")

    _set_clock(monkeypatch, datetime(2026, 3, 15, 9, 0, 0))
    log.append(ActivityEventType.STARTUP, "march startup")

    _set_clock(monkeypatch, datetime(2026, 4, 1, 0, 0, 1))
    log.append(ActivityEventType.CYCLE_STARTED, "april cycle")

    rotated = sorted(tmp_path.glob("activity.*.jsonl"))
    assert [p.name for p in rotated] == [
        "activity.2026-03.jsonl",
        "activity.2026-04.jsonl",
    ]

    events = log.read_all()
    assert [e.message for e in events] == ["march startup", "april cycle"]


def test_filter_combined_predicates(tmp_path: Path) -> None:
    log = ActivityLog(path=tmp_path / "activity.jsonl")
    log.append(ActivityEventType.CYCLE_STARTED, "c1", cycle_id="c1")
    log.append(ActivityEventType.PROPOSAL_GENERATED, "p", cycle_id="c1")
    log.append(ActivityEventType.PROPOSAL_GENERATED, "p", cycle_id="c2")

    events = log.filter(
        cycle_id="c1",
        event_type=ActivityEventType.PROPOSAL_GENERATED,
    )

    assert len(events) == 1
    assert events[0].cycle_id == "c1"
    assert events[0].event_type == ActivityEventType.PROPOSAL_GENERATED.value

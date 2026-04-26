"""Tests for the runtime activity log (Phase 8.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.runtime.activity_log import (
    ActivityEvent,
    ActivityEventType,
    ActivityLog,
)

# =============================================================================
# Append + read round-trip
# =============================================================================


def test_append_creates_parent_directory(tmp_path: Path) -> None:
    log = ActivityLog(path=tmp_path / "nested" / "activity.jsonl")

    log.append(ActivityEventType.STARTUP, "engine up")

    assert log.path.exists()
    assert log.path.parent.is_dir()


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
    # Append a corrupt trailing line.
    with log.path.open("a", encoding="utf-8") as fh:
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

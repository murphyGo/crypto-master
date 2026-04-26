"""Tests for the Engine status page (Phase 8.2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.dashboard.pages.engine import (
    CycleSummary,
    aggregate_cycles,
    build_cycle_duration_dataframe,
    build_cycles_dataframe,
    build_summary_metrics,
    build_timeline_dataframe,
)
from src.runtime.activity_log import ActivityEvent, ActivityEventType, ActivityLog

# =============================================================================
# Helpers
# =============================================================================


def make_event(
    *,
    event_type: ActivityEventType,
    timestamp: datetime,
    cycle_id: str | None = None,
    message: str = "",
    details: dict | None = None,
) -> ActivityEvent:
    return ActivityEvent(
        event_type=event_type,
        timestamp=timestamp,
        message=message,
        details=details or {},
        cycle_id=cycle_id,
    )


def make_cycle_events(
    cycle_id: str,
    *,
    started_at: datetime,
    duration_seconds: float = 12.0,
    proposals_generated: int = 0,
    proposals_accepted: int = 0,
    proposals_rejected: int = 0,
    positions_opened: int = 0,
    positions_closed: int = 0,
    errored: bool = False,
    completed: bool = True,
) -> list[ActivityEvent]:
    """Synthesize a realistic cycle's worth of events."""
    events: list[ActivityEvent] = [
        make_event(
            event_type=ActivityEventType.CYCLE_STARTED,
            timestamp=started_at,
            cycle_id=cycle_id,
            message="cycle begin",
        )
    ]
    cursor = started_at
    for _i in range(proposals_generated):
        cursor += timedelta(seconds=1)
        events.append(
            make_event(
                event_type=ActivityEventType.PROPOSAL_GENERATED,
                timestamp=cursor,
                cycle_id=cycle_id,
                message=f"prop-{_i}",
            )
        )
    for _i in range(proposals_accepted):
        cursor += timedelta(seconds=1)
        events.append(
            make_event(
                event_type=ActivityEventType.PROPOSAL_ACCEPTED,
                timestamp=cursor,
                cycle_id=cycle_id,
                message=f"acc-{_i}",
            )
        )
    for _i in range(proposals_rejected):
        cursor += timedelta(seconds=1)
        events.append(
            make_event(
                event_type=ActivityEventType.PROPOSAL_REJECTED,
                timestamp=cursor,
                cycle_id=cycle_id,
            )
        )
    for _i in range(positions_opened):
        cursor += timedelta(seconds=1)
        events.append(
            make_event(
                event_type=ActivityEventType.POSITION_OPENED,
                timestamp=cursor,
                cycle_id=cycle_id,
            )
        )
    for _i in range(positions_closed):
        cursor += timedelta(seconds=1)
        events.append(
            make_event(
                event_type=ActivityEventType.POSITION_CLOSED,
                timestamp=cursor,
                cycle_id=cycle_id,
            )
        )
    if completed:
        events.append(
            make_event(
                event_type=(
                    ActivityEventType.CYCLE_ERRORED
                    if errored
                    else ActivityEventType.CYCLE_COMPLETED
                ),
                timestamp=started_at + timedelta(seconds=duration_seconds),
                cycle_id=cycle_id,
                message="boom" if errored else "ok",
            )
        )
    return events


# =============================================================================
# aggregate_cycles
# =============================================================================


def test_aggregate_cycles_empty() -> None:
    assert aggregate_cycles([]) == []


def test_aggregate_cycles_skips_events_without_cycle_id() -> None:
    """STARTUP / SHUTDOWN have no cycle_id and must not become cycles."""
    events = [
        make_event(
            event_type=ActivityEventType.STARTUP,
            timestamp=datetime(2026, 4, 27, 12, 0),
            cycle_id=None,
        ),
        make_event(
            event_type=ActivityEventType.SHUTDOWN,
            timestamp=datetime(2026, 4, 27, 12, 30),
            cycle_id=None,
        ),
    ]

    assert aggregate_cycles(events) == []


def test_aggregate_cycles_one_complete_cycle() -> None:
    started = datetime(2026, 4, 27, 12, 0, 0)
    events = make_cycle_events(
        "cycle-a",
        started_at=started,
        duration_seconds=10.0,
        proposals_generated=3,
        proposals_accepted=1,
        proposals_rejected=2,
        positions_opened=1,
        positions_closed=0,
    )

    cycles = aggregate_cycles(events)

    assert len(cycles) == 1
    c = cycles[0]
    assert c.cycle_id == "cycle-a"
    assert c.started_at == started
    assert c.completed_at == started + timedelta(seconds=10)
    assert c.duration_seconds == pytest.approx(10.0)
    assert c.proposals_generated == 3
    assert c.proposals_accepted == 1
    assert c.proposals_rejected == 2
    assert c.positions_opened == 1
    assert c.positions_closed == 0
    assert c.errored is False
    assert c.error_message is None


def test_aggregate_cycles_running_cycle_has_no_duration() -> None:
    """A cycle without a CYCLE_COMPLETED event is in flight."""
    started = datetime(2026, 4, 27, 12, 0, 0)
    events = make_cycle_events(
        "cycle-running",
        started_at=started,
        completed=False,
        proposals_generated=1,
    )

    cycles = aggregate_cycles(events)

    assert len(cycles) == 1
    assert cycles[0].started_at == started
    assert cycles[0].completed_at is None
    assert cycles[0].duration_seconds is None
    assert cycles[0].errored is False


def test_aggregate_cycles_errored_cycle_marked() -> None:
    started = datetime(2026, 4, 27, 12, 0, 0)
    events = make_cycle_events(
        "cycle-bad",
        started_at=started,
        duration_seconds=2.0,
        errored=True,
    )

    cycles = aggregate_cycles(events)

    assert len(cycles) == 1
    assert cycles[0].errored is True
    assert cycles[0].error_message == "boom"
    assert cycles[0].duration_seconds == pytest.approx(2.0)


def test_aggregate_cycles_orders_newest_first() -> None:
    early = make_cycle_events("cycle-early", started_at=datetime(2026, 4, 27, 12, 0, 0))
    late = make_cycle_events("cycle-late", started_at=datetime(2026, 4, 27, 13, 0, 0))

    cycles = aggregate_cycles([*early, *late])

    assert [c.cycle_id for c in cycles] == ["cycle-late", "cycle-early"]


def test_aggregate_cycles_handles_unsorted_events() -> None:
    """Aggregator must not assume events are pre-sorted."""
    started = datetime(2026, 4, 27, 12, 0, 0)
    events = make_cycle_events(
        "c-shuffled",
        started_at=started,
        duration_seconds=5.0,
        proposals_generated=2,
    )
    # Reverse to confirm sorting happens internally.
    events.reverse()

    cycles = aggregate_cycles(events)

    assert cycles[0].started_at == started
    assert cycles[0].duration_seconds == pytest.approx(5.0)


# =============================================================================
# build_summary_metrics
# =============================================================================


def test_summary_metrics_empty() -> None:
    metrics = build_summary_metrics([], [])

    assert metrics["total_cycles"] == 0
    assert metrics["last_cycle_started_at"] is None
    assert metrics["last_cycle_status"] is None
    assert metrics["avg_duration_seconds"] is None
    assert metrics["errored_cycles"] == 0
    assert metrics["positions_opened_total"] == 0
    assert metrics["positions_closed_total"] == 0


def test_summary_metrics_aggregates_across_cycles() -> None:
    cycles = [
        # newest first
        CycleSummary(
            cycle_id="c3",
            started_at=datetime(2026, 4, 27, 13, 0),
            completed_at=datetime(2026, 4, 27, 13, 0, 10),
            duration_seconds=10.0,
            proposals_generated=2,
            proposals_accepted=1,
            proposals_rejected=1,
            positions_opened=1,
            positions_closed=1,
            errored=False,
            error_message=None,
        ),
        CycleSummary(
            cycle_id="c2",
            started_at=datetime(2026, 4, 27, 12, 30),
            completed_at=datetime(2026, 4, 27, 12, 30, 20),
            duration_seconds=20.0,
            proposals_generated=0,
            proposals_accepted=0,
            proposals_rejected=0,
            positions_opened=0,
            positions_closed=2,
            errored=False,
            error_message=None,
        ),
        CycleSummary(
            cycle_id="c1",
            started_at=datetime(2026, 4, 27, 12, 0),
            completed_at=datetime(2026, 4, 27, 12, 0, 30),
            duration_seconds=30.0,
            proposals_generated=1,
            proposals_accepted=0,
            proposals_rejected=1,
            positions_opened=0,
            positions_closed=0,
            errored=True,
            error_message="boom",
        ),
    ]

    metrics = build_summary_metrics([], cycles)

    assert metrics["total_cycles"] == 3
    assert metrics["last_cycle_started_at"] == datetime(2026, 4, 27, 13, 0)
    assert metrics["last_cycle_status"] == "ok"
    assert metrics["avg_duration_seconds"] == pytest.approx(20.0)
    assert metrics["errored_cycles"] == 1
    assert metrics["positions_opened_total"] == 1
    assert metrics["positions_closed_total"] == 3


def test_summary_metrics_running_last_cycle() -> None:
    cycles = [
        CycleSummary(
            cycle_id="c-running",
            started_at=datetime(2026, 4, 27, 13, 0),
            completed_at=None,
            duration_seconds=None,
            proposals_generated=0,
            proposals_accepted=0,
            proposals_rejected=0,
            positions_opened=0,
            positions_closed=0,
            errored=False,
            error_message=None,
        ),
    ]

    metrics = build_summary_metrics([], cycles)

    assert metrics["last_cycle_status"] == "running"
    # No completed cycles → no avg.
    assert metrics["avg_duration_seconds"] is None


def test_summary_metrics_errored_last_cycle() -> None:
    cycles = [
        CycleSummary(
            cycle_id="c-bad",
            started_at=datetime(2026, 4, 27, 13, 0),
            completed_at=datetime(2026, 4, 27, 13, 0, 5),
            duration_seconds=5.0,
            proposals_generated=0,
            proposals_accepted=0,
            proposals_rejected=0,
            positions_opened=0,
            positions_closed=0,
            errored=True,
            error_message="kaput",
        ),
    ]

    metrics = build_summary_metrics([], cycles)

    assert metrics["last_cycle_status"] == "errored"
    assert metrics["errored_cycles"] == 1


# =============================================================================
# DataFrame helpers
# =============================================================================


def test_cycles_dataframe_empty_keeps_columns() -> None:
    df = build_cycles_dataframe([])

    assert df.empty
    assert "Cycle" in df.columns
    assert "Status" in df.columns


def test_cycles_dataframe_marks_status_per_row() -> None:
    cycles = aggregate_cycles(
        [
            *make_cycle_events(
                "c-ok",
                started_at=datetime(2026, 4, 27, 12, 0),
                duration_seconds=2.0,
            ),
            *make_cycle_events(
                "c-running",
                started_at=datetime(2026, 4, 27, 12, 5),
                completed=False,
            ),
            *make_cycle_events(
                "c-bad",
                started_at=datetime(2026, 4, 27, 12, 10),
                duration_seconds=1.0,
                errored=True,
            ),
        ]
    )

    df = build_cycles_dataframe(cycles)

    by_id = {row["Cycle"]: row["Status"] for _, row in df.iterrows()}
    assert by_id["c-ok"[:8]] == "ok"
    assert by_id["c-runnin"] == "running"
    assert by_id["c-bad"[:8]] == "errored"


def test_cycle_duration_dataframe_skips_running_cycles() -> None:
    cycles = aggregate_cycles(
        [
            *make_cycle_events(
                "c-ok",
                started_at=datetime(2026, 4, 27, 12, 0),
                duration_seconds=4.0,
            ),
            *make_cycle_events(
                "c-running",
                started_at=datetime(2026, 4, 27, 12, 5),
                completed=False,
            ),
        ]
    )

    df = build_cycle_duration_dataframe(cycles)

    assert len(df) == 1
    assert df.iloc[0]["cycle_id"] == "c-ok"[:8]


def test_cycle_duration_dataframe_chronological() -> None:
    cycles = aggregate_cycles(
        [
            *make_cycle_events(
                "c-late",
                started_at=datetime(2026, 4, 27, 13, 0),
                duration_seconds=2.0,
            ),
            *make_cycle_events(
                "c-early",
                started_at=datetime(2026, 4, 27, 12, 0),
                duration_seconds=3.0,
            ),
        ]
    )

    df = build_cycle_duration_dataframe(cycles)

    # Chart reads left-to-right as time progresses.
    assert list(df["cycle_id"]) == ["c-early"[:8], "c-late"[:8]]


def test_cycle_duration_dataframe_empty() -> None:
    df = build_cycle_duration_dataframe([])

    assert df.empty
    assert list(df.columns) == ["cycle_id", "duration_seconds"]


def test_timeline_dataframe_orders_newest_first() -> None:
    events = [
        make_event(
            event_type=ActivityEventType.STARTUP,
            timestamp=datetime(2026, 4, 27, 12, 0),
            message="up",
        ),
        make_event(
            event_type=ActivityEventType.CYCLE_STARTED,
            timestamp=datetime(2026, 4, 27, 12, 5),
            cycle_id="c1",
            message="cycle 1 begin",
        ),
        make_event(
            event_type=ActivityEventType.SHUTDOWN,
            timestamp=datetime(2026, 4, 27, 12, 30),
            message="down",
        ),
    ]

    df = build_timeline_dataframe(events)

    assert list(df["Event"]) == [
        ActivityEventType.SHUTDOWN.value,
        ActivityEventType.CYCLE_STARTED.value,
        ActivityEventType.STARTUP.value,
    ]


def test_timeline_dataframe_truncates_long_details() -> None:
    big_payload = {"k": "x" * 1000}
    events = [
        make_event(
            event_type=ActivityEventType.PROPOSAL_GENERATED,
            timestamp=datetime(2026, 4, 27, 12, 0),
            cycle_id="c1",
            details=big_payload,
        ),
    ]

    df = build_timeline_dataframe(events)

    details_str = df.iloc[0]["Details"]
    # Truncated and ellipsised.
    assert details_str.endswith("…")
    assert len(details_str) <= 201


def test_timeline_dataframe_empty_keeps_columns() -> None:
    df = build_timeline_dataframe([])

    assert df.empty
    assert list(df.columns) == ["Timestamp", "Event", "Message", "Cycle", "Details"]


# =============================================================================
# AppTest smoke
# =============================================================================


def test_engine_page_renders_empty_state(tmp_path: Path) -> None:
    """Page must not crash when the activity log is empty / missing."""
    from streamlit.testing.v1 import AppTest

    log_path = tmp_path / "activity.jsonl"

    script = f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})
from pathlib import Path
from src.dashboard.pages.engine import render
from src.runtime.activity_log import ActivityLog

render(activity_log=ActivityLog(path=Path({str(log_path)!r})))
"""
    at = AppTest.from_string(script).run(timeout=10)

    assert not at.exception, [str(e) for e in at.exception]
    info_text = " ".join(i.value for i in at.info)
    assert "Engine activity log is empty" in info_text


def test_engine_page_renders_populated(tmp_path: Path) -> None:
    """End-to-end: a real cycle in the log surfaces in the summary cards."""
    from streamlit.testing.v1 import AppTest

    log_path = tmp_path / "activity.jsonl"
    log = ActivityLog(path=log_path)
    started = datetime(2026, 4, 27, 12, 0, 0)
    for ev in make_cycle_events(
        "c-smoke",
        started_at=started,
        duration_seconds=3.0,
        proposals_generated=1,
        proposals_accepted=1,
        positions_opened=1,
    ):
        log.append(
            (
                ev.event_type
                if isinstance(ev.event_type, ActivityEventType)
                else ActivityEventType(ev.event_type)
            ),
            ev.message,
            details=ev.details,
            cycle_id=ev.cycle_id,
        )

    script = f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})
from pathlib import Path
from src.dashboard.pages.engine import render
from src.runtime.activity_log import ActivityLog

render(activity_log=ActivityLog(path=Path({str(log_path)!r})))
"""
    at = AppTest.from_string(script).run(timeout=15)

    assert not at.exception, [str(e) for e in at.exception]
    titles = [t.value for t in at.title]
    assert any("Engine" in t for t in titles), titles

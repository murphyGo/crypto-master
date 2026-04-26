"""Engine status dashboard page (Phase 8.2).

Reads the runtime ``ActivityLog`` (Phase 8.1) and surfaces:

* Summary cards — total cycles, last cycle status, average cycle
  duration, errored-cycle count, positions opened/closed in window.
* Recent cycles table — per-cycle aggregation (start, duration,
  proposals/opened/closed counts) so the operator can scan
  cycle-by-cycle progress at a glance.
* Cycle-duration bar chart — quick visual of how long each cycle
  took; spikes flag scan/monitor latency issues.
* Activity timeline — tail of the raw event log with a multi-select
  filter on ``ActivityEventType``.

The page is purely a reader of ``data/runtime/activity.jsonl``; it
neither mutates engine state nor talks to the engine in-process. The
engine writes JSONL; this page reads it. Same separation as the
Feedback Loop page.

Related Requirements:
- FR-030: Technique Generation Status (extends to engine cycle status)
- FR-032 / NFR-003: Streamlit dashboard
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import streamlit as st

from src.logger import get_logger
from src.runtime.activity_log import ActivityEvent, ActivityEventType, ActivityLog

logger = get_logger("crypto_master.dashboard.engine")


DEFAULT_TAIL_LIMIT = 300
RECENT_CYCLES_LIMIT = 25
DURATION_HISTOGRAM_LIMIT = 50


# =============================================================================
# Cycle aggregation
# =============================================================================


@dataclass
class CycleSummary:
    """Per-cycle roll-up derived from raw activity events.

    A cycle is identified by ``ActivityEvent.cycle_id``; events with
    no cycle id (process-level STARTUP / SHUTDOWN) are not part of any
    cycle and are excluded from cycle aggregation.
    """

    cycle_id: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    proposals_generated: int
    proposals_accepted: int
    proposals_rejected: int
    positions_opened: int
    positions_closed: int
    errored: bool
    error_message: str | None


def aggregate_cycles(events: list[ActivityEvent]) -> list[CycleSummary]:
    """Group events by ``cycle_id`` and roll them up to ``CycleSummary``.

    Events without a ``cycle_id`` (STARTUP, SHUTDOWN) are skipped.
    Cycles are returned newest-first by ``started_at``. Cycles with
    no ``CYCLE_STARTED`` event still appear (their ``started_at`` is
    ``None``); this can happen if the activity log was truncated
    mid-cycle and the dashboard is reading the surviving tail.

    Args:
        events: Raw activity events, in any order.

    Returns:
        One ``CycleSummary`` per unique non-null ``cycle_id``.
    """
    by_cycle: dict[str, list[ActivityEvent]] = {}
    for ev in events:
        if ev.cycle_id is None:
            continue
        by_cycle.setdefault(ev.cycle_id, []).append(ev)

    summaries: list[CycleSummary] = []
    for cycle_id, evs in by_cycle.items():
        evs_sorted = sorted(evs, key=lambda e: e.timestamp)
        summaries.append(_summarize_cycle(cycle_id, evs_sorted))

    summaries.sort(key=_sort_key_newest_first, reverse=True)
    return summaries


def _summarize_cycle(
    cycle_id: str,
    events: list[ActivityEvent],
) -> CycleSummary:
    """Build a ``CycleSummary`` from one cycle's already-sorted events."""
    started_at = _first_event_timestamp(events, ActivityEventType.CYCLE_STARTED.value)
    end_event = _first_event(
        events,
        (
            ActivityEventType.CYCLE_COMPLETED.value,
            ActivityEventType.CYCLE_ERRORED.value,
        ),
    )
    completed_at = end_event.timestamp if end_event is not None else None
    errored = any(e.event_type == ActivityEventType.CYCLE_ERRORED.value for e in events)

    if started_at is not None and completed_at is not None:
        duration = (completed_at - started_at).total_seconds()
    else:
        duration = None

    counts = _count_events(events)
    error_message = (
        end_event.message
        if end_event is not None
        and end_event.event_type == ActivityEventType.CYCLE_ERRORED.value
        else None
    )

    return CycleSummary(
        cycle_id=cycle_id,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=duration,
        proposals_generated=counts[ActivityEventType.PROPOSAL_GENERATED.value],
        proposals_accepted=counts[ActivityEventType.PROPOSAL_ACCEPTED.value],
        proposals_rejected=counts[ActivityEventType.PROPOSAL_REJECTED.value],
        positions_opened=counts[ActivityEventType.POSITION_OPENED.value],
        positions_closed=counts[ActivityEventType.POSITION_CLOSED.value],
        errored=errored,
        error_message=error_message,
    )


def _first_event_timestamp(
    events: list[ActivityEvent],
    event_type_value: str,
) -> datetime | None:
    for e in events:
        if e.event_type == event_type_value:
            return e.timestamp
    return None


def _first_event(
    events: list[ActivityEvent],
    event_type_values: tuple[str, ...],
) -> ActivityEvent | None:
    for e in events:
        if e.event_type in event_type_values:
            return e
    return None


def _count_events(events: list[ActivityEvent]) -> dict[str, int]:
    counted = {
        ActivityEventType.PROPOSAL_GENERATED.value: 0,
        ActivityEventType.PROPOSAL_ACCEPTED.value: 0,
        ActivityEventType.PROPOSAL_REJECTED.value: 0,
        ActivityEventType.POSITION_OPENED.value: 0,
        ActivityEventType.POSITION_CLOSED.value: 0,
    }
    for e in events:
        if e.event_type in counted:
            counted[e.event_type] += 1
    return counted


def _sort_key_newest_first(summary: CycleSummary) -> datetime:
    """Sort key: cycles without ``started_at`` go last (epoch-min)."""
    return summary.started_at or datetime.min


# =============================================================================
# Pure DataFrame helpers (testable without Streamlit)
# =============================================================================


def build_summary_metrics(
    events: list[ActivityEvent],
    cycles: list[CycleSummary],
) -> dict[str, object]:
    """Roll up the summary cards.

    Returned dict keys:
    - ``total_cycles``: number of distinct cycles in the log.
    - ``last_cycle_started_at``: timestamp of the most recent
      ``CYCLE_STARTED`` (``None`` if no cycles).
    - ``last_cycle_status``: ``"errored"`` / ``"ok"`` / ``"running"``
      / ``None``. ``running`` means the most recent cycle has no
      completion event yet.
    - ``avg_duration_seconds``: average over completed cycles, or
      ``None`` when no cycle has completed.
    - ``errored_cycles``: count of cycles whose ``errored`` flag is
      set.
    - ``positions_opened_total`` / ``positions_closed_total``:
      summed across all cycles in the log.
    """
    if not cycles:
        return {
            "total_cycles": 0,
            "last_cycle_started_at": None,
            "last_cycle_status": None,
            "avg_duration_seconds": None,
            "errored_cycles": 0,
            "positions_opened_total": 0,
            "positions_closed_total": 0,
        }

    durations = [c.duration_seconds for c in cycles if c.duration_seconds is not None]
    avg = sum(durations) / len(durations) if durations else None

    last = cycles[0]
    if last.errored:
        last_status = "errored"
    elif last.completed_at is None:
        last_status = "running"
    else:
        last_status = "ok"

    return {
        "total_cycles": len(cycles),
        "last_cycle_started_at": last.started_at,
        "last_cycle_status": last_status,
        "avg_duration_seconds": avg,
        "errored_cycles": sum(1 for c in cycles if c.errored),
        "positions_opened_total": sum(c.positions_opened for c in cycles),
        "positions_closed_total": sum(c.positions_closed for c in cycles),
    }


def build_cycles_dataframe(cycles: list[CycleSummary]) -> pd.DataFrame:
    """Build the recent-cycles table.

    Columns are picked for at-a-glance scanning: short cycle id,
    when it started, duration, status, and the per-cycle counts that
    matter most operationally (proposals + opens + closes).
    """
    columns = [
        "Cycle",
        "Started",
        "Duration (s)",
        "Status",
        "Proposals",
        "Accepted",
        "Rejected",
        "Opened",
        "Closed",
    ]
    if not cycles:
        return pd.DataFrame(columns=columns)

    rows = []
    for c in cycles:
        if c.errored:
            status = "errored"
        elif c.completed_at is None:
            status = "running"
        else:
            status = "ok"

        rows.append(
            {
                "Cycle": c.cycle_id[:8],
                "Started": c.started_at,
                "Duration (s)": (
                    round(c.duration_seconds, 2)
                    if c.duration_seconds is not None
                    else None
                ),
                "Status": status,
                "Proposals": c.proposals_generated,
                "Accepted": c.proposals_accepted,
                "Rejected": c.proposals_rejected,
                "Opened": c.positions_opened,
                "Closed": c.positions_closed,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def build_cycle_duration_dataframe(
    cycles: list[CycleSummary],
) -> pd.DataFrame:
    """Series of completed-cycle durations for the bar chart.

    Cycles missing a ``duration_seconds`` (no end event yet) are
    dropped — the chart visualizes finished cycles only. Returned in
    chronological order so the chart reads left-to-right as time
    progresses.
    """
    columns = ["cycle_id", "duration_seconds"]
    completed = [c for c in cycles if c.duration_seconds is not None]
    if not completed:
        return pd.DataFrame(columns=columns)

    completed_sorted = sorted(completed, key=lambda c: c.started_at or datetime.min)
    rows = [
        {
            "cycle_id": c.cycle_id[:8],
            "duration_seconds": c.duration_seconds,
        }
        for c in completed_sorted
    ]
    return pd.DataFrame(rows, columns=columns)


def build_timeline_dataframe(events: list[ActivityEvent]) -> pd.DataFrame:
    """Build the activity-timeline table.

    Events are sorted newest-first so the operator sees fresh activity
    at the top. ``Details`` is JSON-serialized and truncated to keep
    the column width sane in Streamlit.
    """
    columns = ["Timestamp", "Event", "Message", "Cycle", "Details"]
    if not events:
        return pd.DataFrame(columns=columns)

    rows = []
    for e in sorted(events, key=lambda ev: ev.timestamp, reverse=True):
        details_str = (
            json.dumps(e.details, default=str, sort_keys=True) if e.details else ""
        )
        rows.append(
            {
                "Timestamp": e.timestamp,
                "Event": e.event_type,
                "Message": e.message,
                "Cycle": (e.cycle_id or "—")[:8],
                "Details": (
                    details_str[:200] + "…" if len(details_str) > 200 else details_str
                ),
            }
        )
    return pd.DataFrame(rows, columns=columns)


# =============================================================================
# Streamlit render
# =============================================================================


def render(
    activity_log: ActivityLog | None = None,
    tail_limit: int = DEFAULT_TAIL_LIMIT,
) -> None:
    """Render the Engine page.

    Args:
        activity_log: Override the source. Defaults to a fresh
            ``ActivityLog()`` reading from
            ``data/runtime/activity.jsonl``.
        tail_limit: Cap on how many timeline rows to render. The
            full event log is still used for cycle aggregation;
            this only bounds the timeline table.
    """
    log = activity_log or ActivityLog()
    events = log.read_all()

    st.title("⚙️ Engine")
    st.caption("Trading engine cycles, per-cycle stats, and the live activity stream.")

    if not events:
        st.info(
            "Engine activity log is empty. The runtime hasn't started yet, "
            f"or `{log.path}` doesn't exist at this path."
        )
        return

    cycles = aggregate_cycles(events)
    metrics = build_summary_metrics(events, cycles)

    # ---- Summary cards ----
    st.subheader("Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Cycles", metrics["total_cycles"])
    last_at = metrics["last_cycle_started_at"]
    c2.metric(
        "Last cycle",
        last_at.isoformat(timespec="seconds") if isinstance(last_at, datetime) else "—",
    )
    c3.metric("Last status", metrics["last_cycle_status"] or "—")
    avg = metrics["avg_duration_seconds"]
    c4.metric(
        "Avg duration",
        f"{float(avg):.1f}s" if isinstance(avg, (int, float)) else "—",
    )
    c5.metric("Errored cycles", metrics["errored_cycles"])

    c6, c7 = st.columns(2)
    c6.metric("Positions opened (total)", metrics["positions_opened_total"])
    c7.metric("Positions closed (total)", metrics["positions_closed_total"])

    # ---- Recent cycles table ----
    st.subheader("Recent Cycles")
    cycles_df = build_cycles_dataframe(cycles[:RECENT_CYCLES_LIMIT])
    if cycles_df.empty:
        st.info("No cycles recorded yet.")
    else:
        st.dataframe(cycles_df, hide_index=True, use_container_width=True)

    # ---- Cycle-duration histogram ----
    st.subheader("Cycle Duration")
    duration_df = build_cycle_duration_dataframe(cycles[:DURATION_HISTOGRAM_LIMIT])
    if duration_df.empty:
        st.info(
            "No completed cycles yet — duration chart will populate once "
            "the engine finishes its first cycle."
        )
    else:
        st.bar_chart(
            duration_df.set_index("cycle_id")["duration_seconds"],
            use_container_width=True,
        )

    # ---- Activity timeline ----
    st.subheader("Activity Timeline")
    all_event_types = sorted({e.event_type for e in events})
    selected_types = st.multiselect(
        "Event types",
        options=all_event_types,
        default=all_event_types,
    )
    tail_events = events[-tail_limit:] if len(events) > tail_limit else events
    filtered = [e for e in tail_events if e.event_type in selected_types]
    timeline_df = build_timeline_dataframe(filtered)
    if timeline_df.empty:
        st.info("No events match the selected filter.")
    else:
        st.dataframe(timeline_df, hide_index=True, use_container_width=True)


__all__ = [
    "CycleSummary",
    "aggregate_cycles",
    "build_cycle_duration_dataframe",
    "build_cycles_dataframe",
    "build_summary_metrics",
    "build_timeline_dataframe",
    "render",
]

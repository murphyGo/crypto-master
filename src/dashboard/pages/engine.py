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
from typing import TypedDict

import pandas as pd
import streamlit as st

# CAH-09 / DASH-F1: the reconciliation, market-regime, and cross-account-risk
# panel clusters live in sibling modules; re-export their public symbols here so
# every existing ``from src.dashboard.pages.engine import ...`` path (notably
# ``trading.py``'s three reconciliation imports) keeps resolving. The siblings do
# NOT import back from this module, so there is no import cycle.
from src.dashboard.pages.engine_cross_account_risk import (
    CROSS_ACCOUNT_RISK_RECENT_LIMIT,
    CapBand,
    FreezeTogglePlan,
    OperatorFreezeState,
    build_cross_account_risk_dataframe,
    build_freeze_toggle_plan,
    build_operator_freeze_state,
    build_portfolio_cap_utilization,
    build_risk_gate_events_dataframe,
    build_symbol_side_exposure_dataframe,
    kill_switch_state_for_account,
    render_cross_account_risk,
    render_operator_freeze_toggle,
)
from src.dashboard.pages.engine_market_regime import (
    MARKET_REGIME_RECENT_LIMIT,
    MarketRegimeAccountPolicyRow,
    MarketRegimeStatusRow,
    build_market_regime_account_dataframe,
    build_market_regime_account_rows,
    build_market_regime_degraded_events_dataframe,
    build_market_regime_events_dataframe,
    build_market_regime_status_dataframe,
    build_market_regime_status_rows,
)
from src.dashboard.pages.engine_reconciliation import (
    ReconciliationBanner,
    ReconciliationColor,
    build_reconciliation_drilldown_dataframe,
    build_reconciliation_status_banner,
    latest_reconciliation_event,
    render_reconciliation_banner,
)
from src.dashboard.query_params import query_param_values as _query_param_values
from src.logger import get_logger
from src.runtime.activity_log import ActivityEvent, ActivityEventType, ActivityLog
from src.runtime.safety_score import (
    RuntimeSafetyScore,
    compute_runtime_safety_score,
    inputs_from_recent_activity_events,
)

logger = get_logger("crypto_master.dashboard.engine")


DEFAULT_TAIL_LIMIT = 300
RECENT_CYCLES_LIMIT = 25
DURATION_HISTOGRAM_LIMIT = 50


class EngineSummaryMetrics(TypedDict):
    """Headline numbers for the Engine page summary cards (DEBT-011).

    Typed return shape for ``build_summary_metrics`` so consumer
    sites pick the right type at each access without ``cast(...)``.
    """

    total_cycles: int
    last_cycle_started_at: datetime | None
    last_cycle_status: str | None
    avg_duration_seconds: float | None
    errored_cycles: int
    positions_opened_total: int
    positions_closed_total: int


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


# cross-account-risk-policy DEBT-068(g-note): the "Rejected" tally must
# count GENUINE hard-blocks, not the literal ``PROPOSAL_REJECTED`` event
# type. Three things changed under the risk-policy unit:
#   - Live cap / kill-switch hard-blocks still emit ``PROPOSAL_REJECTED``
#     (the proposal record's terminal is unchanged) — those count.
#   - Live kill-switch trips ALSO emit a dedicated
#     ``RISK_KILL_SWITCH_TRIPPED`` companion event. Counting that event
#     too would DOUBLE-count the same live rejection; but a paper
#     kill-switch trip emits ONLY ``RISK_KILL_SWITCH_TRIPPED``
#     (``details.advisory=True``) with NO ``PROPOSAL_REJECTED``, and the
#     proposal still proceeds — so that one must NOT count.
#   - ``RISK_CAP_ADVISORY`` is paper-advisory or priority-admitted; it
#     never hard-blocks, so it never counts.
#
# Rule: a genuine rejection is an event that HARD-BLOCKED a proposal,
# i.e. ``details.advisory`` is NOT truthy AND the event is one of the
# rejection-bearing types. ``PROPOSAL_REJECTED`` is always a hard block
# (advisory paper caps reuse ``RISK_CAP_ADVISORY``, not
# ``PROPOSAL_REJECTED``). ``RISK_KILL_SWITCH_TRIPPED`` and
# ``OPERATOR_FREEZE_ENGAGED`` count only when not advisory, AND we must
# avoid double-counting the live kill-switch that emits BOTH events on
# the same ``proposal_id`` — so the kill-switch/freeze events are tallied
# only when there is no sibling ``PROPOSAL_REJECTED`` for the same
# ``proposal_id`` (the freeze path persists a rejected record without a
# ``PROPOSAL_REJECTED`` event, so it must self-count).
_REJECTION_COMPANION_EVENT_TYPES = (
    ActivityEventType.RISK_KILL_SWITCH_TRIPPED.value,
    ActivityEventType.OPERATOR_FREEZE_ENGAGED.value,
)


def _is_advisory(event: ActivityEvent) -> bool:
    """True when the event carries ``details.advisory`` truthy (paper-only)."""
    return bool((event.details or {}).get("advisory"))


def _genuine_rejection_events(events: list[ActivityEvent]) -> list[ActivityEvent]:
    """Filter to events that represent a genuine hard-block rejection.

    See the module-level rule above. Returns the de-duplicated set of
    rejection events: every non-advisory ``PROPOSAL_REJECTED`` plus any
    non-advisory ``RISK_KILL_SWITCH_TRIPPED`` / ``OPERATOR_FREEZE_ENGAGED``
    whose ``proposal_id`` does not already appear in a ``PROPOSAL_REJECTED``
    (so the live kill-switch — which emits BOTH — is counted once).
    """
    rejected_proposal_ids: set[str] = set()
    for e in events:
        if e.event_type == ActivityEventType.PROPOSAL_REJECTED.value:
            pid = (e.details or {}).get("proposal_id")
            if pid is not None:
                rejected_proposal_ids.add(str(pid))

    out: list[ActivityEvent] = []
    for e in events:
        if _is_advisory(e):
            continue
        if e.event_type == ActivityEventType.PROPOSAL_REJECTED.value:
            out.append(e)
        elif e.event_type in _REJECTION_COMPANION_EVENT_TYPES:
            pid = (e.details or {}).get("proposal_id")
            if pid is not None and str(pid) in rejected_proposal_ids:
                # Sibling PROPOSAL_REJECTED already counts this; skip to
                # avoid double-counting the live kill-switch trip.
                continue
            out.append(e)
    return out


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
    # DEBT-068(g-note): rebase the Rejected tally onto genuine hard-blocks
    # (non-advisory kill-switch / freeze companions counted once each)
    # rather than the raw ``PROPOSAL_REJECTED`` event count.
    counted[ActivityEventType.PROPOSAL_REJECTED.value] = len(
        _genuine_rejection_events(events)
    )
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
) -> EngineSummaryMetrics:
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


def build_sub_account_metrics_dataframe(events: list[ActivityEvent]) -> pd.DataFrame:
    """Roll up proposal / position counts by ``details.sub_account_id``.

    DEBT-068(g-note): the Rejected column is tallied from
    :func:`_genuine_rejection_events` (non-advisory hard-blocks, with the
    live kill-switch counted once) rather than from the raw
    ``PROPOSAL_REJECTED`` event type, so live kill-switch trips are no
    longer undercounted and paper advisories are not counted at all.
    """
    columns = ["Sub-account", "Generated", "Accepted", "Rejected", "Opened", "Closed"]
    counters: dict[str, dict[str, int]] = {}
    # Non-rejection columns key straight off the event type.
    mapping = {
        ActivityEventType.PROPOSAL_GENERATED.value: "Generated",
        ActivityEventType.PROPOSAL_ACCEPTED.value: "Accepted",
        ActivityEventType.POSITION_OPENED.value: "Opened",
        ActivityEventType.POSITION_CLOSED.value: "Closed",
    }

    def _row_for(sub_account_id: str) -> dict[str, int]:
        return counters.setdefault(
            sub_account_id,
            {"Generated": 0, "Accepted": 0, "Rejected": 0, "Opened": 0, "Closed": 0},
        )

    for event in events:
        column = mapping.get(event.event_type)
        if column is None:
            continue
        sub_account_id = str(event.details.get("sub_account_id", "default"))
        _row_for(sub_account_id)[column] += 1

    # Rejected: rebased onto genuine hard-blocks (DEBT-068(g-note)).
    for event in _genuine_rejection_events(events):
        sub_account_id = str(event.details.get("sub_account_id", "default"))
        _row_for(sub_account_id)["Rejected"] += 1

    if not counters:
        return pd.DataFrame(columns=columns)

    total = {"Generated": 0, "Accepted": 0, "Rejected": 0, "Opened": 0, "Closed": 0}
    rows: list[dict[str, object]] = []
    for sub_account_id in sorted(counters):
        row = counters[sub_account_id]
        rows.append({"Sub-account": sub_account_id, **row})
        for key, value in row.items():
            total[key] += value
    rows.insert(0, {"Sub-account": "Aggregate", **total})
    return pd.DataFrame(rows, columns=columns)


def build_runtime_safety_score(events: list[ActivityEvent]) -> RuntimeSafetyScore:
    """Compute the dashboard safety score from activity events."""
    return compute_runtime_safety_score(inputs_from_recent_activity_events(events))


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

    # runtime-reconciliation §4: persistent banner above everything so a
    # silent zero-positions defect cannot recur (the Fly 2026-05-13
    # snapshot's exact failure mode). Rendered before the empty-log
    # guard because the banner itself is the engine-not-started signal.
    banner = build_reconciliation_status_banner(events)
    render_reconciliation_banner(banner)
    drilldown_df = build_reconciliation_drilldown_dataframe(events)
    if not drilldown_df.empty:
        with st.expander("Reconciliation status — per-trade detail", expanded=False):
            st.dataframe(drilldown_df, hide_index=True, use_container_width=True)

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
        last_at.isoformat(timespec="seconds") if last_at is not None else "—",
    )
    last_status = metrics["last_cycle_status"]
    c3.metric("Last status", last_status if last_status else "—")
    avg = metrics["avg_duration_seconds"]
    c4.metric(
        "Avg duration",
        f"{avg:.1f}s" if avg is not None else "—",
    )
    c5.metric("Errored cycles", metrics["errored_cycles"])

    c6, c7 = st.columns(2)
    c6.metric("Positions opened (total)", metrics["positions_opened_total"])
    c7.metric("Positions closed (total)", metrics["positions_closed_total"])

    st.subheader("Runtime Safety")
    safety = build_runtime_safety_score(events)
    s1, s2 = st.columns(2)
    s1.metric("Safety score", safety.score)
    s2.metric("Safety band", safety.band.value)
    st.caption("; ".join(safety.factors))

    st.subheader("Sub-account Metrics")
    sub_account_df = build_sub_account_metrics_dataframe(events)
    if sub_account_df.empty:
        st.info("No sub-account activity recorded yet.")
    else:
        st.dataframe(sub_account_df, hide_index=True, use_container_width=True)

    # ---- Cross-account risk (cross-account-risk-policy DEBT-068(f-1)) ----
    render_cross_account_risk(events)

    # ---- Market regime status (market-regime unit) ----
    st.subheader("Market Regime")
    status_rows = build_market_regime_status_rows(events)
    status_df = build_market_regime_status_dataframe(status_rows)
    if status_df.empty:
        st.info(
            "No market-regime classifier reads observed yet. Either no "
            "sub-account has `market_regime.enabled: true`, or no proposal "
            "has hit the gate on the recorded window."
        )
    else:
        st.dataframe(status_df, hide_index=True, use_container_width=True)

    account_rows = build_market_regime_account_rows(events)
    account_df = build_market_regime_account_dataframe(account_rows)
    if not account_df.empty:
        st.caption("Per-sub-account regime gate state")
        st.dataframe(account_df, hide_index=True, use_container_width=True)

    regime_events_df = build_market_regime_events_dataframe(events)
    if not regime_events_df.empty:
        st.caption("Recent regime-blocked events")
        st.dataframe(regime_events_df, hide_index=True, use_container_width=True)

    # Fail-open degraded events sit alongside the blocked table so the
    # operator can spot a silent gate disablement at a glance (quant-
    # trader audit follow-up — see ``MARKET_REGIME_DEGRADED`` docstring).
    regime_degraded_df = build_market_regime_degraded_events_dataframe(events)
    if not regime_degraded_df.empty:
        st.caption("Recent regime-gate degraded (fail-open) events")
        st.dataframe(
            regime_degraded_df, hide_index=True, use_container_width=True
        )

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
    requested_types = _query_param_values("event_type")
    default_types = [
        event_type for event_type in all_event_types if event_type in requested_types
    ]
    if not default_types:
        default_types = all_event_types
    selected_types = st.multiselect(
        "Event types",
        options=all_event_types,
        default=default_types,
    )
    tail_events = events[-tail_limit:] if len(events) > tail_limit else events
    filtered = [e for e in tail_events if e.event_type in selected_types]
    timeline_df = build_timeline_dataframe(filtered)
    if timeline_df.empty:
        st.info("No events match the selected filter.")
    else:
        st.dataframe(timeline_df, hide_index=True, use_container_width=True)


__all__ = [
    "CapBand",
    "CycleSummary",
    "EngineSummaryMetrics",
    "FreezeTogglePlan",
    "MARKET_REGIME_RECENT_LIMIT",
    "CROSS_ACCOUNT_RISK_RECENT_LIMIT",
    "MarketRegimeAccountPolicyRow",
    "MarketRegimeStatusRow",
    "OperatorFreezeState",
    "ReconciliationBanner",
    "ReconciliationColor",
    "aggregate_cycles",
    "build_cross_account_risk_dataframe",
    "build_cycle_duration_dataframe",
    "build_cycles_dataframe",
    "build_freeze_toggle_plan",
    "build_operator_freeze_state",
    "build_portfolio_cap_utilization",
    "build_risk_gate_events_dataframe",
    "build_symbol_side_exposure_dataframe",
    "build_market_regime_account_dataframe",
    "build_market_regime_account_rows",
    "build_market_regime_degraded_events_dataframe",
    "build_market_regime_events_dataframe",
    "build_market_regime_status_dataframe",
    "build_market_regime_status_rows",
    "build_reconciliation_drilldown_dataframe",
    "build_reconciliation_status_banner",
    "build_runtime_safety_score",
    "build_summary_metrics",
    "build_sub_account_metrics_dataframe",
    "build_timeline_dataframe",
    "kill_switch_state_for_account",
    "latest_reconciliation_event",
    "render",
    "render_cross_account_risk",
    "render_operator_freeze_toggle",
    "render_reconciliation_banner",
]

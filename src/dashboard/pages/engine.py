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
from typing import Literal, TypedDict

import pandas as pd
import streamlit as st

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
# Runtime reconciliation (runtime-reconciliation unit)
# =============================================================================


# Color values are stable strings so tests can pin them without
# depending on Streamlit's styling vocabulary; the render call branches
# on these to pick the ``st.success`` / ``st.warning`` / ``st.error``
# helper. Resolution 2026-05-13: persistent banner, never dismissible.
ReconciliationColor = Literal["green", "yellow", "red"]


@dataclass
class ReconciliationBanner:
    """Banner shape derived from the latest reconciliation health report.

    Attributes:
        color: Stable status colour — ``green`` / ``yellow`` / ``red``.
        message: Short human-readable summary the banner renders.
        cta: Optional call-to-action string (the CLI command the
            operator should run). ``None`` on Green.
        open_trade_count: Total open trades across every sub-account
            in the latest report. Used by the Trading-page cash-only
            suppression rule — a non-zero count blocks the page from
            rendering the "no open positions" summary even if the
            portfolio snapshot disagrees with the ledger.
        report_timestamp: When the source event was emitted; ``None``
            if no reconciliation event has been recorded yet.
    """

    color: ReconciliationColor
    message: str
    cta: str | None
    open_trade_count: int
    report_timestamp: datetime | None


def latest_reconciliation_event(
    events: list[ActivityEvent],
) -> ActivityEvent | None:
    """Return the most recent reconciliation event of any kind.

    Considers both ``RECONCILIATION_HEALTH_REPORT`` (the normal
    successful report) and ``RECONCILIATION_HEALTH_CHECK_FAILED`` (Q4
    follow-up — the meta-event emitted when ``compute_health_report``
    crashed). The banner builder branches on the event type to pick
    Yellow + a "check failed" CTA vs the normal Green / Yellow / Red
    decision table sourced from the report payload.
    """
    reconciliation_types = {
        ActivityEventType.RECONCILIATION_HEALTH_REPORT.value,
        ActivityEventType.RECONCILIATION_HEALTH_CHECK_FAILED.value,
    }
    matching = [event for event in events if event.event_type in reconciliation_types]
    if not matching:
        return None
    return max(matching, key=lambda event: event.timestamp)


def build_reconciliation_status_banner(
    events: list[ActivityEvent],
) -> ReconciliationBanner:
    """Pick the banner color + message from the latest reconciliation event.

    Decision table (runtime-reconciliation §4):

    - Red: any sub-account has ``state_counts.unrecoverable > 0``.
    - Yellow: any sub-account has ``state_counts.degraded > 0`` or
      ``locked_consistent == False``.
    - Green: every open trade is ``monitorable`` or
      ``legacy_no_perf_link``, and every sub-account is
      locked-consistent (or has no snapshot + no rows).

    Returns a Green banner with ``open_trade_count=0`` when no
    reconciliation event has been emitted yet (i.e. the engine hasn't
    started). This makes the dashboard render-safe before the first
    boot but still surfaces the absence as ``"No reconciliation report yet"``.
    """
    event = latest_reconciliation_event(events)
    if event is None:
        return ReconciliationBanner(
            color="green",
            message="No reconciliation report yet (engine has not started).",
            cta=None,
            open_trade_count=0,
            report_timestamp=None,
        )

    # Q4 follow-up: the most recent reconciliation event was the
    # ``compute_health_report`` crash meta-event, not a successful
    # report. Render Yellow with a CTA so operators can distinguish
    # "fresh deploy" from "health check crashed on every boot for 9
    # days" — the DEBT-061 silent-disable anti-pattern we are guarding
    # against.
    if event.event_type == ActivityEventType.RECONCILIATION_HEALTH_CHECK_FAILED.value:
        return ReconciliationBanner(
            color="yellow",
            message=(
                "Reconciliation health check failed — investigate logs."
            ),
            cta="Inspect runtime logs for the reconciliation_health_check_failed event",
            open_trade_count=0,
            report_timestamp=event.timestamp,
        )

    details = event.details or {}
    totals = details.get("totals") or {}
    state_counts = totals.get("state_counts") or {}
    open_count = int(totals.get("open_trade_count", 0) or 0)
    unrecoverable = int(state_counts.get("unrecoverable", 0) or 0)
    degraded = int(state_counts.get("degraded", 0) or 0)
    any_inconsistent = bool(totals.get("any_locked_inconsistent", False))

    if unrecoverable > 0:
        return ReconciliationBanner(
            color="red",
            message=(
                f"Reconciliation: {unrecoverable} unrecoverable open trade(s); "
                "operator must close them before the engine can monitor cleanly."
            ),
            cta="python -m src.tools.close_unrecoverable_paper_trades --dry-run",
            open_trade_count=open_count,
            report_timestamp=event.timestamp,
        )
    if degraded > 0 or any_inconsistent:
        causes: list[str] = []
        if degraded > 0:
            causes.append(f"{degraded} degraded open trade(s) missing SL/TP")
        if any_inconsistent:
            causes.append("locked-margin drift vs balances.json")
        return ReconciliationBanner(
            color="yellow",
            message="Reconciliation: " + "; ".join(causes) + ".",
            cta="python -m src.tools.backfill_paper_sl_tp --dry-run",
            open_trade_count=open_count,
            report_timestamp=event.timestamp,
        )
    return ReconciliationBanner(
        color="green",
        message=(
            f"Reconciliation: {open_count} open trade(s), all monitorable."
        ),
        cta=None,
        open_trade_count=open_count,
        report_timestamp=event.timestamp,
    )


def build_reconciliation_drilldown_dataframe(
    events: list[ActivityEvent],
) -> pd.DataFrame:
    """One row per open trade in the latest reconciliation report.

    Sourced from ``totals.classifications`` on the most recent
    ``RECONCILIATION_HEALTH_REPORT`` event so the dashboard does not
    re-walk the ledger (the engine wrote the snapshot of state once;
    the dashboard renders it).
    """
    columns = [
        "Sub-account",
        "Trade ID",
        "Symbol",
        "Side",
        "State",
        "Missing Fields",
    ]
    event = latest_reconciliation_event(events)
    if event is None:
        return pd.DataFrame(columns=columns)
    # Q4 follow-up: the failed-meta-event carries no classifications
    # payload — return an empty drill-through so the dashboard renders
    # the failure banner without a misleading "0 open trades" table
    # implying a successful empty report.
    if event.event_type == ActivityEventType.RECONCILIATION_HEALTH_CHECK_FAILED.value:
        return pd.DataFrame(columns=columns)
    totals = (event.details or {}).get("totals") or {}
    classifications = totals.get("classifications") or []
    if not classifications:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, object]] = []
    for entry in classifications:
        if not isinstance(entry, dict):
            continue
        missing = entry.get("missing_fields") or []
        missing_str = ", ".join(str(field) for field in missing) if missing else "—"
        rows.append(
            {
                "Sub-account": str(entry.get("sub_account_id", "—")),
                "Trade ID": str(entry.get("trade_id", "—")),
                "Symbol": str(entry.get("symbol") or "—"),
                "Side": str(entry.get("side") or "—"),
                "State": str(entry.get("state", "—")),
                "Missing Fields": missing_str,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def render_reconciliation_banner(banner: ReconciliationBanner) -> None:
    """Render a :class:`ReconciliationBanner` via the matching Streamlit helper.

    Kept as a separate helper so both the Engine page and the Trading
    page can call into the same render path with the same colour
    semantics. Persistent (non-dismissible) per spec resolution.
    """
    body = banner.message
    if banner.cta:
        body = f"{body}\n\nRun: `{banner.cta}`"
    if banner.report_timestamp is not None:
        body = f"{body}\n\n_Last report: {banner.report_timestamp.isoformat(timespec='seconds')}_"
    if banner.color == "red":
        st.error(body)
    elif banner.color == "yellow":
        st.warning(body)
    else:
        st.success(body)


# =============================================================================
# Market regime visibility (market-regime unit)
# =============================================================================

# How many recent MARKET_REGIME_BLOCKED events to surface in the table.
MARKET_REGIME_RECENT_LIMIT = 25


@dataclass
class MarketRegimeStatusRow:
    """Latest regime classification observed for one (symbol, timeframe) pair.

    Derived from the most recent ``MARKET_REGIME_BLOCKED`` event — the
    engine only emits the classifier read on the block path today, so
    the dashboard surfaces the same view operators see in the activity
    timeline. Once the proposal-runtime emits a parallel pass-through
    event (future work), this read model expands without a schema
    change on the page.
    """

    reference_symbol: str
    timeframe: str
    regime: str
    baseline: str
    close: str
    last_observed_at: datetime


@dataclass
class MarketRegimeAccountPolicyRow:
    """Per-sub-account policy + current allow/block status row."""

    sub_account_id: str
    last_regime: str
    last_observed_at: datetime
    last_decision: str


def build_market_regime_status_rows(
    events: list[ActivityEvent],
) -> list[MarketRegimeStatusRow]:
    """Most recent classifier read per (reference_symbol, timeframe).

    Sorted newest-first so the operator sees fresh classifications at
    the top.
    """
    latest: dict[tuple[str, str], ActivityEvent] = {}
    for event in events:
        if event.event_type != ActivityEventType.MARKET_REGIME_BLOCKED.value:
            continue
        symbol = str(event.details.get("symbol", ""))
        timeframe = str(event.details.get("timeframe", ""))
        if not symbol or not timeframe:
            continue
        key = (symbol, timeframe)
        seen = latest.get(key)
        if seen is None or event.timestamp > seen.timestamp:
            latest[key] = event

    rows: list[MarketRegimeStatusRow] = []
    for (symbol, timeframe), event in latest.items():
        rows.append(
            MarketRegimeStatusRow(
                reference_symbol=symbol,
                timeframe=timeframe,
                regime=str(event.details.get("regime", "unknown")),
                baseline=str(event.details.get("baseline") or "—"),
                close=str(event.details.get("close") or "—"),
                last_observed_at=event.timestamp,
            )
        )
    rows.sort(key=lambda row: row.last_observed_at, reverse=True)
    return rows


def build_market_regime_status_dataframe(
    rows: list[MarketRegimeStatusRow],
) -> pd.DataFrame:
    columns = [
        "Reference Symbol",
        "Timeframe",
        "Regime",
        "Baseline (SMA)",
        "Close",
        "Last Observed",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "Reference Symbol": row.reference_symbol,
                "Timeframe": row.timeframe,
                "Regime": row.regime,
                "Baseline (SMA)": row.baseline,
                "Close": row.close,
                "Last Observed": row.last_observed_at.isoformat(timespec="seconds"),
            }
            for row in rows
        ],
        columns=columns,
    )


def build_market_regime_account_rows(
    events: list[ActivityEvent],
) -> list[MarketRegimeAccountPolicyRow]:
    """Per-sub-account latest regime decision observed in the log.

    The engine emits ``MARKET_REGIME_BLOCKED`` only on the block path;
    "last_decision" therefore reads "block" for any account that has
    been classified, and the absence of an event is the silent "pass"
    state. Without ranking the events that's the most honest view we
    can give operators today.
    """
    latest: dict[str, ActivityEvent] = {}
    for event in events:
        if event.event_type != ActivityEventType.MARKET_REGIME_BLOCKED.value:
            continue
        sub_account_id = str(event.details.get("sub_account_id", ""))
        if not sub_account_id:
            continue
        seen = latest.get(sub_account_id)
        if seen is None or event.timestamp > seen.timestamp:
            latest[sub_account_id] = event

    rows = [
        MarketRegimeAccountPolicyRow(
            sub_account_id=sub_account_id,
            last_regime=str(event.details.get("regime", "unknown")),
            last_observed_at=event.timestamp,
            last_decision=str(event.details.get("policy_decision", "block")),
        )
        for sub_account_id, event in latest.items()
    ]
    rows.sort(key=lambda row: row.last_observed_at, reverse=True)
    return rows


def build_market_regime_account_dataframe(
    rows: list[MarketRegimeAccountPolicyRow],
) -> pd.DataFrame:
    columns = ["Sub-account", "Last Regime", "Last Decision", "Last Observed"]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "Sub-account": row.sub_account_id,
                "Last Regime": row.last_regime,
                "Last Decision": row.last_decision,
                "Last Observed": row.last_observed_at.isoformat(timespec="seconds"),
            }
            for row in rows
        ],
        columns=columns,
    )


def build_market_regime_events_dataframe(
    events: list[ActivityEvent],
    *,
    limit: int = MARKET_REGIME_RECENT_LIMIT,
) -> pd.DataFrame:
    """Recent regime-blocked events, newest-first, capped at ``limit``."""
    columns = [
        "Timestamp",
        "Sub-account",
        "Reference Symbol",
        "Timeframe",
        "Regime",
        "Reason",
    ]
    blocked = [
        event
        for event in events
        if event.event_type == ActivityEventType.MARKET_REGIME_BLOCKED.value
    ]
    blocked.sort(key=lambda event: event.timestamp, reverse=True)
    blocked = blocked[:limit]
    if not blocked:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "Timestamp": event.timestamp.isoformat(timespec="seconds"),
                "Sub-account": str(event.details.get("sub_account_id", "—")),
                "Reference Symbol": str(event.details.get("symbol", "—")),
                "Timeframe": str(event.details.get("timeframe", "—")),
                "Regime": str(event.details.get("regime", "—")),
                "Reason": str(event.details.get("reason", "—")),
            }
            for event in blocked
        ],
        columns=columns,
    )


def build_market_regime_degraded_events_dataframe(
    events: list[ActivityEvent],
    *,
    limit: int = MARKET_REGIME_RECENT_LIMIT,
) -> pd.DataFrame:
    """Recent regime-degraded fail-open events, newest-first.

    Surfaces the quant-trader audit follow-up:
    ``MARKET_REGIME_DEGRADED`` is emitted whenever the gate's OHLCV
    fetch raises and the gate falls open. Without this surface the
    silent disablement is invisible to the operator (DEBT-061
    anti-pattern). Capped at ``limit`` for symmetry with the blocked
    events table.
    """
    columns = [
        "Timestamp",
        "Sub-account",
        "Reference Symbol",
        "Timeframe",
        "Error Type",
        "Decision",
    ]
    degraded = [
        event
        for event in events
        if event.event_type == ActivityEventType.MARKET_REGIME_DEGRADED.value
    ]
    degraded.sort(key=lambda event: event.timestamp, reverse=True)
    degraded = degraded[:limit]
    if not degraded:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "Timestamp": event.timestamp.isoformat(timespec="seconds"),
                "Sub-account": str(event.details.get("sub_account_id", "—")),
                "Reference Symbol": str(event.details.get("symbol", "—")),
                "Timeframe": str(event.details.get("timeframe", "—")),
                "Error Type": str(event.details.get("error_type", "—")),
                "Decision": str(
                    event.details.get("policy_decision", "pass_through_degraded")
                ),
            }
            for event in degraded
        ],
        columns=columns,
    )


# =============================================================================
# Cross-Account Risk panel (cross-account-risk-policy DEBT-068(f-1))
# =============================================================================
#
# READ-ONLY panel built entirely from ``ActivityEvent``s. The interactive
# operator-freeze TOGGLE (write to ``config/runtime_flags.yaml``) is
# DEFERRED to f-2; this slice renders a read-only freeze-STATE indicator
# only.
#
# Sourcing note (reported back to the lead): the engine does NOT emit a
# dedicated portfolio-snapshot ActivityEvent — ``_record_portfolio_
# snapshot`` writes to ``PortfolioTracker`` (``data/performance/...``),
# not the activity log. So per-account equity / realized-PnL-today /
# open-unrealized / stop-risk / gross-notional are only opportunistically
# sourceable from the risk-gate event ``details`` that DO carry them
# (kill-switch and cap events emitted on a breach). Fields with no event
# source are surfaced as "n/a" rather than invented. Which fields come
# from where:
#   - equity:               kill-switch event ``details.equity``.
#   - realized_pnl_today:    daily-loss kill-switch ``details.realized_pnl_today``.
#   - open_unrealized_pnl:   open-drawdown kill-switch ``details.unrealized_pnl_open``.
#   - open_stop_risk_total:  open-stop-risk kill-switch ``details.open_stop_risk``
#                            OR account-aggregate cap ``details.open_stop_risk_total``.
#   - gross_open_notional:   account-aggregate cap ``details.gross_notional_total``.
# An account that has never tripped a gate appears with all-"n/a" metrics
# but is still listed (derived from any risk event referencing it).

# Color bands mirror the reconciliation banner's stable-string contract so
# the render layer can branch on these without depending on Streamlit's
# styling vocabulary. Thresholds per spec §"Dashboard Behavior":
# GREEN <70%, AMBER 70-90%, RED 90-100%, BREACH >100%.
CapBand = Literal["green", "amber", "red", "breach"]

# Activity event types that reference a sub-account for the risk panel.
_RISK_EVENT_TYPES = (
    ActivityEventType.RISK_CAP_ADVISORY.value,
    ActivityEventType.RISK_KILL_SWITCH_TRIPPED.value,
    ActivityEventType.OPERATOR_FREEZE_ENGAGED.value,
    ActivityEventType.STALE_POSITION_DETECTED.value,
    ActivityEventType.STALE_POSITION_AUTO_CLOSED.value,
)

CROSS_ACCOUNT_RISK_RECENT_LIMIT = 25


def _cap_band(pct: float | None) -> CapBand | None:
    """Map a percent-of-cap to a color band, or ``None`` when unknown."""
    if pct is None:
        return None
    if pct > 100.0:
        return "breach"
    if pct >= 90.0:
        return "red"
    if pct >= 70.0:
        return "amber"
    return "green"


def _latest_by(
    events: list[ActivityEvent],
    *,
    event_types: tuple[str, ...],
    key: str,
) -> dict[str, ActivityEvent]:
    """Most-recent event per ``details[key]`` among the given event types."""
    latest: dict[str, ActivityEvent] = {}
    for event in events:
        if event.event_type not in event_types:
            continue
        value = (event.details or {}).get(key)
        if value in (None, ""):
            continue
        ident = str(value)
        seen = latest.get(ident)
        if seen is None or event.timestamp > seen.timestamp:
            latest[ident] = event
    return latest


def _latest_cycle_id(events: list[ActivityEvent]) -> str | None:
    """The ``cycle_id`` of the most recent event that carries one."""
    latest_ts: datetime | None = None
    latest_cycle: str | None = None
    for event in events:
        if event.cycle_id is None:
            continue
        if latest_ts is None or event.timestamp > latest_ts:
            latest_ts = event.timestamp
            latest_cycle = event.cycle_id
    return latest_cycle


def kill_switch_state_for_account(
    events: list[ActivityEvent],
    sub_account_id: str,
    *,
    cycle_id: str | None,
) -> str:
    """Derive a sub-account's current kill-switch / stale-block state.

    The "current state" window is the latest cycle (``cycle_id``): a
    kill-switch / stale block is a per-cycle gate decision, so an account
    that tripped three cycles ago but not in the current cycle reads
    ``none`` (the gate is stateless across cycles except for daily-loss,
    which re-trips each cycle while it holds). When ``cycle_id`` is
    ``None`` (no cycle context) we fall back to the most-recent event
    overall so a single-shot synthetic log still resolves.

    Returns one of: ``none`` / ``daily-loss-tripped`` /
    ``drawdown-tripped`` / ``stop-risk-tripped`` / ``stale-block``. When
    multiple gates tripped on the same cycle, kill-switch trips win over
    a stale block, and the most-recent trip's gate_reason decides between
    the kill-switch sub-states.
    """
    kill_reason_map = {
        "daily_loss_kill_switch": "daily-loss-tripped",
        "portfolio_daily_loss_kill_switch": "daily-loss-tripped",
        "open_drawdown_kill_switch": "drawdown-tripped",
        "portfolio_kill_switch": "drawdown-tripped",
        "open_stop_risk_kill_switch": "stop-risk-tripped",
    }

    def _in_window(event: ActivityEvent) -> bool:
        if cycle_id is None:
            return True
        return event.cycle_id == cycle_id

    kill_events = [
        e
        for e in events
        if e.event_type == ActivityEventType.RISK_KILL_SWITCH_TRIPPED.value
        and str((e.details or {}).get("sub_account_id", "")) == sub_account_id
        and _in_window(e)
    ]
    if kill_events:
        latest = max(kill_events, key=lambda e: e.timestamp)
        gate_reason = str((latest.details or {}).get("gate_reason", ""))
        return kill_reason_map.get(gate_reason, "drawdown-tripped")

    stale_events = [
        e
        for e in events
        if e.event_type == ActivityEventType.STALE_POSITION_DETECTED.value
        and str((e.details or {}).get("sub_account_id", "")) == sub_account_id
        and _in_window(e)
    ]
    if stale_events:
        return "stale-block"
    return "none"


def build_cross_account_risk_dataframe(events: list[ActivityEvent]) -> pd.DataFrame:
    """Per-sub-account risk metrics table (DEBT-068(f-1) item 1 + 2).

    One row per sub-account referenced by any risk event, with current
    equity, realized-PnL-today, open unrealized PnL, open stop-risk total,
    gross open notional, and the current kill-switch state. Metric values
    are sourced opportunistically from the latest risk-gate event that
    carries each field (see the module-level sourcing note); unavailable
    fields render as ``"n/a"``.
    """
    columns = [
        "Sub-account",
        "Equity",
        "Realized PnL (today)",
        "Open Unrealized PnL",
        "Open Stop-Risk",
        "Gross Open Notional",
        "Kill-switch State",
    ]
    sub_account_ids: set[str] = set()
    for event in events:
        if event.event_type not in _RISK_EVENT_TYPES:
            continue
        value = (event.details or {}).get("sub_account_id")
        if value not in (None, ""):
            sub_account_ids.add(str(value))
    if not sub_account_ids:
        return pd.DataFrame(columns=columns)

    cycle_id = _latest_cycle_id(events)

    # For metric fields, walk every risk event for the account newest-first
    # and pick the first event that carries the field. Different fields may
    # come from different events (a daily-loss trip carries realized PnL; an
    # aggregate-cap event carries gross notional).
    by_account: dict[str, list[ActivityEvent]] = {sa: [] for sa in sub_account_ids}
    for event in events:
        if event.event_type not in _RISK_EVENT_TYPES:
            continue
        value = (event.details or {}).get("sub_account_id")
        if value in (None, ""):
            continue
        by_account[str(value)].append(event)

    def _pick(account_events: list[ActivityEvent], *keys: str) -> str:
        for event in sorted(account_events, key=lambda e: e.timestamp, reverse=True):
            details = event.details or {}
            for key in keys:
                raw = details.get(key)
                if raw not in (None, ""):
                    return str(raw)
        return "n/a"

    rows: list[dict[str, object]] = []
    for sub_account_id in sorted(sub_account_ids):
        account_events = by_account[sub_account_id]
        rows.append(
            {
                "Sub-account": sub_account_id,
                "Equity": _pick(account_events, "equity"),
                "Realized PnL (today)": _pick(
                    account_events,
                    "realized_pnl_today",
                    "portfolio_realized_pnl_today",
                ),
                "Open Unrealized PnL": _pick(
                    account_events,
                    "unrealized_pnl_open",
                    "portfolio_unrealized_pnl",
                ),
                "Open Stop-Risk": _pick(
                    account_events, "open_stop_risk_total", "open_stop_risk"
                ),
                "Gross Open Notional": _pick(account_events, "gross_notional_total"),
                "Kill-switch State": kill_switch_state_for_account(
                    events, sub_account_id, cycle_id=cycle_id
                ),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def build_portfolio_cap_utilization(events: list[ActivityEvent]) -> pd.DataFrame:
    """Portfolio totals vs each configured global cap, with a color band.

    DEBT-068(f-1) item 3. Sourced from the latest global-cap event
    (``RISK_CAP_ADVISORY`` / ``PROPOSAL_REJECTED`` with
    ``gate_reason="global_cap"``): that payload carries both the running
    totals (``*_total``) and the configured limits (``max_*``). One row per
    configured cap (a cap with ``max=None`` is inert and skipped, mirroring
    the runtime's "configured bounds only" rule). Columns: ``Cap``,
    ``Total``, ``Limit``, ``Pct of Cap``, ``Band`` — ``Band`` is one of the
    :data:`CapBand` stable strings so the render layer reuses the
    reconciliation color pattern.

    Note: the limits come from the gate event ``details`` (the only event
    source the page reads). When global caps are configured but have never
    fired a gate, there is no event to read and the table is empty — the
    engine emits no parallel "caps configured" event today, so the page
    cannot show 0%-utilization rows without a config source. Reported back
    to the lead as a known sourcing gap.
    """
    columns = ["Cap", "Total", "Limit", "Pct of Cap", "Band"]
    global_events = [
        e
        for e in events
        if (e.details or {}).get("gate_reason") == "global_cap"
        and e.event_type
        in (
            ActivityEventType.RISK_CAP_ADVISORY.value,
            ActivityEventType.PROPOSAL_REJECTED.value,
        )
    ]
    if not global_events:
        return pd.DataFrame(columns=columns)
    latest = max(global_events, key=lambda e: e.timestamp)
    details = latest.details or {}

    # (label, total_key, limit_key)
    cap_specs = [
        (
            "open_positions_per_symbol_side",
            "open_positions_per_symbol_side_total",
            "max_open_positions_per_symbol_side",
        ),
        (
            "gross_notional_per_symbol_side",
            "gross_notional_per_symbol_side_total",
            "max_gross_notional_per_symbol_side",
        ),
        (
            "gross_notional_per_symbol",
            "gross_notional_per_symbol_total",
            "max_gross_notional_per_symbol",
        ),
    ]

    rows: list[dict[str, object]] = []
    for label, total_key, limit_key in cap_specs:
        limit_raw = details.get(limit_key)
        if limit_raw in (None, ""):
            continue  # cap not configured — inert.
        total_raw = details.get(total_key)
        try:
            limit_val = float(str(limit_raw))
            total_val = (
                float(str(total_raw)) if total_raw not in (None, "") else None
            )
        except (TypeError, ValueError):
            continue
        pct = (total_val / limit_val * 100.0) if (total_val is not None and limit_val) else None
        rows.append(
            {
                "Cap": label,
                "Total": str(total_raw) if total_raw not in (None, "") else "n/a",
                "Limit": str(limit_raw),
                "Pct of Cap": round(pct, 1) if pct is not None else None,
                "Band": _cap_band(pct) or "n/a",
            }
        )
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)


def build_symbol_side_exposure_dataframe(
    events: list[ActivityEvent],
) -> pd.DataFrame:
    """Cross-(symbol, side) exposure summary (DEBT-068(f-1) item 4).

    One row per active ``(symbol, side)`` tuple observed in global-cap
    events, with the count of DISTINCT accounts holding exposure on that
    key, the latest total notional on the key, and which global cap (if
    any) it is closest to breaching. "Active" is sourced from global-cap
    events because those are the only events carrying the cross-account
    aggregate view; per-account events do not roll up a portfolio total.

    The distinct-account count is reconstructed from the latest global-cap
    event's ``existing_holders`` (other accounts already on the key) plus
    the proposing account. "Closest cap" picks the cap with the highest
    percent-of-limit among the configured caps in that event's payload.
    """
    columns = [
        "Symbol",
        "Side",
        "Accounts",
        "Total Notional",
        "Closest Cap",
    ]
    latest_by_key: dict[tuple[str, str], ActivityEvent] = {}
    for event in events:
        details = event.details or {}
        if details.get("gate_reason") != "global_cap":
            continue
        if event.event_type not in (
            ActivityEventType.RISK_CAP_ADVISORY.value,
            ActivityEventType.PROPOSAL_REJECTED.value,
        ):
            continue
        symbol = str(details.get("symbol") or "")
        side = str(details.get("side") or "")
        if not symbol or not side:
            continue
        key = (symbol, side)
        seen = latest_by_key.get(key)
        if seen is None or event.timestamp > seen.timestamp:
            latest_by_key[key] = event
    if not latest_by_key:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    for (symbol, side), event in sorted(latest_by_key.items()):
        details = event.details or {}
        holders = details.get("existing_holders") or []
        accounts: set[str] = {str(h) for h in holders if h not in (None, "")}
        proposer = details.get("proposer_account") or details.get("sub_account_id")
        if proposer not in (None, ""):
            accounts.add(str(proposer))
        ss_notional = details.get("gross_notional_per_symbol_side_total")
        closest = _closest_global_cap(details)
        rows.append(
            {
                "Symbol": symbol,
                "Side": side,
                "Accounts": len(accounts),
                "Total Notional": (
                    str(ss_notional) if ss_notional not in (None, "") else "n/a"
                ),
                "Closest Cap": closest,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _closest_global_cap(details: dict[str, object]) -> str:
    """Cap label with the highest percent-of-limit in a global-cap payload."""
    cap_specs = [
        (
            "open_positions_per_symbol_side",
            "open_positions_per_symbol_side_total",
            "max_open_positions_per_symbol_side",
        ),
        (
            "gross_notional_per_symbol_side",
            "gross_notional_per_symbol_side_total",
            "max_gross_notional_per_symbol_side",
        ),
        (
            "gross_notional_per_symbol",
            "gross_notional_per_symbol_total",
            "max_gross_notional_per_symbol",
        ),
    ]
    best_label = "—"
    best_pct = -1.0
    for label, total_key, limit_key in cap_specs:
        limit_raw = details.get(limit_key)
        total_raw = details.get(total_key)
        if limit_raw in (None, "") or total_raw in (None, ""):
            continue
        try:
            limit_val = float(str(limit_raw))
            total_val = float(str(total_raw))
        except (TypeError, ValueError):
            continue
        if not limit_val:
            continue
        pct = total_val / limit_val * 100.0
        if pct > best_pct:
            best_pct = pct
            best_label = label
    return best_label


def build_risk_gate_events_dataframe(
    events: list[ActivityEvent],
    *,
    limit: int = CROSS_ACCOUNT_RISK_RECENT_LIMIT,
) -> pd.DataFrame:
    """Recent risk-gate-blocked / advisory proposal events (item 5).

    Surfaces ``RISK_CAP_ADVISORY`` / ``RISK_KILL_SWITCH_TRIPPED`` /
    ``OPERATOR_FREEZE_ENGAGED`` plus the live cap / kill-switch
    ``PROPOSAL_REJECTED`` rows (keyed on ``gate_reason`` so unrelated
    proposal rejections like stale-quote are excluded). Newest-first,
    capped at ``limit``. The ``Advisory`` column makes the paper-advisory
    vs hard-block distinction explicit per the spec's paper-first model.
    """
    columns = [
        "Timestamp",
        "Event",
        "Sub-account",
        "Symbol",
        "Side",
        "Gate Reason",
        "Mode",
        "Advisory",
    ]
    risk_gate_reasons = {
        "account_aggregate_cap",
        "global_cap",
        "daily_loss_kill_switch",
        "open_drawdown_kill_switch",
        "open_stop_risk_kill_switch",
        "portfolio_kill_switch",
        "portfolio_daily_loss_kill_switch",
        "operator_freeze",
    }
    dedicated_types = {
        ActivityEventType.RISK_CAP_ADVISORY.value,
        ActivityEventType.RISK_KILL_SWITCH_TRIPPED.value,
        ActivityEventType.OPERATOR_FREEZE_ENGAGED.value,
    }
    selected: list[ActivityEvent] = []
    for event in events:
        details = event.details or {}
        if event.event_type in dedicated_types:
            selected.append(event)
        elif (
            event.event_type == ActivityEventType.PROPOSAL_REJECTED.value
            and str(details.get("gate_reason", "")) in risk_gate_reasons
        ):
            selected.append(event)
    selected.sort(key=lambda e: e.timestamp, reverse=True)
    selected = selected[:limit]
    if not selected:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, object]] = []
    for event in selected:
        details = event.details or {}
        rows.append(
            {
                "Timestamp": event.timestamp.isoformat(timespec="seconds"),
                "Event": event.event_type,
                "Sub-account": str(details.get("sub_account_id", "—")),
                "Symbol": str(details.get("symbol", "—")),
                "Side": str(details.get("side") or details.get("signal") or "—"),
                "Gate Reason": str(details.get("gate_reason", "—")),
                "Mode": str(details.get("mode", "—")),
                "Advisory": bool(details.get("advisory")),
            }
        )
    return pd.DataFrame(rows, columns=columns)


@dataclass
class OperatorFreezeState:
    """Read-only operator-freeze indicator (DEBT-068(f-1)).

    Derived purely from ``OPERATOR_FREEZE_ENGAGED`` events — the write-side
    toggle is deferred to f-2. ``engaged`` is ``True`` when at least one
    freeze-engaged event exists in the current/most-recent cycle; the
    timestamp is the most recent such event. The freeze never auto-releases
    (spec §"Hysteresis"), but a cycle with no freeze events means no
    proposal was blocked by a freeze on that cycle, which is the best
    read-only signal the activity log offers.
    """

    engaged: bool
    last_engaged_at: datetime | None


def build_operator_freeze_state(events: list[ActivityEvent]) -> OperatorFreezeState:
    """Read-only freeze-state indicator from ``OPERATOR_FREEZE_ENGAGED``."""
    freeze_events = [
        e
        for e in events
        if e.event_type == ActivityEventType.OPERATOR_FREEZE_ENGAGED.value
    ]
    if not freeze_events:
        return OperatorFreezeState(engaged=False, last_engaged_at=None)
    latest = max(freeze_events, key=lambda e: e.timestamp)
    cycle_id = _latest_cycle_id(events)
    engaged = cycle_id is None or latest.cycle_id == cycle_id
    return OperatorFreezeState(engaged=engaged, last_engaged_at=latest.timestamp)


def render_cross_account_risk(events: list[ActivityEvent]) -> None:
    """Render the Cross-Account Risk panel (read-only, DEBT-068(f-1)).

    Guards empty data gracefully: when no risk events exist at all, shows
    a friendly info message rather than a clutter of empty tables.
    """
    st.subheader("Cross-Account Risk")

    metrics_df = build_cross_account_risk_dataframe(events)
    cap_df = build_portfolio_cap_utilization(events)
    exposure_df = build_symbol_side_exposure_dataframe(events)
    gate_df = build_risk_gate_events_dataframe(events)
    freeze = build_operator_freeze_state(events)

    if (
        metrics_df.empty
        and cap_df.empty
        and exposure_df.empty
        and gate_df.empty
        and not freeze.engaged
        and freeze.last_engaged_at is None
    ):
        st.info(
            "No cross-account risk data yet. Either no global risk policy is "
            "enabled, or no risk gate (cap / kill-switch / freeze / stale) has "
            "fired on the recorded window."
        )
        return

    # Read-only operator-freeze indicator (write-side toggle deferred to f-2).
    if freeze.engaged:
        suffix = (
            f" (last engaged {freeze.last_engaged_at.isoformat(timespec='seconds')})"
            if freeze.last_engaged_at is not None
            else ""
        )
        st.error(f"Operator manual freeze: ENGAGED — all proposals blocked{suffix}")
    else:
        st.success("Operator manual freeze: not engaged")

    if not metrics_df.empty:
        st.caption("Per-sub-account risk metrics")
        st.dataframe(metrics_df, hide_index=True, use_container_width=True)

    if not cap_df.empty:
        st.caption("Portfolio totals vs global caps (band: green<70% / amber / red / breach>100%)")
        st.dataframe(cap_df, hide_index=True, use_container_width=True)

    if not exposure_df.empty:
        st.caption("Cross-account (symbol, side) exposure")
        st.dataframe(exposure_df, hide_index=True, use_container_width=True)

    if not gate_df.empty:
        st.caption("Recent risk-gate events")
        st.dataframe(gate_df, hide_index=True, use_container_width=True)


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
    "CycleSummary",
    "EngineSummaryMetrics",
    "MarketRegimeAccountPolicyRow",
    "MarketRegimeStatusRow",
    "OperatorFreezeState",
    "ReconciliationBanner",
    "aggregate_cycles",
    "build_cross_account_risk_dataframe",
    "build_cycle_duration_dataframe",
    "build_cycles_dataframe",
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
    "render_reconciliation_banner",
]

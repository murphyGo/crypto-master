"""Runtime reconciliation banner + drilldown (CAH-09 / DASH-F1 split).

Extracted verbatim from ``dashboard/pages/engine.py`` (runtime-reconciliation
unit). Pure read-models over ``ActivityEvent``s plus the one Streamlit render
helper for the banner. ``engine.py`` re-exports every public symbol here so
existing import paths (notably ``trading.py``'s three reconciliation imports)
keep resolving.

Related Requirements:
- FR-030 / FR-032 / NFR-003: engine cycle status surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import pandas as pd
import streamlit as st

from src.runtime.activity_log import ActivityEvent, ActivityEventType

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


__all__ = [
    "ReconciliationBanner",
    "ReconciliationColor",
    "build_reconciliation_drilldown_dataframe",
    "build_reconciliation_status_banner",
    "latest_reconciliation_event",
    "render_reconciliation_banner",
]

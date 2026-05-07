"""Streamlit dashboard entry point (Phase 7.1).

Run with::

    streamlit run src/dashboard/app.py

This module is the chassis. Page navigation is set up via
``st.navigation`` so that each Phase 7 sub-task can register its own
``st.Page`` without touching the others — 7.2 will add Strategies,
7.3 Trading, 7.4 Feedback-Loop. For now only the Home view is wired.

Related Requirements:
- FR-032: Streamlit Web App
- NFR-003: Streamlit UI
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

import pandas as pd
import streamlit as st
from streamlit.navigation.page import StreamlitPage

# ---------------------------------------------------------------------------
# Pre-load every submodule the dashboard pages import.
#
# Streamlit re-execs each page through ``Page.run()`` -> ``exec(code,
# module.__dict__)`` with a fresh module dict. If a page's top-level
# ``from src.X.Y import Z`` happens while ``src.X`` is not yet in
# ``sys.modules``, Python's import machinery can hit
# ``KeyError: 'src.X'`` deep inside ``_find_and_load_unlocked`` —
# observed on Fly under Streamlit 1.56 even though local AppTest
# runs are clean. Force-loading the submodules here populates
# ``sys.modules`` once at app boot so every per-page exec is a cache
# hit. ``noqa: F401`` because these are intentionally unused-but-needed.
# ---------------------------------------------------------------------------
import src.feedback.audit  # noqa: F401
import src.feedback.loop  # noqa: F401
import src.proposal.engine  # noqa: F401
import src.runtime.activity_log  # noqa: F401
import src.strategy.base  # noqa: F401
import src.strategy.loader  # noqa: F401
import src.strategy.performance  # noqa: F401
import src.trading.portfolio  # noqa: F401
from src.config import get_settings
from src.dashboard.pages import engine as engine_page
from src.dashboard.pages import feedback as feedback_page
from src.dashboard.pages import strategies as strategies_page
from src.dashboard.pages import trading as trading_page
from src.dashboard.theme import (
    APP_ICON,
    APP_TAGLINE,
    APP_TITLE,
    configure_page,
)
from src.runtime.activity_log import ActivityEvent, ActivityEventType, ActivityLog
from src.runtime.safety_score import (
    RuntimeSafetyScore,
    compute_runtime_safety_score,
    inputs_from_recent_activity_events,
    recent_activity_events,
)
from src.strategy.performance import TradeHistory, TradeHistoryTracker
from src.trading.portfolio import AssetSnapshot, PortfolioTracker
from src.trading.sub_account_registry import DEFAULT_SUB_ACCOUNT_ID
from src.utils.time import ensure_utc, now_utc

SNAPSHOT_STALE_AFTER_HOURS = 6
COMMAND_CENTER_DEFAULT_MODE = "paper"
COMMAND_CENTER_AGGREGATE_SCOPE = "Aggregate"
DashboardMode = Literal["paper", "live"]
ACTIONABLE_EVENT_TYPES = {
    ActivityEventType.CYCLE_ERRORED.value,
    ActivityEventType.NOTIFICATION_FAILED.value,
    ActivityEventType.LIQUIDATED.value,
    ActivityEventType.COLD_START_BLOCKED.value,
    ActivityEventType.CORRELATION_WARNING.value,
}
ACTIONABLE_LOOKBACK_HOURS = 24
INCIDENT_DISPLAY_LIMIT = 10


@dataclass(frozen=True)
class CommandCenterStatus:
    """Read model for the Home command-center status section."""

    safety: RuntimeSafetyScore
    last_cycle_status: str
    last_cycle_started_at: datetime | None
    open_positions: int
    estimated_open_notional: Decimal
    latest_snapshot_at: datetime | None
    latest_equity: Decimal | None
    snapshot_freshness: str
    actionable_events: int
    sub_account_count: int
    mode: str
    scope: str
    exposure_rows: list[CommandCenterExposureRow]
    candidate_total: int
    candidates_awaiting_approval: int
    candidates_promoted: int
    candidates_errored: int
    incident_rows: list[CommandCenterIncidentRow]


@dataclass(frozen=True)
class CommandCenterExposureRow:
    """Grouped open exposure row for the Home command center."""

    symbol: str
    side: str
    sub_accounts: tuple[str, ...]
    open_count: int
    estimated_notional: Decimal
    estimated_margin: Decimal
    notional_pct_of_equity: float | None
    max_leverage: int

    @property
    def duplicate_across_accounts(self) -> bool:
        """Whether this exposure spans more than one sub-account."""
        return len(self.sub_accounts) > 1


@dataclass(frozen=True)
class CommandCenterIncidentRow:
    """Recent actionable event row for the Home command center."""

    timestamp: datetime
    severity: str
    event_type: str
    message: str
    sub_account_id: str
    symbol: str
    next_step: str


def render_home() -> None:
    """Landing page — overview cards + navigation hints.

    Sub-task 7.2/7.3/7.4 will replace the placeholder cards with live
    summary widgets. Keeping the home page as a function (not a
    separate file) so 7.1 stays a single chassis without spilling
    into the 7.2+ page directories.
    """
    st.title(f"{APP_ICON} {APP_TITLE}")
    st.caption(APP_TAGLINE)

    mode: DashboardMode = st.radio(
        "Command center mode",
        options=("paper", "live"),
        horizontal=True,
        format_func=lambda value: value.capitalize(),
    )
    sub_account_ids = discover_command_center_sub_accounts(mode)
    scope_options = (
        [COMMAND_CENTER_AGGREGATE_SCOPE, *sub_account_ids]
        if len(sub_account_ids) > 1
        else sub_account_ids
    )
    scope = st.selectbox("Command center scope", options=scope_options, index=0)
    status = load_command_center_status(
        mode=mode,
        scope=str(scope),
        sub_account_ids=sub_account_ids,
    )
    render_command_center_status(status)

    st.markdown("### Sections")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.success(
            "**Strategies**\n\n"
            "Registered analysis techniques and their performance trends.\n\n"
            "_Available now — see the sidebar._"
        )
    with col2:
        st.success(
            "**Trading**\n\n"
            "Active positions, recent trades, equity curve, paper vs. live.\n\n"
            "_Available now — see the sidebar._"
        )
    with col3:
        st.success(
            "**Feedback Loop**\n\n"
            "Experimental candidates, backtest verdicts, audit trail.\n\n"
            "_Available now — see the sidebar._"
        )

    st.markdown("### Getting started")
    st.markdown(
        "- Use the sidebar to switch sections.\n"
        "- Configure exchanges and trading mode via the project's `.env` file.\n"
        "- See `docs/development-plan.md` for the dashboard roadmap."
    )


def discover_command_center_sub_accounts(mode: DashboardMode) -> list[str]:
    """Discover sub-account ids for the command-center controls."""
    ids = trading_page.discover_sub_account_ids(get_settings().data_dir, mode)
    return ids or [DEFAULT_SUB_ACCOUNT_ID]


def load_command_center_status(
    *,
    mode: DashboardMode = COMMAND_CENTER_DEFAULT_MODE,
    scope: str = COMMAND_CENTER_AGGREGATE_SCOPE,
    sub_account_ids: list[str] | None = None,
) -> CommandCenterStatus:
    """Load persisted state for the Home command-center read model."""
    events = ActivityLog().read_all()
    ids = sub_account_ids or discover_command_center_sub_accounts(mode)
    load_ids = ids if scope == COMMAND_CENTER_AGGREGATE_SCOPE else [scope]

    trades: list[TradeHistory] = []
    scoped_trades: list[tuple[str, TradeHistory]] = []
    snapshots: list[AssetSnapshot] = []
    for sub_account_id in load_ids:
        trade_tracker = TradeHistoryTracker(sub_account_id=sub_account_id)
        portfolio_tracker = PortfolioTracker(
            trade_tracker=trade_tracker,
            sub_account_id=sub_account_id,
        )
        loaded_trades = trade_tracker.load_trades(mode=mode)
        trades.extend(loaded_trades)
        scoped_trades.extend((sub_account_id, trade) for trade in loaded_trades)
        snapshots.extend(portfolio_tracker.load_snapshots(mode))
    candidate_metrics = feedback_page.build_summary_metrics(
        feedback_page.load_candidate_records(feedback_page.DEFAULT_STATE_DIR)
    )

    return build_command_center_status(
        events=events,
        trades=trades,
        scoped_trades=scoped_trades,
        snapshots=snapshots,
        sub_account_count=len(ids),
        mode=mode,
        scope=scope,
        candidate_metrics=candidate_metrics,
    )


def build_command_center_status(
    *,
    events: list[ActivityEvent],
    trades: list[TradeHistory],
    snapshots: list[AssetSnapshot],
    sub_account_count: int,
    mode: str,
    scoped_trades: list[tuple[str, TradeHistory]] | None = None,
    candidate_metrics: dict[str, int] | None = None,
    scope: str = COMMAND_CENTER_AGGREGATE_SCOPE,
    now: datetime | None = None,
) -> CommandCenterStatus:
    """Build a compact operator-first status from persisted dashboard inputs."""
    cycles = engine_page.aggregate_cycles(events)
    cycle_metrics = engine_page.build_summary_metrics(events, cycles)
    safety = compute_runtime_safety_score(
        inputs_from_recent_activity_events(
            events,
            now=now,
            lookback_hours=ACTIONABLE_LOOKBACK_HOURS,
        )
    )
    latest_snapshot_at = latest_snapshot_timestamp(snapshots)
    latest_equity = latest_snapshot_equity(snapshots)
    open_trades = [trade for trade in trades if trade.status == "open"]
    scoped = scoped_trades or [(DEFAULT_SUB_ACCOUNT_ID, trade) for trade in trades]
    candidate_metrics = candidate_metrics or {}

    return CommandCenterStatus(
        safety=safety,
        last_cycle_status=cycle_metrics["last_cycle_status"] or "missing",
        last_cycle_started_at=cycle_metrics["last_cycle_started_at"],
        open_positions=len(open_trades),
        estimated_open_notional=estimate_open_notional(open_trades),
        latest_snapshot_at=latest_snapshot_at,
        latest_equity=latest_equity,
        snapshot_freshness=snapshot_freshness(latest_snapshot_at, now=now),
        actionable_events=count_actionable_events(events, now=now),
        sub_account_count=sub_account_count,
        mode=mode,
        scope=scope,
        exposure_rows=build_exposure_rows(scoped, latest_equity=latest_equity),
        candidate_total=candidate_metrics.get("total", 0),
        candidates_awaiting_approval=candidate_metrics.get("awaiting_approval", 0),
        candidates_promoted=candidate_metrics.get("promoted", 0),
        candidates_errored=candidate_metrics.get("errored", 0),
        incident_rows=build_incident_rows(events, now=now),
    )


def latest_snapshot_timestamp(snapshots: list[AssetSnapshot]) -> datetime | None:
    """Return the newest persisted portfolio snapshot timestamp."""
    if not snapshots:
        return None
    return max(ensure_utc(snapshot.timestamp) for snapshot in snapshots)


def latest_snapshot_equity(snapshots: list[AssetSnapshot]) -> Decimal | None:
    """Return total equity from the newest persisted portfolio snapshot."""
    if not snapshots:
        return None
    latest = max(snapshots, key=lambda snapshot: ensure_utc(snapshot.timestamp))
    return latest.total_equity


def snapshot_freshness(
    latest_at: datetime | None,
    *,
    now: datetime | None = None,
    stale_after_hours: int = SNAPSHOT_STALE_AFTER_HOURS,
) -> str:
    """Classify persisted snapshot freshness for operator display."""
    if latest_at is None:
        return "missing"
    current = ensure_utc(now or now_utc())
    age = current - ensure_utc(latest_at)
    if age < timedelta(0):
        return "fresh"
    return "stale" if age > timedelta(hours=stale_after_hours) else "fresh"


def estimate_open_notional(trades: list[TradeHistory]) -> Decimal:
    """Estimate open exposure from persisted entry price and quantity."""
    total = Decimal("0")
    for trade in trades:
        if trade.status != "open":
            continue
        total += trade.entry_price * trade.entry_quantity
    return total


def build_exposure_rows(
    scoped_trades: list[tuple[str, TradeHistory]],
    *,
    latest_equity: Decimal | None = None,
) -> list[CommandCenterExposureRow]:
    """Group open trades by symbol/side while preserving sub-account source."""
    grouped: dict[tuple[str, str], list[tuple[str, TradeHistory]]] = {}
    for sub_account_id, trade in scoped_trades:
        if trade.status != "open":
            continue
        key = (trade.symbol, trade.side)
        grouped.setdefault(key, []).append((sub_account_id, trade))

    rows: list[CommandCenterExposureRow] = []
    for (symbol, side), entries in sorted(grouped.items()):
        sub_accounts = tuple(sorted({sub_account_id for sub_account_id, _ in entries}))
        estimated_notional = sum(
            (trade.entry_price * trade.entry_quantity for _, trade in entries),
            Decimal("0"),
        )
        estimated_margin = sum(
            (
                (trade.entry_price * trade.entry_quantity) / Decimal(trade.leverage)
                for _, trade in entries
            ),
            Decimal("0"),
        )
        rows.append(
            CommandCenterExposureRow(
                symbol=symbol,
                side=side,
                sub_accounts=sub_accounts,
                open_count=len(entries),
                estimated_notional=estimated_notional,
                estimated_margin=estimated_margin,
                notional_pct_of_equity=(
                    float((estimated_notional / latest_equity) * Decimal("100"))
                    if latest_equity is not None and latest_equity > 0
                    else None
                ),
                max_leverage=max(trade.leverage for _, trade in entries),
            )
        )
    return rows


def count_actionable_events(
    events: list[ActivityEvent],
    *,
    now: datetime | None = None,
) -> int:
    """Count recent runtime events that deserve operator attention."""
    return len(build_incident_rows(events, now=now))


def build_incident_rows(
    events: list[ActivityEvent],
    *,
    now: datetime | None = None,
    limit: int = INCIDENT_DISPLAY_LIMIT,
) -> list[CommandCenterIncidentRow]:
    """Build recent actionable event rows for the Home command center."""
    recent = recent_activity_events(
        events,
        now=now,
        lookback_hours=ACTIONABLE_LOOKBACK_HOURS,
    )
    incidents = [
        event for event in recent if event.event_type in ACTIONABLE_EVENT_TYPES
    ]
    incidents.sort(key=lambda event: event.timestamp, reverse=True)
    return [_incident_row(event) for event in incidents[:limit]]


def _incident_row(event: ActivityEvent) -> CommandCenterIncidentRow:
    event_type = str(event.event_type)
    return CommandCenterIncidentRow(
        timestamp=ensure_utc(event.timestamp),
        severity=_incident_severity(event_type),
        event_type=event_type,
        message=event.message or "—",
        sub_account_id=str(event.details.get("sub_account_id", "—")),
        symbol=str(event.details.get("symbol", "—")),
        next_step=_incident_next_step(event_type),
    )


def _incident_severity(event_type: str) -> str:
    if event_type in {
        ActivityEventType.CYCLE_ERRORED.value,
        ActivityEventType.LIQUIDATED.value,
    }:
        return "stop"
    if event_type in {
        ActivityEventType.NOTIFICATION_FAILED.value,
        ActivityEventType.CORRELATION_WARNING.value,
    }:
        return "watch"
    return "info"


def _incident_next_step(event_type: str) -> str:
    mapping = {
        ActivityEventType.CYCLE_ERRORED.value: "Open Engine timeline",
        ActivityEventType.NOTIFICATION_FAILED.value: "Check notification route",
        ActivityEventType.LIQUIDATED.value: "Review Trading exposure",
        ActivityEventType.COLD_START_BLOCKED.value: "Review strategy evidence",
        ActivityEventType.CORRELATION_WARNING.value: "Review duplicate exposure",
    }
    return mapping.get(event_type, "Open Engine timeline")


def render_command_center_status(status: CommandCenterStatus) -> None:
    """Render the Home command-center summary."""
    st.markdown("### Command Center")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Runtime safety", status.safety.band.value, f"{status.safety.score}/100")
    c2.metric("Last cycle", status.last_cycle_status)
    c3.metric("Open positions", status.open_positions)
    c4.metric("Snapshot", status.snapshot_freshness)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Mode", status.mode)
    c6.metric("Scope", status.scope)
    c7.metric("Sub-accounts", status.sub_account_count)
    c8.metric("Actionable events", status.actionable_events)

    notional = f"{float(status.estimated_open_notional):,.2f} USDT"
    started = (
        status.last_cycle_started_at.isoformat(timespec="seconds")
        if status.last_cycle_started_at is not None
        else "none"
    )
    latest_snapshot = (
        status.latest_snapshot_at.isoformat(timespec="seconds")
        if status.latest_snapshot_at is not None
        else "none"
    )
    st.caption(
        " | ".join(
            [
                f"Estimated open notional: {notional}",
                f"Last cycle started: {started}",
                f"Latest snapshot: {latest_snapshot}",
            ]
        )
    )
    st.caption("Safety factors: " + "; ".join(status.safety.factors))

    st.markdown("#### Open Exposure")
    exposure_df = build_exposure_dataframe(status.exposure_rows)
    if exposure_df.empty:
        st.info("No open exposure in the selected command-center scope.")
    else:
        st.dataframe(exposure_df, hide_index=True, use_container_width=True)

    st.markdown("#### Recent Incidents")
    incident_df = build_incident_dataframe(status.incident_rows)
    if incident_df.empty:
        st.success("No recent actionable incidents in the last 24 hours.")
    else:
        st.dataframe(incident_df, hide_index=True, use_container_width=True)

    st.markdown("#### Strategy Evidence")
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Candidates", status.candidate_total)
    e2.metric("Awaiting approval", status.candidates_awaiting_approval)
    e3.metric("Promoted", status.candidates_promoted)
    e4.metric("Errored", status.candidates_errored)


def build_exposure_dataframe(rows: list[CommandCenterExposureRow]) -> pd.DataFrame:
    """Build the Home open-exposure table."""
    columns = [
        "Symbol",
        "Side",
        "Sub-accounts",
        "Open Count",
        "Estimated Notional",
        "Estimated Margin",
        "Notional % Equity",
        "Max Leverage",
        "Duplicate Accounts",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "Symbol": row.symbol,
                "Side": row.side.upper(),
                "Sub-accounts": ", ".join(row.sub_accounts),
                "Open Count": row.open_count,
                "Estimated Notional": float(row.estimated_notional),
                "Estimated Margin": float(row.estimated_margin),
                "Notional % Equity": (
                    round(row.notional_pct_of_equity, 2)
                    if row.notional_pct_of_equity is not None
                    else None
                ),
                "Max Leverage": f"{row.max_leverage}x",
                "Duplicate Accounts": row.duplicate_across_accounts,
            }
            for row in rows
        ],
        columns=columns,
    )


def build_incident_dataframe(rows: list[CommandCenterIncidentRow]) -> pd.DataFrame:
    """Build the Home recent-incidents table."""
    columns = [
        "Severity",
        "Event",
        "Timestamp",
        "Sub-account",
        "Symbol",
        "Message",
        "Next Step",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "Severity": row.severity,
                "Event": row.event_type,
                "Timestamp": row.timestamp.isoformat(timespec="seconds"),
                "Sub-account": row.sub_account_id,
                "Symbol": row.symbol,
                "Message": row.message,
                "Next Step": row.next_step,
            }
            for row in rows
        ],
        columns=columns,
    )


def render_sidebar() -> None:
    """Render the persistent sidebar branding/header.

    Per-page content lives inside each page function; this is just the
    chassis (title, version, divider).
    """
    with st.sidebar:
        st.markdown(f"## {APP_ICON} {APP_TITLE}")
        st.caption(APP_TAGLINE)
        st.divider()


def build_navigation() -> StreamlitPage:
    """Construct the multi-page navigation.

    Returns a Streamlit ``Page`` runner. Pages are grouped under
    "Overview" (landing) and "Sections" (per-domain views). 7.3+ will
    append additional pages to the Sections list.
    """
    home = st.Page(
        render_home,
        title="Home",
        icon="🏠",
        default=True,
    )
    strategies = st.Page(
        strategies_page.render,
        title="Strategies",
        icon="📊",
        url_path="strategies",
    )
    trading = st.Page(
        trading_page.render,
        title="Trading",
        icon="💹",
        url_path="trading",
    )
    feedback = st.Page(
        feedback_page.render,
        title="Feedback Loop",
        icon="🔁",
        url_path="feedback",
    )
    engine = st.Page(
        engine_page.render,
        title="Engine",
        icon="⚙️",
        url_path="engine",
    )
    return st.navigation(
        {
            "Overview": [home],
            "Sections": [strategies, trading, feedback, engine],
        }
    )


def main() -> None:
    """Entry point invoked by ``streamlit run``."""
    configure_page()
    render_sidebar()
    page = build_navigation()
    page.run()


# Streamlit executes the script top-to-bottom; the ``__main__`` guard
# also lets ``AppTest.from_file`` reuse the same entry point.
if __name__ == "__main__":
    main()

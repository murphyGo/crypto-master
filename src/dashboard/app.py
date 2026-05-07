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
)
from src.strategy.performance import TradeHistory, TradeHistoryTracker
from src.trading.portfolio import AssetSnapshot, PortfolioTracker
from src.trading.sub_account_registry import DEFAULT_SUB_ACCOUNT_ID
from src.utils.time import ensure_utc, now_utc

SNAPSHOT_STALE_AFTER_HOURS = 6
COMMAND_CENTER_MODE = "paper"
ACTIONABLE_EVENT_TYPES = {
    ActivityEventType.CYCLE_ERRORED.value,
    ActivityEventType.NOTIFICATION_FAILED.value,
    ActivityEventType.LIQUIDATED.value,
    ActivityEventType.COLD_START_BLOCKED.value,
    ActivityEventType.CORRELATION_WARNING.value,
}


@dataclass(frozen=True)
class CommandCenterStatus:
    """Read model for the Home command-center status section."""

    safety: RuntimeSafetyScore
    last_cycle_status: str
    last_cycle_started_at: datetime | None
    open_positions: int
    estimated_open_notional: Decimal
    latest_snapshot_at: datetime | None
    snapshot_freshness: str
    actionable_events: int
    sub_account_count: int
    mode: str


def render_home() -> None:
    """Landing page — overview cards + navigation hints.

    Sub-task 7.2/7.3/7.4 will replace the placeholder cards with live
    summary widgets. Keeping the home page as a function (not a
    separate file) so 7.1 stays a single chassis without spilling
    into the 7.2+ page directories.
    """
    st.title(f"{APP_ICON} {APP_TITLE}")
    st.caption(APP_TAGLINE)

    status = load_command_center_status()
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


def load_command_center_status() -> CommandCenterStatus:
    """Load persisted state for the Home command-center read model."""
    events = ActivityLog().read_all()
    ids = trading_page.discover_sub_account_ids(
        get_settings().data_dir,
        COMMAND_CENTER_MODE,
    )
    if not ids:
        ids = [DEFAULT_SUB_ACCOUNT_ID]

    trades: list[TradeHistory] = []
    snapshots: list[AssetSnapshot] = []
    for sub_account_id in ids:
        trade_tracker = TradeHistoryTracker(sub_account_id=sub_account_id)
        portfolio_tracker = PortfolioTracker(
            trade_tracker=trade_tracker,
            sub_account_id=sub_account_id,
        )
        trades.extend(trade_tracker.load_trades(mode=COMMAND_CENTER_MODE))
        snapshots.extend(portfolio_tracker.load_snapshots(COMMAND_CENTER_MODE))

    return build_command_center_status(
        events=events,
        trades=trades,
        snapshots=snapshots,
        sub_account_count=len(ids),
        mode=COMMAND_CENTER_MODE,
    )


def build_command_center_status(
    *,
    events: list[ActivityEvent],
    trades: list[TradeHistory],
    snapshots: list[AssetSnapshot],
    sub_account_count: int,
    mode: str,
    now: datetime | None = None,
) -> CommandCenterStatus:
    """Build a compact operator-first status from persisted dashboard inputs."""
    cycles = engine_page.aggregate_cycles(events)
    cycle_metrics = engine_page.build_summary_metrics(events, cycles)
    safety = compute_runtime_safety_score(inputs_from_recent_activity_events(events))
    latest_snapshot_at = latest_snapshot_timestamp(snapshots)
    open_trades = [trade for trade in trades if trade.status == "open"]

    return CommandCenterStatus(
        safety=safety,
        last_cycle_status=cycle_metrics["last_cycle_status"] or "missing",
        last_cycle_started_at=cycle_metrics["last_cycle_started_at"],
        open_positions=len(open_trades),
        estimated_open_notional=estimate_open_notional(open_trades),
        latest_snapshot_at=latest_snapshot_at,
        snapshot_freshness=snapshot_freshness(latest_snapshot_at, now=now),
        actionable_events=count_actionable_events(events),
        sub_account_count=sub_account_count,
        mode=mode,
    )


def latest_snapshot_timestamp(snapshots: list[AssetSnapshot]) -> datetime | None:
    """Return the newest persisted portfolio snapshot timestamp."""
    if not snapshots:
        return None
    return max(ensure_utc(snapshot.timestamp) for snapshot in snapshots)


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


def count_actionable_events(events: list[ActivityEvent]) -> int:
    """Count runtime events that deserve operator attention."""
    return sum(1 for event in events if event.event_type in ACTIONABLE_EVENT_TYPES)


def render_command_center_status(status: CommandCenterStatus) -> None:
    """Render the Home command-center summary."""
    st.markdown("### Command Center")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Runtime safety", status.safety.band.value, f"{status.safety.score}/100")
    c2.metric("Last cycle", status.last_cycle_status)
    c3.metric("Open positions", status.open_positions)
    c4.metric("Snapshot", status.snapshot_freshness)

    c5, c6, c7 = st.columns(3)
    c5.metric("Mode", status.mode)
    c6.metric("Sub-accounts", status.sub_account_count)
    c7.metric("Actionable events", status.actionable_events)

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

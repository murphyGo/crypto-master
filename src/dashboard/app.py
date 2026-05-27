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
import src.strategy.trade_autopsy  # noqa: F401
import src.trading.portfolio  # noqa: F401
from src.dashboard.pages import autopsy as autopsy_page
from src.dashboard.pages import engine as engine_page
from src.dashboard.pages import feedback as feedback_page
from src.dashboard.pages import ops as ops_page
from src.dashboard.pages import proposals as proposals_page
from src.dashboard.pages import replay as replay_page
from src.dashboard.pages import strategies as strategies_page
from src.dashboard.pages import trading as trading_page

# CAH-09 / DASH-F6: the Home command-center read-model + builders + render
# functions moved to ``pages/home.py``. ``app.py`` is now the pure navigation
# chassis. Re-export the Home public surface here so existing import paths
# (``from src.dashboard.app import build_command_center_status`` etc. and the
# tests' ``dashboard_app.load_command_center_status`` / ``dashboard_app.ActivityLog``)
# keep resolving. ``home`` imports ``page_for_key`` from this module lazily, so
# there is no import cycle.
from src.dashboard.pages.home import (  # noqa: F401
    ACTIONABLE_EVENT_TYPES,
    ACTIONABLE_LOOKBACK_HOURS,
    CANDIDATE_DISPLAY_LIMIT,
    COMMAND_CENTER_AGGREGATE_SCOPE,
    COMMAND_CENTER_DEFAULT_MODE,
    INCIDENT_DISPLAY_LIMIT,
    SNAPSHOT_STALE_AFTER_HOURS,
    ActivityLog,
    CommandCenterCandidateRow,
    CommandCenterDiagnosticRow,
    CommandCenterExposureRow,
    CommandCenterIncidentRow,
    CommandCenterStatus,
    DashboardMode,
    build_candidate_dataframe,
    build_candidate_rows,
    build_command_center_status,
    build_exposure_dataframe,
    build_exposure_rows,
    build_incident_dataframe,
    build_incident_rows,
    build_runtime_diagnostic_dataframe,
    build_runtime_diagnostic_rows,
    count_actionable_events,
    discover_command_center_sub_accounts,
    estimate_open_notional,
    latest_snapshot_equity,
    latest_snapshot_timestamp,
    load_command_center_status,
    render_command_center_links,
    render_command_center_status,
    render_home,
    snapshot_freshness,
)
from src.dashboard.theme import (
    APP_ICON,
    APP_TAGLINE,
    APP_TITLE,
    configure_page,
)


def page_for_key(page_key: str) -> StreamlitPage:
    """Return a page reference usable by st.navigation and st.page_link."""
    if page_key == "strategies":
        return st.Page(
            strategies_page.render,
            title="Strategies",
            icon="📊",
            url_path="strategies",
        )
    if page_key == "trading":
        return st.Page(
            trading_page.render,
            title="Trading",
            icon="💹",
            url_path="trading",
        )
    if page_key == "feedback":
        return st.Page(
            feedback_page.render,
            title="Feedback Loop",
            icon="🔁",
            url_path="feedback",
        )
    if page_key == "replay":
        return st.Page(
            replay_page.render,
            title="Proposal Replay",
            icon="🧪",
            url_path="replay",
        )
    if page_key == "autopsy":
        return st.Page(
            autopsy_page.render,
            title="Trade Autopsy",
            icon="🔎",
            url_path="autopsy",
        )
    if page_key == "ops":
        return st.Page(
            ops_page.render,
            title="Ops Diagnostics",
            icon="🩺",
            url_path="ops",
        )
    if page_key == "engine":
        return st.Page(
            engine_page.render,
            title="Engine",
            icon="⚙️",
            url_path="engine",
        )
    if page_key == "proposals":
        return st.Page(
            proposals_page.render,
            title="Proposal Funnel",
            icon="🪜",
            url_path="proposals",
        )
    return st.Page(render_home, title="Home", icon="🏠", default=True)


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
    strategies = page_for_key("strategies")
    trading = page_for_key("trading")
    feedback = page_for_key("feedback")
    replay = page_for_key("replay")
    autopsy = page_for_key("autopsy")
    ops = page_for_key("ops")
    engine = page_for_key("engine")
    proposals = page_for_key("proposals")
    return st.navigation(
        {
            "Overview": [home],
            "Sections": [
                strategies,
                trading,
                feedback,
                replay,
                autopsy,
                ops,
                engine,
                proposals,
            ],
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

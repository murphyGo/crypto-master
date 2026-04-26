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

from src.dashboard.theme import (
    APP_ICON,
    APP_TAGLINE,
    APP_TITLE,
    configure_page,
)


def render_home() -> None:
    """Landing page — overview cards + navigation hints.

    Sub-task 7.2/7.3/7.4 will replace the placeholder cards with live
    summary widgets. Keeping the home page as a function (not a
    separate file) so 7.1 stays a single chassis without spilling
    into the 7.2+ page directories.
    """
    st.title(f"{APP_ICON} {APP_TITLE}")
    st.caption(APP_TAGLINE)

    st.markdown("### Sections")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(
            "**Strategies**\n\n"
            "Registered analysis techniques and their performance trends.\n\n"
            "_Coming in Phase 7.2._"
        )
    with col2:
        st.info(
            "**Trading**\n\n"
            "Active positions, recent trades, equity curve, paper vs. live.\n\n"
            "_Coming in Phase 7.3._"
        )
    with col3:
        st.info(
            "**Feedback Loop**\n\n"
            "Experimental candidates, backtest verdicts, audit trail.\n\n"
            "_Coming in Phase 7.4._"
        )

    st.markdown("### Getting started")
    st.markdown(
        "- Use the sidebar to switch sections.\n"
        "- Configure exchanges and trading mode via the project's `.env` file.\n"
        "- See `docs/development-plan.md` for the dashboard roadmap."
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


def build_navigation() -> st.navigation:  # type: ignore[name-defined]
    """Construct the multi-page navigation.

    Returns a Streamlit ``Page`` runner. Pages are grouped under a
    single "Overview" section for now; 7.2+ will add their pages and
    likely additional groups.
    """
    home = st.Page(
        render_home,
        title="Home",
        icon="🏠",
        default=True,
    )
    return st.navigation({"Overview": [home]})


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

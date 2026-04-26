"""Dashboard theme + page-config helpers (Phase 7.1).

Single source of truth for the app's title, icon, and layout so every
sub-page can reuse the same values without re-stating them. Future
sub-tasks adding pages should import from here rather than redeclare.

Related Requirements:
- FR-032: Streamlit Web App
- NFR-003: Streamlit UI
"""

from __future__ import annotations

import streamlit as st

APP_TITLE = "Crypto Master"
APP_ICON = "📈"
APP_TAGLINE = "Automated crypto trading with Claude-powered analysis"

PAGE_LAYOUT = "wide"
INITIAL_SIDEBAR_STATE = "expanded"


def configure_page() -> None:
    """Apply the global ``st.set_page_config`` for every page.

    Must be the first Streamlit call in the script, so ``app.main`` calls
    this before anything else renders.
    """
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout=PAGE_LAYOUT,
        initial_sidebar_state=INITIAL_SIDEBAR_STATE,
    )


__all__ = [
    "APP_ICON",
    "APP_TAGLINE",
    "APP_TITLE",
    "INITIAL_SIDEBAR_STATE",
    "PAGE_LAYOUT",
    "configure_page",
]

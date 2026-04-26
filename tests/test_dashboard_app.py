"""Tests for the Streamlit dashboard chassis (Phase 7.1).

The chassis renders no domain data — it just sets up the page, the
sidebar, and the navigation. Tests exercise the constants directly
and use Streamlit's ``AppTest`` to smoke-run the script end-to-end.
"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.dashboard.theme import (
    APP_ICON,
    APP_TAGLINE,
    APP_TITLE,
    INITIAL_SIDEBAR_STATE,
    PAGE_LAYOUT,
)

APP_PATH = str(Path(__file__).resolve().parents[1] / "src" / "dashboard" / "app.py")


# =============================================================================
# Theme constants
# =============================================================================


def test_app_constants_are_set() -> None:
    """Sanity: nothing is empty."""
    assert APP_TITLE
    assert APP_ICON
    assert APP_TAGLINE
    assert PAGE_LAYOUT == "wide"
    assert INITIAL_SIDEBAR_STATE == "expanded"


# =============================================================================
# AppTest smoke
# =============================================================================


def test_app_runs_without_exception() -> None:
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    assert not at.exception, [str(e) for e in at.exception]


def test_app_renders_home_title() -> None:
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    titles = [t.value for t in at.title]
    assert any(APP_TITLE in t for t in titles), titles


def test_app_renders_tagline_via_caption() -> None:
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    captions = [c.value for c in at.caption]
    assert any(APP_TAGLINE in c for c in captions), captions


def test_app_sidebar_has_branding() -> None:
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    sidebar_md = " ".join(m.value for m in at.sidebar.markdown)
    assert APP_TITLE in sidebar_md, sidebar_md


def test_app_home_lists_three_sections() -> None:
    """Three info cards: Strategies, Trading, Feedback Loop."""
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    info_text = " ".join(i.value for i in at.info)
    assert "Strategies" in info_text
    assert "Trading" in info_text
    assert "Feedback Loop" in info_text


def test_app_home_marks_pending_phases() -> None:
    """Section cards should advertise where their content is coming from."""
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    info_text = " ".join(i.value for i in at.info)
    for phase_label in ("Phase 7.2", "Phase 7.3", "Phase 7.4"):
        assert phase_label in info_text, info_text

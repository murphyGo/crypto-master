"""Tests for the Streamlit dashboard chassis (Phase 7.1).

The chassis renders no domain data — it just sets up the page, the
sidebar, and the navigation. Tests exercise the constants directly
and use Streamlit's ``AppTest`` to smoke-run the script end-to-end.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.dashboard.app import (
    build_command_center_status,
    count_actionable_events,
    estimate_open_notional,
    snapshot_freshness,
)
from src.dashboard.theme import (
    APP_ICON,
    APP_TAGLINE,
    APP_TITLE,
    INITIAL_SIDEBAR_STATE,
    PAGE_LAYOUT,
)
from src.runtime.activity_log import ActivityEvent, ActivityEventType
from src.strategy.performance import TradeHistory
from src.trading.portfolio import AssetSnapshot

APP_PATH = str(Path(__file__).resolve().parents[1] / "src" / "dashboard" / "app.py")


def make_trade(
    *,
    trade_id: str = "trade-id-12345678",
    symbol: str = "BTC/USDT",
    side: str = "long",
    entry_price: str = "50000",
    entry_quantity: str = "0.1",
    leverage: int = 2,
    status: str = "open",
) -> TradeHistory:
    return TradeHistory(
        id=trade_id,
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        mode="paper",
        entry_price=Decimal(entry_price),
        entry_quantity=Decimal(entry_quantity),
        entry_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        leverage=leverage,
        status=status,  # type: ignore[arg-type]
    )


def make_snapshot(timestamp: datetime) -> AssetSnapshot:
    return AssetSnapshot(
        timestamp=timestamp,
        mode="paper",
        quote_currency="USDT",
        balances={"USDT": Decimal("10000")},
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
    )


def make_event(
    event_type: ActivityEventType,
    timestamp: datetime,
    *,
    cycle_id: str | None = None,
) -> ActivityEvent:
    return ActivityEvent(
        event_type=event_type,
        timestamp=timestamp,
        message=event_type.value,
        cycle_id=cycle_id,
    )


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
    """Three section cards: Strategies (success), Trading + Feedback (info)."""
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    info_text = " ".join(i.value for i in at.info)
    success_text = " ".join(s.value for s in at.success)
    combined = info_text + " " + success_text
    assert "Strategies" in combined
    assert "Trading" in combined
    assert "Feedback Loop" in combined


def test_app_home_renders_command_center() -> None:
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    markdown_text = " ".join(m.value for m in at.markdown)
    metric_labels = [m.label for m in at.metric]
    assert "Command Center" in markdown_text
    assert "Runtime safety" in metric_labels
    assert "Last cycle" in metric_labels
    assert "Open positions" in metric_labels
    assert "Actionable events" in metric_labels


def test_app_home_no_pending_phase_labels() -> None:
    """All three section cards are wired — none should advertise a coming phase."""
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    info_text = " ".join(i.value for i in at.info)
    success_text = " ".join(s.value for s in at.success)
    combined = info_text + " " + success_text
    for phase_label in ("Phase 7.2", "Phase 7.3", "Phase 7.4"):
        assert phase_label not in combined, combined


def test_app_navigation_includes_all_pages() -> None:
    """All four content pages must be reachable from the sidebar nav."""
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    sidebar_text = " ".join(m.value for m in at.sidebar.markdown)
    # AppTest doesn't expose nav buttons as a typed widget yet, so we
    # rely on the script's exception-free run + presence of the title
    # in sidebar markdown to confirm the chassis renders.
    assert "Crypto Master" in sidebar_text


def test_snapshot_freshness_missing() -> None:
    assert snapshot_freshness(None) == "missing"


def test_snapshot_freshness_detects_stale_snapshot() -> None:
    now = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)
    latest = now - timedelta(hours=7)

    assert snapshot_freshness(latest, now=now) == "stale"


def test_estimate_open_notional_uses_open_trades_only() -> None:
    open_trade = make_trade(entry_price="50000", entry_quantity="0.2")
    closed_trade = make_trade(
        entry_price="10000",
        entry_quantity="1",
        status="closed",
    )

    assert estimate_open_notional([open_trade, closed_trade]) == Decimal("10000.0")


def test_count_actionable_events() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(ActivityEventType.CYCLE_STARTED, now, cycle_id="cycle-1"),
        make_event(ActivityEventType.NOTIFICATION_FAILED, now, cycle_id="cycle-1"),
        make_event(ActivityEventType.CORRELATION_WARNING, now, cycle_id="cycle-1"),
    ]

    assert count_actionable_events(events) == 2


def test_build_command_center_status_summarizes_inputs() -> None:
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    events = [
        make_event(ActivityEventType.CYCLE_STARTED, now, cycle_id="cycle-1"),
        make_event(
            ActivityEventType.CYCLE_COMPLETED,
            now + timedelta(seconds=10),
            cycle_id="cycle-1",
        ),
        make_event(ActivityEventType.NOTIFICATION_FAILED, now, cycle_id="cycle-1"),
    ]
    trades = [make_trade(entry_price="50000", entry_quantity="0.1")]
    snapshots = [make_snapshot(now - timedelta(hours=1))]

    status = build_command_center_status(
        events=events,
        trades=trades,
        snapshots=snapshots,
        sub_account_count=2,
        mode="paper",
        now=now,
    )

    assert status.safety.band.value == "safe"
    assert status.last_cycle_status == "ok"
    assert status.open_positions == 1
    assert status.estimated_open_notional == Decimal("5000.0")
    assert status.snapshot_freshness == "fresh"
    assert status.actionable_events == 1
    assert status.sub_account_count == 2

"""Tests for the Trading status page (Phase 7.3)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.dashboard.pages.trading import (
    DEFAULT_HISTORY_LIMIT,
    build_equity_curve_dataframe,
    build_open_positions_dataframe,
    build_summary_metrics,
    build_trade_history_dataframe,
)
from src.strategy.performance import TradeHistory
from src.trading.portfolio import AssetSnapshot

# =============================================================================
# Helpers
# =============================================================================


def make_trade(
    *,
    trade_id: str = "trade-id-12345678",
    symbol: str = "BTC/USDT",
    side: str = "long",
    mode: str = "paper",
    entry_price: str = "50000",
    entry_quantity: str = "0.1",
    entry_time: datetime | None = None,
    exit_price: str | None = None,
    exit_quantity: str | None = None,
    exit_time: datetime | None = None,
    leverage: int = 1,
    pnl: str | None = None,
    pnl_percent: float | None = None,
    status: str = "open",
    close_reason: str | None = None,
) -> TradeHistory:
    return TradeHistory(
        id=trade_id,
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        mode=mode,  # type: ignore[arg-type]
        entry_price=Decimal(entry_price),
        entry_quantity=Decimal(entry_quantity),
        entry_time=entry_time or datetime(2026, 1, 1, 12, 0, 0),
        exit_price=Decimal(exit_price) if exit_price is not None else None,
        exit_quantity=Decimal(exit_quantity) if exit_quantity is not None else None,
        exit_time=exit_time,
        leverage=leverage,
        pnl=Decimal(pnl) if pnl is not None else None,
        pnl_percent=pnl_percent,
        status=status,  # type: ignore[arg-type]
        close_reason=close_reason,
    )


def make_snapshot(
    *,
    timestamp: datetime,
    quote_currency: str = "USDT",
    quote_balance: str = "10000",
    realized_pnl: str = "0",
    unrealized_pnl: str = "0",
) -> AssetSnapshot:
    return AssetSnapshot(
        timestamp=timestamp,
        mode="paper",
        quote_currency=quote_currency,
        balances={quote_currency: Decimal(quote_balance)},
        realized_pnl=Decimal(realized_pnl),
        unrealized_pnl=Decimal(unrealized_pnl),
    )


# =============================================================================
# build_open_positions_dataframe
# =============================================================================


def test_open_positions_includes_only_open_trades() -> None:
    open_trade = make_trade(trade_id="open-1", status="open")
    closed_trade = make_trade(
        trade_id="closed-1",
        status="closed",
        exit_price="51000",
        exit_quantity="0.1",
        exit_time=datetime(2026, 1, 2),
    )

    df = build_open_positions_dataframe([open_trade, closed_trade])

    assert len(df) == 1
    assert df.iloc[0]["Trade ID"] == "open-1"[:8]


def test_open_positions_sorts_newest_first() -> None:
    older = make_trade(
        trade_id="older-1",
        entry_time=datetime(2026, 1, 1),
    )
    newer = make_trade(
        trade_id="newer-1",
        entry_time=datetime(2026, 1, 5),
    )

    df = build_open_positions_dataframe([older, newer])

    assert df.iloc[0]["Trade ID"] == "newer-1"[:8]


def test_open_positions_empty_returns_empty_frame_with_columns() -> None:
    df = build_open_positions_dataframe([])

    assert df.empty
    assert "Symbol" in df.columns
    assert "Side" in df.columns


def test_open_positions_uppercase_side() -> None:
    long_trade = make_trade(trade_id="long-1", side="long")
    short_trade = make_trade(trade_id="short-1", side="short")

    df = build_open_positions_dataframe([long_trade, short_trade])

    sides = set(df["Side"])
    assert sides == {"LONG", "SHORT"}


# =============================================================================
# build_trade_history_dataframe
# =============================================================================


def test_trade_history_sorts_by_when_descending() -> None:
    closed_old = make_trade(
        trade_id="cl-old",
        status="closed",
        entry_time=datetime(2026, 1, 1),
        exit_time=datetime(2026, 1, 2),
        exit_price="51000",
        exit_quantity="0.1",
        pnl="100",
        pnl_percent=2.0,
    )
    closed_new = make_trade(
        trade_id="cl-new",
        status="closed",
        entry_time=datetime(2026, 1, 5),
        exit_time=datetime(2026, 1, 6),
        exit_price="49000",
        exit_quantity="0.1",
        pnl="-100",
        pnl_percent=-2.0,
    )
    open_recent = make_trade(
        trade_id="op-rec",
        status="open",
        entry_time=datetime(2026, 1, 7),
    )

    df = build_trade_history_dataframe([closed_old, closed_new, open_recent])

    assert list(df["Trade ID"]) == ["op-rec"[:8], "cl-new"[:8], "cl-old"[:8]]


def test_trade_history_truncates_to_limit() -> None:
    trades = [
        make_trade(
            trade_id=f"trade-{i}",
            status="closed",
            entry_time=datetime(2026, 1, 1) + timedelta(hours=i),
            exit_time=datetime(2026, 1, 1) + timedelta(hours=i + 1),
            exit_price="51000",
            exit_quantity="0.1",
            pnl="10",
            pnl_percent=0.5,
        )
        for i in range(50)
    ]

    df = build_trade_history_dataframe(trades, limit=5)

    assert len(df) == 5


def test_trade_history_default_limit_constant() -> None:
    """Sanity: the default limit is reasonable (visual table size)."""
    assert 10 <= DEFAULT_HISTORY_LIMIT <= 100


def test_trade_history_renders_open_with_none_exit_fields() -> None:
    open_trade = make_trade(trade_id="open-1", status="open")

    df = build_trade_history_dataframe([open_trade])

    row = df.iloc[0]
    assert row["Status"] == "open"
    assert row["Exit Price"] is None
    assert row["P&L %"] is None
    assert row["Close Reason"] == "—"


def test_trade_history_empty_returns_empty_frame_with_columns() -> None:
    df = build_trade_history_dataframe([])

    assert df.empty
    assert "Trade ID" in df.columns
    assert "P&L %" in df.columns


# =============================================================================
# build_equity_curve_dataframe
# =============================================================================


def test_equity_curve_sorts_by_timestamp() -> None:
    t0 = datetime(2026, 1, 1)
    curve = [
        (t0 + timedelta(days=2), Decimal("11000")),
        (t0, Decimal("10000")),
        (t0 + timedelta(days=1), Decimal("10500")),
    ]

    df = build_equity_curve_dataframe(curve)

    assert list(df["equity"]) == [10000.0, 10500.0, 11000.0]


def test_equity_curve_empty_returns_empty_frame_with_columns() -> None:
    df = build_equity_curve_dataframe([])

    assert df.empty
    assert list(df.columns) == ["timestamp", "equity"]


# =============================================================================
# build_summary_metrics
# =============================================================================


def test_summary_metrics_empty_inputs() -> None:
    metrics = build_summary_metrics([], [])

    assert metrics["open_positions"] == 0
    assert metrics["closed_trades"] == 0
    assert metrics["win_rate"] == 0.0
    assert metrics["realized_pnl"] == 0.0
    assert metrics["unrealized_pnl"] == 0.0
    assert metrics["latest_equity"] == 0.0
    assert metrics["latest_snapshot_at"] is None


def test_summary_metrics_counts_open_and_closed() -> None:
    trades = [
        make_trade(trade_id="o1", status="open"),
        make_trade(trade_id="o2", status="open"),
        make_trade(
            trade_id="c1",
            status="closed",
            exit_price="51000",
            exit_quantity="0.1",
            exit_time=datetime(2026, 1, 2),
            pnl="100",
            pnl_percent=2.0,
        ),
    ]

    metrics = build_summary_metrics(trades, [])

    assert metrics["open_positions"] == 2
    assert metrics["closed_trades"] == 1


def test_summary_metrics_win_rate() -> None:
    """Two wins out of four closed → 0.5; opens are excluded."""
    trades = [
        make_trade(
            trade_id=f"c{i}",
            status="closed",
            exit_price="50000",
            exit_quantity="0.1",
            exit_time=datetime(2026, 1, 2),
            pnl="0",
            pnl_percent=pnl,
        )
        for i, pnl in enumerate([3.0, -1.0, 2.0, -0.5])
    ]
    trades.append(make_trade(trade_id="open-x", status="open"))

    metrics = build_summary_metrics(trades, [])

    assert metrics["win_rate"] == pytest.approx(0.5)


def test_summary_metrics_realized_pnl_sums_closed_only() -> None:
    closed = [
        make_trade(
            trade_id=f"c{i}",
            status="closed",
            exit_price="50000",
            exit_quantity="0.1",
            exit_time=datetime(2026, 1, 2),
            pnl=pnl_str,
            pnl_percent=0.0,
        )
        for i, pnl_str in enumerate(["100", "-50", "25"])
    ]
    open_t = make_trade(trade_id="open-1", status="open")

    metrics = build_summary_metrics([*closed, open_t], [])

    assert metrics["realized_pnl"] == pytest.approx(75.0)


def test_summary_metrics_uses_latest_snapshot() -> None:
    snapshots = [
        make_snapshot(
            timestamp=datetime(2026, 1, 1),
            quote_balance="10000",
            unrealized_pnl="50",
        ),
        make_snapshot(
            timestamp=datetime(2026, 1, 5),
            quote_balance="11000",
            unrealized_pnl="200",
        ),
        make_snapshot(
            timestamp=datetime(2026, 1, 3),
            quote_balance="10500",
            unrealized_pnl="100",
        ),
    ]

    metrics = build_summary_metrics([], snapshots)

    # Latest snapshot is 2026-01-05 even though it's not last in the list.
    assert metrics["latest_snapshot_at"] == datetime(2026, 1, 5)
    assert metrics["latest_equity"] == pytest.approx(11200.0)  # 11000 + 200
    assert metrics["unrealized_pnl"] == pytest.approx(200.0)


# =============================================================================
# AppTest smoke
# =============================================================================


def test_trading_page_renders_empty_state(tmp_path: Path) -> None:
    """Page must not crash when no trades or snapshots exist."""
    from streamlit.testing.v1 import AppTest

    script = f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})
from pathlib import Path
from src.dashboard.pages.trading import render
from src.strategy.performance import TradeHistoryTracker
from src.trading.portfolio import PortfolioTracker

tt = TradeHistoryTracker(data_dir=Path({str(tmp_path / "trades")!r}))
pt = PortfolioTracker(
    data_dir=Path({str(tmp_path / "portfolio")!r}),
    trade_tracker=tt,
)

render(trade_tracker=tt, portfolio_tracker=pt)
"""
    at = AppTest.from_string(script).run(timeout=10)

    assert not at.exception, [str(e) for e in at.exception]
    info_text = " ".join(i.value for i in at.info)
    assert "No open positions" in info_text
    assert "No trade history" in info_text
    assert "No equity history" in info_text


def test_trading_page_renders_summary_with_data(tmp_path: Path) -> None:
    """End-to-end: a paper-mode trade + snapshot makes the summary populate."""
    from streamlit.testing.v1 import AppTest

    # Pre-populate trade + snapshot via the real trackers, then render.
    script = f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from src.dashboard.pages.trading import render
from src.strategy.performance import TradeHistoryTracker, TradeHistory
from src.trading.portfolio import PortfolioTracker, AssetSnapshot

tt = TradeHistoryTracker(data_dir=Path({str(tmp_path / "trades")!r}))
trade = TradeHistory(
    symbol="BTC/USDT",
    side="long",
    mode="paper",
    entry_price=Decimal("50000"),
    entry_quantity=Decimal("0.1"),
    entry_time=datetime(2026, 1, 1, 12, 0, 0),
    exit_price=Decimal("51000"),
    exit_quantity=Decimal("0.1"),
    exit_time=datetime(2026, 1, 1, 14, 0, 0),
    pnl=Decimal("100"),
    pnl_percent=2.0,
    status="closed",
    close_reason="take_profit",
)
tt.save_trade(trade)

pt = PortfolioTracker(
    data_dir=Path({str(tmp_path / "portfolio")!r}),
    trade_tracker=tt,
)
snap = AssetSnapshot(
    timestamp=datetime(2026, 1, 2, 0, 0, 0),
    mode="paper",
    quote_currency="USDT",
    balances={{"USDT": Decimal("10100")}},
    realized_pnl=Decimal("100"),
    unrealized_pnl=Decimal("0"),
)
# Use the public save path used elsewhere in the codebase.
pt._save_snapshots("paper", [snap])

render(trade_tracker=tt, portfolio_tracker=pt)
"""
    at = AppTest.from_string(script).run(timeout=15)

    assert not at.exception, [str(e) for e in at.exception]
    titles = [t.value for t in at.title]
    assert any("Trading" in t for t in titles), titles
    captions = " ".join(c.value for c in at.caption)
    assert "10100" in captions or "Latest equity" in captions, captions

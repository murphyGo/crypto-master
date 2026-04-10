"""Tests for the portfolio management module."""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.strategy.performance import TradeHistoryTracker
from src.trading.portfolio import (
    AssetSnapshot,
    Portfolio,
    PortfolioTracker,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def trade_tracker(tmp_path: Path) -> TradeHistoryTracker:
    """Fresh TradeHistoryTracker under tmp_path."""
    return TradeHistoryTracker(data_dir=tmp_path / "trades")


@pytest.fixture
def portfolio_tracker(
    tmp_path: Path, trade_tracker: TradeHistoryTracker
) -> PortfolioTracker:
    """PortfolioTracker wired to the same tmp_path as trade_tracker."""
    return PortfolioTracker(
        data_dir=tmp_path / "portfolio",
        trade_tracker=trade_tracker,
    )


def _open_and_close(
    tracker: TradeHistoryTracker,
    *,
    mode: str = "paper",
    symbol: str = "BTC/USDT",
    side: str = "long",
    entry: str = "50000",
    qty: str = "0.1",
    leverage: int = 10,
    exit_price: str = "51000",
) -> None:
    """Helper: open a trade and immediately close it."""
    trade = tracker.open_trade(
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        entry_price=Decimal(entry),
        entry_quantity=Decimal(qty),
        mode=mode,  # type: ignore[arg-type]
        leverage=leverage,
    )
    tracker.close_trade(
        trade_id=trade.id,
        exit_price=Decimal(exit_price),
        close_reason="manual",
    )


# =============================================================================
# AssetSnapshot model
# =============================================================================


class TestAssetSnapshot:
    """Tests for the AssetSnapshot model."""

    def test_default_timestamp(self) -> None:
        """Timestamp defaults to now."""
        before = datetime.now()
        snap = AssetSnapshot(mode="paper", quote_currency="USDT")
        after = datetime.now()
        assert before <= snap.timestamp <= after

    def test_balances_coercion(self) -> None:
        """String/float balance values are coerced to Decimal."""
        snap = AssetSnapshot(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": "1000", "BTC": 0.5},  # type: ignore[dict-item]
        )
        assert snap.balances["USDT"] == Decimal("1000")
        assert snap.balances["BTC"] == Decimal("0.5")

    def test_quote_balance(self) -> None:
        """quote_balance returns the entry matching quote_currency."""
        snap = AssetSnapshot(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("1500"), "BTC": Decimal("0.2")},
        )
        assert snap.quote_balance == Decimal("1500")

    def test_quote_balance_missing_defaults_zero(self) -> None:
        """quote_balance returns 0 if quote currency is absent."""
        snap = AssetSnapshot(
            mode="paper",
            quote_currency="USDT",
            balances={"BTC": Decimal("0.1")},
        )
        assert snap.quote_balance == Decimal("0")

    def test_total_equity(self) -> None:
        """total_equity = quote_balance + unrealized_pnl."""
        snap = AssetSnapshot(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("10000")},
            unrealized_pnl=Decimal("250"),
        )
        assert snap.total_equity == Decimal("10250")

    def test_total_pnl(self) -> None:
        """total_pnl = realized + unrealized."""
        snap = AssetSnapshot(
            mode="paper",
            quote_currency="USDT",
            realized_pnl=Decimal("500"),
            unrealized_pnl=Decimal("200"),
        )
        assert snap.total_pnl == Decimal("700")


# =============================================================================
# Portfolio model
# =============================================================================


class TestPortfolio:
    """Tests for the Portfolio view model."""

    def test_total_equity_and_pnl(self) -> None:
        """Portfolio math mirrors AssetSnapshot."""
        portfolio = Portfolio(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("9500"), "BTC": Decimal("0.1")},
            realized_pnl=Decimal("300"),
            unrealized_pnl=Decimal("150"),
            open_positions_count=2,
            closed_trades_count=5,
        )
        assert portfolio.quote_balance == Decimal("9500")
        assert portfolio.total_equity == Decimal("9650")
        assert portfolio.total_pnl == Decimal("450")


# =============================================================================
# PortfolioTracker: realized P&L
# =============================================================================


class TestRealizedPnL:
    """Tests for PortfolioTracker.calculate_realized_pnl."""

    def test_no_trades_returns_zero(
        self, portfolio_tracker: PortfolioTracker
    ) -> None:
        """No closed trades → zero realized P&L."""
        assert portfolio_tracker.calculate_realized_pnl("paper") == Decimal("0")

    def test_sums_closed_trade_pnl(
        self,
        portfolio_tracker: PortfolioTracker,
        trade_tracker: TradeHistoryTracker,
    ) -> None:
        """Realized P&L sums closed trade.pnl values."""
        # Trade 1: long 0.1 BTC, entry 50000 -> exit 51000, 10x
        # pnl = (51000-50000) * 0.1 * 10 = 1000
        _open_and_close(trade_tracker, exit_price="51000")
        # Trade 2: long 0.1 BTC, entry 50000 -> exit 49500
        # pnl = (49500-50000) * 0.1 * 10 = -500
        _open_and_close(trade_tracker, exit_price="49500")

        realized = portfolio_tracker.calculate_realized_pnl("paper")
        assert realized == Decimal("500")

    def test_excludes_open_trades(
        self,
        portfolio_tracker: PortfolioTracker,
        trade_tracker: TradeHistoryTracker,
    ) -> None:
        """Open trades are not counted in realized P&L."""
        _open_and_close(trade_tracker, exit_price="51000")  # +1000
        trade_tracker.open_trade(
            symbol="ETH/USDT",
            side="long",
            entry_price=Decimal("3000"),
            entry_quantity=Decimal("1"),
            mode="paper",
            leverage=5,
        )  # open, no pnl
        assert (
            portfolio_tracker.calculate_realized_pnl("paper") == Decimal("1000")
        )

    def test_mode_separation(
        self,
        portfolio_tracker: PortfolioTracker,
        trade_tracker: TradeHistoryTracker,
    ) -> None:
        """Realized P&L is computed per mode."""
        _open_and_close(trade_tracker, mode="paper", exit_price="51000")
        _open_and_close(trade_tracker, mode="live", exit_price="52000")

        paper = portfolio_tracker.calculate_realized_pnl("paper")
        live = portfolio_tracker.calculate_realized_pnl("live")
        assert paper == Decimal("1000")
        assert live == Decimal("2000")


# =============================================================================
# PortfolioTracker: unrealized P&L
# =============================================================================


class TestUnrealizedPnL:
    """Tests for PortfolioTracker.calculate_unrealized_pnl."""

    def test_no_open_trades(
        self, portfolio_tracker: PortfolioTracker
    ) -> None:
        """Empty open-trade set → zero unrealized."""
        result = portfolio_tracker.calculate_unrealized_pnl(
            "paper", {"BTC/USDT": Decimal("50000")}
        )
        assert result == Decimal("0")

    def test_long_unrealized_profit(
        self,
        portfolio_tracker: PortfolioTracker,
        trade_tracker: TradeHistoryTracker,
    ) -> None:
        """Long position gains as price rises."""
        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
            leverage=10,
        )
        unreal = portfolio_tracker.calculate_unrealized_pnl(
            "paper", {"BTC/USDT": Decimal("51000")}
        )
        # (51000-50000) * 0.1 * 10 = 1000
        assert unreal == Decimal("1000")

    def test_short_unrealized_profit(
        self,
        portfolio_tracker: PortfolioTracker,
        trade_tracker: TradeHistoryTracker,
    ) -> None:
        """Short position gains as price falls."""
        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="short",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
            leverage=10,
        )
        unreal = portfolio_tracker.calculate_unrealized_pnl(
            "paper", {"BTC/USDT": Decimal("49000")}
        )
        # (50000-49000) * 0.1 * 10 = 1000
        assert unreal == Decimal("1000")

    def test_multiple_positions_summed(
        self,
        portfolio_tracker: PortfolioTracker,
        trade_tracker: TradeHistoryTracker,
    ) -> None:
        """Unrealized P&L sums across positions."""
        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
            leverage=10,
        )
        trade_tracker.open_trade(
            symbol="ETH/USDT",
            side="long",
            entry_price=Decimal("3000"),
            entry_quantity=Decimal("1"),
            mode="paper",
            leverage=5,
        )
        unreal = portfolio_tracker.calculate_unrealized_pnl(
            "paper",
            {
                "BTC/USDT": Decimal("51000"),  # +1000
                "ETH/USDT": Decimal("3100"),  # +500
            },
        )
        assert unreal == Decimal("1500")

    def test_missing_price_skips_position(
        self,
        portfolio_tracker: PortfolioTracker,
        trade_tracker: TradeHistoryTracker,
    ) -> None:
        """Positions with no current price are skipped, not zeroed."""
        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
            leverage=10,
        )
        trade_tracker.open_trade(
            symbol="ETH/USDT",
            side="long",
            entry_price=Decimal("3000"),
            entry_quantity=Decimal("1"),
            mode="paper",
            leverage=5,
        )
        unreal = portfolio_tracker.calculate_unrealized_pnl(
            "paper", {"BTC/USDT": Decimal("51000")}  # no ETH price
        )
        assert unreal == Decimal("1000")  # only BTC contributes


# =============================================================================
# PortfolioTracker: get_portfolio
# =============================================================================


class TestGetPortfolio:
    """Tests for PortfolioTracker.get_portfolio."""

    def test_empty_mode(
        self, portfolio_tracker: PortfolioTracker
    ) -> None:
        """Empty mode returns portfolio with zeros and correct counts."""
        portfolio = portfolio_tracker.get_portfolio(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("10000")},
        )
        assert portfolio.mode == "paper"
        assert portfolio.quote_balance == Decimal("10000")
        assert portfolio.realized_pnl == Decimal("0")
        assert portfolio.unrealized_pnl == Decimal("0")
        assert portfolio.open_positions_count == 0
        assert portfolio.closed_trades_count == 0
        assert portfolio.total_equity == Decimal("10000")

    def test_with_closed_and_open(
        self,
        portfolio_tracker: PortfolioTracker,
        trade_tracker: TradeHistoryTracker,
    ) -> None:
        """Portfolio aggregates closed + open + balances + prices."""
        _open_and_close(trade_tracker, exit_price="51000")  # +1000 realized
        trade_tracker.open_trade(
            symbol="ETH/USDT",
            side="long",
            entry_price=Decimal("3000"),
            entry_quantity=Decimal("1"),
            mode="paper",
            leverage=5,
        )

        portfolio = portfolio_tracker.get_portfolio(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("11000")},
            current_prices={"ETH/USDT": Decimal("3100")},
        )
        assert portfolio.realized_pnl == Decimal("1000")
        assert portfolio.unrealized_pnl == Decimal("500")  # (3100-3000)*1*5
        assert portfolio.open_positions_count == 1
        assert portfolio.closed_trades_count == 1
        assert portfolio.total_equity == Decimal("11500")
        assert portfolio.total_pnl == Decimal("1500")

    def test_without_current_prices(
        self,
        portfolio_tracker: PortfolioTracker,
        trade_tracker: TradeHistoryTracker,
    ) -> None:
        """Missing current_prices yields zero unrealized."""
        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
            leverage=10,
        )
        portfolio = portfolio_tracker.get_portfolio(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("9500")},
        )
        assert portfolio.unrealized_pnl == Decimal("0")
        assert portfolio.open_positions_count == 1


# =============================================================================
# PortfolioTracker: record / load snapshots
# =============================================================================


class TestSnapshots:
    """Tests for snapshot persistence and loading."""

    def test_record_and_load(
        self, portfolio_tracker: PortfolioTracker
    ) -> None:
        """A recorded snapshot can be reloaded."""
        snap = portfolio_tracker.record_snapshot(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("10000")},
        )
        loaded = portfolio_tracker.load_snapshots("paper")
        assert len(loaded) == 1
        assert loaded[0].timestamp == snap.timestamp
        assert loaded[0].quote_balance == Decimal("10000")

    def test_snapshot_captures_pnl(
        self,
        portfolio_tracker: PortfolioTracker,
        trade_tracker: TradeHistoryTracker,
    ) -> None:
        """Snapshot captures realized and unrealized P&L at record time."""
        _open_and_close(trade_tracker, exit_price="51000")  # realized +1000
        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
            leverage=10,
        )

        snap = portfolio_tracker.record_snapshot(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("10500")},
            current_prices={"BTC/USDT": Decimal("51000")},
        )
        assert snap.realized_pnl == Decimal("1000")
        assert snap.unrealized_pnl == Decimal("1000")
        assert snap.total_equity == Decimal("11500")
        assert snap.total_pnl == Decimal("2000")

    def test_append_snapshots(
        self, portfolio_tracker: PortfolioTracker
    ) -> None:
        """Subsequent snapshots append, not overwrite."""
        portfolio_tracker.record_snapshot(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("10000")},
        )
        portfolio_tracker.record_snapshot(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("10100")},
        )
        loaded = portfolio_tracker.load_snapshots("paper")
        assert len(loaded) == 2
        assert loaded[0].quote_balance == Decimal("10000")
        assert loaded[1].quote_balance == Decimal("10100")

    def test_mode_separation_in_storage(
        self, portfolio_tracker: PortfolioTracker, tmp_path: Path
    ) -> None:
        """Snapshots for different modes go to different files."""
        portfolio_tracker.record_snapshot(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("10000")},
        )
        portfolio_tracker.record_snapshot(
            mode="live",
            quote_currency="USDT",
            balances={"USDT": Decimal("5000")},
        )

        paper_snaps = portfolio_tracker.load_snapshots("paper")
        live_snaps = portfolio_tracker.load_snapshots("live")
        assert len(paper_snaps) == 1
        assert len(live_snaps) == 1
        assert paper_snaps[0].quote_balance == Decimal("10000")
        assert live_snaps[0].quote_balance == Decimal("5000")

        # Verify on-disk layout
        assert (tmp_path / "portfolio" / "paper" / "snapshots.json").exists()
        assert (tmp_path / "portfolio" / "live" / "snapshots.json").exists()

    def test_load_empty(
        self, portfolio_tracker: PortfolioTracker
    ) -> None:
        """Loading with no snapshots returns []."""
        assert portfolio_tracker.load_snapshots("paper") == []

    def test_load_with_date_range(
        self, portfolio_tracker: PortfolioTracker
    ) -> None:
        """Snapshots can be filtered by [start, end]."""
        now = datetime.now()
        older = AssetSnapshot(
            timestamp=now - timedelta(hours=2),
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("9000")},
        )
        middle = AssetSnapshot(
            timestamp=now - timedelta(hours=1),
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("9500")},
        )
        newest = AssetSnapshot(
            timestamp=now,
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("10000")},
        )
        portfolio_tracker._save_snapshots(
            "paper", [older, middle, newest]
        )

        result = portfolio_tracker.load_snapshots(
            "paper",
            start=now - timedelta(hours=1, minutes=30),
            end=now - timedelta(minutes=10),
        )
        assert len(result) == 1
        assert result[0].quote_balance == Decimal("9500")

    def test_load_corrupt_file_returns_empty(
        self,
        portfolio_tracker: PortfolioTracker,
        tmp_path: Path,
    ) -> None:
        """Malformed snapshot file yields an empty list, not a crash."""
        path = (
            tmp_path / "portfolio" / "paper" / "snapshots.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json")
        assert portfolio_tracker.load_snapshots("paper") == []

    def test_snapshot_roundtrip_preserves_decimals(
        self, portfolio_tracker: PortfolioTracker
    ) -> None:
        """Decimal precision survives a save/load round trip."""
        portfolio_tracker.record_snapshot(
            mode="paper",
            quote_currency="USDT",
            balances={
                "USDT": Decimal("1234.56789"),
                "BTC": Decimal("0.12345678"),
            },
        )
        loaded = portfolio_tracker.load_snapshots("paper")
        assert loaded[0].balances["USDT"] == Decimal("1234.56789")
        assert loaded[0].balances["BTC"] == Decimal("0.12345678")


# =============================================================================
# PortfolioTracker: equity curve and deletion
# =============================================================================


class TestEquityCurve:
    """Tests for equity curve and deletion helpers."""

    def test_equity_curve(
        self, portfolio_tracker: PortfolioTracker
    ) -> None:
        """get_equity_curve returns (timestamp, equity) pairs."""
        portfolio_tracker.record_snapshot(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("10000")},
        )
        portfolio_tracker.record_snapshot(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("10500")},
        )

        curve = portfolio_tracker.get_equity_curve("paper")
        assert len(curve) == 2
        assert curve[0][1] == Decimal("10000")
        assert curve[1][1] == Decimal("10500")

    def test_delete_snapshots(
        self, portfolio_tracker: PortfolioTracker
    ) -> None:
        """delete_snapshots removes stored data for a mode."""
        portfolio_tracker.record_snapshot(
            mode="paper",
            quote_currency="USDT",
            balances={"USDT": Decimal("10000")},
        )
        assert portfolio_tracker.delete_snapshots("paper") is True
        assert portfolio_tracker.load_snapshots("paper") == []

    def test_delete_nonexistent_mode(
        self, portfolio_tracker: PortfolioTracker
    ) -> None:
        """Deleting a mode with nothing stored returns False."""
        assert portfolio_tracker.delete_snapshots("paper") is False

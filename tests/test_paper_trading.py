"""Tests for the paper trading module.

Tests the PaperBalance, PaperTrader, and related classes.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from src.models import Position
from src.trading.paper import (
    InsufficientPaperBalanceError,
    OpenPosition,
    PaperBalance,
    PaperTrader,
    PaperTradingError,
)


# =============================================================================
# PaperBalance Tests
# =============================================================================


class TestPaperBalance:
    """Tests for PaperBalance class."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        balance = PaperBalance(currency="USDT")
        assert balance.currency == "USDT"
        assert balance.free == Decimal("0")
        assert balance.locked == Decimal("0")
        assert balance.total == Decimal("0")

    def test_init_with_values(self) -> None:
        """Test initialization with values."""
        balance = PaperBalance(
            currency="USDT",
            free=Decimal("1000"),
            locked=Decimal("500"),
        )
        assert balance.free == Decimal("1000")
        assert balance.locked == Decimal("500")
        assert balance.total == Decimal("1500")

    def test_lock_success(self) -> None:
        """Test successful lock operation."""
        balance = PaperBalance(currency="USDT", free=Decimal("1000"))
        balance.lock(Decimal("400"))
        assert balance.free == Decimal("600")
        assert balance.locked == Decimal("400")
        assert balance.total == Decimal("1000")

    def test_lock_insufficient_balance(self) -> None:
        """Test lock with insufficient balance."""
        balance = PaperBalance(currency="USDT", free=Decimal("100"))
        with pytest.raises(InsufficientPaperBalanceError) as exc_info:
            balance.lock(Decimal("500"))
        assert exc_info.value.required == Decimal("500")
        assert exc_info.value.available == Decimal("100")
        assert exc_info.value.currency == "USDT"

    def test_lock_zero_amount(self) -> None:
        """Test lock with zero amount."""
        balance = PaperBalance(currency="USDT", free=Decimal("1000"))
        with pytest.raises(PaperTradingError, match="must be positive"):
            balance.lock(Decimal("0"))

    def test_lock_negative_amount(self) -> None:
        """Test lock with negative amount."""
        balance = PaperBalance(currency="USDT", free=Decimal("1000"))
        with pytest.raises(PaperTradingError, match="must be positive"):
            balance.lock(Decimal("-100"))

    def test_unlock_success(self) -> None:
        """Test successful unlock operation."""
        balance = PaperBalance(
            currency="USDT",
            free=Decimal("600"),
            locked=Decimal("400"),
        )
        balance.unlock(Decimal("200"))
        assert balance.free == Decimal("800")
        assert balance.locked == Decimal("200")
        assert balance.total == Decimal("1000")

    def test_unlock_exceeds_locked(self) -> None:
        """Test unlock with amount exceeding locked."""
        balance = PaperBalance(
            currency="USDT",
            free=Decimal("600"),
            locked=Decimal("400"),
        )
        with pytest.raises(PaperTradingError, match="Cannot unlock"):
            balance.unlock(Decimal("500"))

    def test_unlock_zero_amount(self) -> None:
        """Test unlock with zero amount."""
        balance = PaperBalance(currency="USDT", locked=Decimal("100"))
        with pytest.raises(PaperTradingError, match="must be positive"):
            balance.unlock(Decimal("0"))

    def test_add_success(self) -> None:
        """Test successful add operation."""
        balance = PaperBalance(currency="USDT", free=Decimal("1000"))
        balance.add(Decimal("500"))
        assert balance.free == Decimal("1500")
        assert balance.total == Decimal("1500")

    def test_add_zero_amount(self) -> None:
        """Test add with zero amount."""
        balance = PaperBalance(currency="USDT", free=Decimal("1000"))
        with pytest.raises(PaperTradingError, match="must be positive"):
            balance.add(Decimal("0"))

    def test_deduct_success(self) -> None:
        """Test successful deduct operation."""
        balance = PaperBalance(currency="USDT", free=Decimal("1000"))
        balance.deduct(Decimal("300"))
        assert balance.free == Decimal("700")
        assert balance.total == Decimal("700")

    def test_deduct_insufficient_balance(self) -> None:
        """Test deduct with insufficient balance."""
        balance = PaperBalance(currency="USDT", free=Decimal("100"))
        with pytest.raises(InsufficientPaperBalanceError) as exc_info:
            balance.deduct(Decimal("500"))
        assert exc_info.value.required == Decimal("500")
        assert exc_info.value.available == Decimal("100")

    def test_deduct_zero_amount(self) -> None:
        """Test deduct with zero amount."""
        balance = PaperBalance(currency="USDT", free=Decimal("1000"))
        with pytest.raises(PaperTradingError, match="must be positive"):
            balance.deduct(Decimal("0"))


# =============================================================================
# OpenPosition Tests
# =============================================================================


class TestOpenPosition:
    """Tests for OpenPosition class."""

    def test_init(self) -> None:
        """Test OpenPosition initialization."""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
        )
        open_pos = OpenPosition(
            trade_id="test-123",
            position=position,
            margin=Decimal("500"),
            quote_currency="USDT",
        )
        assert open_pos.trade_id == "test-123"
        assert open_pos.position == position
        assert open_pos.margin == Decimal("500")
        assert open_pos.quote_currency == "USDT"


# =============================================================================
# PaperTrader Initialization Tests
# =============================================================================


class TestPaperTraderInit:
    """Tests for PaperTrader initialization."""

    def test_init_no_balance(self, tmp_path: Path) -> None:
        """Test initialization with no initial balance."""
        trader = PaperTrader(data_dir=tmp_path)
        assert trader.get_all_balances() == {}

    def test_init_with_balance(self, tmp_path: Path) -> None:
        """Test initialization with initial balance."""
        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )
        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.free == Decimal("10000")
        assert balance.locked == Decimal("0")

    def test_init_multiple_currencies(self, tmp_path: Path) -> None:
        """Test initialization with multiple currencies."""
        trader = PaperTrader(
            initial_balance={
                "USDT": Decimal("10000"),
                "BTC": Decimal("1"),
            },
            data_dir=tmp_path,
        )
        assert trader.get_balance("USDT") is not None
        assert trader.get_balance("BTC") is not None
        assert trader.get_balance("ETH") is None


# =============================================================================
# PaperTrader Balance Management Tests
# =============================================================================


class TestPaperTraderBalance:
    """Tests for PaperTrader balance management."""

    @pytest.fixture
    def trader(self, tmp_path: Path) -> PaperTrader:
        """Create a PaperTrader with initial balance."""
        return PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

    def test_get_balance(self, trader: PaperTrader) -> None:
        """Test getting balance."""
        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.free == Decimal("10000")

    def test_get_balance_not_found(self, trader: PaperTrader) -> None:
        """Test getting balance for non-existent currency."""
        assert trader.get_balance("ETH") is None

    def test_set_balance_existing(self, trader: PaperTrader) -> None:
        """Test setting balance for existing currency."""
        trader.set_balance("USDT", Decimal("5000"))
        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.free == Decimal("5000")

    def test_set_balance_new_currency(self, trader: PaperTrader) -> None:
        """Test setting balance for new currency."""
        trader.set_balance("ETH", Decimal("10"))
        balance = trader.get_balance("ETH")
        assert balance is not None
        assert balance.free == Decimal("10")

    def test_get_balance_summary(self, trader: PaperTrader) -> None:
        """Test getting balance summary."""
        summary = trader.get_balance_summary()
        assert "USDT" in summary
        assert summary["USDT"]["free"] == "10000"
        assert summary["USDT"]["locked"] == "0"
        assert summary["USDT"]["total"] == "10000"


# =============================================================================
# PaperTrader Position Opening Tests
# =============================================================================


class TestPaperTraderOpenPosition:
    """Tests for PaperTrader position opening."""

    @pytest.fixture
    def trader(self, tmp_path: Path) -> PaperTrader:
        """Create a PaperTrader with initial balance."""
        return PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

    @pytest.fixture
    def long_position(self) -> Position:
        """Create a long position."""
        return Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
        )

    @pytest.fixture
    def short_position(self) -> Position:
        """Create a short position."""
        return Position(
            symbol="BTC/USDT",
            side="short",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
            stop_loss=Decimal("51000"),
            take_profit=Decimal("48000"),
        )

    def test_open_long_position(
        self, trader: PaperTrader, long_position: Position
    ) -> None:
        """Test opening a long position."""
        trade = trader.open_position(long_position)

        assert trade is not None
        assert trade.symbol == "BTC/USDT"
        assert trade.side == "long"
        assert trade.entry_price == Decimal("50000")
        assert trade.entry_quantity == Decimal("0.1")
        assert trade.leverage == 10
        assert trade.mode == "paper"
        assert trade.status == "open"

        # Check margin was locked
        # Notional = 50000 * 0.1 = 5000
        # Margin = 5000 / 10 = 500
        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.free == Decimal("9500")
        assert balance.locked == Decimal("500")

    def test_open_short_position(
        self, trader: PaperTrader, short_position: Position
    ) -> None:
        """Test opening a short position."""
        trade = trader.open_position(short_position)

        assert trade is not None
        assert trade.side == "short"
        assert trade.status == "open"

        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.locked == Decimal("500")

    def test_open_position_insufficient_balance(
        self, trader: PaperTrader
    ) -> None:
        """Test opening position with insufficient balance."""
        large_position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("10"),  # 10 BTC = $500,000 notional
            leverage=10,  # $50,000 margin required
        )
        with pytest.raises(InsufficientPaperBalanceError):
            trader.open_position(large_position)

    def test_open_position_no_balance_currency(self, tmp_path: Path) -> None:
        """Test opening position without quote currency balance."""
        trader = PaperTrader(
            initial_balance={"BTC": Decimal("1")},
            data_dir=tmp_path,
        )
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
        )
        with pytest.raises(PaperTradingError, match="No USDT balance"):
            trader.open_position(position)

    def test_open_multiple_positions(
        self, trader: PaperTrader, long_position: Position
    ) -> None:
        """Test opening multiple positions."""
        trade1 = trader.open_position(long_position)
        trade2 = trader.open_position(long_position)

        assert trade1.id != trade2.id

        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.locked == Decimal("1000")  # 500 * 2


# =============================================================================
# PaperTrader Position Closing Tests
# =============================================================================


class TestPaperTraderClosePosition:
    """Tests for PaperTrader position closing."""

    @pytest.fixture
    def trader(self, tmp_path: Path) -> PaperTrader:
        """Create a PaperTrader with initial balance."""
        return PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

    @pytest.fixture
    def long_position(self) -> Position:
        """Create a long position."""
        return Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
        )

    def test_close_position_with_profit(
        self, trader: PaperTrader, long_position: Position
    ) -> None:
        """Test closing position with profit."""
        trade = trader.open_position(long_position)

        # Close at higher price (profit)
        closed = trader.close_position(
            trade.id, Decimal("51000"), "take_profit"
        )

        assert closed is not None
        assert closed.status == "closed"
        assert closed.close_reason == "take_profit"
        assert closed.exit_price == Decimal("51000")

        # TradeHistory P&L includes leverage: 0.1 * 1000 * 10 = 1000
        assert closed.pnl == Decimal("1000")

        # Balance uses unleveraged P&L: 9500 + 500 + 100 = 10100
        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.free == Decimal("10100")
        assert balance.locked == Decimal("0")

    def test_close_position_with_loss(
        self, trader: PaperTrader, long_position: Position
    ) -> None:
        """Test closing position with loss."""
        trade = trader.open_position(long_position)

        # Close at lower price (loss)
        closed = trader.close_position(
            trade.id, Decimal("49500"), "stop_loss"
        )

        assert closed is not None
        assert closed.status == "closed"
        assert closed.close_reason == "stop_loss"

        # TradeHistory P&L includes leverage: 0.1 * (-500) * 10 = -500
        assert closed.pnl == Decimal("-500")

        # Balance uses unleveraged P&L: 9500 + 500 - 50 = 9950
        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.free == Decimal("9950")
        assert balance.locked == Decimal("0")

    def test_close_position_manual(
        self, trader: PaperTrader, long_position: Position
    ) -> None:
        """Test closing position manually."""
        trade = trader.open_position(long_position)
        closed = trader.close_position(trade.id, Decimal("50500"), "manual")

        assert closed is not None
        assert closed.close_reason == "manual"

    def test_close_position_not_found(self, trader: PaperTrader) -> None:
        """Test closing non-existent position."""
        closed = trader.close_position("non-existent", Decimal("50000"))
        assert closed is None

    def test_close_short_position_with_profit(
        self, trader: PaperTrader
    ) -> None:
        """Test closing short position with profit."""
        short_position = Position(
            symbol="BTC/USDT",
            side="short",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
            stop_loss=Decimal("51000"),
            take_profit=Decimal("48000"),
        )
        trade = trader.open_position(short_position)

        # Close at lower price (profit for short)
        closed = trader.close_position(
            trade.id, Decimal("49000"), "take_profit"
        )

        # TradeHistory P&L includes leverage: 0.1 * 1000 * 10 = 1000
        assert closed is not None
        assert closed.pnl == Decimal("1000")


# =============================================================================
# PaperTrader Exit Condition Tests
# =============================================================================


class TestPaperTraderExitConditions:
    """Tests for PaperTrader exit condition checking."""

    @pytest.fixture
    def trader(self, tmp_path: Path) -> PaperTrader:
        """Create a PaperTrader with initial balance."""
        return PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

    def test_long_stop_loss_triggered(self, trader: PaperTrader) -> None:
        """Test long position stop loss trigger."""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
        )
        trade = trader.open_position(position)

        # Price at stop loss
        should_exit, reason = trader.check_exit_conditions(
            trade.id, Decimal("49000")
        )
        assert should_exit is True
        assert reason == "stop_loss"

        # Price below stop loss
        should_exit, reason = trader.check_exit_conditions(
            trade.id, Decimal("48000")
        )
        assert should_exit is True
        assert reason == "stop_loss"

    def test_long_take_profit_triggered(self, trader: PaperTrader) -> None:
        """Test long position take profit trigger."""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
        )
        trade = trader.open_position(position)

        # Price at take profit
        should_exit, reason = trader.check_exit_conditions(
            trade.id, Decimal("52000")
        )
        assert should_exit is True
        assert reason == "take_profit"

        # Price above take profit
        should_exit, reason = trader.check_exit_conditions(
            trade.id, Decimal("53000")
        )
        assert should_exit is True
        assert reason == "take_profit"

    def test_long_no_exit(self, trader: PaperTrader) -> None:
        """Test long position no exit trigger."""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
        )
        trade = trader.open_position(position)

        # Price in between
        should_exit, reason = trader.check_exit_conditions(
            trade.id, Decimal("50500")
        )
        assert should_exit is False
        assert reason is None

    def test_short_stop_loss_triggered(self, trader: PaperTrader) -> None:
        """Test short position stop loss trigger."""
        position = Position(
            symbol="BTC/USDT",
            side="short",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
            stop_loss=Decimal("51000"),
            take_profit=Decimal("48000"),
        )
        trade = trader.open_position(position)

        # Price at stop loss
        should_exit, reason = trader.check_exit_conditions(
            trade.id, Decimal("51000")
        )
        assert should_exit is True
        assert reason == "stop_loss"

    def test_short_take_profit_triggered(self, trader: PaperTrader) -> None:
        """Test short position take profit trigger."""
        position = Position(
            symbol="BTC/USDT",
            side="short",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
            stop_loss=Decimal("51000"),
            take_profit=Decimal("48000"),
        )
        trade = trader.open_position(position)

        # Price at take profit
        should_exit, reason = trader.check_exit_conditions(
            trade.id, Decimal("48000")
        )
        assert should_exit is True
        assert reason == "take_profit"

    def test_check_exit_position_not_found(self, trader: PaperTrader) -> None:
        """Test checking exit for non-existent position."""
        should_exit, reason = trader.check_exit_conditions(
            "non-existent", Decimal("50000")
        )
        assert should_exit is False
        assert reason is None

    def test_position_without_sl_tp(self, trader: PaperTrader) -> None:
        """Test position without SL/TP."""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
        )
        trade = trader.open_position(position)

        # No SL/TP means no automatic exit
        should_exit, reason = trader.check_exit_conditions(
            trade.id, Decimal("40000")
        )
        assert should_exit is False
        assert reason is None


# =============================================================================
# PaperTrader Trade Query Tests
# =============================================================================


class TestPaperTraderQueries:
    """Tests for PaperTrader trade queries."""

    @pytest.fixture
    def trader(self, tmp_path: Path) -> PaperTrader:
        """Create a PaperTrader with initial balance."""
        return PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

    @pytest.fixture
    def position(self) -> Position:
        """Create a position."""
        return Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
        )

    def test_get_open_trades(
        self, trader: PaperTrader, position: Position
    ) -> None:
        """Test getting open trades."""
        trade1 = trader.open_position(position)
        trade2 = trader.open_position(position)

        open_trades = trader.get_open_trades()
        assert len(open_trades) == 2
        trade_ids = [t.id for t in open_trades]
        assert trade1.id in trade_ids
        assert trade2.id in trade_ids

    def test_get_trade(self, trader: PaperTrader, position: Position) -> None:
        """Test getting a specific trade."""
        trade = trader.open_position(position)
        retrieved = trader.get_trade(trade.id)
        assert retrieved is not None
        assert retrieved.id == trade.id

    def test_get_trade_not_found(self, trader: PaperTrader) -> None:
        """Test getting non-existent trade."""
        assert trader.get_trade("non-existent") is None

    def test_get_open_position(
        self, trader: PaperTrader, position: Position
    ) -> None:
        """Test getting open position details."""
        trade = trader.open_position(position)
        open_pos = trader.get_open_position(trade.id)
        assert open_pos is not None
        assert open_pos.trade_id == trade.id
        assert open_pos.margin == Decimal("500")

    def test_get_open_position_after_close(
        self, trader: PaperTrader, position: Position
    ) -> None:
        """Test getting open position after closing."""
        trade = trader.open_position(position)
        trader.close_position(trade.id, Decimal("51000"))
        assert trader.get_open_position(trade.id) is None


# =============================================================================
# PaperTrader P&L Tests
# =============================================================================


class TestPaperTraderPnL:
    """Tests for PaperTrader P&L calculations."""

    @pytest.fixture
    def trader(self, tmp_path: Path) -> PaperTrader:
        """Create a PaperTrader with initial balance."""
        return PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

    def test_update_unrealized_pnl(self, trader: PaperTrader) -> None:
        """Test updating unrealized P&L."""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
        )
        trade = trader.open_position(position)

        pnl_by_trade = trader.update_unrealized_pnl({
            "BTC/USDT": Decimal("51000")
        })

        # P&L = 0.1 * (51000 - 50000) = 100
        assert trade.id in pnl_by_trade
        assert pnl_by_trade[trade.id] == Decimal("100")

    def test_get_total_unrealized_pnl(self, trader: PaperTrader) -> None:
        """Test getting total unrealized P&L."""
        position1 = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
        )
        position2 = Position(
            symbol="ETH/USDT",
            side="long",
            entry_price=Decimal("3000"),
            quantity=Decimal("1"),
            leverage=5,
        )
        trader.set_balance("USDT", Decimal("20000"))
        trader.open_position(position1)
        trader.open_position(position2)

        total_pnl = trader.get_total_unrealized_pnl({
            "BTC/USDT": Decimal("51000"),  # +100
            "ETH/USDT": Decimal("3100"),   # +100
        })

        assert total_pnl == Decimal("200")

    def test_get_total_equity(self, trader: PaperTrader) -> None:
        """Test getting total equity."""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
        )
        trader.open_position(position)

        # Initial: 10000, Margin: 500, Unrealized: 100
        equity = trader.get_total_equity(
            "USDT",
            {"BTC/USDT": Decimal("51000")}
        )

        # Total = 9500 (free) + 500 (locked) + 100 (unrealized) = 10100
        assert equity == Decimal("10100")

    def test_get_total_equity_no_balance(self, trader: PaperTrader) -> None:
        """Test getting total equity for non-existent currency."""
        equity = trader.get_total_equity("ETH")
        assert equity == Decimal("0")


# =============================================================================
# PaperTrader Integration Tests
# =============================================================================


class TestPaperTraderIntegration:
    """Integration tests for PaperTrader."""

    def test_full_trade_lifecycle(self, tmp_path: Path) -> None:
        """Test complete trade lifecycle."""
        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

        # Create and open position
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
        )
        trade = trader.open_position(position)
        assert trade.status == "open"

        # Check balance
        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.free == Decimal("9500")
        assert balance.locked == Decimal("500")

        # Simulate price movement, check exit
        should_exit, reason = trader.check_exit_conditions(
            trade.id, Decimal("50500")
        )
        assert should_exit is False

        # Price hits take profit
        should_exit, reason = trader.check_exit_conditions(
            trade.id, Decimal("52000")
        )
        assert should_exit is True
        assert reason == "take_profit"

        # Close position
        closed = trader.close_position(trade.id, Decimal("52000"), reason)
        assert closed is not None
        assert closed.status == "closed"
        # TradeHistory P&L includes leverage: 0.1 * 2000 * 10 = 2000
        assert closed.pnl == Decimal("2000")

        # Check final balance (uses unleveraged P&L: 0.1 * 2000 = 200)
        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.free == Decimal("10200")
        assert balance.locked == Decimal("0")

    def test_multiple_positions_and_closes(self, tmp_path: Path) -> None:
        """Test multiple positions with different outcomes."""
        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

        # Position 1: Long, will profit
        pos1 = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.05"),
            leverage=10,
        )
        trade1 = trader.open_position(pos1)

        # Position 2: Short, will profit
        pos2 = Position(
            symbol="ETH/USDT",
            side="short",
            entry_price=Decimal("3000"),
            quantity=Decimal("0.5"),
            leverage=5,
        )
        trade2 = trader.open_position(pos2)

        # Check both positions open
        assert len(trader.get_open_trades()) == 2

        # Close position 1 with profit
        trader.close_position(trade1.id, Decimal("52000"))
        # P&L = 0.05 * 2000 = 100

        # Close position 2 with profit (short)
        trader.close_position(trade2.id, Decimal("2800"))
        # P&L = 0.5 * 200 = 100

        # All closed
        assert len(trader.get_open_trades()) == 0

        # Final balance: 10000 + 100 + 100 = 10200
        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.free == Decimal("10200")

    def test_trade_history_persistence(self, tmp_path: Path) -> None:
        """Test that trade history is persisted."""
        # Create trader and open/close position
        trader1 = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
        )
        trade = trader1.open_position(position)
        trade_id = trade.id
        trader1.close_position(trade_id, Decimal("51000"))

        # Create new trader with same data dir
        trader2 = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

        # Trade should be retrievable
        retrieved = trader2.get_trade(trade_id)
        assert retrieved is not None
        assert retrieved.status == "closed"
        # TradeHistory P&L includes leverage: 0.1 * 1000 * 10 = 1000
        assert retrieved.pnl == Decimal("1000")


# =============================================================================
# PaperTrader Quote Currency Extraction Tests
# =============================================================================


class TestQuoteCurrencyExtraction:
    """Tests for quote currency extraction from symbols."""

    def test_extract_usdt(self, tmp_path: Path) -> None:
        """Test extracting USDT from symbol."""
        trader = PaperTrader(data_dir=tmp_path)
        assert trader._get_quote_currency("BTC/USDT") == "USDT"

    def test_extract_usd(self, tmp_path: Path) -> None:
        """Test extracting USD from symbol."""
        trader = PaperTrader(data_dir=tmp_path)
        assert trader._get_quote_currency("BTCUSD") == "USD"

    def test_extract_btc(self, tmp_path: Path) -> None:
        """Test extracting BTC from symbol."""
        trader = PaperTrader(data_dir=tmp_path)
        assert trader._get_quote_currency("ETHBTC") == "BTC"

    def test_extract_with_slash(self, tmp_path: Path) -> None:
        """Test extracting currency with slash separator."""
        trader = PaperTrader(data_dir=tmp_path)
        assert trader._get_quote_currency("ETH/BTC") == "BTC"

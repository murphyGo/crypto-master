"""Tests for PaperTrader testnet integration.

Tests the exchange testnet integration features of PaperTrader,
including balance sync, order execution, and position management
via exchange APIs.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exchange.base import BaseExchange, ExchangeAPIError
from src.models import Balance, Order, OrderRequest, OrderStatus, Position
from src.trading.paper import (
    InsufficientPaperBalanceError,
    PaperBalance,
    PaperTrader,
    PaperTradingError,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_exchange_testnet() -> MagicMock:
    """Create a mock exchange in testnet mode."""
    exchange = MagicMock(spec=BaseExchange)
    exchange.testnet = True
    exchange.name = "mock_exchange"
    exchange.get_balance = AsyncMock()
    exchange.create_order = AsyncMock()
    return exchange


@pytest.fixture
def mock_exchange_mainnet() -> MagicMock:
    """Create a mock exchange in mainnet mode."""
    exchange = MagicMock(spec=BaseExchange)
    exchange.testnet = False
    exchange.name = "mock_exchange"
    return exchange


@pytest.fixture
def sample_position() -> Position:
    """Create a sample position for testing."""
    return Position(
        symbol="BTC/USDT",
        side="long",
        entry_price=Decimal("50000"),
        quantity=Decimal("0.1"),
        stop_loss=Decimal("48000"),
        take_profit=Decimal("55000"),
        leverage=10,
    )


@pytest.fixture
def sample_order() -> Order:
    """Create a sample order response."""
    return Order(
        id="testnet-order-123",
        symbol="BTC/USDT",
        side="buy",
        type="market",
        quantity=Decimal("0.1"),
        filled_quantity=Decimal("0.1"),
        status=OrderStatus.FILLED,
        created_at=datetime.now(),
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestPaperTraderTestnetInit:
    """Tests for testnet mode initialization."""

    def test_testnet_mode_with_exchange(
        self, mock_exchange_testnet: MagicMock, tmp_path
    ) -> None:
        """Test is_testnet_mode True when exchange in testnet."""
        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )
        assert trader.is_testnet_mode is True
        assert trader.exchange is mock_exchange_testnet

    def test_local_mode_without_exchange(self, tmp_path) -> None:
        """Test is_testnet_mode False when no exchange."""
        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )
        assert trader.is_testnet_mode is False
        assert trader.exchange is None

    def test_local_mode_with_mainnet_exchange(
        self, mock_exchange_mainnet: MagicMock, tmp_path
    ) -> None:
        """Test is_testnet_mode False when exchange not in testnet."""
        trader = PaperTrader(
            exchange=mock_exchange_mainnet,
            data_dir=tmp_path,
        )
        assert trader.is_testnet_mode is False
        assert trader.exchange is mock_exchange_mainnet

    def test_testnet_mode_with_initial_balance(
        self, mock_exchange_testnet: MagicMock, tmp_path
    ) -> None:
        """Test initial balance is set even in testnet mode."""
        trader = PaperTrader(
            initial_balance={"USDT": Decimal("5000")},
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )
        assert trader.is_testnet_mode is True
        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.free == Decimal("5000")


# =============================================================================
# Balance Sync Tests
# =============================================================================


class TestSyncBalanceFromExchange:
    """Tests for balance synchronization."""

    @pytest.mark.asyncio
    async def test_sync_updates_internal_balance(
        self, mock_exchange_testnet: MagicMock, tmp_path
    ) -> None:
        """Test balance sync updates PaperBalance."""
        mock_exchange_testnet.get_balance.return_value = [
            Balance(currency="USDT", free=Decimal("1000"), locked=Decimal("200")),
            Balance(currency="BTC", free=Decimal("0.5"), locked=Decimal("0")),
        ]

        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        await trader.sync_balance_from_exchange()

        usdt = trader.get_balance("USDT")
        assert usdt is not None
        assert usdt.free == Decimal("1000")
        assert usdt.locked == Decimal("200")
        assert usdt.total == Decimal("1200")

        btc = trader.get_balance("BTC")
        assert btc is not None
        assert btc.free == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_sync_with_currency_filter(
        self, mock_exchange_testnet: MagicMock, tmp_path
    ) -> None:
        """Test balance sync with currency filter."""
        mock_exchange_testnet.get_balance.return_value = [
            Balance(currency="USDT", free=Decimal("500"), locked=Decimal("0")),
        ]

        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        await trader.sync_balance_from_exchange("USDT")

        mock_exchange_testnet.get_balance.assert_called_once_with("USDT")
        usdt = trader.get_balance("USDT")
        assert usdt is not None
        assert usdt.free == Decimal("500")

    @pytest.mark.asyncio
    async def test_sync_requires_testnet_mode(self, tmp_path) -> None:
        """Test sync raises error without testnet."""
        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

        with pytest.raises(PaperTradingError) as exc_info:
            await trader.sync_balance_from_exchange()

        assert "requires testnet mode" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_sync_requires_testnet_mode_with_mainnet_exchange(
        self, mock_exchange_mainnet: MagicMock, tmp_path
    ) -> None:
        """Test sync raises error with mainnet exchange."""
        trader = PaperTrader(
            exchange=mock_exchange_mainnet,
            data_dir=tmp_path,
        )

        with pytest.raises(PaperTradingError) as exc_info:
            await trader.sync_balance_from_exchange()

        assert "requires testnet mode" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_sync_handles_exchange_error(
        self, mock_exchange_testnet: MagicMock, tmp_path
    ) -> None:
        """Test graceful handling of exchange API errors."""
        mock_exchange_testnet.get_balance.side_effect = ExchangeAPIError(
            "Network error"
        )

        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        with pytest.raises(PaperTradingError) as exc_info:
            await trader.sync_balance_from_exchange()

        assert "Failed to sync balance" in str(exc_info.value)


# =============================================================================
# Open Position on Testnet Tests
# =============================================================================


class TestOpenPositionOnTestnet:
    """Tests for testnet order execution."""

    @pytest.mark.asyncio
    async def test_creates_real_order_on_testnet(
        self,
        mock_exchange_testnet: MagicMock,
        sample_position: Position,
        sample_order: Order,
        tmp_path,
    ) -> None:
        """Test order is created via exchange API."""
        mock_exchange_testnet.create_order.return_value = sample_order

        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        trade = await trader.open_position_on_testnet(sample_position)

        # Verify order was created
        mock_exchange_testnet.create_order.assert_called_once()
        call_args = mock_exchange_testnet.create_order.call_args[0][0]
        assert isinstance(call_args, OrderRequest)
        assert call_args.symbol == "BTC/USDT"
        assert call_args.side == "buy"  # long -> buy
        assert call_args.type == "market"
        assert call_args.quantity == Decimal("0.1")

        # Verify trade was recorded
        assert trade is not None
        assert trade.symbol == "BTC/USDT"
        assert trade.side == "long"

    @pytest.mark.asyncio
    async def test_records_exchange_order_id(
        self,
        mock_exchange_testnet: MagicMock,
        sample_position: Position,
        sample_order: Order,
        tmp_path,
    ) -> None:
        """Test TradeHistory contains real order ID."""
        mock_exchange_testnet.create_order.return_value = sample_order

        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        trade = await trader.open_position_on_testnet(sample_position)

        # Verify real order ID is stored
        assert trade.entry_order_id == "testnet-order-123"

    @pytest.mark.asyncio
    async def test_tracks_open_position(
        self,
        mock_exchange_testnet: MagicMock,
        sample_position: Position,
        sample_order: Order,
        tmp_path,
    ) -> None:
        """Test open position is tracked internally."""
        mock_exchange_testnet.create_order.return_value = sample_order

        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        trade = await trader.open_position_on_testnet(sample_position)

        # Verify position is tracked
        open_pos = trader.get_open_position(trade.id)
        assert open_pos is not None
        assert open_pos.position.symbol == "BTC/USDT"
        assert open_pos.quote_currency == "USDT"

    @pytest.mark.asyncio
    async def test_short_position_creates_sell_order(
        self, mock_exchange_testnet: MagicMock, sample_order: Order, tmp_path
    ) -> None:
        """Test short position creates sell order."""
        short_position = Position(
            symbol="ETH/USDT",
            side="short",
            entry_price=Decimal("3000"),
            quantity=Decimal("1.0"),
            leverage=5,
        )
        sample_order.side = "sell"
        sample_order.symbol = "ETH/USDT"
        mock_exchange_testnet.create_order.return_value = sample_order

        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        await trader.open_position_on_testnet(short_position)

        call_args = mock_exchange_testnet.create_order.call_args[0][0]
        assert call_args.side == "sell"  # short -> sell

    @pytest.mark.asyncio
    async def test_requires_testnet_mode(
        self, sample_position: Position, tmp_path
    ) -> None:
        """Test requires testnet mode."""
        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

        with pytest.raises(PaperTradingError) as exc_info:
            await trader.open_position_on_testnet(sample_position)

        assert "requires testnet mode" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handles_insufficient_funds(
        self,
        mock_exchange_testnet: MagicMock,
        sample_position: Position,
        tmp_path,
    ) -> None:
        """Test proper error when testnet has no funds."""
        mock_exchange_testnet.create_order.side_effect = ExchangeAPIError(
            "Insufficient balance", code="INSUFFICIENT_FUNDS"
        )

        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        with pytest.raises(InsufficientPaperBalanceError):
            await trader.open_position_on_testnet(sample_position)

    @pytest.mark.asyncio
    async def test_handles_generic_exchange_error(
        self,
        mock_exchange_testnet: MagicMock,
        sample_position: Position,
        tmp_path,
    ) -> None:
        """Test wraps generic exchange errors."""
        mock_exchange_testnet.create_order.side_effect = ExchangeAPIError(
            "Unknown error"
        )

        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        with pytest.raises(PaperTradingError) as exc_info:
            await trader.open_position_on_testnet(sample_position)

        assert "Failed to create testnet order" in str(exc_info.value)


# =============================================================================
# Close Position on Testnet Tests
# =============================================================================


class TestClosePositionOnTestnet:
    """Tests for closing positions on testnet."""

    @pytest.mark.asyncio
    async def test_creates_closing_order(
        self,
        mock_exchange_testnet: MagicMock,
        sample_position: Position,
        sample_order: Order,
        tmp_path,
    ) -> None:
        """Test closing order is created."""
        # Setup: open position first
        mock_exchange_testnet.create_order.return_value = sample_order

        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        trade = await trader.open_position_on_testnet(sample_position)

        # Close with new order
        closing_order = Order(
            id="testnet-close-456",
            symbol="BTC/USDT",
            side="sell",
            type="market",
            quantity=Decimal("0.1"),
            filled_quantity=Decimal("0.1"),
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
        )
        mock_exchange_testnet.create_order.return_value = closing_order

        closed_trade = await trader.close_position_on_testnet(
            trade.id, exit_price=Decimal("52000"), reason="take_profit"
        )

        # Verify closing order was created
        assert mock_exchange_testnet.create_order.call_count == 2
        close_call = mock_exchange_testnet.create_order.call_args[0][0]
        assert close_call.side == "sell"  # long position closes with sell
        assert close_call.type == "market"

        # Verify trade was closed
        assert closed_trade is not None
        assert closed_trade.status == "closed"
        assert closed_trade.close_reason == "take_profit"

    @pytest.mark.asyncio
    async def test_short_position_closes_with_buy(
        self, mock_exchange_testnet: MagicMock, tmp_path
    ) -> None:
        """Test short position closes with buy order."""
        short_position = Position(
            symbol="ETH/USDT",
            side="short",
            entry_price=Decimal("3000"),
            quantity=Decimal("1.0"),
            leverage=5,
        )

        # Mock open order
        open_order = Order(
            id="testnet-open-123",
            symbol="ETH/USDT",
            side="sell",
            type="market",
            quantity=Decimal("1.0"),
            filled_quantity=Decimal("1.0"),
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
        )
        mock_exchange_testnet.create_order.return_value = open_order

        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        trade = await trader.open_position_on_testnet(short_position)

        # Mock close order
        close_order = Order(
            id="testnet-close-456",
            symbol="ETH/USDT",
            side="buy",
            type="market",
            quantity=Decimal("1.0"),
            filled_quantity=Decimal("1.0"),
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
        )
        mock_exchange_testnet.create_order.return_value = close_order

        await trader.close_position_on_testnet(
            trade.id, exit_price=Decimal("2800"), reason="take_profit"
        )

        close_call = mock_exchange_testnet.create_order.call_args[0][0]
        assert close_call.side == "buy"  # short closes with buy

    @pytest.mark.asyncio
    async def test_updates_trade_history(
        self,
        mock_exchange_testnet: MagicMock,
        sample_position: Position,
        sample_order: Order,
        tmp_path,
    ) -> None:
        """Test TradeHistory is properly updated."""
        mock_exchange_testnet.create_order.return_value = sample_order

        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        trade = await trader.open_position_on_testnet(sample_position)

        # Close
        closing_order = Order(
            id="close-789",
            symbol="BTC/USDT",
            side="sell",
            type="market",
            quantity=Decimal("0.1"),
            filled_quantity=Decimal("0.1"),
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
        )
        mock_exchange_testnet.create_order.return_value = closing_order

        closed_trade = await trader.close_position_on_testnet(
            trade.id, exit_price=Decimal("51000"), reason="manual"
        )

        assert closed_trade.exit_price == Decimal("51000")
        assert closed_trade.close_reason == "manual"

    @pytest.mark.asyncio
    async def test_removes_from_open_positions(
        self,
        mock_exchange_testnet: MagicMock,
        sample_position: Position,
        sample_order: Order,
        tmp_path,
    ) -> None:
        """Test position is removed from tracking after close."""
        mock_exchange_testnet.create_order.return_value = sample_order

        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        trade = await trader.open_position_on_testnet(sample_position)
        assert trader.get_open_position(trade.id) is not None

        # Close
        closing_order = Order(
            id="close-order",
            symbol="BTC/USDT",
            side="sell",
            type="market",
            quantity=Decimal("0.1"),
            filled_quantity=Decimal("0.1"),
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
        )
        mock_exchange_testnet.create_order.return_value = closing_order

        await trader.close_position_on_testnet(
            trade.id, exit_price=Decimal("50000"), reason="manual"
        )

        assert trader.get_open_position(trade.id) is None

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_trade(
        self, mock_exchange_testnet: MagicMock, tmp_path
    ) -> None:
        """Test returns None when trade not found."""
        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        result = await trader.close_position_on_testnet(
            "unknown-trade-id", exit_price=Decimal("50000")
        )

        assert result is None
        mock_exchange_testnet.create_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_requires_testnet_mode(self, tmp_path) -> None:
        """Test requires testnet mode."""
        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

        with pytest.raises(PaperTradingError) as exc_info:
            await trader.close_position_on_testnet(
                "some-trade", exit_price=Decimal("50000")
            )

        assert "requires testnet mode" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handles_exchange_error_on_close(
        self,
        mock_exchange_testnet: MagicMock,
        sample_position: Position,
        sample_order: Order,
        tmp_path,
    ) -> None:
        """Test wraps exchange errors during close."""
        mock_exchange_testnet.create_order.return_value = sample_order

        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        trade = await trader.open_position_on_testnet(sample_position)

        # Make close fail
        mock_exchange_testnet.create_order.side_effect = ExchangeAPIError(
            "Exchange unavailable"
        )

        with pytest.raises(PaperTradingError) as exc_info:
            await trader.close_position_on_testnet(
                trade.id, exit_price=Decimal("50000")
            )

        assert "Failed to create testnet closing order" in str(exc_info.value)


# =============================================================================
# Integration Tests
# =============================================================================


class TestTestnetIntegration:
    """Integration tests for complete testnet workflow."""

    @pytest.mark.asyncio
    async def test_full_testnet_workflow(
        self, mock_exchange_testnet: MagicMock, tmp_path
    ) -> None:
        """Test complete workflow: sync -> open -> close."""
        # Setup mocks
        mock_exchange_testnet.get_balance.return_value = [
            Balance(currency="USDT", free=Decimal("10000"), locked=Decimal("0")),
        ]

        open_order = Order(
            id="open-001",
            symbol="BTC/USDT",
            side="buy",
            type="market",
            quantity=Decimal("0.1"),
            filled_quantity=Decimal("0.1"),
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
        )

        close_order = Order(
            id="close-001",
            symbol="BTC/USDT",
            side="sell",
            type="market",
            quantity=Decimal("0.1"),
            filled_quantity=Decimal("0.1"),
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
        )

        # Create trader
        trader = PaperTrader(
            exchange=mock_exchange_testnet,
            data_dir=tmp_path,
        )

        # Step 1: Sync balance
        await trader.sync_balance_from_exchange()
        assert trader.get_balance("USDT") is not None
        assert trader.get_balance("USDT").free == Decimal("10000")

        # Step 2: Open position
        mock_exchange_testnet.create_order.return_value = open_order
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
        )
        trade = await trader.open_position_on_testnet(position)
        assert trade.entry_order_id == "open-001"
        assert len(trader.get_open_trades()) == 1

        # Step 3: Close position
        mock_exchange_testnet.create_order.return_value = close_order
        closed = await trader.close_position_on_testnet(
            trade.id, exit_price=Decimal("52000"), reason="take_profit"
        )
        assert closed.status == "closed"
        assert len(trader.get_open_trades()) == 0

    @pytest.mark.asyncio
    async def test_local_simulation_still_works(self, tmp_path) -> None:
        """Test local simulation mode is unaffected by testnet code."""
        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

        assert trader.is_testnet_mode is False

        # Local open_position should still work
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
        )

        trade = trader.open_position(position)
        assert trade is not None
        assert trade.entry_order_id.startswith("paper-")

        # Local close_position should still work
        closed = trader.close_position(trade.id, Decimal("51000"), "manual")
        assert closed is not None
        assert closed.status == "closed"

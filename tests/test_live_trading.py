"""Tests for the live trading module.

Covers LiveTrader with a mocked exchange. Verifies the user
confirmation flow (NFR-012), order execution, error paths, and
position monitoring for stop-loss / take-profit auto-exits.
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.exchange.base import BaseExchange
from src.models import Order, OrderStatus, Position, Ticker
from src.trading.live import (
    LiveConfirmationRejectedError,
    LiveModeError,
    LiveOrderRejectedError,
    LiveTrader,
    LiveTradingError,
    default_confirmation,
)

# =============================================================================
# Fixtures
# =============================================================================


def _make_order(
    status: OrderStatus = OrderStatus.FILLED,
    side: Literal["buy", "sell"] = "buy",
    filled_qty: Decimal = Decimal("0.1"),
    order_id: str = "live-order-1",
) -> Order:
    """Build an Order stub with sensible defaults."""
    return Order(
        id=order_id,
        symbol="BTC/USDT",
        side=side,
        type="market",
        quantity=Decimal("0.1"),
        filled_quantity=filled_qty,
        status=status,
        created_at=datetime.now(),
    )


@pytest.fixture
def mock_exchange() -> MagicMock:
    """Mainnet exchange with mocked async methods."""
    exchange = MagicMock(spec=BaseExchange)
    exchange.testnet = False
    exchange.name = "mock_live"
    exchange.create_order = AsyncMock(return_value=_make_order())
    exchange.get_ticker = AsyncMock()
    return exchange


@pytest.fixture
def mock_exchange_testnet() -> MagicMock:
    """Testnet exchange should be rejected by LiveTrader."""
    exchange = MagicMock(spec=BaseExchange)
    exchange.testnet = True
    exchange.name = "mock_live"
    return exchange


@pytest.fixture
def long_position() -> Position:
    """Standard long position with SL/TP."""
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
def short_position() -> Position:
    """Standard short position with SL/TP."""
    return Position(
        symbol="BTC/USDT",
        side="short",
        entry_price=Decimal("50000"),
        quantity=Decimal("0.1"),
        leverage=10,
        stop_loss=Decimal("51000"),
        take_profit=Decimal("48000"),
    )


def make_approve() -> AsyncMock:
    """Confirmation callback that always approves."""
    return AsyncMock(return_value=True)


def make_reject() -> AsyncMock:
    """Confirmation callback that always declines."""
    return AsyncMock(return_value=False)


# =============================================================================
# Initialization
# =============================================================================


class TestLiveTraderInit:
    """Tests for LiveTrader construction."""

    def test_init_rejects_testnet_exchange(
        self, mock_exchange_testnet: MagicMock, tmp_path: Path
    ) -> None:
        """LiveTrader must refuse a testnet exchange."""
        with pytest.raises(LiveModeError, match="testnet"):
            LiveTrader(
                exchange=mock_exchange_testnet,
                data_dir=tmp_path,
            )

    def test_init_default_confirmation(
        self, mock_exchange: MagicMock, tmp_path: Path
    ) -> None:
        """Default confirmation is used when none is provided."""
        trader = LiveTrader(exchange=mock_exchange, data_dir=tmp_path)
        assert trader._confirmation_callback is default_confirmation

    def test_init_accepts_custom_callback(
        self, mock_exchange: MagicMock, tmp_path: Path
    ) -> None:
        """Custom confirmation callback is stored."""
        callback = make_approve()
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=callback,
        )
        assert trader._confirmation_callback is callback

    def test_exchange_property(
        self, mock_exchange: MagicMock, tmp_path: Path
    ) -> None:
        """exchange property returns injected instance."""
        trader = LiveTrader(exchange=mock_exchange, data_dir=tmp_path)
        assert trader.exchange is mock_exchange


# =============================================================================
# open_position
# =============================================================================


class TestLiveOpenPosition:
    """Tests for LiveTrader.open_position."""

    @pytest.mark.asyncio
    async def test_open_long_position(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """Approving opens a long via a buy market order."""
        callback = make_approve()
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=callback,
        )

        trade = await trader.open_position(long_position)

        assert trade is not None
        assert trade.mode == "live"
        assert trade.side == "long"
        assert trade.status == "open"
        assert trade.entry_order_id == "live-order-1"

        callback.assert_awaited_once_with(long_position, "open")

        mock_exchange.create_order.assert_awaited_once()
        order_arg = mock_exchange.create_order.await_args.args[0]
        assert order_arg.side == "buy"
        assert order_arg.type == "market"
        assert order_arg.quantity == Decimal("0.1")

    @pytest.mark.asyncio
    async def test_open_short_position_uses_sell(
        self,
        mock_exchange: MagicMock,
        short_position: Position,
        tmp_path: Path,
    ) -> None:
        """Short opens via a sell market order."""
        mock_exchange.create_order.return_value = _make_order(side="sell")
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        await trader.open_position(short_position)

        order_arg = mock_exchange.create_order.await_args.args[0]
        assert order_arg.side == "sell"

    @pytest.mark.asyncio
    async def test_open_rejected_by_user_raises(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """Declined confirmation raises and sends no order."""
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_reject(),
        )

        with pytest.raises(LiveConfirmationRejectedError):
            await trader.open_position(long_position)

        mock_exchange.create_order.assert_not_awaited()
        assert trader.get_open_trades() == []

    @pytest.mark.asyncio
    async def test_open_exchange_error_wrapped(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """Exchange exceptions are wrapped as LiveOrderRejectedError."""
        mock_exchange.create_order.side_effect = RuntimeError("boom")
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )

        with pytest.raises(LiveOrderRejectedError, match="boom"):
            await trader.open_position(long_position)

        assert trader.get_open_trades() == []

    @pytest.mark.asyncio
    async def test_open_rejected_status_raises(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """REJECTED status from the exchange becomes an error."""
        mock_exchange.create_order.return_value = _make_order(
            status=OrderStatus.REJECTED, order_id="rej-1"
        )
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )

        with pytest.raises(LiveOrderRejectedError) as exc_info:
            await trader.open_position(long_position)

        assert exc_info.value.order_id == "rej-1"
        assert trader.get_open_trades() == []

    @pytest.mark.asyncio
    async def test_open_uses_filled_quantity(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """Entry quantity on the trade record uses the exchange fill."""
        mock_exchange.create_order.return_value = _make_order(
            filled_qty=Decimal("0.05")
        )
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        trade = await trader.open_position(long_position)
        assert trade.entry_quantity == Decimal("0.05")


# =============================================================================
# close_position
# =============================================================================


class TestLiveClosePosition:
    """Tests for LiveTrader.close_position."""

    @pytest.mark.asyncio
    async def test_close_long_uses_sell(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """Closing a long sends a sell order after confirmation."""
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        trade = await trader.open_position(long_position)

        mock_exchange.create_order.return_value = _make_order(
            side="sell", order_id="close-1"
        )

        closed = await trader.close_position(
            trade.id, exit_price=Decimal("51000"), reason="manual"
        )

        assert closed is not None
        assert closed.status == "closed"
        assert closed.close_reason == "manual"
        assert closed.exit_order_id == "close-1"
        assert closed.exit_price == Decimal("51000")

        # Second call to create_order is the closing order
        last_call = mock_exchange.create_order.await_args_list[-1]
        order_arg = last_call.args[0]
        assert order_arg.side == "sell"

        # Trade removed from in-memory tracking
        assert trader.get_tracked_position(trade.id) is None

    @pytest.mark.asyncio
    async def test_close_short_uses_buy(
        self,
        mock_exchange: MagicMock,
        short_position: Position,
        tmp_path: Path,
    ) -> None:
        """Closing a short sends a buy order."""
        mock_exchange.create_order.return_value = _make_order(side="sell")
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        trade = await trader.open_position(short_position)

        mock_exchange.create_order.return_value = _make_order(
            side="buy", order_id="close-short"
        )
        await trader.close_position(
            trade.id, exit_price=Decimal("49000"), reason="manual"
        )

        last_call = mock_exchange.create_order.await_args_list[-1]
        order_arg = last_call.args[0]
        assert order_arg.side == "buy"

    @pytest.mark.asyncio
    async def test_close_rejected_by_user_raises(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """Declining a manual close raises and leaves the position open."""
        callback = AsyncMock(side_effect=[True, False])  # open=True, close=False
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=callback,
        )
        trade = await trader.open_position(long_position)

        with pytest.raises(LiveConfirmationRejectedError):
            await trader.close_position(trade.id)

        # Position still tracked
        assert trader.get_tracked_position(trade.id) is not None
        # Trade still open in tracker
        assert trader.get_trade(trade.id).status == "open"

    @pytest.mark.asyncio
    async def test_close_unknown_trade_returns_none(
        self,
        mock_exchange: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Closing an unknown trade logs and returns None."""
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        result = await trader.close_position("unknown-id")
        assert result is None


# =============================================================================
# monitor_positions
# =============================================================================


class TestLiveMonitorPositions:
    """Tests for LiveTrader.monitor_positions."""

    @pytest.mark.asyncio
    async def test_monitor_triggers_long_stop_loss(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """Price at or below SL auto-closes a long without re-prompting."""
        callback = AsyncMock(return_value=True)
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=callback,
        )
        trade = await trader.open_position(long_position)

        # Callback was called exactly once for the open
        assert callback.await_count == 1

        mock_exchange.get_ticker.return_value = Ticker(
            symbol="BTC/USDT",
            price=Decimal("48500"),  # below stop_loss 49000
            timestamp=datetime.now(),
        )
        mock_exchange.create_order.return_value = _make_order(
            side="sell", order_id="sl-close"
        )

        closed = await trader.monitor_positions()

        assert len(closed) == 1
        assert closed[0].id == trade.id
        assert closed[0].close_reason == "stop_loss"
        assert closed[0].exit_price == Decimal("48500")
        # Auto-exit must not re-ask confirmation
        assert callback.await_count == 1

    @pytest.mark.asyncio
    async def test_monitor_triggers_long_take_profit(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """Price at/above TP auto-closes a long."""
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        await trader.open_position(long_position)

        mock_exchange.get_ticker.return_value = Ticker(
            symbol="BTC/USDT",
            price=Decimal("52500"),
            timestamp=datetime.now(),
        )
        mock_exchange.create_order.return_value = _make_order(side="sell")

        closed = await trader.monitor_positions()
        assert len(closed) == 1
        assert closed[0].close_reason == "take_profit"

    @pytest.mark.asyncio
    async def test_monitor_triggers_short_stop_loss(
        self,
        mock_exchange: MagicMock,
        short_position: Position,
        tmp_path: Path,
    ) -> None:
        """Price at/above SL auto-closes a short."""
        mock_exchange.create_order.return_value = _make_order(side="sell")
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        await trader.open_position(short_position)

        mock_exchange.get_ticker.return_value = Ticker(
            symbol="BTC/USDT",
            price=Decimal("51500"),
            timestamp=datetime.now(),
        )
        mock_exchange.create_order.return_value = _make_order(
            side="buy", order_id="sl-short"
        )

        closed = await trader.monitor_positions()
        assert len(closed) == 1
        assert closed[0].close_reason == "stop_loss"

    @pytest.mark.asyncio
    async def test_monitor_no_exit_when_price_within_range(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """Price between SL and TP leaves position open."""
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        trade = await trader.open_position(long_position)

        mock_exchange.get_ticker.return_value = Ticker(
            symbol="BTC/USDT",
            price=Decimal("50500"),
            timestamp=datetime.now(),
        )
        closed = await trader.monitor_positions()

        assert closed == []
        assert trader.get_tracked_position(trade.id) is not None

    @pytest.mark.asyncio
    async def test_monitor_skips_ticker_errors(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """Ticker fetch failure is logged and the pass continues."""
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        trade = await trader.open_position(long_position)

        mock_exchange.get_ticker.side_effect = RuntimeError("network down")
        closed = await trader.monitor_positions()

        assert closed == []
        assert trader.get_tracked_position(trade.id) is not None

    @pytest.mark.asyncio
    async def test_monitor_auto_exit_swallows_close_rejection(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """If closing order is rejected, monitor logs and keeps going."""
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        await trader.open_position(long_position)

        mock_exchange.get_ticker.return_value = Ticker(
            symbol="BTC/USDT",
            price=Decimal("48000"),
            timestamp=datetime.now(),
        )
        mock_exchange.create_order.side_effect = RuntimeError("rejected")

        closed = await trader.monitor_positions()
        assert closed == []

    @pytest.mark.asyncio
    async def test_monitor_no_positions(
        self, mock_exchange: MagicMock, tmp_path: Path
    ) -> None:
        """Monitor is a no-op with no open positions."""
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        closed = await trader.monitor_positions()
        assert closed == []
        mock_exchange.get_ticker.assert_not_awaited()


# =============================================================================
# Query methods
# =============================================================================


class TestLiveQueries:
    """Tests for query helpers on LiveTrader."""

    @pytest.mark.asyncio
    async def test_get_open_trades(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """get_open_trades returns only open live trades."""
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        trade = await trader.open_position(long_position)
        open_trades = trader.get_open_trades()
        assert len(open_trades) == 1
        assert open_trades[0].id == trade.id
        assert open_trades[0].mode == "live"

    @pytest.mark.asyncio
    async def test_get_trade_by_id(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """get_trade retrieves a record by ID."""
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        trade = await trader.open_position(long_position)
        assert trader.get_trade(trade.id).id == trade.id

    @pytest.mark.asyncio
    async def test_get_trade_not_found(
        self, mock_exchange: MagicMock, tmp_path: Path
    ) -> None:
        """get_trade returns None for an unknown ID."""
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        assert trader.get_trade("unknown") is None


# =============================================================================
# default_confirmation
# =============================================================================


class TestDefaultConfirmation:
    """Tests for the CLI default confirmation helper."""

    @pytest.mark.asyncio
    async def test_default_confirmation_yes(
        self, long_position: Position, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """'yes' response approves the trade."""
        monkeypatch.setattr("builtins.input", lambda _: "yes")
        assert await default_confirmation(long_position, "open") is True

    @pytest.mark.asyncio
    async def test_default_confirmation_y(
        self, long_position: Position, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """'y' response approves the trade."""
        monkeypatch.setattr("builtins.input", lambda _: "y")
        assert await default_confirmation(long_position, "close") is True

    @pytest.mark.asyncio
    async def test_default_confirmation_no(
        self, long_position: Position, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Any other response declines the trade."""
        monkeypatch.setattr("builtins.input", lambda _: "no")
        assert await default_confirmation(long_position, "open") is False

    @pytest.mark.asyncio
    async def test_default_confirmation_case_insensitive(
        self, long_position: Position, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Response is case-insensitive."""
        monkeypatch.setattr("builtins.input", lambda _: "  YES ")
        assert await default_confirmation(long_position, "open") is True


# =============================================================================
# Hierarchy
# =============================================================================


class TestExceptionHierarchy:
    """Confirm the exception hierarchy wires through TradingError."""

    def test_live_mode_error_is_live_trading(self) -> None:
        assert issubclass(LiveModeError, LiveTradingError)

    def test_live_confirmation_rejected_is_live_trading(self) -> None:
        assert issubclass(LiveConfirmationRejectedError, LiveTradingError)

    def test_live_order_rejected_is_live_trading(self) -> None:
        assert issubclass(LiveOrderRejectedError, LiveTradingError)

    def test_live_order_rejected_carries_metadata(self) -> None:
        err = LiveOrderRejectedError(
            "x", order_id="oid", status=OrderStatus.REJECTED
        )
        assert err.order_id == "oid"
        assert err.status == OrderStatus.REJECTED

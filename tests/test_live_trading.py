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
    average_price: Decimal | None = None,
    fee: Decimal | None = None,
    fee_currency: str | None = None,
) -> Order:
    """Build an Order stub with sensible defaults."""
    return Order(
        id=order_id,
        symbol="BTC/USDT",
        side=side,
        type="market",
        quantity=Decimal("0.1"),
        filled_quantity=filled_qty,
        average_price=average_price,
        fee=fee,
        fee_currency=fee_currency,
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

    def test_exchange_property(self, mock_exchange: MagicMock, tmp_path: Path) -> None:
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
        assert trade.stop_loss == Decimal("49000")
        assert trade.take_profit == Decimal("52000")

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
    async def test_open_rejects_partial_fill(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """Live market opens must not persist partial fills."""
        mock_exchange.create_order.return_value = _make_order(
            filled_qty=Decimal("0.05")
        )
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )

        with pytest.raises(LiveOrderRejectedError, match="partial fill"):
            await trader.open_position(long_position)

        assert trader.get_open_trades() == []

    @pytest.mark.asyncio
    async def test_open_rejects_zero_fill(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """A filled status with zero filled quantity is not a live position."""
        mock_exchange.create_order.return_value = _make_order(filled_qty=Decimal("0"))
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )

        with pytest.raises(LiveOrderRejectedError, match="zero fill"):
            await trader.open_position(long_position)

        assert trader.get_open_trades() == []

    @pytest.mark.asyncio
    async def test_open_rejects_non_filled_status(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """Open or partially-filled exchange statuses are not persisted."""
        mock_exchange.create_order.return_value = _make_order(
            status=OrderStatus.OPEN,
            filled_qty=Decimal("0"),
            order_id="open-1",
        )
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )

        with pytest.raises(LiveOrderRejectedError) as exc_info:
            await trader.open_position(long_position)

        assert exc_info.value.order_id == "open-1"
        assert exc_info.value.status == OrderStatus.OPEN
        assert trader.get_open_trades() == []

    @pytest.mark.asyncio
    async def test_open_cleans_entry_fee_stash_when_post_persist_step_fails(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A late open failure must not leave stale in-memory fee state."""
        mock_exchange.create_order.return_value = _make_order(
            average_price=Decimal("50050"),
            fee=Decimal("2.5"),
        )
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )

        def fail_open_log(message: str, *args: object, **kwargs: object) -> None:
            if message.startswith("Opened live position:"):
                raise RuntimeError("post-persist failure")

        monkeypatch.setattr("src.trading.live.logger.info", fail_open_log)

        with pytest.raises(RuntimeError, match="post-persist failure"):
            await trader.open_position(long_position)

        assert trader._entry_fees == {}
        assert trader._open_positions == {}


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
            await trader.close_position(trade.id, exit_price=Decimal("50500"))

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
        result = await trader.close_position("unknown-id", exit_price=Decimal("50000"))
        assert result is None

    @pytest.mark.asyncio
    async def test_close_rejects_partial_fill_and_keeps_position_open(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """A partial close fill must not mark the live trade closed."""
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        trade = await trader.open_position(long_position)

        mock_exchange.create_order.return_value = _make_order(
            side="sell",
            filled_qty=Decimal("0.05"),
            order_id="partial-close",
        )

        with pytest.raises(LiveOrderRejectedError, match="partial fill"):
            await trader.close_position(
                trade.id,
                exit_price=Decimal("51000"),
                reason="manual",
            )

        assert trader.get_tracked_position(trade.id) is not None
        assert trader.get_trade(trade.id).status == "open"

    @pytest.mark.asyncio
    async def test_close_records_actual_fill_price_and_fees(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """LiveTrader records the exchange's reported fill price and fees (CH-06).

        Before consistency-hardening CH-06, ``_execute_close`` used the
        caller-passed ``exit_price`` as the recorded close price and
        never threaded ``order.fee`` to the tracker, so realised P&L on
        disk diverged from what actually executed and live vs. paper
        P&L could not be compared.
        """
        # Open with an entry-side fill that reports its own average and fee.
        mock_exchange.create_order.return_value = _make_order(
            side="buy",
            average_price=Decimal("50050"),
            fee=Decimal("2.5"),
            fee_currency="USDT",
            order_id="open-attr",
        )
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        trade = await trader.open_position(long_position)
        # Entry price recorded from the exchange average, not
        # ``long_position.entry_price``.
        persisted_open = trader.get_trade(trade.id)
        assert persisted_open.entry_price == Decimal("50050")
        assert persisted_open.fees == Decimal("2.5")

        # Close fills above the operator's expected exit price; the
        # exchange's average wins and entry+exit fees aggregate.
        mock_exchange.create_order.return_value = _make_order(
            side="sell",
            average_price=Decimal("51075"),
            fee=Decimal("2.55"),
            fee_currency="USDT",
            order_id="close-attr",
        )
        closed = await trader.close_position(
            trade.id,
            exit_price=Decimal("51000"),  # operator-expected; exchange wins
            reason="manual",
        )

        assert closed is not None
        assert closed.exit_price == Decimal("51075")
        # entry_fee 2.5 + exit_fee 2.55 == 5.05
        assert closed.fees == Decimal("5.05")

    @pytest.mark.asyncio
    async def test_restart_rehydrates_open_live_position_for_monitoring(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """Persisted SL/TP lets a restarted LiveTrader keep monitoring (CH-07)."""
        first = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        trade = await first.open_position(long_position)

        restarted = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )

        rehydrated = restarted.get_open_position(trade.id)
        assert rehydrated is not None
        assert rehydrated.symbol == long_position.symbol
        assert rehydrated.side == long_position.side
        assert rehydrated.entry_price == long_position.entry_price
        assert rehydrated.quantity == long_position.quantity
        assert rehydrated.stop_loss == long_position.stop_loss
        assert rehydrated.take_profit == long_position.take_profit

        mock_exchange.get_ticker.return_value = Ticker(
            symbol="BTC/USDT",
            price=Decimal("48500"),
            timestamp=datetime.now(),
        )
        mock_exchange.create_order.return_value = _make_order(
            side="sell", order_id="restart-sl"
        )

        closed = await restarted.monitor_positions()
        assert len(closed) == 1
        assert closed[0].id == trade.id
        assert closed[0].close_reason == "stop_loss"

    @pytest.mark.asyncio
    async def test_restart_keeps_legacy_open_trade_orphaned_without_bounds(
        self,
        mock_exchange: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Legacy open live trades without SL/TP are visible but not monitorable."""
        from src.strategy.performance import TradeHistoryTracker

        tracker = TradeHistoryTracker(data_dir=tmp_path)
        trade = tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="live",
            leverage=10,
        )

        restarted = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )

        assert restarted.get_open_trades()[0].id == trade.id
        assert restarted.get_open_position(trade.id) is None
        assert restarted.check_exit_conditions(trade.id, Decimal("48000")) == (
            False,
            None,
        )

    @pytest.mark.asyncio
    async def test_live_rehydrate_parity_backfill(
        self,
        mock_exchange: MagicMock,
        tmp_path: Path,
    ) -> None:
        """DEBT-071 parity: a legacy open live trade missing SL/TP but linked to
        a resolvable ``performance_record_id`` is backfilled and rehydrated
        into ``_open_positions`` exactly like the paper path.
        """
        from src.strategy.performance import (
            PerformanceRecord,
            PerformanceTracker,
            TradeHistoryTracker,
        )

        perf_tracker = PerformanceTracker(
            data_dir=tmp_path / "performance",
            sub_account_id="default",
        )
        record = PerformanceRecord(
            technique_name="tech_a",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.8,
            mode="live",
            sub_account_id="default",
        )
        perf_tracker.save_record(record)

        tracker = TradeHistoryTracker(data_dir=tmp_path / "trades")
        legacy = tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="live",
            leverage=10,
            performance_record_id=record.id,
        )
        assert legacy.stop_loss is None and legacy.take_profit is None

        restarted = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path / "trades",
            confirmation_callback=make_approve(),
        )

        rehydrated = restarted.get_open_position(legacy.id)
        assert rehydrated is not None
        assert rehydrated.stop_loss == Decimal("49000")
        assert rehydrated.take_profit == Decimal("52000")

    @pytest.mark.asyncio
    async def test_close_falls_back_to_caller_price_when_exchange_omits_average(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        """When the adapter doesn't surface ``average_price``, fall back gracefully."""
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        trade = await trader.open_position(long_position)

        # Adapter that never surfaces average / fee (legacy behaviour).
        mock_exchange.create_order.return_value = _make_order(
            side="sell", order_id="close-legacy"
        )
        closed = await trader.close_position(
            trade.id, exit_price=Decimal("51000"), reason="manual"
        )
        assert closed is not None
        assert closed.exit_price == Decimal("51000")
        assert closed.fees == Decimal("0")


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
    async def test_check_exit_conditions_uses_shared_boundary_semantics(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        short_position: Position,
        tmp_path: Path,
    ) -> None:
        """Live exit checks use inclusive SL/TP bounds and stop-loss priority."""
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )

        long_trade = await trader.open_position(long_position)
        assert trader.check_exit_conditions(long_trade.id, Decimal("49000")) == (
            True,
            "stop_loss",
        )
        assert trader.check_exit_conditions(long_trade.id, Decimal("52000")) == (
            True,
            "take_profit",
        )

        mock_exchange.create_order.return_value = _make_order(side="sell")
        short_trade = await trader.open_position(short_position)
        assert trader.check_exit_conditions(short_trade.id, Decimal("51000")) == (
            True,
            "stop_loss",
        )
        assert trader.check_exit_conditions(short_trade.id, Decimal("48000")) == (
            True,
            "take_profit",
        )

        priority_position = long_position.model_copy(
            update={
                "symbol": "ETH/USDT",
                "stop_loss": Decimal("50000"),
                "take_profit": Decimal("50000"),
            }
        )
        priority_trade = await trader.open_position(priority_position)
        assert trader.check_exit_conditions(priority_trade.id, Decimal("50000")) == (
            True,
            "stop_loss",
        )

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
        err = LiveOrderRejectedError("x", order_id="oid", status=OrderStatus.REJECTED)
        assert err.order_id == "oid"
        assert err.status == OrderStatus.REJECTED


# =============================================================================
# force_close_orphan (DEBT-058 follow-up)
# =============================================================================


class TestForceCloseOrphanLive:
    """Persistence-only orphan force-close on LiveTrader.

    DEBT-058 follow-up watchdog hook. The live implementation must
    update the persisted ledger without placing an exchange order
    (the orphan branch by definition has no in-memory position the
    engine can use to construct one) and must log a WARNING that
    operator reconciliation may still be needed.
    """

    @pytest.mark.asyncio
    async def test_force_close_orphan_persists_closed_live_trade(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        trade = await trader.open_position(long_position)

        # Drop the in-memory state to simulate the orphan scenario.
        trader._open_positions.pop(trade.id, None)
        trader._entry_fees.pop(trade.id, None)

        # Reset create_order so the test can assert it was NOT called
        # by the watchdog path.
        mock_exchange.create_order.reset_mock()

        closed = await trader.force_close_orphan(trade.id, Decimal("48500"))

        assert closed is not None
        assert closed.status == "closed"
        assert closed.close_reason == "orphan_force_close"
        assert closed.exit_price == Decimal("48500")

        # Crucially: the watchdog must NOT submit any exchange order.
        mock_exchange.create_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_close_orphan_logs_warning_about_exchange_state(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A WARNING must be emitted naming the exchange-side reconciliation gap."""
        import logging

        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        trade = await trader.open_position(long_position)
        trader._open_positions.pop(trade.id, None)
        trader._entry_fees.pop(trade.id, None)

        # ``get_logger`` disables propagation; attach the caplog handler
        # to the named logger so the assertion can see the WARNING.
        target_logger = logging.getLogger("crypto_master.trading.live")
        target_logger.addHandler(caplog.handler)
        target_logger.setLevel(logging.WARNING)
        try:
            await trader.force_close_orphan(trade.id, Decimal("48500"))
        finally:
            target_logger.removeHandler(caplog.handler)

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "exchange-side position may still be open" in r.getMessage()
            for r in warnings
        ), [r.getMessage() for r in warnings]

    @pytest.mark.asyncio
    async def test_force_close_orphan_idempotent_on_already_closed(
        self,
        mock_exchange: MagicMock,
        long_position: Position,
        tmp_path: Path,
    ) -> None:
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        trade = await trader.open_position(long_position)
        trader._open_positions.pop(trade.id, None)
        trader._entry_fees.pop(trade.id, None)

        first = await trader.force_close_orphan(trade.id, Decimal("48500"))
        assert first is not None

        second = await trader.force_close_orphan(trade.id, Decimal("48400"))
        assert second is None

    @pytest.mark.asyncio
    async def test_force_close_orphan_returns_none_for_unknown_trade(
        self,
        mock_exchange: MagicMock,
        tmp_path: Path,
    ) -> None:
        trader = LiveTrader(
            exchange=mock_exchange,
            data_dir=tmp_path,
            confirmation_callback=make_approve(),
        )
        result = await trader.force_close_orphan("does-not-exist", Decimal("50000"))
        assert result is None

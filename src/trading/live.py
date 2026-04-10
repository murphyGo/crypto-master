"""Live trading engine.

Executes real orders against an exchange mainnet account. Every trade
(open or manual close) flows through an explicit user confirmation
callback before an order is sent, per NFR-012.

Related Requirements:
- FR-009: Live Trading Mode
- FR-010: Paper/Live Mode Switching
- NFR-007: Trading History Storage
- NFR-008: Asset/PnL History (mode separation)
- NFR-012: Live Trading Confirmation
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from src.logger import get_logger
from src.models import OrderRequest, OrderStatus, Position
from src.strategy.performance import TradeHistory, TradeHistoryTracker
from src.trading.strategy import TradingError

if TYPE_CHECKING:
    from src.exchange.base import BaseExchange

logger = get_logger("crypto_master.trading.live")


# Callback signature: (position, action) -> bool
# ``action`` is one of "open" or "close" so the callback can vary
# phrasing. Must return True to authorize the trade.
ConfirmationCallback = Callable[[Position, str], Awaitable[bool]]


class LiveTradingError(TradingError):
    """Base exception for live trading errors."""

    pass


class LiveModeError(LiveTradingError):
    """Raised when live trading is attempted on a testnet exchange.

    Live trading requires a mainnet exchange instance. Testnet exchanges
    should be used with ``PaperTrader`` instead.
    """

    pass


class LiveConfirmationRejectedError(LiveTradingError):
    """Raised when the user declines to confirm a live trade (NFR-012)."""

    pass


class LiveOrderRejectedError(LiveTradingError):
    """Raised when the exchange rejects an order or reports a non-filled state.

    Attributes:
        order_id: Exchange-assigned order ID, if available.
        status: The reported order status.
    """

    def __init__(
        self,
        message: str,
        order_id: str | None = None,
        status: OrderStatus | str | None = None,
    ) -> None:
        """Initialize LiveOrderRejectedError.

        Args:
            message: Error message.
            order_id: Exchange order ID, if known.
            status: The order status reported by the exchange.
        """
        super().__init__(message)
        self.order_id = order_id
        self.status = status


async def default_confirmation(position: Position, action: str) -> bool:
    """Default interactive CLI confirmation (NFR-012).

    Prints a summary of the proposed trade and reads a yes/no response
    from stdin in a worker thread so the event loop is not blocked.

    Args:
        position: The position being opened or closed.
        action: "open" or "close".

    Returns:
        True if the user types ``yes``/``y`` (case-insensitive).
    """
    lines = [
        "",
        "=== LIVE TRADE CONFIRMATION ===",
        f"Action:       {action.upper()}",
        f"Symbol:       {position.symbol}",
        f"Side:         {position.side}",
        f"Quantity:     {position.quantity}",
        f"Entry Price:  {position.entry_price}",
        f"Leverage:     {position.leverage}x",
        f"Notional:     {position.notional_value}",
    ]
    if position.stop_loss is not None:
        lines.append(f"Stop Loss:    {position.stop_loss}")
    if position.take_profit is not None:
        lines.append(f"Take Profit:  {position.take_profit}")
    lines.append("================================")
    print("\n".join(lines))

    response = await asyncio.to_thread(
        input, "Proceed with live trade? (yes/no): "
    )
    return response.strip().lower() in ("yes", "y")


class LiveTrader:
    """Executes real orders against an exchange mainnet account.

    LiveTrader mirrors PaperTrader's public shape where possible but
    every order-placing call asks the injected ``confirmation_callback``
    first. The exchange must be connected and must NOT be in testnet
    mode — attempting to construct a LiveTrader with a testnet exchange
    raises ``LiveModeError``.

    Automatic exits triggered by stop-loss / take-profit (via
    :meth:`monitor_positions`) do not re-prompt, because the user
    already approved those bounds when the position was opened.

    Related Requirements:
    - FR-009: Live Trading Mode
    - NFR-007: Trading History Storage
    - NFR-012: Live Trading Confirmation

    Usage:
        exchange = BinanceExchange(config, testnet=False)
        await exchange.connect()

        trader = LiveTrader(exchange=exchange)

        trade = await trader.open_position(position)
        ...
        closed_trades = await trader.monitor_positions()
    """

    def __init__(
        self,
        exchange: BaseExchange,
        data_dir: Path | None = None,
        confirmation_callback: ConfirmationCallback | None = None,
    ) -> None:
        """Initialize LiveTrader.

        Args:
            exchange: Connected exchange instance in mainnet mode.
            data_dir: Directory for trade history storage. Defaults to
                     ``data/trades/`` via ``TradeHistoryTracker``.
            confirmation_callback: Async callable asked to approve each
                     user-initiated order. Defaults to an interactive
                     CLI prompt.

        Raises:
            LiveModeError: If the exchange is in testnet mode.
        """
        if exchange.testnet:
            raise LiveModeError(
                "LiveTrader cannot be used with a testnet exchange; "
                "use PaperTrader for testnet execution."
            )

        self._exchange = exchange
        self._trade_tracker = TradeHistoryTracker(data_dir=data_dir)
        self._confirmation_callback: ConfirmationCallback = (
            confirmation_callback or default_confirmation
        )
        # trade_id -> Position (so monitor_positions can check SL/TP)
        self._open_positions: dict[str, Position] = {}

        logger.info(
            f"LiveTrader initialized on exchange {exchange.name} (mainnet)"
        )

    @property
    def exchange(self) -> BaseExchange:
        """Get the configured exchange instance."""
        return self._exchange

    async def open_position(
        self,
        position: Position,
        performance_record_id: str | None = None,
    ) -> TradeHistory:
        """Open a live position after explicit user confirmation.

        Args:
            position: The Position to open.
            performance_record_id: Optional link to PerformanceRecord.

        Returns:
            TradeHistory record with the exchange order ID.

        Raises:
            LiveConfirmationRejectedError: If the callback declined.
            LiveOrderRejectedError: If the exchange rejected the order
                or reported a terminal non-filled state.
            LiveTradingError: For other unexpected exchange errors.
        """
        approved = await self._confirmation_callback(position, "open")
        if not approved:
            logger.info(
                f"Live open rejected by user: {position.side} "
                f"{position.symbol} qty={position.quantity}"
            )
            raise LiveConfirmationRejectedError(
                f"User declined to open {position.side} {position.symbol}"
            )

        order_request = OrderRequest(
            symbol=position.symbol,
            side="buy" if position.side == "long" else "sell",
            type="market",
            quantity=position.quantity,
        )

        order = await self._submit_order(order_request, action="open")

        filled_qty = order.filled_quantity or position.quantity

        trade = self._trade_tracker.open_trade(
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            entry_quantity=filled_qty,
            mode="live",
            leverage=position.leverage,
            entry_order_id=order.id,
            performance_record_id=performance_record_id,
        )

        self._open_positions[trade.id] = position

        logger.info(
            f"Opened live position: {position.side} {position.symbol} "
            f"@ {position.entry_price}, qty={filled_qty}, order_id={order.id}"
        )
        return trade

    async def close_position(
        self,
        trade_id: str,
        reason: str = "manual",
        exit_price: Decimal | None = None,
    ) -> TradeHistory | None:
        """Close a live position after explicit user confirmation.

        Args:
            trade_id: ID of the trade to close.
            reason: Reason for closing. Must be "manual" for
                user-initiated closes; "stop_loss" and "take_profit"
                are reserved for the monitor loop.
            exit_price: Expected exit price (used for P&L and records
                since market orders may omit price in the response).

        Returns:
            Updated TradeHistory, or None if the trade is not open.

        Raises:
            LiveConfirmationRejectedError: If the callback declined.
            LiveOrderRejectedError: If the exchange rejected the order.
        """
        position = self._open_positions.get(trade_id)
        if position is None:
            logger.warning(f"No open live position found: {trade_id}")
            return None

        approved = await self._confirmation_callback(position, "close")
        if not approved:
            logger.info(
                f"Live close rejected by user: trade_id={trade_id}"
            )
            raise LiveConfirmationRejectedError(
                f"User declined to close trade {trade_id}"
            )

        return await self._execute_close(
            trade_id=trade_id,
            position=position,
            reason=reason,
            exit_price=exit_price,
        )

    async def monitor_positions(
        self,
    ) -> list[TradeHistory]:
        """Check SL/TP for all open positions and auto-close matches.

        Fetches the latest ticker for each tracked position's symbol,
        evaluates stop-loss / take-profit bounds, and closes any
        positions whose exit conditions are triggered. Auto-exits do
        NOT call the confirmation callback — the user pre-authorized
        the SL/TP levels when opening.

        Returns:
            List of TradeHistory records for positions that were
            closed during this monitor pass.
        """
        closed: list[TradeHistory] = []

        # Snapshot to allow safe mutation during iteration.
        for trade_id, position in list(self._open_positions.items()):
            try:
                ticker = await self._exchange.get_ticker(position.symbol)
            except Exception as e:
                logger.warning(
                    f"Ticker fetch failed for {position.symbol}: {e}"
                )
                continue

            reason = self._check_exit_reason(position, ticker.price)
            if reason is None:
                continue

            logger.info(
                f"Auto-exit triggered ({reason}) for {trade_id} "
                f"at {ticker.price}"
            )
            try:
                result = await self._execute_close(
                    trade_id=trade_id,
                    position=position,
                    reason=reason,
                    exit_price=ticker.price,
                )
            except LiveOrderRejectedError as e:
                logger.error(
                    f"Auto-exit order rejected for {trade_id}: {e}"
                )
                continue

            if result is not None:
                closed.append(result)

        return closed

    @staticmethod
    def _check_exit_reason(
        position: Position, current_price: Decimal
    ) -> str | None:
        """Return the exit reason if SL/TP is hit, else None."""
        if position.stop_loss is not None:
            if position.side == "long" and current_price <= position.stop_loss:
                return "stop_loss"
            if position.side == "short" and current_price >= position.stop_loss:
                return "stop_loss"

        if position.take_profit is not None:
            if position.side == "long" and current_price >= position.take_profit:
                return "take_profit"
            if position.side == "short" and current_price <= position.take_profit:
                return "take_profit"

        return None

    async def _execute_close(
        self,
        trade_id: str,
        position: Position,
        reason: str,
        exit_price: Decimal | None,
    ) -> TradeHistory | None:
        """Submit closing market order and update trade history.

        Args:
            trade_id: Trade ID to close.
            position: The tracked Position.
            reason: Close reason for the record.
            exit_price: Expected exit price for P&L.

        Returns:
            Updated TradeHistory, or None if trade not found.
        """
        closing_side = "sell" if position.side == "long" else "buy"
        order_request = OrderRequest(
            symbol=position.symbol,
            side=closing_side,
            type="market",
            quantity=position.quantity,
        )

        order = await self._submit_order(order_request, action="close")

        actual_exit_price = exit_price or position.entry_price

        closed_trade = self._trade_tracker.close_trade(
            trade_id=trade_id,
            exit_price=actual_exit_price,
            close_reason=reason,
            exit_order_id=order.id,
        )

        self._open_positions.pop(trade_id, None)

        logger.info(
            f"Closed live position {trade_id}: {reason}, "
            f"exit_price={actual_exit_price}, order_id={order.id}"
        )
        return closed_trade

    async def _submit_order(
        self,
        order_request: OrderRequest,
        action: str,
    ) -> object:
        """Submit an order to the exchange and validate the response.

        Args:
            order_request: Order to submit.
            action: "open" or "close" for logging/errors.

        Returns:
            The ``Order`` returned by the exchange.

        Raises:
            LiveOrderRejectedError: On non-filled/terminal status or
                exchange errors.
        """
        try:
            order = await self._exchange.create_order(order_request)
        except Exception as e:
            raise LiveOrderRejectedError(
                f"Exchange rejected {action} order: {e}"
            ) from e

        # Treat rejected/cancelled statuses as failures. Anything else
        # (filled, partially_filled, open for passive orders) is passed
        # through for the caller to record.
        if order.status in (OrderStatus.REJECTED, OrderStatus.CANCELLED):
            raise LiveOrderRejectedError(
                f"Exchange reported {order.status.value} for {action} order",
                order_id=order.id,
                status=order.status,
            )

        return order

    def get_open_trades(self) -> list[TradeHistory]:
        """Get all open live trades from the tracker.

        Returns:
            List of open TradeHistory records in live mode.
        """
        return self._trade_tracker.get_open_trades(mode="live")

    def get_trade(self, trade_id: str) -> TradeHistory | None:
        """Get a trade by ID.

        Args:
            trade_id: The trade ID.

        Returns:
            TradeHistory or None if not found.
        """
        return self._trade_tracker.get_trade(trade_id)

    def get_tracked_position(self, trade_id: str) -> Position | None:
        """Get the in-memory Position for an open live trade.

        Args:
            trade_id: The trade ID.

        Returns:
            The Position that was supplied when the trade was opened,
            or None if the trade is not currently tracked.
        """
        return self._open_positions.get(trade_id)

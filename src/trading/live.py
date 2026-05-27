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
from src.models import Order, OrderRequest, OrderStatus, Position
from src.strategy.performance import TradeHistory, TradeHistoryTracker
from src.trading.base import exit_condition_for_position, exit_reason_for_position
from src.trading.strategy import TradingError
from src.utils.trading_types import (
    OrderSide,
    closing_order_side,
    entry_order_side,
)

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

    response = await asyncio.to_thread(input, "Proceed with live trade? (yes/no): ")
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
        sub_account_id: str = "default",
    ) -> None:
        """Initialize LiveTrader.

        Args:
            exchange: Connected exchange instance in mainnet mode.
            data_dir: Directory for trade history storage. Defaults to
                     ``data/trades/`` via ``TradeHistoryTracker``.
            confirmation_callback: Async callable asked to approve each
                     user-initiated order. Defaults to an interactive
                     CLI prompt.
            sub_account_id: Capital bucket whose live trade history
                     this trader owns. Defaults to ``"default"`` for
                     legacy single-account live deployments.

        Raises:
            LiveModeError: If the exchange is in testnet mode.
        """
        if exchange.testnet:
            raise LiveModeError(
                "LiveTrader cannot be used with a testnet exchange; "
                "use PaperTrader for testnet execution."
            )

        self._exchange = exchange
        self._trade_tracker = TradeHistoryTracker(
            data_dir=data_dir,
            sub_account_id=sub_account_id,
        )
        self._confirmation_callback: ConfirmationCallback = (
            confirmation_callback or default_confirmation
        )
        # trade_id -> Position (so monitor_positions can check SL/TP)
        self._open_positions: dict[str, Position] = {}
        # trade_id -> entry-side fee actually paid on the open fill.
        # The trade record's ``fees`` field is set in one shot at close
        # time (``TradeHistoryTracker.close_trade`` accumulates), so we
        # park the entry fee here until then. Without this map the open
        # fee was previously dropped and live trade ``fees`` always read
        # zero, which silently overstated realised P&L on disk
        # (consistency-hardening CH-06).
        self._entry_fees: dict[str, Decimal] = {}
        self._rehydrate_open_positions()

        logger.info(f"LiveTrader initialized on exchange {exchange.name} (mainnet)")

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
            side=entry_order_side(position.side),
            type="market",
            quantity=position.quantity,
        )

        order = await self._submit_order(order_request, action="open")
        filled_qty = order.filled_quantity
        # Prefer the exchange's reported fill economics over the
        # caller-side ``position.entry_price`` so realised P&L matches
        # what actually executed (CH-06). Falls back to the request
        # price for adapters that don't yet surface ``average_price``.
        entry_fill_price = order.average_price or position.entry_price
        entry_fee = order.fee or Decimal("0")

        trade = self._trade_tracker.open_trade(
            symbol=position.symbol,
            side=position.side,
            entry_price=entry_fill_price,
            entry_quantity=filled_qty,
            mode="live",
            leverage=position.leverage,
            entry_order_id=order.id,
            performance_record_id=performance_record_id,
            fees=entry_fee,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
        )

        try:
            self._open_positions[trade.id] = position.model_copy(
                update={"quantity": filled_qty, "entry_price": entry_fill_price}
            )
            self._entry_fees[trade.id] = entry_fee

            logger.info(
                f"Opened live position: {position.side} {position.symbol} "
                f"@ {entry_fill_price}, qty={filled_qty}, "
                f"entry_fee={entry_fee} {order.fee_currency or ''}, "
                f"order_id={order.id}"
            )
        except Exception:
            self._open_positions.pop(trade.id, None)
            self._entry_fees.pop(trade.id, None)
            raise
        return trade

    async def close_position(
        self,
        trade_id: str,
        exit_price: Decimal,
        reason: str = "manual",
    ) -> TradeHistory | None:
        """Close a live position; asks for confirmation on manual closes.

        Signature matches :meth:`PaperTrader.close_position` and the
        :class:`~src.trading.base.Trader` protocol so the runtime
        engine can drive both implementations through the same call
        shape.

        Confirmation policy: ``reason="manual"`` calls the
        confirmation callback (the user explicitly initiated this
        close). ``reason="stop_loss"`` / ``"take_profit"`` skip the
        callback because the user already pre-authorized those bounds
        when the position was opened — fulfilling the same
        no-extra-prompt contract :meth:`monitor_positions` provides.

        Args:
            trade_id: ID of the trade to close.
            exit_price: Expected exit price (used for P&L and records
                since market orders may omit price in the response).
            reason: Reason for closing. ``"manual"`` (default),
                ``"stop_loss"``, or ``"take_profit"``.

        Returns:
            Updated TradeHistory, or None if the trade is not open.

        Raises:
            LiveConfirmationRejectedError: If the callback declined a
                manual close.
            LiveOrderRejectedError: If the exchange rejected the order.
        """
        position = self._open_positions.get(trade_id)
        if position is None:
            logger.warning(f"No open live position found: {trade_id}")
            return None

        if reason == "manual":
            approved = await self._confirmation_callback(position, "close")
            if not approved:
                logger.info(f"Live close rejected by user: trade_id={trade_id}")
                raise LiveConfirmationRejectedError(
                    f"User declined to close trade {trade_id}"
                )

        return await self._execute_close(
            trade_id=trade_id,
            position=position,
            reason=reason,
            exit_price=exit_price,
        )

    def check_exit_conditions(
        self,
        trade_id: str,
        current_price: Decimal,
    ) -> tuple[bool, str | None]:
        """Decide whether ``trade_id`` should exit at ``current_price``.

        Mirrors :meth:`PaperTrader.check_exit_conditions`. Returns
        ``(False, None)`` if no SL/TP is configured, or the trade is
        not currently open.
        """
        position = self._open_positions.get(trade_id)
        if position is None:
            return False, None
        return exit_condition_for_position(position, current_price)

    async def force_close_orphan(
        self,
        trade_id: str,
        exit_price: Decimal,
    ) -> TradeHistory | None:
        """Persistence-only force-close for an orphaned live trade.

        DEBT-058 follow-up watchdog hook (see
        :class:`~src.trading.base.Trader`). Closes the persisted trade
        record without touching the exchange — by definition the
        in-memory ``_open_positions`` entry is gone, and the watchdog
        cannot safely place an exchange order without it.

        Returns ``None`` (no-op) when the trade is already closed or
        unknown; mirrors the missing-trade contract on
        :meth:`close_position`.

        IMPORTANT: this method does NOT call
        ``exchange.create_order(close)``. The exchange-side position
        (if any still exists) must be reconciled separately by an
        operator. A WARNING is logged at force-close time so the
        situation is never silent.
        """
        existing = self._trade_tracker.get_trade(trade_id)
        if existing is None or existing.status != "open":
            logger.warning(
                "force_close_orphan: live trade %s not found or not open "
                "(status=%s); no-op",
                trade_id,
                existing.status if existing is not None else "missing",
            )
            return None

        # Defensive race: if a late rehydration restored
        # ``_open_positions[trade_id]`` between the watchdog's
        # ``_missing_position_state`` check and now, drop it so the
        # in-memory map doesn't outlive the persisted "closed" row.
        self._open_positions.pop(trade_id, None)
        self._entry_fees.pop(trade_id, None)

        closed = self._trade_tracker.close_trade(
            trade_id=trade_id,
            exit_price=exit_price,
            close_reason="orphan_force_close",
        )

        if closed is not None:
            logger.warning(
                "force_close_orphan: closed persisted live trade %s at %s "
                "(side=%s entry=%s pnl=%s) — exchange-side position may still "
                "be open; operator reconciliation required",
                trade_id,
                exit_price,
                closed.side,
                closed.entry_price,
                closed.pnl,
            )

        return closed

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
                logger.warning(f"Ticker fetch failed for {position.symbol}: {e}")
                continue

            reason = exit_reason_for_position(position, ticker.price)
            if reason is None:
                continue

            logger.info(
                f"Auto-exit triggered ({reason}) for {trade_id} " f"at {ticker.price}"
            )
            try:
                result = await self._execute_close(
                    trade_id=trade_id,
                    position=position,
                    reason=reason,
                    exit_price=ticker.price,
                )
            except LiveOrderRejectedError as e:
                logger.error(f"Auto-exit order rejected for {trade_id}: {e}")
                continue

            if result is not None:
                closed.append(result)

        return closed

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
        closing_side: OrderSide = closing_order_side(position.side)
        order_request = OrderRequest(
            symbol=position.symbol,
            side=closing_side,
            type="market",
            quantity=position.quantity,
        )

        order = await self._submit_order(order_request, action="close")

        # Prefer the exchange's reported fill price over the caller's
        # expected ``exit_price`` so realised P&L matches what actually
        # executed (CH-06). The caller-side price is still used as a
        # last-resort fallback for adapters that haven't been updated
        # to surface ``average_price`` yet.
        actual_exit_price = order.average_price or exit_price or position.entry_price

        exit_fee = order.fee or Decimal("0")
        persisted_trade = self._trade_tracker.get_trade(trade_id)
        persisted_fees = persisted_trade.fees if persisted_trade is not None else None
        entry_fee = self._entry_fees.pop(trade_id, Decimal("0"))
        fees_to_add = exit_fee if persisted_fees else entry_fee + exit_fee

        closed_trade = self._trade_tracker.close_trade(
            trade_id=trade_id,
            exit_price=actual_exit_price,
            close_reason=reason,
            exit_order_id=order.id,
            fees=fees_to_add,
        )

        self._open_positions.pop(trade_id, None)

        logger.info(
            f"Closed live position {trade_id}: {reason}, "
            f"exit_price={actual_exit_price}, order_id={order.id}, "
            f"fees=entry({persisted_fees if persisted_fees else entry_fee})+"
            f"exit({exit_fee})"
        )
        return closed_trade

    def _rehydrate_open_positions(self) -> None:
        """Rebuild monitorable live positions from persisted open trades.

        Legacy open trades may not carry SL/TP bounds. Those remain visible
        through ``get_open_trades`` but are intentionally left out of
        ``_open_positions`` so the runtime orphan guard can require operator
        reconciliation instead of pretending they are safe to monitor.
        """
        for trade in self._trade_tracker.get_open_trades(mode="live"):
            if trade.stop_loss is None and trade.take_profit is None:
                logger.warning(
                    "Open live trade %s has no persisted SL/TP bounds; "
                    "operator reconciliation required before monitoring",
                    trade.id,
                )
                continue
            self._open_positions[trade.id] = Position(
                symbol=trade.symbol,
                side=trade.side,
                entry_price=trade.entry_price,
                quantity=trade.entry_quantity,
                leverage=trade.leverage,
                stop_loss=trade.stop_loss,
                take_profit=trade.take_profit,
            )

    async def _submit_order(
        self,
        order_request: OrderRequest,
        action: str,
    ) -> Order:
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

        if order.status in (OrderStatus.REJECTED, OrderStatus.CANCELLED):
            raise LiveOrderRejectedError(
                f"Exchange reported {order.status.value} for {action} order",
                order_id=order.id,
                status=order.status,
            )
        if order.status != OrderStatus.FILLED:
            raise LiveOrderRejectedError(
                f"Exchange reported non-filled status {order.status.value} "
                f"for {action} market order",
                order_id=order.id,
                status=order.status,
            )
        if order.filled_quantity <= 0:
            raise LiveOrderRejectedError(
                f"Exchange reported zero fill for {action} market order",
                order_id=order.id,
                status=order.status,
            )
        if order.filled_quantity != order_request.quantity:
            raise LiveOrderRejectedError(
                f"Exchange reported partial fill for {action} market order: "
                f"filled={order.filled_quantity} requested={order_request.quantity}",
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

    async def get_balances(self) -> dict[str, Decimal]:
        """Query the exchange for all balances and return totals per currency.

        Used by the engine's portfolio-snapshot recorder so the
        dashboard's Trading page can show current equity. Network
        failures propagate to the caller — the engine wraps the call
        in a guard so a flaky exchange query doesn't break the cycle.
        """
        balances = await self._exchange.get_balance()
        return {b.currency: b.total for b in balances}

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

    def get_open_position(self, trade_id: str) -> Position | None:
        """Return the monitorable in-memory position for a live trade."""
        return self.get_tracked_position(trade_id)

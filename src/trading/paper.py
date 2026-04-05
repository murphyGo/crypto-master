"""Paper trading engine for simulated trading.

Provides a virtual trading environment that simulates real trading
without using actual funds.

Related Requirements:
- FR-010: Paper Trading Mode
- NFR-007: Trading History Storage
- NFR-008: Asset/PnL History (mode separation)
"""

import uuid
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from src.logger import get_logger
from src.models import Position
from src.strategy.performance import TradeHistory, TradeHistoryTracker
from src.trading.strategy import TradingError

logger = get_logger("crypto_master.trading.paper")


class PaperTradingError(TradingError):
    """Base exception for paper trading errors."""

    pass


class InsufficientPaperBalanceError(PaperTradingError):
    """Raised when paper balance is insufficient for operation.

    Attributes:
        required: The required amount.
        available: The available amount.
        currency: The currency.
    """

    def __init__(
        self,
        message: str,
        required: Decimal,
        available: Decimal,
        currency: str,
    ) -> None:
        """Initialize InsufficientPaperBalanceError.

        Args:
            message: Error message.
            required: The required amount.
            available: The available amount.
            currency: The currency.
        """
        super().__init__(message)
        self.required = required
        self.available = available
        self.currency = currency


class PaperBalance(BaseModel):
    """Virtual balance for paper trading.

    Tracks free (available) and locked (in positions) amounts.

    Attributes:
        currency: Currency code (e.g., "USDT").
        free: Available balance.
        locked: Balance locked in open positions.
    """

    currency: str
    free: Decimal = Field(default=Decimal("0"), ge=0)
    locked: Decimal = Field(default=Decimal("0"), ge=0)

    model_config = {"validate_assignment": True}

    @property
    def total(self) -> Decimal:
        """Get total balance (free + locked)."""
        return self.free + self.locked

    def lock(self, amount: Decimal) -> None:
        """Lock an amount from free balance.

        Args:
            amount: Amount to lock.

        Raises:
            InsufficientPaperBalanceError: If insufficient free balance.
        """
        if amount <= 0:
            raise PaperTradingError(f"Lock amount must be positive: {amount}")

        if amount > self.free:
            raise InsufficientPaperBalanceError(
                f"Insufficient free balance: need {amount} {self.currency}, "
                f"have {self.free}",
                required=amount,
                available=self.free,
                currency=self.currency,
            )

        self.free -= amount
        self.locked += amount

    def unlock(self, amount: Decimal) -> None:
        """Unlock an amount back to free balance.

        Args:
            amount: Amount to unlock.

        Raises:
            PaperTradingError: If amount exceeds locked balance.
        """
        if amount <= 0:
            raise PaperTradingError(f"Unlock amount must be positive: {amount}")

        if amount > self.locked:
            raise PaperTradingError(
                f"Cannot unlock {amount} {self.currency}: only {self.locked} locked"
            )

        self.locked -= amount
        self.free += amount

    def add(self, amount: Decimal) -> None:
        """Add amount to free balance (e.g., profit or deposit).

        Args:
            amount: Amount to add.
        """
        if amount <= 0:
            raise PaperTradingError(f"Add amount must be positive: {amount}")

        self.free += amount

    def deduct(self, amount: Decimal) -> None:
        """Deduct amount from free balance (e.g., loss or withdrawal).

        Args:
            amount: Amount to deduct.

        Raises:
            InsufficientPaperBalanceError: If insufficient free balance.
        """
        if amount <= 0:
            raise PaperTradingError(f"Deduct amount must be positive: {amount}")

        if amount > self.free:
            raise InsufficientPaperBalanceError(
                f"Insufficient free balance to deduct: need {amount} {self.currency}, "
                f"have {self.free}",
                required=amount,
                available=self.free,
                currency=self.currency,
            )

        self.free -= amount


class OpenPosition(BaseModel):
    """Tracks an open position in paper trading.

    Links a Position to its TradeHistory and tracks margin.

    Attributes:
        trade_id: ID of the associated TradeHistory.
        position: The original Position.
        margin: Margin locked for this position.
        quote_currency: The quote currency (for balance management).
    """

    trade_id: str
    position: Position
    margin: Decimal
    quote_currency: str


class PaperTrader:
    """Simulates trading with virtual funds.

    Provides a complete paper trading environment including:
    - Virtual balance management
    - Market order instant fill simulation
    - Stop-loss and take-profit monitoring
    - Trade history recording via TradeHistoryTracker

    Related Requirements:
    - FR-010: Paper Trading Mode
    - NFR-007: Trading History Storage
    - NFR-008: Asset/PnL History

    Usage:
        trader = PaperTrader(initial_balance={"USDT": Decimal("10000")})

        # Open position from a Position object
        trade = trader.open_position(position)

        # Check exit conditions with current price
        should_exit, reason = trader.check_exit_conditions(trade.id, current_price)
        if should_exit:
            trader.close_position(trade.id, current_price, reason)

        # Or close manually
        trader.close_position(trade.id, exit_price, "manual")
    """

    def __init__(
        self,
        initial_balance: dict[str, Decimal] | None = None,
        data_dir: Path | None = None,
    ) -> None:
        """Initialize PaperTrader.

        Args:
            initial_balance: Initial virtual balances per currency.
                            Example: {"USDT": Decimal("10000")}
            data_dir: Directory for trade history storage.
                     Defaults to data/trades/.
        """
        self._balances: dict[str, PaperBalance] = {}
        self._open_positions: dict[str, OpenPosition] = {}
        self._trade_tracker = TradeHistoryTracker(data_dir=data_dir)

        # Initialize balances
        if initial_balance:
            for currency, amount in initial_balance.items():
                self._balances[currency] = PaperBalance(
                    currency=currency,
                    free=amount,
                )

        logger.info(
            f"PaperTrader initialized with balances: "
            f"{self.get_balance_summary()}"
        )

    def get_balance_summary(self) -> dict[str, dict[str, str]]:
        """Get a summary of all balances.

        Returns:
            Dictionary of currency -> {free, locked, total} as strings.
        """
        return {
            currency: {
                "free": str(balance.free),
                "locked": str(balance.locked),
                "total": str(balance.total),
            }
            for currency, balance in self._balances.items()
        }

    def get_balance(self, currency: str) -> PaperBalance | None:
        """Get balance for a currency.

        Args:
            currency: Currency code.

        Returns:
            PaperBalance or None if currency not found.
        """
        return self._balances.get(currency)

    def get_all_balances(self) -> dict[str, PaperBalance]:
        """Get all balances.

        Returns:
            Dictionary of currency -> PaperBalance.
        """
        return self._balances.copy()

    def set_balance(self, currency: str, amount: Decimal) -> None:
        """Set the free balance for a currency.

        Creates the currency balance if it doesn't exist.

        Args:
            currency: Currency code.
            amount: Amount to set as free balance.
        """
        if currency in self._balances:
            # Reset to the new amount (keeping locked as is)
            balance = self._balances[currency]
            balance.free = amount
        else:
            self._balances[currency] = PaperBalance(
                currency=currency,
                free=amount,
            )

    def _get_quote_currency(self, symbol: str) -> str:
        """Extract quote currency from symbol.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT").

        Returns:
            Quote currency (e.g., "USDT").
        """
        if "/" in symbol:
            return symbol.split("/")[1]
        # Assume last 4 characters for USDT, 3 for USD, etc.
        if symbol.endswith("USDT"):
            return "USDT"
        if symbol.endswith("USD"):
            return "USD"
        if symbol.endswith("BTC"):
            return "BTC"
        # Default fallback
        return symbol[-4:] if len(symbol) > 4 else symbol

    def _calculate_required_margin(self, position: Position) -> Decimal:
        """Calculate margin required for a position.

        Args:
            position: The position.

        Returns:
            Required margin amount.
        """
        notional = position.notional_value
        return notional / Decimal(position.leverage)

    def _generate_order_id(self) -> str:
        """Generate a simulated order ID.

        Returns:
            Unique order ID string.
        """
        return f"paper-{uuid.uuid4().hex[:12]}"

    def open_position(
        self,
        position: Position,
        performance_record_id: str | None = None,
    ) -> TradeHistory:
        """Open a paper trading position.

        Locks the required margin and creates a trade record.

        Args:
            position: The Position to open (from TradingStrategy.create_position).
            performance_record_id: Optional link to PerformanceRecord.

        Returns:
            TradeHistory record for the opened trade.

        Raises:
            InsufficientPaperBalanceError: If insufficient balance for margin.
            PaperTradingError: If position is invalid.
        """
        # Extract quote currency for balance management
        quote_currency = self._get_quote_currency(position.symbol)

        # Check balance exists
        balance = self.get_balance(quote_currency)
        if balance is None:
            raise PaperTradingError(
                f"No {quote_currency} balance configured for paper trading"
            )

        # Calculate and lock margin
        margin = self._calculate_required_margin(position)
        balance.lock(margin)

        # Generate order ID for simulation
        order_id = self._generate_order_id()

        # Record trade via TradeHistoryTracker
        trade = self._trade_tracker.open_trade(
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            entry_quantity=position.quantity,
            mode="paper",
            leverage=position.leverage,
            entry_order_id=order_id,
            performance_record_id=performance_record_id,
        )

        # Track open position
        self._open_positions[trade.id] = OpenPosition(
            trade_id=trade.id,
            position=position,
            margin=margin,
            quote_currency=quote_currency,
        )

        logger.info(
            f"Opened paper position: {position.side} {position.symbol} "
            f"@ {position.entry_price}, qty={position.quantity}, "
            f"margin={margin} {quote_currency}"
        )

        return trade

    def close_position(
        self,
        trade_id: str,
        exit_price: Decimal,
        reason: str = "manual",
    ) -> TradeHistory | None:
        """Close a paper trading position.

        Calculates P&L, updates balance, and records the trade closure.

        Args:
            trade_id: ID of the trade to close.
            exit_price: Price at which to close.
            reason: Reason for closing (manual, stop_loss, take_profit).

        Returns:
            Updated TradeHistory, or None if trade not found.

        Raises:
            PaperTradingError: If trade is not an open paper trade.
        """
        # Get open position
        open_pos = self._open_positions.get(trade_id)
        if open_pos is None:
            logger.warning(f"No open paper position found: {trade_id}")
            return None

        position = open_pos.position
        margin = open_pos.margin
        quote_currency = open_pos.quote_currency

        # Calculate P&L
        pnl = position.calculate_pnl(exit_price)

        # Update balance: unlock margin and apply P&L
        balance = self.get_balance(quote_currency)
        if balance:
            balance.unlock(margin)
            if pnl > 0:
                balance.add(pnl)
            elif pnl < 0:
                # Deduct loss from free balance (already unlocked margin)
                loss_amount = abs(pnl)
                if loss_amount <= balance.free:
                    balance.deduct(loss_amount)
                else:
                    # Margin was the max loss; adjust to available
                    balance.free = Decimal("0")

        # Close trade via tracker
        closed_trade = self._trade_tracker.close_trade(
            trade_id=trade_id,
            exit_price=exit_price,
            close_reason=reason,
        )

        # Remove from open positions
        del self._open_positions[trade_id]

        logger.info(
            f"Closed paper position {trade_id}: {reason}, "
            f"exit_price={exit_price}, P&L={pnl}"
        )

        return closed_trade

    def check_exit_conditions(
        self,
        trade_id: str,
        current_price: Decimal,
    ) -> tuple[bool, str | None]:
        """Check if a position should be closed due to SL/TP.

        Args:
            trade_id: ID of the trade to check.
            current_price: Current market price.

        Returns:
            Tuple of (should_exit, reason). reason is None if should_exit is False.
        """
        open_pos = self._open_positions.get(trade_id)
        if open_pos is None:
            return False, None

        position = open_pos.position

        # Check stop loss
        if position.stop_loss is not None:
            if position.side == "long" and current_price <= position.stop_loss:
                return True, "stop_loss"
            if position.side == "short" and current_price >= position.stop_loss:
                return True, "stop_loss"

        # Check take profit
        if position.take_profit is not None:
            if position.side == "long" and current_price >= position.take_profit:
                return True, "take_profit"
            if position.side == "short" and current_price <= position.take_profit:
                return True, "take_profit"

        return False, None

    def get_open_trades(self) -> list[TradeHistory]:
        """Get all open paper trades.

        Returns:
            List of open TradeHistory records.
        """
        return self._trade_tracker.get_open_trades(mode="paper")

    def get_trade(self, trade_id: str) -> TradeHistory | None:
        """Get a trade by ID.

        Args:
            trade_id: The trade ID.

        Returns:
            TradeHistory or None if not found.
        """
        return self._trade_tracker.get_trade(trade_id)

    def get_open_position(self, trade_id: str) -> OpenPosition | None:
        """Get an open position's details.

        Args:
            trade_id: The trade ID.

        Returns:
            OpenPosition or None if not found.
        """
        return self._open_positions.get(trade_id)

    def update_unrealized_pnl(
        self,
        current_prices: dict[str, Decimal],
    ) -> dict[str, Decimal]:
        """Update unrealized P&L for all open positions.

        Args:
            current_prices: Dictionary of symbol -> current price.

        Returns:
            Dictionary of trade_id -> unrealized P&L.
        """
        pnl_by_trade: dict[str, Decimal] = {}

        for trade_id, open_pos in self._open_positions.items():
            symbol = open_pos.position.symbol
            if symbol in current_prices:
                current_price = current_prices[symbol]
                pnl = open_pos.position.calculate_pnl(current_price)
                pnl_by_trade[trade_id] = pnl

        return pnl_by_trade

    def get_total_unrealized_pnl(
        self,
        current_prices: dict[str, Decimal],
    ) -> Decimal:
        """Get total unrealized P&L across all open positions.

        Args:
            current_prices: Dictionary of symbol -> current price.

        Returns:
            Total unrealized P&L.
        """
        pnl_by_trade = self.update_unrealized_pnl(current_prices)
        return sum(pnl_by_trade.values(), Decimal("0"))

    def get_total_equity(
        self,
        quote_currency: str,
        current_prices: dict[str, Decimal] | None = None,
    ) -> Decimal:
        """Get total equity (balance + unrealized P&L).

        Args:
            quote_currency: The quote currency to calculate equity for.
            current_prices: Current prices for unrealized P&L calculation.

        Returns:
            Total equity in quote currency.
        """
        balance = self.get_balance(quote_currency)
        if balance is None:
            return Decimal("0")

        equity = balance.total

        if current_prices:
            unrealized_pnl = self.get_total_unrealized_pnl(current_prices)
            equity += unrealized_pnl

        return equity

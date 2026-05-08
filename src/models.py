"""Common data models for Crypto Master.

This module defines the core data structures used throughout the application
for trading, exchange interactions, and analysis.

Related Requirements:
- FR-006: Risk/Reward Calculation
- FR-008: Entry/Take-Profit/Stop-Loss Setting
- FR-020: Historical Chart Data Query
- NFR-007: Trading History Storage
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from src.utils.time import now_utc

# DEBT-035 (Phase 26.2): the legacy ``Trade`` Pydantic model lived here
# but was never instantiated anywhere in ``src/``. The live and paper
# trading layers persist :class:`src.strategy.performance.TradeHistory`,
# the backtester emits :class:`src.backtest.engine.BacktestTrade`, and
# nothing ever consumed the generic ``Trade`` shape. Removed in 26.2 to
# stop the dead-code drift; re-introduce only with a real consumer.


class OrderStatus(str, Enum):
    """Status of an order in the exchange."""

    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OHLCV(BaseModel):
    """OHLCV (Open, High, Low, Close, Volume) candlestick data.

    Represents a single candlestick in chart data.
    Uses Decimal for financial precision.
    """

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    model_config = {"frozen": True}


class Ticker(BaseModel):
    """Current price ticker for a trading pair.

    Represents the latest price information from an exchange.
    """

    symbol: str
    price: Decimal
    timestamp: datetime

    model_config = {"frozen": True}


class Balance(BaseModel):
    """Account balance for a specific currency.

    Tracks free (available), locked (in orders), and total balance.
    """

    currency: str
    free: Decimal = Decimal("0")
    locked: Decimal = Decimal("0")
    total: Decimal = Decimal("0")

    def model_post_init(self, __context: object) -> None:
        """Validate that total equals free + locked if not explicitly set."""
        expected_total = self.free + self.locked
        if self.total == Decimal("0") and expected_total > 0:
            object.__setattr__(self, "total", expected_total)


class OrderRequest(BaseModel):
    """Request to create a new order.

    Used when submitting orders to an exchange.
    """

    symbol: str
    side: Literal["buy", "sell"]
    type: Literal["market", "limit"]
    quantity: Decimal = Field(gt=0)
    price: Decimal | None = Field(default=None, gt=0)

    def model_post_init(self, __context: object) -> None:
        """Validate that limit orders have a price."""
        if self.type == "limit" and self.price is None:
            raise ValueError("Limit orders must specify a price")


class Order(BaseModel):
    """An order that has been submitted to an exchange.

    Tracks the full lifecycle of an order from creation to completion.

    ``average_price`` and ``fee`` carry the actual fill economics from
    the exchange so :class:`~src.trading.live.LiveTrader` can attribute
    realised P&L to what really happened — the request-side ``price``
    is None for market orders and ``filled_quantity`` alone cannot tell
    a caller what they paid (consistency-hardening CH-06).
    """

    id: str
    symbol: str
    side: Literal["buy", "sell"]
    type: Literal["market", "limit"]
    price: Decimal | None = None
    quantity: Decimal = Field(gt=0)
    filled_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    average_price: Decimal | None = Field(default=None, gt=0)
    fee: Decimal | None = Field(default=None, ge=0)
    fee_currency: str | None = None
    status: OrderStatus
    created_at: datetime
    updated_at: datetime | None = None

    @property
    def remaining_quantity(self) -> Decimal:
        """Calculate the unfilled quantity."""
        return self.quantity - self.filled_quantity

    @property
    def is_complete(self) -> bool:
        """Check if the order is in a terminal state."""
        return self.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        )


class Position(BaseModel):
    """An open trading position.

    Represents a long or short position with associated risk parameters.
    """

    symbol: str
    side: Literal["long", "short"]
    entry_price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    leverage: int = Field(default=1, ge=1, le=125)
    stop_loss: Decimal | None = Field(default=None, gt=0)
    take_profit: Decimal | None = Field(default=None, gt=0)
    unrealized_pnl: Decimal = Decimal("0")

    @property
    def notional_value(self) -> Decimal:
        """Calculate the notional value of the position."""
        return self.entry_price * self.quantity

    @property
    def margin_required(self) -> Decimal:
        """Calculate the margin required for this position."""
        return self.notional_value / Decimal(self.leverage)

    def calculate_pnl(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized PnL at a given price.

        Matches the canonical convention pinned by
        :func:`src.utils.trading_math.pnl_for_trade`: ``quantity``
        already reflects the levered notional from
        :meth:`TradingStrategy.calculate_position_size`, so leverage
        is *not* re-multiplied here (DEBT-024 / Phase 20.1).

        Args:
            current_price: Current market price.

        Returns:
            Decimal: Unrealized profit/loss.
        """
        price_diff = current_price - self.entry_price
        if self.side == "short":
            price_diff = -price_diff
        return price_diff * self.quantity


class AnalysisResult(BaseModel):
    """Result from chart analysis.

    Contains the trading signal and associated parameters
    from an analysis technique.
    """

    signal: Literal["long", "short", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    entry_price: Decimal = Field(gt=0)
    stop_loss: Decimal = Field(gt=0)
    take_profit: Decimal = Field(gt=0)
    reasoning: str
    timestamp: datetime = Field(default_factory=now_utc)

    @property
    def risk_reward_ratio(self) -> float | None:
        """Calculate the risk/reward ratio.

        Returns:
            float | None: R/R ratio, or None if invalid prices.
        """
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)
        if risk == 0:
            return None
        return float(reward / risk)

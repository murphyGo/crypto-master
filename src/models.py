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
    """

    id: str
    symbol: str
    side: Literal["buy", "sell"]
    type: Literal["market", "limit"]
    price: Decimal | None = None
    quantity: Decimal = Field(gt=0)
    filled_quantity: Decimal = Field(default=Decimal("0"), ge=0)
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
    timestamp: datetime = Field(default_factory=datetime.now)

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


class Trade(BaseModel):
    """A completed trade (entry + exit).

    Records the full lifecycle of a trade for history and analysis.
    """

    id: str
    symbol: str
    side: Literal["long", "short"]
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    leverage: int = 1
    entry_time: datetime
    exit_time: datetime
    pnl: Decimal
    pnl_percentage: float
    fees: Decimal = Decimal("0")

    @property
    def is_profitable(self) -> bool:
        """Check if the trade was profitable."""
        return self.pnl > 0

    @property
    def duration(self) -> float:
        """Calculate trade duration in hours."""
        delta = self.exit_time - self.entry_time
        return delta.total_seconds() / 3600

"""Closed-trade autopsy evidence models.

This module normalizes paper/live ``TradeHistory`` and backtest
``BacktestTrade`` records into a common post-trade diagnostic shape. MFE/MAE
and candle-window metrics are added in later construction steps.

Related Requirements:
- FR-005: Analysis Technique Performance Tracking
- FR-021: Strategy Improvement
- FR-041: Trade quality autopsy
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, field_validator

from src.strategy.performance import TradeHistory
from src.utils.time import ensure_utc

if TYPE_CHECKING:
    from src.backtest.engine import BacktestTrade


class TradeAutopsyError(ValueError):
    """Raised when a trade cannot be converted into an autopsy record."""


class TradeAutopsyOutcome(str, Enum):
    """Outcome bucket for closed-trade autopsy records."""

    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


class TradeAutopsy(BaseModel):
    """Normalized evidence for one closed trade."""

    trade_id: str
    symbol: str
    side: Literal["long", "short"]
    mode: Literal["backtest", "paper", "live"]
    sub_account_id: str = "default"
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    leverage: int
    fees: Decimal = Decimal("0")
    pnl: Decimal
    pnl_percent: float | None = None
    close_reason: str
    holding_seconds: float = Field(ge=0.0)
    outcome: TradeAutopsyOutcome
    evidence: list[str] = Field(default_factory=list)

    @field_validator("entry_time", "exit_time", mode="after")
    @classmethod
    def _coerce_timestamps_to_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @classmethod
    def from_trade_history(cls, trade: TradeHistory) -> TradeAutopsy:
        """Build autopsy evidence from a closed runtime trade."""
        if trade.status != "closed":
            raise TradeAutopsyError(f"trade {trade.id} is not closed")
        if trade.exit_price is None or trade.exit_time is None:
            raise TradeAutopsyError(f"trade {trade.id} has no exit fill")
        if trade.exit_quantity is None:
            raise TradeAutopsyError(f"trade {trade.id} has no exit quantity")
        if trade.pnl is None:
            raise TradeAutopsyError(f"trade {trade.id} has no realized pnl")
        close_reason = trade.close_reason or "unknown"
        return cls(
            trade_id=trade.id,
            symbol=trade.symbol,
            side=trade.side,
            mode=trade.mode,
            sub_account_id=trade.sub_account_id,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            quantity=trade.exit_quantity,
            leverage=trade.leverage,
            fees=trade.fees,
            pnl=trade.pnl,
            pnl_percent=trade.pnl_percent,
            close_reason=close_reason,
            holding_seconds=_holding_seconds(trade.entry_time, trade.exit_time),
            outcome=_outcome_for_pnl(trade.pnl),
            evidence=[f"closed by {close_reason}", f"mode={trade.mode}"],
        )

    @classmethod
    def from_backtest_trade(cls, trade: BacktestTrade) -> TradeAutopsy:
        """Build autopsy evidence from a backtest trade."""
        return cls(
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            side=trade.side,
            mode="backtest",
            sub_account_id=trade.sub_account_id,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            quantity=trade.quantity,
            leverage=trade.leverage,
            fees=trade.entry_fee + trade.exit_fee,
            pnl=trade.pnl,
            pnl_percent=_pnl_percent(
                pnl=trade.pnl,
                entry_price=trade.entry_price,
                quantity=trade.quantity,
            ),
            close_reason=trade.close_reason,
            holding_seconds=_holding_seconds(trade.entry_time, trade.exit_time),
            outcome=_outcome_for_pnl(trade.pnl),
            evidence=[f"closed by {trade.close_reason}", "mode=backtest"],
        )


def _outcome_for_pnl(pnl: Decimal) -> TradeAutopsyOutcome:
    if pnl > 0:
        return TradeAutopsyOutcome.WIN
    if pnl < 0:
        return TradeAutopsyOutcome.LOSS
    return TradeAutopsyOutcome.BREAKEVEN


def _holding_seconds(entry_time: datetime, exit_time: datetime) -> float:
    return max(0.0, (ensure_utc(exit_time) - ensure_utc(entry_time)).total_seconds())


def _pnl_percent(
    *,
    pnl: Decimal,
    entry_price: Decimal,
    quantity: Decimal,
) -> float | None:
    notional = entry_price * quantity
    if notional == 0:
        return None
    return float(pnl / notional) * 100


__all__ = [
    "TradeAutopsy",
    "TradeAutopsyError",
    "TradeAutopsyOutcome",
]

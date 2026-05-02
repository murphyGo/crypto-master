"""Multi-account backtest report models (Phase 19.5)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from src.backtest.analyzer import PerformanceMetrics
from src.backtest.engine import BacktestTrade


class MultiAccountReport(BaseModel):
    """Comparative report for strategy-combination A/B backtests."""

    run_id: str
    symbol: str
    timeframe: str
    per_sub_account: dict[str, PerformanceMetrics]
    equity_curves: dict[str, list[tuple[datetime, Decimal]]] = Field(
        default_factory=dict
    )
    pairwise_correlation: dict[str, float] = Field(default_factory=dict)
    merged_trade_ledger: list[BacktestTrade] = Field(default_factory=list)
    robustness_passed: dict[str, bool | None] = Field(default_factory=dict)


__all__ = ["MultiAccountReport"]

"""Shared backtest metric helpers."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TradeOutcomeCounts:
    """Win/loss/breakeven counts for a closed-trade PnL series."""

    wins: int
    losses: int
    breakevens: int

    @property
    def total(self) -> int:
        return self.wins + self.losses + self.breakevens

    @property
    def win_rate(self) -> float:
        return self.wins / self.total if self.total else 0.0

    @property
    def loss_rate(self) -> float:
        return self.losses / self.total if self.total else 0.0


def count_trade_outcomes(pnls: Iterable[Decimal]) -> TradeOutcomeCounts:
    """Count positive, negative, and flat trade PnLs."""
    wins = losses = breakevens = 0
    for pnl in pnls:
        if pnl > 0:
            wins += 1
        elif pnl < 0:
            losses += 1
        else:
            breakevens += 1
    return TradeOutcomeCounts(wins=wins, losses=losses, breakevens=breakevens)


def return_percent(initial: Decimal, final: Decimal) -> float:
    """Return percentage from ``initial`` to ``final``; zero if undefined."""
    if initial <= 0:
        return 0.0
    return float((final - initial) / initial * 100)


def max_drawdown_from_equity_values(
    values: Iterable[Decimal],
    initial: Decimal,
) -> tuple[Decimal, float]:
    """Largest peak-to-trough drawdown from an equity value sequence."""
    peak = initial
    max_dd_abs = Decimal("0")
    max_dd_peak = initial
    for equity in values:
        if equity > peak:
            peak = equity
        drawdown = peak - equity
        if drawdown > max_dd_abs:
            max_dd_abs = drawdown
            max_dd_peak = peak
    if max_dd_peak <= 0:
        return max_dd_abs, 0.0
    return max_dd_abs, float(max_dd_abs / max_dd_peak * 100)


def sharpe_from_returns(
    returns: Sequence[float],
    annualization_factor: int | None = None,
) -> float | None:
    """Mean/std Sharpe with optional sqrt(N) annualization."""
    if len(returns) < 2:
        return None
    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    std_r = math.sqrt(variance)
    if std_r == 0:
        return None
    sharpe = mean_r / std_r
    if annualization_factor is not None and annualization_factor > 0:
        sharpe *= math.sqrt(annualization_factor)
    return sharpe


def sharpe_from_trade_pnls(
    pnls: Sequence[Decimal],
    initial_balance: Decimal,
    annualization_factor: int | None = None,
) -> float | None:
    """Sharpe from trade PnL values normalized by initial balance."""
    if initial_balance <= 0:
        return None
    returns = [float(pnl / initial_balance) for pnl in pnls]
    return sharpe_from_returns(returns, annualization_factor)

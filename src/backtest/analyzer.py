"""Performance analyzer for backtest results.

Consumes a ``BacktestResult`` and produces summary statistics —
win rate, returns, max drawdown, Sharpe ratio, profit factor,
expectancy — plus a human-readable markdown report.

Related Requirements:
- FR-021: Technique Performance Analysis
- FR-025: Backtesting Execution (consumes BacktestResult)
- NFR-006: Backtesting Result Storage
"""

from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from src.backtest.engine import BacktestResult, BacktestTrade
from src.logger import get_logger

logger = get_logger("crypto_master.backtest.analyzer")


# Days per year used for annualized return scaling
DAYS_PER_YEAR = 365


class PerformanceMetrics(BaseModel):
    """Aggregate performance metrics for a backtest.

    Any metric that is undefined for the input (e.g. profit factor
    with no losing trades, Sharpe with a single trade) is reported
    as ``None`` rather than a sentinel. Callers should render
    ``None`` as ``"n/a"`` or similar in UIs.

    Attributes:
        total_trades: Total number of closed trades.
        wins: Trades with positive net P&L.
        losses: Trades with negative net P&L.
        breakevens: Trades with zero net P&L.
        win_rate: wins / total_trades, 0 if no trades.
        initial_balance: Starting balance (from the run).
        final_balance: Ending balance.
        total_return: Final − initial.
        return_percent: total_return / initial × 100.
        annualized_return_percent: Return scaled to 365 days, or
            None if the run spans under a day.
        max_drawdown: Largest absolute peak-to-trough equity drop.
        max_drawdown_percent: ``max_drawdown`` as % of the peak
            equity at the time of the drop.
        sharpe_ratio: mean(trade returns) / std(trade returns).
            Per-trade; unannualized unless ``trades_per_year`` was
            supplied at analysis time.
        profit_factor: gross_profit / |gross_loss|, None if no losses.
        expectancy: (win_rate × avg_win) + (loss_rate × avg_loss).
            Expected P&L per trade (same units as P&L).
        avg_win: Mean P&L of winning trades (0 if no wins).
        avg_loss: Mean P&L of losing trades (0 if no losses), always ≤ 0.
        largest_win: Biggest single winner (0 if no wins).
        largest_loss: Biggest single loser (0 if no losses), always ≤ 0.
        total_fees: Sum of entry + exit fees across all trades.
        gross_profit: Sum of positive-P&L trade pnls.
        gross_loss: Sum of negative-P&L trade pnls (≤ 0).
    """

    # Trade counts
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    win_rate: float = 0.0

    # Returns
    initial_balance: Decimal = Decimal("0")
    final_balance: Decimal = Decimal("0")
    total_return: Decimal = Decimal("0")
    return_percent: float = 0.0
    annualized_return_percent: float | None = None

    # Risk
    max_drawdown: Decimal = Decimal("0")
    max_drawdown_percent: float = 0.0
    sharpe_ratio: float | None = None

    # P&L shape
    profit_factor: float | None = None
    expectancy: Decimal = Decimal("0")
    avg_win: Decimal = Decimal("0")
    avg_loss: Decimal = Decimal("0")
    largest_win: Decimal = Decimal("0")
    largest_loss: Decimal = Decimal("0")
    gross_profit: Decimal = Decimal("0")
    gross_loss: Decimal = Decimal("0")

    # Costs
    total_fees: Decimal = Decimal("0")

    model_config = {"validate_assignment": True}


class PerformanceAnalyzer:
    """Computes metrics and markdown reports from a ``BacktestResult``.

    The analyzer is stateless; a fresh instance can be reused across
    runs, or a new one can be constructed per call — both are cheap.
    """

    def analyze(
        self,
        result: BacktestResult,
        trades_per_year: int | None = None,
    ) -> PerformanceMetrics:
        """Compute ``PerformanceMetrics`` from a backtest result.

        Args:
            result: The backtest to analyze.
            trades_per_year: Optional annualization factor for the
                Sharpe ratio. If provided, Sharpe is multiplied by
                sqrt(trades_per_year); if None, Sharpe is per-trade.

        Returns:
            Populated ``PerformanceMetrics``.
        """
        trades = result.trades

        if not trades:
            return PerformanceMetrics(
                initial_balance=result.initial_balance,
                final_balance=result.final_balance,
                total_return=result.final_balance - result.initial_balance,
                return_percent=self._safe_return_percent(
                    result.initial_balance, result.final_balance
                ),
                annualized_return_percent=self._annualize(
                    result.initial_balance, result.final_balance, result
                ),
                total_fees=result.total_fees,
            )

        winners = [t for t in trades if t.pnl > 0]
        losers = [t for t in trades if t.pnl < 0]
        breakevens = [t for t in trades if t.pnl == 0]

        gross_profit = sum((t.pnl for t in winners), Decimal("0"))
        gross_loss = sum((t.pnl for t in losers), Decimal("0"))

        avg_win = (
            gross_profit / Decimal(len(winners)) if winners else Decimal("0")
        )
        avg_loss = (
            gross_loss / Decimal(len(losers)) if losers else Decimal("0")
        )
        largest_win = max((t.pnl for t in winners), default=Decimal("0"))
        largest_loss = min((t.pnl for t in losers), default=Decimal("0"))

        win_rate = len(winners) / len(trades)
        loss_rate = len(losers) / len(trades)
        expectancy = Decimal(str(win_rate)) * avg_win + Decimal(
            str(loss_rate)
        ) * avg_loss

        profit_factor = self._profit_factor(gross_profit, gross_loss)
        max_dd, max_dd_pct = self._max_drawdown(trades, result.initial_balance)
        sharpe = self._sharpe(trades, result.initial_balance, trades_per_year)

        return PerformanceMetrics(
            total_trades=len(trades),
            wins=len(winners),
            losses=len(losers),
            breakevens=len(breakevens),
            win_rate=win_rate,
            initial_balance=result.initial_balance,
            final_balance=result.final_balance,
            total_return=result.final_balance - result.initial_balance,
            return_percent=self._safe_return_percent(
                result.initial_balance, result.final_balance
            ),
            annualized_return_percent=self._annualize(
                result.initial_balance, result.final_balance, result
            ),
            max_drawdown=max_dd,
            max_drawdown_percent=max_dd_pct,
            sharpe_ratio=sharpe,
            profit_factor=profit_factor,
            expectancy=expectancy,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            total_fees=result.total_fees,
        )

    # ------------------------------------------------------------------
    # Metric helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_return_percent(
        initial: Decimal, final: Decimal
    ) -> float:
        """Compute return % guarding against zero initial balance."""
        if initial <= 0:
            return 0.0
        return float((final - initial) / initial * 100)

    @staticmethod
    def _annualize(
        initial: Decimal, final: Decimal, result: BacktestResult
    ) -> float | None:
        """Annualize a total return by (365 / days) compounding.

        Returns None if the run spans under a day (not meaningful) or
        if initial is non-positive.
        """
        if initial <= 0:
            return None
        days = (result.end_time - result.start_time).total_seconds() / 86400
        if days < 1:
            return None
        growth = float(final / initial)
        if growth <= 0:
            # Ruined account; annualization is meaningless.
            return -100.0
        return (growth ** (DAYS_PER_YEAR / days) - 1) * 100

    @staticmethod
    def _profit_factor(
        gross_profit: Decimal, gross_loss: Decimal
    ) -> float | None:
        """Profit factor = gross_profit / |gross_loss|.

        Returns None when there are no losses (undefined ratio).
        """
        if gross_loss == 0:
            return None
        return float(gross_profit / abs(gross_loss))

    @staticmethod
    def _max_drawdown(
        trades: list[BacktestTrade], initial: Decimal
    ) -> tuple[Decimal, float]:
        """Walk the equity curve and find the largest peak-to-trough drop.

        Returns (absolute_drawdown, drawdown_percent_of_peak).
        """
        equity = initial
        peak = initial
        max_dd_abs = Decimal("0")
        max_dd_peak = initial

        # Trades are appended in exit-order by the engine; sort just in
        # case callers pass a reordered list.
        ordered = sorted(trades, key=lambda t: t.exit_time)
        for trade in ordered:
            equity = equity + trade.pnl
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_dd_abs:
                max_dd_abs = drawdown
                max_dd_peak = peak

        if max_dd_peak <= 0:
            return max_dd_abs, 0.0
        return max_dd_abs, float(max_dd_abs / max_dd_peak * 100)

    @staticmethod
    def _sharpe(
        trades: list[BacktestTrade],
        initial: Decimal,
        trades_per_year: int | None,
    ) -> float | None:
        """Compute per-trade Sharpe.

        Per-trade return = pnl_i / equity_before_i, where
        equity_before_i is the running balance just before the trade
        closed (we approximate that as the running equity at that
        point in the equity walk).

        With fewer than 2 trades, std is undefined and the function
        returns None.
        """
        if len(trades) < 2 or initial <= 0:
            return None

        ordered = sorted(trades, key=lambda t: t.exit_time)

        returns: list[float] = []
        equity = initial
        for trade in ordered:
            if equity <= 0:
                # Blown account; stop contributing — subsequent
                # "returns" are not meaningful.
                break
            returns.append(float(trade.pnl / equity))
            equity = equity + trade.pnl

        if len(returns) < 2:
            return None

        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std_r = math.sqrt(variance)
        if std_r == 0:
            return None

        sharpe = mean_r / std_r
        if trades_per_year is not None and trades_per_year > 0:
            sharpe *= math.sqrt(trades_per_year)
        return sharpe

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def generate_report(
        self,
        result: BacktestResult,
        metrics: PerformanceMetrics | None = None,
    ) -> str:
        """Produce a markdown report summarizing a run.

        Args:
            result: The backtest result to describe.
            metrics: Optional pre-computed metrics. If None, computed
                via :meth:`analyze`.

        Returns:
            Markdown-formatted report as a single string.
        """
        metrics = metrics or self.analyze(result)

        days_span = (result.end_time - result.start_time).total_seconds() / 86400
        profile_line = (
            f"- **Profile**: {result.profile_name}\n"
            if result.profile_name
            else "- **Profile**: _none_\n"
        )

        annualized_str = (
            f"{metrics.annualized_return_percent:+.2f}%"
            if metrics.annualized_return_percent is not None
            else "n/a (run < 1 day)"
        )
        sharpe_str = (
            f"{metrics.sharpe_ratio:.3f}"
            if metrics.sharpe_ratio is not None
            else "n/a"
        )
        profit_factor_str = (
            f"{metrics.profit_factor:.2f}"
            if metrics.profit_factor is not None
            else "∞ (no losses)"
            if metrics.wins > 0 or metrics.breakevens > 0
            else "n/a"
        )

        currency = "USDT"  # Result doesn't carry quote currency yet

        lines = [
            f"# Backtest Report: {result.technique_name} v{result.technique_version}",
            "",
            "## Summary",
            f"- **Run ID**: `{result.run_id}`",
            f"- **Symbol**: {result.symbol}",
            f"- **Timeframe**: {result.timeframe}",
            f"- **Period**: {result.start_time.isoformat()} → "
            f"{result.end_time.isoformat()} ({days_span:.1f} days)",
            profile_line.rstrip(),
            "",
            "## Returns",
            f"- **Initial Balance**: {metrics.initial_balance} {currency}",
            f"- **Final Balance**: {metrics.final_balance} {currency}",
            f"- **Total Return**: {metrics.total_return:+} {currency} "
            f"({metrics.return_percent:+.2f}%)",
            f"- **Annualized Return**: {annualized_str}",
            "",
            "## Risk",
            f"- **Max Drawdown**: {metrics.max_drawdown} {currency} "
            f"({metrics.max_drawdown_percent:.2f}%)",
            f"- **Sharpe Ratio (per-trade)**: {sharpe_str}",
            "",
            "## Trades",
            f"- **Total**: {metrics.total_trades}",
            f"- **Wins / Losses / Breakevens**: "
            f"{metrics.wins} / {metrics.losses} / {metrics.breakevens}",
            f"- **Win Rate**: {metrics.win_rate * 100:.2f}%",
            f"- **Profit Factor**: {profit_factor_str}",
            f"- **Expectancy**: {metrics.expectancy:+} {currency} / trade",
            f"- **Avg Win / Avg Loss**: "
            f"{metrics.avg_win:+} / {metrics.avg_loss:+} {currency}",
            f"- **Largest Win / Largest Loss**: "
            f"{metrics.largest_win:+} / {metrics.largest_loss:+} {currency}",
            "",
            "## Costs",
            f"- **Total Fees**: {metrics.total_fees} {currency}",
            f"- **Gross Profit**: {metrics.gross_profit} {currency}",
            f"- **Gross Loss**: {metrics.gross_loss} {currency}",
            "",
        ]
        return "\n".join(lines)

    def save_report(
        self,
        result: BacktestResult,
        report_dir: Path,
        metrics: PerformanceMetrics | None = None,
    ) -> Path:
        """Write a markdown report to disk beside the backtest result.

        Args:
            result: The backtest result.
            report_dir: Directory to write into. Created if missing.
                Typical caller: ``backtester.data_dir / result.run_id``.
            metrics: Optional pre-computed metrics.

        Returns:
            Path to the written ``report.md``.
        """
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / "report.md"
        text = self.generate_report(result, metrics=metrics)
        path.write_text(text, encoding="utf-8")
        logger.info(f"Saved backtest report for {result.run_id} to {path}")
        return path

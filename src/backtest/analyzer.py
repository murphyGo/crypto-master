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

from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from src.backtest.engine import BacktestResult, BacktestTrade, EquityPoint
from src.backtest.metrics import (
    count_trade_outcomes,
    return_percent,
    sharpe_from_returns,
)
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

        outcomes = count_trade_outcomes(t.pnl for t in trades)
        winners = [t for t in trades if t.pnl > 0]
        losers = [t for t in trades if t.pnl < 0]

        gross_profit = sum((t.pnl for t in winners), Decimal("0"))
        gross_loss = sum((t.pnl for t in losers), Decimal("0"))

        avg_win = gross_profit / Decimal(len(winners)) if winners else Decimal("0")
        avg_loss = gross_loss / Decimal(len(losers)) if losers else Decimal("0")
        largest_win = max((t.pnl for t in winners), default=Decimal("0"))
        largest_loss = min((t.pnl for t in losers), default=Decimal("0"))

        expectancy = (
            Decimal(str(outcomes.win_rate)) * avg_win
            + Decimal(str(outcomes.loss_rate)) * avg_loss
        )

        profit_factor = self._profit_factor(gross_profit, gross_loss)
        # Phase 24.1 / DEBT-030: prefer the per-bar mark-to-market
        # equity curve when the engine populated it. Closed-trade-only
        # walks miss every drawdown that occurs while a trade is open
        # and recovers before exit.
        max_dd, max_dd_pct = self._max_drawdown(
            trades, result.initial_balance, result.equity_curve
        )
        sharpe = self._sharpe(
            trades,
            result.initial_balance,
            trades_per_year,
            result.equity_curve,
        )

        return PerformanceMetrics(
            total_trades=len(trades),
            wins=outcomes.wins,
            losses=outcomes.losses,
            breakevens=outcomes.breakevens,
            win_rate=outcomes.win_rate,
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
    def _safe_return_percent(initial: Decimal, final: Decimal) -> float:
        """Compute return % guarding against zero initial balance."""
        return return_percent(initial, final)

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
        return float((growth ** (DAYS_PER_YEAR / days) - 1) * 100)

    @staticmethod
    def _profit_factor(gross_profit: Decimal, gross_loss: Decimal) -> float | None:
        """Profit factor = gross_profit / |gross_loss|.

        Returns None when there are no losses (undefined ratio).
        """
        if gross_loss == 0:
            return None
        return float(gross_profit / abs(gross_loss))

    @staticmethod
    def _max_drawdown(
        trades: list[BacktestTrade],
        initial: Decimal,
        equity_curve: list[EquityPoint] | None = None,
    ) -> tuple[Decimal, float]:
        """Walk the equity curve and find the largest peak-to-trough drop.

        Phase 24.1 / DEBT-030: when the per-bar mark-to-market
        ``equity_curve`` is supplied (populated by
        :meth:`Backtester.run` and ``run_multi_timeframe``), the walk
        uses bar equity so intra-trade drawdowns are captured. The
        legacy closed-trade walk is preserved as a fallback for
        ``BacktestResult`` instances built directly in tests / older
        persisted runs.

        Returns (absolute_drawdown, drawdown_percent_of_peak).
        """
        if equity_curve:
            return PerformanceAnalyzer._max_drawdown_from_equity_curve(
                equity_curve, initial
            )

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
    def _max_drawdown_from_equity_curve(
        curve: list[EquityPoint], initial: Decimal
    ) -> tuple[Decimal, float]:
        """Phase 24.1 / DEBT-030: peak-to-trough drop over per-bar equity."""
        peak = initial
        max_dd_abs = Decimal("0")
        max_dd_peak = initial
        for point in curve:
            equity = point.equity
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
        equity_curve: list[EquityPoint] | None = None,
    ) -> float | None:
        """Compute Sharpe ratio.

        Phase 24.1 / DEBT-030: when the per-bar mark-to-market
        ``equity_curve`` is supplied, Sharpe is computed from bar
        returns (``equity[i] / equity[i-1] - 1``). Bar returns reflect
        intra-trade volatility — the closed-trade-return surface
        flatters strategies whose trades are individually small but
        whose intra-trade swings are large, and that mismatch is what
        DEBT-030 closes.

        The legacy closed-trade-return path is preserved as a fallback
        for ``BacktestResult`` instances without an equity curve.

        With fewer than 2 return samples, std is undefined and the
        function returns None.

        Phase 24.2 fix (DEBT-030): on the bar-equity-curve path, the
        annualization factor is derived from the candle cadence (median
        Δt between successive ``EquityPoint`` timestamps), not the
        caller-supplied ``trades_per_year``. Bar-granularity returns
        scale by ``√bars_per_year`` (e.g. ~√8760 on hourly cadence);
        multiplying them by ``√trades_per_year=√252`` would silently
        inflate Sharpe by ~5.9× on hourly bars. The closed-trade
        fallback path keeps ``trades_per_year`` as before.
        """
        if equity_curve and len(equity_curve) >= 2:
            return PerformanceAnalyzer._sharpe_from_equity_curve(equity_curve)

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

        return sharpe_from_returns(returns, trades_per_year)

    @staticmethod
    def _sharpe_from_equity_curve(
        curve: list[EquityPoint],
    ) -> float | None:
        """Phase 24.1 / DEBT-030: Sharpe over per-bar returns.

        Phase 24.2 fix: the annualization factor is derived from the
        candle cadence rather than ``trades_per_year``. Without this
        guard, hourly bars annualized at ``√252`` (the
        ``trades_per_year`` default consumers pass for the closed-trade
        path) inflate Sharpe by ``√(8760/252) ≈ 5.9×`` because bar
        returns are sampled ``8760`` times per year, not ``252``.

        Cadence is the **median** Δt between successive equity points
        (robust to a single missing or duplicated bar). When the curve
        has fewer than two distinct timestamps, or the median cadence
        is non-positive, annualization is skipped and the raw per-bar
        Sharpe is returned.
        """
        returns: list[float] = []
        prev = curve[0].equity
        for point in curve[1:]:
            if prev <= 0:
                # Blown account; downstream "returns" are not meaningful.
                break
            returns.append(float((point.equity - prev) / prev))
            prev = point.equity

        bars_per_year = PerformanceAnalyzer._bars_per_year(curve)
        return sharpe_from_returns(returns, bars_per_year)

    @staticmethod
    def _bars_per_year(curve: list[EquityPoint]) -> int | None:
        """Phase 24.2 / DEBT-030 fix: derive annualization from cadence.

        Returns ``int(round((365 * 24 * 3600) / median_dt_seconds))`` or
        ``None`` when the cadence is undefined (fewer than two points,
        non-positive median Δt). The integer round-trip lines up with
        ``_sharpe_from_returns``'s ``int | None`` contract; the
        precision loss from rounding is negligible against ``√(N)``
        scaling.
        """
        if len(curve) < 2:
            return None
        deltas: list[float] = []
        for i in range(1, len(curve)):
            dt = (curve[i].timestamp - curve[i - 1].timestamp).total_seconds()
            if dt > 0:
                deltas.append(dt)
        if not deltas:
            return None
        deltas.sort()
        mid = len(deltas) // 2
        if len(deltas) % 2 == 1:
            median_dt = deltas[mid]
        else:
            median_dt = (deltas[mid - 1] + deltas[mid]) / 2
        if median_dt <= 0:
            return None
        seconds_per_year = 365 * 24 * 3600
        return int(round(seconds_per_year / median_dt))

    @staticmethod
    def _sharpe_from_returns(
        returns: list[float], trades_per_year: int | None
    ) -> float | None:
        """Common tail: mean / std with optional sqrt(N) annualization."""
        return sharpe_from_returns(returns, trades_per_year)

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
            f"{metrics.sharpe_ratio:.3f}" if metrics.sharpe_ratio is not None else "n/a"
        )
        profit_factor_str = (
            f"{metrics.profit_factor:.2f}"
            if metrics.profit_factor is not None
            else (
                "∞ (no losses)" if metrics.wins > 0 or metrics.breakevens > 0 else "n/a"
            )
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

"""Tests for the PerformanceAnalyzer."""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.backtest.analyzer import PerformanceAnalyzer, PerformanceMetrics
from src.backtest.engine import BacktestResult, BacktestTrade

# =============================================================================
# Builders
# =============================================================================


def _make_trade(
    pnl: str,
    *,
    entry_time: datetime | None = None,
    exit_time: datetime | None = None,
    side: str = "long",
    entry_fee: str = "0",
    exit_fee: str = "0",
    entry: str = "50000",
    exit_: str = "50500",
    close_reason: str = "take_profit",
    trade_id: str = "bt-test",
) -> BacktestTrade:
    """Build a BacktestTrade with sensible defaults, parameterized on pnl."""
    t0 = entry_time or datetime(2026, 1, 1, 12, 0, 0)
    t1 = exit_time or datetime(2026, 1, 1, 13, 0, 0)
    return BacktestTrade(
        trade_id=trade_id,
        symbol="BTC/USDT",
        side=side,  # type: ignore[arg-type]
        entry_time=t0,
        exit_time=t1,
        entry_price=Decimal(entry),
        exit_price=Decimal(exit_),
        quantity=Decimal("0.1"),
        leverage=1,
        stop_loss=Decimal("49000"),
        take_profit=Decimal("51000"),
        entry_fee=Decimal(entry_fee),
        exit_fee=Decimal(exit_fee),
        pnl=Decimal(pnl),
        close_reason=close_reason,  # type: ignore[arg-type]
    )


def _make_result(
    trades: list[BacktestTrade],
    *,
    initial: str = "10000",
    final: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    technique: str = "test",
    version: str = "1.0.0",
    profile: str | None = None,
) -> BacktestResult:
    """Build a BacktestResult that's internally consistent with trades."""
    initial_dec = Decimal(initial)
    total_pnl = sum((t.pnl for t in trades), Decimal("0"))
    total_fees = sum((t.entry_fee + t.exit_fee for t in trades), Decimal("0"))
    final_dec = Decimal(final) if final is not None else initial_dec + total_pnl

    wins = sum(1 for t in trades if t.pnl > 0)
    losses = sum(1 for t in trades if t.pnl < 0)
    breakevens = sum(1 for t in trades if t.pnl == 0)
    win_rate = wins / len(trades) if trades else 0.0
    return_pct = (
        float((final_dec - initial_dec) / initial_dec * 100) if initial_dec > 0 else 0.0
    )

    return BacktestResult(
        run_id="bt-run-1",
        technique_name=technique,
        technique_version=version,
        profile_name=profile,
        symbol="BTC/USDT",
        timeframe="1h",
        start_time=start or datetime(2026, 1, 1, 0, 0, 0),
        end_time=end or datetime(2026, 1, 31, 0, 0, 0),
        initial_balance=initial_dec,
        final_balance=final_dec,
        total_trades=len(trades),
        wins=wins,
        losses=losses,
        breakevens=breakevens,
        total_pnl=total_pnl,
        total_fees=total_fees,
        win_rate=win_rate,
        return_percent=return_pct,
        trades=trades,
    )


@pytest.fixture
def analyzer() -> PerformanceAnalyzer:
    return PerformanceAnalyzer()


# =============================================================================
# Zero trades
# =============================================================================


class TestNoTrades:
    """Analyzer handles an empty result gracefully."""

    def test_empty_result(self, analyzer: PerformanceAnalyzer) -> None:
        result = _make_result([])
        metrics = analyzer.analyze(result)

        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.total_trades == 0
        assert metrics.wins == 0
        assert metrics.losses == 0
        assert metrics.win_rate == 0.0
        assert metrics.total_return == Decimal("0")
        assert metrics.return_percent == 0.0
        assert metrics.max_drawdown == Decimal("0")
        assert metrics.sharpe_ratio is None
        assert metrics.profit_factor is None


# =============================================================================
# Trade counts and win rate
# =============================================================================


class TestTradeCounts:
    """Win / loss / breakeven counts and win rate."""

    def test_mixed_trades_counts(self, analyzer: PerformanceAnalyzer) -> None:
        trades = [
            _make_trade("100"),
            _make_trade("-50"),
            _make_trade("0", close_reason="stop_loss"),
            _make_trade("200"),
        ]
        result = _make_result(trades)
        metrics = analyzer.analyze(result)

        assert metrics.total_trades == 4
        assert metrics.wins == 2
        assert metrics.losses == 1
        assert metrics.breakevens == 1
        assert metrics.win_rate == 0.5

    def test_all_winners(self, analyzer: PerformanceAnalyzer) -> None:
        trades = [_make_trade("100"), _make_trade("200")]
        metrics = analyzer.analyze(_make_result(trades))
        assert metrics.wins == 2
        assert metrics.losses == 0
        assert metrics.win_rate == 1.0
        # No losses → profit factor undefined
        assert metrics.profit_factor is None

    def test_all_losers(self, analyzer: PerformanceAnalyzer) -> None:
        trades = [_make_trade("-50"), _make_trade("-75")]
        metrics = analyzer.analyze(_make_result(trades))
        assert metrics.losses == 2
        assert metrics.win_rate == 0.0
        assert metrics.profit_factor == 0.0  # gross_profit / |gross_loss|


# =============================================================================
# Averages and extremes
# =============================================================================


class TestAveragesAndExtremes:
    """Avg win/loss and largest win/loss."""

    def test_avg_and_largest(self, analyzer: PerformanceAnalyzer) -> None:
        trades = [
            _make_trade("100"),
            _make_trade("300"),
            _make_trade("-50"),
            _make_trade("-150"),
        ]
        metrics = analyzer.analyze(_make_result(trades))
        assert metrics.avg_win == Decimal("200")  # (100+300)/2
        assert metrics.avg_loss == Decimal("-100")  # (-50-150)/2
        assert metrics.largest_win == Decimal("300")
        assert metrics.largest_loss == Decimal("-150")
        assert metrics.gross_profit == Decimal("400")
        assert metrics.gross_loss == Decimal("-200")

    def test_no_wins_yields_zero_avg_win(self, analyzer: PerformanceAnalyzer) -> None:
        trades = [_make_trade("-50")]
        metrics = analyzer.analyze(_make_result(trades))
        assert metrics.avg_win == Decimal("0")
        assert metrics.largest_win == Decimal("0")


# =============================================================================
# Profit factor
# =============================================================================


class TestProfitFactor:
    def test_normal(self, analyzer: PerformanceAnalyzer) -> None:
        # PF = 400 / 200 = 2.0
        trades = [
            _make_trade("100"),
            _make_trade("300"),
            _make_trade("-50"),
            _make_trade("-150"),
        ]
        metrics = analyzer.analyze(_make_result(trades))
        assert metrics.profit_factor == 2.0

    def test_no_losses_returns_none(self, analyzer: PerformanceAnalyzer) -> None:
        metrics = analyzer.analyze(
            _make_result([_make_trade("100"), _make_trade("200")])
        )
        assert metrics.profit_factor is None


# =============================================================================
# Returns
# =============================================================================


class TestReturns:
    def test_return_percent(self, analyzer: PerformanceAnalyzer) -> None:
        # 10000 -> 11000 = +10%
        trades = [_make_trade("1000")]
        metrics = analyzer.analyze(_make_result(trades))
        assert metrics.total_return == Decimal("1000")
        assert metrics.return_percent == pytest.approx(10.0)

    def test_annualized_return_30_days(self, analyzer: PerformanceAnalyzer) -> None:
        """30-day run with 10% return annualizes via compounding."""
        trades = [_make_trade("1000")]
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        metrics = analyzer.analyze(_make_result(trades, start=start, end=end))
        assert metrics.annualized_return_percent is not None
        # (1.1)^(365/30) - 1 ≈ 2.188 → ~218.87%
        assert metrics.annualized_return_percent == pytest.approx(218.87, rel=0.01)

    def test_annualized_none_for_short_run(self, analyzer: PerformanceAnalyzer) -> None:
        """< 1 day span → annualization is not meaningful."""
        trades = [_make_trade("100")]
        start = datetime(2026, 1, 1, 0, 0, 0)
        end = datetime(2026, 1, 1, 6, 0, 0)
        metrics = analyzer.analyze(_make_result(trades, start=start, end=end))
        assert metrics.annualized_return_percent is None


# =============================================================================
# Max drawdown
# =============================================================================


class TestMaxDrawdown:
    def test_linear_profit_no_drawdown(self, analyzer: PerformanceAnalyzer) -> None:
        trades = [
            _make_trade("100"),
            _make_trade("100"),
            _make_trade("100"),
        ]
        metrics = analyzer.analyze(_make_result(trades))
        assert metrics.max_drawdown == Decimal("0")
        assert metrics.max_drawdown_percent == 0.0

    def test_drawdown_from_peak(self, analyzer: PerformanceAnalyzer) -> None:
        """Equity: 10000 → 10500 → 10100 → 10300. MDD = 400."""
        t0 = datetime(2026, 1, 1)
        trades = [
            _make_trade(
                "500",
                entry_time=t0,
                exit_time=t0 + timedelta(hours=1),
            ),
            _make_trade(
                "-400",
                entry_time=t0 + timedelta(hours=2),
                exit_time=t0 + timedelta(hours=3),
                close_reason="stop_loss",
            ),
            _make_trade(
                "200",
                entry_time=t0 + timedelta(hours=4),
                exit_time=t0 + timedelta(hours=5),
            ),
        ]
        metrics = analyzer.analyze(_make_result(trades))
        # Peak = 10500; trough after 2nd trade = 10100; DD = 400
        assert metrics.max_drawdown == Decimal("400")
        # MDD % = 400 / 10500 ≈ 3.81%
        assert metrics.max_drawdown_percent == pytest.approx(3.81, rel=0.01)

    def test_drawdown_requires_peak_above_initial(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        """If you only lose, MDD peak = initial balance."""
        trades = [_make_trade("-100"), _make_trade("-200")]
        metrics = analyzer.analyze(_make_result(trades))
        # Peak never exceeds initial 10000; max DD = 300
        assert metrics.max_drawdown == Decimal("300")
        assert metrics.max_drawdown_percent == pytest.approx(3.0, rel=0.01)

    def test_drawdown_orders_by_exit_time(self, analyzer: PerformanceAnalyzer) -> None:
        """MDD walk sorts by exit_time regardless of input order."""
        t0 = datetime(2026, 1, 1)
        # Same trades as test_drawdown_from_peak but passed reversed
        trades = [
            _make_trade(
                "200",
                entry_time=t0 + timedelta(hours=4),
                exit_time=t0 + timedelta(hours=5),
            ),
            _make_trade(
                "-400",
                entry_time=t0 + timedelta(hours=2),
                exit_time=t0 + timedelta(hours=3),
            ),
            _make_trade(
                "500",
                entry_time=t0,
                exit_time=t0 + timedelta(hours=1),
            ),
        ]
        metrics = analyzer.analyze(_make_result(trades))
        assert metrics.max_drawdown == Decimal("400")


# =============================================================================
# Sharpe
# =============================================================================


class TestSharpe:
    def test_sharpe_with_zero_returns_is_none(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        """All-zero returns (breakeven trades) → std = 0 → Sharpe undefined."""
        trades = [
            _make_trade("0", close_reason="stop_loss"),
            _make_trade("0", close_reason="stop_loss"),
            _make_trade("0", close_reason="stop_loss"),
        ]
        metrics = analyzer.analyze(_make_result(trades))
        assert metrics.sharpe_ratio is None

    def test_single_trade_yields_none(self, analyzer: PerformanceAnalyzer) -> None:
        metrics = analyzer.analyze(_make_result([_make_trade("100")]))
        assert metrics.sharpe_ratio is None

    def test_sharpe_positive_when_avg_return_positive(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        trades = [
            _make_trade("200"),
            _make_trade("-50"),
            _make_trade("150"),
            _make_trade("100"),
        ]
        metrics = analyzer.analyze(_make_result(trades))
        assert metrics.sharpe_ratio is not None
        assert metrics.sharpe_ratio > 0

    def test_sharpe_annualization_scales_by_sqrt(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        """Passing trades_per_year scales Sharpe by sqrt(n)."""
        trades = [
            _make_trade("200"),
            _make_trade("-50"),
            _make_trade("150"),
            _make_trade("100"),
        ]
        result = _make_result(trades)
        raw = analyzer.analyze(result).sharpe_ratio
        scaled = analyzer.analyze(result, trades_per_year=100).sharpe_ratio
        assert raw is not None and scaled is not None
        # scaled ≈ raw * sqrt(100) = raw * 10
        assert scaled == pytest.approx(raw * 10, rel=0.001)


# =============================================================================
# Expectancy
# =============================================================================


class TestExpectancy:
    def test_expectancy_formula(self, analyzer: PerformanceAnalyzer) -> None:
        # 2 winners avg 200, 2 losers avg -100. WR=0.5, LR=0.5.
        # Expectancy = 0.5 * 200 + 0.5 * -100 = 50
        trades = [
            _make_trade("100"),
            _make_trade("300"),
            _make_trade("-50"),
            _make_trade("-150"),
        ]
        metrics = analyzer.analyze(_make_result(trades))
        assert metrics.expectancy == Decimal("50")


# =============================================================================
# Fees
# =============================================================================


class TestFees:
    def test_total_fees_summed(self, analyzer: PerformanceAnalyzer) -> None:
        trades = [
            _make_trade("100", entry_fee="1.5", exit_fee="1.5"),
            _make_trade("-50", entry_fee="2", exit_fee="2"),
        ]
        metrics = analyzer.analyze(_make_result(trades))
        assert metrics.total_fees == Decimal("7")


# =============================================================================
# Markdown report
# =============================================================================


class TestReport:
    def test_generate_report_contains_sections(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        trades = [_make_trade("500"), _make_trade("-100")]
        report = analyzer.generate_report(_make_result(trades))
        assert "# Backtest Report:" in report
        assert "## Summary" in report
        assert "## Returns" in report
        assert "## Risk" in report
        assert "## Trades" in report
        assert "## Costs" in report
        assert "Win Rate" in report

    def test_report_references_profile_when_set(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        report = analyzer.generate_report(
            _make_result([_make_trade("100")], profile="moderate")
        )
        assert "moderate" in report

    def test_report_marks_none_profile(self, analyzer: PerformanceAnalyzer) -> None:
        report = analyzer.generate_report(_make_result([_make_trade("100")]))
        assert "_none_" in report

    def test_report_handles_zero_trades(self, analyzer: PerformanceAnalyzer) -> None:
        report = analyzer.generate_report(_make_result([]))
        assert "**Total**: 0" in report
        # Sharpe n/a in the trades section header
        assert "n/a" in report

    def test_save_report_writes_file(
        self, analyzer: PerformanceAnalyzer, tmp_path: Path
    ) -> None:
        result = _make_result([_make_trade("100")])
        path = analyzer.save_report(result, tmp_path / "run-a")
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Backtest Report" in content
        assert path.name == "report.md"


# =============================================================================
# Phase 24.1 / DEBT-030: per-bar (intra-trade) MDD + Sharpe
# =============================================================================


class TestEquityCurveMaxDrawdown:
    """When the per-bar equity curve is populated, MDD reflects intra-trade
    drawdowns the closed-trade walk would miss."""

    def test_intra_trade_mdd_strictly_below_closed_trade_mdd(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        """Long trade goes deep underwater mid-flight, then recovers to a
        small loss at exit. Closed-trade MDD = abs(small loss); per-bar
        MDD ≥ deep mid-trade drawdown.
        """
        from src.backtest.engine import EquityPoint

        t0 = datetime(2026, 1, 1, 12, 0, 0)
        # Trade entered at t0, exited at t0+5h with pnl=-50 (small loss).
        trade = _make_trade(
            "-50",
            entry_time=t0,
            exit_time=t0 + timedelta(hours=5),
            close_reason="end_of_data",
        )

        # Per-bar equity (initial 10000):
        #   10000 → 9990 → 9500 → 9200 → 9700 → 9950
        # mid-trade drawdown = 10000 - 9200 = 800, recovered to -50 at exit.
        equity_curve = [
            EquityPoint(timestamp=t0, equity=Decimal("10000")),
            EquityPoint(timestamp=t0 + timedelta(hours=1), equity=Decimal("9990")),
            EquityPoint(timestamp=t0 + timedelta(hours=2), equity=Decimal("9500")),
            EquityPoint(timestamp=t0 + timedelta(hours=3), equity=Decimal("9200")),
            EquityPoint(timestamp=t0 + timedelta(hours=4), equity=Decimal("9700")),
            EquityPoint(timestamp=t0 + timedelta(hours=5), equity=Decimal("9950")),
        ]
        result = _make_result([trade])
        # Inject the curve (Phase 24.1 contract — the analyzer prefers
        # bar equity when present).
        result_with_curve = result.model_copy(update={"equity_curve": equity_curve})

        # Closed-trade-only MDD via the legacy path (no curve).
        closed_metrics = analyzer.analyze(result)
        # Per-bar MDD via the new path.
        bar_metrics = analyzer.analyze(result_with_curve)

        # Strict inequality is the regression invariant — bar MDD must
        # exceed closed-trade MDD whenever an intra-trade drawdown
        # exceeds the closed P&L.
        assert closed_metrics.max_drawdown == Decimal("50")
        assert bar_metrics.max_drawdown == Decimal("800")
        assert bar_metrics.max_drawdown > closed_metrics.max_drawdown

    def test_empty_equity_curve_falls_back_to_closed_trades(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        """No curve → closed-trade walk (legacy back-compat surface)."""
        trade = _make_trade("-50")
        result = _make_result([trade])
        assert result.equity_curve == []  # Default factory
        metrics = analyzer.analyze(result)
        # Closed-trade MDD on a single losing trade = abs(pnl).
        assert metrics.max_drawdown == Decimal("50")

    def test_sharpe_uses_bar_returns_when_curve_present(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        """With an equity curve, Sharpe is computed from per-bar returns."""
        from src.backtest.engine import EquityPoint

        t0 = datetime(2026, 1, 1, 12, 0, 0)
        trade = _make_trade(
            "100",
            entry_time=t0,
            exit_time=t0 + timedelta(hours=2),
        )
        curve = [
            EquityPoint(timestamp=t0, equity=Decimal("10000")),
            EquityPoint(timestamp=t0 + timedelta(hours=1), equity=Decimal("10050")),
            EquityPoint(timestamp=t0 + timedelta(hours=2), equity=Decimal("10100")),
        ]
        result = _make_result([trade]).model_copy(update={"equity_curve": curve})
        metrics = analyzer.analyze(result)
        # Two bar returns: +0.005, +0.00497..; std non-zero, mean > 0
        # → finite positive Sharpe.
        assert metrics.sharpe_ratio is not None
        assert metrics.sharpe_ratio > 0


class TestEquityCurveSharpeAnnualization:
    """Phase 24.2 fix (DEBT-030): bar-equity Sharpe annualization derives
    its factor from the candle cadence, not the caller-supplied
    ``trades_per_year``. Without this guard hourly bars would be
    annualized at ``√252`` (the closed-trade default) and Sharpe would
    silently scale ~5.9× larger than the bar-cadence-aware value.
    """

    def test_hourly_cadence_annualization_factor_matches_sqrt_8760(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        """Hourly cadence → bars_per_year ≈ 8760 → factor ≈ √8760 ≈ 93.6.

        Hand-computed scale: build an hourly equity curve with two
        bar returns (+0.01, -0.005). Per-bar mean = 0.0025, sample
        stdev ≈ 0.01060660; raw per-bar Sharpe ≈ 0.2357. Annualized
        Sharpe = raw × √8760 ≈ 22.07. The annualization factor is the
        load-bearing assertion; the absolute Sharpe is checked to
        ±5% to absorb tiny rounding in the cadence calculation.
        """
        from src.backtest.engine import EquityPoint

        t0 = datetime(2026, 1, 1, 12, 0, 0)
        # Hourly equity curve:
        #   r1 = (10100 - 10000)/10000 = +0.01
        #   r2 = (10049.5 - 10100)/10100 ≈ -0.005
        curve = [
            EquityPoint(timestamp=t0, equity=Decimal("10000")),
            EquityPoint(timestamp=t0 + timedelta(hours=1), equity=Decimal("10100")),
            EquityPoint(timestamp=t0 + timedelta(hours=2), equity=Decimal("10049.50")),
        ]
        # ``trade`` is required for ``_make_result`` to populate stats;
        # the analyzer only consumes ``equity_curve`` for Sharpe.
        trade = _make_trade(
            "49.50",
            entry_time=t0,
            exit_time=t0 + timedelta(hours=2),
        )
        result = _make_result([trade]).model_copy(update={"equity_curve": curve})

        # ``trades_per_year=252`` deliberately used as the *closed-
        # trade* convention; the equity-curve path must IGNORE it and
        # use the bar cadence instead. If the bug regresses, Sharpe
        # would scale by √252 ≈ 15.87 instead of √8760 ≈ 93.6.
        metrics = analyzer.analyze(result, trades_per_year=252)
        assert metrics.sharpe_ratio is not None

        # Hand-computed expected value:
        #   r = [0.01, -0.005]
        #   mean = 0.0025
        #   variance (sample) = ((0.01-0.0025)^2 + (-0.005-0.0025)^2) / 1
        #                     = 0.0001125
        #   std = sqrt(0.0001125) ≈ 0.01060660
        #   per-bar sharpe = 0.0025 / 0.01060660 ≈ 0.235702
        #   bars/year = 365*24 = 8760
        #   annualized = 0.235702 * sqrt(8760) ≈ 22.066
        expected = 0.235702 * (8760**0.5)
        assert metrics.sharpe_ratio == pytest.approx(expected, rel=0.01)

        # Defense-in-depth: the annualization factor itself.
        # bars_per_year is the public seam used by the analyzer.
        bars_per_year = PerformanceAnalyzer._bars_per_year(curve)
        assert bars_per_year == 8760

    def test_daily_cadence_annualization_factor_matches_sqrt_365(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        """Daily cadence → bars_per_year = 365 → factor ≈ √365 ≈ 19.1.

        Pinned regression for the cadence-detection logic on a
        timeframe other than hourly. The previous (broken) path would
        have used ``trades_per_year`` (often 252) on this curve, off
        by ~1.31× from the cadence-correct value.
        """
        from src.backtest.engine import EquityPoint

        t0 = datetime(2026, 1, 1)
        curve = [
            EquityPoint(timestamp=t0 + timedelta(days=i), equity=Decimal("10000"))
            for i in range(5)
        ]
        bars_per_year = PerformanceAnalyzer._bars_per_year(curve)
        assert bars_per_year == 365

    def test_bars_per_year_is_none_for_single_point_curve(self) -> None:
        """A degenerate one-point curve has no cadence; return None."""
        from src.backtest.engine import EquityPoint

        curve = [EquityPoint(timestamp=datetime(2026, 1, 1), equity=Decimal("10000"))]
        assert PerformanceAnalyzer._bars_per_year(curve) is None

    def test_bar_sharpe_ignores_caller_trades_per_year(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        """Bar-equity-curve path must NOT scale by ``trades_per_year``.

        Sanity: with the same equity curve, two analyses passing
        different ``trades_per_year`` values must produce identical
        Sharpe ratios — the bar-cadence-derived factor is the only
        scaler that applies.
        """
        from src.backtest.engine import EquityPoint

        t0 = datetime(2026, 1, 1, 12, 0, 0)
        curve = [
            EquityPoint(timestamp=t0, equity=Decimal("10000")),
            EquityPoint(timestamp=t0 + timedelta(hours=1), equity=Decimal("10100")),
            EquityPoint(timestamp=t0 + timedelta(hours=2), equity=Decimal("10049.50")),
        ]
        trade = _make_trade(
            "49.50",
            entry_time=t0,
            exit_time=t0 + timedelta(hours=2),
        )
        result = _make_result([trade]).model_copy(update={"equity_curve": curve})

        a = analyzer.analyze(result, trades_per_year=None).sharpe_ratio
        b = analyzer.analyze(result, trades_per_year=252).sharpe_ratio
        c = analyzer.analyze(result, trades_per_year=10_000).sharpe_ratio

        assert a is not None and b is not None and c is not None
        assert a == pytest.approx(b, rel=1e-9)
        assert b == pytest.approx(c, rel=1e-9)

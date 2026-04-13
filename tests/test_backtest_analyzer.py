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
    total_fees = sum(
        (t.entry_fee + t.exit_fee for t in trades), Decimal("0")
    )
    final_dec = Decimal(final) if final is not None else initial_dec + total_pnl

    wins = sum(1 for t in trades if t.pnl > 0)
    losses = sum(1 for t in trades if t.pnl < 0)
    breakevens = sum(1 for t in trades if t.pnl == 0)
    win_rate = wins / len(trades) if trades else 0.0
    return_pct = (
        float((final_dec - initial_dec) / initial_dec * 100)
        if initial_dec > 0
        else 0.0
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

    def test_mixed_trades_counts(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
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

    def test_no_wins_yields_zero_avg_win(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
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

    def test_no_losses_returns_none(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
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

    def test_annualized_return_30_days(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        """30-day run with 10% return annualizes via compounding."""
        trades = [_make_trade("1000")]
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        metrics = analyzer.analyze(_make_result(trades, start=start, end=end))
        assert metrics.annualized_return_percent is not None
        # (1.1)^(365/30) - 1 ≈ 2.188 → ~218.87%
        assert metrics.annualized_return_percent == pytest.approx(
            218.87, rel=0.01
        )

    def test_annualized_none_for_short_run(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
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
    def test_linear_profit_no_drawdown(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        trades = [
            _make_trade("100"),
            _make_trade("100"),
            _make_trade("100"),
        ]
        metrics = analyzer.analyze(_make_result(trades))
        assert metrics.max_drawdown == Decimal("0")
        assert metrics.max_drawdown_percent == 0.0

    def test_drawdown_from_peak(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
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

    def test_drawdown_orders_by_exit_time(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
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

    def test_single_trade_yields_none(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
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
    def test_expectancy_formula(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
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
    def test_total_fees_summed(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
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

    def test_report_marks_none_profile(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
        report = analyzer.generate_report(_make_result([_make_trade("100")]))
        assert "_none_" in report

    def test_report_handles_zero_trades(
        self, analyzer: PerformanceAnalyzer
    ) -> None:
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

"""Tests for the RobustnessGate validator."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

import pytest

from src.backtest.engine import BacktestConfig, Backtester
from src.backtest.validator import (
    GateStatus,
    RobustnessConfig,
    RobustnessGate,
    RobustnessReport,
    _classify_regimes,
    _sharpe_from_trades,
)
from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, TechniqueInfo

# =============================================================================
# Test doubles
# =============================================================================


def info(name: str = "test") -> TechniqueInfo:
    return TechniqueInfo(
        name=name,
        version="1.0.0",
        description="test technique",
        technique_type="code",
    )


def neutral() -> AnalysisResult:
    return AnalysisResult(
        signal="neutral",
        confidence=0.0,
        entry_price=Decimal("50000"),
        stop_loss=Decimal("49000"),
        take_profit=Decimal("51000"),
        reasoning="neutral",
    )


def long_signal(
    entry: str = "50000",
    sl: str = "49500",
    tp: str = "51000",
) -> AnalysisResult:
    return AnalysisResult(
        signal="long",
        confidence=0.8,
        entry_price=Decimal(entry),
        stop_loss=Decimal(sl),
        take_profit=Decimal(tp),
        reasoning="long",
    )


class PeriodicLongStrategy(BaseStrategy):
    """Fires a long every ``period`` candles. The fired ``signal`` is
    parameterized so callers can force wins/losses by choosing SL/TP
    that the candle stream will or will not hit.
    """

    def __init__(
        self,
        period: int = 5,
        signal: AnalysisResult | None = None,
        info_obj: TechniqueInfo | None = None,
    ) -> None:
        super().__init__(info=info_obj or info("periodic_long"))
        self.period = period
        self._signal = signal or long_signal()

    async def analyze(
        self, ohlcv: list[OHLCV], symbol: str, timeframe: str = "1h"
    ) -> AnalysisResult:
        idx = len(ohlcv) - 1
        # Fire only when current index is a multiple of the period and
        # we are past the warm-up region. Otherwise neutral.
        if idx > 0 and idx % self.period == 0:
            return self._signal
        return neutral()


def make_candles(
    count: int,
    *,
    pattern: Literal["winning", "losing", "rising", "falling", "flat"] = "flat",
    start: datetime | None = None,
    base_price: Decimal = Decimal("50000"),
) -> list[OHLCV]:
    """Build synthetic candles with controlled SL/TP behavior.

    ``winning``: every candle's high exceeds 51000 (TP for long_signal),
        and low stays above 49500 (no SL hit). Long signals always win.
    ``losing``: every candle's low drops below 49500 (SL hit), high
        below 51000 (no TP). Long signals always lose.
    ``rising``: linear price increase — useful for regime tests.
    ``falling``: linear price decrease.
    ``flat``: no movement.
    """
    if start is None:
        start = datetime(2026, 1, 1)
    candles: list[OHLCV] = []
    for i in range(count):
        ts = start + timedelta(hours=i)
        if pattern == "winning":
            o = base_price
            h = base_price + Decimal("2000")  # high enough for TP=51000
            low = base_price - Decimal("400")  # above SL=49500
            c = base_price
        elif pattern == "losing":
            o = base_price
            h = base_price + Decimal("400")  # below TP=51000
            low = base_price - Decimal("1000")  # below SL=49500
            c = base_price
        elif pattern == "rising":
            price = base_price + Decimal(i) * Decimal("100")
            o = h = low = c = price
            h = price + Decimal("100")
            low = price - Decimal("100")
        elif pattern == "falling":
            price = base_price - Decimal(i) * Decimal("100")
            o = h = low = c = price
            h = price + Decimal("100")
            low = price - Decimal("100")
        else:  # flat
            o = c = base_price
            h = base_price + Decimal("100")
            low = base_price - Decimal("100")
        candles.append(
            OHLCV(timestamp=ts, open=o, high=h, low=low, close=c, volume=Decimal("1"))
        )
    return candles


def make_gate(
    *,
    warmup: int = 2,
    config: RobustnessConfig | None = None,
) -> RobustnessGate:
    """Build a RobustnessGate with permissive backtester settings.

    Zero fees / slippage so signals → trade outcomes are deterministic.
    """
    bt = Backtester(
        config=BacktestConfig(
            initial_balance=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_bps=0,
            warmup_candles=warmup,
            leverage=1,
            risk_percent=1.0,
            max_position_size_percent=50.0,
            min_risk_reward_ratio=1.0,
        )
    )
    return RobustnessGate(backtester=bt, config=config or RobustnessConfig())


# =============================================================================
# Helper: _sharpe_from_trades
# =============================================================================


class TestSharpeHelper:
    def test_returns_none_for_one_trade(self) -> None:
        # Need at least 2 trades for variance.
        from src.backtest.engine import BacktestTrade

        t = BacktestTrade(
            trade_id="x",
            symbol="BTC/USDT",
            side="long",
            entry_time=datetime(2026, 1, 1),
            exit_time=datetime(2026, 1, 2),
            entry_price=Decimal("50000"),
            exit_price=Decimal("51000"),
            quantity=Decimal("1"),
            leverage=1,
            stop_loss=None,
            take_profit=None,
            entry_fee=Decimal("0"),
            exit_fee=Decimal("0"),
            pnl=Decimal("100"),
            close_reason="take_profit",
        )
        assert _sharpe_from_trades([t], Decimal("10000")) is None

    def test_returns_none_for_zero_variance(self) -> None:
        from src.backtest.engine import BacktestTrade

        trades = [
            BacktestTrade(
                trade_id=f"x{i}",
                symbol="BTC/USDT",
                side="long",
                entry_time=datetime(2026, 1, 1),
                exit_time=datetime(2026, 1, 2),
                entry_price=Decimal("50000"),
                exit_price=Decimal("51000"),
                quantity=Decimal("1"),
                leverage=1,
                stop_loss=None,
                take_profit=None,
                entry_fee=Decimal("0"),
                exit_fee=Decimal("0"),
                pnl=Decimal("100"),  # identical pnl → std=0
                close_reason="take_profit",
            )
            for i in range(3)
        ]
        assert _sharpe_from_trades(trades, Decimal("10000")) is None


# =============================================================================
# Helper: _classify_regimes
# =============================================================================


class TestRegimeClassifier:
    def test_skips_warmup_candles(self) -> None:
        candles = make_candles(50, pattern="flat")
        out = _classify_regimes(candles, sma_period=20, band_pct=0.02)
        # Only candles at index >= 19 are classified.
        assert len(out) == 50 - 19

    def test_returns_empty_when_too_short(self) -> None:
        candles = make_candles(10, pattern="flat")
        assert _classify_regimes(candles, sma_period=20, band_pct=0.02) == {}

    def test_rising_prices_become_bull(self) -> None:
        candles = make_candles(50, pattern="rising")
        # Linear +100/candle gives ~1.76% gap to a 20-period SMA at the
        # tail, so use a small band so the late candles register as bull.
        out = _classify_regimes(candles, sma_period=20, band_pct=0.005)
        late = [out[c.timestamp] for c in candles[-5:]]
        assert all(r == "bull" for r in late)


# =============================================================================
# OOS gate
# =============================================================================


class TestOOSGate:
    @pytest.mark.asyncio
    async def test_passes_when_oos_consistent_with_is(self) -> None:
        gate = make_gate(
            config=RobustnessConfig(
                oos_min_trades=2, walk_forward_windows=2,
                regime_sma_period=20,
            )
        )
        # 60 winning candles → IS and OOS both win.
        candles = make_candles(60, pattern="winning")
        strategy = PeriodicLongStrategy(period=5)
        report = await gate.evaluate(strategy, candles, "BTC/USDT")
        oos = next(g for g in report.gates if g.name == "oos")
        assert oos.status in (GateStatus.PASSED, GateStatus.SKIPPED)
        # If it ran, both splits had identical positive Sharpe.
        if oos.status == GateStatus.PASSED:
            assert oos.details["is_trades"] >= 2
            assert oos.details["oos_trades"] >= 2

    @pytest.mark.asyncio
    async def test_fails_when_oos_collapses(self) -> None:
        gate = make_gate(
            config=RobustnessConfig(
                oos_min_trades=2, walk_forward_windows=2,
                regime_sma_period=20, oos_fraction=0.4,
            )
        )
        # First 60 candles: winning. Last 40: losing. OOS half = losing.
        candles = (
            make_candles(60, pattern="winning")
            + make_candles(
                40, pattern="losing", start=datetime(2026, 1, 1) + timedelta(hours=60)
            )
        )
        strategy = PeriodicLongStrategy(period=5)
        report = await gate.evaluate(strategy, candles, "BTC/USDT")
        oos = next(g for g in report.gates if g.name == "oos")
        assert oos.status == GateStatus.FAILED

    @pytest.mark.asyncio
    async def test_skipped_when_too_few_candles(self) -> None:
        gate = make_gate()
        candles = make_candles(5, pattern="flat")
        strategy = PeriodicLongStrategy(period=10)
        report = await gate.evaluate(strategy, candles, "BTC/USDT")
        oos = next(g for g in report.gates if g.name == "oos")
        assert oos.status == GateStatus.SKIPPED


# =============================================================================
# Walk-forward gate
# =============================================================================


class TestWalkForwardGate:
    @pytest.mark.asyncio
    async def test_passes_when_all_windows_profitable(self) -> None:
        gate = make_gate(
            config=RobustnessConfig(
                walk_forward_windows=4,
                walk_forward_min_trades_per_window=1,
                regime_sma_period=20,
                oos_min_trades=1,
            )
        )
        candles = make_candles(80, pattern="winning")
        strategy = PeriodicLongStrategy(period=4)
        report = await gate.evaluate(strategy, candles, "BTC/USDT")
        wf = next(g for g in report.gates if g.name == "walk_forward")
        assert wf.status == GateStatus.PASSED
        assert wf.score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_fails_when_majority_unprofitable(self) -> None:
        gate = make_gate(
            config=RobustnessConfig(
                walk_forward_windows=4,
                walk_forward_min_trades_per_window=1,
                walk_forward_positive_fraction=0.75,
                regime_sma_period=20,
                oos_min_trades=1,
            )
        )
        # 80 candles: first 20 winning, next 60 losing → 1/4 windows positive.
        winning = make_candles(20, pattern="winning")
        losing = make_candles(
            60, pattern="losing", start=datetime(2026, 1, 1) + timedelta(hours=20)
        )
        strategy = PeriodicLongStrategy(period=4)
        report = await gate.evaluate(strategy, winning + losing, "BTC/USDT")
        wf = next(g for g in report.gates if g.name == "walk_forward")
        assert wf.status == GateStatus.FAILED

    @pytest.mark.asyncio
    async def test_skipped_when_not_enough_candles(self) -> None:
        gate = make_gate(
            config=RobustnessConfig(walk_forward_windows=10, regime_sma_period=20)
        )
        candles = make_candles(20, pattern="flat")
        strategy = PeriodicLongStrategy(period=5)
        report = await gate.evaluate(strategy, candles, "BTC/USDT")
        wf = next(g for g in report.gates if g.name == "walk_forward")
        assert wf.status == GateStatus.SKIPPED


# =============================================================================
# Regime gate
# =============================================================================


class TestRegimeGate:
    @pytest.mark.asyncio
    async def test_skipped_when_no_baseline_trades(self) -> None:
        gate = make_gate(config=RobustnessConfig(regime_sma_period=20))
        candles = make_candles(60, pattern="flat")
        # period larger than candle count so no signal fires.
        strategy = PeriodicLongStrategy(period=999)
        report = await gate.evaluate(strategy, candles, "BTC/USDT")
        regime = next(g for g in report.gates if g.name == "regime")
        assert regime.status == GateStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_passes_when_all_evaluable_regimes_positive(self) -> None:
        gate = make_gate(
            config=RobustnessConfig(
                regime_sma_period=20,
                regime_min_trades_per_regime=2,
                oos_min_trades=1,
            )
        )
        candles = make_candles(80, pattern="winning")
        strategy = PeriodicLongStrategy(period=4)
        report = await gate.evaluate(strategy, candles, "BTC/USDT")
        regime = next(g for g in report.gates if g.name == "regime")
        # All trades are winners → every populated regime has positive expectancy.
        assert regime.status in (GateStatus.PASSED, GateStatus.SKIPPED)
        if regime.status == GateStatus.PASSED:
            for stats in regime.details["per_regime"].values():
                if stats["evaluable"]:
                    assert stats["expectancy"] >= 0


# =============================================================================
# Sensitivity gate
# =============================================================================


class TestSensitivityGate:
    @pytest.mark.asyncio
    async def test_skipped_without_factory_or_grid(self) -> None:
        gate = make_gate(config=RobustnessConfig(regime_sma_period=20))
        candles = make_candles(60, pattern="winning")
        strategy = PeriodicLongStrategy(period=5)
        report = await gate.evaluate(strategy, candles, "BTC/USDT")
        sens = next(g for g in report.gates if g.name == "sensitivity")
        assert sens.status == GateStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_passes_when_all_grid_points_profitable(self) -> None:
        gate = make_gate(
            config=RobustnessConfig(
                regime_sma_period=20,
                oos_min_trades=1,
                sensitivity_profitable_fraction=0.6,
                sensitivity_sharpe_retention=0.3,
            )
        )
        candles = make_candles(80, pattern="winning")

        def factory(period: int = 5) -> BaseStrategy:
            return PeriodicLongStrategy(period=period)

        report = await gate.evaluate(
            PeriodicLongStrategy(period=5),
            candles,
            "BTC/USDT",
            strategy_factory=factory,
            param_grid={"period": [4, 5, 6]},
        )
        sens = next(g for g in report.gates if g.name == "sensitivity")
        assert sens.status == GateStatus.PASSED
        assert sens.details["combos"] == 3
        assert sens.details["profitable_fraction"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_fails_when_grid_exceeds_cap(self) -> None:
        gate = make_gate(
            config=RobustnessConfig(
                regime_sma_period=20, sensitivity_max_combos=2
            )
        )
        candles = make_candles(60, pattern="winning")

        def factory(period: int = 5) -> BaseStrategy:
            return PeriodicLongStrategy(period=period)

        report = await gate.evaluate(
            PeriodicLongStrategy(period=5),
            candles,
            "BTC/USDT",
            strategy_factory=factory,
            param_grid={"period": [3, 4, 5, 6]},  # 4 combos > cap of 2
        )
        sens = next(g for g in report.gates if g.name == "sensitivity")
        assert sens.status == GateStatus.FAILED
        assert "exceeding cap" in sens.reason


# =============================================================================
# Aggregate report
# =============================================================================


class TestAggregateReport:
    @pytest.mark.asyncio
    async def test_overall_passed_requires_no_failures(self) -> None:
        gate = make_gate(
            config=RobustnessConfig(
                regime_sma_period=20,
                walk_forward_windows=4,
                walk_forward_min_trades_per_window=1,
                oos_min_trades=1,
            )
        )
        candles = make_candles(80, pattern="winning")
        strategy = PeriodicLongStrategy(period=4)
        report = await gate.evaluate(strategy, candles, "BTC/USDT")
        # No gate FAILED → overall passes (sensitivity is SKIPPED).
        assert report.overall_passed is True
        assert isinstance(report, RobustnessReport)
        assert report.baseline_trades > 0

    @pytest.mark.asyncio
    async def test_summary_lists_outcomes(self) -> None:
        gate = make_gate(
            config=RobustnessConfig(
                regime_sma_period=20,
                walk_forward_windows=4,
                walk_forward_min_trades_per_window=1,
                oos_min_trades=1,
            )
        )
        candles = make_candles(80, pattern="winning")
        strategy = PeriodicLongStrategy(period=4)
        report = await gate.evaluate(strategy, candles, "BTC/USDT")
        assert "Robustness verdict" in report.summary
        assert "Baseline Sharpe" in report.summary

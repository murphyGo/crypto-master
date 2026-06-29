"""Tests for the RobustnessGate validator."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

import pytest

from src.backtest.engine import (
    BacktestConfig,
    Backtester,
    BacktestResult,
    BacktestTrade,
)
from src.backtest.validator import (
    GateStatus,
    RobustnessConfig,
    RobustnessGate,
    RobustnessReport,
    _classify_regimes,
    _sharpe_from_trades,
    classify_entry_regime,
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

    def test_classify_entry_regime_uses_latest_pre_entry_candle(self) -> None:
        candles = make_candles(50, pattern="rising")
        assert classify_entry_regime(candles, sma_period=20, band_pct=0.005) == "bull"

    def test_classify_entry_regime_unknown_when_too_short(self) -> None:
        candles = make_candles(10, pattern="flat")
        assert classify_entry_regime(candles, sma_period=20) == "unknown"


# =============================================================================
# OOS gate
# =============================================================================


class TestOOSGate:
    @pytest.mark.asyncio
    async def test_passes_when_oos_consistent_with_is(self) -> None:
        gate = make_gate(
            config=RobustnessConfig(
                oos_min_trades=2,
                walk_forward_windows=2,
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
                oos_min_trades=2,
                walk_forward_windows=2,
                regime_sma_period=20,
                oos_fraction=0.4,
            )
        )
        # First 60 candles: winning. Last 40: losing. OOS half = losing.
        candles = make_candles(60, pattern="winning") + make_candles(
            40, pattern="losing", start=datetime(2026, 1, 1) + timedelta(hours=60)
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

    @pytest.mark.asyncio
    async def test_skipped_when_is_trades_below_minimum_floor(self) -> None:
        """Phase 24.1 / DEBT-032: tiny IS with non-positive Sharpe → SKIPPED.

        Regression for the over-eager FAIL: an operator who relaxes
        ``oos_min_trades`` below the Sharpe-significance floor would
        otherwise see a strategy with positive expected value but only
        2-3 IS trades hard-failed by sampling noise. The IS-floor guard
        converts that path to SKIPPED.

        Phase 24.2 follow-up: relies on the default
        ``minimum_is_trades=10`` (bumped from 5 per quant-trader-expert
        review). Sharpe estimates with N<10 trades have prohibitively
        high variance.
        """
        # ``oos_min_trades=2`` so the under-populated-split SKIP
        # doesn't claim the verdict first — the IS-Sharpe-noise SKIP
        # under test must take priority. The new default
        # ``minimum_is_trades=10`` is the IS floor (Phase 24.2 /
        # DEBT-032).
        # 60-candle losing series, oos_fraction=0.5 → IS=30 / OOS=30.
        # PeriodicLongStrategy(period=8) fires roughly 3 trades per
        # split — above ``oos_min_trades=2`` (so the existing skip
        # doesn't trigger) but below ``minimum_is_trades=10`` (so the
        # new IS-floor skip is the path under test).
        gate = make_gate(
            config=RobustnessConfig(
                oos_min_trades=2,
                # Default minimum_is_trades=10 — left implicit to pin
                # the new default contract.
                walk_forward_windows=2,
                regime_sma_period=20,
                oos_fraction=0.5,
            )
        )
        candles = make_candles(60, pattern="losing")
        strategy = PeriodicLongStrategy(period=8)
        report = await gate.evaluate(strategy, candles, "BTC/USDT")
        oos = next(g for g in report.gates if g.name == "oos")
        assert oos.status == GateStatus.SKIPPED
        assert oos.details is not None
        # IS trade count is the floor's discriminator.
        assert oos.details["is_trades"] >= 2  # past the OOS-min-trades skip
        assert oos.details["is_trades"] < 10  # below the IS-Sharpe-noise floor
        assert "Insufficient IS trades" in (oos.reason or "")

    @pytest.mark.asyncio
    async def test_minimum_is_trades_default_is_ten(self) -> None:
        """Phase 24.2 / DEBT-032 follow-up: the bumped default value
        is the load-bearing contract.

        Quant-trader-expert called out that N=5 Sharpe is "essentially
        noise" — bumped to N=10 as a defensible compromise (strict
        statistical floor would be N=20; 10 balances the floor with
        practical feasibility for nascent strategies).
        """
        cfg = RobustnessConfig()
        assert cfg.minimum_is_trades == 10

    @pytest.mark.asyncio
    async def test_below_floor_skips_but_at_or_above_floor_fails(self) -> None:
        """Phase 24.2 / DEBT-032 follow-up: pin the floor's exclusive
        boundary at the new default of 10.

        The gate's SKIP guard reads ``is_trades < minimum_is_trades``,
        so with the default ``minimum_is_trades=10``:

        * IS=9  → below the floor → SKIPPED (Sharpe is noise-dominated).
        * IS=10 → at the floor → execution falls through to the
          IS-Sharpe-non-positive branch, which FAILs on a losing
          candle stream.

        This is the boundary that the bumped default (5 → 10) is
        meant to enforce: strategies with N<10 IS trades are no
        longer hard-killed by sampling variance.

        Two configurations differ only in their candle stream length
        (drives the IS trade count); everything else is held constant
        so the boundary inequality is the load-bearing assertion.
        """
        # PeriodicLongStrategy(period=4) on a losing series, split
        # 50/50 by ``oos_fraction=0.5``. Empirically calibrated:
        #   total=78 candles → IS=39 candles → IS=9 trades  (below floor)
        #   total=82 candles → IS=41 candles → IS=10 trades (at floor)
        common = {
            "oos_min_trades": 2,
            "walk_forward_windows": 2,
            "regime_sma_period": 20,
            "oos_fraction": 0.5,
        }

        # N=9 → below default floor (10) → SKIPPED.
        gate_skip = make_gate(config=RobustnessConfig(**common))  # type: ignore[arg-type]
        candles_skip = make_candles(78, pattern="losing")
        strategy = PeriodicLongStrategy(period=4)
        report_skip = await gate_skip.evaluate(strategy, candles_skip, "BTC/USDT")
        oos_skip = next(g for g in report_skip.gates if g.name == "oos")

        # N=10 → at the floor → FAIL on the losing-IS-Sharpe branch.
        gate_fail = make_gate(config=RobustnessConfig(**common))  # type: ignore[arg-type]
        candles_fail = make_candles(82, pattern="losing")
        report_fail = await gate_fail.evaluate(strategy, candles_fail, "BTC/USDT")
        oos_fail = next(g for g in report_fail.gates if g.name == "oos")

        # Floor boundary contract: below the floor → SKIPPED; at the
        # floor → FAILED (since the candle stream is losing and IS
        # Sharpe is non-positive). The two outcomes together pin the
        # inequality direction (``<`` not ``<=``).
        assert oos_skip.status == GateStatus.SKIPPED
        assert oos_skip.details is not None
        assert oos_skip.details["is_trades"] == 9  # below the floor
        assert "Insufficient IS trades" in (oos_skip.reason or "")

        assert oos_fail.status == GateStatus.FAILED
        assert oos_fail.details is not None
        # FAIL details carry is_sharpe / oos_sharpe (no is_trades — the
        # FAIL branch is past the SKIP guards by definition).
        is_sharpe = oos_fail.details["is_sharpe"]
        assert is_sharpe is None or is_sharpe <= 0


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

    @pytest.mark.asyncio
    async def test_skips_when_only_one_regime_is_evaluable(self) -> None:
        gate = make_gate(
            config=RobustnessConfig(
                regime_sma_period=20,
                regime_min_trades_per_regime=2,
            )
        )
        candles = make_candles(80, pattern="rising")
        trades = [
            BacktestTrade(
                trade_id=f"t{i}",
                symbol="BTC/USDT",
                side="long",
                entry_time=candles[25 + i].timestamp,
                exit_time=candles[26 + i].timestamp,
                entry_price=Decimal("50000"),
                exit_price=Decimal("50100"),
                quantity=Decimal("1"),
                leverage=1,
                stop_loss=None,
                take_profit=None,
                entry_fee=Decimal("0"),
                exit_fee=Decimal("0"),
                pnl=Decimal("100"),
                close_reason="take_profit",
            )
            for i in range(2)
        ]
        baseline = BacktestResult(
            run_id="bt-regime",
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            start_time=candles[0].timestamp,
            end_time=candles[-1].timestamp,
            initial_balance=Decimal("10000"),
            final_balance=Decimal("10200"),
            total_trades=2,
            wins=2,
            losses=0,
            breakevens=0,
            total_pnl=Decimal("200"),
            total_fees=Decimal("0"),
            win_rate=1.0,
            return_percent=2.0,
            trades=trades,
        )

        result = await gate._gate_regime(baseline, candles)

        assert result.status == GateStatus.SKIPPED
        assert result.details["evaluable_count"] == 1
        assert "at least 2 evaluable regimes" in result.reason


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
            config=RobustnessConfig(regime_sma_period=20, sensitivity_max_combos=2)
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


# =============================================================================
# Phase 9.3: Multi-TF gate routing
# =============================================================================


class _MultiTFPeriodicLongStrategy(BaseStrategy):
    """Like ``PeriodicLongStrategy`` but declares multi-TF and verifies
    the engine actually fed it the per-TF dict.

    The signal logic is unchanged so existing pattern fixtures (winning
    candles → trades hit TP) still drive the gate's accept/reject path.
    Captures every analyze call so tests can assert no future leakage
    in the OOS / walk-forward higher-TF slices.
    """

    def __init__(self, period: int = 5) -> None:
        super().__init__(
            info=TechniqueInfo(
                name="multi_tf_periodic",
                version="1.0.0",
                description="multi-tf periodic long for gate testing",
                technique_type="code",
                requires_multi_timeframe=True,
            )
        )
        self.period = period
        self.calls: list[dict[str, object]] = []

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
        current_price: Decimal | None = None,
    ) -> AnalysisResult:
        self.calls.append(
            {
                "primary_last_ts": ohlcv[-1].timestamp if ohlcv else None,
                "by_tf_keys": (
                    sorted(ohlcv_by_timeframe.keys())
                    if ohlcv_by_timeframe is not None
                    else None
                ),
                "by_tf_last_ts": (
                    {
                        tf: (c[-1].timestamp if c else None)
                        for tf, c in ohlcv_by_timeframe.items()
                    }
                    if ohlcv_by_timeframe is not None
                    else None
                ),
            }
        )
        idx = len(ohlcv) - 1
        if idx > 0 and idx % self.period == 0:
            return long_signal()
        return neutral()


class TestMultiTimeframeRouting:
    @pytest.mark.asyncio
    async def test_oos_gate_does_not_leak_future_higher_tf(self) -> None:
        """The IS half must not see any higher-TF candle past its boundary."""
        gate = make_gate(
            config=RobustnessConfig(
                regime_sma_period=20,
                walk_forward_windows=4,
                walk_forward_min_trades_per_window=1,
                oos_min_trades=1,
            )
        )
        primary = make_candles(80, pattern="winning")
        # Build a sparser higher-TF stream with the same timestamps as
        # every 4th primary candle. Cleanly aligned so the bisect cut
        # falls on a candle boundary.
        higher = [primary[i] for i in range(0, len(primary), 4)]
        strategy = _MultiTFPeriodicLongStrategy(period=4)

        report = await gate.evaluate(
            strategy,
            primary,
            "BTC/USDT",
            ohlcv_by_timeframe={"1h": primary, "4h": higher},
        )

        # Every analyze call's higher-TF cutoff must be ≤ primary cutoff.
        for c in strategy.calls:
            primary_ts = c["primary_last_ts"]
            higher_last = c["by_tf_last_ts"]["4h"]  # type: ignore[index]
            assert primary_ts is not None
            if higher_last is not None:
                assert higher_last <= primary_ts
        assert report.baseline_trades > 0
        # Sanity: every analyze call was multi-TF (no fallback to
        # single-TF dispatch on this strategy).
        assert all(c["by_tf_keys"] == ["1h", "4h"] for c in strategy.calls)

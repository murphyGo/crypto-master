"""Robustness validation for backtested strategies.

A backtest passing on a single full-history run is a weak signal —
overfitting, regime luck, and parameter cliffs all produce strong
in-sample numbers that collapse in live trading. ``RobustnessGate``
runs four independent checks on top of a baseline backtest and only
admits a strategy if it survives all of them:

1. **Out-of-sample (OOS) split** — train/test the strategy on a 70/30
   chronological split. Penalize any strategy whose held-out Sharpe
   is materially worse than its in-sample Sharpe.

2. **Walk-forward windows** — slice the timeline into N consecutive
   windows and require the strategy to be profitable in a majority
   of them. Catches strategies that rely on a single lucky regime.

3. **Regime split** — classify each entry candle as bull / bear /
   sideways using a long-period SMA. Require non-negative expectancy
   in every regime that has enough trades to evaluate. Catches
   "only works in bull markets" strategies.

4. **Parameter sensitivity** — if the caller supplies a parameter
   grid and a factory, sweep neighboring parameter values and require
   the strategy to remain robust. A "tall narrow peak" in parameter
   space is a textbook overfit signature.

Each gate returns a ``GateResult`` with status, score, threshold, and
diagnostics. The overall report fails on any FAILED gate; SKIPPED
gates (insufficient data or missing inputs) are neutral. Callers
should treat SKIPPED gates as "you did not give me what I needed
to check this" — not as silent passes.

Related Requirements:
- FR-025: Backtesting Execution (consumes baseline backtests)
- FR-026: Automated Feedback Loop (this is the promotion gate)
- FR-027: Technique Adoption (only robust strategies promoted)
- NFR-006: Backtesting Result Storage
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.backtest.engine import (
    BacktestConfig,
    BacktestResult,
    BacktestTrade,
    Backtester,
)
from src.logger import get_logger
from src.models import OHLCV
from src.strategy.base import BaseStrategy
from src.trading.profiles import TradingProfile

logger = get_logger("crypto_master.backtest.validator")


# Strategy factories used by the sensitivity gate. They take a flat
# kwargs dict of parameter names -> values and must return a fresh
# ``BaseStrategy`` instance configured with those parameters.
StrategyFactory = Callable[..., BaseStrategy]
# Async variants are also accepted (LLM-backed strategies may need
# to do I/O during construction).
AsyncStrategyFactory = Callable[..., Awaitable[BaseStrategy]]


# =============================================================================
# Models
# =============================================================================


class GateStatus(str, Enum):
    """Outcome of a single robustness gate."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class GateResult(BaseModel):
    """Outcome of one robustness check.

    Attributes:
        name: Gate identifier (e.g. ``"oos"``).
        status: PASSED, FAILED, or SKIPPED.
        score: The primary metric the gate scored on. Comparable to
            ``threshold``. May be None for SKIPPED gates.
        threshold: The minimum acceptable score. None for SKIPPED.
        reason: One-sentence human-readable verdict.
        details: Gate-specific diagnostics (per-window Sharpes,
            per-regime expectancy, etc.). Always JSON-serializable.
    """

    name: str
    status: GateStatus
    score: float | None = None
    threshold: float | None = None
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)


class RobustnessReport(BaseModel):
    """Aggregate verdict across all gates.

    A report is "passed" if no gate FAILED. SKIPPED gates do not
    block promotion but their absence should be visible to operators
    so they don't mistake "untested" for "validated."

    Attributes:
        overall_passed: True iff no gate has status FAILED.
        gates: Ordered list of every gate that ran.
        summary: One-paragraph human-readable summary.
        baseline_sharpe: Per-trade Sharpe of the baseline (full-data)
            backtest, included for context in the summary.
        baseline_trades: Trade count of the baseline backtest.
    """

    overall_passed: bool
    gates: list[GateResult]
    summary: str
    baseline_sharpe: float | None = None
    baseline_trades: int = 0


class RobustnessConfig(BaseModel):
    """Tunable thresholds for each gate.

    Defaults are deliberately conservative — they reflect the "if in
    doubt, fail" principle. The cost of letting a bad strategy through
    is real money lost; the cost of failing a good strategy is a few
    hours of re-evaluation.

    Attributes:
        oos_fraction: Fraction of candles reserved for the OOS split.
            0.3 means 70% IS / 30% OOS.
        oos_sharpe_retention: OOS Sharpe must be at least this fraction
            of IS Sharpe. 0.7 = "OOS may be up to 30% worse than IS".
        oos_min_trades: Minimum trade count required in *each* split
            for the gate to evaluate. Below this, status is SKIPPED.
        walk_forward_windows: Number of equal-size chronological
            windows the timeline is sliced into.
        walk_forward_positive_fraction: Fraction of windows that must
            have a positive return. 0.6 = "at least 60% profitable".
        walk_forward_min_trades_per_window: Skip windows with fewer
            trades than this when computing the fraction.
        regime_sma_period: Lookback for the long SMA used to classify
            bull / bear.
        regime_band_pct: ± band around the SMA that defines the
            "sideways" regime. 0.02 = "within ±2% of SMA".
        regime_min_trades_per_regime: Regimes with fewer trades than
            this are excluded from the verdict (insufficient data).
        regime_require_positive_in_all: If True, every evaluated regime
            must have non-negative expectancy. If False, only the
            average across regimes must be non-negative.
        sensitivity_sharpe_retention: Mean Sharpe across the parameter
            grid must be at least this fraction of the baseline Sharpe.
        sensitivity_profitable_fraction: Fraction of parameter combos
            that must produce a positive return. 0.6 = robust hill;
            below this is a "narrow peak" overfit signature.
        sensitivity_max_combos: Hard cap on grid size to avoid
            accidental combinatorial explosions. Excess combos cause
            the gate to FAIL fast (not silently truncate).
    """

    # OOS split
    oos_fraction: float = Field(default=0.3, gt=0, lt=1)
    oos_sharpe_retention: float = Field(default=0.7, gt=0, le=2)
    oos_min_trades: int = Field(default=10, ge=1)

    # Walk-forward
    walk_forward_windows: int = Field(default=5, ge=2)
    walk_forward_positive_fraction: float = Field(default=0.6, gt=0, le=1)
    walk_forward_min_trades_per_window: int = Field(default=3, ge=1)

    # Regime
    regime_sma_period: int = Field(default=200, ge=20)
    regime_band_pct: float = Field(default=0.02, ge=0, le=0.2)
    regime_min_trades_per_regime: int = Field(default=5, ge=1)
    regime_require_positive_in_all: bool = True

    # Parameter sensitivity
    sensitivity_sharpe_retention: float = Field(default=0.5, gt=0, le=2)
    sensitivity_profitable_fraction: float = Field(default=0.6, gt=0, le=1)
    sensitivity_max_combos: int = Field(default=64, ge=1)


# =============================================================================
# Gate orchestrator
# =============================================================================


class RobustnessGate:
    """Run all robustness gates against a strategy + dataset.

    The gate is stateless — a single instance can evaluate many
    strategies. All four gates execute regardless of intermediate
    failures so the caller sees the full diagnostic picture; the
    overall verdict is the AND of non-skipped results.

    Usage::

        gate = RobustnessGate(Backtester(BacktestConfig()))
        report = await gate.evaluate(
            strategy=my_strategy,
            ohlcv=candles,
            symbol="BTC/USDT",
            strategy_factory=lambda **kw: MyStrategy(info, **kw),
            param_grid={"rsi_threshold": [25, 30, 35]},
        )
        if not report.overall_passed:
            for g in report.gates:
                print(g.status, g.name, g.reason)
    """

    def __init__(
        self,
        backtester: Backtester | None = None,
        config: RobustnessConfig | None = None,
    ) -> None:
        """Initialize the gate.

        Args:
            backtester: Backtester instance used for every sub-run.
                A fresh instance with default config is created if
                omitted. Pass your own to share fee/slippage settings
                with the baseline run.
            config: Threshold tuning. Defaults are conservative.
        """
        self.backtester = backtester or Backtester(BacktestConfig())
        self.config = config or RobustnessConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def evaluate(
        self,
        strategy: BaseStrategy,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        profile: TradingProfile | None = None,
        strategy_factory: StrategyFactory | AsyncStrategyFactory | None = None,
        param_grid: dict[str, list[Any]] | None = None,
    ) -> RobustnessReport:
        """Run all four gates and produce an aggregate verdict.

        Args:
            strategy: The strategy under evaluation. Used as-is for
                the OOS, walk-forward, and regime gates.
            ohlcv: Historical candles, chronologically ascending.
                Must be long enough for at least
                ``walk_forward_windows`` slices and the
                ``regime_sma_period`` lookback.
            symbol: Trading pair symbol passed through to the
                backtester.
            timeframe: Candle timeframe label.
            profile: Optional trading profile applied to every sub-run.
            strategy_factory: Optional callable that builds a strategy
                from a parameter dict. Required for the sensitivity
                gate; without it, sensitivity is SKIPPED.
            param_grid: Mapping of parameter name → list of values to
                sweep. Required for the sensitivity gate. Cartesian
                product capped at ``sensitivity_max_combos``.

        Returns:
            A ``RobustnessReport`` with one ``GateResult`` per gate.
        """
        # Baseline run — used by gates for context (e.g. baseline Sharpe
        # for sensitivity comparison) and surfaced in the summary.
        baseline = await self._run_subset(
            strategy, ohlcv, symbol, timeframe, profile
        )
        baseline_sharpe = _sharpe_from_trades(
            baseline.trades, baseline.initial_balance
        )

        gates: list[GateResult] = [
            await self._gate_oos(strategy, ohlcv, symbol, timeframe, profile),
            await self._gate_walk_forward(
                strategy, ohlcv, symbol, timeframe, profile
            ),
            await self._gate_regime(baseline, ohlcv),
            await self._gate_sensitivity(
                ohlcv,
                symbol,
                timeframe,
                profile,
                strategy_factory,
                param_grid,
                baseline_sharpe,
            ),
        ]

        overall = all(g.status != GateStatus.FAILED for g in gates)
        return RobustnessReport(
            overall_passed=overall,
            gates=gates,
            summary=self._build_summary(gates, baseline_sharpe, baseline),
            baseline_sharpe=baseline_sharpe,
            baseline_trades=baseline.total_trades,
        )

    # ------------------------------------------------------------------
    # Gate implementations
    # ------------------------------------------------------------------

    async def _gate_oos(
        self,
        strategy: BaseStrategy,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str,
        profile: TradingProfile | None,
    ) -> GateResult:
        """In-sample / out-of-sample split (chronological).

        Splits the candle series at ``1 - oos_fraction`` and runs the
        strategy independently on each half. Compares Sharpe ratios.
        """
        cfg = self.config
        split_idx = int(len(ohlcv) * (1 - cfg.oos_fraction))
        is_data = ohlcv[:split_idx]
        oos_data = ohlcv[split_idx:]

        # Both splits need enough warm-up for the strategy to fire.
        warmup = self.backtester.config.warmup_candles
        if len(is_data) <= warmup or len(oos_data) <= warmup:
            return GateResult(
                name="oos",
                status=GateStatus.SKIPPED,
                reason=(
                    f"Not enough candles to split: IS={len(is_data)}, "
                    f"OOS={len(oos_data)}, warmup={warmup}"
                ),
            )

        is_run = await self._run_subset(
            strategy, is_data, symbol, timeframe, profile
        )
        oos_run = await self._run_subset(
            strategy, oos_data, symbol, timeframe, profile
        )

        if (
            is_run.total_trades < cfg.oos_min_trades
            or oos_run.total_trades < cfg.oos_min_trades
        ):
            return GateResult(
                name="oos",
                status=GateStatus.SKIPPED,
                reason=(
                    f"Insufficient trades for OOS verdict: "
                    f"IS={is_run.total_trades}, OOS={oos_run.total_trades} "
                    f"(min {cfg.oos_min_trades} per split)"
                ),
                details={
                    "is_trades": is_run.total_trades,
                    "oos_trades": oos_run.total_trades,
                },
            )

        is_sharpe = _sharpe_from_trades(is_run.trades, is_run.initial_balance)
        oos_sharpe = _sharpe_from_trades(
            oos_run.trades, oos_run.initial_balance
        )

        # If IS Sharpe is None or non-positive, the strategy isn't even
        # working in-sample — there is nothing for OOS to "retain."
        if is_sharpe is None or is_sharpe <= 0:
            return GateResult(
                name="oos",
                status=GateStatus.FAILED,
                score=is_sharpe,
                threshold=0.0,
                reason=(
                    f"In-sample Sharpe is non-positive ({is_sharpe}); "
                    "strategy has no edge to validate."
                ),
                details={"is_sharpe": is_sharpe, "oos_sharpe": oos_sharpe},
            )

        threshold = is_sharpe * cfg.oos_sharpe_retention
        oos_score = oos_sharpe if oos_sharpe is not None else float("-inf")
        passed = oos_score >= threshold

        return GateResult(
            name="oos",
            status=GateStatus.PASSED if passed else GateStatus.FAILED,
            score=oos_sharpe,
            threshold=threshold,
            reason=(
                f"OOS Sharpe {oos_sharpe:.3f} "
                f"{'≥' if passed else '<'} threshold {threshold:.3f} "
                f"(IS Sharpe {is_sharpe:.3f} × retention "
                f"{cfg.oos_sharpe_retention})"
                if oos_sharpe is not None
                else "OOS Sharpe undefined (insufficient variance in OOS)"
            ),
            details={
                "is_sharpe": is_sharpe,
                "oos_sharpe": oos_sharpe,
                "is_trades": is_run.total_trades,
                "oos_trades": oos_run.total_trades,
                "is_return_pct": is_run.return_percent,
                "oos_return_pct": oos_run.return_percent,
            },
        )

    async def _gate_walk_forward(
        self,
        strategy: BaseStrategy,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str,
        profile: TradingProfile | None,
    ) -> GateResult:
        """N consecutive non-overlapping windows.

        Strategies in this codebase are not parameter-fit on each
        window (prompts and rule sets are static), so walk-forward
        here is "rolling OOS": the same strategy runs on N independent
        time slices and we check consistency.
        """
        cfg = self.config
        n = cfg.walk_forward_windows
        warmup = self.backtester.config.warmup_candles

        # Need at least warmup + a few useful candles per window.
        min_window_size = warmup + 5
        if len(ohlcv) < n * min_window_size:
            return GateResult(
                name="walk_forward",
                status=GateStatus.SKIPPED,
                reason=(
                    f"Need at least {n * min_window_size} candles for "
                    f"{n} windows (warmup={warmup}); have {len(ohlcv)}"
                ),
            )

        window_size = len(ohlcv) // n
        results: list[BacktestResult] = []
        for w in range(n):
            start = w * window_size
            # Last window absorbs any remainder so no candles are lost.
            end = (w + 1) * window_size if w < n - 1 else len(ohlcv)
            window = ohlcv[start:end]
            result = await self._run_subset(
                strategy, window, symbol, timeframe, profile
            )
            results.append(result)

        # Only count windows that actually produced enough trades to
        # be a meaningful sample.
        evaluable = [
            r
            for r in results
            if r.total_trades >= cfg.walk_forward_min_trades_per_window
        ]
        if not evaluable:
            return GateResult(
                name="walk_forward",
                status=GateStatus.SKIPPED,
                reason=(
                    f"No window had ≥ "
                    f"{cfg.walk_forward_min_trades_per_window} trades; "
                    "strategy too inactive to walk-forward."
                ),
                details={
                    "window_trade_counts": [r.total_trades for r in results],
                },
            )

        positive = [r for r in evaluable if r.return_percent > 0]
        positive_fraction = len(positive) / len(evaluable)
        passed = positive_fraction >= cfg.walk_forward_positive_fraction

        return GateResult(
            name="walk_forward",
            status=GateStatus.PASSED if passed else GateStatus.FAILED,
            score=positive_fraction,
            threshold=cfg.walk_forward_positive_fraction,
            reason=(
                f"{len(positive)}/{len(evaluable)} evaluable windows "
                f"profitable ({positive_fraction:.0%}); threshold "
                f"{cfg.walk_forward_positive_fraction:.0%}"
            ),
            details={
                "window_returns_pct": [r.return_percent for r in results],
                "window_trade_counts": [r.total_trades for r in results],
                "evaluable_windows": len(evaluable),
            },
        )

    async def _gate_regime(
        self,
        baseline: BacktestResult,
        ohlcv: list[OHLCV],
    ) -> GateResult:
        """Classify each trade's entry regime; require non-negative
        expectancy in every evaluable regime.

        Regime classification uses the closing price at the entry
        candle vs. the long-period SMA at that same candle:
            close > SMA × (1 + band) → bull
            close < SMA × (1 - band) → bear
            otherwise                 → sideways
        """
        cfg = self.config
        if len(ohlcv) <= cfg.regime_sma_period:
            return GateResult(
                name="regime",
                status=GateStatus.SKIPPED,
                reason=(
                    f"Need > {cfg.regime_sma_period} candles for SMA "
                    f"regime classification; have {len(ohlcv)}"
                ),
            )

        if not baseline.trades:
            return GateResult(
                name="regime",
                status=GateStatus.SKIPPED,
                reason="Baseline run produced no trades to classify.",
            )

        regime_by_ts = _classify_regimes(
            ohlcv, cfg.regime_sma_period, cfg.regime_band_pct
        )

        buckets: dict[str, list[BacktestTrade]] = {
            "bull": [],
            "bear": [],
            "sideways": [],
        }
        unclassified = 0
        for trade in baseline.trades:
            regime = regime_by_ts.get(trade.entry_time)
            if regime is None:
                unclassified += 1
                continue
            buckets[regime].append(trade)

        # Per-regime expectancy (average pnl per trade).
        per_regime: dict[str, dict[str, Any]] = {}
        evaluable_failures: list[str] = []
        evaluable_count = 0
        for regime, trades in buckets.items():
            if len(trades) < cfg.regime_min_trades_per_regime:
                per_regime[regime] = {
                    "trades": len(trades),
                    "expectancy": None,
                    "evaluable": False,
                }
                continue
            evaluable_count += 1
            expectancy = float(
                sum((t.pnl for t in trades), Decimal("0")) / Decimal(len(trades))
            )
            per_regime[regime] = {
                "trades": len(trades),
                "expectancy": expectancy,
                "evaluable": True,
            }
            if expectancy < 0:
                evaluable_failures.append(regime)

        if evaluable_count == 0:
            return GateResult(
                name="regime",
                status=GateStatus.SKIPPED,
                reason=(
                    "No regime has enough trades to evaluate "
                    f"(min {cfg.regime_min_trades_per_regime})."
                ),
                details={"per_regime": per_regime, "unclassified": unclassified},
            )

        if cfg.regime_require_positive_in_all:
            passed = not evaluable_failures
            reason = (
                "All evaluable regimes have non-negative expectancy"
                if passed
                else f"Negative expectancy in: {', '.join(evaluable_failures)}"
            )
        else:
            avg = sum(
                v["expectancy"]
                for v in per_regime.values()
                if v["evaluable"]
            ) / evaluable_count
            passed = avg >= 0
            reason = (
                f"Average expectancy across {evaluable_count} regimes: "
                f"{avg:.4f}"
            )

        return GateResult(
            name="regime",
            status=GateStatus.PASSED if passed else GateStatus.FAILED,
            score=float(evaluable_count - len(evaluable_failures)),
            threshold=float(evaluable_count),
            reason=reason,
            details={
                "per_regime": per_regime,
                "unclassified": unclassified,
                "evaluable_count": evaluable_count,
            },
        )

    async def _gate_sensitivity(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str,
        profile: TradingProfile | None,
        factory: StrategyFactory | AsyncStrategyFactory | None,
        param_grid: dict[str, list[Any]] | None,
        baseline_sharpe: float | None,
    ) -> GateResult:
        """Sweep the parameter grid; require a robust hill, not a peak.

        SKIPPED if the caller did not supply both a factory and a
        non-empty grid. This is intentional: most strategies in this
        codebase are prompt-based and have no tunable numeric
        parameters. The gate is meaningful only when it has knobs to
        turn.
        """
        cfg = self.config
        if factory is None or not param_grid:
            return GateResult(
                name="sensitivity",
                status=GateStatus.SKIPPED,
                reason=(
                    "No strategy_factory or param_grid supplied; "
                    "parameter sensitivity cannot be assessed."
                ),
            )

        # Cartesian product of all parameter values.
        keys = list(param_grid.keys())
        value_lists = [param_grid[k] for k in keys]
        combos = list(itertools.product(*value_lists))
        if len(combos) > cfg.sensitivity_max_combos:
            return GateResult(
                name="sensitivity",
                status=GateStatus.FAILED,
                reason=(
                    f"Parameter grid produces {len(combos)} combos, "
                    f"exceeding cap of {cfg.sensitivity_max_combos}. "
                    "Reduce grid before re-running."
                ),
                details={"combos": len(combos), "cap": cfg.sensitivity_max_combos},
            )

        if baseline_sharpe is None or baseline_sharpe <= 0:
            return GateResult(
                name="sensitivity",
                status=GateStatus.FAILED,
                score=baseline_sharpe,
                threshold=0.0,
                reason=(
                    f"Baseline Sharpe is {baseline_sharpe}; nothing to "
                    "test sensitivity against."
                ),
            )

        per_combo: list[dict[str, Any]] = []
        sharpes: list[float] = []
        positive = 0
        for values in combos:
            params = dict(zip(keys, values, strict=True))
            built = factory(**params)
            variant = await built if isinstance(built, Awaitable) else built
            run = await self._run_subset(
                variant, ohlcv, symbol, timeframe, profile
            )
            sharpe = _sharpe_from_trades(run.trades, run.initial_balance)
            sharpes.append(sharpe if sharpe is not None else 0.0)
            if run.return_percent > 0:
                positive += 1
            per_combo.append(
                {
                    "params": params,
                    "sharpe": sharpe,
                    "return_pct": run.return_percent,
                    "trades": run.total_trades,
                }
            )

        mean_sharpe = sum(sharpes) / len(sharpes)
        sharpe_threshold = baseline_sharpe * cfg.sensitivity_sharpe_retention
        profitable_fraction = positive / len(combos)

        sharpe_ok = mean_sharpe >= sharpe_threshold
        fraction_ok = profitable_fraction >= cfg.sensitivity_profitable_fraction
        passed = sharpe_ok and fraction_ok

        reason_parts: list[str] = []
        reason_parts.append(
            f"mean Sharpe {mean_sharpe:.3f} "
            f"{'≥' if sharpe_ok else '<'} threshold {sharpe_threshold:.3f}"
        )
        reason_parts.append(
            f"profitable fraction {profitable_fraction:.0%} "
            f"{'≥' if fraction_ok else '<'} threshold "
            f"{cfg.sensitivity_profitable_fraction:.0%}"
        )

        return GateResult(
            name="sensitivity",
            status=GateStatus.PASSED if passed else GateStatus.FAILED,
            score=mean_sharpe,
            threshold=sharpe_threshold,
            reason="; ".join(reason_parts),
            details={
                "combos": len(combos),
                "mean_sharpe": mean_sharpe,
                "profitable_fraction": profitable_fraction,
                "baseline_sharpe": baseline_sharpe,
                "per_combo": per_combo,
            },
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _run_subset(
        self,
        strategy: BaseStrategy,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str,
        profile: TradingProfile | None,
    ) -> BacktestResult:
        """Run a backtest on a candle subset.

        A thin wrapper so every gate uses the same call shape and the
        backtester's config (fees, slippage, leverage) is consistent
        across all sub-runs.
        """
        return await self.backtester.run(
            strategy=strategy,
            ohlcv=ohlcv,
            symbol=symbol,
            timeframe=timeframe,
            profile=profile,
        )

    @staticmethod
    def _build_summary(
        gates: list[GateResult],
        baseline_sharpe: float | None,
        baseline: BacktestResult,
    ) -> str:
        """Compose the human-readable summary string."""
        passed = [g.name for g in gates if g.status == GateStatus.PASSED]
        failed = [g.name for g in gates if g.status == GateStatus.FAILED]
        skipped = [g.name for g in gates if g.status == GateStatus.SKIPPED]

        sharpe_str = (
            f"{baseline_sharpe:.3f}" if baseline_sharpe is not None else "n/a"
        )
        verdict = "PASSED" if not failed else "FAILED"
        return (
            f"Robustness verdict: {verdict}. "
            f"Baseline Sharpe={sharpe_str}, trades={baseline.total_trades}, "
            f"return={baseline.return_percent:.2f}%. "
            f"Passed: {passed or 'none'}. "
            f"Failed: {failed or 'none'}. "
            f"Skipped: {skipped or 'none'}."
        )


# =============================================================================
# Stand-alone helpers (also used by tests)
# =============================================================================


def _sharpe_from_trades(
    trades: list[BacktestTrade],
    initial_balance: Decimal,
) -> float | None:
    """Per-trade Sharpe from a list of trades.

    Returns ``mean(r) / stdev(r)`` over trade-level returns
    (pnl / initial_balance). Returns None if there are fewer than two
    trades or zero variance — both states make Sharpe meaningless.
    """
    if len(trades) < 2 or initial_balance <= 0:
        return None
    returns = [float(t.pnl / initial_balance) for t in trades]
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(variance)
    if std == 0:
        return None
    return mean / std


def _classify_regimes(
    ohlcv: list[OHLCV],
    sma_period: int,
    band_pct: float,
) -> dict[datetime, str]:
    """Classify each candle by regime relative to its trailing SMA.

    Candles before the SMA can be computed (index < sma_period - 1)
    are absent from the result; trades entered on those candles will
    be reported as ``unclassified`` by the regime gate.
    """
    out: dict[datetime, str] = {}
    if len(ohlcv) < sma_period:
        return out
    # Rolling sum keeps this O(n) instead of O(n × sma_period).
    rolling_sum = sum(c.close for c in ohlcv[:sma_period])
    for i in range(sma_period - 1, len(ohlcv)):
        if i >= sma_period:
            rolling_sum += ohlcv[i].close - ohlcv[i - sma_period].close
        sma = rolling_sum / Decimal(sma_period)
        close = ohlcv[i].close
        upper = sma * (Decimal("1") + Decimal(str(band_pct)))
        lower = sma * (Decimal("1") - Decimal(str(band_pct)))
        if close > upper:
            regime = "bull"
        elif close < lower:
            regime = "bear"
        else:
            regime = "sideways"
        out[ohlcv[i].timestamp] = regime
    return out


__all__ = [
    "GateStatus",
    "GateResult",
    "RobustnessReport",
    "RobustnessConfig",
    "RobustnessGate",
]

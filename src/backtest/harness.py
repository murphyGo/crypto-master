"""Multi-sub-account backtest harness (Phase 19.5)."""

from __future__ import annotations

import math
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from src.backtest.analyzer import PerformanceAnalyzer
from src.backtest.engine import (
    BacktestConfig,
    Backtester,
    BacktestResult,
    BacktestTrade,
    EquityPoint,
)
from src.backtest.multi_account_report import MultiAccountReport
from src.backtest.validator import RobustnessGate
from src.models import OHLCV
from src.strategy.base import BaseStrategy
from src.trading.sub_account import SubAccount
from src.utils.io import atomic_write_text

EquityTuple = tuple[datetime, Decimal]


class BacktestHarness:
    """Run strategy whitelists for multiple sub-accounts on one OHLCV window."""

    def __init__(
        self,
        *,
        analyzer: PerformanceAnalyzer | None = None,
        gate: RobustnessGate | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self.analyzer = analyzer or PerformanceAnalyzer()
        self.gate = gate
        self.data_dir = data_dir or Path("data/backtest/combinations")

    async def run_sub_accounts(
        self,
        sub_accounts: list[SubAccount],
        ohlcv_by_symbol_tf: dict[tuple[str, str], list[OHLCV]],
        strategies: dict[str, BaseStrategy],
    ) -> MultiAccountReport:
        """Run every active sub-account's strategy whitelist."""
        if not ohlcv_by_symbol_tf:
            raise ValueError("ohlcv_by_symbol_tf must contain at least one window")
        (symbol, timeframe), ohlcv = next(iter(ohlcv_by_symbol_tf.items()))
        if not ohlcv:
            raise ValueError("OHLCV window must not be empty")

        run_id = f"combo-{uuid.uuid4().hex[:12]}"
        per_sub_account = {}
        equity_curves: dict[str, list[EquityTuple]] = {}
        merged: list[BacktestTrade] = []
        robustness: dict[str, bool | None] = {}

        for sub in sub_accounts:
            if not sub.enabled:
                continue
            selected = self._select_strategies(sub, strategies)
            if not selected:
                raise ValueError(f"sub-account {sub.id!r} has no matching strategies")

            results = [
                await self._run_one(sub, strategy, ohlcv, symbol, timeframe)
                for strategy in selected
            ]
            combined = self._combine_results(sub, results, symbol, timeframe)
            per_sub_account[sub.id] = self.analyzer.analyze(combined)
            equity_curves[sub.id] = [
                (point.timestamp, point.equity) for point in combined.equity_curve
            ]
            merged.extend(combined.trades)
            robustness[sub.id] = await self._evaluate_robustness(
                selected[0], ohlcv, symbol, timeframe
            )

        return MultiAccountReport(
            run_id=run_id,
            symbol=symbol,
            timeframe=timeframe,
            per_sub_account=per_sub_account,
            equity_curves=equity_curves,
            pairwise_correlation=_pairwise_correlations(equity_curves),
            merged_trade_ledger=sorted(merged, key=lambda t: t.entry_time),
            robustness_passed=robustness,
        )

    def save_report(self, report: MultiAccountReport) -> Path:
        """Persist ``report.json`` under ``data/backtest/combinations``."""
        run_dir = self.data_dir / report.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "report.json"
        atomic_write_text(path, report.model_dump_json(indent=2))
        return path

    async def _run_one(
        self,
        sub: SubAccount,
        strategy: BaseStrategy,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str,
    ) -> BacktestResult:
        balance = sub.initial_balance.get("USDT", Decimal("10000"))
        defaults = BacktestConfig()
        risk_percent = (
            float(sub.risk_overrides.risk_percent)
            if sub.risk_overrides.risk_percent is not None
            else defaults.risk_percent
        )
        leverage = sub.risk_overrides.leverage_cap or defaults.leverage
        backtester = Backtester(
            BacktestConfig(
                initial_balance=balance,
                risk_percent=risk_percent,
                leverage=leverage,
            ),
            data_dir=self.data_dir,
        )
        return await backtester.run(strategy, ohlcv, symbol, timeframe)

    def _select_strategies(
        self, sub: SubAccount, strategies: dict[str, BaseStrategy]
    ) -> list[BaseStrategy]:
        if sub.strategy_filter is None:
            return list(strategies.values())
        return [strategies[name] for name in sub.strategy_filter if name in strategies]

    def _combine_results(
        self,
        sub: SubAccount,
        results: list[BacktestResult],
        symbol: str,
        timeframe: str,
    ) -> BacktestResult:
        initial = sub.initial_balance.get("USDT", Decimal("10000"))
        total_delta = sum(
            (r.final_balance - r.initial_balance for r in results),
            Decimal("0"),
        )
        trades = [
            trade.model_copy(
                update={
                    "sub_account_id": sub.id,
                    "technique_name": result.technique_name,
                }
            )
            for result in results
            for trade in result.trades
        ]
        curve = _combine_equity_curves(initial, [r.equity_curve for r in results])
        final = initial + total_delta
        wins = sum(1 for t in trades if t.pnl > 0)
        losses = sum(1 for t in trades if t.pnl < 0)
        breakevens = sum(1 for t in trades if t.pnl == 0)
        total = len(trades)
        return BacktestResult(
            run_id=f"bt-{uuid.uuid4().hex[:12]}",
            technique_name="+".join(r.technique_name for r in results),
            technique_version="multi",
            symbol=symbol,
            timeframe=timeframe,
            start_time=results[0].start_time,
            end_time=results[0].end_time,
            initial_balance=initial,
            final_balance=final,
            total_trades=total,
            wins=wins,
            losses=losses,
            breakevens=breakevens,
            total_pnl=sum((t.pnl for t in trades), Decimal("0")),
            total_fees=sum((t.entry_fee + t.exit_fee for t in trades), Decimal("0")),
            win_rate=(wins / total if total else 0.0),
            return_percent=(
                float((final - initial) / initial) * 100 if initial else 0.0
            ),
            trades=trades,
            equity_curve=curve,
            liquidated=any(r.liquidated for r in results),
        )

    async def _evaluate_robustness(
        self,
        strategy: BaseStrategy,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str,
    ) -> bool | None:
        if self.gate is None:
            return None
        report = await self.gate.evaluate(strategy, ohlcv, symbol, timeframe)
        return report.overall_passed


def _combine_equity_curves(
    initial: Decimal, curves: list[list[EquityPoint]]
) -> list[EquityPoint]:
    if not curves:
        return []
    base = curves[0]
    combined = []
    for index, point in enumerate(base):
        equity = initial
        for curve in curves:
            if index < len(curve):
                equity += curve[index].equity - curve[0].equity
        combined.append(EquityPoint(timestamp=point.timestamp, equity=equity))
    return combined


def _pairwise_correlations(
    equity_curves: dict[str, list[EquityTuple]],
) -> dict[str, float]:
    ids = sorted(equity_curves)
    out: dict[str, float] = {}
    for left_index, left in enumerate(ids):
        for right in ids[left_index + 1 :]:
            out[f"{left}|{right}"] = _correlation(
                _returns(equity_curves[left]),
                _returns(equity_curves[right]),
            )
    return out


def _returns(curve: list[EquityTuple]) -> list[float]:
    values = [float(point[1]) for point in curve]
    return [
        (values[i] - values[i - 1]) / values[i - 1]
        for i in range(1, len(values))
        if values[i - 1] != 0
    ]


def _correlation(left: list[float], right: list[float]) -> float:
    n = min(len(left), len(right))
    if n < 2:
        return 0.0
    x = left[:n]
    y = right[:n]
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y, strict=True))
    denom_x = math.sqrt(sum((a - mean_x) ** 2 for a in x))
    denom_y = math.sqrt(sum((b - mean_y) ** 2 for b in y))
    if denom_x == 0 or denom_y == 0:
        return 0.0
    return numerator / (denom_x * denom_y)


__all__ = ["BacktestHarness"]

"""Tests for the Phase 19.5 multi-sub-account backtest harness."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.backtest.harness import BacktestHarness
from src.backtest.validator import RobustnessReport
from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, TechniqueInfo
from src.trading.sub_account import RiskOverrides, SubAccount


def _candles(count: int = 32) -> list[OHLCV]:
    start = datetime(2026, 1, 1)
    candles = []
    for idx in range(count):
        close = Decimal("100") + Decimal(idx)
        candles.append(
            OHLCV(
                timestamp=start + timedelta(hours=idx),
                open=close,
                high=close + Decimal("3"),
                low=close - Decimal("0.5"),
                close=close,
                volume=Decimal("100"),
            )
        )
    return candles


class LongEveryBarStrategy(BaseStrategy):
    def __init__(self, name: str) -> None:
        super().__init__(
            TechniqueInfo(
                name=name,
                version="1.0.0",
                description=f"{name} test strategy",
                technique_type="code",
            )
        )

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
        current_price: Decimal | None = None,
    ) -> AnalysisResult:
        del symbol, timeframe, ohlcv_by_timeframe, current_price
        price = ohlcv[-1].close
        return AnalysisResult(
            signal="long",
            confidence=0.9,
            entry_price=price,
            stop_loss=price - Decimal("1"),
            take_profit=price + Decimal("2"),
            reasoning="test long",
        )


class RecordingGate:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def evaluate(
        self,
        strategy: BaseStrategy,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str,
        **kwargs: Any,
    ) -> RobustnessReport:
        del ohlcv, kwargs
        self.calls.append((strategy.name, symbol, timeframe))
        return RobustnessReport(overall_passed=True, gates=[], summary="passed")


def _sub_account(account_id: str, strategy_name: str) -> SubAccount:
    return SubAccount(
        id=account_id,
        name=account_id,
        mode="paper",
        initial_balance={"USDT": Decimal("10000")},
        strategy_filter=[strategy_name],
        risk_overrides=RiskOverrides(risk_percent=Decimal("1")),
    )


@pytest.mark.asyncio
async def test_run_sub_accounts_merges_ledgers_and_correlates(
    tmp_path: Path,
) -> None:
    harness = BacktestHarness(data_dir=tmp_path)
    report = await harness.run_sub_accounts(
        [_sub_account("suba", "alpha"), _sub_account("subb", "beta")],
        {("BTC/USDT", "1h"): _candles()},
        {
            "alpha": LongEveryBarStrategy("alpha"),
            "beta": LongEveryBarStrategy("beta"),
        },
    )

    assert report.symbol == "BTC/USDT"
    assert report.timeframe == "1h"
    assert set(report.per_sub_account) == {"suba", "subb"}
    assert set(report.equity_curves) == {"suba", "subb"}
    assert "suba|subb" in report.pairwise_correlation
    assert report.merged_trade_ledger
    assert {trade.sub_account_id for trade in report.merged_trade_ledger} == {
        "suba",
        "subb",
    }

    path = harness.save_report(report)
    assert path == tmp_path / report.run_id / "report.json"
    assert path.exists()


@pytest.mark.asyncio
async def test_robustness_gate_runs_per_sub_account(tmp_path: Path) -> None:
    gate = RecordingGate()
    harness = BacktestHarness(data_dir=tmp_path, gate=gate)  # type: ignore[arg-type]

    report = await harness.run_sub_accounts(
        [_sub_account("suba", "alpha"), _sub_account("subb", "beta")],
        {("ETH/USDT", "4h"): _candles()},
        {
            "alpha": LongEveryBarStrategy("alpha"),
            "beta": LongEveryBarStrategy("beta"),
        },
    )

    assert gate.calls == [("alpha", "ETH/USDT", "4h"), ("beta", "ETH/USDT", "4h")]
    assert report.robustness_passed == {"suba": True, "subb": True}

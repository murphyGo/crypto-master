"""Tests for the Phase 19.5 multi-sub-account backtest harness."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.backtest.harness import BacktestHarness
from src.backtest.reproducibility import ReplayIdentity
from src.backtest.snapshot import Snapshot, SnapshotMetadata
from src.backtest.snapshot_replay import SnapshotReplaySource
from src.backtest.snapshot_v2 import VersionedSnapshot
from src.backtest.validator import RobustnessReport
from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, TechniqueInfo
from src.trading.sub_account import (
    CapitalPolicy,
    RiskPolicy,
    StrategyPolicy,
    SubAccount,
)


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


class RecordingMultiTimeframeStrategy(LongEveryBarStrategy):
    def __init__(self, name: str) -> None:
        BaseStrategy.__init__(
            self,
            TechniqueInfo(
                name=name,
                version="1.0.0",
                description=f"{name} multi-timeframe test strategy",
                technique_type="code",
                requires_multi_timeframe=True,
                timeframes=["1h", "4h"],
            ),
        )
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
                "symbol": symbol,
                "timeframe": timeframe,
                "keys": sorted((ohlcv_by_timeframe or {}).keys()),
                "primary_len": len(ohlcv),
                "current_price": current_price,
            }
        )
        return await super().analyze(
            ohlcv,
            symbol,
            timeframe,
            ohlcv_by_timeframe=ohlcv_by_timeframe,
            current_price=current_price,
        )


class RecordingGate:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.multi_tf_keys: list[list[str]] = []
        self.snapshot_calls: list[tuple[str, str | None]] = []

    async def evaluate(
        self,
        strategy: BaseStrategy,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str,
        **kwargs: Any,
    ) -> RobustnessReport:
        del ohlcv
        self.calls.append((strategy.name, symbol, timeframe))
        self.multi_tf_keys.append(sorted(kwargs["ohlcv_by_timeframe"].keys()))
        return RobustnessReport(overall_passed=True, gates=[], summary="passed")

    async def evaluate_snapshot(
        self,
        strategy: BaseStrategy,
        replay: SnapshotReplaySource,
        **kwargs: Any,
    ) -> RobustnessReport:
        self.snapshot_calls.append((strategy.name, replay.generation_id))
        self.multi_tf_keys.append(sorted(kwargs["ohlcv_by_timeframe"].keys()))
        return RobustnessReport(
            overall_passed=True,
            gates=[],
            summary="passed",
            replay_identity=replay.identity,
        )


def _sub_account(account_id: str, strategy_name: str) -> SubAccount:
    return SubAccount(
        id=account_id,
        name=account_id,
        mode="paper",
        capital_policy=CapitalPolicy(initial_balance={"USDT": Decimal("10000")}),
        strategy_policy=StrategyPolicy(strategy_filter=[strategy_name]),
        risk_policy=RiskPolicy(risk_percent=Decimal("1")),
    )


def _legacy_replay(candles: list[OHLCV]) -> SnapshotReplaySource:
    return SnapshotReplaySource(
        VersionedSnapshot(
            schema_version=1,
            legacy_snapshot=Snapshot(
                metadata=SnapshotMetadata(
                    symbol="BTC/USDT",
                    timeframe="1h",
                    source="binance",
                    fetched_at=candles[-1].timestamp,
                    candle_count=len(candles),
                    first_timestamp=candles[0].timestamp,
                    last_timestamp=candles[-1].timestamp,
                    fetcher_version="test",
                ),
                ohlcv=candles,
            ),
        )
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
    assert report.robustness_by_strategy == {
        "suba": {"alpha": True},
        "subb": {"beta": True},
    }


@pytest.mark.asyncio
async def test_multi_timeframe_strategy_receives_timeframe_context(
    tmp_path: Path,
) -> None:
    gate = RecordingGate()
    harness = BacktestHarness(data_dir=tmp_path, gate=gate)  # type: ignore[arg-type]
    strategy = RecordingMultiTimeframeStrategy("mtf")

    report = await harness.run_sub_accounts(
        [_sub_account("suba", "mtf")],
        {
            ("BTC/USDT", "1h"): _candles(32),
            ("BTC/USDT", "4h"): _candles(32),
        },
        {"mtf": strategy},
    )

    assert strategy.calls
    assert all(call["keys"] == ["1h", "4h"] for call in strategy.calls)
    assert gate.calls == [("mtf", "BTC/USDT", "1h")]
    assert gate.multi_tf_keys == [["1h", "4h"]]
    assert report.robustness_by_strategy == {"suba": {"mtf": True}}


@pytest.mark.asyncio
async def test_harness_propagates_one_pinned_replay_to_backtest_and_gate(
    tmp_path: Path,
) -> None:
    candles = _candles(32)
    replay = _legacy_replay(candles)
    gate = RecordingGate()
    harness = BacktestHarness(data_dir=tmp_path, gate=gate)  # type: ignore[arg-type]

    report = await harness.run_sub_accounts(
        [_sub_account("suba", "alpha")],
        {("BTC/USDT", "1h"): candles},
        {"alpha": LongEveryBarStrategy("alpha")},
        replay_sources={("BTC/USDT", "1h"): replay},
    )

    assert gate.snapshot_calls == [("alpha", None)]
    assert report.robustness_by_strategy == {"suba": {"alpha": True}}


@pytest.mark.asyncio
async def test_harness_rejects_primary_data_that_differs_from_replay(
    tmp_path: Path,
) -> None:
    candles = _candles(32)
    replay = _legacy_replay(candles)
    mismatched = list(candles)
    mismatched[-1] = mismatched[-1].model_copy(
        update={"close": mismatched[-1].close + Decimal("1")}
    )

    with pytest.raises(ValueError, match="must match the pinned replay"):
        await BacktestHarness(data_dir=tmp_path).run_sub_accounts(
            [_sub_account("suba", "alpha")],
            {("BTC/USDT", "1h"): mismatched},
            {"alpha": LongEveryBarStrategy("alpha")},
            replay_sources={("BTC/USDT", "1h"): replay},
        )


def test_harness_rejects_conflicting_generation_results(tmp_path: Path) -> None:
    candles = _candles(2)
    base = {
        "run_id": "one",
        "technique_name": "alpha",
        "technique_version": "1.0.0",
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "start_time": candles[0].timestamp,
        "end_time": candles[-1].timestamp,
        "initial_balance": Decimal("10000"),
        "final_balance": Decimal("10000"),
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "breakevens": 0,
        "total_pnl": Decimal("0"),
        "total_fees": Decimal("0"),
        "win_rate": 0.0,
        "return_percent": 0.0,
    }
    from src.backtest.engine import BacktestResult

    first = BacktestResult(
        **base,
        replay_identity=ReplayIdentity(
            schema_version=2,
            generation_id="a" * 64,
            source="binance",
            symbol="BTC/USDT",
            timeframe="1h",
        ),
    )
    second = BacktestResult(
        **{**base, "run_id": "two", "technique_name": "beta"},
        replay_identity=ReplayIdentity(
            schema_version=2,
            generation_id="b" * 64,
            source="binance",
            symbol="BTC/USDT",
            timeframe="1h",
        ),
    )

    with pytest.raises(ValueError, match="conflicting replay generations"):
        BacktestHarness(data_dir=tmp_path)._combine_results(
            _sub_account("suba", "alpha"),
            [first, second],
            "BTC/USDT",
            "1h",
        )

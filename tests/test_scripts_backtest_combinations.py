"""Smoke tests for the strategy-combination backtest operator script."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from scripts import backtest_combinations
from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, TechniqueInfo


class ScriptLongStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            TechniqueInfo(
                name="alpha",
                version="1.0.0",
                description="script smoke strategy",
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
            reasoning="script smoke",
        )


class FakeExchange:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False


def _candles(count: int = 32) -> list[OHLCV]:
    start = datetime(2026, 1, 1)
    return [
        OHLCV(
            timestamp=start + timedelta(hours=idx),
            open=Decimal("100") + Decimal(idx),
            high=Decimal("103") + Decimal(idx),
            low=Decimal("99") + Decimal(idx),
            close=Decimal("100") + Decimal(idx),
            volume=Decimal("100"),
        )
        for idx in range(count)
    ]


def test_load_sub_accounts_config_and_window_parser(tmp_path: Path) -> None:
    config = tmp_path / "sub_accounts.yaml"
    config.write_text(
        """
sub_accounts:
  - id: suba
    name: Sub A
    mode: paper
    initial_balance:
      USDT: "10000"
    strategy_filter: [alpha]
""",
        encoding="utf-8",
    )

    accounts = backtest_combinations.load_sub_accounts_config(config)

    assert accounts[0].id == "suba"
    assert accounts[0].strategy_filter == ["alpha"]
    assert backtest_combinations._candles_from_window("2d", "1h") == 48


@pytest.mark.asyncio
async def test_run_from_config_writes_expected_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "sub_accounts.yaml"
    config.write_text(
        """
sub_accounts:
  - id: suba
    name: Sub A
    mode: paper
    initial_balance:
      USDT: "10000"
    strategy_filter: [alpha]
""",
        encoding="utf-8",
    )

    async def fake_fetch_ohlcv_window(**kwargs: Any) -> list[OHLCV]:
        del kwargs
        return _candles()

    monkeypatch.setattr(backtest_combinations, "BinanceExchange", FakeExchange)
    monkeypatch.setattr(
        backtest_combinations, "fetch_ohlcv_window", fake_fetch_ohlcv_window
    )
    monkeypatch.setattr(
        backtest_combinations,
        "load_all_strategies",
        lambda: {"alpha": ScriptLongStrategy()},
    )

    report_path = await backtest_combinations.run_from_config(
        config,
        symbol="BTC/USDT",
        timeframe="1h",
        candles=32,
        output_dir=tmp_path / "runs",
    )

    assert report_path.exists()
    assert (report_path.parent / "trades.csv").exists()
    png = report_path.parent / "equity_curves.png"
    assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

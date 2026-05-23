"""Unit tests for the tsmom_vol_breakout strategy.

The strategy is single-timeframe (4h), trend-gated time-series momentum
with a Donchian volatility-breakout trigger. It returns ``long`` only in a
rising, trending regime with a fresh 20-bar breakout (mirror for short) and
forces ``neutral`` in chop. ``minimum_candles`` is 251 (EMA_SLOW=200 +
SLOPE_LOOKBACK=50 + 1), so the series must be long enough.

Loaded via :func:`src.strategy.loader.load_strategy` per the active-pool
location ``strategies/tsmom_vol_breakout.py``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.models import OHLCV
from src.strategy.base import BaseStrategy, StrategyValidationError
from src.strategy.loader import load_strategy

STRATEGY_PATH = (
    Path(__file__).resolve().parents[1] / "strategies" / "tsmom_vol_breakout.py"
)


def _load() -> BaseStrategy:
    return load_strategy(STRATEGY_PATH)


def _candles(
    closes: list[float], *, highs: list[float], lows: list[float]
) -> list[OHLCV]:
    start = datetime(2026, 1, 1)
    delta = timedelta(hours=4)
    out: list[OHLCV] = []
    for i, close in enumerate(closes):
        out.append(
            OHLCV(
                timestamp=start + i * delta,
                open=Decimal(str(close)),
                high=Decimal(str(highs[i])),
                low=Decimal(str(lows[i])),
                close=Decimal(str(close)),
                volume=Decimal("1000"),
            )
        )
    return out


def _uptrend(n: int = 300) -> list[float]:
    """Steady linear uptrend so EMA50 > EMA200, price > EMA200, slope > 0."""
    return [100.0 + i * 1.0 for i in range(n)]


def _downtrend(n: int = 300) -> list[float]:
    """Steady linear downtrend (mirror of _uptrend)."""
    return [100.0 + (n - i) * 1.0 for i in range(n)]


def _flat(n: int = 300) -> list[float]:
    """Sideways oscillation: EMA slope stays under the regime threshold."""
    return [500.0 + (5.0 if i % 2 == 0 else -5.0) for i in range(n)]


async def test_long_on_trend_up_breakout_positive_momentum() -> None:
    strategy = _load()
    closes = _uptrend()
    # Force a clean Donchian breakout: final close well above the prior 20-bar
    # high. Highs track close+1 except the last bar pops to confirm the break.
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    closes[-1] = closes[-2] + 30.0  # breakout candle
    highs[-1] = closes[-1] + 1.0
    lows[-1] = closes[-2]

    result = await strategy.analyze(
        _candles(closes, highs=highs, lows=lows), "BTC/USDT"
    )

    assert result.signal == "long"
    assert result.stop_loss < result.entry_price
    assert result.take_profit > result.entry_price


async def test_short_on_trend_down_breakdown_negative_momentum() -> None:
    strategy = _load()
    closes = _downtrend()
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    closes[-1] = closes[-2] - 30.0  # breakdown candle
    lows[-1] = closes[-1] - 1.0
    highs[-1] = closes[-2]

    result = await strategy.analyze(
        _candles(closes, highs=highs, lows=lows), "BTC/USDT"
    )

    assert result.signal == "short"
    assert result.stop_loss > result.entry_price
    assert result.take_profit < result.entry_price


async def test_neutral_when_sideways_flat_slope() -> None:
    strategy = _load()
    closes = _flat()
    highs = [c + 2.0 for c in closes]
    lows = [c - 2.0 for c in closes]

    result = await strategy.analyze(
        _candles(closes, highs=highs, lows=lows), "BTC/USDT"
    )

    assert result.signal == "neutral"


async def test_insufficient_data_raises_validation_error() -> None:
    strategy = _load()
    closes = _uptrend(n=100)  # below minimum_candles (251)
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]

    with pytest.raises(StrategyValidationError):
        await strategy.analyze(_candles(closes, highs=highs, lows=lows), "BTC/USDT")

"""Tests for the deterministic baseline strategies (Phase 9.2).

Each strategy gets:
  - A "long-trigger" test (data engineered to fire long).
  - A "short-trigger" test (mirror).
  - A "neutral / no setup" test.
  - A "not enough data" test (returns neutral, doesn't crash).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.models import OHLCV, AnalysisResult

STRATEGIES_DIR = Path(__file__).resolve().parents[1] / "strategies"


# =============================================================================
# Helpers
# =============================================================================


def _load_strategy_module(filename: str):
    """Load one of the baseline strategy modules from strategies/."""
    path = STRATEGIES_DIR / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


def _make_ohlcv(
    closes: list[float],
    *,
    start: datetime | None = None,
    delta: timedelta = timedelta(hours=1),
) -> list[OHLCV]:
    """Build a minimal OHLCV series from a close-price list.

    Uses close as the open/high/low for simplicity — the baseline
    strategies only look at the close column. Volume is constant.
    """
    start = start or datetime(2026, 1, 1)
    out: list[OHLCV] = []
    for i, close in enumerate(closes):
        out.append(
            OHLCV(
                timestamp=start + i * delta,
                open=Decimal(str(close)),
                high=Decimal(str(close * 1.001)),
                low=Decimal(str(close * 0.999)),
                close=Decimal(str(close)),
                volume=Decimal("1000"),
            )
        )
    return out


def _build(module, **kwargs):
    """Construct the strategy class defined in ``module``.

    Each baseline file exposes a single ``BaseStrategy`` subclass and
    the ``TECHNIQUE_INFO`` dict; we infer the class name by scanning
    for the subclass since the names differ per module.
    """
    from src.strategy.base import BaseStrategy, TechniqueInfo

    info = TechniqueInfo(
        name=module.TECHNIQUE_INFO["name"],
        version=module.TECHNIQUE_INFO["version"],
        description=module.TECHNIQUE_INFO["description"],
        technique_type="code",
        symbols=module.TECHNIQUE_INFO.get("symbols", []),
    )

    klass = next(
        v
        for v in vars(module).values()
        if isinstance(v, type) and issubclass(v, BaseStrategy) and v is not BaseStrategy
    )
    return klass(info=info, **kwargs)


# =============================================================================
# RSI mean reversion
# =============================================================================


@pytest.fixture
def rsi_module():
    return _load_strategy_module("rsi.py")


async def test_rsi_long_when_oversold(rsi_module) -> None:
    strategy = _build(rsi_module)
    # Need ≥ 42 candles (period × 3 warm-up). Flat then sustained drop
    # so the recent window is dominated by losses → RSI ≪ 30.
    closes = [100.0] * 35 + [
        99.0,
        97.0,
        94.0,
        90.0,
        85.0,
        80.0,
        75.0,
        70.0,
        65.0,
        60.0,
        55.0,
        50.0,
        45.0,
        40.0,
    ]
    ohlcv = _make_ohlcv(closes)

    result = await strategy.analyze(ohlcv, "BTC/USDT", "1h")

    assert isinstance(result, AnalysisResult)
    assert result.signal == "long"
    assert result.entry_price == Decimal("40.00")
    # SL below entry, TP above entry — long shape.
    assert result.stop_loss < result.entry_price
    assert result.take_profit > result.entry_price


async def test_rsi_short_when_overbought(rsi_module) -> None:
    strategy = _build(rsi_module)
    closes = [100.0] * 35 + [
        101.0,
        103.0,
        106.0,
        110.0,
        115.0,
        120.0,
        125.0,
        130.0,
        135.0,
        140.0,
        145.0,
        150.0,
        155.0,
        160.0,
    ]
    ohlcv = _make_ohlcv(closes)

    result = await strategy.analyze(ohlcv, "BTC/USDT", "1h")

    assert result.signal == "short"
    # SL above entry, TP below entry — short shape.
    assert result.stop_loss > result.entry_price
    assert result.take_profit < result.entry_price


async def test_rsi_neutral_when_in_band(rsi_module) -> None:
    strategy = _build(rsi_module)
    # Slight oscillation that keeps RSI well within [30, 70].
    closes = [100.0 + ((-1) ** i) * 0.1 for i in range(50)]
    ohlcv = _make_ohlcv(closes)

    result = await strategy.analyze(ohlcv, "BTC/USDT", "1h")

    assert result.signal == "neutral"


async def test_rsi_insufficient_candles_raises(rsi_module) -> None:
    """Strategy validate_input requires period*3 candles; below that
    ``BaseStrategy.validate_input`` raises a StrategyValidationError
    which the engine logs and skips."""
    from src.strategy.base import StrategyValidationError

    strategy = _build(rsi_module)
    short_ohlcv = _make_ohlcv([100.0] * 5)

    with pytest.raises(StrategyValidationError):
        await strategy.analyze(short_ohlcv, "BTC/USDT", "1h")


# =============================================================================
# Bollinger Band reversion
# =============================================================================


@pytest.fixture
def bb_module():
    return _load_strategy_module("bollinger_bands.py")


async def test_bb_long_when_close_below_lower_band(bb_module) -> None:
    strategy = _build(bb_module)
    # 19 stable bars + 1 sharp drop → close pierces the lower band.
    closes = [100.0] * 19 + [85.0]
    ohlcv = _make_ohlcv(closes)

    result = await strategy.analyze(ohlcv, "BTC/USDT", "1h")

    assert result.signal == "long"
    assert result.entry_price == Decimal("85.00")
    # TP is the middle band (the mean to revert to).
    assert result.take_profit > result.entry_price


async def test_bb_short_when_close_above_upper_band(bb_module) -> None:
    strategy = _build(bb_module)
    closes = [100.0] * 19 + [115.0]
    ohlcv = _make_ohlcv(closes)

    result = await strategy.analyze(ohlcv, "BTC/USDT", "1h")

    assert result.signal == "short"
    assert result.entry_price == Decimal("115.00")
    assert result.take_profit < result.entry_price


async def test_bb_neutral_when_close_inside_bands(bb_module) -> None:
    strategy = _build(bb_module)
    # Modest oscillation around 100 — close stays between bands.
    closes = [100.0 + ((-1) ** i) * 1.0 for i in range(20)]
    ohlcv = _make_ohlcv(closes)

    result = await strategy.analyze(ohlcv, "BTC/USDT", "1h")

    assert result.signal == "neutral"


# =============================================================================
# MA crossover
# =============================================================================


@pytest.fixture
def ma_module():
    return _load_strategy_module("ma_crossover.py")


async def test_ma_long_on_bullish_cross(ma_module) -> None:
    """Engineer a fresh cross specifically at the latest bar.

    The crossover detector requires `prev_short <= prev_long` AND
    `cur_short > cur_long`. A multi-bar rally would have crossed
    earlier, so we need a flat history (both MAs equal) plus one
    sharp jump on the last bar that pulls the short MA above the
    long MA in a single step.
    """
    strategy = _build(ma_module)
    closes = [100.0] * 28 + [120.0]  # spike on the final bar
    ohlcv = _make_ohlcv(closes)

    result = await strategy.analyze(ohlcv, "BTC/USDT", "1h")

    assert result.signal == "long"


async def test_ma_short_on_bearish_cross(ma_module) -> None:
    strategy = _build(ma_module)
    closes = [100.0] * 28 + [80.0]  # crash on the final bar
    ohlcv = _make_ohlcv(closes)

    result = await strategy.analyze(ohlcv, "BTC/USDT", "1h")

    assert result.signal == "short"


async def test_ma_neutral_when_no_cross(ma_module) -> None:
    strategy = _build(ma_module)
    # Both MAs trending together, no fresh cross on the last bar.
    closes = [100.0 + 0.1 * i for i in range(40)]
    ohlcv = _make_ohlcv(closes)

    result = await strategy.analyze(ohlcv, "BTC/USDT", "1h")

    assert result.signal == "neutral"


async def test_ma_long_sl_excludes_current_candle_lookback(ma_module) -> None:
    """Phase 24.1 / DEBT-031: SL window excludes the current candle.

    Regression for the silent-drop bug: on a bullish cross where the
    current close is itself the 5-bar low, the OLD code computed
    ``stop_loss = min(closes[-5:])`` which equals the current close
    (the entry), so ``validate_prices`` would raise downstream with
    ``stop_loss >= entry_price`` and the signal silently disappeared.

    Fixture closes [10, 20, 60, 75, 50, 100, 50] with short=2 / long=3:

    * Bullish cross at the last bar: prev_short=75 == prev_long=75
      flips to cur_short=75 > cur_long=66.67.
    * ``closes[-5:]`` = [60, 75, 50, 100, 50], min = 50 = current → OLD
      code SL == entry_price → silent drop.
    * ``closes[-6:-1]`` = [20, 60, 75, 50, 100], min = 20 < entry=50 →
      NEW code emits a valid long signal.
    """
    strategy = _build(ma_module, short_period=2, long_period=3)
    closes = [10.0, 20.0, 60.0, 75.0, 50.0, 100.0, 50.0]
    ohlcv = _make_ohlcv(closes)

    result = await strategy.analyze(ohlcv, "BTC/USDT", "1h")

    # Signal must be emitted (not silently dropped) and SL must satisfy
    # the long-side ``stop_loss < entry_price`` invariant that
    # ``TradingStrategy.validate_prices`` enforces downstream.
    assert result.signal == "long"
    assert result.entry_price == Decimal("50.00")
    assert result.stop_loss == Decimal("20.00")
    assert result.stop_loss < result.entry_price


async def test_ma_short_sl_excludes_current_candle_lookback(ma_module) -> None:
    """Phase 24.1 / DEBT-031: short-side mirror of the SL fix.

    On a bearish cross where the current close is the 5-bar high, the
    OLD ``max(closes[-5:])`` collapses SL onto entry. NEW
    ``max(closes[-6:-1])`` preserves a structural high above entry.

    Mirror of the long fixture: closes [200, 100, 60, 50, 100, 30, 100]
    with short=2 / long=3 forces a fresh bearish cross at the last bar
    AND puts the current close at the 5-bar high (tied), with a
    strictly higher prior-window bar so the new look-back yields a
    valid SL strictly above entry.
    """
    strategy = _build(ma_module, short_period=2, long_period=3)
    # Mirror of the long fixture (each level reflected around 100):
    # long had [10, 20, 60, 75, 50, 100, 50] → mirror is
    # [a, b, c, d, e, f, current] with cur=50 → 200-50=150 etc.
    # SMA values mirror: prev_short=125, prev_long=125 (equality
    # satisfies ≥), cur_short=125 < cur_long=133.33.
    closes = [190.0, 180.0, 140.0, 125.0, 150.0, 100.0, 150.0]
    ohlcv = _make_ohlcv(closes)

    result = await strategy.analyze(ohlcv, "BTC/USDT", "1h")

    assert result.signal == "short"
    assert result.entry_price == Decimal("150.00")
    # OLD: max(closes[-5:]) = max([140,125,150,100,150]) = 150 = entry
    # → invalid (short needs SL > entry).
    # NEW: max(closes[-6:-1]) = max([180,140,125,150,100]) = 180 > 150.
    assert result.stop_loss == Decimal("180.00")
    assert result.stop_loss > result.entry_price

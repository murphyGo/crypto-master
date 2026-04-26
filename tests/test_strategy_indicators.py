"""Tests for src/strategy/indicators.py (Phase 9.2)."""

from __future__ import annotations

import math

import pytest

from src.strategy.indicators import (
    InsufficientDataError,
    bollinger_bands,
    rsi,
    sma,
)

# =============================================================================
# sma
# =============================================================================


def test_sma_basic_average() -> None:
    assert sma([1.0, 2.0, 3.0, 4.0, 5.0], period=5) == 3.0


def test_sma_uses_only_last_period_values() -> None:
    # Period 3 over [10, 20, 30, 40, 50] → mean of [30, 40, 50] = 40.
    assert sma([10.0, 20.0, 30.0, 40.0, 50.0], period=3) == 40.0


def test_sma_single_period_returns_last_value() -> None:
    assert sma([1.0, 2.0, 3.0], period=1) == 3.0


def test_sma_insufficient_data_raises() -> None:
    with pytest.raises(InsufficientDataError):
        sma([1.0, 2.0], period=5)


def test_sma_zero_period_raises() -> None:
    with pytest.raises(ValueError, match="period must be positive"):
        sma([1.0, 2.0, 3.0], period=0)


def test_sma_negative_period_raises() -> None:
    with pytest.raises(ValueError, match="period must be positive"):
        sma([1.0, 2.0, 3.0], period=-3)


# =============================================================================
# rsi
# =============================================================================


def test_rsi_constant_prices_returns_neutral() -> None:
    """No movement → no gains, no losses → conventional 50."""
    closes = [100.0] * 30
    assert rsi(closes, period=14) == 50.0


def test_rsi_monotonic_uptrend_saturates_high() -> None:
    """Pure uptrend → all gains, no losses → 100."""
    closes = [100.0 + i for i in range(30)]
    assert rsi(closes, period=14) == 100.0


def test_rsi_monotonic_downtrend_saturates_low() -> None:
    """Pure downtrend → no gains, all losses → 0."""
    closes = [100.0 - i for i in range(30)]
    assert rsi(closes, period=14) == 0.0


def test_rsi_in_oversold_range_for_recent_drop() -> None:
    """Stable then sharp drop → RSI well below 50."""
    closes = [100.0] * 14 + [99.0, 97.0, 94.0, 90.0, 85.0, 80.0]
    value = rsi(closes, period=14)
    assert value < 50.0


def test_rsi_in_overbought_range_for_recent_rally() -> None:
    closes = [100.0] * 14 + [101.0, 103.0, 106.0, 110.0, 115.0, 120.0]
    value = rsi(closes, period=14)
    assert value > 50.0


def test_rsi_value_within_zero_one_hundred() -> None:
    closes = [100.0 + ((-1) ** i) * (i % 5) for i in range(50)]
    value = rsi(closes, period=14)
    assert 0.0 <= value <= 100.0


def test_rsi_insufficient_data_raises() -> None:
    with pytest.raises(InsufficientDataError):
        rsi([100.0, 101.0, 102.0], period=14)


def test_rsi_invalid_period_raises() -> None:
    with pytest.raises(ValueError, match="period must be positive"):
        rsi([100.0] * 30, period=0)


# =============================================================================
# bollinger_bands
# =============================================================================


def test_bollinger_bands_constant_history_zero_width() -> None:
    """Flat history → zero variance → bands collapse onto the mean."""
    lower, middle, upper = bollinger_bands([100.0] * 20, period=20, std_dev=2.0)
    assert lower == middle == upper == 100.0


def test_bollinger_bands_symmetric_around_middle() -> None:
    closes = [100.0, 102.0, 98.0, 104.0, 96.0] * 4
    lower, middle, upper = bollinger_bands(closes, period=20, std_dev=2.0)
    # mid is the SMA, which for this sequence is 100.0
    assert math.isclose(middle, 100.0)
    # band offsets are equal by definition.
    assert math.isclose(upper - middle, middle - lower)


def test_bollinger_bands_uses_population_std() -> None:
    """Verify the math: closes [10, 20], population std = 5."""
    # period=2, only two values: variance = ((10-15)^2 + (20-15)^2) / 2 = 25.
    # std = 5. Bands at ±2σ → ±10 from mid 15.
    lower, middle, upper = bollinger_bands([10.0, 20.0], period=2, std_dev=2.0)
    assert middle == 15.0
    assert math.isclose(lower, 5.0)
    assert math.isclose(upper, 25.0)


def test_bollinger_bands_insufficient_data_raises() -> None:
    with pytest.raises(InsufficientDataError):
        bollinger_bands([100.0, 101.0], period=20, std_dev=2.0)


def test_bollinger_bands_negative_std_dev_raises() -> None:
    with pytest.raises(ValueError, match="std_dev must be non-negative"):
        bollinger_bands([100.0] * 20, period=20, std_dev=-1.0)


def test_bollinger_bands_zero_period_raises() -> None:
    with pytest.raises(ValueError, match="period must be positive"):
        bollinger_bands([100.0] * 20, period=0, std_dev=2.0)

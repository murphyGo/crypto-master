"""Pure-Python technical indicator math (Phase 9.2).

A small, dependency-free toolkit used by the deterministic baseline
strategies (`strategies/rsi.py`, `strategies/bollinger_bands.py`,
`strategies/ma_crossover.py`). Each function takes a flat sequence of
floats — close prices typically — and returns the indicator value at
the *latest* bar. That's deliberately the only contract: strategies
care about "is the current candle's RSI oversold?" not the full
history; if a future use case wants the whole indicator series, add a
sibling ``*_series`` function rather than retrofitting these.

All math is closed-form Wilder's smoothing for RSI and rolling
window for SMA / Bollinger Bands. No NumPy / Pandas dependency to
keep import time fast on the engine's per-cycle hot path.

Related Requirements:
- FR-003 / FR-004: Strategy framework (deterministic baselines
  alongside LLM-driven techniques)
"""

from __future__ import annotations

import math
from collections.abc import Sequence

__all__ = [
    "InsufficientDataError",
    "bollinger_bands",
    "rsi",
    "sma",
]


class InsufficientDataError(ValueError):
    """Raised when there are fewer values than the indicator needs.

    Strategies catch this and report a neutral signal rather than
    propagating it as a hard error — a fresh symbol with only a few
    candles of history is a normal "not enough data yet" condition,
    not a bug.
    """


def sma(values: Sequence[float], period: int) -> float:
    """Simple moving average over the most recent ``period`` values.

    Args:
        values: Numeric sequence (typically close prices). Must have
            length ≥ ``period``.
        period: Window size. Must be positive.

    Returns:
        The arithmetic mean of the last ``period`` values.

    Raises:
        InsufficientDataError: If ``len(values) < period``.
        ValueError: If ``period <= 0``.
    """
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    if len(values) < period:
        raise InsufficientDataError(f"sma needs >= {period} values, got {len(values)}")
    window = values[-period:]
    return sum(window) / period


def rsi(closes: Sequence[float], period: int = 14) -> float:
    """Wilder's Relative Strength Index at the latest bar.

    Implementation follows Wilder's smoothing rather than the simple
    SMA variant: after the initial ``period`` average of gains and
    losses, each subsequent bar updates via
    ``avg = (prev_avg * (period - 1) + current) / period``.

    Args:
        closes: Close price series in chronological order. Length must
            be ≥ ``period + 1`` so that at least one delta is computed
            for the initial average.
        period: Lookback window. 14 is the canonical Wilder default.

    Returns:
        RSI value in [0, 100]. Returns 100.0 when ``avg_loss`` is zero
        (all-up window) and 0.0 when ``avg_gain`` is zero (all-down
        window) — same convention as TradingView / common libraries.

    Raises:
        InsufficientDataError: If fewer than ``period + 1`` closes.
        ValueError: If ``period <= 0``.
    """
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    if len(closes) < period + 1:
        raise InsufficientDataError(
            f"rsi needs >= {period + 1} closes, got {len(closes)}"
        )

    # Initial avg from the first ``period`` deltas.
    initial_gains = 0.0
    initial_losses = 0.0
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        if delta > 0:
            initial_gains += delta
        else:
            initial_losses -= delta  # store as positive
    avg_gain = initial_gains / period
    avg_loss = initial_losses / period

    # Wilder smoothing for every subsequent bar.
    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0  # all-flat window → 50
    if avg_gain == 0:
        return 0.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def bollinger_bands(
    closes: Sequence[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[float, float, float]:
    """Bollinger Bands at the latest bar.

    Args:
        closes: Close price series in chronological order. Must have
            length ≥ ``period``.
        period: Window for the SMA and stdev. 20 is canonical.
        std_dev: Band width in standard deviations. 2.0 is canonical
            (covers ~95% of moves under a normal distribution).

    Returns:
        ``(lower, middle, upper)`` for the latest bar. ``middle`` is
        the SMA over the window; the bands are ``middle ±
        std_dev × population_std``. Population (not sample) stdev is
        used to match the most common implementation in TA libraries.

    Raises:
        InsufficientDataError: If ``len(closes) < period``.
        ValueError: If ``period <= 0`` or ``std_dev < 0``.
    """
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    if std_dev < 0:
        raise ValueError(f"std_dev must be non-negative, got {std_dev}")
    if len(closes) < period:
        raise InsufficientDataError(
            f"bollinger_bands needs >= {period} closes, got {len(closes)}"
        )

    window = closes[-period:]
    middle = sum(window) / period
    variance = sum((c - middle) ** 2 for c in window) / period
    sigma = math.sqrt(variance)
    spread = std_dev * sigma
    return (middle - spread, middle, middle + spread)

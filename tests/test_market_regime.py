"""Tests for the deterministic market-regime classifier.

Covers the four label outputs and both ``unknown`` branches
(insufficient candles, stale last-candle timestamp). The classifier is
pure-math and synchronous; no exchange or activity-log fixtures are
needed here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.models import OHLCV
from src.runtime.market_regime import (
    DEFAULT_SMA_PERIOD,
    classify_regime,
    classify_regime_detailed,
    timeframe_to_seconds,
)


def _make_candles(
    closes: list[float],
    *,
    timeframe_seconds: int = 4 * 60 * 60,
    last_timestamp: datetime | None = None,
) -> list[OHLCV]:
    """Build ``len(closes)`` OHLCV candles ending at ``last_timestamp``.

    Only ``close`` and ``timestamp`` matter for the classifier — open
    / high / low / volume are filled with the same close value so the
    fixture stays compact.
    """
    if last_timestamp is None:
        last_timestamp = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    candles: list[OHLCV] = []
    n = len(closes)
    for index, close in enumerate(closes):
        ts = last_timestamp - timedelta(
            seconds=timeframe_seconds * (n - 1 - index),
        )
        price = Decimal(str(close))
        candles.append(
            OHLCV(
                timestamp=ts,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=Decimal("1"),
            )
        )
    return candles


def _fresh_now(last_ts: datetime, offset_seconds: int = 60) -> datetime:
    """A wall clock that sits ``offset_seconds`` after the last candle."""
    return last_ts + timedelta(seconds=offset_seconds)


def test_classify_regime_bull_when_close_above_bull_band() -> None:
    # 199 candles at 100, last candle at 103 -> SMA = (100*199 + 103)/200
    # which is still ≈ 100.015; 103 > 100.015 * 1.02 (= 102.015) -> bull.
    closes = [100.0] * 199 + [103.0]
    candles = _make_candles(closes)
    regime = classify_regime(
        candles,
        timeframe="4h",
        now=_fresh_now(candles[-1].timestamp),
    )
    assert regime == "bull"


def test_classify_regime_bear_when_close_below_bear_band() -> None:
    # 199 candles at 100, last candle at 97 -> SMA ≈ 99.985; 97 < 99.985
    # * 0.98 (= 97.985) -> bear.
    closes = [100.0] * 199 + [97.0]
    candles = _make_candles(closes)
    regime = classify_regime(
        candles,
        timeframe="4h",
        now=_fresh_now(candles[-1].timestamp),
    )
    assert regime == "bear"


def test_classify_regime_sideways_when_close_inside_band() -> None:
    # 199 candles at 100, last candle at 101 -> close inside the
    # ±2% neutral band (98 < 101 < 102) -> sideways.
    closes = [100.0] * 199 + [101.0]
    candles = _make_candles(closes)
    regime = classify_regime(
        candles,
        timeframe="4h",
        now=_fresh_now(candles[-1].timestamp),
    )
    assert regime == "sideways"


def test_classify_regime_unknown_when_insufficient_candles() -> None:
    closes = [100.0] * (DEFAULT_SMA_PERIOD - 1)
    candles = _make_candles(closes)
    regime = classify_regime(
        candles,
        timeframe="4h",
        now=_fresh_now(candles[-1].timestamp),
    )
    assert regime == "unknown"


def test_classify_regime_unknown_when_empty_candles() -> None:
    assert classify_regime([], timeframe="4h") == "unknown"


def test_classify_regime_unknown_when_last_candle_is_stale() -> None:
    # 200 candles, all closes equal so SMA == close == 100 -> would
    # be sideways. But the wall clock sits well past 2× the 4h budget
    # from the last candle, so the classifier must downgrade to
    # ``unknown`` instead of returning a stale view as actionable.
    closes = [100.0] * 200
    candles = _make_candles(closes)
    stale_now = candles[-1].timestamp + timedelta(hours=24)
    assert classify_regime(candles, timeframe="4h", now=stale_now) == "unknown"


def test_classify_regime_fresh_within_budget() -> None:
    # Exactly one candle late is still fresh — the budget is 2× the
    # timeframe. This pins the boundary so a single missed close on
    # a slow exchange does not flip the regime to ``unknown``.
    closes = [100.0] * 199 + [103.0]
    candles = _make_candles(closes)
    one_late_now = candles[-1].timestamp + timedelta(hours=4)
    assert (
        classify_regime(candles, timeframe="4h", now=one_late_now) == "bull"
    )


def test_classify_regime_detailed_reports_baseline_and_close() -> None:
    closes = [100.0] * 199 + [103.0]
    candles = _make_candles(closes)
    result = classify_regime_detailed(
        candles,
        timeframe="4h",
        now=_fresh_now(candles[-1].timestamp),
    )
    assert result.regime == "bull"
    assert result.close == Decimal("103")
    assert result.baseline is not None
    # SMA over 199 × 100 + 103 → (19900 + 103) / 200 = 100.015
    assert result.baseline == Decimal("100.015")
    assert result.last_candle_timestamp == candles[-1].timestamp


def test_classify_regime_detailed_marks_insufficient_data_reason() -> None:
    candles = _make_candles([100.0] * 50)
    result = classify_regime_detailed(
        candles,
        timeframe="4h",
        now=_fresh_now(candles[-1].timestamp),
    )
    assert result.regime == "unknown"
    assert result.reason == "insufficient_data"
    assert result.baseline is None
    assert result.close is None


def test_classify_regime_detailed_marks_stale_data_reason() -> None:
    candles = _make_candles([100.0] * 200)
    stale_now = candles[-1].timestamp + timedelta(hours=24)
    result = classify_regime_detailed(candles, timeframe="4h", now=stale_now)
    assert result.regime == "unknown"
    assert result.reason == "stale_data"
    # Stale path still records the last-known close so dashboards can
    # show what was observed when the feed went quiet.
    assert result.close == Decimal("100")
    assert result.baseline is None


def test_classify_regime_custom_bands() -> None:
    # Wider bands (±5%) keep a 103 close that would normally be ``bull``
    # at the default ±2% band inside the neutral zone.
    closes = [100.0] * 199 + [103.0]
    candles = _make_candles(closes)
    regime = classify_regime(
        candles,
        timeframe="4h",
        now=_fresh_now(candles[-1].timestamp),
        bull_band=1.05,
        bear_band=0.95,
    )
    assert regime == "sideways"


def test_classify_regime_rejects_non_positive_sma_period() -> None:
    candles = _make_candles([100.0] * 200)
    with pytest.raises(ValueError, match="sma_period must be positive"):
        classify_regime(
            candles,
            sma_period=0,
            timeframe="4h",
            now=_fresh_now(candles[-1].timestamp),
        )


def test_timeframe_to_seconds_known_and_unknown() -> None:
    assert timeframe_to_seconds("4h") == 4 * 60 * 60
    assert timeframe_to_seconds("1d") == 24 * 60 * 60
    # Unknown timeframe falls back to one hour so the classifier can
    # still answer instead of crashing on a new exchange string.
    assert timeframe_to_seconds("not-a-timeframe") == 60 * 60

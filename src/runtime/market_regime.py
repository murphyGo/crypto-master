"""Deterministic market-regime classifier.

Shared runtime view of the current market condition so the engine can
distinguish bullish, bearish, and sideways environments before deciding
which strategy proposals should be allowed. The classifier is
intentionally pure-math and synchronous: strategies and runtime gates
both consume it, but neither owns the rule.

The classification rule (functional-design spec §1 "Regime Labels"):

- last 2 candles BOTH ``close > SMA(sma_period) * bull_band`` -> ``bull``
- last 2 candles BOTH ``close < SMA(sma_period) * bear_band`` -> ``bear``
- otherwise -> ``sideways``
- insufficient data (< ``sma_period`` candles) -> ``unknown``
- stale data (last-candle timestamp older than ``2 *
  timeframe_seconds`` from ``now``) -> ``unknown``

The two-bar confirmation (DEBT-063) prevents per-cycle regime flapping
when price oscillates around the ±2% band. The ±2% threshold itself is
unchanged so live and backtest regime views stay consistent
(``RobustnessGate._classify_regimes`` in ``src/backtest/validator.py``).

The defaults (``sma_period=200``, ``bull_band=1.02``, ``bear_band=0.98``)
match the existing ``RobustnessGate`` regime classifier in
``src/backtest/validator.py`` so backtest verdicts and live operator
views agree on what "bull" / "bear" / "sideways" mean.

Stale-data rule
---------------

"Stale" is defined as the last candle's ``timestamp`` being older than
``2 * timeframe_seconds`` from the current wall clock. This is the
canonical "one missed candle" budget — a single late close on a slow
exchange is fine, two consecutive late closes mean the market data
pipeline is no longer current and the regime classification cannot be
trusted. Callers that need a different freshness budget pass an explicit
``now`` for testability and a different ``timeframe`` to widen the
window.

Related Requirements:
- FR-029: market-regime view fed into proposal generation
- FR-031: dashboard regime visibility
- FR-045: per-sub-account regime gating
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.models import OHLCV
from src.utils.time import ensure_utc, now_utc

__all__ = [
    "DEFAULT_BEAR_BAND",
    "DEFAULT_BULL_BAND",
    "DEFAULT_SMA_PERIOD",
    "MarketRegime",
    "RegimeClassification",
    "classify_regime",
    "classify_regime_detailed",
    "timeframe_to_seconds",
]


MarketRegime = Literal["bull", "bear", "sideways", "unknown"]

DEFAULT_SMA_PERIOD = 200
DEFAULT_BULL_BAND = 1.02
DEFAULT_BEAR_BAND = 0.98

# Multiplier applied to ``timeframe_seconds`` when deciding whether the
# last candle is stale. Two missed candles is the budget — see
# module docstring "Stale-data rule".
STALE_MULTIPLIER = 2

# Supported timeframe → seconds. Mirrors the keys used elsewhere in the
# trading-math layer (see ``TF_MIN_SL_PCT`` in
# ``src/utils/trading_math.py``). Unknown timeframes fall back to a
# conservative one-hour budget so the classifier never crashes on a new
# timeframe — it just over-reports staleness, which fails closed.
_TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 3 * 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 60 * 60,
    "2h": 2 * 60 * 60,
    "4h": 4 * 60 * 60,
    "6h": 6 * 60 * 60,
    "8h": 8 * 60 * 60,
    "12h": 12 * 60 * 60,
    "1d": 24 * 60 * 60,
    "3d": 3 * 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
}


class RegimeClassification(BaseModel):
    """Structured classifier output for downstream callers.

    The proposal-gating site (``TradingEngine._market_regime_gate``)
    consumes ``regime`` for the allow/block decision and the other
    fields for the spec §4 activity event payload. ``close`` and
    ``baseline`` are ``None`` when the classifier returns ``unknown``
    for insufficient data — there is nothing to report yet.
    """

    regime: MarketRegime
    close: Decimal | None = None
    baseline: Decimal | None = None
    last_candle_timestamp: datetime | None = None
    reason: str | None = None

    model_config = ConfigDict(frozen=True)


def timeframe_to_seconds(timeframe: str) -> int:
    """Translate an exchange timeframe string to seconds.

    Unknown timeframes fall back to one hour. The classifier uses the
    return value for the stale-data budget only, so an unknown
    timeframe over-reports staleness rather than crashing — failing
    closed is the desired behaviour for an unrecognised input.
    """
    return _TIMEFRAME_SECONDS.get(timeframe, 60 * 60)


def classify_regime(
    ohlcv: list[OHLCV],
    *,
    sma_period: int = DEFAULT_SMA_PERIOD,
    bull_band: float = DEFAULT_BULL_BAND,
    bear_band: float = DEFAULT_BEAR_BAND,
    timeframe: str = "4h",
    now: datetime | None = None,
) -> MarketRegime:
    """Classify the current market regime.

    Args:
        ohlcv: Chronologically-ordered candle series. Must contain
            at least ``sma_period`` candles for a non-``unknown``
            classification.
        sma_period: Lookback window for the simple moving average
            baseline. 200 is canonical.
        bull_band: Multiplier on SMA above which ``close`` is
            classified as ``bull``. 1.02 = "2% above SMA".
        bear_band: Multiplier on SMA below which ``close`` is
            classified as ``bear``. 0.98 = "2% below SMA".
        timeframe: Exchange timeframe of the supplied candles. Used
            only for the stale-data check; the SMA math itself is
            timeframe-agnostic.
        now: Optional wall-clock override for the stale-data check.
            Defaults to ``now_utc()``. Tests pass a fixed timestamp
            so the classification is deterministic.

    Returns:
        One of ``"bull"``, ``"bear"``, ``"sideways"``, ``"unknown"``.
    """
    return classify_regime_detailed(
        ohlcv,
        sma_period=sma_period,
        bull_band=bull_band,
        bear_band=bear_band,
        timeframe=timeframe,
        now=now,
    ).regime


def classify_regime_detailed(
    ohlcv: list[OHLCV],
    *,
    sma_period: int = DEFAULT_SMA_PERIOD,
    bull_band: float = DEFAULT_BULL_BAND,
    bear_band: float = DEFAULT_BEAR_BAND,
    timeframe: str = "4h",
    now: datetime | None = None,
) -> RegimeClassification:
    """Classify and also return the inputs the rule consumed.

    Same semantics as :func:`classify_regime` but returns the
    intermediate SMA baseline and last close so the proposal-gating
    activity event can record what the classifier saw. Callers that
    only need the label use :func:`classify_regime`.
    """
    if sma_period <= 0:
        raise ValueError(f"sma_period must be positive, got {sma_period}")

    if len(ohlcv) < sma_period:
        return RegimeClassification(
            regime="unknown",
            reason="insufficient_data",
        )

    last = ohlcv[-1]
    current = ensure_utc(now) if now is not None else now_utc()
    last_ts = ensure_utc(last.timestamp)
    age_seconds = (current - last_ts).total_seconds()
    budget_seconds = STALE_MULTIPLIER * timeframe_to_seconds(timeframe)
    if age_seconds > budget_seconds:
        return RegimeClassification(
            regime="unknown",
            close=last.close,
            last_candle_timestamp=last_ts,
            reason="stale_data",
        )

    closes = ohlcv[-sma_period:]
    sma = sum((c.close for c in closes), Decimal("0")) / Decimal(sma_period)
    bull_threshold = sma * Decimal(str(bull_band))
    bear_threshold = sma * Decimal(str(bear_band))

    # DEBT-063: require the last 2 candles to both sit on the new side
    # of the band before flipping out of ``sideways``. A single-candle
    # band crossing in a chopping market (price oscillating in the
    # 1.5%-2.5% range around SMA(200)) would flap the regime every
    # cycle, repeatedly admitting/blocking the same strategy at the
    # band edges. Two-bar confirmation keeps the ±2% threshold (matches
    # the backtest-side ``RobustnessGate._classify_regimes`` for live /
    # backtest consistency) and changes the rule, not the number. The
    # ``ohlcv[-2]`` access is safe: the ``len(ohlcv) < sma_period``
    # guard above requires at least ``sma_period`` (>=1) candles, and
    # the canonical ``sma_period`` is 200 so two trailing candles are
    # always available. A defensive guard handles the degenerate
    # ``sma_period == 1`` case by falling back to ``sideways`` rather
    # than flipping on a single bar.
    if len(ohlcv) < 2:
        regime: MarketRegime = "sideways"
    else:
        prev_close = ohlcv[-2].close
        if last.close > bull_threshold and prev_close > bull_threshold:
            regime = "bull"
        elif last.close < bear_threshold and prev_close < bear_threshold:
            regime = "bear"
        else:
            regime = "sideways"

    return RegimeClassification(
        regime=regime,
        close=last.close,
        baseline=sma,
        last_candle_timestamp=last_ts,
    )

"""Rolling VWAP band mean-reversion strategy.

Computes a rolling VWAP and volume-weighted standard deviation. In a
non-trending local regime, price extensions beyond the outer bands are
faded back toward VWAP.

Related Requirements:
- FR-001 / FR-002 / FR-003 / FR-004 / FR-005
"""

from datetime import datetime
from decimal import Decimal
from math import sqrt

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, StrategyExecutionError

TECHNIQUE_INFO = {
    "name": "vwap_mean_reversion",
    "version": "1.0.0",
    "description": (
        "VWAP band mean reversion: fade 2-sigma VWAP extensions when "
        "local trend slope is muted."
    ),
    "author": "system",
    "symbols": [],
    "timeframes": ["15m", "1h"],
    "status": "experimental",
    "changelog": "Initial deterministic VWAP mean-reversion candidate",
}


VWAP_PERIOD = 48
STD_MULTIPLIER = 2.0
EMA_PERIOD = 20
SLOPE_LOOKBACK = 5
MAX_TREND_SLOPE = 0.015
STOP_BAND_MULTIPLIER = 2.8


class VWAPMeanReversionStrategy(BaseStrategy):
    """Fade VWAP band extremes only when local slope is muted."""

    @property
    def minimum_candles(self) -> int:
        return max(VWAP_PERIOD, EMA_PERIOD + SLOPE_LOOKBACK)

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "15m",
    ) -> AnalysisResult:
        self.validate_input(ohlcv, min_candles=self.minimum_candles)

        try:
            closes = [float(c.close) for c in ohlcv]
            current_price = closes[-1]
            vwap, sigma = _rolling_vwap_sigma(ohlcv, VWAP_PERIOD)
            ema_now = _ema(closes, EMA_PERIOD)
            ema_prev = _ema(closes[:-SLOPE_LOOKBACK], EMA_PERIOD)
        except Exception as e:
            raise StrategyExecutionError(
                f"VWAP mean reversion analysis failed: {e}",
                strategy_name=self.name,
            ) from e

        upper = vwap + sigma * STD_MULTIPLIER
        lower = vwap - sigma * STD_MULTIPLIER
        trend_slope = abs(ema_now - ema_prev) / current_price
        range_ok = trend_slope <= MAX_TREND_SLOPE

        if current_price < lower and range_ok:
            stop = min(
                current_price * 0.99,
                current_price - max(sigma * 0.8, current_price * 0.005),
            )
            return _directional_result(
                signal="long",
                current_price=current_price,
                stop=stop,
                take_profit=vwap,
                confidence=min(0.9, 0.45 + (lower - current_price) / max(sigma, 1e-9)),
                reasoning=(
                    f"Close {current_price:.2f} below VWAP lower band "
                    f"{lower:.2f}; muted EMA slope {trend_slope:.4f}"
                ),
            )
        if current_price > upper and range_ok:
            stop = max(
                current_price * 1.01,
                current_price + max(sigma * 0.8, current_price * 0.005),
            )
            return _directional_result(
                signal="short",
                current_price=current_price,
                stop=stop,
                take_profit=vwap,
                confidence=min(0.9, 0.45 + (current_price - upper) / max(sigma, 1e-9)),
                reasoning=(
                    f"Close {current_price:.2f} above VWAP upper band "
                    f"{upper:.2f}; muted EMA slope {trend_slope:.4f}"
                ),
            )

        return _neutral_result(
            current_price,
            (
                f"No VWAP reversion: price={current_price:.2f}, "
                f"band=[{lower:.2f}, {upper:.2f}], range_ok={range_ok}"
            ),
        )


def _rolling_vwap_sigma(ohlcv: list[OHLCV], period: int) -> tuple[float, float]:
    window = ohlcv[-period:]
    weighted_sum = 0.0
    volume_sum = 0.0
    typicals = []
    volumes = []
    for candle in window:
        typical = (float(candle.high) + float(candle.low) + float(candle.close)) / 3.0
        volume = float(candle.volume)
        typicals.append(typical)
        volumes.append(volume)
        weighted_sum += typical * volume
        volume_sum += volume
    if volume_sum <= 0:
        raise ValueError("rolling vwap needs positive volume")
    vwap = weighted_sum / volume_sum
    variance = (
        sum(v * (t - vwap) ** 2 for t, v in zip(typicals, volumes, strict=True))
        / volume_sum
    )
    return vwap, sqrt(variance)


def _ema(values: list[float], period: int) -> float:
    if len(values) < period:
        raise ValueError(f"ema needs >= {period} values")
    k = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    for value in values[period:]:
        ema = value * k + ema * (1 - k)
    return ema


def _directional_result(
    *,
    signal: str,
    current_price: float,
    stop: float,
    take_profit: float,
    confidence: float,
    reasoning: str,
) -> AnalysisResult:
    return AnalysisResult(
        signal=signal,  # type: ignore[arg-type]
        confidence=max(0.1, min(1.0, confidence)),
        entry_price=Decimal(str(round(current_price, 2))),
        stop_loss=Decimal(str(round(max(stop, 0.01), 2))),
        take_profit=Decimal(str(round(max(take_profit, 0.01), 2))),
        reasoning=reasoning,
        timestamp=datetime.now(),
    )


def _neutral_result(current_price: float, reason: str) -> AnalysisResult:
    price = Decimal(str(round(current_price, 2)))
    return AnalysisResult(
        signal="neutral",
        confidence=0.3,
        entry_price=price,
        stop_loss=Decimal(str(round(current_price * 0.99, 2))),
        take_profit=Decimal(str(round(current_price * 1.01, 2))),
        reasoning=reason,
        timestamp=datetime.now(),
    )

"""Turtle Soup liquidity reclaim strategy.

Fades failed 20-bar breakouts: a wick through a prior range extreme
followed by a close back inside the range is treated as a liquidity
reclaim, with ATR-buffered risk and a short time-to-live thesis.

Related Requirements:
- FR-001 / FR-002 / FR-003 / FR-004 / FR-005
"""

from datetime import datetime
from decimal import Decimal

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, StrategyExecutionError

TECHNIQUE_INFO = {
    "name": "turtle_soup_reclaim",
    "version": "1.0.0",
    "description": (
        "Turtle Soup reclaim: fade failed 20-bar high/low breakouts "
        "when the candle closes back inside the prior range."
    ),
    "author": "system",
    "symbols": [],
    "timeframes": ["4h", "1d"],
    "status": "experimental",
    "changelog": "Initial deterministic Turtle Soup candidate",
    "counter_trend": True,
}


LOOKBACK = 20
ATR_PERIOD = 14
MIN_STALE_BARS = 3
VOLUME_LOOKBACK = 20
VOLUME_MULTIPLIER = 1.1
STOP_ATR_BUFFER = 0.25
TAKE_PROFIT_R = 2.0


class TurtleSoupReclaimStrategy(BaseStrategy):
    """Fade a reclaimed sweep of the prior 20-bar range."""

    @property
    def minimum_candles(self) -> int:
        return max(LOOKBACK + MIN_STALE_BARS + 2, ATR_PERIOD + 2)

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "4h",
    ) -> AnalysisResult:
        self.validate_input(ohlcv, min_candles=self.minimum_candles)

        try:
            highs = [float(c.high) for c in ohlcv]
            lows = [float(c.low) for c in ohlcv]
            closes = [float(c.close) for c in ohlcv]
            volumes = [float(c.volume) for c in ohlcv]
            current_price = closes[-1]
            prior_highs = highs[-LOOKBACK - 1 : -1]
            prior_lows = lows[-LOOKBACK - 1 : -1]
            prior_high = max(prior_highs)
            prior_low = min(prior_lows)
            high_age = LOOKBACK - 1 - prior_highs.index(prior_high)
            low_age = LOOKBACK - 1 - prior_lows.index(prior_low)
            atr = _atr(highs, lows, closes, ATR_PERIOD)
            avg_volume = sum(volumes[-VOLUME_LOOKBACK - 1 : -1]) / VOLUME_LOOKBACK
            volume_ok = volumes[-1] >= avg_volume * VOLUME_MULTIPLIER
        except Exception as e:
            raise StrategyExecutionError(
                f"Turtle Soup reclaim analysis failed: {e}",
                strategy_name=self.name,
            ) from e

        swept_low_reclaimed = (
            lows[-1] < prior_low
            and current_price > prior_low
            and low_age >= MIN_STALE_BARS
            and volume_ok
        )
        swept_high_rejected = (
            highs[-1] > prior_high
            and current_price < prior_high
            and high_age >= MIN_STALE_BARS
            and volume_ok
        )

        if swept_low_reclaimed:
            stop = lows[-1] - atr * STOP_ATR_BUFFER
            return _directional_result(
                signal="long",
                current_price=current_price,
                stop=stop,
                take_profit=current_price + (current_price - stop) * TAKE_PROFIT_R,
                confidence=0.72,
                reasoning=(
                    f"Swept {LOOKBACK}-bar low {prior_low:.2f} and reclaimed; "
                    f"volume {volumes[-1]:.0f}/{avg_volume:.0f}"
                ),
            )
        if swept_high_rejected:
            stop = highs[-1] + atr * STOP_ATR_BUFFER
            return _directional_result(
                signal="short",
                current_price=current_price,
                stop=stop,
                take_profit=current_price - (stop - current_price) * TAKE_PROFIT_R,
                confidence=0.72,
                reasoning=(
                    f"Swept {LOOKBACK}-bar high {prior_high:.2f} and rejected; "
                    f"volume {volumes[-1]:.0f}/{avg_volume:.0f}"
                ),
            )

        return _neutral_result(
            current_price,
            (
                f"No Turtle Soup reclaim: prior range "
                f"[{prior_low:.2f}, {prior_high:.2f}], volume_ok={volume_ok}"
            ),
        )


def _atr(
    highs: list[float], lows: list[float], closes: list[float], period: int
) -> float:
    if len(closes) < period + 1:
        raise ValueError(f"atr needs >= {period + 1} candles")
    ranges = []
    for i in range(1, len(closes)):
        ranges.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    return sum(ranges[-period:]) / period


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
        confidence=confidence,
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

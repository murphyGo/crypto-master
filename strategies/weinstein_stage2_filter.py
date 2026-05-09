"""Weinstein Stage 2 / Stage 4 regime strategy.

Approximates Stan Weinstein's stage analysis with OHLCV-only rules.
It emits a long signal for Stage 2 breakouts above a rising long
moving average and a short signal for Stage 4 breakdowns below a
falling long moving average.

Related Requirements:
- FR-001 / FR-002 / FR-003 / FR-004 / FR-005
"""

from datetime import datetime
from decimal import Decimal

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, StrategyExecutionError

TECHNIQUE_INFO = {
    "name": "weinstein_stage2_filter",
    "version": "1.0.0",
    "description": (
        "Weinstein stage regime candidate: long Stage 2 breakouts above "
        "a rising long MA, short Stage 4 breakdowns below a falling MA."
    ),
    "author": "system",
    "symbols": [],
    "timeframes": ["1d"],
    "status": "experimental",
    "changelog": "Initial deterministic Weinstein stage candidate",
    # 1d Stage-2 / Stage-4 swing: 60 bars (~2 months) is enough for
    # a regime move to mature without holding through a full cycle.
    "max_bars_held": 60,
}


MA_PERIOD = 150
SLOPE_LOOKBACK = 20
BASE_LOOKBACK = 30
VOLUME_LOOKBACK = 20
VOLUME_MULTIPLIER = 1.2
STOP_BUFFER = 0.01
TAKE_PROFIT_R = 2.0


class WeinsteinStage2FilterStrategy(BaseStrategy):
    """Trade only clear Stage 2 breakouts or Stage 4 breakdowns."""

    @property
    def minimum_candles(self) -> int:
        return MA_PERIOD + SLOPE_LOOKBACK + 1

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1d",
    ) -> AnalysisResult:
        self.validate_input(ohlcv, min_candles=self.minimum_candles)

        try:
            closes = [float(c.close) for c in ohlcv]
            highs = [float(c.high) for c in ohlcv]
            lows = [float(c.low) for c in ohlcv]
            volumes = [float(c.volume) for c in ohlcv]
            current_price = closes[-1]
            ma_now = _sma(closes, MA_PERIOD)
            ma_prev = _sma(closes[:-SLOPE_LOOKBACK], MA_PERIOD)
            resistance = max(highs[-BASE_LOOKBACK - 1 : -1])
            support = min(lows[-BASE_LOOKBACK - 1 : -1])
            avg_volume = sum(volumes[-VOLUME_LOOKBACK - 1 : -1]) / VOLUME_LOOKBACK
        except Exception as e:
            raise StrategyExecutionError(
                f"Weinstein stage analysis failed: {e}",
                strategy_name=self.name,
            ) from e

        volume_ok = volumes[-1] >= avg_volume * VOLUME_MULTIPLIER
        stage2 = (
            current_price > ma_now
            and ma_now > ma_prev
            and current_price > resistance
            and volume_ok
        )
        stage4 = (
            current_price < ma_now
            and ma_now < ma_prev
            and current_price < support
            and volume_ok
        )

        if stage2:
            stop = min(support, ma_now) * (1 - STOP_BUFFER)
            return _directional_result(
                signal="long",
                current_price=current_price,
                stop=stop,
                take_profit=current_price + (current_price - stop) * TAKE_PROFIT_R,
                confidence=0.75,
                reasoning=(
                    f"Stage 2 breakout above {resistance:.2f}; "
                    f"SMA{MA_PERIOD} rising {ma_prev:.2f}->{ma_now:.2f}, "
                    f"volume {volumes[-1]:.0f}/{avg_volume:.0f}"
                ),
            )
        if stage4:
            stop = max(resistance, ma_now) * (1 + STOP_BUFFER)
            return _directional_result(
                signal="short",
                current_price=current_price,
                stop=stop,
                take_profit=current_price - (stop - current_price) * TAKE_PROFIT_R,
                confidence=0.75,
                reasoning=(
                    f"Stage 4 breakdown below {support:.2f}; "
                    f"SMA{MA_PERIOD} falling {ma_prev:.2f}->{ma_now:.2f}, "
                    f"volume {volumes[-1]:.0f}/{avg_volume:.0f}"
                ),
            )

        return _neutral_result(
            current_price,
            (
                f"No Weinstein stage trigger: price={current_price:.2f}, "
                f"SMA{MA_PERIOD}={ma_now:.2f}, volume_ok={volume_ok}"
            ),
        )


def _sma(values: list[float], period: int) -> float:
    if len(values) < period:
        raise ValueError(f"sma needs >= {period} values")
    return sum(values[-period:]) / period


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
        stop_loss=Decimal(str(round(current_price * 0.98, 2))),
        take_profit=Decimal(str(round(current_price * 1.02, 2))),
        reasoning=reason,
        timestamp=datetime.now(),
    )

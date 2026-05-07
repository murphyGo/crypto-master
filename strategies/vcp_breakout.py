"""Crypto Minervini-style VCP breakout strategy.

Deterministic OHLCV-only candidate inspired by Mark Minervini's trend
template and volatility contraction pattern. It looks for a strong
uptrend, recent range/ATR contraction, and a volume-backed pivot
breakout.

Related Requirements:
- FR-001 / FR-002 / FR-003 / FR-004 / FR-005
"""

from datetime import datetime
from decimal import Decimal

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, StrategyExecutionError

TECHNIQUE_INFO = {
    "name": "vcp_breakout",
    "version": "1.0.0",
    "description": (
        "Crypto Minervini VCP breakout: trend-template alignment, "
        "volatility contraction, pivot breakout, and volume expansion."
    ),
    "author": "system",
    "symbols": [],
    "timeframes": ["4h", "1d"],
    "status": "experimental",
    "changelog": "Initial deterministic VCP candidate",
}


EMA_FAST = 50
EMA_MID = 150
EMA_SLOW = 200
EMA_SLOPE_LOOKBACK = 20
HIGH_LOOKBACK = 120
LOW_LOOKBACK = 120
PIVOT_LOOKBACK = 20
ATR_FAST = 10
ATR_SLOW = 40
VOLUME_LOOKBACK = 20
VOLUME_MULTIPLIER = 1.4
CONTRACTION_RATIO = 0.8
STOP_BUFFER_ATR = 0.5
TAKE_PROFIT_R = 2.5


class VCPBreakoutStrategy(BaseStrategy):
    """Long when a contracted uptrend resolves through a pivot on volume."""

    @property
    def minimum_candles(self) -> int:
        return max(EMA_SLOW + EMA_SLOPE_LOOKBACK, HIGH_LOOKBACK + 1)

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "4h",
    ) -> AnalysisResult:
        self.validate_input(ohlcv, min_candles=self.minimum_candles)

        try:
            closes = [float(c.close) for c in ohlcv]
            highs = [float(c.high) for c in ohlcv]
            lows = [float(c.low) for c in ohlcv]
            volumes = [float(c.volume) for c in ohlcv]
            current_price = closes[-1]

            ema_fast = _ema(closes, EMA_FAST)
            ema_mid = _ema(closes, EMA_MID)
            ema_slow = _ema(closes, EMA_SLOW)
            ema_slow_prev = _ema(closes[:-EMA_SLOPE_LOOKBACK], EMA_SLOW)
            recent_high = max(highs[-HIGH_LOOKBACK:])
            recent_low = min(lows[-LOW_LOOKBACK:])
            pivot = max(highs[-PIVOT_LOOKBACK - 1 : -1])
            pivot_floor = min(lows[-PIVOT_LOOKBACK - 1 : -1])
            # VCP contraction is evaluated before the breakout bar; the
            # breakout expansion itself should not disqualify the setup.
            atr_fast = _atr(highs[:-1], lows[:-1], closes[:-1], ATR_FAST)
            atr_slow = _atr(highs, lows, closes, ATR_SLOW)
            avg_volume = sum(volumes[-VOLUME_LOOKBACK - 1 : -1]) / VOLUME_LOOKBACK
        except Exception as e:
            raise StrategyExecutionError(
                f"VCP breakout analysis failed: {e}",
                strategy_name=self.name,
            ) from e

        trend_ok = (
            current_price > ema_fast > ema_mid > ema_slow
            and ema_slow > ema_slow_prev
            and current_price >= recent_high * 0.75
            and current_price >= recent_low * 1.25
        )
        contraction_ok = atr_fast <= atr_slow * CONTRACTION_RATIO
        breakout_ok = (
            current_price > pivot and volumes[-1] >= avg_volume * VOLUME_MULTIPLIER
        )

        if not (trend_ok and contraction_ok and breakout_ok):
            return _neutral_result(
                current_price,
                (
                    "No VCP breakout: "
                    f"trend={trend_ok}, contraction={contraction_ok}, "
                    f"breakout={breakout_ok}"
                ),
            )

        entry = Decimal(str(round(current_price, 2)))
        stop = min(pivot_floor, current_price - atr_fast * STOP_BUFFER_ATR)
        stop_loss = Decimal(str(round(stop, 2)))
        risk = current_price - float(stop_loss)
        take_profit = Decimal(str(round(current_price + risk * TAKE_PROFIT_R, 2)))
        confidence = min(
            0.95,
            0.45
            + (current_price - pivot) / current_price * 10
            + min(0.25, volumes[-1] / avg_volume / 10),
        )

        return AnalysisResult(
            signal="long",
            confidence=max(0.1, confidence),
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=(
                f"VCP breakout above pivot {pivot:.2f}; EMA "
                f"{EMA_FAST}/{EMA_MID}/{EMA_SLOW} aligned, ATR contraction "
                f"{atr_fast:.2f}/{atr_slow:.2f}, volume {volumes[-1]:.0f} "
                f"vs avg {avg_volume:.0f}"
            ),
            timestamp=datetime.now(),
        )


def _ema(values: list[float], period: int) -> float:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        raise ValueError(f"ema needs >= {period} values")
    k = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    for value in values[period:]:
        ema = value * k + ema * (1 - k)
    return ema


def _atr(
    highs: list[float], lows: list[float], closes: list[float], period: int
) -> float:
    if len(closes) < period + 1:
        raise ValueError(f"atr needs >= {period + 1} candles")
    true_ranges = []
    for i in range(1, len(closes)):
        true_ranges.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    return sum(true_ranges[-period:]) / period


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

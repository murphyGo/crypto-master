"""Raschke Holy Grail pullback strategy.

Uses ADX to identify a strong trend, then enters when a pullback into
EMA20 resumes through the prior bar. The setup is intentionally
deterministic and OHLCV-only for baseline backtesting.

Related Requirements:
- FR-001 / FR-002 / FR-003 / FR-004 / FR-005
"""

from datetime import datetime
from decimal import Decimal

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, StrategyExecutionError
from src.strategy.indicators import atr as _atr
from src.strategy.indicators import ema as _ema

TECHNIQUE_INFO = {
    "name": "raschke_holy_grail",
    "version": "1.0.0",
    "description": (
        "Raschke Holy Grail: ADX-confirmed trend pullback into EMA20 "
        "with breakout resumption."
    ),
    "author": "system",
    "symbols": [],
    "timeframes": ["1h", "4h"],
    "status": "experimental",
    "changelog": "Initial deterministic Holy Grail pullback candidate",
}


ADX_PERIOD = 14
EMA_PERIOD = 20
ATR_PERIOD = 14
ADX_THRESHOLD = 25.0
EMA_TOUCH_TOLERANCE = 0.004
TAKE_PROFIT_R = 2.0


class RaschkeHolyGrailStrategy(BaseStrategy):
    """Enter trend pullbacks when ADX confirms a strong trend."""

    @property
    def minimum_candles(self) -> int:
        return max(EMA_PERIOD, ADX_PERIOD * 3, ATR_PERIOD + 2)

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
    ) -> AnalysisResult:
        self.validate_input(ohlcv, min_candles=self.minimum_candles)

        try:
            highs = [float(c.high) for c in ohlcv]
            lows = [float(c.low) for c in ohlcv]
            closes = [float(c.close) for c in ohlcv]
            current_price = closes[-1]
            previous = ohlcv[-2]
            ema_now = _ema(closes, EMA_PERIOD)
            ema_prev = _ema(closes[:-1], EMA_PERIOD)
            adx, plus_di, minus_di = _adx(highs, lows, closes, ADX_PERIOD)
            atr = _atr(highs, lows, closes, ATR_PERIOD)
        except Exception as e:
            raise StrategyExecutionError(
                f"Raschke Holy Grail analysis failed: {e}",
                strategy_name=self.name,
            ) from e

        prev_low = float(previous.low)
        prev_high = float(previous.high)
        bullish_trend = (
            adx >= ADX_THRESHOLD and plus_di > minus_di and ema_now > ema_prev
        )
        bearish_trend = (
            adx >= ADX_THRESHOLD and minus_di > plus_di and ema_now < ema_prev
        )
        pulled_back_to_ema = prev_low <= ema_now * (
            1 + EMA_TOUCH_TOLERANCE
        ) and prev_high >= ema_now * (1 - EMA_TOUCH_TOLERANCE)

        if bullish_trend and pulled_back_to_ema and current_price > prev_high:
            stop = min(prev_low, current_price - atr)
            return _directional_result(
                signal="long",
                current_price=current_price,
                stop=stop,
                take_profit=current_price + (current_price - stop) * TAKE_PROFIT_R,
                confidence=min(0.9, 0.55 + (adx - ADX_THRESHOLD) / 100),
                reasoning=(
                    f"Holy Grail long: ADX={adx:.2f}, +DI={plus_di:.2f}, "
                    f"EMA{EMA_PERIOD} rising and pullback reclaimed"
                ),
            )
        if bearish_trend and pulled_back_to_ema and current_price < prev_low:
            stop = max(prev_high, current_price + atr)
            return _directional_result(
                signal="short",
                current_price=current_price,
                stop=stop,
                take_profit=current_price - (stop - current_price) * TAKE_PROFIT_R,
                confidence=min(0.9, 0.55 + (adx - ADX_THRESHOLD) / 100),
                reasoning=(
                    f"Holy Grail short: ADX={adx:.2f}, -DI={minus_di:.2f}, "
                    f"EMA{EMA_PERIOD} falling and pullback rejected"
                ),
            )

        return _neutral_result(
            current_price,
            (
                f"No Holy Grail trigger: ADX={adx:.2f}, +DI={plus_di:.2f}, "
                f"-DI={minus_di:.2f}, pulled_back={pulled_back_to_ema}"
            ),
        )


def _adx(
    highs: list[float], lows: list[float], closes: list[float], period: int
) -> tuple[float, float, float]:
    if len(closes) < period * 2 + 1:
        raise ValueError(f"adx needs >= {period * 2 + 1} candles")

    true_ranges = []
    plus_dm = []
    minus_dm = []
    for i in range(1, len(closes)):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
        true_ranges.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )

    dx_values = []
    for end in range(period, len(true_ranges) + 1):
        tr_sum = sum(true_ranges[end - period : end])
        if tr_sum == 0:
            dx_values.append(0.0)
            continue
        plus_di = 100.0 * sum(plus_dm[end - period : end]) / tr_sum
        minus_di = 100.0 * sum(minus_dm[end - period : end]) / tr_sum
        denom = plus_di + minus_di
        dx_values.append(0.0 if denom == 0 else 100.0 * abs(plus_di - minus_di) / denom)

    adx = sum(dx_values[-period:]) / period
    tr_sum = sum(true_ranges[-period:])
    plus_di = 100.0 * sum(plus_dm[-period:]) / tr_sum if tr_sum else 0.0
    minus_di = 100.0 * sum(minus_dm[-period:]) / tr_sum if tr_sum else 0.0
    return adx, plus_di, minus_di


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

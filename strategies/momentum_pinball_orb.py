"""Momentum Pinball opening-range breakout strategy.

The setup combines a daily mean-reversion precursor with an intraday
opening-range breakout. A low daily pinball reading prepares a long
breakout on the next session; a high reading prepares a short
breakdown.

Related Requirements:
- FR-001 / FR-002 / FR-003 / FR-004 / FR-005
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from decimal import Decimal

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, StrategyExecutionError

TECHNIQUE_INFO = {
    "name": "momentum_pinball_orb",
    "version": "1.0.0",
    "description": (
        "Momentum Pinball ORB: daily RSI(3) of ROC(1) precursor plus "
        "next-session opening-range breakout."
    ),
    "author": "system",
    "symbols": [],
    "timeframes": ["15m", "1h"],
    "status": "experimental",
    "changelog": "Initial deterministic Momentum Pinball ORB candidate",
    # ORB on 15m: 96 bars (~24h) is the day-trade ceiling for an
    # opening-range thesis before the breakout reading is stale.
    "max_bars_held": 96,
}


PINBALL_PERIOD = 3
OVERSOLD = 30.0
OVERBOUGHT = 70.0
OPENING_RANGE_BARS = 4
MIN_DAILY_CLOSES = PINBALL_PERIOD + 2
TAKE_PROFIT_R = 1.8


class MomentumPinballORBStrategy(BaseStrategy):
    """Trade opening-range breakouts after a daily pinball extreme."""

    @property
    def minimum_candles(self) -> int:
        return 30

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "15m",
    ) -> AnalysisResult:
        self.validate_input(ohlcv, min_candles=self.minimum_candles)

        try:
            current_price = float(ohlcv[-1].close)
            session = _latest_session(ohlcv)
            if len(session) <= OPENING_RANGE_BARS:
                return _neutral_result(
                    current_price,
                    f"Latest session has only {len(session)} candles",
                )

            daily_closes = _completed_daily_closes_before_latest_session(ohlcv)
            if len(daily_closes) < MIN_DAILY_CLOSES:
                return _neutral_result(
                    current_price,
                    f"Need >= {MIN_DAILY_CLOSES} completed daily closes",
                )

            pinball = _pinball(daily_closes, PINBALL_PERIOD)
            opening_range = session[:OPENING_RANGE_BARS]
            range_high = max(float(c.high) for c in opening_range)
            range_low = min(float(c.low) for c in opening_range)
        except Exception as e:
            raise StrategyExecutionError(
                f"Momentum Pinball ORB analysis failed: {e}",
                strategy_name=self.name,
            ) from e

        if pinball < OVERSOLD and current_price > range_high:
            return _directional_result(
                signal="long",
                current_price=current_price,
                stop=range_low,
                take_profit=current_price + (current_price - range_low) * TAKE_PROFIT_R,
                confidence=min(0.9, 0.55 + (OVERSOLD - pinball) / 100),
                reasoning=(
                    f"Pinball {pinball:.2f} oversold; price broke opening "
                    f"range high {range_high:.2f}"
                ),
            )
        if pinball > OVERBOUGHT and current_price < range_low:
            return _directional_result(
                signal="short",
                current_price=current_price,
                stop=range_high,
                take_profit=current_price
                - (range_high - current_price) * TAKE_PROFIT_R,
                confidence=min(0.9, 0.55 + (pinball - OVERBOUGHT) / 100),
                reasoning=(
                    f"Pinball {pinball:.2f} overbought; price broke opening "
                    f"range low {range_low:.2f}"
                ),
            )

        return _neutral_result(
            current_price,
            (
                f"No pinball ORB trigger: pinball={pinball:.2f}, "
                f"range=[{range_low:.2f}, {range_high:.2f}]"
            ),
        )


def _latest_session(ohlcv: list[OHLCV]) -> list[OHLCV]:
    session_date = ohlcv[-1].timestamp.date()
    return [c for c in ohlcv if c.timestamp.date() == session_date]


def _completed_daily_closes_before_latest_session(ohlcv: list[OHLCV]) -> list[float]:
    latest_date = ohlcv[-1].timestamp.date()
    by_day: OrderedDict[object, OHLCV] = OrderedDict()
    for candle in ohlcv:
        day = candle.timestamp.date()
        if day >= latest_date:
            continue
        by_day[day] = candle
    return [float(c.close) for c in by_day.values()]


def _pinball(daily_closes: list[float], period: int) -> float:
    roc = [
        (daily_closes[i] - daily_closes[i - 1]) / daily_closes[i - 1] * 100
        for i in range(1, len(daily_closes))
    ]
    return _rsi(roc, period)


def _rsi(values: list[float], period: int) -> float:
    if len(values) < period + 1:
        raise ValueError(f"rsi needs >= {period + 1} values")
    gains = []
    losses = []
    for i in range(1, len(values)):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    if avg_gain == 0:
        return 0.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


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

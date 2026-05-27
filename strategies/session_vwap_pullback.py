"""Session VWAP pullback continuation strategy.

v1.1.0: anchor sessions at the London open (07:00 UTC) instead of UTC
midnight, and require ``MIN_SESSION_CANDLES = 16`` (~4h on 15m) before
firing. Long setups require an uptrend, a pullback into VWAP, and a
fresh close back above the prior candle. Short setups mirror.

Related Requirements:
- FR-001 / FR-002 / FR-003 / FR-004 / FR-005
"""

from datetime import datetime, timedelta
from decimal import Decimal

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, StrategyExecutionError

TECHNIQUE_INFO = {
    "name": "session_vwap_pullback",
    "version": "1.1.0",
    "description": (
        "Session VWAP continuation: trade the trend when price pulls "
        "back into VWAP and reclaims momentum. Sessions anchored at "
        "the London open (07:00 UTC); requires >=16 candles of "
        "post-anchor data before firing."
    ),
    "author": "system",
    "symbols": [],
    "timeframes": ["15m", "1h"],
    "status": "experimental",
    "changelog": (
        "1.1.0: anchor sessions at 07:00 UTC London open instead of "
        "UTC midnight (Asia open mid-session); raise "
        "MIN_SESSION_CANDLES 6 -> 16 so VWAP has >=4h of statistical "
        "mass on 15m before firing. 12-day Fly paper data showed early "
        "post-midnight signals fading low-strength sessions. "
        "1.0.0: Initial deterministic VWAP pullback candidate."
    ),
    "counter_trend": True,
    # Approximate "close by end of session": the strategy doesn't
    # natively know session boundaries, so 96 bars (~24h on 15m)
    # caps the stale-pullback case without truncating valid swings.
    "max_bars_held": 96,
}


EMA_PERIOD = 20
ATR_PERIOD = 14
# v1.1.0: 16 candles ~ 4h on 15m. Earlier sessions had <6h of mass
# before firing, leaving VWAP statistically weak. London-open anchor
# combined with 16-candle minimum gives the first signal at ~11:00
# UTC each day (anchor + 4h).
MIN_SESSION_CANDLES = 16
VWAP_TOUCH_TOLERANCE = 0.002
TAKE_PROFIT_R = 1.8

# v1.1.0: anchor sessions at the London open. Crypto is 24/7 but
# institutional flow and effective liquidity step-changes around
# the London cash open; UTC midnight (Asia open mid-session) was
# arbitrary and anchored every session in low-mass conditions.
SESSION_ANCHOR_HOUR_UTC = 7


class SessionVWAPPullbackStrategy(BaseStrategy):
    """Continue a VWAP-supported intraday trend."""

    @property
    def minimum_candles(self) -> int:
        return EMA_PERIOD + ATR_PERIOD + MIN_SESSION_CANDLES

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "15m",
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
        current_price: Decimal | None = None,
    ) -> AnalysisResult:
        self.validate_input(ohlcv, min_candles=self.minimum_candles)

        try:
            session = _latest_session(ohlcv)
            if len(session) < MIN_SESSION_CANDLES:
                return _neutral_result(
                    float(ohlcv[-1].close),
                    f"Latest VWAP session has only {len(session)} candles",
                )
            closes = [float(c.close) for c in ohlcv]
            highs = [float(c.high) for c in ohlcv]
            lows = [float(c.low) for c in ohlcv]
            current_price = closes[-1]
            previous = ohlcv[-2]
            vwap = _vwap(session)
            ema_now = _ema(closes, EMA_PERIOD)
            ema_prev = _ema(closes[:-1], EMA_PERIOD)
            atr = _atr(highs, lows, closes, ATR_PERIOD)
        except Exception as e:
            raise StrategyExecutionError(
                f"Session VWAP pullback analysis failed: {e}",
                strategy_name=self.name,
            ) from e

        prev_low = float(previous.low)
        prev_high = float(previous.high)
        long_setup = (
            current_price > vwap
            and ema_now > ema_prev
            and prev_low <= vwap * (1 + VWAP_TOUCH_TOLERANCE)
            and current_price > prev_high
        )
        short_setup = (
            current_price < vwap
            and ema_now < ema_prev
            and prev_high >= vwap * (1 - VWAP_TOUCH_TOLERANCE)
            and current_price < prev_low
        )

        if long_setup:
            stop = min(vwap - atr * 0.25, prev_low)
            return _directional_result(
                signal="long",
                current_price=current_price,
                stop=float(stop),
                take_profit=current_price
                + (current_price - float(stop)) * TAKE_PROFIT_R,
                confidence=0.7,
                reasoning=(
                    f"Uptrend VWAP pullback reclaimed prior high; "
                    f"VWAP={vwap:.2f}, EMA{EMA_PERIOD} rising"
                ),
            )
        if short_setup:
            stop = max(vwap + atr * 0.25, prev_high)
            return _directional_result(
                signal="short",
                current_price=current_price,
                stop=float(stop),
                take_profit=current_price
                - (float(stop) - current_price) * TAKE_PROFIT_R,
                confidence=0.7,
                reasoning=(
                    f"Downtrend VWAP pullback rejected prior low; "
                    f"VWAP={vwap:.2f}, EMA{EMA_PERIOD} falling"
                ),
            )

        return _neutral_result(
            current_price,
            f"No VWAP pullback continuation: price={current_price:.2f}, vwap={vwap:.2f}",
        )


def _latest_session(ohlcv: list[OHLCV]) -> list[OHLCV]:
    """Filter candles to the latest London-open-anchored 24h session.

    The session begins at the most recent ``SESSION_ANCHOR_HOUR_UTC``
    that is <= the latest candle's timestamp. If the anchor hour has
    not yet occurred today, falls back to yesterday's anchor.
    """
    last_ts = ohlcv[-1].timestamp
    anchor = last_ts.replace(
        hour=SESSION_ANCHOR_HOUR_UTC, minute=0, second=0, microsecond=0
    )
    if anchor > last_ts:
        anchor -= timedelta(days=1)
    return [c for c in ohlcv if c.timestamp >= anchor]


def _typical(candle: OHLCV) -> float:
    return (float(candle.high) + float(candle.low) + float(candle.close)) / 3.0


def _vwap(candles: list[OHLCV]) -> float:
    volume = sum(float(c.volume) for c in candles)
    if volume <= 0:
        raise ValueError("vwap needs positive session volume")
    return sum(_typical(c) * float(c.volume) for c in candles) / volume


def _ema(values: list[float], period: int) -> float:
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
        stop_loss=Decimal(str(round(stop, 2))),
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

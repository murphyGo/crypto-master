"""Crypto Minervini-style VCP breakout strategy.

Deterministic OHLCV-only candidate inspired by Mark Minervini's trend
template and volatility contraction pattern. It looks for a strong
uptrend, recent range/ATR contraction, and a volume-backed pivot
breakout.

v1.1.0: relaxed for crypto cycles. Dropped EMA200 from the trend
template (EMA50 > EMA150 alignment is sufficient on 4h crypto where
a 200-period EMA is ~33 days and rarely satisfied). Slope check now
uses EMA150 instead of EMA200 (more responsive to crypto regime
flips). CONTRACTION_RATIO 0.8 -> 0.9 and VOLUME_MULTIPLIER 1.4 -> 1.2
make the contraction + breakout-volume gate less restrictive without
abandoning the core thesis.

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
    "name": "vcp_breakout",
    "version": "1.1.0",
    "description": (
        "Crypto Minervini VCP breakout: EMA50/EMA150 trend template, "
        "volatility contraction, pivot breakout, and volume expansion."
    ),
    "author": "system",
    "symbols": [],
    "timeframes": ["4h", "1d"],
    "status": "experimental",
    "changelog": (
        "1.1.0: drop EMA200 from trend template (rarely satisfied "
        "on 4h crypto cycles); slope check moved to EMA150; "
        "CONTRACTION_RATIO 0.8 -> 0.9; VOLUME_MULTIPLIER 1.4 -> 1.2. "
        "12-day Fly paper data showed zero fires under v1.0.0 -- the "
        "compound AND of strict trend + tight contraction + strong "
        "volume was structurally unattainable. "
        "1.0.0: initial deterministic VCP candidate."
    ),
    # 4h VCP swing: 84 bars (~2 weeks) captures the typical
    # post-pivot move while still cutting late-stage drift.
    "max_bars_held": 84,
}


EMA_FAST = 50
EMA_MID = 150
EMA_SLOPE_LOOKBACK = 20
HIGH_LOOKBACK = 120
LOW_LOOKBACK = 120
PIVOT_LOOKBACK = 20
ATR_FAST = 10
ATR_SLOW = 40
VOLUME_LOOKBACK = 20
# v1.1.0: relaxed from 1.4. Crypto breakout bars often print with
# only 1.1-1.3x volume (24/7 markets dilute the prior-bar baseline);
# 1.4x was structurally unattainable on the 12-day Fly run.
VOLUME_MULTIPLIER = 1.2
# v1.1.0: relaxed from 0.8. True Minervini-style 3-2-1 contractions
# are rare in crypto's noisier ATR; 0.9 still requires a measurable
# contraction without demanding an equity-style coil.
CONTRACTION_RATIO = 0.9
STOP_BUFFER_ATR = 0.5
TAKE_PROFIT_R = 2.5


class VCPBreakoutStrategy(BaseStrategy):
    """Long when a contracted uptrend resolves through a pivot on volume."""

    @property
    def minimum_candles(self) -> int:
        # v1.1.0: was max(EMA_SLOW + EMA_SLOPE_LOOKBACK, HIGH_LOOKBACK + 1)
        # = 220. Dropping EMA_SLOW lets the strategy fire after 170 candles
        # (EMA_MID + EMA_SLOPE_LOOKBACK) -- ~28 days on 4h instead of 37.
        return max(EMA_MID + EMA_SLOPE_LOOKBACK, HIGH_LOOKBACK + 1)

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "4h",
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
        current_price: Decimal | None = None,
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
            # v1.1.0: slope check now anchored on EMA_MID (was EMA_SLOW).
            # EMA_MID inflects ~33% faster, catching crypto regime flips
            # before the slow EMA confirms.
            ema_mid_prev = _ema(closes[:-EMA_SLOPE_LOOKBACK], EMA_MID)
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
            # v1.1.0: dropped `> ema_slow` -- on 4h crypto the 200-period
            # EMA is ~33 days, often unsatisfied even mid-bull.
            current_price > ema_fast > ema_mid
            and ema_mid > ema_mid_prev
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
                f"{EMA_FAST}/{EMA_MID} aligned, ATR contraction "
                f"{atr_fast:.2f}/{atr_slow:.2f}, volume {volumes[-1]:.0f} "
                f"vs avg {avg_volume:.0f}"
            ),
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

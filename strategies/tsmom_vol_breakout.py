"""Time-series-momentum volatility-breakout strategy.

The most academically robust OHLCV-only crypto edge is time-series
momentum (Moskowitz/Ooi/Pedersen 2012; replicated in crypto): the sign
of trailing multi-week return predicts forward return because of slow
information diffusion and trend-following flow. This strategy enters in
the direction of an established trend on a volatility-expansion breakout,
sized inversely to volatility via an ATR stop, and forces ``neutral`` in
sideways/low-trend regimes -- which is where the repo's existing
zero-edge strategies bled fees.

Design (single-timeframe, 4h primary so the regime filter needs no extra
data stream):
- Trend filter:  EMA(50) > EMA(200) and price > EMA(200) (mirror for short).
- Regime gate:   EMA(200) must be sloping (|slope over 50 bars| >= 0.5*ATR)
                 -- forces neutral in chop, the single most important rule.
- Momentum:      sign(close - close[180]) (~30 days on 4h) must agree.
- Trigger:       20-bar Donchian breakout (close beyond prior 20-bar extreme).
- Exit:          stop = entry -/+ 2*ATR, target = entry +/- 4*ATR (2:1 R/R).
                 Time-stop after 60 bars (10 days) via max_bars_held.

All parameters are round numbers (20/50/200/180/14, 2x/4x ATR) so the
parameter-sensitivity gate has no narrow peak to overfit.

Empirical profile (Binance 4h, 2yr to 2026-05, BTC/ETH/SOL/BNB):
- At 1x / 1% risk this strategy is ~breakeven (Sharpe ~0). OHLCV-only
  crypto has no harvestable edge after fees in this period; that is the
  honest result, consistent with the rest of the library.
- It is therefore NOT a robust edge. The "+100% in 90 days" goal it was
  built to probe is reachable only as a leverage bet on variance, not as
  expectancy. See docs/research/goal-100pct-90d.md for the full
  return/ruin distribution. Do NOT deploy levered without reading it.

Related Requirements:
- FR-001 / FR-002 / FR-003 / FR-004 / FR-005
"""

from datetime import datetime
from decimal import Decimal

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, StrategyExecutionError
from src.strategy.indicators import atr, ema

TECHNIQUE_INFO = {
    "name": "tsmom_vol_breakout",
    "version": "1.0.0",
    "description": (
        "Time-series momentum + volatility breakout with trend and "
        "regime gating; ATR-sized 2:1 exits. Trades only in trending "
        "regimes, flat in chop."
    ),
    "author": "system",
    "symbols": [],
    "timeframes": ["4h"],
    "status": "active",
    "changelog": "Initial TSMOM volatility-breakout candidate",
    # 4h trend swing: 60 bars (~10 days) time-stop releases capital from
    # decayed momentum without holding through a full cycle reversal.
    "max_bars_held": 60,
}

EMA_FAST = 50
EMA_SLOW = 200
MOM_LOOKBACK = 180  # ~30 days on 4h
SLOPE_LOOKBACK = 50
DONCHIAN = 20
ATR_PERIOD = 14
SLOPE_ATR_MULT = 0.5  # EMA_SLOW must drift >= 0.5 ATR over SLOPE_LOOKBACK
STOP_ATR_MULT = 2.0
TP_ATR_MULT = 4.0  # -> 2:1 reward:risk


class TsmomVolBreakoutStrategy(BaseStrategy):
    """Trend-gated time-series momentum with a volatility-breakout trigger."""

    @property
    def minimum_candles(self) -> int:
        return EMA_SLOW + SLOPE_LOOKBACK + 1

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
            price = closes[-1]

            ema_fast = ema(closes, EMA_FAST)
            ema_slow = ema(closes, EMA_SLOW)
            ema_slow_prev = ema(closes[:-SLOPE_LOOKBACK], EMA_SLOW)
            atr_now = atr(highs, lows, closes, ATR_PERIOD)
            # Donchian channel from the prior DONCHIAN bars (exclude current).
            donchian_hi = max(highs[-DONCHIAN - 1 : -1])
            donchian_lo = min(lows[-DONCHIAN - 1 : -1])
            mom = price - closes[-MOM_LOOKBACK - 1]
        except Exception as e:  # noqa: BLE001
            raise StrategyExecutionError(
                f"TSMOM vol-breakout analysis failed: {e}",
                strategy_name=self.name,
            ) from e

        if atr_now <= 0:
            return _neutral_result(price, "ATR is zero; cannot size risk")

        slope = ema_slow - ema_slow_prev
        trending = abs(slope) >= SLOPE_ATR_MULT * atr_now
        trend_up = ema_fast > ema_slow and price > ema_slow and slope > 0
        trend_dn = ema_fast < ema_slow and price < ema_slow and slope < 0
        # Conviction scales with how far the trend drift exceeds the floor.
        conf = max(0.3, min(0.9, abs(slope) / (atr_now * 2.0)))

        long_ok = trending and trend_up and mom > 0 and price > donchian_hi
        short_ok = trending and trend_dn and mom < 0 and price < donchian_lo

        if long_ok:
            stop = price - STOP_ATR_MULT * atr_now
            take = price + TP_ATR_MULT * atr_now
            return _directional_result(
                signal="long",
                price=price,
                stop=stop,
                take_profit=take,
                confidence=conf,
                reasoning=(
                    f"TSMOM long: price {price:.4g} > donchian_hi "
                    f"{donchian_hi:.4g}, EMA{EMA_FAST}>EMA{EMA_SLOW} rising "
                    f"(slope {slope:.4g} >= {SLOPE_ATR_MULT}*ATR {atr_now:.4g}), "
                    f"mom30d {mom:.4g}>0"
                ),
            )
        if short_ok:
            stop = price + STOP_ATR_MULT * atr_now
            take = price - TP_ATR_MULT * atr_now
            return _directional_result(
                signal="short",
                price=price,
                stop=stop,
                take_profit=take,
                confidence=conf,
                reasoning=(
                    f"TSMOM short: price {price:.4g} < donchian_lo "
                    f"{donchian_lo:.4g}, EMA{EMA_FAST}<EMA{EMA_SLOW} falling "
                    f"(slope {slope:.4g}), mom30d {mom:.4g}<0"
                ),
            )

        return _neutral_result(
            price,
            (
                f"No trend-gated breakout: trending={trending}, "
                f"trend_up={trend_up}, trend_dn={trend_dn}, mom={mom:.4g}"
            ),
        )


def _q(value: float) -> Decimal:
    """Quantize a price to a sensible precision for any asset magnitude."""
    return Decimal(str(round(max(value, 1e-8), 8)))


def _directional_result(
    *,
    signal: str,
    price: float,
    stop: float,
    take_profit: float,
    confidence: float,
    reasoning: str,
) -> AnalysisResult:
    return AnalysisResult(
        signal=signal,  # type: ignore[arg-type]
        confidence=confidence,
        entry_price=_q(price),
        stop_loss=_q(stop),
        take_profit=_q(take_profit),
        reasoning=reasoning,
        timestamp=datetime.now(),
    )


def _neutral_result(price: float, reason: str) -> AnalysisResult:
    return AnalysisResult(
        signal="neutral",
        confidence=0.3,
        entry_price=_q(price),
        stop_loss=_q(price * 0.98),
        take_profit=_q(price * 1.02),
        reasoning=reason,
        timestamp=datetime.now(),
    )

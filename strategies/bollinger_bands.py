"""Bollinger Band mean-reversion strategy (Phase 9.2 baseline).

Standard 20-period, 2-sigma bands. Long when the close pierces the
lower band (oversold relative to the recent mean), short when it
pierces the upper band. Mean reversion: targets the middle band;
stops sit just outside the triggering band so the trade is
invalidated if the move keeps extending.

Like the RSI baseline, this is deliberately simple and
deterministic — its job is to be a comparison floor for the
LLM-driven techniques.

Related Requirements:
- FR-001 / FR-002 / FR-003 / FR-004
"""

from datetime import datetime
from decimal import Decimal

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, StrategyExecutionError, TechniqueInfo
from src.strategy.indicators import InsufficientDataError, bollinger_bands

TECHNIQUE_INFO = {
    "name": "bollinger_band_reversion",
    "version": "1.1.0",
    "description": (
        "Bollinger Band mean reversion: long when close < lower band, "
        "short when close > upper band. Deterministic baseline."
    ),
    "author": "system",
    "symbols": [],
    "timeframes": ["1h", "4h"],
    "status": "experimental",
    "changelog": (
        "1.1.0: widen SL_BUFFER_FRACTION 0.5->1.0; require "
        "MIN_ENTRY_DEPTH_FRACTION 0.25; require prior-bar "
        "confirmation; tighten confidence calibration. "
        "1.0.0: Initial version (baseline)"
    ),
    "counter_trend": True,
    # 1h band reversion: 12 bars (~12h) — bands re-expand fast and a
    # stuck trade past that window is rarely a reversion any more.
    "max_bars_held": 12,
}


BB_PERIOD = 20
BB_STD_DEV = 2.0
# Stop-loss buffer past the triggering band, expressed as a fraction of
# the half-band-width (band − middle). Was 0.5 (stop inside ~0.5 sigma
# of trigger). 12-day Fly paper run showed median 0.31% SL distance,
# inside typical 1h crypto candle wick. 1.0 places stop one full
# half-band-width past the trigger band — ~3 sigma from the SMA
# centre. Pairs with the universal ATR floor at the proposal layer for
# additional safety on low-vol regimes.
SL_BUFFER_FRACTION = Decimal("1.0")
# Minimum depth past the band before firing, expressed as a fraction
# of the half-band-width. 0.25 means the close must pierce the band by
# at least 25% of the half-band-width on top of just touching it.
# Filters out shallow noise pierces that produced the median 0.05
# composite score on the 44 rejected proposals during the Fly run.
MIN_ENTRY_DEPTH_FRACTION = Decimal("0.25")
# Require the prior bar to also close beyond the band on the same
# side. Filters single-bar wick fakes that are common in trending
# crypto regimes — a real mean-reversion setup doesn't usually appear
# from a single noise bar.
REQUIRE_PRIOR_BAR_CONFIRMATION = True


class BollingerBandReversionStrategy(BaseStrategy):
    """Mean-revert when price pierces a Bollinger Band."""

    def __init__(
        self,
        info: TechniqueInfo,
        period: int = BB_PERIOD,
        std_dev: float = BB_STD_DEV,
    ) -> None:
        super().__init__(info)
        self.period = period
        self.std_dev = std_dev

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
    ) -> AnalysisResult:
        self.validate_input(ohlcv, min_candles=self.period)

        try:
            closes = [float(c.close) for c in ohlcv]
            current_price = closes[-1]
            lower, middle, upper = bollinger_bands(
                closes, period=self.period, std_dev=self.std_dev
            )
        except InsufficientDataError as e:
            return _neutral_result(current_price=float(ohlcv[-1].close), reason=str(e))
        except Exception as e:
            raise StrategyExecutionError(
                f"Bollinger Bands analysis failed: {e}",
                strategy_name=self.name,
            ) from e

        band_half_width = (upper - middle) or 1e-9  # avoid /0 on flat history
        min_depth = float(MIN_ENTRY_DEPTH_FRACTION)
        sl_buffer = float(SL_BUFFER_FRACTION)

        # Prior-bar confirmation: compute bands one bar back so we can
        # check the prior close also breached the same side. Need
        # period+1 closes total; on shorter history we silently skip
        # confirmation rather than crash, since the warm-up gate above
        # already ensures we have ``period`` closes.
        prior_lower: float | None = None
        prior_upper: float | None = None
        if REQUIRE_PRIOR_BAR_CONFIRMATION and len(closes) > self.period:
            try:
                prior_lower, _prior_middle, prior_upper = bollinger_bands(
                    closes[:-1], period=self.period, std_dev=self.std_dev
                )
            except InsufficientDataError:
                prior_lower = None
                prior_upper = None

        if current_price < lower:
            depth = (lower - current_price) / band_half_width
            if depth < min_depth:
                return _neutral_result(
                    current_price=current_price,
                    reason=(
                        f"Close {current_price:.2f} below lower band "
                        f"{lower:.2f} but depth {depth:.3f} < "
                        f"min {min_depth:.3f}"
                    ),
                )
            if REQUIRE_PRIOR_BAR_CONFIRMATION:
                if prior_lower is None or closes[-2] >= prior_lower:
                    return _neutral_result(
                        current_price=current_price,
                        reason=(
                            f"Close {current_price:.2f} below lower band "
                            f"{lower:.2f} but prior bar did not "
                            "confirm (close inside its band)"
                        ),
                    )
            signal: str = "long"
            # Confidence proportional to how far price is below the band.
            # Floor at MIN_ENTRY_DEPTH_FRACTION (the gate above ensures
            # surviving signals already meet this); 1σ below band → 1.0.
            confidence = min(1.0, max(min_depth, depth))
            sl_price = lower - (middle - lower) * sl_buffer
            entry = Decimal(str(round(current_price, 2)))
            stop_loss = Decimal(str(round(sl_price, 2)))
            take_profit = Decimal(str(round(middle, 2)))
            reasoning = (
                f"Close {current_price:.2f} below lower band "
                f"{lower:.2f} (mid {middle:.2f}, σ×2 width "
                f"{band_half_width:.2f}, depth {depth:.2f})"
            )
        elif current_price > upper:
            depth = (current_price - upper) / band_half_width
            if depth < min_depth:
                return _neutral_result(
                    current_price=current_price,
                    reason=(
                        f"Close {current_price:.2f} above upper band "
                        f"{upper:.2f} but depth {depth:.3f} < "
                        f"min {min_depth:.3f}"
                    ),
                )
            if REQUIRE_PRIOR_BAR_CONFIRMATION:
                if prior_upper is None or closes[-2] <= prior_upper:
                    return _neutral_result(
                        current_price=current_price,
                        reason=(
                            f"Close {current_price:.2f} above upper band "
                            f"{upper:.2f} but prior bar did not "
                            "confirm (close inside its band)"
                        ),
                    )
            signal = "short"
            confidence = min(1.0, max(min_depth, depth))
            sl_price = upper + (upper - middle) * sl_buffer
            entry = Decimal(str(round(current_price, 2)))
            stop_loss = Decimal(str(round(sl_price, 2)))
            take_profit = Decimal(str(round(middle, 2)))
            reasoning = (
                f"Close {current_price:.2f} above upper band "
                f"{upper:.2f} (mid {middle:.2f}, σ×2 width "
                f"{band_half_width:.2f}, depth {depth:.2f})"
            )
        else:
            return _neutral_result(
                current_price=current_price,
                reason=(
                    f"Close {current_price:.2f} inside bands "
                    f"[{lower:.2f}, {upper:.2f}]"
                ),
            )

        return AnalysisResult(
            signal=signal,  # type: ignore[arg-type]
            confidence=confidence,
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=reasoning,
            timestamp=datetime.now(),
        )


def _neutral_result(current_price: float, reason: str) -> AnalysisResult:
    """Neutral signal with placeholder valid prices."""
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

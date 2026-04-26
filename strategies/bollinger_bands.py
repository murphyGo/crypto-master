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
    "version": "1.0.0",
    "description": (
        "Bollinger Band mean reversion: long when close < lower band, "
        "short when close > upper band. Deterministic baseline."
    ),
    "author": "system",
    "symbols": [],
    "timeframes": ["1h", "4h"],
    "status": "experimental",
    "changelog": "Initial version (baseline)",
}


BB_PERIOD = 20
BB_STD_DEV = 2.0
# Stop-loss is placed half a sigma outside the triggering band so an
# immediate continuation invalidates the mean-reversion thesis. TP is
# the middle band (the mean we expect to revert to).
SL_BUFFER_FRACTION = 0.5  # of (band − middle)


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

        if current_price < lower:
            signal: str = "long"
            # Confidence proportional to how far price is below the band.
            # 1σ below band → confidence 1.0.
            depth = (lower - current_price) / band_half_width
            confidence = min(1.0, max(0.05, depth))
            sl_price = lower - (middle - lower) * SL_BUFFER_FRACTION
            entry = Decimal(str(round(current_price, 2)))
            stop_loss = Decimal(str(round(sl_price, 2)))
            take_profit = Decimal(str(round(middle, 2)))
            reasoning = (
                f"Close {current_price:.2f} below lower band "
                f"{lower:.2f} (mid {middle:.2f}, σ×2 width "
                f"{band_half_width:.2f})"
            )
        elif current_price > upper:
            signal = "short"
            depth = (current_price - upper) / band_half_width
            confidence = min(1.0, max(0.05, depth))
            sl_price = upper + (upper - middle) * SL_BUFFER_FRACTION
            entry = Decimal(str(round(current_price, 2)))
            stop_loss = Decimal(str(round(sl_price, 2)))
            take_profit = Decimal(str(round(middle, 2)))
            reasoning = (
                f"Close {current_price:.2f} above upper band "
                f"{upper:.2f} (mid {middle:.2f}, σ×2 width "
                f"{band_half_width:.2f})"
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

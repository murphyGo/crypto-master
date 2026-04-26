"""Moving-average crossover strategy (Phase 9.2 baseline).

Classic dual-SMA crossover: long when the fast MA crosses above the
slow MA on the latest bar, short on the opposite cross, otherwise
neutral. Built on the same shared :mod:`src.strategy.indicators`
math as the RSI and Bollinger baselines.

Defaults (10 / 20 SMA) are sensible for hourly candles. Tunable via
constructor args if you want a different cadence — but stay aware
that loose vs tight crossovers behave very differently and shouldn't
be retuned without backtesting first.

Related Requirements:
- FR-001 / FR-002 / FR-003 / FR-004
"""

from datetime import datetime
from decimal import Decimal

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, StrategyExecutionError, TechniqueInfo
from src.strategy.indicators import InsufficientDataError, sma

TECHNIQUE_INFO = {
    "name": "ma_crossover",
    "version": "1.0.0",
    "description": (
        "Dual SMA crossover: long on bullish cross, short on bearish "
        "cross. Deterministic baseline."
    ),
    "author": "system",
    "symbols": [],  # universal
    "timeframes": ["1h", "4h", "1d"],
    "status": "experimental",
    "changelog": "Promoted from sample_code.py to a real baseline (Phase 9.2)",
}


SHORT_PERIOD = 10
LONG_PERIOD = 20


class MACrossoverStrategy(BaseStrategy):
    """Long on bullish cross, short on bearish cross, neutral otherwise."""

    def __init__(
        self,
        info: TechniqueInfo,
        short_period: int = SHORT_PERIOD,
        long_period: int = LONG_PERIOD,
    ) -> None:
        super().__init__(info)
        self.short_period = short_period
        self.long_period = long_period

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
    ) -> AnalysisResult:
        # Need at least long_period + 1 closes to compute the previous
        # bar's MAs (for cross detection).
        self.validate_input(ohlcv, min_candles=self.long_period + 1)

        try:
            closes = [float(c.close) for c in ohlcv]
            current_price = closes[-1]
            short_ma = sma(closes, self.short_period)
            long_ma = sma(closes, self.long_period)
            prev_short_ma = sma(closes[:-1], self.short_period)
            prev_long_ma = sma(closes[:-1], self.long_period)
        except InsufficientDataError as e:
            return _neutral_result(current_price=float(ohlcv[-1].close), reason=str(e))
        except Exception as e:
            raise StrategyExecutionError(
                f"MA crossover analysis failed: {e}",
                strategy_name=self.name,
            ) from e

        if short_ma > long_ma and prev_short_ma <= prev_long_ma:
            signal: str = "long"
            # Confidence proportional to the cross magnitude (capped).
            confidence = min(0.8, abs(short_ma - long_ma) / current_price * 100)
            stop_loss = Decimal(str(round(min(closes[-5:]), 2)))
            take_profit = Decimal(str(round(current_price * 1.05, 2)))
            reasoning = (
                f"Bullish cross: SMA({self.short_period})={short_ma:.2f} "
                f"crossed above SMA({self.long_period})={long_ma:.2f}"
            )
        elif short_ma < long_ma and prev_short_ma >= prev_long_ma:
            signal = "short"
            confidence = min(0.8, abs(short_ma - long_ma) / current_price * 100)
            stop_loss = Decimal(str(round(max(closes[-5:]), 2)))
            take_profit = Decimal(str(round(current_price * 0.95, 2)))
            reasoning = (
                f"Bearish cross: SMA({self.short_period})={short_ma:.2f} "
                f"crossed below SMA({self.long_period})={long_ma:.2f}"
            )
        else:
            return _neutral_result(
                current_price=current_price,
                reason=(
                    f"No cross. SMA({self.short_period})={short_ma:.2f}, "
                    f"SMA({self.long_period})={long_ma:.2f}"
                ),
            )

        return AnalysisResult(
            signal=signal,  # type: ignore[arg-type]
            confidence=confidence,
            entry_price=Decimal(str(round(current_price, 2))),
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
        stop_loss=Decimal(str(round(current_price * 0.98, 2))),
        take_profit=Decimal(str(round(current_price * 1.02, 2))),
        reasoning=reason,
        timestamp=datetime.now(),
    )

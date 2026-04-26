"""RSI mean-reversion strategy (Phase 9.2 baseline).

Wilder's RSI on the closes. Long when RSI < 30 (oversold,
expect reversion up), short when RSI > 70 (overbought, expect
reversion down), neutral in between. SL/TP are fixed percentages
from entry so the R/R is constant across symbols and timeframes —
the baseline's "edge" lives entirely in signal *timing*, which makes
it a clean reference point for comparing against LLM-driven
techniques.

Once Phase 9.1 ships multi-timeframe support, this will split into
``rsi_4h.py`` and ``rsi_15m.py`` for the swing- vs scalp-cadence
variants the user asked for. Today the engine fetches one
timeframe per cycle (``EngineConfig.timeframe``); this strategy
runs on whatever the engine passes.

Related Requirements:
- FR-001 / FR-002 / FR-003 / FR-004
"""

from datetime import datetime
from decimal import Decimal

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, StrategyExecutionError, TechniqueInfo
from src.strategy.indicators import InsufficientDataError, rsi

TECHNIQUE_INFO = {
    "name": "rsi_mean_reversion",
    "version": "1.0.0",
    "description": (
        "RSI mean-reversion: long when RSI<30, short when RSI>70. "
        "Deterministic baseline."
    ),
    "author": "system",
    "symbols": [],  # universal
    "timeframes": ["1h", "4h", "15m"],
    "status": "experimental",
    "changelog": "Initial version (baseline)",
}


# Tunables. Pulled out of the class so a future settings-driven
# override is a one-line change.
RSI_PERIOD = 14
OVERSOLD_THRESHOLD = 30.0
OVERBOUGHT_THRESHOLD = 70.0
STOP_LOSS_PCT = 0.02  # 2%
TAKE_PROFIT_PCT = 0.04  # 4% → R/R = 2 : 1


class RSIMeanReversionStrategy(BaseStrategy):
    """RSI < 30 → long; RSI > 70 → short; otherwise neutral."""

    def __init__(
        self,
        info: TechniqueInfo,
        period: int = RSI_PERIOD,
        oversold: float = OVERSOLD_THRESHOLD,
        overbought: float = OVERBOUGHT_THRESHOLD,
    ) -> None:
        super().__init__(info)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
    ) -> AnalysisResult:
        # ``period + 1`` deltas are needed for Wilder's RSI; ask for a
        # margin so the smoothing has time to converge to canonical
        # behavior. Strategies should request enough warm-up to match
        # what TradingView etc. show.
        self.validate_input(ohlcv, min_candles=self.period * 3)

        try:
            closes = [float(c.close) for c in ohlcv]
            current_price = closes[-1]
            current_rsi = rsi(closes, period=self.period)
        except InsufficientDataError as e:
            # Surfaced from indicators when a fresh symbol has too
            # little history. Treat as "no signal".
            return _neutral_result(
                symbol, current_price=float(ohlcv[-1].close), reason=str(e)
            )
        except Exception as e:
            raise StrategyExecutionError(
                f"RSI analysis failed: {e}", strategy_name=self.name
            ) from e

        # Confidence ramps from 0 at the threshold to 1 at full
        # overbought / oversold extremes (RSI = 90 or 10 respectively).
        if current_rsi < self.oversold:
            signal: str = "long"
            confidence = min(1.0, max(0.0, (self.oversold - current_rsi) / 20.0))
            entry = Decimal(str(round(current_price, 2)))
            stop_loss = Decimal(str(round(current_price * (1 - STOP_LOSS_PCT), 2)))
            take_profit = Decimal(str(round(current_price * (1 + TAKE_PROFIT_PCT), 2)))
            reasoning = f"RSI({self.period})={current_rsi:.2f} below oversold {self.oversold:.0f}"
        elif current_rsi > self.overbought:
            signal = "short"
            confidence = min(1.0, max(0.0, (current_rsi - self.overbought) / 20.0))
            entry = Decimal(str(round(current_price, 2)))
            stop_loss = Decimal(str(round(current_price * (1 + STOP_LOSS_PCT), 2)))
            take_profit = Decimal(str(round(current_price * (1 - TAKE_PROFIT_PCT), 2)))
            reasoning = f"RSI({self.period})={current_rsi:.2f} above overbought {self.overbought:.0f}"
        else:
            return _neutral_result(
                symbol,
                current_price=current_price,
                reason=(
                    f"RSI({self.period})={current_rsi:.2f} between "
                    f"{self.oversold:.0f}/{self.overbought:.0f}"
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


def _neutral_result(symbol: str, current_price: float, reason: str) -> AnalysisResult:
    """Build a neutral ``AnalysisResult`` for when there's no setup.

    Entry/SL/TP must still be valid numbers (Pydantic enforces > 0)
    even though the engine ignores them on neutral signals — set them
    to small ±1% bands around the current price.
    """
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

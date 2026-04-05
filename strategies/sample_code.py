"""Sample code-based strategy using moving average crossover.

This is a reference implementation showing how to create
code-based analysis techniques.
"""

from datetime import datetime
from decimal import Decimal
from statistics import mean

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, StrategyExecutionError, TechniqueInfo

TECHNIQUE_INFO = {
    "name": "ma_crossover",
    "version": "1.0.0",
    "description": "Simple moving average crossover strategy",
    "author": "system",
    "symbols": ["BTC/USDT", "ETH/USDT"],
    "timeframes": ["1h", "4h", "1d"],
    "status": "experimental",
    "changelog": "Initial implementation",
}


class MACrossoverStrategy(BaseStrategy):
    """Moving average crossover strategy.

    Generates signals based on short-term MA crossing long-term MA.
    """

    def __init__(
        self,
        info: TechniqueInfo,
        short_period: int = 10,
        long_period: int = 20,
    ) -> None:
        """Initialize strategy with MA periods.

        Args:
            info: Technique metadata.
            short_period: Short MA period.
            long_period: Long MA period.
        """
        super().__init__(info)
        self.short_period = short_period
        self.long_period = long_period

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
    ) -> AnalysisResult:
        """Analyze using MA crossover logic.

        Args:
            ohlcv: OHLCV candlestick data.
            symbol: Trading pair symbol.
            timeframe: Candle timeframe.

        Returns:
            AnalysisResult with signal based on MA crossover.

        Raises:
            StrategyExecutionError: If analysis fails.
        """
        self.validate_input(ohlcv, min_candles=self.long_period + 1)

        try:
            closes = [float(c.close) for c in ohlcv]

            # Calculate MAs
            short_ma = mean(closes[-self.short_period :])
            long_ma = mean(closes[-self.long_period :])
            prev_short_ma = mean(closes[-self.short_period - 1 : -1])
            prev_long_ma = mean(closes[-self.long_period - 1 : -1])

            current_price = closes[-1]

            # Determine signal
            if short_ma > long_ma and prev_short_ma <= prev_long_ma:
                # Bullish crossover
                signal = "long"
                confidence = min(0.8, abs(short_ma - long_ma) / current_price * 100)
                stop_loss = Decimal(str(round(min(closes[-5:]), 2)))
                take_profit = Decimal(str(round(current_price * 1.05, 2)))
            elif short_ma < long_ma and prev_short_ma >= prev_long_ma:
                # Bearish crossover
                signal = "short"
                confidence = min(0.8, abs(short_ma - long_ma) / current_price * 100)
                stop_loss = Decimal(str(round(max(closes[-5:]), 2)))
                take_profit = Decimal(str(round(current_price * 0.95, 2)))
            else:
                # No crossover
                signal = "neutral"
                confidence = 0.3
                stop_loss = Decimal(str(round(current_price * 0.98, 2)))
                take_profit = Decimal(str(round(current_price * 1.02, 2)))

            return AnalysisResult(
                signal=signal,
                confidence=confidence,
                entry_price=Decimal(str(round(current_price, 2))),
                stop_loss=stop_loss,
                take_profit=take_profit,
                reasoning=(
                    f"MA({self.short_period})={short_ma:.2f}, "
                    f"MA({self.long_period})={long_ma:.2f}"
                ),
                timestamp=datetime.now(),
            )

        except Exception as e:
            raise StrategyExecutionError(
                f"Analysis failed: {e}", strategy_name=self.name
            )

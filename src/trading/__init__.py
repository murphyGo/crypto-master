"""Trading module for Crypto Master.

Provides trading strategy calculation, position management, and
trade execution logic.

Related Requirements:
- FR-006: Risk/Reward Calculation
- FR-007: Leverage Setting
- FR-008: Entry/Take-Profit/Stop-Loss Setting
- FR-009: Live Trading Mode
- FR-010: Paper Trading Mode
"""

from src.trading.live import (
    LiveConfirmationRejectedError,
    LiveModeError,
    LiveOrderRejectedError,
    LiveTrader,
    LiveTradingError,
)
from src.trading.paper import (
    DEFAULT_FEE_CONFIGS,
    FeeConfig,
    InsufficientPaperBalanceError,
    OpenPosition,
    PaperBalance,
    PaperTrader,
    PaperTradingError,
)
from src.trading.portfolio import (
    AssetSnapshot,
    Portfolio,
    PortfolioTracker,
)
from src.trading.strategy import (
    InsufficientBalanceError,
    TradingError,
    TradingStrategy,
    TradingStrategyConfig,
    TradingValidationError,
)

__all__ = [
    # Exceptions
    "TradingError",
    "TradingValidationError",
    "InsufficientBalanceError",
    "PaperTradingError",
    "InsufficientPaperBalanceError",
    "LiveTradingError",
    "LiveModeError",
    "LiveConfirmationRejectedError",
    "LiveOrderRejectedError",
    # Strategy Classes
    "TradingStrategy",
    "TradingStrategyConfig",
    # Paper Trading Classes
    "PaperTrader",
    "PaperBalance",
    "OpenPosition",
    "FeeConfig",
    "DEFAULT_FEE_CONFIGS",
    # Live Trading Classes
    "LiveTrader",
    # Portfolio Classes
    "Portfolio",
    "PortfolioTracker",
    "AssetSnapshot",
]

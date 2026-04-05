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
    # Classes
    "TradingStrategy",
    "TradingStrategyConfig",
]

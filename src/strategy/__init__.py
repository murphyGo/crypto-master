"""Strategy framework for Crypto Master.

This module provides the analysis technique framework for chart analysis,
supporting both prompt-based (.md) and code-based (.py) strategies.

Related Requirements:
- FR-001: Bitcoin Chart Analysis
- FR-002: Altcoin Chart Analysis
- FR-003: Chart Analysis Technique Definition
- FR-004: Analysis Technique Storage/Management
- NFR-005: Analysis Technique Storage
- NFR-010: Analysis Technique Extensibility
"""

from src.strategy.base import (
    BaseStrategy,
    StrategyError,
    StrategyExecutionError,
    StrategyLoadError,
    StrategyValidationError,
    TechniqueInfo,
)
from src.strategy.factory import (
    clear_strategy_cache,
    clear_strategy_registry,
    get_available_strategies,
    get_strategies_by_status,
    get_strategies_by_symbol,
    get_strategy,
    load_strategies_from_directory,
    register_strategy,
)
from src.strategy.loader import (
    DEFAULT_STRATEGIES_DIR,
    PromptStrategy,
    discover_strategies,
    load_all_strategies,
    load_strategy,
    load_technique_info_from_md,
    load_technique_info_from_py,
)

__all__ = [
    # Base classes
    "BaseStrategy",
    "PromptStrategy",
    "TechniqueInfo",
    # Exceptions
    "StrategyError",
    "StrategyValidationError",
    "StrategyExecutionError",
    "StrategyLoadError",
    # Factory functions
    "register_strategy",
    "get_strategy",
    "get_available_strategies",
    "get_strategies_by_symbol",
    "get_strategies_by_status",
    "load_strategies_from_directory",
    "clear_strategy_cache",
    "clear_strategy_registry",
    # Loader functions
    "load_strategy",
    "load_all_strategies",
    "discover_strategies",
    "load_technique_info_from_md",
    "load_technique_info_from_py",
    "DEFAULT_STRATEGIES_DIR",
]

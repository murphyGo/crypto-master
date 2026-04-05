"""Strategy factory for Crypto Master.

Provides factory functions and registry for creating strategy instances.

Related Requirements:
- NFR-010: Analysis Technique Extensibility
"""

from pathlib import Path
from typing import Callable

from src.strategy.base import BaseStrategy, StrategyError, TechniqueInfo
from src.strategy.loader import (
    DEFAULT_STRATEGIES_DIR,
    load_all_strategies,
)

# Registry for code-based strategy implementations
_strategy_registry: dict[str, type[BaseStrategy]] = {}

# Cache for loaded strategies
_loaded_strategies: dict[str, BaseStrategy] = {}

# Flag to track if strategies have been loaded
_strategies_loaded: bool = False


def register_strategy(
    name: str,
) -> Callable[[type[BaseStrategy]], type[BaseStrategy]]:
    """Decorator to register a strategy implementation.

    Usage:
        @register_strategy("my_strategy")
        class MyStrategy(BaseStrategy):
            async def analyze(self, ohlcv, symbol, timeframe="1h"):
                ...

    Args:
        name: Strategy name (case-insensitive).

    Returns:
        Decorator function.
    """

    def decorator(cls: type[BaseStrategy]) -> type[BaseStrategy]:
        _strategy_registry[name.lower()] = cls
        return cls

    return decorator


def get_strategy(name: str) -> BaseStrategy:
    """Get a strategy by name.

    First checks the loaded strategies cache, then falls back to
    loading from the strategies directory.

    Args:
        name: Strategy name.

    Returns:
        Strategy instance.

    Raises:
        StrategyError: If strategy not found.
    """
    name_lower = name.lower()

    # Check cache
    if name_lower in _loaded_strategies:
        return _loaded_strategies[name_lower]

    # Try to load from directory
    load_strategies_from_directory()

    if name_lower in _loaded_strategies:
        return _loaded_strategies[name_lower]

    available = ", ".join(sorted(_loaded_strategies.keys())) or "none"
    raise StrategyError(f"Strategy '{name}' not found. Available: {available}")


def load_strategies_from_directory(
    directory: Path = DEFAULT_STRATEGIES_DIR,
    force_reload: bool = False,
) -> dict[str, BaseStrategy]:
    """Load all strategies from the strategies directory.

    Args:
        directory: Directory containing strategy files.
        force_reload: If True, reload even if already loaded.

    Returns:
        Dict mapping strategy name to strategy instance.
    """
    global _loaded_strategies, _strategies_loaded

    if _strategies_loaded and not force_reload:
        return _loaded_strategies

    _loaded_strategies = {}

    # Load from directory
    loaded = load_all_strategies(directory)
    for name, strategy in loaded.items():
        _loaded_strategies[name.lower()] = strategy

    # Also include registered strategies that aren't loaded yet
    for name, cls in _strategy_registry.items():
        if name not in _loaded_strategies:
            # Create a default TechniqueInfo for registered strategies
            info = TechniqueInfo(
                name=name,
                version="1.0.0",
                description=cls.__doc__ or f"Strategy: {name}",
                technique_type="code",
            )
            _loaded_strategies[name] = cls(info=info)

    _strategies_loaded = True
    return _loaded_strategies


def get_available_strategies() -> list[str]:
    """Get list of available strategy names.

    Returns:
        Sorted list of strategy names.
    """
    load_strategies_from_directory()
    return sorted(_loaded_strategies.keys())


def get_strategies_by_symbol(symbol: str) -> list[BaseStrategy]:
    """Get strategies that support a specific symbol.

    Args:
        symbol: Trading pair symbol (e.g., "BTC/USDT").

    Returns:
        List of strategies supporting this symbol.
    """
    load_strategies_from_directory()
    return [
        s
        for s in _loaded_strategies.values()
        if symbol in s.info.symbols or "*" in s.info.symbols
    ]


def get_strategies_by_status(
    status: str,
) -> list[BaseStrategy]:
    """Get strategies with a specific status.

    Args:
        status: Status to filter by ("experimental", "active", "deprecated").

    Returns:
        List of strategies with the specified status.
    """
    load_strategies_from_directory()
    return [s for s in _loaded_strategies.values() if s.info.status == status]


def clear_strategy_cache() -> None:
    """Clear the loaded strategies cache.

    Useful for testing or when strategy files change.
    """
    global _loaded_strategies, _strategies_loaded
    _loaded_strategies.clear()
    _strategies_loaded = False


def clear_strategy_registry() -> None:
    """Clear the strategy registry.

    Useful for testing.
    """
    global _strategy_registry
    _strategy_registry.clear()

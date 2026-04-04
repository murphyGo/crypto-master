"""Exchange factory for Crypto Master.

Provides factory function and registry for creating exchange instances.

Related Requirements:
- FR-019: Exchange Abstraction
- NFR-009: Exchange Extensibility - Plugin architecture
"""

from typing import TYPE_CHECKING

from src.config import get_settings
from src.exchange.base import BaseExchange, ExchangeError

if TYPE_CHECKING:
    from src.config import BinanceConfig, BybitConfig, Settings

# Registry for exchange implementations
_exchange_registry: dict[str, type[BaseExchange]] = {}


def register_exchange(name: str):
    """Decorator to register an exchange implementation.

    Usage:
        @register_exchange("binance")
        class BinanceExchange(BaseExchange):
            ...

    Args:
        name: Exchange name (case-insensitive)

    Returns:
        Decorator function
    """

    def decorator(cls: type[BaseExchange]) -> type[BaseExchange]:
        _exchange_registry[name.lower()] = cls
        return cls

    return decorator


def create_exchange(
    name: str,
    testnet: bool | None = None,
) -> BaseExchange:
    """Create an exchange instance.

    Args:
        name: Exchange name (e.g., "binance", "bybit")
        testnet: Override testnet setting. If None, uses config value.

    Returns:
        Exchange instance (not yet connected)

    Raises:
        ExchangeError: If exchange is not registered or not configured

    Usage:
        exchange = create_exchange("binance")
        async with exchange:
            ticker = await exchange.get_ticker("BTC/USDT")
    """
    name_lower = name.lower()

    if name_lower not in _exchange_registry:
        available = ", ".join(_exchange_registry.keys()) or "none"
        raise ExchangeError(
            f"Exchange '{name}' is not registered. Available: {available}"
        )

    # Get exchange config from settings
    settings = get_settings()
    config = _get_exchange_config(name_lower, settings)

    if config is None:
        raise ExchangeError(f"Exchange '{name}' is not configured in settings")

    if not config.is_configured():
        raise ExchangeError(
            f"Exchange '{name}' credentials not configured. "
            f"Set {name.upper()}_API_KEY and {name.upper()}_API_SECRET environment variables."
        )

    # Determine testnet setting
    use_testnet = testnet if testnet is not None else config.testnet

    # Create exchange instance
    exchange_class = _exchange_registry[name_lower]
    return exchange_class(config=config, testnet=use_testnet)


def _get_exchange_config(
    name: str, settings: "Settings"
) -> "BinanceConfig | BybitConfig | None":
    """Get exchange-specific config from settings.

    Args:
        name: Exchange name (lowercase)
        settings: Application settings

    Returns:
        Exchange config or None if not found
    """
    config_map = {
        "binance": settings.binance,
        "bybit": settings.bybit,
    }
    return config_map.get(name)


def get_available_exchanges() -> list[str]:
    """Get list of registered exchange names.

    Returns:
        List of exchange names that can be used with create_exchange()
    """
    return list(_exchange_registry.keys())


def get_configured_exchanges() -> list[str]:
    """Get list of exchanges that are both registered and configured.

    Returns:
        List of exchange names that are ready to use
    """
    settings = get_settings()
    configured = []

    for name in _exchange_registry:
        config = _get_exchange_config(name, settings)
        if config is not None and config.is_configured():
            configured.append(name)

    return configured

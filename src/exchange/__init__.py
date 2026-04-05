"""Exchange abstraction layer for Crypto Master.

Related Requirements:
- FR-019: Exchange Abstraction - Common interface for all exchanges
- NFR-009: Exchange Extensibility - Plugin architecture
"""

from src.exchange.base import (
    BaseExchange,
    ExchangeAPIError,
    ExchangeConnectionError,
    ExchangeError,
)
from src.exchange.binance import BinanceExchange
from src.exchange.bybit import BybitExchange
from src.exchange.factory import (
    create_exchange,
    get_available_exchanges,
    register_exchange,
)

__all__ = [
    "BaseExchange",
    "ExchangeError",
    "ExchangeConnectionError",
    "ExchangeAPIError",
    "BinanceExchange",
    "BybitExchange",
    "create_exchange",
    "get_available_exchanges",
    "register_exchange",
]

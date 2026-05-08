"""Base exchange abstraction for Crypto Master.

Related Requirements:
- FR-019: Exchange Abstraction - Common interface for all exchanges
- FR-020: Historical Chart Data Query - OHLCV data collection
- NFR-009: Exchange Extensibility - Plugin architecture
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Literal

from src.models import OHLCV, Balance, Order, OrderRequest, Ticker


def _decimal_or_none(value: Any) -> Decimal | None:
    """Coerce a ccxt scalar to ``Decimal``, returning None for null/0/empty.

    ccxt fills numeric fields with ``None`` when the venue did not
    return a value and with ``0`` for "no fill yet" — both cases are
    semantically "absent" for the Order model's optional fields.
    """
    if value in (None, "", 0, 0.0):
        return None
    try:
        decimal_value = Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return None
    return decimal_value if decimal_value > 0 else None


def _extract_ccxt_fee(raw_order: dict[str, Any]) -> tuple[Decimal | None, str | None]:
    """Pull the total fee out of a ccxt order response.

    ccxt unifies fee data across venues into either a single ``fee``
    object (``{"cost": 0.5, "currency": "USDT", ...}``) or a list of
    per-fill fee objects under ``fees``. Sum costs across the list when
    present so callers see the trade-level total. Returns
    ``(amount, currency)`` where amount may be ``None`` if the venue
    didn't surface a fee (consistency-hardening CH-06).
    """
    total = Decimal("0")
    currency: str | None = None
    fees_list = raw_order.get("fees")
    if isinstance(fees_list, list) and fees_list:
        for entry in fees_list:
            if not isinstance(entry, dict):
                continue
            cost = _decimal_or_none(entry.get("cost"))
            if cost is not None:
                total += cost
                if currency is None:
                    entry_currency = entry.get("currency")
                    if isinstance(entry_currency, str) and entry_currency:
                        currency = entry_currency
    fee_block = raw_order.get("fee")
    if isinstance(fee_block, dict):
        cost = _decimal_or_none(fee_block.get("cost"))
        if cost is not None and not (isinstance(fees_list, list) and fees_list):
            total += cost
            entry_currency = fee_block.get("currency")
            if isinstance(entry_currency, str) and entry_currency and currency is None:
                currency = entry_currency
    if total <= 0:
        return None, currency
    return total, currency


class ExchangeError(Exception):
    """Base exception for exchange errors."""

    pass


class ExchangeConnectionError(ExchangeError):
    """Connection to exchange failed."""

    pass


class ExchangeAPIError(ExchangeError):
    """API returned an error."""

    def __init__(self, message: str, code: str | None = None) -> None:
        """Initialize API error.

        Args:
            message: Error message
            code: Optional error code from exchange
        """
        super().__init__(message)
        self.code = code


class BaseExchange(ABC):
    """Abstract base class for exchange implementations.

    Related Requirements:
    - FR-019: Exchange Abstraction
    - NFR-009: Exchange Extensibility
    - FR-010: Paper Trading Mode (via testnet support)

    All exchange implementations must inherit from this class and implement
    the abstract methods. This ensures a consistent interface across all
    supported exchanges.

    Attributes:
        name: Exchange identifier (e.g., "binance", "bybit").
        testnet: Whether to use testnet/sandbox mode.

    Usage:
        async with exchange as ex:
            ticker = await ex.get_ticker("BTC/USDT")
            print(ticker.price)
    """

    name: str  # Exchange name (e.g., "binance", "bybit")

    def __init__(self, testnet: bool = False) -> None:
        """Initialize base exchange.

        Args:
            testnet: Whether to use testnet/sandbox mode for paper trading.
        """
        self.testnet = testnet

    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection to the exchange.

        This method should be called before any other operations.
        It may initialize API clients, authenticate, etc.

        Raises:
            ExchangeConnectionError: If connection fails
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the exchange.

        This method should clean up any resources (close sessions, etc).
        """
        pass

    @abstractmethod
    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w"],
        limit: int = 100,
        since: int | None = None,
    ) -> list[OHLCV]:
        """Fetch OHLCV candlestick data.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe
            limit: Number of candles to fetch (max depends on exchange)
            since: Optional UTC timestamp in milliseconds. When provided,
                the exchange returns the page of candles whose start
                timestamp is >= ``since``. When ``None`` (default), the
                exchange returns the most recent candles — preserving
                pre-13.3 behaviour.

        Returns:
            List of OHLCV data points, sorted by timestamp ascending

        Raises:
            ExchangeAPIError: If API request fails
        """
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """Get current price ticker for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")

        Returns:
            Current ticker data

        Raises:
            ExchangeAPIError: If API request fails
        """
        pass

    @abstractmethod
    async def get_balance(self, currency: str | None = None) -> list[Balance]:
        """Get account balances.

        Args:
            currency: Optional currency filter. If None, returns all balances.

        Returns:
            List of balance objects

        Raises:
            ExchangeAPIError: If API request fails
        """
        pass

    @abstractmethod
    async def create_order(self, order: OrderRequest) -> Order:
        """Create a new order.

        Args:
            order: Order request with details

        Returns:
            Created order with ID and status

        Raises:
            ExchangeAPIError: If order creation fails
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an existing order.

        Args:
            order_id: ID of the order to cancel
            symbol: Trading pair the order was placed on

        Returns:
            True if cancellation was successful

        Raises:
            ExchangeAPIError: If cancellation fails
        """
        pass

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> Order:
        """Get order details by ID.

        Args:
            order_id: ID of the order
            symbol: Trading pair the order was placed on

        Returns:
            Order details

        Raises:
            ExchangeAPIError: If order not found or request fails
        """
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        """Get all open orders.

        Args:
            symbol: Optional symbol filter. If None, returns all open orders.

        Returns:
            List of open orders

        Raises:
            ExchangeAPIError: If API request fails
        """
        pass

    async def __aenter__(self) -> "BaseExchange":
        """Enter async context manager."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context manager."""
        await self.disconnect()

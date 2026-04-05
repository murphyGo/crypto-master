"""Bybit exchange implementation for Crypto Master.

Related Requirements:
- FR-017: Bybit Integration - Execute trades and query data through Bybit API
- FR-019: Exchange Abstraction - Common interface for all exchanges
- FR-020: Historical Chart Data Query - OHLCV data collection
- CON-002: Rate Limit Compliance - Comply with exchange rate limits
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

import ccxt.async_support as ccxt
from ccxt.base.errors import (
    AuthenticationError,
    ExchangeNotAvailable,
    InsufficientFunds,
    InvalidOrder,
    NetworkError,
    OrderNotFound,
    RateLimitExceeded,
)
from ccxt.base.errors import ExchangeError as CCXTExchangeError

from src.config import BybitConfig
from src.exchange.base import (
    BaseExchange,
    ExchangeAPIError,
    ExchangeConnectionError,
    ExchangeError,
)
from src.exchange.factory import register_exchange
from src.models import OHLCV, Balance, Order, OrderRequest, OrderStatus, Ticker


@register_exchange("bybit")
class BybitExchange(BaseExchange):
    """Bybit exchange implementation using ccxt.

    Uses Bybit's unified API for spot and derivatives trading.
    Uses ccxt's built-in rate limiting for API compliance.

    Related Requirements:
    - FR-017: Bybit Integration
    - FR-019: Exchange Abstraction
    - CON-002: Rate Limit Compliance
    """

    name = "bybit"

    # Timeframe mapping: project timeframes to ccxt/Bybit timeframes
    TIMEFRAME_MAP: dict[str, str] = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1w",
    }

    def __init__(self, config: BybitConfig, testnet: bool = False) -> None:
        """Initialize BybitExchange.

        Args:
            config: Bybit configuration with API credentials
            testnet: Whether to use testnet (sandbox) mode
        """
        self.config = config
        self.testnet = testnet
        self._client: ccxt.bybit | None = None

    async def connect(self) -> None:
        """Initialize connection to Bybit.

        Creates the ccxt client and validates credentials by loading markets.

        Raises:
            ExchangeConnectionError: If connection or authentication fails
        """
        try:
            # Initialize ccxt client
            self._client = ccxt.bybit(
                {
                    "apiKey": self.config.api_key,
                    "secret": self.config.api_secret,
                    "sandbox": self.testnet,
                    "enableRateLimit": True,
                    "options": {
                        "adjustForTimeDifference": True,
                    },
                }
            )

            # Validate connection by loading markets
            await self._client.load_markets()

        except AuthenticationError as e:
            raise ExchangeConnectionError(f"Authentication failed: {e}") from e
        except NetworkError as e:
            raise ExchangeConnectionError(f"Network error: {e}") from e
        except ExchangeNotAvailable as e:
            raise ExchangeConnectionError(f"Exchange not available: {e}") from e
        except Exception as e:
            raise ExchangeConnectionError(f"Failed to connect: {e}") from e

    async def disconnect(self) -> None:
        """Close connection to Bybit.

        Closes the aiohttp session used by ccxt.
        """
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w"],
        limit: int = 100,
    ) -> list[OHLCV]:
        """Fetch OHLCV candlestick data from Bybit.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe
            limit: Number of candles (max 200 for Bybit)

        Returns:
            List of OHLCV data points, sorted by timestamp ascending

        Raises:
            ExchangeAPIError: If API request fails
        """
        client = self._ensure_connected()

        try:
            # Bybit max limit is 200
            limit = min(limit, 200)

            # ccxt returns: [[timestamp, open, high, low, close, volume], ...]
            raw_data = await client.fetch_ohlcv(
                symbol=symbol,
                timeframe=self.TIMEFRAME_MAP[timeframe],
                limit=limit,
            )

            return [
                OHLCV(
                    timestamp=datetime.fromtimestamp(candle[0] / 1000),
                    open=Decimal(str(candle[1])),
                    high=Decimal(str(candle[2])),
                    low=Decimal(str(candle[3])),
                    close=Decimal(str(candle[4])),
                    volume=Decimal(str(candle[5])),
                )
                for candle in raw_data
            ]

        except RateLimitExceeded as e:
            raise ExchangeAPIError(
                f"Rate limit exceeded: {e}", code="RATE_LIMIT"
            ) from e
        except CCXTExchangeError as e:
            raise ExchangeAPIError(f"Failed to fetch OHLCV: {e}") from e

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get current price ticker for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")

        Returns:
            Current ticker data

        Raises:
            ExchangeAPIError: If API request fails
        """
        client = self._ensure_connected()

        try:
            raw_ticker = await client.fetch_ticker(symbol)

            return Ticker(
                symbol=symbol,
                price=Decimal(str(raw_ticker["last"])),
                timestamp=datetime.fromtimestamp(raw_ticker["timestamp"] / 1000),
            )

        except RateLimitExceeded as e:
            raise ExchangeAPIError(
                f"Rate limit exceeded: {e}", code="RATE_LIMIT"
            ) from e
        except CCXTExchangeError as e:
            raise ExchangeAPIError(f"Failed to fetch ticker: {e}") from e

    async def get_balance(self, currency: str | None = None) -> list[Balance]:
        """Get account balances.

        Args:
            currency: Optional currency filter (e.g., "USDT", "BTC")

        Returns:
            List of Balance objects

        Raises:
            ExchangeAPIError: If API request fails
        """
        client = self._ensure_connected()

        try:
            raw_balance = await client.fetch_balance()

            balances = []
            for curr, data in raw_balance.items():
                # Skip metadata keys
                if curr in ("info", "timestamp", "datetime", "free", "used", "total"):
                    continue

                # Skip non-dict entries
                if not isinstance(data, dict):
                    continue

                # Apply currency filter
                if currency is not None and curr != currency:
                    continue

                # Extract balance values
                free = Decimal(str(data.get("free", 0) or 0))
                locked = Decimal(str(data.get("used", 0) or 0))
                total = Decimal(str(data.get("total", 0) or 0))

                # Skip zero balances
                if total == 0:
                    continue

                balances.append(
                    Balance(
                        currency=curr,
                        free=free,
                        locked=locked,
                        total=total,
                    )
                )

            return balances

        except RateLimitExceeded as e:
            raise ExchangeAPIError(
                f"Rate limit exceeded: {e}", code="RATE_LIMIT"
            ) from e
        except CCXTExchangeError as e:
            raise ExchangeAPIError(f"Failed to fetch balance: {e}") from e

    async def create_order(self, order: OrderRequest) -> Order:
        """Create a new order on Bybit.

        Args:
            order: Order request with details

        Returns:
            Created order with ID and status

        Raises:
            ExchangeAPIError: If order creation fails
        """
        client = self._ensure_connected()

        try:
            # Execute order
            if order.type == "market":
                raw_order = await client.create_market_order(
                    symbol=order.symbol,
                    side=order.side,
                    amount=float(order.quantity),
                )
            else:  # limit
                # order.price is validated by OrderRequest model for limit orders
                assert order.price is not None, "Limit order must have price"
                raw_order = await client.create_limit_order(
                    symbol=order.symbol,
                    side=order.side,
                    amount=float(order.quantity),
                    price=float(order.price),
                )

            return self._map_order(raw_order)

        except InvalidOrder as e:
            raise ExchangeAPIError(f"Invalid order: {e}", code="INVALID_ORDER") from e
        except InsufficientFunds as e:
            raise ExchangeAPIError(
                f"Insufficient funds: {e}", code="INSUFFICIENT_FUNDS"
            ) from e
        except RateLimitExceeded as e:
            raise ExchangeAPIError(
                f"Rate limit exceeded: {e}", code="RATE_LIMIT"
            ) from e
        except CCXTExchangeError as e:
            raise ExchangeAPIError(f"Failed to create order: {e}") from e

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
        client = self._ensure_connected()

        try:
            await client.cancel_order(order_id, symbol)
            return True

        except OrderNotFound:
            return False  # Order already filled or cancelled
        except RateLimitExceeded as e:
            raise ExchangeAPIError(
                f"Rate limit exceeded: {e}", code="RATE_LIMIT"
            ) from e
        except CCXTExchangeError as e:
            raise ExchangeAPIError(f"Failed to cancel order: {e}") from e

    async def get_order(self, order_id: str, symbol: str) -> Order:
        """Get order details by ID.

        Args:
            order_id: ID of the order
            symbol: Trading pair

        Returns:
            Order details

        Raises:
            ExchangeAPIError: If order not found or request fails
        """
        client = self._ensure_connected()

        try:
            raw_order = await client.fetch_order(order_id, symbol)
            return self._map_order(raw_order)

        except OrderNotFound as e:
            raise ExchangeAPIError(
                f"Order not found: {order_id}", code="NOT_FOUND"
            ) from e
        except RateLimitExceeded as e:
            raise ExchangeAPIError(
                f"Rate limit exceeded: {e}", code="RATE_LIMIT"
            ) from e
        except CCXTExchangeError as e:
            raise ExchangeAPIError(f"Failed to fetch order: {e}") from e

    async def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        """Get all open orders.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of open orders

        Raises:
            ExchangeAPIError: If API request fails
        """
        client = self._ensure_connected()

        try:
            raw_orders = await client.fetch_open_orders(symbol)
            return [self._map_order(o) for o in raw_orders]

        except RateLimitExceeded as e:
            raise ExchangeAPIError(
                f"Rate limit exceeded: {e}", code="RATE_LIMIT"
            ) from e
        except CCXTExchangeError as e:
            raise ExchangeAPIError(f"Failed to fetch open orders: {e}") from e

    def _ensure_connected(self) -> ccxt.bybit:
        """Ensure client is connected and return it.

        Returns:
            The connected ccxt client

        Raises:
            ExchangeError: If not connected
        """
        if self._client is None:
            raise ExchangeError("Not connected. Call connect() first.")
        return self._client

    def _map_order(self, raw_order: dict) -> Order:
        """Map ccxt order response to Order model.

        Args:
            raw_order: Raw order dict from ccxt

        Returns:
            Order model instance
        """
        return Order(
            id=str(raw_order["id"]),
            symbol=raw_order["symbol"],
            side=raw_order["side"],
            type=raw_order["type"],
            price=(
                Decimal(str(raw_order["price"])) if raw_order.get("price") else None
            ),
            quantity=Decimal(str(raw_order["amount"])),
            filled_quantity=Decimal(str(raw_order.get("filled", 0) or 0)),
            status=self._map_order_status(raw_order["status"]),
            created_at=datetime.fromtimestamp(raw_order["timestamp"] / 1000),
            updated_at=(
                datetime.fromtimestamp(raw_order["lastTradeTimestamp"] / 1000)
                if raw_order.get("lastTradeTimestamp")
                else None
            ),
        )

    def _map_order_status(self, ccxt_status: str) -> OrderStatus:
        """Map ccxt order status to OrderStatus enum.

        Args:
            ccxt_status: Status string from ccxt

        Returns:
            OrderStatus enum value
        """
        status_map = {
            "open": OrderStatus.OPEN,
            "closed": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "expired": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
        }
        return status_map.get(ccxt_status, OrderStatus.PENDING)

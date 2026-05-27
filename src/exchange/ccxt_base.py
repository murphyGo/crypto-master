"""Shared ccxt adapter base for Crypto Master.

Related Requirements:
- FR-019: Exchange Abstraction - Common interface for all exchanges
- FR-020: Historical Chart Data Query - OHLCV data collection
- NFR-009: Exchange Extensibility - new exchange = new adapter, no edits to siblings
- CON-002: Rate Limit Compliance - Comply with exchange rate limits

CAH-11: ``BinanceExchange`` and ``BybitExchange`` were ~95% byte-identical.
This module holds the shared ccxt-adapter logic; the concrete adapters become
thin subclasses overriding only what genuinely differs between the venues
(client construction via ``_build_client``, the OHLCV limit cap, the exchange
``name``, and the config/logger wiring).

EXCH-F5: the ccxt-mapping helpers ``_extract_ccxt_fee`` / ``_decimal_or_none``
live here (ccxt-adapter knowledge), not in the ``BaseExchange`` port module.
"""

from decimal import Decimal
from logging import Logger
from typing import Any, Literal, Protocol

from ccxt.base.errors import ExchangeError as CCXTExchangeError
from ccxt.base.errors import (
    InsufficientFunds,
    InvalidOrder,
    OrderNotFound,
    RateLimitExceeded,
)

from src.exchange.base import (
    BaseExchange,
    ExchangeAPIError,
    ExchangeError,
)
from src.models import OHLCV, Balance, Order, OrderRequest, OrderStatus, Ticker
from src.utils.time import from_unix_ms, now_utc


def _decimal_or_none(value: Any) -> Decimal | None:
    """Coerce a ccxt scalar to ``Decimal``, returning None for null/0/empty.

    ccxt fills numeric fields with ``None`` when the venue did not
    return a value and with ``0`` for "no fill yet" — both cases are
    semantically "absent" for the Order model's optional fields.

    EXCH-F5: moved out of the ``BaseExchange`` port module — this is
    ccxt-adapter knowledge, not port domain.
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

    EXCH-F5: moved out of the ``BaseExchange`` port module — this is
    ccxt-adapter knowledge, not port domain.
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


class CCXTClient(Protocol):
    """Structural subset of the ccxt async client we actually call.

    DEBT-005: ccxt has no type stubs, so its async methods come back as
    untyped. This Protocol covers exactly the calls the ccxt adapters make
    against ``ccxt.async_support`` clients so mypy can check our use without
    pulling in ccxt's whole surface.
    """

    async def load_markets(self, reload: bool = ...) -> dict[str, Any]: ...
    async def close(self) -> None: ...
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = ...,
        since: int | None = ...,
        limit: int | None = ...,
        params: dict[str, Any] = ...,
    ) -> list[list[float]]: ...
    async def fetch_ticker(
        self, symbol: str, params: dict[str, Any] = ...
    ) -> dict[str, Any]: ...
    async def fetch_balance(self, params: dict[str, Any] = ...) -> dict[str, Any]: ...
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float | None = ...,
        params: dict[str, Any] = ...,
    ) -> dict[str, Any]: ...
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        params: dict[str, Any] = ...,
    ) -> dict[str, Any]: ...
    async def cancel_order(
        self,
        id: str,
        symbol: str | None = ...,
        params: dict[str, Any] = ...,
    ) -> dict[str, Any]: ...
    async def fetch_order(
        self,
        id: str,
        symbol: str | None = ...,
        params: dict[str, Any] = ...,
    ) -> dict[str, Any]: ...
    async def fetch_open_orders(
        self,
        symbol: str | None = ...,
        since: int | None = ...,
        limit: int | None = ...,
        params: dict[str, Any] = ...,
    ) -> list[dict[str, Any]]: ...


class CcxtExchange(BaseExchange):
    """Shared base adapter for ccxt-backed exchanges.

    Holds every method that is byte-identical (or trivially parameterized)
    across ``BinanceExchange`` / ``BybitExchange``. Subclasses override only
    the genuinely-divergent surface:

    - ``_build_client(api_key, api_secret)`` — returns the configured ccxt
      client. binance branches on spot/futures and adds an ``options`` block;
      bybit is a single ``ccxt.bybit``. Modeled as a real per-subclass hook so
      the connect divergence is expressed once, in each adapter.
    - ``OHLCV_LIMIT`` — venue cap on candles per page (binance 1500, bybit 200).
    - ``name`` — exchange identifier (set by subclass / ``@register_exchange``).
    - ``logger`` — per-subclass named logger so adapter warnings stay routed to
      the venue-specific logger (the CAH-01 warning tests rely on this).

    Related Requirements:
    - FR-019: Exchange Abstraction
    - NFR-009: Exchange Extensibility
    - FR-010: Paper Trading Mode (via testnet)
    - CON-002: Rate Limit Compliance
    """

    # Subclasses MUST set these.
    OHLCV_LIMIT: int
    logger: Logger

    # Timeframe mapping: project timeframes to ccxt timeframes. Identical
    # across the supported venues.
    TIMEFRAME_MAP: dict[str, str] = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1w",
    }

    def __init__(self, config: Any, testnet: bool = False) -> None:
        """Initialize the ccxt adapter.

        Args:
            config: Venue-specific configuration with API credentials. The
                concrete subclass narrows the annotation to its config type.
            testnet: Whether to use testnet (sandbox) mode.
        """
        super().__init__(testnet=testnet)
        self.config = config
        self._client: CCXTClient | None = None

    def _build_client(self, api_key: str, api_secret: str) -> CCXTClient:
        """Construct the configured ccxt client for this venue.

        Per-subclass hook (CAH-11). The connect divergence between adapters
        (binance's spot/futures branch + extra ``options``, vs bybit's single
        ``ccxt.bybit``) is the only intended behavioral distinction in
        connection setup, expressed here.

        Args:
            api_key: Credential selected against the runtime sandbox flag.
            api_secret: Credential selected against the runtime sandbox flag.

        Returns:
            A configured (not yet validated) ccxt async client.
        """
        raise NotImplementedError(
            "ccxt adapter subclasses must implement _build_client()"
        )

    async def connect(self) -> None:
        """Initialize connection to the exchange.

        Selects credentials against the runtime sandbox flag, builds the venue
        client via ``_build_client``, then validates by loading markets.

        Raises:
            ExchangeConnectionError: If connection or authentication fails
        """
        # Imported lazily so the heavy ccxt error classes used only here for
        # the connect ladder don't change the module import surface.
        from ccxt.base.errors import (
            AuthenticationError,
            ExchangeNotAvailable,
            NetworkError,
        )

        from src.exchange.base import ExchangeConnectionError

        try:
            # Align credential selection with the runtime sandbox flag the
            # exchange was constructed with. The factory may force a mode
            # (paper => testnet=True, live => testnet=False) that differs from
            # the legacy ``<VENUE>_TESTNET`` env default; selecting creds off
            # ``self.testnet`` keeps the ccxt URL and the keys consistent.
            api_key, api_secret = self.config.get_credentials(testnet=self.testnet)

            self._client = self._build_client(api_key, api_secret)

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
        """Close connection to the exchange.

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
        since: int | None = None,
    ) -> list[OHLCV]:
        """Fetch OHLCV candlestick data.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe
            limit: Number of candles (capped at ``OHLCV_LIMIT`` for the venue)
            since: Optional UTC timestamp in milliseconds. Forwarded to
                ccxt's ``fetch_ohlcv(since=...)`` to anchor the returned
                page; ``None`` (default) returns the most recent candles.

        Returns:
            List of OHLCV data points, sorted by timestamp ascending

        Raises:
            ExchangeAPIError: If API request fails
        """
        client = self._ensure_connected()

        try:
            # Cap at the venue's per-page maximum.
            limit = min(limit, self.OHLCV_LIMIT)

            # ccxt returns: [[timestamp, open, high, low, close, volume], ...]
            raw_data = await client.fetch_ohlcv(
                symbol=symbol,
                timeframe=self.TIMEFRAME_MAP[timeframe],
                since=since,
                limit=limit,
            )

            return [
                OHLCV(
                    # DEBT-025: UTC-aware via src.utils.time.from_unix_ms.
                    timestamp=from_unix_ms(candle[0]),
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

            # CAH-01 [BUGFIX]: ccxt returns None timestamps on some venues.
            # A None ticker timestamp is *less* trustworthy than a real one,
            # not maximally fresh — stamping now_utc() here would launder a
            # stale tape into "0 seconds old" and silently defeat the
            # stale-quote gate (DEBT-033). Pass None through so the gate can
            # treat unverifiable freshness as fail-closed; the warning keeps
            # the anomaly visible. The guard also avoids from_unix_ms(None)
            # raising TypeError (which would escape the ExchangeAPIError-only
            # contract below).
            raw_ts = raw_ticker.get("timestamp")
            if raw_ts is None:
                self.logger.warning(
                    "%s returned no ticker timestamp for %s; "
                    "passing through timestamp=None",
                    self.name.capitalize(),
                    symbol,
                )
                ticker_ts = None
            else:
                ticker_ts = from_unix_ms(raw_ts)

            return Ticker(
                symbol=symbol,
                price=Decimal(str(raw_ticker["last"])),
                timestamp=ticker_ts,
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
        """Create a new order.

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

    def _ensure_connected(self) -> CCXTClient:
        """Ensure client is connected and return it.

        EXCH-F3: the per-subclass return annotations (bybit's ``ccxt.bybit``
        vs binance's ``CCXTClient``) collapse to the single ``CCXTClient``
        here.

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
        average_price = _decimal_or_none(raw_order.get("average"))
        fee_amount, fee_currency = _extract_ccxt_fee(raw_order)
        # CAH-01 [BUGFIX]: ccxt returns None timestamps on some venues. Order
        # .created_at is a required (non-nullable) datetime, so fall back to
        # now_utc() rather than letting from_unix_ms(None) raise TypeError and
        # turn an otherwise-valid order into a throw (breaking reconciliation).
        raw_ts = raw_order.get("timestamp")
        if raw_ts is None:
            self.logger.warning(
                "%s returned no timestamp for order %s; "
                "falling back to receipt time for created_at",
                self.name.capitalize(),
                raw_order.get("id"),
            )
            created_at = now_utc()
        else:
            created_at = from_unix_ms(raw_ts)
        return Order(
            id=str(raw_order["id"]),
            symbol=raw_order["symbol"],
            side=raw_order["side"],
            type=raw_order["type"],
            price=_decimal_or_none(raw_order.get("price")),
            quantity=Decimal(str(raw_order["amount"])),
            filled_quantity=Decimal(str(raw_order.get("filled", 0) or 0)),
            average_price=average_price,
            fee=fee_amount,
            fee_currency=fee_currency,
            status=self._map_order_status(raw_order["status"]),
            created_at=created_at,
            updated_at=(
                from_unix_ms(raw_order["lastTradeTimestamp"])
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

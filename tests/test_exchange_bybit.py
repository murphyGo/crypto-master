"""Tests for the Bybit exchange implementation."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from src.config import BybitConfig
from src.exchange.base import ExchangeAPIError, ExchangeConnectionError, ExchangeError
from src.exchange.bybit import BybitExchange
from src.models import OHLCV, Balance, Order, OrderRequest, OrderStatus, Ticker


@pytest.fixture
def bybit_config() -> BybitConfig:
    """Create a test Bybit configuration."""
    return BybitConfig(
        api_key="test_api_key",
        api_secret="test_api_secret",
        testnet=True,
    )


@pytest.fixture
def mock_ccxt_client() -> AsyncMock:
    """Create a mock ccxt client."""
    client = AsyncMock()
    client.load_markets = AsyncMock()
    client.close = AsyncMock()
    return client


class TestBybitExchangeInit:
    """Tests for BybitExchange initialization."""

    def test_initialization_stores_config(self, bybit_config: BybitConfig) -> None:
        """Test config is stored correctly."""
        exchange = BybitExchange(config=bybit_config, testnet=True)
        assert exchange.config is bybit_config
        assert exchange.testnet is True
        assert exchange.name == "bybit"

    def test_client_is_none_before_connect(self, bybit_config: BybitConfig) -> None:
        """Test client is None before connect() is called."""
        exchange = BybitExchange(config=bybit_config, testnet=True)
        assert exchange._client is None

    def test_testnet_defaults_to_false(self, bybit_config: BybitConfig) -> None:
        """Test testnet defaults to False if not specified."""
        exchange = BybitExchange(config=bybit_config)
        assert exchange.testnet is False

    def test_timeframe_map_contains_all_timeframes(self) -> None:
        """Test TIMEFRAME_MAP contains all supported timeframes."""
        expected = {"1m", "5m", "15m", "1h", "4h", "1d", "1w"}
        assert set(BybitExchange.TIMEFRAME_MAP.keys()) == expected

    def test_url_constants_exist(self) -> None:
        """Test URL constants are defined for reference."""
        assert BybitExchange.MAINNET_URL == "https://api.bybit.com"
        assert BybitExchange.TESTNET_URL == "https://api-testnet.bybit.com"


class TestBybitExchangeConnect:
    """Tests for connect/disconnect methods."""

    @pytest.mark.asyncio
    async def test_connect_creates_client(self, bybit_config: BybitConfig) -> None:
        """Test connect creates bybit client."""
        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_client = AsyncMock()
            mock_class.return_value = mock_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            mock_class.assert_called_once()
            assert exchange._client is mock_client

    @pytest.mark.asyncio
    async def test_connect_loads_markets(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test connect calls load_markets to validate connection."""
        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            mock_ccxt_client.load_markets.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_sets_sandbox_mode(self, bybit_config: BybitConfig) -> None:
        """Test connect sets sandbox=True when testnet is enabled."""
        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_client = AsyncMock()
            mock_class.return_value = mock_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            # Check the config passed to ccxt
            call_args = mock_class.call_args[0][0]
            assert call_args["sandbox"] is True
            assert call_args["enableRateLimit"] is True

    @pytest.mark.asyncio
    async def test_connect_uses_testnet_credentials(self) -> None:
        """Test connect uses testnet credentials when testnet=True."""
        config = BybitConfig(
            api_key="live_key",
            api_secret="live_secret",
            testnet_api_key="testnet_key",
            testnet_api_secret="testnet_secret",
            testnet=True,
        )

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_client = AsyncMock()
            mock_class.return_value = mock_client

            exchange = BybitExchange(config=config, testnet=True)
            await exchange.connect()

            # Check the credentials passed to ccxt
            call_args = mock_class.call_args[0][0]
            assert call_args["apiKey"] == "testnet_key"
            assert call_args["secret"] == "testnet_secret"

    @pytest.mark.asyncio
    async def test_connect_uses_live_credentials_when_testnet_false(self) -> None:
        """Test connect uses live credentials when testnet=False."""
        config = BybitConfig(
            api_key="live_key",
            api_secret="live_secret",
            testnet_api_key="testnet_key",
            testnet_api_secret="testnet_secret",
            testnet=False,
        )

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_client = AsyncMock()
            mock_class.return_value = mock_client

            exchange = BybitExchange(config=config, testnet=False)
            await exchange.connect()

            # Check the credentials passed to ccxt
            call_args = mock_class.call_args[0][0]
            assert call_args["apiKey"] == "live_key"
            assert call_args["secret"] == "live_secret"
            assert call_args["sandbox"] is False

    @pytest.mark.asyncio
    async def test_connect_authentication_error(
        self, bybit_config: BybitConfig
    ) -> None:
        """Test connect raises ExchangeConnectionError on auth failure."""
        from ccxt.base.errors import AuthenticationError

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_client = AsyncMock()
            mock_client.load_markets.side_effect = AuthenticationError("Invalid key")
            mock_class.return_value = mock_client

            exchange = BybitExchange(config=bybit_config, testnet=True)

            with pytest.raises(ExchangeConnectionError) as exc_info:
                await exchange.connect()
            assert "Authentication failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_network_error(self, bybit_config: BybitConfig) -> None:
        """Test connect raises ExchangeConnectionError on network failure."""
        from ccxt.base.errors import NetworkError

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_client = AsyncMock()
            mock_client.load_markets.side_effect = NetworkError("Connection timeout")
            mock_class.return_value = mock_client

            exchange = BybitExchange(config=bybit_config, testnet=True)

            with pytest.raises(ExchangeConnectionError) as exc_info:
                await exchange.connect()
            assert "Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect_closes_client(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test disconnect closes the ccxt client."""
        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()
            await exchange.disconnect()

            mock_ccxt_client.close.assert_called_once()
            assert exchange._client is None

    @pytest.mark.asyncio
    async def test_disconnect_handles_none_client(
        self, bybit_config: BybitConfig
    ) -> None:
        """Test disconnect handles case when client is None."""
        exchange = BybitExchange(config=bybit_config, testnet=True)
        # Should not raise
        await exchange.disconnect()
        assert exchange._client is None


class TestBybitExchangeOHLCV:
    """Tests for get_ohlcv method."""

    @pytest.mark.asyncio
    async def test_get_ohlcv_returns_list(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_ohlcv returns list of OHLCV."""
        mock_ccxt_client.fetch_ohlcv.return_value = [
            [1704067200000, 42000.0, 42500.0, 41800.0, 42300.0, 1000.0],
            [1704070800000, 42300.0, 42600.0, 42100.0, 42400.0, 1200.0],
        ]

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_ohlcv("BTC/USDT", "1h", limit=100)

            assert len(result) == 2
            assert isinstance(result[0], OHLCV)
            assert result[0].open == Decimal("42000.0")
            assert result[0].high == Decimal("42500.0")
            assert result[0].low == Decimal("41800.0")
            assert result[0].close == Decimal("42300.0")
            assert result[0].volume == Decimal("1000.0")

    @pytest.mark.asyncio
    async def test_get_ohlcv_limits_to_200(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_ohlcv limits to max 200 candles (Bybit limit)."""
        mock_ccxt_client.fetch_ohlcv.return_value = []

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            await exchange.get_ohlcv("BTC/USDT", "1h", limit=500)

            # Verify limit was capped at 200
            call_kwargs = mock_ccxt_client.fetch_ohlcv.call_args[1]
            assert call_kwargs["limit"] == 200

    @pytest.mark.asyncio
    async def test_get_ohlcv_converts_timestamp(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_ohlcv converts millisecond timestamp to datetime."""
        mock_ccxt_client.fetch_ohlcv.return_value = [
            [1704067200000, 42000.0, 42500.0, 41800.0, 42300.0, 1000.0],
        ]

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_ohlcv("BTC/USDT", "1h")

            assert isinstance(result[0].timestamp, datetime)

    @pytest.mark.asyncio
    async def test_get_ohlcv_raises_on_not_connected(
        self, bybit_config: BybitConfig
    ) -> None:
        """Test get_ohlcv raises error if not connected."""
        exchange = BybitExchange(config=bybit_config, testnet=True)

        with pytest.raises(ExchangeError) as exc_info:
            await exchange.get_ohlcv("BTC/USDT", "1h")
        assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_ohlcv_rate_limit_error(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_ohlcv handles rate limit error."""
        from ccxt.base.errors import RateLimitExceeded

        mock_ccxt_client.fetch_ohlcv.side_effect = RateLimitExceeded("Too many requests")

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            with pytest.raises(ExchangeAPIError) as exc_info:
                await exchange.get_ohlcv("BTC/USDT", "1h")
            assert exc_info.value.code == "RATE_LIMIT"


class TestBybitExchangeTicker:
    """Tests for get_ticker method."""

    @pytest.mark.asyncio
    async def test_get_ticker_returns_ticker(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_ticker returns Ticker."""
        mock_ccxt_client.fetch_ticker.return_value = {
            "symbol": "BTC/USDT",
            "last": 42500.0,
            "timestamp": 1704067200000,
        }

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_ticker("BTC/USDT")

            assert isinstance(result, Ticker)
            assert result.symbol == "BTC/USDT"
            assert result.price == Decimal("42500.0")

    @pytest.mark.asyncio
    async def test_get_ticker_converts_timestamp(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_ticker converts timestamp correctly."""
        mock_ccxt_client.fetch_ticker.return_value = {
            "symbol": "BTC/USDT",
            "last": 42500.0,
            "timestamp": 1704067200000,
        }

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_ticker("BTC/USDT")

            assert isinstance(result.timestamp, datetime)


class TestBybitExchangeBalance:
    """Tests for get_balance method."""

    @pytest.mark.asyncio
    async def test_get_balance_returns_balances(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_balance returns Balance list."""
        mock_ccxt_client.fetch_balance.return_value = {
            "USDT": {"free": 1000.0, "used": 200.0, "total": 1200.0},
            "BTC": {"free": 0.5, "used": 0.0, "total": 0.5},
            "info": {},  # Metadata - should be skipped
            "timestamp": 1704067200000,
            "datetime": "2024-01-01T00:00:00.000Z",
            "free": {},
            "used": {},
            "total": {},
        }

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_balance()

            assert len(result) == 2
            usdt = next(b for b in result if b.currency == "USDT")
            assert usdt.free == Decimal("1000.0")
            assert usdt.locked == Decimal("200.0")
            assert usdt.total == Decimal("1200.0")

    @pytest.mark.asyncio
    async def test_get_balance_with_currency_filter(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_balance filters by currency."""
        mock_ccxt_client.fetch_balance.return_value = {
            "USDT": {"free": 1000.0, "used": 0.0, "total": 1000.0},
            "BTC": {"free": 0.5, "used": 0.0, "total": 0.5},
        }

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_balance("USDT")

            assert len(result) == 1
            assert result[0].currency == "USDT"

    @pytest.mark.asyncio
    async def test_get_balance_skips_zero_balances(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_balance skips currencies with zero balance."""
        mock_ccxt_client.fetch_balance.return_value = {
            "USDT": {"free": 1000.0, "used": 0.0, "total": 1000.0},
            "ETH": {"free": 0.0, "used": 0.0, "total": 0.0},
        }

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_balance()

            assert len(result) == 1
            assert result[0].currency == "USDT"


class TestBybitExchangeOrders:
    """Tests for order methods."""

    @pytest.mark.asyncio
    async def test_create_market_order(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test create_order with market order."""
        mock_ccxt_client.create_market_order.return_value = {
            "id": "12345",
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "market",
            "price": None,
            "amount": 0.1,
            "filled": 0.1,
            "status": "closed",
            "timestamp": 1704067200000,
            "lastTradeTimestamp": 1704067200000,
        }

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            request = OrderRequest(
                symbol="BTC/USDT",
                side="buy",
                type="market",
                quantity=Decimal("0.1"),
            )
            result = await exchange.create_order(request)

            assert isinstance(result, Order)
            assert result.id == "12345"
            assert result.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_create_limit_order(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test create_order with limit order."""
        mock_ccxt_client.create_limit_order.return_value = {
            "id": "12346",
            "symbol": "BTC/USDT",
            "side": "sell",
            "type": "limit",
            "price": 45000.0,
            "amount": 0.1,
            "filled": 0.0,
            "status": "open",
            "timestamp": 1704067200000,
            "lastTradeTimestamp": None,
        }

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            request = OrderRequest(
                symbol="BTC/USDT",
                side="sell",
                type="limit",
                quantity=Decimal("0.1"),
                price=Decimal("45000.0"),
            )
            result = await exchange.create_order(request)

            assert result.type == "limit"
            assert result.price == Decimal("45000.0")
            assert result.status == OrderStatus.OPEN

    @pytest.mark.asyncio
    async def test_create_order_invalid_order_error(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test create_order handles invalid order error."""
        from ccxt.base.errors import InvalidOrder

        mock_ccxt_client.create_market_order.side_effect = InvalidOrder("Invalid qty")

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            request = OrderRequest(
                symbol="BTC/USDT",
                side="buy",
                type="market",
                quantity=Decimal("0.0001"),
            )

            with pytest.raises(ExchangeAPIError) as exc_info:
                await exchange.create_order(request)
            assert exc_info.value.code == "INVALID_ORDER"

    @pytest.mark.asyncio
    async def test_create_order_insufficient_funds_error(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test create_order handles insufficient funds error."""
        from ccxt.base.errors import InsufficientFunds

        mock_ccxt_client.create_market_order.side_effect = InsufficientFunds(
            "Insufficient balance"
        )

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            request = OrderRequest(
                symbol="BTC/USDT",
                side="buy",
                type="market",
                quantity=Decimal("1000"),
            )

            with pytest.raises(ExchangeAPIError) as exc_info:
                await exchange.create_order(request)
            assert exc_info.value.code == "INSUFFICIENT_FUNDS"

    @pytest.mark.asyncio
    async def test_cancel_order_success(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test cancel_order returns True on success."""
        mock_ccxt_client.cancel_order.return_value = {}

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            result = await exchange.cancel_order("12345", "BTC/USDT")

            assert result is True

    @pytest.mark.asyncio
    async def test_cancel_order_not_found(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test cancel_order returns False when order not found."""
        from ccxt.base.errors import OrderNotFound

        mock_ccxt_client.cancel_order.side_effect = OrderNotFound("Order not found")

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            result = await exchange.cancel_order("99999", "BTC/USDT")

            assert result is False

    @pytest.mark.asyncio
    async def test_get_order_returns_order(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_order returns Order."""
        mock_ccxt_client.fetch_order.return_value = {
            "id": "12345",
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "limit",
            "price": 42000.0,
            "amount": 0.1,
            "filled": 0.1,
            "status": "closed",
            "timestamp": 1704067200000,
            "lastTradeTimestamp": 1704067200000,
        }

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_order("12345", "BTC/USDT")

            assert isinstance(result, Order)
            assert result.id == "12345"
            assert result.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_get_order_not_found(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_order raises error when order not found."""
        from ccxt.base.errors import OrderNotFound

        mock_ccxt_client.fetch_order.side_effect = OrderNotFound("Order not found")

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            with pytest.raises(ExchangeAPIError) as exc_info:
                await exchange.get_order("99999", "BTC/USDT")
            assert exc_info.value.code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_open_orders_returns_list(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_open_orders returns list of orders."""
        mock_ccxt_client.fetch_open_orders.return_value = [
            {
                "id": "12345",
                "symbol": "BTC/USDT",
                "side": "buy",
                "type": "limit",
                "price": 40000.0,
                "amount": 0.1,
                "filled": 0.0,
                "status": "open",
                "timestamp": 1704067200000,
                "lastTradeTimestamp": None,
            },
            {
                "id": "12346",
                "symbol": "BTC/USDT",
                "side": "sell",
                "type": "limit",
                "price": 45000.0,
                "amount": 0.1,
                "filled": 0.0,
                "status": "open",
                "timestamp": 1704067200000,
                "lastTradeTimestamp": None,
            },
        ]

        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_open_orders("BTC/USDT")

            assert len(result) == 2
            assert all(isinstance(o, Order) for o in result)
            assert all(o.status == OrderStatus.OPEN for o in result)


class TestBybitExchangeOrderStatusMapping:
    """Tests for order status mapping."""

    def test_map_order_status_open(self, bybit_config: BybitConfig) -> None:
        """Test mapping 'open' status."""
        exchange = BybitExchange(config=bybit_config, testnet=True)
        assert exchange._map_order_status("open") == OrderStatus.OPEN

    def test_map_order_status_closed(self, bybit_config: BybitConfig) -> None:
        """Test mapping 'closed' status to FILLED."""
        exchange = BybitExchange(config=bybit_config, testnet=True)
        assert exchange._map_order_status("closed") == OrderStatus.FILLED

    def test_map_order_status_canceled(self, bybit_config: BybitConfig) -> None:
        """Test mapping 'canceled' status."""
        exchange = BybitExchange(config=bybit_config, testnet=True)
        assert exchange._map_order_status("canceled") == OrderStatus.CANCELLED

    def test_map_order_status_expired(self, bybit_config: BybitConfig) -> None:
        """Test mapping 'expired' status to CANCELLED."""
        exchange = BybitExchange(config=bybit_config, testnet=True)
        assert exchange._map_order_status("expired") == OrderStatus.CANCELLED

    def test_map_order_status_rejected(self, bybit_config: BybitConfig) -> None:
        """Test mapping 'rejected' status."""
        exchange = BybitExchange(config=bybit_config, testnet=True)
        assert exchange._map_order_status("rejected") == OrderStatus.REJECTED

    def test_map_order_status_unknown(self, bybit_config: BybitConfig) -> None:
        """Test mapping unknown status defaults to PENDING."""
        exchange = BybitExchange(config=bybit_config, testnet=True)
        assert exchange._map_order_status("unknown") == OrderStatus.PENDING


class TestBybitExchangeContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_connects_and_disconnects(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test async context manager protocol."""
        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)
            assert exchange._client is None

            async with exchange as ex:
                assert ex is exchange
                assert exchange._client is not None

            assert exchange._client is None

    @pytest.mark.asyncio
    async def test_context_manager_disconnects_on_exception(
        self, bybit_config: BybitConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test context manager disconnects even on exception."""
        with patch("src.exchange.bybit.ccxt.bybit") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BybitExchange(config=bybit_config, testnet=True)

            with pytest.raises(ValueError):
                async with exchange:
                    assert exchange._client is not None
                    raise ValueError("Test exception")

            assert exchange._client is None


class TestBybitExchangeRegistration:
    """Tests for exchange registration."""

    def test_bybit_is_registered(self) -> None:
        """Test BybitExchange is registered with factory."""
        from src.exchange.factory import _exchange_registry

        assert "bybit" in _exchange_registry
        assert _exchange_registry["bybit"] is BybitExchange

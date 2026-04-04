"""Tests for the exchange abstraction layer."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest

from src.exchange.base import (
    BaseExchange,
    ExchangeAPIError,
    ExchangeConnectionError,
    ExchangeError,
)
from src.exchange.factory import (
    _exchange_registry,
    create_exchange,
    get_available_exchanges,
    get_configured_exchanges,
    register_exchange,
)
from src.models import OHLCV, Balance, Order, OrderRequest, OrderStatus, Ticker


class TestExchangeErrors:
    """Tests for exchange error classes."""

    def test_exchange_error_is_exception(self) -> None:
        """Test ExchangeError inherits from Exception."""
        error = ExchangeError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_exchange_connection_error_inherits_from_exchange_error(self) -> None:
        """Test ExchangeConnectionError inherits from ExchangeError."""
        error = ExchangeConnectionError("Connection failed")
        assert isinstance(error, ExchangeError)
        assert isinstance(error, Exception)

    def test_exchange_api_error_inherits_from_exchange_error(self) -> None:
        """Test ExchangeAPIError inherits from ExchangeError."""
        error = ExchangeAPIError("API error")
        assert isinstance(error, ExchangeError)
        assert isinstance(error, Exception)

    def test_exchange_api_error_stores_code(self) -> None:
        """Test ExchangeAPIError stores error code."""
        error = ExchangeAPIError("Rate limited", code="429")
        assert error.code == "429"
        assert str(error) == "Rate limited"

    def test_exchange_api_error_code_is_optional(self) -> None:
        """Test ExchangeAPIError code is optional."""
        error = ExchangeAPIError("Generic error")
        assert error.code is None


class TestBaseExchangeAbstract:
    """Tests for BaseExchange abstract class."""

    def test_cannot_instantiate_directly(self) -> None:
        """Test BaseExchange cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            BaseExchange()  # type: ignore
        assert "abstract" in str(exc_info.value).lower()

    def test_must_implement_all_abstract_methods(self) -> None:
        """Test that subclass must implement all abstract methods."""

        class IncompleteExchange(BaseExchange):
            name = "incomplete"

            async def connect(self) -> None:
                pass

            # Missing other abstract methods

        with pytest.raises(TypeError):
            IncompleteExchange()  # type: ignore


class MockExchange(BaseExchange):
    """Mock exchange implementation for testing."""

    name = "mock"

    def __init__(
        self, config: object = None, testnet: bool = False, should_fail: bool = False
    ) -> None:
        """Initialize mock exchange."""
        self.config = config
        self.testnet = testnet
        self.should_fail = should_fail
        self.connected = False

    async def connect(self) -> None:
        """Connect to mock exchange."""
        if self.should_fail:
            raise ExchangeConnectionError("Mock connection failed")
        self.connected = True

    async def disconnect(self) -> None:
        """Disconnect from mock exchange."""
        self.connected = False

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w"],
        limit: int = 100,
    ) -> list[OHLCV]:
        """Get mock OHLCV data."""
        return [
            OHLCV(
                timestamp=datetime.now(),
                open=Decimal("100"),
                high=Decimal("105"),
                low=Decimal("95"),
                close=Decimal("102"),
                volume=Decimal("1000"),
            )
        ]

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get mock ticker."""
        return Ticker(symbol=symbol, price=Decimal("50000"), timestamp=datetime.now())

    async def get_balance(self, currency: str | None = None) -> list[Balance]:
        """Get mock balance."""
        return [Balance(currency="USDT", free=Decimal("1000"), total=Decimal("1000"))]

    async def create_order(self, order: OrderRequest) -> Order:
        """Create mock order."""
        return Order(
            id="mock_order_1",
            symbol=order.symbol,
            side=order.side,
            type=order.type,
            price=order.price,
            quantity=order.quantity,
            status=OrderStatus.OPEN,
            created_at=datetime.now(),
        )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel mock order."""
        return True

    async def get_order(self, order_id: str, symbol: str) -> Order:
        """Get mock order."""
        return Order(
            id=order_id,
            symbol=symbol,
            side="buy",
            type="limit",
            price=Decimal("50000"),
            quantity=Decimal("0.1"),
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
        )

    async def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        """Get mock open orders."""
        return []


class TestBaseExchangeImplementation:
    """Tests for BaseExchange with concrete implementation."""

    def test_can_instantiate_complete_implementation(self) -> None:
        """Test that complete implementation can be instantiated."""
        exchange = MockExchange()
        assert exchange.name == "mock"

    @pytest.mark.asyncio
    async def test_connect_sets_connected(self) -> None:
        """Test connect method works."""
        exchange = MockExchange()
        assert not exchange.connected
        await exchange.connect()
        assert exchange.connected

    @pytest.mark.asyncio
    async def test_disconnect_unsets_connected(self) -> None:
        """Test disconnect method works."""
        exchange = MockExchange()
        await exchange.connect()
        await exchange.disconnect()
        assert not exchange.connected

    @pytest.mark.asyncio
    async def test_connect_failure_raises_error(self) -> None:
        """Test connection failure raises ExchangeConnectionError."""
        exchange = MockExchange(should_fail=True)
        with pytest.raises(ExchangeConnectionError):
            await exchange.connect()

    @pytest.mark.asyncio
    async def test_context_manager_connects_and_disconnects(self) -> None:
        """Test async context manager protocol."""
        exchange = MockExchange()
        assert not exchange.connected

        async with exchange as ex:
            assert ex is exchange
            assert exchange.connected

        assert not exchange.connected

    @pytest.mark.asyncio
    async def test_context_manager_disconnects_on_exception(self) -> None:
        """Test context manager disconnects even on exception."""
        exchange = MockExchange()

        with pytest.raises(ValueError):
            async with exchange:
                assert exchange.connected
                raise ValueError("Test exception")

        assert not exchange.connected

    @pytest.mark.asyncio
    async def test_get_ohlcv_returns_list(self) -> None:
        """Test get_ohlcv returns OHLCV list."""
        exchange = MockExchange()
        ohlcv = await exchange.get_ohlcv("BTC/USDT", "1h")
        assert isinstance(ohlcv, list)
        assert len(ohlcv) > 0
        assert isinstance(ohlcv[0], OHLCV)

    @pytest.mark.asyncio
    async def test_get_ticker_returns_ticker(self) -> None:
        """Test get_ticker returns Ticker."""
        exchange = MockExchange()
        ticker = await exchange.get_ticker("BTC/USDT")
        assert isinstance(ticker, Ticker)
        assert ticker.symbol == "BTC/USDT"

    @pytest.mark.asyncio
    async def test_get_balance_returns_list(self) -> None:
        """Test get_balance returns Balance list."""
        exchange = MockExchange()
        balances = await exchange.get_balance()
        assert isinstance(balances, list)
        assert len(balances) > 0
        assert isinstance(balances[0], Balance)

    @pytest.mark.asyncio
    async def test_create_order_returns_order(self) -> None:
        """Test create_order returns Order."""
        exchange = MockExchange()
        request = OrderRequest(
            symbol="BTC/USDT",
            side="buy",
            type="market",
            quantity=Decimal("0.1"),
        )
        order = await exchange.create_order(request)
        assert isinstance(order, Order)
        assert order.symbol == "BTC/USDT"

    @pytest.mark.asyncio
    async def test_cancel_order_returns_bool(self) -> None:
        """Test cancel_order returns bool."""
        exchange = MockExchange()
        result = await exchange.cancel_order("order_123", "BTC/USDT")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_get_order_returns_order(self) -> None:
        """Test get_order returns Order."""
        exchange = MockExchange()
        order = await exchange.get_order("order_123", "BTC/USDT")
        assert isinstance(order, Order)
        assert order.id == "order_123"

    @pytest.mark.asyncio
    async def test_get_open_orders_returns_list(self) -> None:
        """Test get_open_orders returns Order list."""
        exchange = MockExchange()
        orders = await exchange.get_open_orders()
        assert isinstance(orders, list)


@pytest.fixture(autouse=True)
def clean_registry():
    """Clean exchange registry before and after each test."""
    # Save current registry
    saved = dict(_exchange_registry)
    _exchange_registry.clear()
    yield
    # Restore registry
    _exchange_registry.clear()
    _exchange_registry.update(saved)


class TestRegisterExchange:
    """Tests for register_exchange decorator."""

    def test_registers_exchange_in_registry(self) -> None:
        """Test register_exchange adds class to registry."""

        @register_exchange("test_exchange")
        class TestExchange(MockExchange):
            name = "test_exchange"

        assert "test_exchange" in _exchange_registry
        assert _exchange_registry["test_exchange"] is TestExchange

    def test_registry_is_case_insensitive(self) -> None:
        """Test exchange names are stored lowercase."""

        @register_exchange("MyExchange")
        class TestExchange(MockExchange):
            name = "myexchange"

        assert "myexchange" in _exchange_registry
        assert "MyExchange" not in _exchange_registry

    def test_returns_original_class(self) -> None:
        """Test decorator returns the original class."""

        @register_exchange("another")
        class AnotherExchange(MockExchange):
            name = "another"

        assert AnotherExchange.name == "another"


class TestGetAvailableExchanges:
    """Tests for get_available_exchanges function."""

    def test_returns_empty_list_when_no_exchanges(self) -> None:
        """Test returns empty list when no exchanges registered."""
        result = get_available_exchanges()
        assert result == []

    def test_returns_registered_exchanges(self) -> None:
        """Test returns list of registered exchange names."""

        @register_exchange("exchange_a")
        class ExchangeA(MockExchange):
            name = "exchange_a"

        @register_exchange("exchange_b")
        class ExchangeB(MockExchange):
            name = "exchange_b"

        result = get_available_exchanges()
        assert set(result) == {"exchange_a", "exchange_b"}


class TestCreateExchange:
    """Tests for create_exchange factory function."""

    def test_raises_error_for_unregistered_exchange(self) -> None:
        """Test create_exchange raises error for unknown exchange."""
        with pytest.raises(ExchangeError) as exc_info:
            create_exchange("unknown")
        assert "not registered" in str(exc_info.value)
        assert "unknown" in str(exc_info.value)

    def test_raises_error_with_available_exchanges_in_message(self) -> None:
        """Test error message includes available exchanges."""

        @register_exchange("available")
        class AvailableExchange(MockExchange):
            name = "available"

        with pytest.raises(ExchangeError) as exc_info:
            create_exchange("unknown")
        assert "available" in str(exc_info.value).lower()

    def test_is_case_insensitive(self) -> None:
        """Test create_exchange is case insensitive."""

        @register_exchange("testex")
        class TestEx(MockExchange):
            name = "testex"

        # Mock the config check to pass
        with patch("src.exchange.factory.get_settings") as mock_settings:
            mock_config = MagicMock()
            mock_config.is_configured.return_value = True
            mock_config.testnet = False
            mock_settings.return_value.binance = mock_config
            mock_settings.return_value.bybit = mock_config

            # This would fail config check, but we're testing case insensitivity
            # of the registry lookup
            with pytest.raises(ExchangeError) as exc_info:
                create_exchange("TESTEX")
            # Should get past registry check and fail on config check
            assert "not configured" in str(exc_info.value)

    def test_creates_exchange_with_config(self) -> None:
        """Test create_exchange passes config to exchange."""

        @register_exchange("binance")
        class TestBinance(MockExchange):
            name = "binance"

        with patch("src.exchange.factory.get_settings") as mock_settings:
            mock_config = MagicMock()
            mock_config.is_configured.return_value = True
            mock_config.testnet = False
            mock_settings.return_value.binance = mock_config

            exchange = create_exchange("binance")
            assert exchange.config is mock_config
            assert exchange.testnet is False

    def test_testnet_override(self) -> None:
        """Test testnet parameter overrides config."""

        @register_exchange("binance")
        class TestBinance(MockExchange):
            name = "binance"

        with patch("src.exchange.factory.get_settings") as mock_settings:
            mock_config = MagicMock()
            mock_config.is_configured.return_value = True
            mock_config.testnet = False  # Config says False
            mock_settings.return_value.binance = mock_config

            exchange = create_exchange("binance", testnet=True)  # Override to True
            assert exchange.testnet is True

    def test_raises_error_for_unconfigured_exchange(self) -> None:
        """Test create_exchange raises error if credentials not configured."""

        @register_exchange("binance")
        class TestBinance(MockExchange):
            name = "binance"

        with patch("src.exchange.factory.get_settings") as mock_settings:
            mock_config = MagicMock()
            mock_config.is_configured.return_value = False  # Not configured
            mock_settings.return_value.binance = mock_config

            with pytest.raises(ExchangeError) as exc_info:
                create_exchange("binance")
            assert "credentials not configured" in str(exc_info.value)


class TestGetConfiguredExchanges:
    """Tests for get_configured_exchanges function."""

    def test_returns_empty_when_none_configured(self) -> None:
        """Test returns empty list when no exchanges configured."""

        @register_exchange("binance")
        class TestBinance(MockExchange):
            name = "binance"

        with patch("src.exchange.factory.get_settings") as mock_settings:
            mock_config = MagicMock()
            mock_config.is_configured.return_value = False
            mock_settings.return_value.binance = mock_config
            mock_settings.return_value.bybit = mock_config

            result = get_configured_exchanges()
            assert result == []

    def test_returns_only_configured_exchanges(self) -> None:
        """Test returns only exchanges that are configured."""

        @register_exchange("binance")
        class TestBinance(MockExchange):
            name = "binance"

        @register_exchange("bybit")
        class TestBybit(MockExchange):
            name = "bybit"

        with patch("src.exchange.factory.get_settings") as mock_settings:
            mock_binance = MagicMock()
            mock_binance.is_configured.return_value = True

            mock_bybit = MagicMock()
            mock_bybit.is_configured.return_value = False

            mock_settings.return_value.binance = mock_binance
            mock_settings.return_value.bybit = mock_bybit

            result = get_configured_exchanges()
            assert result == ["binance"]

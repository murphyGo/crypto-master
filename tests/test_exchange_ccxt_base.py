"""Tests for the shared ccxt adapter base (CAH-11).

Proves the NFR-009 extensibility goal: a new ccxt-backed exchange is a new
adapter that overrides only ``_build_client()`` + ``OHLCV_LIMIT`` (plus name /
logger wiring), with NO edits to sibling adapters or the base. The toy adapter
below drives every shared method end-to-end against a mocked client.

The behaviour-preservation proof for Binance/Bybit specifically lives in
``test_exchange_binance.py`` / ``test_exchange_bybit.py`` (unchanged).
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.exchange.base import ExchangeAPIError, ExchangeError
from src.exchange.ccxt_base import (
    CCXTClient,
    CcxtExchange,
    _decimal_or_none,
    _extract_ccxt_fee,
)
from src.models import OHLCV, Order, OrderRequest, OrderStatus, Ticker

_toy_logger = logging.getLogger("crypto_master.exchange.toy")


class _ToyConfig:
    """Minimal config exposing the credential hook the base relies on."""

    def __init__(self, testnet_key: str = "tk", live_key: str = "lk") -> None:
        self.testnet_key = testnet_key
        self.live_key = live_key
        self.captured_testnet: bool | None = None

    def get_credentials(self, testnet: bool | None = None) -> tuple[str, str]:
        self.captured_testnet = testnet
        if testnet:
            return self.testnet_key, f"{self.testnet_key}_secret"
        return self.live_key, f"{self.live_key}_secret"


class ToyExchange(CcxtExchange):
    """A toy ccxt adapter overriding only the divergent surface (NFR-009)."""

    name = "toy"
    logger = _toy_logger
    OHLCV_LIMIT = 42

    def __init__(self, config: _ToyConfig, testnet: bool = False) -> None:
        super().__init__(config=config, testnet=testnet)
        self.config: _ToyConfig = config
        self.built_client: CCXTClient | None = None
        self.build_args: tuple[str, str] | None = None

    def _build_client(self, api_key: str, api_secret: str) -> CCXTClient:
        self.build_args = (api_key, api_secret)
        client = AsyncMock()
        client.load_markets = AsyncMock()
        client.close = AsyncMock()
        self.built_client = client
        return client


@pytest.fixture
def toy_config() -> _ToyConfig:
    return _ToyConfig()


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.load_markets = AsyncMock()
    client.close = AsyncMock()
    return client


async def _connected(config: _ToyConfig, client: AsyncMock) -> ToyExchange:
    """Build a ToyExchange whose ``_build_client`` returns ``client``."""
    exchange = ToyExchange(config=config, testnet=True)
    exchange._client = client  # bypass _build_client for method-level tests
    return exchange


class TestToyAdapterWiring:
    """The subclass-only overrides are honoured by the base."""

    def test_inherits_shared_timeframe_map(self) -> None:
        expected = {"1m", "5m", "15m", "1h", "4h", "1d", "1w"}
        assert set(ToyExchange.TIMEFRAME_MAP.keys()) == expected

    def test_client_none_before_connect(self, toy_config: _ToyConfig) -> None:
        assert ToyExchange(config=toy_config)._client is None

    def test_ensure_connected_raises_when_disconnected(
        self, toy_config: _ToyConfig
    ) -> None:
        with pytest.raises(ExchangeError, match="Not connected"):
            ToyExchange(config=toy_config)._ensure_connected()


class TestToyAdapterConnect:
    """connect() uses the _build_client hook and validates via load_markets."""

    async def test_connect_uses_build_client_hook(
        self, toy_config: _ToyConfig
    ) -> None:
        exchange = ToyExchange(config=toy_config, testnet=True)
        await exchange.connect()

        assert exchange._client is exchange.built_client
        # Credentials selected against runtime sandbox flag (testnet=True).
        assert toy_config.captured_testnet is True
        assert exchange.build_args == ("tk", "tk_secret")
        exchange.built_client.load_markets.assert_called_once()  # type: ignore[union-attr]

    async def test_connect_live_credentials(self, toy_config: _ToyConfig) -> None:
        exchange = ToyExchange(config=toy_config, testnet=False)
        await exchange.connect()
        assert exchange.build_args == ("lk", "lk_secret")

    async def test_connect_wraps_failure(self, toy_config: _ToyConfig) -> None:
        from src.exchange.base import ExchangeConnectionError

        class FailingToy(ToyExchange):
            def _build_client(self, api_key: str, api_secret: str) -> CCXTClient:
                client = AsyncMock()
                client.load_markets = AsyncMock(side_effect=RuntimeError("boom"))
                return client

        with pytest.raises(ExchangeConnectionError, match="Failed to connect"):
            await FailingToy(config=toy_config, testnet=True).connect()

    async def test_disconnect_closes_client(self, toy_config: _ToyConfig) -> None:
        exchange = ToyExchange(config=toy_config, testnet=True)
        await exchange.connect()
        client = exchange._client
        await exchange.disconnect()
        client.close.assert_called_once()  # type: ignore[union-attr]
        assert exchange._client is None


class TestToyAdapterOhlcv:
    async def test_get_ohlcv_caps_at_subclass_limit(
        self, toy_config: _ToyConfig, mock_client: AsyncMock
    ) -> None:
        mock_client.fetch_ohlcv.return_value = []
        exchange = await _connected(toy_config, mock_client)

        await exchange.get_ohlcv("BTC/USDT", "1h", limit=1000)

        # The toy OHLCV_LIMIT (42) caps the request — proves the constant hook.
        assert mock_client.fetch_ohlcv.call_args[1]["limit"] == 42

    async def test_get_ohlcv_maps_candles(
        self, toy_config: _ToyConfig, mock_client: AsyncMock
    ) -> None:
        mock_client.fetch_ohlcv.return_value = [
            [1704067200000, 42000.0, 42500.0, 41800.0, 42300.0, 1000.0],
        ]
        exchange = await _connected(toy_config, mock_client)

        result = await exchange.get_ohlcv("BTC/USDT", "1h")

        assert len(result) == 1
        candle = result[0]
        assert isinstance(candle, OHLCV)
        assert candle.open == Decimal("42000.0")
        assert candle.close == Decimal("42300.0")

    async def test_get_ohlcv_translates_ccxt_error(
        self, toy_config: _ToyConfig, mock_client: AsyncMock
    ) -> None:
        from ccxt.base.errors import ExchangeError as CCXTExchangeError

        mock_client.fetch_ohlcv.side_effect = CCXTExchangeError("down")
        exchange = await _connected(toy_config, mock_client)

        with pytest.raises(ExchangeAPIError, match="Failed to fetch OHLCV"):
            await exchange.get_ohlcv("BTC/USDT", "1h")


class TestToyAdapterTicker:
    async def test_get_ticker_maps_price(
        self, toy_config: _ToyConfig, mock_client: AsyncMock
    ) -> None:
        mock_client.fetch_ticker.return_value = {
            "last": 42000.0,
            "timestamp": 1704067200000,
        }
        exchange = await _connected(toy_config, mock_client)

        ticker = await exchange.get_ticker("BTC/USDT")

        assert isinstance(ticker, Ticker)
        assert ticker.price == Decimal("42000.0")
        assert ticker.timestamp == datetime(2024, 1, 1, tzinfo=timezone.utc)

    async def test_get_ticker_none_timestamp_passes_through(
        self,
        toy_config: _ToyConfig,
        mock_client: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """CAH-01 guard lives once in the base — None ts -> None, warning."""
        mock_client.fetch_ticker.return_value = {"last": 42000.0, "timestamp": None}
        exchange = await _connected(toy_config, mock_client)

        _toy_logger.addHandler(caplog.handler)
        _toy_logger.setLevel(logging.WARNING)
        try:
            ticker = await exchange.get_ticker("BTC/USDT")
        finally:
            _toy_logger.removeHandler(caplog.handler)

        assert ticker.timestamp is None
        assert any("no ticker timestamp" in r.getMessage() for r in caplog.records)


class TestToyAdapterOrders:
    async def test_create_market_order(
        self, toy_config: _ToyConfig, mock_client: AsyncMock
    ) -> None:
        mock_client.create_market_order.return_value = {
            "id": "1",
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "market",
            "amount": 0.1,
            "status": "closed",
            "timestamp": 1704067200000,
        }
        exchange = await _connected(toy_config, mock_client)

        order = await exchange.create_order(
            OrderRequest(symbol="BTC/USDT", side="buy", type="market", quantity=Decimal("0.1"))
        )

        assert isinstance(order, Order)
        assert order.status == OrderStatus.FILLED

    async def test_map_order_none_timestamp_falls_back(
        self,
        toy_config: _ToyConfig,
        mock_client: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """CAH-01 order guard lives once in the base — None ts -> now_utc."""
        mock_client.fetch_order.return_value = {
            "id": "1",
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "market",
            "amount": 0.1,
            "status": "open",
            "timestamp": None,
        }
        exchange = await _connected(toy_config, mock_client)

        _toy_logger.addHandler(caplog.handler)
        _toy_logger.setLevel(logging.WARNING)
        try:
            order = await exchange.get_order("1", "BTC/USDT")
        finally:
            _toy_logger.removeHandler(caplog.handler)

        assert order.created_at is not None
        assert any("no timestamp for order" in r.getMessage() for r in caplog.records)

    async def test_cancel_order_not_found_returns_false(
        self, toy_config: _ToyConfig, mock_client: AsyncMock
    ) -> None:
        from ccxt.base.errors import OrderNotFound

        mock_client.cancel_order.side_effect = OrderNotFound("gone")
        exchange = await _connected(toy_config, mock_client)

        assert await exchange.cancel_order("1", "BTC/USDT") is False

    async def test_get_open_orders_maps_all(
        self, toy_config: _ToyConfig, mock_client: AsyncMock
    ) -> None:
        mock_client.fetch_open_orders.return_value = [
            {
                "id": "1",
                "symbol": "BTC/USDT",
                "side": "buy",
                "type": "limit",
                "price": 42000.0,
                "amount": 0.1,
                "status": "open",
                "timestamp": 1704067200000,
            }
        ]
        exchange = await _connected(toy_config, mock_client)

        orders = await exchange.get_open_orders()
        assert len(orders) == 1
        assert orders[0].status == OrderStatus.OPEN


class TestCcxtHelpersMoved:
    """EXCH-F5: the ccxt-mapping helpers live in ccxt_base now."""

    def test_decimal_or_none_zero_is_none(self) -> None:
        assert _decimal_or_none(0) is None
        assert _decimal_or_none(None) is None
        assert _decimal_or_none("1.5") == Decimal("1.5")

    def test_extract_ccxt_fee_sums_fees_list(self) -> None:
        amount, currency = _extract_ccxt_fee(
            {"fees": [{"cost": 0.5, "currency": "USDT"}, {"cost": 0.25}]}
        )
        assert amount == Decimal("0.75")
        assert currency == "USDT"

    def test_helpers_not_in_port_module(self) -> None:
        import src.exchange.base as port

        assert not hasattr(port, "_extract_ccxt_fee")
        assert not hasattr(port, "_decimal_or_none")

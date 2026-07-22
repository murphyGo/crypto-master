"""Tests for the Binance exchange implementation."""

import logging
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from ccxt.base.errors import (
    AuthenticationError,
    ExchangeNotAvailable,
    NetworkError,
    RateLimitExceeded,
)
from ccxt.base.errors import (
    ExchangeError as CCXTExchangeError,
)

from src.config import BinanceConfig
from src.exchange.base import ExchangeAPIError, ExchangeConnectionError, ExchangeError
from src.exchange.binance import BinanceExchange
from src.exchange.derivatives import (
    CurrentFundingRate,
    DerivativesDataContiguityError,
    DerivativesDataValidationError,
    OpenInterestHistory,
    OpenInterestPoint,
    UnsupportedFundingIntervalError,
)
from src.models import OHLCV, Order, OrderRequest, OrderStatus, Ticker


def _capture_adapter_log(caplog: pytest.LogCaptureFixture) -> None:
    """Route the binance adapter logger into ``caplog``.

    ``src.logger.get_logger`` sets ``propagate = False`` (so adapter
    warnings don't bubble to the root logger / duplicate handlers).
    pytest's ``caplog`` attaches only to the root logger, so a
    non-propagating module logger is invisible to it. Attaching
    ``caplog.handler`` directly to the named logger makes the
    CAH-01 fallback warnings assertable. The autouse logger-reset
    fixture in ``conftest.py`` tears the handler down per test.
    """
    logger = logging.getLogger("crypto_master.exchange.binance")
    logger.addHandler(caplog.handler)
    logger.setLevel(logging.WARNING)


@pytest.fixture
def binance_config() -> BinanceConfig:
    """Create a test Binance configuration."""
    return BinanceConfig(
        api_key="test_api_key",
        api_secret="test_api_secret",
        market_type="futures",
        testnet=True,
    )


@pytest.fixture
def spot_config() -> BinanceConfig:
    """Create a test Binance spot configuration."""
    return BinanceConfig(
        api_key="test_api_key",
        api_secret="test_api_secret",
        market_type="spot",
        testnet=True,
    )


@pytest.fixture
def mock_ccxt_client() -> AsyncMock:
    """Create a mock ccxt client."""
    client = AsyncMock()
    client.load_markets = AsyncMock()
    client.close = AsyncMock()
    return client


DERIVATIVES_START_MS = 1751328000000  # 2025-07-01 00:00:00 UTC
HOUR_MS = 60 * 60 * 1000


def _funding_raw(
    hours: int,
    *,
    rate: str = "0.0001",
    symbol: str = "BTC/USDT:USDT",
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "timestamp": DERIVATIVES_START_MS + hours * HOUR_MS,
        "fundingRate": rate,
        "info": {"rawMustNotEscape": True},
    }


def _oi_raw(
    hours: int,
    *,
    amount: str = "100",
    symbol: str = "BTC/USDT:USDT",
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "timestamp": DERIVATIVES_START_MS + hours * HOUR_MS,
        "openInterestAmount": amount,
        "openInterestValue": "5000000",
        "info": {"rawMustNotEscape": True},
    }


def _connected_derivatives_exchange(
    config: BinanceConfig, client: AsyncMock
) -> BinanceExchange:
    exchange = BinanceExchange(config=config, testnet=False)
    exchange._client = client
    return exchange


class TestBinanceExchangeInit:
    """Tests for BinanceExchange initialization."""

    def test_initialization_stores_config(self, binance_config: BinanceConfig) -> None:
        """Test config is stored correctly."""
        exchange = BinanceExchange(config=binance_config, testnet=True)
        assert exchange.config is binance_config
        assert exchange.testnet is True
        assert exchange.name == "binance"

    def test_client_is_none_before_connect(self, binance_config: BinanceConfig) -> None:
        """Test client is None before connect() is called."""
        exchange = BinanceExchange(config=binance_config, testnet=True)
        assert exchange._client is None

    def test_testnet_defaults_to_false(self, binance_config: BinanceConfig) -> None:
        """Test testnet defaults to False if not specified."""
        exchange = BinanceExchange(config=binance_config)
        assert exchange.testnet is False

    def test_timeframe_map_contains_all_timeframes(self) -> None:
        """Test TIMEFRAME_MAP contains all supported timeframes."""
        expected = {"1m", "5m", "15m", "1h", "4h", "1d", "1w"}
        assert set(BinanceExchange.TIMEFRAME_MAP.keys()) == expected

    def test_url_constants_exist(self) -> None:
        """Test URL constants are defined for reference."""
        assert BinanceExchange.MAINNET_URL == "https://api.binance.com"
        assert BinanceExchange.TESTNET_SPOT_URL == "https://testnet.binance.vision"
        assert (
            BinanceExchange.TESTNET_FUTURES_URL == "https://testnet.binancefutures.com"
        )

    def test_derivatives_capability_is_enabled(
        self, binance_config: BinanceConfig
    ) -> None:
        assert BinanceExchange(config=binance_config).supports_derivatives_data is True


class TestBinanceExchangeConnect:
    """Tests for connect/disconnect methods."""

    @pytest.mark.asyncio
    async def test_connect_creates_futures_client(
        self, binance_config: BinanceConfig
    ) -> None:
        """Test connect creates binanceusdm client for futures."""
        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_client = AsyncMock()
            mock_class.return_value = mock_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            mock_class.assert_called_once()
            assert exchange._client is mock_client

    @pytest.mark.asyncio
    async def test_connect_creates_spot_client(
        self, spot_config: BinanceConfig
    ) -> None:
        """Test connect creates binance client for spot."""
        with patch("src.exchange.binance.ccxt.binance") as mock_class:
            mock_client = AsyncMock()
            mock_class.return_value = mock_client

            exchange = BinanceExchange(config=spot_config, testnet=True)
            await exchange.connect()

            mock_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_loads_markets(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test connect calls load_markets to validate connection."""
        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            mock_ccxt_client.load_markets.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_sets_sandbox_mode(
        self, binance_config: BinanceConfig
    ) -> None:
        """Test connect sets sandbox=True when testnet is enabled."""
        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_client = AsyncMock()
            mock_class.return_value = mock_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            # Check the config passed to ccxt
            call_args = mock_class.call_args[0][0]
            assert call_args["sandbox"] is True
            assert call_args["enableRateLimit"] is True

    @pytest.mark.asyncio
    async def test_connect_uses_testnet_credentials(self) -> None:
        """Test connect uses testnet credentials when testnet=True."""
        config = BinanceConfig(
            api_key="live_key",
            api_secret="live_secret",
            testnet_api_key="testnet_key",
            testnet_api_secret="testnet_secret",
            testnet=True,
        )

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_client = AsyncMock()
            mock_class.return_value = mock_client

            exchange = BinanceExchange(config=config, testnet=True)
            await exchange.connect()

            # Check the credentials passed to ccxt
            call_args = mock_class.call_args[0][0]
            assert call_args["apiKey"] == "testnet_key"
            assert call_args["secret"] == "testnet_secret"

    @pytest.mark.asyncio
    async def test_connect_uses_live_credentials_when_testnet_false(self) -> None:
        """Test connect uses live credentials when testnet=False."""
        config = BinanceConfig(
            api_key="live_key",
            api_secret="live_secret",
            testnet_api_key="testnet_key",
            testnet_api_secret="testnet_secret",
            testnet=False,
        )

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_client = AsyncMock()
            mock_class.return_value = mock_client

            exchange = BinanceExchange(config=config, testnet=False)
            await exchange.connect()

            # Check the credentials passed to ccxt
            call_args = mock_class.call_args[0][0]
            assert call_args["apiKey"] == "live_key"
            assert call_args["secret"] == "live_secret"
            assert call_args["sandbox"] is False

    @pytest.mark.asyncio
    async def test_connect_omits_empty_public_credentials(self) -> None:
        config = BinanceConfig(
            api_key="",
            api_secret="",
            testnet_api_key="",
            testnet_api_secret="",
            market_type="futures",
            testnet=False,
        )

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = AsyncMock()
            exchange = BinanceExchange(config=config, testnet=False)
            await exchange.connect()

            call_config = mock_class.call_args.args[0]
            assert "apiKey" not in call_config
            assert "secret" not in call_config
            assert call_config["enableRateLimit"] is True

    @pytest.mark.asyncio
    async def test_connect_aligns_credentials_with_runtime_testnet(self) -> None:
        """Runtime testnet flag drives credential selection (consistency-hardening).

        ``BinanceConfig.testnet`` reflects the legacy ``BINANCE_TESTNET`` env
        default. ``BinanceExchange(..., testnet=...)`` may override that —
        for example paper-mode dispatch forces ``testnet=True`` even when
        env says live. The runtime flag must drive credential selection so
        the ccxt sandbox URL and the keys stay consistent.
        """
        config = BinanceConfig(
            api_key="live_key",
            api_secret="live_secret",
            testnet_api_key="testnet_key",
            testnet_api_secret="testnet_secret",
            testnet=False,
        )

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_client = AsyncMock()
            mock_class.return_value = mock_client

            exchange = BinanceExchange(config=config, testnet=True)
            await exchange.connect()

            call_args = mock_class.call_args[0][0]
            assert call_args["apiKey"] == "testnet_key"
            assert call_args["secret"] == "testnet_secret"
            assert call_args["sandbox"] is True

    @pytest.mark.asyncio
    async def test_connect_authentication_error(
        self, binance_config: BinanceConfig
    ) -> None:
        """Test connect raises ExchangeConnectionError on auth failure."""
        from ccxt.base.errors import AuthenticationError

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_client = AsyncMock()
            mock_client.load_markets.side_effect = AuthenticationError("Invalid key")
            mock_class.return_value = mock_client

            exchange = BinanceExchange(config=binance_config, testnet=True)

            with pytest.raises(ExchangeConnectionError) as exc_info:
                await exchange.connect()
            assert "Authentication failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_network_error(self, binance_config: BinanceConfig) -> None:
        """Test connect raises ExchangeConnectionError on network failure."""
        from ccxt.base.errors import NetworkError

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_client = AsyncMock()
            mock_client.load_markets.side_effect = NetworkError("Connection timeout")
            mock_class.return_value = mock_client

            exchange = BinanceExchange(config=binance_config, testnet=True)

            with pytest.raises(ExchangeConnectionError) as exc_info:
                await exchange.connect()
            assert "Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect_closes_client(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test disconnect closes the ccxt client."""
        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()
            await exchange.disconnect()

            mock_ccxt_client.close.assert_called_once()
            assert exchange._client is None

    @pytest.mark.asyncio
    async def test_disconnect_handles_none_client(
        self, binance_config: BinanceConfig
    ) -> None:
        """Test disconnect handles case when client is None."""
        exchange = BinanceExchange(config=binance_config, testnet=True)
        # Should not raise
        await exchange.disconnect()
        assert exchange._client is None


class TestBinanceExchangeOHLCV:
    """Tests for get_ohlcv method."""

    @pytest.mark.asyncio
    async def test_get_ohlcv_returns_list(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_ohlcv returns list of OHLCV."""
        mock_ccxt_client.fetch_ohlcv.return_value = [
            [1704067200000, 42000.0, 42500.0, 41800.0, 42300.0, 1000.0],
            [1704070800000, 42300.0, 42600.0, 42100.0, 42400.0, 1200.0],
        ]

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
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
    async def test_get_ohlcv_limits_to_1500(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_ohlcv limits to max 1500 candles."""
        mock_ccxt_client.fetch_ohlcv.return_value = []

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            await exchange.get_ohlcv("BTC/USDT", "1h", limit=2000)

            # Verify limit was capped at 1500
            call_kwargs = mock_ccxt_client.fetch_ohlcv.call_args[1]
            assert call_kwargs["limit"] == 1500

    @pytest.mark.asyncio
    async def test_get_ohlcv_converts_timestamp(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_ohlcv converts millisecond timestamp to datetime."""
        # Jan 1, 2024 00:00:00 UTC
        mock_ccxt_client.fetch_ohlcv.return_value = [
            [1704067200000, 42000.0, 42500.0, 41800.0, 42300.0, 1000.0],
        ]

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_ohlcv("BTC/USDT", "1h")

            assert isinstance(result[0].timestamp, datetime)

    @pytest.mark.asyncio
    async def test_get_ohlcv_raises_on_not_connected(
        self, binance_config: BinanceConfig
    ) -> None:
        """Test get_ohlcv raises error if not connected."""
        exchange = BinanceExchange(config=binance_config, testnet=True)

        with pytest.raises(ExchangeError) as exc_info:
            await exchange.get_ohlcv("BTC/USDT", "1h")
        assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_ohlcv_rate_limit_error(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_ohlcv handles rate limit error."""
        from ccxt.base.errors import RateLimitExceeded

        mock_ccxt_client.fetch_ohlcv.side_effect = RateLimitExceeded(
            "Too many requests"
        )

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            with pytest.raises(ExchangeAPIError) as exc_info:
                await exchange.get_ohlcv("BTC/USDT", "1h")
            assert exc_info.value.code == "RATE_LIMIT"

    @pytest.mark.asyncio
    async def test_get_ohlcv_forwards_since_to_ccxt(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_ohlcv forwards ``since`` to ccxt.fetch_ohlcv (DEBT-004)."""
        mock_ccxt_client.fetch_ohlcv.return_value = []

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            await exchange.get_ohlcv("BTC/USDT", "1h", limit=500, since=12345)

            call_kwargs = mock_ccxt_client.fetch_ohlcv.call_args[1]
            assert call_kwargs["since"] == 12345
            assert call_kwargs["limit"] == 500

    @pytest.mark.asyncio
    async def test_get_ohlcv_defaults_since_to_none(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """When ``since`` is omitted the ccxt call gets ``since=None``."""
        mock_ccxt_client.fetch_ohlcv.return_value = []

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            await exchange.get_ohlcv("BTC/USDT", "1h", limit=100)

            call_kwargs = mock_ccxt_client.fetch_ohlcv.call_args[1]
            assert call_kwargs["since"] is None


class TestBinanceExchangeTicker:
    """Tests for get_ticker method."""

    @pytest.mark.asyncio
    async def test_get_ticker_returns_ticker(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_ticker returns Ticker."""
        mock_ccxt_client.fetch_ticker.return_value = {
            "symbol": "BTC/USDT",
            "last": 42500.0,
            "timestamp": 1704067200000,
        }

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_ticker("BTC/USDT")

            assert isinstance(result, Ticker)
            assert result.symbol == "BTC/USDT"
            assert result.price == Decimal("42500.0")

    @pytest.mark.asyncio
    async def test_get_ticker_converts_timestamp(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_ticker converts timestamp correctly."""
        mock_ccxt_client.fetch_ticker.return_value = {
            "symbol": "BTC/USDT",
            "last": 42500.0,
            "timestamp": 1704067200000,
        }

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_ticker("BTC/USDT")

            assert isinstance(result.timestamp, datetime)


class TestBinanceNoneTimestampGuard:
    """CAH-01 [BUGFIX]: ccxt returns None timestamps on some venues.

    from_unix_ms(None) raises TypeError, which would escape the
    adapter's documented ExchangeAPIError-only contract. For the
    *ticker* the guard passes ``timestamp=None`` through (a missing
    timestamp is unverifiable freshness, not maximally fresh, so the
    stale-quote gate can fail-closed) and logs a warning. For the
    *order* ``created_at`` is non-nullable, so it falls back to
    now_utc() and logs a warning instead of raising.
    """

    @pytest.mark.asyncio
    async def test_get_ticker_none_timestamp_is_none(
        self,
        binance_config: BinanceConfig,
        mock_ccxt_client: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """None ticker timestamp -> no TypeError, timestamp is None, warning."""
        mock_ccxt_client.fetch_ticker.return_value = {
            "symbol": "BTC/USDT",
            "last": 42500.0,
            "timestamp": None,
        }

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            _capture_adapter_log(caplog)
            result = await exchange.get_ticker("BTC/USDT")

        assert isinstance(result, Ticker)
        # CAH-01: a missing timestamp is passed through as None, never
        # fabricated as now_utc() — otherwise the stale-quote gate would
        # treat a stale tape as "0 seconds old".
        assert result.timestamp is None
        assert any("no ticker timestamp" in r.getMessage() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_get_ticker_numeric_timestamp_unchanged(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Regression: a normal numeric timestamp still maps exactly as before."""
        mock_ccxt_client.fetch_ticker.return_value = {
            "symbol": "BTC/USDT",
            "last": 42500.0,
            "timestamp": 1704067200000,
        }

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_ticker("BTC/USDT")

        assert result.timestamp == datetime(2024, 1, 1, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_get_order_none_timestamp_falls_back_to_now(
        self,
        binance_config: BinanceConfig,
        mock_ccxt_client: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """None order timestamp -> no TypeError, order returned, now_utc() created_at."""
        mock_ccxt_client.fetch_order.return_value = {
            "id": "12345",
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "limit",
            "price": 42000.0,
            "amount": 0.1,
            "filled": 0.1,
            "status": "closed",
            "timestamp": None,
            "lastTradeTimestamp": None,
        }
        before = datetime.now(tz=timezone.utc)

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            _capture_adapter_log(caplog)
            result = await exchange.get_order("12345", "BTC/USDT")

        after = datetime.now(tz=timezone.utc)
        assert isinstance(result, Order)
        assert result.id == "12345"
        # created_at is a required non-nullable datetime -> now_utc() fallback.
        assert result.created_at.tzinfo == timezone.utc
        assert before <= result.created_at <= after
        # updated_at mirrors the pre-existing guard (None on missing).
        assert result.updated_at is None
        assert any("no timestamp for order" in r.getMessage() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_get_order_numeric_timestamp_unchanged(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Regression: a normal numeric order timestamp still maps exactly as before."""
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

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_order("12345", "BTC/USDT")

        assert result.created_at == datetime(2024, 1, 1, tzinfo=timezone.utc)


class TestBinanceExchangeBalance:
    """Tests for get_balance method."""

    @pytest.mark.asyncio
    async def test_get_balance_returns_balances(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
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

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_balance()

            assert len(result) == 2
            usdt = next(b for b in result if b.currency == "USDT")
            assert usdt.free == Decimal("1000.0")
            assert usdt.locked == Decimal("200.0")
            assert usdt.total == Decimal("1200.0")

    @pytest.mark.asyncio
    async def test_get_balance_with_currency_filter(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_balance filters by currency."""
        mock_ccxt_client.fetch_balance.return_value = {
            "USDT": {"free": 1000.0, "used": 0.0, "total": 1000.0},
            "BTC": {"free": 0.5, "used": 0.0, "total": 0.5},
        }

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_balance("USDT")

            assert len(result) == 1
            assert result[0].currency == "USDT"

    @pytest.mark.asyncio
    async def test_get_balance_skips_zero_balances(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_balance skips currencies with zero balance."""
        mock_ccxt_client.fetch_balance.return_value = {
            "USDT": {"free": 1000.0, "used": 0.0, "total": 1000.0},
            "ETH": {"free": 0.0, "used": 0.0, "total": 0.0},
        }

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_balance()

            assert len(result) == 1
            assert result[0].currency == "USDT"


class TestBinanceExchangeOrders:
    """Tests for order methods."""

    @pytest.mark.asyncio
    async def test_create_market_order(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
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

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
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
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
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

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
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
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test create_order handles invalid order error."""
        from ccxt.base.errors import InvalidOrder

        mock_ccxt_client.create_market_order.side_effect = InvalidOrder("Invalid qty")

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
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
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test create_order handles insufficient funds error."""
        from ccxt.base.errors import InsufficientFunds

        mock_ccxt_client.create_market_order.side_effect = InsufficientFunds(
            "Insufficient balance"
        )

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
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
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test cancel_order returns True on success."""
        mock_ccxt_client.cancel_order.return_value = {}

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            result = await exchange.cancel_order("12345", "BTC/USDT")

            assert result is True

    @pytest.mark.asyncio
    async def test_cancel_order_not_found(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test cancel_order returns False when order not found."""
        from ccxt.base.errors import OrderNotFound

        mock_ccxt_client.cancel_order.side_effect = OrderNotFound("Order not found")

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            result = await exchange.cancel_order("99999", "BTC/USDT")

            assert result is False

    @pytest.mark.asyncio
    async def test_get_order_returns_order(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
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

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_order("12345", "BTC/USDT")

            assert isinstance(result, Order)
            assert result.id == "12345"
            assert result.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_get_order_not_found(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test get_order raises error when order not found."""
        from ccxt.base.errors import OrderNotFound

        mock_ccxt_client.fetch_order.side_effect = OrderNotFound("Order not found")

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            with pytest.raises(ExchangeAPIError) as exc_info:
                await exchange.get_order("99999", "BTC/USDT")
            assert exc_info.value.code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_open_orders_returns_list(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
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

        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_open_orders("BTC/USDT")

            assert len(result) == 2
            assert all(isinstance(o, Order) for o in result)
            assert all(o.status == OrderStatus.OPEN for o in result)


class TestBinanceExchangeOrderStatusMapping:
    """Tests for order status mapping."""

    def test_map_order_status_open(self, binance_config: BinanceConfig) -> None:
        """Test mapping 'open' status."""
        exchange = BinanceExchange(config=binance_config, testnet=True)
        assert exchange._map_order_status("open") == OrderStatus.OPEN

    def test_map_order_status_closed(self, binance_config: BinanceConfig) -> None:
        """Test mapping 'closed' status to FILLED."""
        exchange = BinanceExchange(config=binance_config, testnet=True)
        assert exchange._map_order_status("closed") == OrderStatus.FILLED

    def test_map_order_status_canceled(self, binance_config: BinanceConfig) -> None:
        """Test mapping 'canceled' status."""
        exchange = BinanceExchange(config=binance_config, testnet=True)
        assert exchange._map_order_status("canceled") == OrderStatus.CANCELLED

    def test_map_order_status_expired(self, binance_config: BinanceConfig) -> None:
        """Test mapping 'expired' status to CANCELLED."""
        exchange = BinanceExchange(config=binance_config, testnet=True)
        assert exchange._map_order_status("expired") == OrderStatus.CANCELLED

    def test_map_order_status_rejected(self, binance_config: BinanceConfig) -> None:
        """Test mapping 'rejected' status."""
        exchange = BinanceExchange(config=binance_config, testnet=True)
        assert exchange._map_order_status("rejected") == OrderStatus.REJECTED

    def test_map_order_status_unknown(self, binance_config: BinanceConfig) -> None:
        """Test mapping unknown status defaults to PENDING."""
        exchange = BinanceExchange(config=binance_config, testnet=True)
        assert exchange._map_order_status("unknown") == OrderStatus.PENDING


class TestBinanceMapOrderFillAttribution:
    """ccxt fill economics flow into the Order model (CH-06)."""

    def _raw(self, **overrides: object) -> dict[str, object]:
        base = {
            "id": "abc",
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "market",
            "price": None,
            "amount": "0.1",
            "filled": "0.1",
            "status": "closed",
            "timestamp": 1_700_000_000_000,
            "lastTradeTimestamp": 1_700_000_000_000,
        }
        base.update(overrides)
        return base

    def test_map_order_extracts_average_and_fee(
        self, binance_config: BinanceConfig
    ) -> None:
        exchange = BinanceExchange(config=binance_config, testnet=True)
        raw = self._raw(
            average="50050.5",
            fee={"cost": "2.5", "currency": "USDT"},
        )
        order = exchange._map_order(raw)
        assert order.average_price == Decimal("50050.5")
        assert order.fee == Decimal("2.5")
        assert order.fee_currency == "USDT"

    def test_map_order_sums_per_fill_fees_list(
        self, binance_config: BinanceConfig
    ) -> None:
        exchange = BinanceExchange(config=binance_config, testnet=True)
        raw = self._raw(
            average="50050.5",
            fees=[
                {"cost": "1.0", "currency": "USDT"},
                {"cost": "1.5", "currency": "USDT"},
            ],
        )
        order = exchange._map_order(raw)
        assert order.fee == Decimal("2.5")
        assert order.fee_currency == "USDT"

    def test_map_order_returns_none_when_average_and_fee_missing(
        self, binance_config: BinanceConfig
    ) -> None:
        """Adapters that don't surface fills downgrade gracefully."""
        exchange = BinanceExchange(config=binance_config, testnet=True)
        raw = self._raw()
        order = exchange._map_order(raw)
        assert order.average_price is None
        assert order.fee is None
        assert order.fee_currency is None


class TestBinanceExchangeContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_connects_and_disconnects(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test async context manager protocol."""
        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)
            assert exchange._client is None

            async with exchange as ex:
                assert ex is exchange
                assert exchange._client is not None

            assert exchange._client is None

    @pytest.mark.asyncio
    async def test_context_manager_disconnects_on_exception(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Test context manager disconnects even on exception."""
        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client

            exchange = BinanceExchange(config=binance_config, testnet=True)

            with pytest.raises(ValueError):
                async with exchange:
                    assert exchange._client is not None
                    raise ValueError("Test exception")

            assert exchange._client is None


class TestBinanceExchangeRegistration:
    """Tests for exchange registration."""

    def test_binance_is_registered(self) -> None:
        """Test BinanceExchange is registered with factory."""
        from src.exchange.factory import _exchange_registry

        assert "binance" in _exchange_registry
        assert _exchange_registry["binance"] is BinanceExchange


# =============================================================================
# Phase 21.1 / DEBT-025: UTC-aware adapter timestamps
# =============================================================================


_HAS_TZSET = hasattr(time, "tzset") and sys.platform != "win32"


@pytest.fixture
def kst_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a non-UTC host (Asia/Seoul, UTC+9).

    Without ``tz=`` argument, ``datetime.fromtimestamp(ms / 1000)``
    interprets the input in *host-local* time, so the same Unix ms
    decodes to different wall-clock values depending on host TZ.
    Phase 21.1 closes that surface; this fixture is the regression
    harness.
    """
    if not _HAS_TZSET:
        pytest.skip("time.tzset() not available on this platform")
    original_tz = os.environ.get("TZ")
    monkeypatch.setenv("TZ", "Asia/Seoul")
    time.tzset()
    yield
    if original_tz is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original_tz
    time.tzset()


class TestBinanceTimestampUTCAware:
    """Adapter must return UTC-aware timestamps regardless of host TZ."""

    @pytest.mark.asyncio
    async def test_get_ohlcv_returns_utc_aware_timestamp_on_kst_host(
        self,
        binance_config: BinanceConfig,
        mock_ccxt_client: AsyncMock,
        kst_host: None,
    ) -> None:
        """OHLCV bar timestamp carries tzinfo=UTC even on a UTC+9 host,
        and the wall-clock UTC value matches the input ms exactly."""
        # 1704067200000 ms == 2024-01-01 00:00:00 UTC
        mock_ccxt_client.fetch_ohlcv.return_value = [
            [1704067200000, 42000.0, 42500.0, 41800.0, 42300.0, 1000.0],
        ]
        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client
            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_ohlcv("BTC/USDT", "1h")

        assert result[0].timestamp.tzinfo is timezone.utc
        assert result[0].timestamp == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_get_ticker_returns_utc_aware_timestamp(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        """Ticker timestamp is UTC-aware (assertion holds on any host)."""
        mock_ccxt_client.fetch_ticker.return_value = {
            "symbol": "BTC/USDT",
            "last": 42500.0,
            "timestamp": 1704067200000,
        }
        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client
            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            result = await exchange.get_ticker("BTC/USDT")

        assert result.timestamp.tzinfo is timezone.utc
        assert result.timestamp == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_map_order_returns_utc_aware_timestamps_on_kst_host(
        self,
        binance_config: BinanceConfig,
        mock_ccxt_client: AsyncMock,
        kst_host: None,
    ) -> None:
        """Order created_at / updated_at are UTC-aware on a non-UTC host."""
        mock_ccxt_client.fetch_order.return_value = {
            "id": "order-1",
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "limit",
            "price": 42000.0,
            "amount": 0.1,
            "filled": 0.1,
            "status": "closed",
            "timestamp": 1704067200000,
            "lastTradeTimestamp": 1704067260000,
        }
        with patch("src.exchange.binance.ccxt.binanceusdm") as mock_class:
            mock_class.return_value = mock_ccxt_client
            exchange = BinanceExchange(config=binance_config, testnet=True)
            await exchange.connect()

            order = await exchange.get_order("order-1", "BTC/USDT")

        assert order.created_at.tzinfo is timezone.utc
        assert order.created_at == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert order.updated_at is not None
        assert order.updated_at.tzinfo is timezone.utc
        assert order.updated_at == datetime(2024, 1, 1, 0, 1, 0, tzinfo=timezone.utc)


class TestBinanceDerivativesCurrent:
    """Current Funding/OI mappings stay normalized and payload-safe."""

    @pytest.mark.asyncio
    async def test_get_funding_rate_maps_current_and_predicted_values(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        mock_ccxt_client.fetch_funding_rate.return_value = {
            **_funding_raw(0),
            "nextFundingRate": "-0.0002",
            "nextFundingTimestamp": DERIVATIVES_START_MS + 8 * HOUR_MS,
            "interval": "8h",
        }
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        result = await exchange.get_funding_rate("BTC/USDT")

        assert isinstance(result, CurrentFundingRate)
        assert result.symbol == "BTC/USDT"
        assert result.rate == Decimal("0.0001")
        assert result.predicted_rate == Decimal("-0.0002")
        assert result.observed_at.tzinfo is timezone.utc
        assert result.interval_hours == 8
        assert "info" not in result.model_dump()

    @pytest.mark.asyncio
    async def test_get_open_interest_maps_current_point(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        mock_ccxt_client.fetch_open_interest.return_value = _oi_raw(0)
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        result = await exchange.get_open_interest("BTC/USDT")

        assert isinstance(result, OpenInterestPoint)
        assert result.open_interest == Decimal("100")
        assert result.open_interest_value == Decimal("5000000")
        assert result.timestamp.tzinfo is timezone.utc
        assert "info" not in result.model_dump()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "payload",
        [
            {"symbol": "BTC/USDT", "timestamp": DERIVATIVES_START_MS},
            {
                "symbol": "ETH/USDT:USDT",
                "timestamp": DERIVATIVES_START_MS,
                "fundingRate": "0.0001",
            },
            {
                "symbol": "BTC/USDT:USDT",
                "timestamp": "not-a-timestamp",
                "fundingRate": "0.0001",
            },
            {
                "symbol": "BTC/USDT:USDT",
                "timestamp": float("nan"),
                "fundingRate": "0.0001",
            },
        ],
    )
    async def test_get_funding_rate_rejects_malformed_payload(
        self,
        payload: dict[str, object],
        binance_config: BinanceConfig,
        mock_ccxt_client: AsyncMock,
    ) -> None:
        mock_ccxt_client.fetch_funding_rate.return_value = payload
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        with pytest.raises(DerivativesDataValidationError) as exc_info:
            await exchange.get_funding_rate("BTC/USDT")

        assert exc_info.value.code == "invalid_payload"

    @pytest.mark.asyncio
    async def test_current_funding_rejects_non_8h_interval(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        mock_ccxt_client.fetch_funding_rate.return_value = {
            **_funding_raw(0),
            "interval": "4h",
        }
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        with pytest.raises(UnsupportedFundingIntervalError) as exc_info:
            await exchange.get_funding_rate("BTC/USDT")

        assert exc_info.value.code == "unsupported_interval"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("error", "expected_code"),
        [
            (RateLimitExceeded("secret-bearing-url"), "rate_limited"),
            (ExchangeNotAvailable("secret-bearing-url"), "venue_unavailable"),
            (NetworkError("secret-bearing-url"), "network_transient"),
            (
                AuthenticationError("secret-bearing-url"),
                "authentication_unexpected",
            ),
            (CCXTExchangeError("secret-bearing-url"), "remote_5xx"),
        ],
    )
    async def test_derivatives_error_ladder_is_typed_and_sanitized(
        self,
        error: CCXTExchangeError,
        expected_code: str,
        binance_config: BinanceConfig,
        mock_ccxt_client: AsyncMock,
    ) -> None:
        mock_ccxt_client.fetch_funding_rate.side_effect = error
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        with pytest.raises(ExchangeAPIError) as exc_info:
            await exchange.get_funding_rate("BTC/USDT")

        assert exc_info.value.code == expected_code
        assert "secret-bearing-url" not in str(exc_info.value)
        assert exc_info.value.__cause__ is error


class TestBinanceFundingHistory:
    """Funding history uses actual received records and validates the 8h grid."""

    @pytest.mark.asyncio
    async def test_short_pages_use_last_actual_record_for_next_cursor(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        mock_ccxt_client.fetch_funding_rate_history.side_effect = [
            [_funding_raw(0), _funding_raw(8)],
            [_funding_raw(16)],
            [],
        ]
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        result = await exchange.get_funding_rate_history(
            "BTC/USDT", DERIVATIVES_START_MS, limit=1500
        )

        assert [point.timestamp.hour for point in result] == [0, 8, 16]
        calls = mock_ccxt_client.fetch_funding_rate_history.call_args_list
        assert calls[0].kwargs["limit"] == 1000
        assert calls[1].kwargs["limit"] == 1000
        assert calls[1].kwargs["since"] == DERIVATIVES_START_MS + 16 * HOUR_MS

    @pytest.mark.asyncio
    async def test_multi_page_history_deduplicates_overlap(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        mock_ccxt_client.fetch_funding_rate_history.side_effect = [
            [_funding_raw(0), _funding_raw(8)],
            [_funding_raw(8), _funding_raw(16), _funding_raw(24)],
        ]
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        result = await exchange.get_funding_rate_history(
            "BTC/USDT", DERIVATIVES_START_MS, limit=4
        )

        assert len(result) == 4
        assert len({point.timestamp for point in result}) == 4
        assert result == sorted(result, key=lambda point: point.timestamp)

    @pytest.mark.asyncio
    async def test_funding_history_gap_fails_loudly(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        mock_ccxt_client.fetch_funding_rate_history.return_value = [
            _funding_raw(0),
            _funding_raw(16),
        ]
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        with pytest.raises(DerivativesDataContiguityError) as exc_info:
            await exchange.get_funding_rate_history(
                "BTC/USDT", DERIVATIVES_START_MS, limit=2
            )

        assert exc_info.value.code == "timestamp_gap"

    @pytest.mark.asyncio
    async def test_funding_history_non_8h_spacing_is_unsupported(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        mock_ccxt_client.fetch_funding_rate_history.return_value = [
            _funding_raw(0),
            _funding_raw(4),
        ]
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        with pytest.raises(UnsupportedFundingIntervalError) as exc_info:
            await exchange.get_funding_rate_history(
                "BTC/USDT", DERIVATIVES_START_MS, limit=2
            )

        assert exc_info.value.code == "unsupported_interval"

    @pytest.mark.asyncio
    async def test_funding_history_empty_response_returns_empty(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        mock_ccxt_client.fetch_funding_rate_history.return_value = []
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        result = await exchange.get_funding_rate_history(
            "BTC/USDT", DERIVATIVES_START_MS
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_funding_history_until_is_inclusive(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        until = DERIVATIVES_START_MS + 8 * HOUR_MS
        mock_ccxt_client.fetch_funding_rate_history.return_value = [
            _funding_raw(0),
            _funding_raw(8),
            _funding_raw(16),
        ]
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        result = await exchange.get_funding_rate_history(
            "BTC/USDT", DERIVATIVES_START_MS, until=until
        )

        assert [int(point.timestamp.timestamp() * 1000) for point in result] == [
            DERIVATIVES_START_MS,
            until,
        ]
        assert mock_ccxt_client.fetch_funding_rate_history.call_args.kwargs[
            "params"
        ] == {"endTime": until}


class TestBinanceOpenInterestHistory:
    """OI history validates 1h suffixes and reports retention loss explicitly."""

    @pytest.mark.asyncio
    async def test_short_pages_respect_500_cap_and_actual_cursor(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        mock_ccxt_client.fetch_open_interest_history.side_effect = [
            [_oi_raw(0), _oi_raw(1)],
            [_oi_raw(2)],
            [],
        ]
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        result = await exchange.get_open_interest_history(
            "BTC/USDT", since=DERIVATIVES_START_MS, limit=600
        )

        assert isinstance(result, OpenInterestHistory)
        assert len(result.points) == 3
        calls = mock_ccxt_client.fetch_open_interest_history.call_args_list
        assert calls[0].kwargs["limit"] == 500
        assert calls[1].kwargs["limit"] == 500
        assert calls[1].kwargs["since"] == DERIVATIVES_START_MS + 2 * HOUR_MS

    @pytest.mark.asyncio
    async def test_multi_page_oi_history_deduplicates_overlap(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        mock_ccxt_client.fetch_open_interest_history.side_effect = [
            [_oi_raw(0), _oi_raw(1)],
            [_oi_raw(1), _oi_raw(2), _oi_raw(3)],
        ]
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        result = await exchange.get_open_interest_history(
            "BTC/USDT", since=DERIVATIVES_START_MS, limit=4
        )

        assert len(result.points) == 4
        assert len({point.timestamp for point in result.points}) == 4

    @pytest.mark.asyncio
    async def test_oi_history_marks_retention_truncated_prefix(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        mock_ccxt_client.fetch_open_interest_history.return_value = [
            _oi_raw(24),
            _oi_raw(25),
        ]
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        result = await exchange.get_open_interest_history(
            "BTC/USDT", since=DERIVATIVES_START_MS, limit=2
        )

        assert result.truncated_at_venue_retention is True
        assert result.requested_since == datetime.fromtimestamp(
            DERIVATIVES_START_MS / 1000, tz=timezone.utc
        )
        assert result.actual_since == result.points[0].timestamp

    @pytest.mark.asyncio
    async def test_oi_history_exact_start_is_not_retention_truncated(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        mock_ccxt_client.fetch_open_interest_history.return_value = [
            _oi_raw(0),
            _oi_raw(1),
        ]
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        result = await exchange.get_open_interest_history(
            "BTC/USDT", since=DERIVATIVES_START_MS, limit=2
        )

        assert result.truncated_at_venue_retention is False
        assert result.actual_since == result.requested_since

    @pytest.mark.asyncio
    async def test_oi_history_gap_fails_loudly(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        mock_ccxt_client.fetch_open_interest_history.return_value = [
            _oi_raw(0),
            _oi_raw(2),
        ]
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        with pytest.raises(DerivativesDataContiguityError) as exc_info:
            await exchange.get_open_interest_history(
                "BTC/USDT", since=DERIVATIVES_START_MS, limit=2
            )

        assert exc_info.value.code == "timestamp_gap"

    @pytest.mark.asyncio
    async def test_oi_history_no_data_has_explicit_empty_coverage(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        mock_ccxt_client.fetch_open_interest_history.return_value = []
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        result = await exchange.get_open_interest_history(
            "BTC/USDT", since=DERIVATIVES_START_MS
        )

        assert result.points == ()
        assert result.actual_since is None
        assert result.actual_until is None
        assert result.truncated_at_venue_retention is False

    @pytest.mark.asyncio
    async def test_oi_history_until_is_inclusive(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        until = DERIVATIVES_START_MS + HOUR_MS
        mock_ccxt_client.fetch_open_interest_history.return_value = [
            _oi_raw(0),
            _oi_raw(1),
            _oi_raw(2),
        ]
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        result = await exchange.get_open_interest_history(
            "BTC/USDT", since=DERIVATIVES_START_MS, until=until
        )

        assert len(result.points) == 2
        assert result.actual_until == datetime.fromtimestamp(
            until / 1000, tz=timezone.utc
        )
        assert mock_ccxt_client.fetch_open_interest_history.call_args.kwargs[
            "params"
        ] == {"endTime": until}

    @pytest.mark.asyncio
    async def test_oi_history_rejects_non_1h_timeframe(
        self, binance_config: BinanceConfig, mock_ccxt_client: AsyncMock
    ) -> None:
        exchange = _connected_derivatives_exchange(binance_config, mock_ccxt_client)

        with pytest.raises(DerivativesDataValidationError) as exc_info:
            await exchange.get_open_interest_history("BTC/USDT", timeframe="5m")

        assert exc_info.value.code == "unsupported_interval"

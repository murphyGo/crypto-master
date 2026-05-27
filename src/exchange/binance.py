"""Binance exchange implementation for Crypto Master.

Related Requirements:
- FR-016: Binance Integration - Execute trades and query data through Binance API
- FR-019: Exchange Abstraction - Common interface for all exchanges
- FR-020: Historical Chart Data Query - OHLCV data collection
- CON-002: Rate Limit Compliance - Comply with exchange rate limits

CAH-11: the shared ccxt-adapter logic lives in ``src.exchange.ccxt_base``.
This adapter overrides only the genuinely-divergent surface: client
construction (spot/futures branch + ``adjustForTimeDifference`` option),
the OHLCV per-page cap, the exchange ``name``, and the config/logger wiring.
"""

from typing import cast

import ccxt.async_support as ccxt

from src.config import BinanceConfig
from src.exchange.ccxt_base import CCXTClient, CcxtExchange
from src.exchange.factory import register_exchange
from src.logger import get_logger

logger = get_logger("crypto_master.exchange.binance")


@register_exchange("binance")
class BinanceExchange(CcxtExchange):
    """Binance exchange implementation using ccxt.

    Supports both spot and futures markets based on config.market_type.
    Uses ccxt's built-in rate limiting for API compliance.

    Related Requirements:
    - FR-016: Binance Integration
    - FR-019: Exchange Abstraction
    - FR-010: Paper Trading Mode (via testnet)
    - CON-002: Rate Limit Compliance
    """

    name = "binance"
    logger = logger

    # Binance allows up to 1500 candles per OHLCV page.
    OHLCV_LIMIT = 1500

    # API URLs (for reference - ccxt handles routing via sandbox parameter)
    MAINNET_URL = "https://api.binance.com"
    TESTNET_SPOT_URL = "https://testnet.binance.vision"
    TESTNET_FUTURES_URL = "https://testnet.binancefutures.com"

    def __init__(self, config: BinanceConfig, testnet: bool = False) -> None:
        """Initialize BinanceExchange.

        Args:
            config: Binance configuration with API credentials and market type
            testnet: Whether to use testnet (sandbox) mode
        """
        super().__init__(config=config, testnet=testnet)
        self.config: BinanceConfig = config

    def _build_client(self, api_key: str, api_secret: str) -> CCXTClient:
        """Construct the configured ccxt client for Binance.

        Chooses ``binanceusdm`` (futures) or ``binance`` (spot) based on
        ``config.market_type`` and sets ``adjustForTimeDifference`` — the
        connect divergence vs the single-client venues (CAH-11).

        Args:
            api_key: Credential selected against the runtime sandbox flag.
            api_secret: Credential selected against the runtime sandbox flag.

        Returns:
            A configured (not yet validated) ccxt async client.
        """
        # Choose client class based on market type
        if self.config.market_type == "futures":
            exchange_class = ccxt.binanceusdm
        else:
            exchange_class = ccxt.binance

        # DEBT-005: ccxt is untyped, so the constructed client is Any; cast to
        # the CCXTClient Protocol the base operates against.
        return cast(
            CCXTClient,
            exchange_class(
                {
                    "apiKey": api_key,
                    "secret": api_secret,
                    "sandbox": self.testnet,
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": self.config.market_type,
                        "adjustForTimeDifference": True,
                    },
                }
            ),
        )

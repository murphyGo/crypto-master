"""Bybit exchange implementation for Crypto Master.

Related Requirements:
- FR-017: Bybit Integration - Execute trades and query data through Bybit API
- FR-019: Exchange Abstraction - Common interface for all exchanges
- FR-020: Historical Chart Data Query - OHLCV data collection
- CON-002: Rate Limit Compliance - Comply with exchange rate limits

CAH-11: the shared ccxt-adapter logic lives in ``src.exchange.ccxt_base``.
This adapter overrides only the genuinely-divergent surface: client
construction (a single ``ccxt.bybit``), the OHLCV per-page cap, the exchange
``name``, and the config/logger wiring.
"""

from typing import cast

import ccxt.async_support as ccxt

from src.config import BybitConfig
from src.exchange.ccxt_base import CCXTClient, CcxtExchange
from src.exchange.factory import register_exchange
from src.logger import get_logger

logger = get_logger("crypto_master.exchange.bybit")


@register_exchange("bybit")
class BybitExchange(CcxtExchange):
    """Bybit exchange implementation using ccxt.

    Uses Bybit's unified API for spot and derivatives trading.
    Uses ccxt's built-in rate limiting for API compliance.

    Related Requirements:
    - FR-017: Bybit Integration
    - FR-019: Exchange Abstraction
    - FR-010: Paper Trading Mode (via testnet)
    - CON-002: Rate Limit Compliance
    """

    name = "bybit"
    logger = logger

    # Bybit allows up to 200 candles per OHLCV page.
    OHLCV_LIMIT = 200

    # API URLs (for reference - ccxt handles routing via sandbox parameter)
    MAINNET_URL = "https://api.bybit.com"
    TESTNET_URL = "https://api-testnet.bybit.com"

    def __init__(self, config: BybitConfig, testnet: bool = False) -> None:
        """Initialize BybitExchange.

        Args:
            config: Bybit configuration with API credentials
            testnet: Whether to use testnet (sandbox) mode
        """
        super().__init__(config=config, testnet=testnet)
        self.config: BybitConfig = config

    def _build_client(self, api_key: str, api_secret: str) -> CCXTClient:
        """Construct the configured ccxt client for Bybit.

        A single ``ccxt.bybit`` (no spot/futures branch) — the connect
        divergence vs Binance (CAH-11).

        Args:
            api_key: Credential selected against the runtime sandbox flag.
            api_secret: Credential selected against the runtime sandbox flag.

        Returns:
            A configured (not yet validated) ccxt async client.
        """
        # DEBT-005: ccxt is untyped, so the constructed client is Any; cast to
        # the CCXTClient Protocol the base operates against.
        return cast(
            CCXTClient,
            ccxt.bybit(
                {
                    "apiKey": api_key,
                    "secret": api_secret,
                    "sandbox": self.testnet,
                    "enableRateLimit": True,
                    "options": {
                        "adjustForTimeDifference": True,
                    },
                }
            ),
        )

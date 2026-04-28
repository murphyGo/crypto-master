"""Configuration management module for Crypto Master.

This module provides centralized configuration management using Pydantic Settings.
All configuration is loaded from environment variables and .env file.

Related Requirements:
- NFR-004: Environment Variable Management
- NFR-011: API Key Protection
"""

from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class BinanceConfig(BaseSettings):
    """Binance exchange configuration.

    Environment variables:
    - BINANCE_API_KEY: API key for Binance (live/mainnet)
    - BINANCE_API_SECRET: API secret for Binance (live/mainnet)
    - BINANCE_TESTNET_API_KEY: API key for Binance testnet
    - BINANCE_TESTNET_API_SECRET: API secret for Binance testnet
    - BINANCE_MARKET_TYPE: Market type (spot/futures)
    - BINANCE_TESTNET: Whether to use testnet
    """

    api_key: str = ""
    api_secret: str = ""
    testnet_api_key: str = ""
    testnet_api_secret: str = ""
    market_type: Literal["spot", "futures"] = "futures"
    testnet: bool = True

    model_config = SettingsConfigDict(env_prefix="BINANCE_")

    def is_configured(self) -> bool:
        """Check if API credentials are configured.

        Returns True if either live or testnet credentials are set.
        """
        has_live = bool(self.api_key and self.api_secret)
        has_testnet = bool(self.testnet_api_key and self.testnet_api_secret)
        return has_live or has_testnet

    def get_credentials(self) -> tuple[str, str]:
        """Get appropriate API credentials based on testnet setting.

        Returns testnet credentials if testnet=True and testnet keys are set,
        otherwise returns live credentials.

        Returns:
            Tuple of (api_key, api_secret).
        """
        if self.testnet and self.testnet_api_key:
            return self.testnet_api_key, self.testnet_api_secret
        return self.api_key, self.api_secret


class BybitConfig(BaseSettings):
    """Bybit exchange configuration.

    Environment variables:
    - BYBIT_API_KEY: API key for Bybit (live/mainnet)
    - BYBIT_API_SECRET: API secret for Bybit (live/mainnet)
    - BYBIT_TESTNET_API_KEY: API key for Bybit testnet
    - BYBIT_TESTNET_API_SECRET: API secret for Bybit testnet
    - BYBIT_TESTNET: Whether to use testnet
    """

    api_key: str = ""
    api_secret: str = ""
    testnet_api_key: str = ""
    testnet_api_secret: str = ""
    testnet: bool = True

    model_config = SettingsConfigDict(env_prefix="BYBIT_")

    def is_configured(self) -> bool:
        """Check if API credentials are configured.

        Returns True if either live or testnet credentials are set.
        """
        has_live = bool(self.api_key and self.api_secret)
        has_testnet = bool(self.testnet_api_key and self.testnet_api_secret)
        return has_live or has_testnet

    def get_credentials(self) -> tuple[str, str]:
        """Get appropriate API credentials based on testnet setting.

        Returns testnet credentials if testnet=True and testnet keys are set,
        otherwise returns live credentials.

        Returns:
            Tuple of (api_key, api_secret).
        """
        if self.testnet and self.testnet_api_key:
            return self.testnet_api_key, self.testnet_api_secret
        return self.api_key, self.api_secret


class Settings(BaseSettings):
    """Main application settings.

    Loads configuration from environment variables and .env file.
    Nested exchange configurations are loaded with their respective prefixes.
    """

    # Trading Mode
    trading_mode: Literal["paper", "live"] = "paper"

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_file: Path = Path("data/logs/crypto-master.log")

    # Data Storage
    data_dir: Path = Path("data")

    # Paper Trading Configuration
    paper_initial_balance: float = Field(default=10000.0, gt=0)

    # Risk Management
    max_leverage: int = Field(default=10, ge=1, le=125)
    max_position_size_pct: float = Field(default=10.0, gt=0, le=100)
    default_stop_loss_pct: float = Field(default=2.0, gt=0, le=100)

    # Trading Engine Tunables (Phase 10.2)
    # Defaults match ``src.runtime.engine.EngineConfig`` so existing
    # deployments don't change behaviour without an explicit env setting.
    engine_cycle_interval: int = Field(default=300, ge=10)
    engine_auto_approve_threshold: float = Field(default=1.0, ge=0.0)
    # ``NoDecode`` prevents pydantic-settings from JSON-parsing the env
    # string before the validator runs; without it,
    # ``ENGINE_SYMBOLS=BTC/USDT,ETH/USDT`` raises a JSON decode error.
    engine_symbols: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "ETH/USDT",
            "SOL/USDT",
            "BNB/USDT",
            "ADA/USDT",
            "AVAX/USDT",
        ]
    )
    engine_balance: Decimal = Field(default=Decimal("10000"))

    # Log Retention (Phase 10.4)
    # ``JsonlRotator`` keeps the active month + this many archive
    # months merged into ``read_all``. Older rotated files stay on
    # disk untouched but are not surfaced to the application. The
    # same value also drives ``ProposalHistory.purge_old`` (one file
    # per proposal, age-based purge into ``proposals/archive/<YYYY-MM>/``).
    log_retention_months: int = Field(default=12, ge=1)

    # Notification Push Backend (Phase 11.3)
    # Slack incoming-webhook URL. When unset (default), no Slack
    # notifier is registered and the dispatcher falls back to the
    # Console + File backends only. The URL itself is a secret —
    # the application MUST NOT log it. Generate one at
    # https://api.slack.com/messaging/webhooks.
    slack_webhook_url: str | None = Field(default=None)

    # Exchange Configurations (nested)
    binance: BinanceConfig = Field(default_factory=BinanceConfig)
    bybit: BybitConfig = Field(default_factory=BybitConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("engine_symbols", mode="before")
    @classmethod
    def _parse_engine_symbols(cls, v: object) -> object:
        """Parse ``ENGINE_SYMBOLS`` from a comma-separated env string.

        Pydantic-settings hands env values in as strings; the engine
        wants a ``list[str]``. Empty / blank entries are stripped so
        ``"ETH/USDT, ,SOL/USDT"`` cleans up to two symbols.
        Non-string inputs (e.g. a ``list`` set programmatically in
        tests) pass through untouched.
        """
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    def validate_for_live_trading(self) -> None:
        """Validate that configuration is suitable for live trading.

        Raises:
            ValueError: If live trading is enabled but no exchange is configured.
        """
        if self.trading_mode != "live":
            return

        if not self.binance.is_configured() and not self.bybit.is_configured():
            raise ValueError(
                "Live trading requires at least one exchange to be configured. "
                "Please set API keys for Binance or Bybit in your .env file."
            )

    def get_configured_exchanges(self) -> list[str]:
        """Return list of exchanges that have API credentials configured."""
        exchanges = []
        if self.binance.is_configured():
            exchanges.append("binance")
        if self.bybit.is_configured():
            exchanges.append("bybit")
        return exchanges


# Module-level singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the application settings singleton.

    Returns:
        Settings: The application settings instance.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Force reload of settings from environment.

    Useful for testing or when environment variables change.

    Returns:
        Settings: A fresh Settings instance.
    """
    global _settings
    _settings = None
    return get_settings()

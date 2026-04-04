"""Configuration management module for Crypto Master.

This module provides centralized configuration management using Pydantic Settings.
All configuration is loaded from environment variables and .env file.

Related Requirements:
- NFR-004: Environment Variable Management
- NFR-011: API Key Protection
"""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BinanceConfig(BaseSettings):
    """Binance exchange configuration.

    Environment variables:
    - BINANCE_API_KEY: API key for Binance
    - BINANCE_API_SECRET: API secret for Binance
    - BINANCE_MARKET_TYPE: Market type (spot/futures)
    """

    api_key: str = ""
    api_secret: str = ""
    market_type: Literal["spot", "futures"] = "futures"

    model_config = SettingsConfigDict(env_prefix="BINANCE_")

    def is_configured(self) -> bool:
        """Check if API credentials are configured."""
        return bool(self.api_key and self.api_secret)


class BybitConfig(BaseSettings):
    """Bybit exchange configuration.

    Environment variables:
    - BYBIT_API_KEY: API key for Bybit
    - BYBIT_API_SECRET: API secret for Bybit
    - BYBIT_TESTNET: Whether to use testnet
    """

    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True

    model_config = SettingsConfigDict(env_prefix="BYBIT_")

    def is_configured(self) -> bool:
        """Check if API credentials are configured."""
        return bool(self.api_key and self.api_secret)


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

    # Exchange Configurations (nested)
    binance: BinanceConfig = Field(default_factory=BinanceConfig)
    bybit: BybitConfig = Field(default_factory=BybitConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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

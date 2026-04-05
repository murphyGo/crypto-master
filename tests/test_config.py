"""Tests for the configuration module.

Tests cover:
- Default settings loading
- Environment variable loading
- Validation rules
- Exchange configuration
- Singleton pattern
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config import (
    BinanceConfig,
    BybitConfig,
    Settings,
    get_settings,
    reload_settings,
)


class TestBinanceConfig:
    """Tests for BinanceConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = BinanceConfig()
        assert config.api_key == ""
        assert config.api_secret == ""
        assert config.market_type == "futures"

    def test_is_configured_false_when_empty(self) -> None:
        """Test is_configured returns False when credentials are empty."""
        config = BinanceConfig()
        assert config.is_configured() is False

    def test_is_configured_true_when_set(self) -> None:
        """Test is_configured returns True when credentials are set."""
        config = BinanceConfig(api_key="test_key", api_secret="test_secret")
        assert config.is_configured() is True

    def test_is_configured_false_when_partial(self) -> None:
        """Test is_configured returns False when only one credential is set."""
        config = BinanceConfig(api_key="test_key")
        assert config.is_configured() is False

    def test_market_type_validation(self) -> None:
        """Test market_type only accepts valid values."""
        config = BinanceConfig(market_type="spot")
        assert config.market_type == "spot"

        config = BinanceConfig(market_type="futures")
        assert config.market_type == "futures"

    def test_invalid_market_type_raises_error(self) -> None:
        """Test invalid market_type raises ValidationError."""
        with pytest.raises(ValidationError):
            BinanceConfig(market_type="invalid")

    def test_loads_from_env_with_prefix(self) -> None:
        """Test configuration loads from environment with BINANCE_ prefix."""
        with patch.dict(
            os.environ,
            {
                "BINANCE_API_KEY": "env_key",
                "BINANCE_API_SECRET": "env_secret",
                "BINANCE_MARKET_TYPE": "spot",
            },
        ):
            config = BinanceConfig()
            assert config.api_key == "env_key"
            assert config.api_secret == "env_secret"
            assert config.market_type == "spot"

    def test_get_credentials_returns_live_keys_when_testnet_false(self) -> None:
        """Test get_credentials returns live keys when testnet=False."""
        config = BinanceConfig(
            api_key="live_key",
            api_secret="live_secret",
            testnet_api_key="testnet_key",
            testnet_api_secret="testnet_secret",
            testnet=False,
        )
        key, secret = config.get_credentials()
        assert key == "live_key"
        assert secret == "live_secret"

    def test_get_credentials_returns_testnet_keys_when_testnet_true(self) -> None:
        """Test get_credentials returns testnet keys when testnet=True."""
        config = BinanceConfig(
            api_key="live_key",
            api_secret="live_secret",
            testnet_api_key="testnet_key",
            testnet_api_secret="testnet_secret",
            testnet=True,
        )
        key, secret = config.get_credentials()
        assert key == "testnet_key"
        assert secret == "testnet_secret"

    def test_get_credentials_fallback_to_live_when_no_testnet_keys(self) -> None:
        """Test get_credentials falls back to live keys when testnet keys not set."""
        config = BinanceConfig(
            api_key="live_key",
            api_secret="live_secret",
            testnet=True,
        )
        key, secret = config.get_credentials()
        assert key == "live_key"
        assert secret == "live_secret"

    def test_is_configured_true_with_testnet_keys(self) -> None:
        """Test is_configured returns True when only testnet credentials are set."""
        config = BinanceConfig(
            testnet_api_key="testnet_key", testnet_api_secret="testnet_secret"
        )
        assert config.is_configured() is True

    def test_testnet_keys_load_from_env(self) -> None:
        """Test testnet keys load from environment variables."""
        with patch.dict(
            os.environ,
            {
                "BINANCE_TESTNET_API_KEY": "env_testnet_key",
                "BINANCE_TESTNET_API_SECRET": "env_testnet_secret",
            },
        ):
            config = BinanceConfig()
            assert config.testnet_api_key == "env_testnet_key"
            assert config.testnet_api_secret == "env_testnet_secret"


class TestBybitConfig:
    """Tests for BybitConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = BybitConfig()
        assert config.api_key == ""
        assert config.api_secret == ""
        assert config.testnet is True

    def test_is_configured_false_when_empty(self) -> None:
        """Test is_configured returns False when credentials are empty."""
        config = BybitConfig()
        assert config.is_configured() is False

    def test_is_configured_true_when_set(self) -> None:
        """Test is_configured returns True when credentials are set."""
        config = BybitConfig(api_key="test_key", api_secret="test_secret")
        assert config.is_configured() is True

    def test_testnet_boolean_conversion(self) -> None:
        """Test testnet accepts boolean values."""
        config = BybitConfig(testnet=False)
        assert config.testnet is False

    def test_loads_from_env_with_prefix(self) -> None:
        """Test configuration loads from environment with BYBIT_ prefix."""
        with patch.dict(
            os.environ,
            {
                "BYBIT_API_KEY": "env_key",
                "BYBIT_API_SECRET": "env_secret",
                "BYBIT_TESTNET": "false",
            },
        ):
            config = BybitConfig()
            assert config.api_key == "env_key"
            assert config.api_secret == "env_secret"
            assert config.testnet is False

    def test_get_credentials_returns_live_keys_when_testnet_false(self) -> None:
        """Test get_credentials returns live keys when testnet=False."""
        config = BybitConfig(
            api_key="live_key",
            api_secret="live_secret",
            testnet_api_key="testnet_key",
            testnet_api_secret="testnet_secret",
            testnet=False,
        )
        key, secret = config.get_credentials()
        assert key == "live_key"
        assert secret == "live_secret"

    def test_get_credentials_returns_testnet_keys_when_testnet_true(self) -> None:
        """Test get_credentials returns testnet keys when testnet=True."""
        config = BybitConfig(
            api_key="live_key",
            api_secret="live_secret",
            testnet_api_key="testnet_key",
            testnet_api_secret="testnet_secret",
            testnet=True,
        )
        key, secret = config.get_credentials()
        assert key == "testnet_key"
        assert secret == "testnet_secret"

    def test_get_credentials_fallback_to_live_when_no_testnet_keys(self) -> None:
        """Test get_credentials falls back to live keys when testnet keys not set."""
        config = BybitConfig(
            api_key="live_key",
            api_secret="live_secret",
            testnet=True,
        )
        key, secret = config.get_credentials()
        assert key == "live_key"
        assert secret == "live_secret"

    def test_is_configured_true_with_testnet_keys(self) -> None:
        """Test is_configured returns True when only testnet credentials are set."""
        config = BybitConfig(
            testnet_api_key="testnet_key", testnet_api_secret="testnet_secret"
        )
        assert config.is_configured() is True

    def test_testnet_keys_load_from_env(self) -> None:
        """Test testnet keys load from environment variables."""
        with patch.dict(
            os.environ,
            {
                "BYBIT_TESTNET_API_KEY": "env_testnet_key",
                "BYBIT_TESTNET_API_SECRET": "env_testnet_secret",
            },
        ):
            config = BybitConfig()
            assert config.testnet_api_key == "env_testnet_key"
            assert config.testnet_api_secret == "env_testnet_secret"


class TestSettings:
    """Tests for main Settings class."""

    def test_default_values(self) -> None:
        """Test default settings values."""
        settings = Settings()
        assert settings.trading_mode == "paper"
        assert settings.log_level == "INFO"
        assert settings.log_file == Path("data/logs/crypto-master.log")
        assert settings.data_dir == Path("data")
        assert settings.paper_initial_balance == 10000.0
        assert settings.max_leverage == 10
        assert settings.max_position_size_pct == 10.0
        assert settings.default_stop_loss_pct == 2.0

    def test_trading_mode_validation(self) -> None:
        """Test trading_mode only accepts valid values."""
        settings = Settings(trading_mode="paper")
        assert settings.trading_mode == "paper"

        settings = Settings(trading_mode="live")
        assert settings.trading_mode == "live"

    def test_invalid_trading_mode_raises_error(self) -> None:
        """Test invalid trading_mode raises ValidationError."""
        with pytest.raises(ValidationError):
            Settings(trading_mode="invalid")

    def test_log_level_validation(self) -> None:
        """Test log_level only accepts valid values."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            settings = Settings(log_level=level)
            assert settings.log_level == level

    def test_invalid_log_level_raises_error(self) -> None:
        """Test invalid log_level raises ValidationError."""
        with pytest.raises(ValidationError):
            Settings(log_level="INVALID")

    def test_paper_initial_balance_must_be_positive(self) -> None:
        """Test paper_initial_balance must be greater than 0."""
        with pytest.raises(ValidationError):
            Settings(paper_initial_balance=0)

        with pytest.raises(ValidationError):
            Settings(paper_initial_balance=-100)

    def test_max_leverage_constraints(self) -> None:
        """Test max_leverage must be between 1 and 125."""
        settings = Settings(max_leverage=1)
        assert settings.max_leverage == 1

        settings = Settings(max_leverage=125)
        assert settings.max_leverage == 125

        with pytest.raises(ValidationError):
            Settings(max_leverage=0)

        with pytest.raises(ValidationError):
            Settings(max_leverage=126)

    def test_max_position_size_pct_constraints(self) -> None:
        """Test max_position_size_pct must be between 0 and 100."""
        settings = Settings(max_position_size_pct=0.1)
        assert settings.max_position_size_pct == 0.1

        settings = Settings(max_position_size_pct=100)
        assert settings.max_position_size_pct == 100

        with pytest.raises(ValidationError):
            Settings(max_position_size_pct=0)

        with pytest.raises(ValidationError):
            Settings(max_position_size_pct=101)

    def test_default_stop_loss_pct_constraints(self) -> None:
        """Test default_stop_loss_pct must be between 0 and 100."""
        settings = Settings(default_stop_loss_pct=0.5)
        assert settings.default_stop_loss_pct == 0.5

        with pytest.raises(ValidationError):
            Settings(default_stop_loss_pct=0)

        with pytest.raises(ValidationError):
            Settings(default_stop_loss_pct=101)

    def test_nested_exchange_configs(self) -> None:
        """Test nested exchange configurations are created."""
        settings = Settings()
        assert isinstance(settings.binance, BinanceConfig)
        assert isinstance(settings.bybit, BybitConfig)

    def test_validate_for_live_trading_paper_mode(self) -> None:
        """Test validation passes for paper trading without API keys."""
        settings = Settings(trading_mode="paper")
        settings.validate_for_live_trading()  # Should not raise

    def test_validate_for_live_trading_with_binance(self) -> None:
        """Test validation passes for live trading with Binance configured."""
        settings = Settings(
            trading_mode="live",
            binance=BinanceConfig(api_key="key", api_secret="secret"),
        )
        settings.validate_for_live_trading()  # Should not raise

    def test_validate_for_live_trading_with_bybit(self) -> None:
        """Test validation passes for live trading with Bybit configured."""
        settings = Settings(
            trading_mode="live",
            bybit=BybitConfig(api_key="key", api_secret="secret"),
        )
        settings.validate_for_live_trading()  # Should not raise

    def test_validate_for_live_trading_no_exchange_raises(self) -> None:
        """Test validation fails for live trading without any exchange."""
        settings = Settings(trading_mode="live")
        with pytest.raises(ValueError, match="Live trading requires"):
            settings.validate_for_live_trading()

    def test_get_configured_exchanges_none(self) -> None:
        """Test get_configured_exchanges returns empty list when none configured."""
        settings = Settings()
        assert settings.get_configured_exchanges() == []

    def test_get_configured_exchanges_binance(self) -> None:
        """Test get_configured_exchanges includes binance when configured."""
        settings = Settings(
            binance=BinanceConfig(api_key="key", api_secret="secret")
        )
        assert settings.get_configured_exchanges() == ["binance"]

    def test_get_configured_exchanges_both(self) -> None:
        """Test get_configured_exchanges includes both when configured."""
        settings = Settings(
            binance=BinanceConfig(api_key="key", api_secret="secret"),
            bybit=BybitConfig(api_key="key", api_secret="secret"),
        )
        assert settings.get_configured_exchanges() == ["binance", "bybit"]

    def test_loads_from_env(self) -> None:
        """Test settings load from environment variables."""
        with patch.dict(
            os.environ,
            {
                "TRADING_MODE": "live",
                "LOG_LEVEL": "DEBUG",
                "MAX_LEVERAGE": "20",
                "BINANCE_API_KEY": "binance_key",
                "BINANCE_API_SECRET": "binance_secret",
            },
        ):
            settings = Settings()
            assert settings.trading_mode == "live"
            assert settings.log_level == "DEBUG"
            assert settings.max_leverage == 20
            assert settings.binance.api_key == "binance_key"
            assert settings.binance.api_secret == "binance_secret"


class TestSingleton:
    """Tests for singleton pattern functions."""

    def test_get_settings_returns_same_instance(self) -> None:
        """Test get_settings returns the same instance on multiple calls."""
        reload_settings()  # Reset first
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_reload_settings_creates_new_instance(self) -> None:
        """Test reload_settings creates a new instance."""
        settings1 = get_settings()
        settings2 = reload_settings()
        # They should be different objects but with same default values
        assert settings1 is not settings2
        assert settings1.trading_mode == settings2.trading_mode

    def test_reload_settings_picks_up_env_changes(self) -> None:
        """Test reload_settings picks up environment variable changes."""
        reload_settings()  # Reset
        settings1 = get_settings()
        assert settings1.trading_mode == "paper"

        with patch.dict(os.environ, {"TRADING_MODE": "live"}):
            settings2 = reload_settings()
            assert settings2.trading_mode == "live"

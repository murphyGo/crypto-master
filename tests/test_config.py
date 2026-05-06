"""Tests for the configuration module.

Tests cover:
- Default settings loading
- Environment variable loading
- Validation rules
- Exchange configuration
- Singleton pattern
"""

import os
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config import (
    BinanceConfig,
    BybitConfig,
    ExchangeCredential,
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

    def test_exchange_credentials_parse_named_env_refs(self) -> None:
        with patch.dict(
            os.environ,
            {
                "EXCHANGE_BINANCE_MAIN_API_KEY": "bn-main-key",
                "EXCHANGE_BINANCE_MAIN_API_SECRET": "bn-main-secret",
                "EXCHANGE_BINANCE_ALT_API_KEY": "bn-alt-key",
                "EXCHANGE_BINANCE_ALT_API_SECRET": "bn-alt-secret",
                "EXCHANGE_BINANCE_ALT_TESTNET": "false",
                "EXCHANGE_BYBIT_MAIN_API_KEY": "by-main-key",
                "EXCHANGE_BYBIT_MAIN_API_SECRET": "by-main-secret",
                "EXCHANGE_BYBIT_MAIN_EXCHANGE": "bybit",
            },
            clear=False,
        ):
            settings = Settings()

        assert set(settings.exchange_credentials) >= {
            "binance_main",
            "binance_alt",
            "bybit_main",
        }
        assert settings.exchange_credentials["binance_alt"].exchange == "binance"
        assert settings.exchange_credentials["binance_alt"].api_key == "bn-alt-key"
        assert settings.exchange_credentials["bybit_main"].exchange == "bybit"

    def test_exchange_credentials_legacy_binance_alias(self) -> None:
        settings = Settings(
            binance=BinanceConfig(api_key="key", api_secret="secret", testnet=False)
        )

        credential = settings.exchange_credentials["binance_main"]
        assert credential == ExchangeCredential(
            ref="binance_main",
            exchange="binance",
            api_key="key",
            api_secret="secret",
            testnet=False,
            market_type="futures",
        )

    def test_exchange_credentials_reject_legacy_explicit_conflict(self) -> None:
        with patch.dict(
            os.environ,
            {
                "EXCHANGE_BINANCE_MAIN_API_KEY": "explicit-key",
                "EXCHANGE_BINANCE_MAIN_API_SECRET": "explicit-secret",
            },
            clear=False,
        ):
            with pytest.raises(ValidationError, match="Conflicting credentials"):
                Settings(
                    binance=BinanceConfig(
                        api_key="legacy-key",
                        api_secret="legacy-secret",
                    )
                )

    def test_validate_for_live_trading_accepts_named_credentials(self) -> None:
        settings = Settings(
            trading_mode="live",
            exchange_credentials={
                "binance_alt": ExchangeCredential(
                    ref="binance_alt",
                    exchange="binance",
                    api_key="key",
                    api_secret="secret",
                )
            },
        )

        settings.validate_for_live_trading()

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
        settings = Settings(binance=BinanceConfig(api_key="key", api_secret="secret"))
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


class TestEngineSettings:
    """Tests for the Phase 10.2 ``engine_*`` env-overridable fields.

    Defaults must match the hardcoded values in
    ``src.runtime.engine.EngineConfig`` so existing deployments don't
    change behaviour when the env vars are unset.
    """

    def test_engine_defaults_match_engine_config(self) -> None:
        """Default values must match EngineConfig's defaults exactly."""
        from src.runtime.engine import EngineConfig

        settings = Settings()
        ec = EngineConfig()

        assert settings.engine_cycle_interval == ec.cycle_interval_seconds
        assert settings.engine_auto_approve_threshold == ec.auto_approve_threshold
        assert settings.engine_symbols == ec.altcoin_symbols
        assert settings.engine_balance == ec.balance
        # Phase 13.2: remaining fields also default-match EngineConfig.
        assert settings.engine_monitor_interval == ec.monitor_interval_seconds
        assert settings.engine_bitcoin_symbol == ec.bitcoin_symbol
        assert settings.engine_altcoin_top_k == ec.altcoin_top_k
        assert settings.engine_actor == ec.actor
        # Phase 18.1: stale-quote sanity gate fields.
        assert settings.engine_fill_slippage_tolerance == ec.fill_slippage_tolerance
        assert settings.engine_reject_if_past_stop_loss == ec.reject_if_past_stop_loss

    def test_engine_cycle_interval_loads_from_env(self) -> None:
        with patch.dict(os.environ, {"ENGINE_CYCLE_INTERVAL": "120"}):
            assert Settings().engine_cycle_interval == 120

    def test_engine_cycle_interval_minimum_enforced(self) -> None:
        """Mirrors EngineConfig's ge=10 floor."""
        with pytest.raises(ValidationError):
            Settings(engine_cycle_interval=5)

    def test_engine_auto_approve_threshold_loads_from_env(self) -> None:
        with patch.dict(os.environ, {"ENGINE_AUTO_APPROVE_THRESHOLD": "2.5"}):
            assert Settings().engine_auto_approve_threshold == 2.5

    def test_engine_auto_approve_threshold_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            Settings(engine_auto_approve_threshold=-0.1)

    def test_engine_symbols_parses_comma_separated_env(self) -> None:
        with patch.dict(
            os.environ,
            {"ENGINE_SYMBOLS": "BTC/USDT,ETH/USDT,SOL/USDT"},
        ):
            assert Settings().engine_symbols == [
                "BTC/USDT",
                "ETH/USDT",
                "SOL/USDT",
            ]

    def test_engine_symbols_strips_whitespace_and_blanks(self) -> None:
        with patch.dict(
            os.environ,
            {"ENGINE_SYMBOLS": " ETH/USDT , ,SOL/USDT  "},
        ):
            assert Settings().engine_symbols == ["ETH/USDT", "SOL/USDT"]

    def test_engine_symbols_accepts_list_directly(self) -> None:
        """Programmatic list assignment (e.g. tests) still works."""
        s = Settings(engine_symbols=["A/USDT", "B/USDT"])
        assert s.engine_symbols == ["A/USDT", "B/USDT"]

    def test_notification_slack_webhook_routes_parse_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "NOTIFICATION_SLACK_WEBHOOK_URLS": (
                    "experimental=https://hooks.slack.com/services/T0/B0/EXP,"
                    "btc=https://hooks.slack.com/services/T0/B0/BTC"
                )
            },
        ):
            assert Settings().notification_slack_webhook_urls == {
                "experimental": "https://hooks.slack.com/services/T0/B0/EXP",
                "btc": "https://hooks.slack.com/services/T0/B0/BTC",
            }

    def test_notification_slack_webhook_routes_parse_json_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "NOTIFICATION_SLACK_WEBHOOK_URLS": (
                    '{"experimental":"https://hooks.slack.com/services/T0/B0/EXP"}'
                )
            },
        ):
            assert Settings().notification_slack_webhook_urls == {
                "experimental": "https://hooks.slack.com/services/T0/B0/EXP"
            }

    def test_engine_balance_loads_from_env(self) -> None:
        with patch.dict(os.environ, {"ENGINE_BALANCE": "5000.50"}):
            assert Settings().engine_balance == Decimal("5000.50")

    def test_engine_balance_default_is_decimal(self) -> None:
        s = Settings()
        assert isinstance(s.engine_balance, Decimal)
        assert s.engine_balance == Decimal("10000")

    # Phase 13.2 (DEBT-003): remaining EngineConfig fields env override
    # ------------------------------------------------------------------

    def test_engine_monitor_interval_default_and_env(self) -> None:
        """Default 60s; ``ENGINE_MONITOR_INTERVAL=120`` overrides."""
        assert Settings().engine_monitor_interval == 60
        with patch.dict(os.environ, {"ENGINE_MONITOR_INTERVAL": "120"}):
            assert Settings().engine_monitor_interval == 120

    def test_engine_monitor_interval_minimum_enforced(self) -> None:
        """Mirrors EngineConfig's ge=10 floor."""
        with pytest.raises(ValidationError):
            Settings(engine_monitor_interval=5)

    def test_engine_bitcoin_symbol_default_and_env(self) -> None:
        """Default ``BTC/USDT``; env override propagates."""
        assert Settings().engine_bitcoin_symbol == "BTC/USDT"
        with patch.dict(os.environ, {"ENGINE_BITCOIN_SYMBOL": "BTC/USD"}):
            assert Settings().engine_bitcoin_symbol == "BTC/USD"

    def test_engine_altcoin_top_k_default_and_env(self) -> None:
        """Default 3; env override propagates; ``ge=1`` validator
        rejects zero/negative."""
        assert Settings().engine_altcoin_top_k == 3
        with patch.dict(os.environ, {"ENGINE_ALTCOIN_TOP_K": "5"}):
            assert Settings().engine_altcoin_top_k == 5
        with patch.dict(os.environ, {"ENGINE_ALTCOIN_TOP_K": "0"}):
            with pytest.raises(ValidationError):
                Settings()

    def test_engine_actor_default_and_env(self) -> None:
        """Default ``auto-engine``; env override propagates."""
        assert Settings().engine_actor == "auto-engine"
        with patch.dict(os.environ, {"ENGINE_ACTOR": "fly-prod-1"}):
            assert Settings().engine_actor == "fly-prod-1"


class TestBacktestEngineSettings:
    """Tests for the Phase 17.2 / DEBT-019 backtest circuit-breaker
    fields. Defaults must match ``BacktestConfig``'s defaults so
    callers that build ``BacktestConfig()`` inherit the same
    breaker behaviour as callers that thread ``Settings`` through.
    """

    def test_backtest_defaults_match_backtest_config(self) -> None:
        """Settings defaults must match ``BacktestConfig``'s defaults."""
        from src.backtest.engine import BacktestConfig

        settings = Settings()
        bc = BacktestConfig()

        assert settings.engine_backtest_per_bar_timeout == bc.per_bar_timeout
        assert settings.engine_backtest_max_parse_failures == bc.max_parse_failures

    def test_per_bar_timeout_default_and_env(self) -> None:
        """Default 600.0 (DEBT-020); env override propagates."""
        assert Settings().engine_backtest_per_bar_timeout == 600.0
        with patch.dict(os.environ, {"ENGINE_BACKTEST_PER_BAR_TIMEOUT": "180.0"}):
            assert Settings().engine_backtest_per_bar_timeout == 180.0

    def test_per_bar_timeout_minimum_enforced(self) -> None:
        """``ge=1.0`` floor — sub-second timeout is meaningless."""
        with pytest.raises(ValidationError):
            Settings(engine_backtest_per_bar_timeout=0.5)

    def test_max_parse_failures_default_and_env(self) -> None:
        """Default 5; env override propagates."""
        assert Settings().engine_backtest_max_parse_failures == 5
        with patch.dict(os.environ, {"ENGINE_BACKTEST_MAX_PARSE_FAILURES": "20"}):
            assert Settings().engine_backtest_max_parse_failures == 20

    def test_max_parse_failures_minimum_enforced(self) -> None:
        """``ge=1`` floor — zero would trip on the first error."""
        with pytest.raises(ValidationError):
            Settings(engine_backtest_max_parse_failures=0)


class TestLogRetentionSettings:
    """Tests for the Phase 10.4 ``log_retention_months`` field."""

    def test_default_is_twelve_months(self) -> None:
        assert Settings().log_retention_months == 12

    def test_loads_from_env(self) -> None:
        with patch.dict(os.environ, {"LOG_RETENTION_MONTHS": "6"}):
            assert Settings().log_retention_months == 6

    def test_must_be_at_least_one(self) -> None:
        """``ge=1`` floor — zero or negative retention is meaningless."""
        with pytest.raises(ValidationError):
            Settings(log_retention_months=0)
        with pytest.raises(ValidationError):
            Settings(log_retention_months=-1)


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

"""Tests for trading strategy module.

Tests TradingStrategy, TradingStrategyConfig, and related exceptions.
"""

from decimal import Decimal

import pytest

from src.models import AnalysisResult, Position
from src.trading.strategy import (
    InsufficientBalanceError,
    TradingError,
    TradingStrategy,
    TradingStrategyConfig,
    TradingValidationError,
)


@pytest.fixture
def strategy() -> TradingStrategy:
    """Create a TradingStrategy with default config but high max position size."""
    config = TradingStrategyConfig(
        max_position_size_percent=100.0,  # Allow full position for basic tests
    )
    return TradingStrategy(config=config)


@pytest.fixture
def custom_strategy() -> TradingStrategy:
    """Create a TradingStrategy with custom config."""
    config = TradingStrategyConfig(
        min_risk_reward_ratio=2.0,
        default_risk_percent=2.0,
        default_leverage=5,
        max_leverage=50,
        max_position_size_percent=20.0,
    )
    return TradingStrategy(config=config)


@pytest.fixture
def long_analysis() -> AnalysisResult:
    """Create a valid long analysis result."""
    return AnalysisResult(
        signal="long",
        confidence=0.8,
        entry_price=Decimal("50000"),
        stop_loss=Decimal("49000"),  # 2% below entry
        take_profit=Decimal("53000"),  # 6% above entry, R/R = 3.0
        reasoning="Bullish pattern",
    )


@pytest.fixture
def short_analysis() -> AnalysisResult:
    """Create a valid short analysis result."""
    return AnalysisResult(
        signal="short",
        confidence=0.75,
        entry_price=Decimal("50000"),
        stop_loss=Decimal("51000"),  # 2% above entry
        take_profit=Decimal("47000"),  # 6% below entry, R/R = 3.0
        reasoning="Bearish pattern",
    )


@pytest.fixture
def neutral_analysis() -> AnalysisResult:
    """Create a neutral analysis result."""
    return AnalysisResult(
        signal="neutral",
        confidence=0.5,
        entry_price=Decimal("50000"),
        stop_loss=Decimal("49000"),
        take_profit=Decimal("51000"),
        reasoning="No clear signal",
    )


class TestTradingExceptions:
    """Tests for trading exception classes."""

    def test_trading_error_base(self) -> None:
        """Test TradingError is base exception."""
        error = TradingError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_trading_validation_error(self) -> None:
        """Test TradingValidationError with field and value."""
        error = TradingValidationError(
            "Invalid stop loss",
            field="stop_loss",
            value=Decimal("51000"),
        )
        assert str(error) == "Invalid stop loss"
        assert error.field == "stop_loss"
        assert error.value == Decimal("51000")
        assert isinstance(error, TradingError)

    def test_insufficient_balance_error(self) -> None:
        """Test InsufficientBalanceError with amounts."""
        error = InsufficientBalanceError(
            "Not enough balance",
            required=Decimal("10000"),
            available=Decimal("5000"),
        )
        assert str(error) == "Not enough balance"
        assert error.required == Decimal("10000")
        assert error.available == Decimal("5000")
        assert isinstance(error, TradingError)


class TestTradingStrategyConfig:
    """Tests for TradingStrategyConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = TradingStrategyConfig()
        assert config.min_risk_reward_ratio == 1.5
        assert config.default_risk_percent == 1.0
        assert config.default_leverage == 1
        assert config.max_leverage == 125
        assert config.max_position_size_percent == 10.0

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = TradingStrategyConfig(
            min_risk_reward_ratio=2.0,
            default_risk_percent=0.5,
            max_leverage=20,
        )
        assert config.min_risk_reward_ratio == 2.0
        assert config.default_risk_percent == 0.5
        assert config.max_leverage == 20

    def test_validation_risk_percent_zero(self) -> None:
        """Test risk_percent must be positive."""
        with pytest.raises(ValueError):
            TradingStrategyConfig(default_risk_percent=0)

    def test_validation_risk_percent_over_100(self) -> None:
        """Test risk_percent must be <= 100."""
        with pytest.raises(ValueError):
            TradingStrategyConfig(default_risk_percent=101)

    def test_validation_leverage_below_one(self) -> None:
        """Test leverage must be >= 1."""
        with pytest.raises(ValueError):
            TradingStrategyConfig(default_leverage=0)

    def test_validation_leverage_above_125(self) -> None:
        """Test leverage must be <= 125."""
        with pytest.raises(ValueError):
            TradingStrategyConfig(max_leverage=126)


class TestPriceValidation:
    """Tests for price validation logic."""

    def test_valid_long_prices(self, strategy: TradingStrategy) -> None:
        """Test valid long position prices."""
        strategy.validate_prices(
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
        )
        # Should not raise

    def test_valid_short_prices(self, strategy: TradingStrategy) -> None:
        """Test valid short position prices."""
        strategy.validate_prices(
            signal="short",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("51000"),
            take_profit=Decimal("48000"),
        )
        # Should not raise

    def test_long_sl_above_entry_fails(self, strategy: TradingStrategy) -> None:
        """Test long with SL above entry fails."""
        with pytest.raises(TradingValidationError) as exc_info:
            strategy.validate_prices(
                signal="long",
                entry_price=Decimal("50000"),
                stop_loss=Decimal("51000"),  # Above entry - invalid
                take_profit=Decimal("52000"),
            )
        assert exc_info.value.field == "stop_loss"

    def test_long_sl_equal_entry_fails(self, strategy: TradingStrategy) -> None:
        """Test long with SL equal to entry fails."""
        with pytest.raises(TradingValidationError) as exc_info:
            strategy.validate_prices(
                signal="long",
                entry_price=Decimal("50000"),
                stop_loss=Decimal("50000"),  # Equal to entry - invalid
                take_profit=Decimal("52000"),
            )
        assert exc_info.value.field == "stop_loss"

    def test_long_tp_below_entry_fails(self, strategy: TradingStrategy) -> None:
        """Test long with TP below entry fails."""
        with pytest.raises(TradingValidationError) as exc_info:
            strategy.validate_prices(
                signal="long",
                entry_price=Decimal("50000"),
                stop_loss=Decimal("49000"),
                take_profit=Decimal("49500"),  # Below entry - invalid
            )
        assert exc_info.value.field == "take_profit"

    def test_short_sl_below_entry_fails(self, strategy: TradingStrategy) -> None:
        """Test short with SL below entry fails."""
        with pytest.raises(TradingValidationError) as exc_info:
            strategy.validate_prices(
                signal="short",
                entry_price=Decimal("50000"),
                stop_loss=Decimal("49000"),  # Below entry - invalid for short
                take_profit=Decimal("48000"),
            )
        assert exc_info.value.field == "stop_loss"

    def test_short_tp_above_entry_fails(self, strategy: TradingStrategy) -> None:
        """Test short with TP above entry fails."""
        with pytest.raises(TradingValidationError) as exc_info:
            strategy.validate_prices(
                signal="short",
                entry_price=Decimal("50000"),
                stop_loss=Decimal("51000"),
                take_profit=Decimal("50500"),  # Above entry - invalid for short
            )
        assert exc_info.value.field == "take_profit"

    def test_neutral_skips_validation(self, strategy: TradingStrategy) -> None:
        """Test neutral signal skips price validation."""
        strategy.validate_prices(
            signal="neutral",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("51000"),  # Would be invalid for long
            take_profit=Decimal("49000"),  # Would be invalid for long
        )
        # Should not raise

    def test_negative_entry_fails(self, strategy: TradingStrategy) -> None:
        """Test negative entry price fails."""
        with pytest.raises(TradingValidationError) as exc_info:
            strategy.validate_prices(
                signal="long",
                entry_price=Decimal("-50000"),
                stop_loss=Decimal("49000"),
                take_profit=Decimal("52000"),
            )
        assert exc_info.value.field == "entry_price"


class TestRiskRewardValidation:
    """Tests for R/R ratio validation."""

    def test_valid_rr_ratio(
        self,
        strategy: TradingStrategy,
        long_analysis: AnalysisResult,
    ) -> None:
        """Test valid R/R ratio passes."""
        rr = strategy.validate_risk_reward(long_analysis)
        assert rr == 3.0  # (53000-50000) / (50000-49000)

    def test_low_rr_ratio_fails(self, strategy: TradingStrategy) -> None:
        """Test R/R below minimum fails."""
        low_rr_analysis = AnalysisResult(
            signal="long",
            confidence=0.8,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("50500"),  # Only 0.5 R/R
            reasoning="Test",
        )

        with pytest.raises(TradingValidationError) as exc_info:
            strategy.validate_risk_reward(low_rr_analysis)
        assert exc_info.value.field == "risk_reward_ratio"

    def test_custom_min_rr(
        self,
        custom_strategy: TradingStrategy,
        long_analysis: AnalysisResult,
    ) -> None:
        """Test custom minimum R/R threshold."""
        # custom_strategy has min_risk_reward_ratio=2.0
        # long_analysis has R/R=3.0, should pass
        rr = custom_strategy.validate_risk_reward(long_analysis)
        assert rr == 3.0

    def test_rr_below_custom_min_fails(
        self,
        custom_strategy: TradingStrategy,
    ) -> None:
        """Test R/R below custom minimum fails."""
        # R/R = 1.5, below custom min of 2.0
        analysis = AnalysisResult(
            signal="long",
            confidence=0.8,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("51500"),  # R/R = 1.5
            reasoning="Test",
        )

        with pytest.raises(TradingValidationError):
            custom_strategy.validate_risk_reward(analysis)

    def test_zero_risk_fails(self, strategy: TradingStrategy) -> None:
        """Test zero risk (SL = entry) fails."""
        zero_risk = AnalysisResult(
            signal="long",
            confidence=0.8,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("50000"),  # Same as entry
            take_profit=Decimal("52000"),
            reasoning="Test",
        )

        with pytest.raises(TradingValidationError):
            strategy.validate_risk_reward(zero_risk)

    def test_override_min_ratio(
        self,
        strategy: TradingStrategy,
    ) -> None:
        """Test overriding min_ratio parameter."""
        # R/R = 1.0
        analysis = AnalysisResult(
            signal="long",
            confidence=0.8,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("51000"),  # R/R = 1.0
            reasoning="Test",
        )

        # Default min is 1.5, should fail
        with pytest.raises(TradingValidationError):
            strategy.validate_risk_reward(analysis)

        # Override to 0.5, should pass
        rr = strategy.validate_risk_reward(analysis, min_ratio=0.5)
        assert rr == 1.0


class TestAnalysisValidation:
    """Tests for combined analysis validation."""

    def test_valid_long_analysis(
        self,
        strategy: TradingStrategy,
        long_analysis: AnalysisResult,
    ) -> None:
        """Test valid long analysis passes."""
        strategy.validate_analysis(long_analysis)
        # Should not raise

    def test_valid_short_analysis(
        self,
        strategy: TradingStrategy,
        short_analysis: AnalysisResult,
    ) -> None:
        """Test valid short analysis passes."""
        strategy.validate_analysis(short_analysis)
        # Should not raise

    def test_neutral_skips_validation(
        self,
        strategy: TradingStrategy,
        neutral_analysis: AnalysisResult,
    ) -> None:
        """Test neutral analysis skips validation."""
        strategy.validate_analysis(neutral_analysis)
        # Should not raise


class TestLeverageValidation:
    """Tests for leverage validation."""

    def test_valid_leverage(self, strategy: TradingStrategy) -> None:
        """Test valid leverage passes."""
        assert strategy.validate_leverage(10) == 10
        assert strategy.validate_leverage(1) == 1
        assert strategy.validate_leverage(125) == 125

    def test_leverage_below_one_fails(self, strategy: TradingStrategy) -> None:
        """Test leverage below 1 fails."""
        with pytest.raises(TradingValidationError):
            strategy.validate_leverage(0)

    def test_negative_leverage_fails(self, strategy: TradingStrategy) -> None:
        """Test negative leverage fails."""
        with pytest.raises(TradingValidationError):
            strategy.validate_leverage(-5)

    def test_leverage_capped_at_max(
        self,
        custom_strategy: TradingStrategy,
    ) -> None:
        """Test leverage above max is capped."""
        # custom_strategy has max_leverage=50
        result = custom_strategy.validate_leverage(100)
        assert result == 50


class TestPositionSizeCalculation:
    """Tests for position size calculation."""

    def test_basic_position_size(self, strategy: TradingStrategy) -> None:
        """Test basic position size calculation."""
        # Risk 1% of 10000 = 100 USDT
        # Risk per unit = |50000 - 49000| = 1000
        # Quantity = 100 / 1000 = 0.1
        quantity = strategy.calculate_position_size(
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            balance=Decimal("10000"),
            risk_percent=1.0,
        )
        assert quantity == Decimal("0.1")

    def test_position_size_with_different_risk_percent(
        self,
        strategy: TradingStrategy,
    ) -> None:
        """Test position size with different risk percent."""
        # Risk 2% of 10000 = 200 USDT
        # Risk per unit = 1000
        # Quantity = 200 / 1000 = 0.2
        quantity = strategy.calculate_position_size(
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            balance=Decimal("10000"),
            risk_percent=2.0,
        )
        assert quantity == Decimal("0.2")

    def test_position_size_short(self, strategy: TradingStrategy) -> None:
        """Test position size for short (risk per unit same)."""
        # Risk 1% of 10000 = 100 USDT
        # Risk per unit = |50000 - 51000| = 1000
        # Quantity = 100 / 1000 = 0.1
        quantity = strategy.calculate_position_size(
            entry_price=Decimal("50000"),
            stop_loss=Decimal("51000"),  # Above entry for short
            balance=Decimal("10000"),
            risk_percent=1.0,
        )
        assert quantity == Decimal("0.1")

    def test_position_capped_at_max_size(
        self,
        custom_strategy: TradingStrategy,
    ) -> None:
        """Test position is capped at max position size percent."""
        # custom_strategy has max_position_size_percent=20.0
        # With very tight SL, position would be huge
        quantity = custom_strategy.calculate_position_size(
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49990"),  # Very tight SL (10 risk per unit)
            balance=Decimal("10000"),
            risk_percent=50.0,  # Would create 500 qty
            leverage=1,
        )
        # Max margin = 20% of 10000 = 2000
        # Max notional at 1x leverage = 2000
        # Max quantity = 2000 / 50000 = 0.04
        assert quantity == Decimal("0.04")

    def test_position_with_leverage(self, custom_strategy: TradingStrategy) -> None:
        """Test position with leverage increases max size."""
        # With 10x leverage, can use 10x the margin
        quantity = custom_strategy.calculate_position_size(
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49990"),  # Very tight SL
            balance=Decimal("10000"),
            risk_percent=50.0,
            leverage=10,
        )
        # Max margin = 20% of 10000 = 2000
        # Max notional at 10x leverage = 2000 * 10 = 20000
        # Max quantity = 20000 / 50000 = 0.4
        assert quantity == Decimal("0.4")

    def test_invalid_balance_fails(self, strategy: TradingStrategy) -> None:
        """Test zero/negative balance fails."""
        with pytest.raises(TradingValidationError) as exc_info:
            strategy.calculate_position_size(
                entry_price=Decimal("50000"),
                stop_loss=Decimal("49000"),
                balance=Decimal("0"),
                risk_percent=1.0,
            )
        assert exc_info.value.field == "balance"

    def test_invalid_risk_percent_fails(self, strategy: TradingStrategy) -> None:
        """Test invalid risk percent fails."""
        with pytest.raises(TradingValidationError) as exc_info:
            strategy.calculate_position_size(
                entry_price=Decimal("50000"),
                stop_loss=Decimal("49000"),
                balance=Decimal("10000"),
                risk_percent=0,
            )
        assert exc_info.value.field == "risk_percent"

    def test_zero_risk_per_unit_fails(self, strategy: TradingStrategy) -> None:
        """Test zero risk per unit (SL = entry) fails."""
        with pytest.raises(TradingValidationError) as exc_info:
            strategy.calculate_position_size(
                entry_price=Decimal("50000"),
                stop_loss=Decimal("50000"),  # Same as entry
                balance=Decimal("10000"),
                risk_percent=1.0,
            )
        assert exc_info.value.field == "stop_loss"


class TestCreatePosition:
    """Tests for position creation."""

    def test_create_long_position(
        self,
        strategy: TradingStrategy,
        long_analysis: AnalysisResult,
    ) -> None:
        """Test creating a long position."""
        position = strategy.create_position(
            analysis=long_analysis,
            symbol="BTC/USDT",
            balance=Decimal("10000"),
            leverage=10,
        )

        assert position.symbol == "BTC/USDT"
        assert position.side == "long"
        assert position.entry_price == Decimal("50000")
        assert position.stop_loss == Decimal("49000")
        assert position.take_profit == Decimal("53000")
        assert position.leverage == 10
        assert position.quantity > 0
        assert position.unrealized_pnl == Decimal("0")

    def test_create_short_position(
        self,
        strategy: TradingStrategy,
        short_analysis: AnalysisResult,
    ) -> None:
        """Test creating a short position."""
        position = strategy.create_position(
            analysis=short_analysis,
            symbol="BTC/USDT",
            balance=Decimal("10000"),
            leverage=5,
        )

        assert position.side == "short"
        assert position.stop_loss == Decimal("51000")
        assert position.take_profit == Decimal("47000")
        assert position.leverage == 5

    def test_create_position_neutral_fails(
        self,
        strategy: TradingStrategy,
        neutral_analysis: AnalysisResult,
    ) -> None:
        """Test creating position from neutral fails."""
        with pytest.raises(TradingValidationError) as exc_info:
            strategy.create_position(
                analysis=neutral_analysis,
                symbol="BTC/USDT",
                balance=Decimal("10000"),
            )
        assert exc_info.value.field == "signal"

    def test_create_position_uses_default_leverage(
        self,
        custom_strategy: TradingStrategy,
        long_analysis: AnalysisResult,
    ) -> None:
        """Test position uses default leverage from config."""
        # custom_strategy has default_leverage=5
        position = custom_strategy.create_position(
            analysis=long_analysis,
            symbol="BTC/USDT",
            balance=Decimal("10000"),
        )

        assert position.leverage == 5

    def test_create_position_skip_validation(
        self,
        strategy: TradingStrategy,
    ) -> None:
        """Test position can skip validation."""
        # Invalid analysis (low R/R)
        low_rr = AnalysisResult(
            signal="long",
            confidence=0.8,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("50500"),  # R/R = 0.5
            reasoning="Test",
        )

        # Should fail with validation
        with pytest.raises(TradingValidationError):
            strategy.create_position(
                analysis=low_rr,
                symbol="BTC/USDT",
                balance=Decimal("10000"),
                validate=True,
            )

        # Should succeed without validation
        position = strategy.create_position(
            analysis=low_rr,
            symbol="BTC/USDT",
            balance=Decimal("10000"),
            validate=False,
        )
        assert position is not None
        assert position.side == "long"


class TestTradeMetrics:
    """Tests for trade metrics calculation."""

    def test_calculate_trade_metrics(
        self,
        strategy: TradingStrategy,
        long_analysis: AnalysisResult,
    ) -> None:
        """Test trade metrics calculation."""
        metrics = strategy.calculate_trade_metrics(
            analysis=long_analysis,
            balance=Decimal("10000"),
            leverage=10,
            risk_percent=1.0,
        )

        assert metrics["signal"] == "long"
        assert metrics["entry_price"] == Decimal("50000")
        assert metrics["risk_reward_ratio"] == 3.0
        assert metrics["leverage"] == 10
        assert metrics["risk_percent"] == 1.0
        assert metrics["quantity"] > 0
        assert metrics["notional_value"] > 0
        assert metrics["margin_required"] > 0
        assert metrics["potential_profit"] > 0
        assert metrics["potential_loss"] > 0

    def test_metrics_match_position(
        self,
        strategy: TradingStrategy,
        long_analysis: AnalysisResult,
    ) -> None:
        """Test metrics match created position."""
        metrics = strategy.calculate_trade_metrics(
            analysis=long_analysis,
            balance=Decimal("10000"),
            leverage=10,
            risk_percent=1.0,
        )

        position = strategy.create_position(
            analysis=long_analysis,
            symbol="BTC/USDT",
            balance=Decimal("10000"),
            leverage=10,
            risk_percent=1.0,
        )

        assert position.quantity == metrics["quantity"]
        assert position.leverage == metrics["leverage"]


class TestTradingStrategyIntegration:
    """Integration tests for TradingStrategy."""

    def test_full_workflow(self, strategy: TradingStrategy) -> None:
        """Test complete workflow from analysis to position."""
        # Create analysis
        analysis = AnalysisResult(
            signal="long",
            confidence=0.85,
            entry_price=Decimal("45000"),
            stop_loss=Decimal("44000"),
            take_profit=Decimal("48000"),
            reasoning="Strong support at 44k",
        )

        # Validate
        strategy.validate_analysis(analysis)

        # Calculate metrics
        metrics = strategy.calculate_trade_metrics(
            analysis=analysis,
            balance=Decimal("5000"),
            leverage=20,
            risk_percent=2.0,
        )

        # Create position
        position = strategy.create_position(
            analysis=analysis,
            symbol="BTC/USDT",
            balance=Decimal("5000"),
            leverage=20,
            risk_percent=2.0,
        )

        # Verify position matches metrics
        assert position.quantity == metrics["quantity"]
        assert position.leverage == metrics["leverage"]

    def test_position_margin_calculation(
        self,
        strategy: TradingStrategy,
        long_analysis: AnalysisResult,
    ) -> None:
        """Test that position margin is calculated correctly."""
        position = strategy.create_position(
            analysis=long_analysis,
            symbol="BTC/USDT",
            balance=Decimal("10000"),
            leverage=10,
        )

        # Verify margin = notional / leverage
        expected_margin = position.notional_value / Decimal(position.leverage)
        assert position.margin_required == expected_margin

    def test_strategy_with_settings_defaults(self) -> None:
        """Test strategy uses settings defaults when no config provided."""
        strategy = TradingStrategy()
        # Should not raise, uses config from get_settings()
        assert strategy.config is not None
        assert strategy.config.max_leverage > 0

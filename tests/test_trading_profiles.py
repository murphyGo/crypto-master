"""Tests for TradingProfile model and technique+profile execution helpers."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.models import AnalysisResult
from src.trading.profiles import (
    TradingProfile,
    create_position_from_profile,
    create_strategy_from_profile,
)
from src.trading.strategy import (
    TradingStrategy,
    TradingStrategyConfig,
    TradingValidationError,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def valid_long_analysis() -> AnalysisResult:
    """High-confidence long signal with a solid 2:1 R/R."""
    return AnalysisResult(
        signal="long",
        confidence=0.8,
        entry_price=Decimal("50000"),
        stop_loss=Decimal("49500"),
        take_profit=Decimal("51000"),
        reasoning="test long setup",
        timestamp=datetime.now(),
    )


@pytest.fixture
def low_confidence_analysis() -> AnalysisResult:
    """Same structure as the long analysis but under typical min_confidence."""
    return AnalysisResult(
        signal="long",
        confidence=0.3,
        entry_price=Decimal("50000"),
        stop_loss=Decimal("49500"),
        take_profit=Decimal("51000"),
        reasoning="uncertain setup",
        timestamp=datetime.now(),
    )


@pytest.fixture
def neutral_analysis() -> AnalysisResult:
    """Neutral signal — profiles should reject it."""
    return AnalysisResult(
        signal="neutral",
        confidence=0.9,
        entry_price=Decimal("50000"),
        stop_loss=Decimal("49000"),
        take_profit=Decimal("51000"),
        reasoning="no setup",
        timestamp=datetime.now(),
    )


# =============================================================================
# TradingProfile model
# =============================================================================


class TestTradingProfile:
    """Tests for TradingProfile schema and methods."""

    def test_construct_with_defaults(self) -> None:
        """Profile builds with only the required name."""
        profile = TradingProfile(name="default")
        assert profile.name == "default"
        assert profile.risk_percent == 1.0
        assert profile.max_leverage == 10
        assert profile.default_leverage == 1
        assert profile.order_type == "market"
        assert profile.require_confirmation is True

    def test_name_required_nonempty(self) -> None:
        """Empty name is rejected."""
        with pytest.raises(ValueError):
            TradingProfile(name="")

    def test_default_leverage_cannot_exceed_max(self) -> None:
        """default_leverage must be <= max_leverage."""
        with pytest.raises(ValueError, match="default_leverage"):
            TradingProfile(
                name="broken",
                max_leverage=3,
                default_leverage=10,
            )

    def test_risk_percent_bounds(self) -> None:
        """risk_percent must be in (0, 100]."""
        with pytest.raises(ValueError):
            TradingProfile(name="zero", risk_percent=0)
        with pytest.raises(ValueError):
            TradingProfile(name="over", risk_percent=101)

    def test_min_confidence_bounds(self) -> None:
        """min_confidence must be in [0, 1]."""
        with pytest.raises(ValueError):
            TradingProfile(name="neg", min_confidence=-0.1)
        with pytest.raises(ValueError):
            TradingProfile(name="over", min_confidence=1.5)

    def test_to_strategy_config(self) -> None:
        """to_strategy_config maps profile fields onto TradingStrategyConfig."""
        profile = TradingProfile(
            name="test",
            risk_percent=1.5,
            max_leverage=20,
            default_leverage=5,
            max_position_size_percent=15.0,
            min_risk_reward_ratio=1.8,
        )
        config = profile.to_strategy_config()
        assert isinstance(config, TradingStrategyConfig)
        assert config.default_risk_percent == 1.5
        assert config.max_leverage == 20
        assert config.default_leverage == 5
        assert config.max_position_size_percent == 15.0
        assert config.min_risk_reward_ratio == 1.8

    def test_accepts_signal_high_confidence(
        self,
        valid_long_analysis: AnalysisResult,
    ) -> None:
        """High-confidence signal passes the filter."""
        profile = TradingProfile(name="test", min_confidence=0.5)
        assert profile.accepts_signal(valid_long_analysis) is True

    def test_accepts_signal_low_confidence(
        self,
        low_confidence_analysis: AnalysisResult,
    ) -> None:
        """Low-confidence signal is rejected."""
        profile = TradingProfile(name="test", min_confidence=0.5)
        assert profile.accepts_signal(low_confidence_analysis) is False

    def test_accepts_signal_neutral_rejected(
        self,
        neutral_analysis: AnalysisResult,
    ) -> None:
        """Neutral signals are always rejected regardless of confidence."""
        profile = TradingProfile(name="test", min_confidence=0.0)
        assert profile.accepts_signal(neutral_analysis) is False

    def test_accepts_signal_equal_to_threshold(
        self, valid_long_analysis: AnalysisResult
    ) -> None:
        """Confidence equal to min_confidence is accepted."""
        profile = TradingProfile(name="test", min_confidence=0.8)
        assert profile.accepts_signal(valid_long_analysis) is True


# =============================================================================
# create_strategy_from_profile
# =============================================================================


class TestCreateStrategyFromProfile:
    """Tests for the TradingStrategy factory helper."""

    def test_returns_trading_strategy(self) -> None:
        profile = TradingProfile(name="test", risk_percent=2.0, max_leverage=5)
        strategy = create_strategy_from_profile(profile)
        assert isinstance(strategy, TradingStrategy)
        assert strategy.config.default_risk_percent == 2.0
        assert strategy.config.max_leverage == 5


# =============================================================================
# create_position_from_profile
# =============================================================================


class TestCreatePositionFromProfile:
    """Tests for the technique+profile integration helper."""

    def test_high_confidence_creates_position(
        self,
        valid_long_analysis: AnalysisResult,
    ) -> None:
        """Accepted signal yields a Position."""
        profile = TradingProfile(
            name="test",
            risk_percent=1.0,
            min_confidence=0.5,
            min_risk_reward_ratio=1.5,
            max_leverage=10,
            default_leverage=5,
        )
        position = create_position_from_profile(
            analysis=valid_long_analysis,
            profile=profile,
            symbol="BTC/USDT",
            balance=Decimal("10000"),
        )
        assert position is not None
        assert position.symbol == "BTC/USDT"
        assert position.side == "long"
        assert position.leverage == 5

    def test_low_confidence_returns_none(
        self,
        low_confidence_analysis: AnalysisResult,
    ) -> None:
        """Signal below min_confidence is skipped (returns None)."""
        profile = TradingProfile(name="test", min_confidence=0.5)
        result = create_position_from_profile(
            analysis=low_confidence_analysis,
            profile=profile,
            symbol="BTC/USDT",
            balance=Decimal("10000"),
        )
        assert result is None

    def test_neutral_returns_none(
        self,
        neutral_analysis: AnalysisResult,
    ) -> None:
        """Neutral signals return None (profile filter rejects)."""
        profile = TradingProfile(name="test", min_confidence=0.0)
        result = create_position_from_profile(
            analysis=neutral_analysis,
            profile=profile,
            symbol="BTC/USDT",
            balance=Decimal("10000"),
        )
        assert result is None

    def test_leverage_clamped_to_max(
        self,
        valid_long_analysis: AnalysisResult,
    ) -> None:
        """Requested leverage above profile.max_leverage is clamped."""
        profile = TradingProfile(
            name="test",
            max_leverage=3,
            default_leverage=1,
            min_risk_reward_ratio=1.5,
        )
        position = create_position_from_profile(
            analysis=valid_long_analysis,
            profile=profile,
            symbol="BTC/USDT",
            balance=Decimal("10000"),
            leverage=50,
        )
        assert position is not None
        assert position.leverage == 3

    def test_uses_default_leverage_when_unspecified(
        self,
        valid_long_analysis: AnalysisResult,
    ) -> None:
        """When leverage isn't passed, default_leverage is used."""
        profile = TradingProfile(
            name="test",
            max_leverage=10,
            default_leverage=7,
            min_risk_reward_ratio=1.5,
        )
        position = create_position_from_profile(
            analysis=valid_long_analysis,
            profile=profile,
            symbol="BTC/USDT",
            balance=Decimal("10000"),
        )
        assert position is not None
        assert position.leverage == 7

    def test_raises_when_rr_below_profile_min(self) -> None:
        """R/R below profile's minimum raises TradingValidationError."""
        # 50000 entry, 49900 stop, 50050 take -> R/R = 0.5 < 1.5
        poor_rr = AnalysisResult(
            signal="long",
            confidence=0.9,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49900"),
            take_profit=Decimal("50050"),
            reasoning="poor r/r",
            timestamp=datetime.now(),
        )
        profile = TradingProfile(
            name="strict",
            min_confidence=0.5,
            min_risk_reward_ratio=1.5,
        )
        with pytest.raises(TradingValidationError, match="R/R"):
            create_position_from_profile(
                analysis=poor_rr,
                profile=profile,
                symbol="BTC/USDT",
                balance=Decimal("10000"),
            )

    def test_position_sizing_uses_profile_risk_percent(
        self, valid_long_analysis: AnalysisResult
    ) -> None:
        """Position size scales with the profile's risk_percent.

        Uses 10x leverage and a generous max_position_size_percent so
        neither leg hits the position-size cap — that way the ratio
        between low and high risk is purely risk_percent-driven.
        """
        low_risk = TradingProfile(
            name="low",
            risk_percent=0.5,
            min_confidence=0.5,
            min_risk_reward_ratio=1.5,
            max_leverage=10,
            default_leverage=10,
            max_position_size_percent=50.0,
        )
        high_risk = TradingProfile(
            name="high",
            risk_percent=2.0,
            min_confidence=0.5,
            min_risk_reward_ratio=1.5,
            max_leverage=10,
            default_leverage=10,
            max_position_size_percent=50.0,
        )
        balance = Decimal("10000")
        low_pos = create_position_from_profile(
            valid_long_analysis, low_risk, "BTC/USDT", balance
        )
        high_pos = create_position_from_profile(
            valid_long_analysis, high_risk, "BTC/USDT", balance
        )
        assert low_pos is not None and high_pos is not None
        # high risk = 4x low risk, neither capped
        assert high_pos.quantity == low_pos.quantity * 4

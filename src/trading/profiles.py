"""Trading strategy profiles.

A ``TradingProfile`` captures the *style* dimension of a trade —
risk appetite, leverage caps, signal-confidence floor, order type,
confirmation requirements — independent of the analysis technique
that generated the signal. Analysis techniques produce signals;
profiles decide how aggressively to act on them.

Profiles can be combined with any ``AnalysisResult`` via
:func:`create_position_from_profile`, and with the on-disk
``PerformanceTracker`` so that the same technique run under
different profiles can be compared.

Related Requirements:
- FR-005: Analysis Technique Performance Tracking (technique+profile combos)
- FR-006: Risk/Reward Calculation
- FR-007: Leverage Setting
- FR-008: Entry/Take-Profit/Stop-Loss Setting
- FR-009: Live Trading Mode (confirmation toggle)
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from src.logger import get_logger
from src.models import AnalysisResult, Position
from src.trading.strategy import (
    TradingStrategy,
    TradingStrategyConfig,
    TradingValidationError,
)

if TYPE_CHECKING:
    pass

logger = get_logger("crypto_master.trading.profiles")


class TradingProfile(BaseModel):
    """Risk and execution parameters for a trading style.

    A profile is a declarative bundle of knobs that constrain how a
    signal gets turned into a position. Separate from analysis
    technique so the same technique can be backtested or traded
    under multiple profiles (FR-005).

    Attributes:
        name: Unique profile name (file stem on disk).
        version: Profile version string (for change tracking).
        description: Human-readable description of the style.
        risk_percent: Percent of balance to risk per trade.
        max_leverage: Upper bound on leverage applied to any trade.
        default_leverage: Leverage used when none is specified at
            execution time. Must be <= max_leverage.
        max_position_size_percent: Cap on margin as a percentage of
            the account balance.
        min_risk_reward_ratio: Minimum acceptable R/R for a signal
            to produce a trade.
        min_confidence: Minimum signal confidence (0..1) to act on.
            Signals below this are silently skipped.
        order_type: Preferred order type ("market" or "limit").
        require_confirmation: If True, live trading uses an explicit
            user confirmation step (NFR-012). Ignored in paper mode
            where the paper trader executes directly.
    """

    name: str = Field(min_length=1)
    version: str = "1.0.0"
    description: str = ""

    # Risk parameters
    risk_percent: float = Field(default=1.0, gt=0, le=100)
    max_leverage: int = Field(default=10, ge=1, le=125)
    default_leverage: int = Field(default=1, ge=1, le=125)
    max_position_size_percent: float = Field(default=10.0, gt=0, le=100)
    min_risk_reward_ratio: float = Field(default=1.5, gt=0)

    # Signal filtering
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # Execution preferences
    order_type: Literal["market", "limit"] = "market"
    require_confirmation: bool = True

    model_config = {"validate_assignment": True}

    def model_post_init(self, __context: object) -> None:
        """Ensure default_leverage never exceeds max_leverage."""
        if self.default_leverage > self.max_leverage:
            raise ValueError(
                f"default_leverage ({self.default_leverage}) cannot exceed "
                f"max_leverage ({self.max_leverage}) for profile '{self.name}'"
            )

    def to_strategy_config(self) -> TradingStrategyConfig:
        """Translate this profile into a ``TradingStrategyConfig``.

        The returned config can be plugged into ``TradingStrategy``
        to enforce the profile's risk rules.
        """
        return TradingStrategyConfig(
            min_risk_reward_ratio=self.min_risk_reward_ratio,
            default_risk_percent=self.risk_percent,
            default_leverage=self.default_leverage,
            max_leverage=self.max_leverage,
            max_position_size_percent=self.max_position_size_percent,
        )

    def accepts_signal(self, analysis: AnalysisResult) -> bool:
        """Check whether a signal meets the profile's filter rules.

        Currently this only enforces the confidence floor; R/R is
        enforced later by :class:`TradingStrategy` when the position
        is created. Split so callers can short-circuit cheaply.

        Args:
            analysis: The analysis result to evaluate.

        Returns:
            True if the signal should be acted on under this profile.
        """
        if analysis.signal == "neutral":
            return False
        if analysis.confidence < self.min_confidence:
            logger.info(
                f"Profile '{self.name}' rejected signal: confidence "
                f"{analysis.confidence:.2f} < min {self.min_confidence:.2f}"
            )
            return False
        return True


def create_strategy_from_profile(
    profile: TradingProfile,
) -> TradingStrategy:
    """Build a ``TradingStrategy`` preconfigured from a profile.

    Args:
        profile: The profile whose config should drive the strategy.

    Returns:
        A new TradingStrategy instance bound to the profile's rules.
    """
    return TradingStrategy(config=profile.to_strategy_config())


def create_position_from_profile(
    analysis: AnalysisResult,
    profile: TradingProfile,
    symbol: str,
    balance: Decimal,
    leverage: int | None = None,
) -> Position | None:
    """Combine an analysis result with a trading profile.

    This is the main integration point for FR-005's technique+profile
    tracking: analysis produces the signal; the profile decides the
    risk envelope and whether to take it at all.

    Args:
        analysis: The signal from an analysis technique.
        profile: The trading profile to apply.
        symbol: Trading pair symbol.
        balance: Account balance to size the position against.
        leverage: Override leverage. Clamped to the profile's
            max_leverage; if omitted, the profile's default is used.

    Returns:
        A Position ready for execution, or None if the profile's
        signal filter (e.g. confidence floor) rejected the signal.

    Raises:
        TradingValidationError: If the resulting position fails the
            profile's validation (R/R, price consistency, etc).
    """
    if not profile.accepts_signal(analysis):
        return None

    strategy = create_strategy_from_profile(profile)

    effective_leverage = leverage if leverage is not None else profile.default_leverage
    if effective_leverage > profile.max_leverage:
        logger.warning(
            f"Requested leverage {effective_leverage} exceeds profile "
            f"'{profile.name}' max {profile.max_leverage}; clamping"
        )
        effective_leverage = profile.max_leverage

    try:
        position = strategy.create_position(
            analysis=analysis,
            symbol=symbol,
            balance=balance,
            leverage=effective_leverage,
            risk_percent=profile.risk_percent,
        )
    except TradingValidationError:
        raise

    logger.info(
        f"Built position for profile '{profile.name}': {position.side} "
        f"{symbol} qty={position.quantity} lev={effective_leverage}x"
    )
    return position

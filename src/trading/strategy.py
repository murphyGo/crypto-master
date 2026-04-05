"""Trading strategy calculator for position sizing and validation.

Provides calculations for Risk/Reward ratio, position sizing, and
trade parameter validation.

Related Requirements:
- FR-006: Risk/Reward Calculation
- FR-007: Leverage Setting
- FR-008: Entry/Take-Profit/Stop-Loss Setting
"""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.config import get_settings
from src.logger import get_logger
from src.models import AnalysisResult, Position

logger = get_logger("crypto_master.trading.strategy")


class TradingError(Exception):
    """Base exception for trading errors."""

    pass


class TradingValidationError(TradingError):
    """Raised when trade parameters fail validation.

    Attributes:
        field: The field that failed validation.
        value: The invalid value.
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
    ) -> None:
        """Initialize TradingValidationError.

        Args:
            message: Error message.
            field: The field that failed validation.
            value: The invalid value.
        """
        super().__init__(message)
        self.field = field
        self.value = value


class InsufficientBalanceError(TradingError):
    """Raised when balance is insufficient for position.

    Attributes:
        required: The required balance.
        available: The available balance.
    """

    def __init__(
        self,
        message: str,
        required: Decimal,
        available: Decimal,
    ) -> None:
        """Initialize InsufficientBalanceError.

        Args:
            message: Error message.
            required: The required balance.
            available: The available balance.
        """
        super().__init__(message)
        self.required = required
        self.available = available


class TradingStrategyConfig(BaseModel):
    """Configuration for trading strategy calculations.

    Attributes:
        min_risk_reward_ratio: Minimum acceptable R/R ratio.
        default_risk_percent: Default percentage of balance to risk per trade.
        default_leverage: Default leverage if not specified.
        max_leverage: Maximum allowed leverage.
        max_position_size_percent: Maximum position size as % of balance.
    """

    min_risk_reward_ratio: float = Field(default=1.5, gt=0)
    default_risk_percent: float = Field(default=1.0, gt=0, le=100)
    default_leverage: int = Field(default=1, ge=1, le=125)
    max_leverage: int = Field(default=125, ge=1, le=125)
    max_position_size_percent: float = Field(default=10.0, gt=0, le=100)


class TradingStrategy:
    """Trading strategy calculator for position sizing and validation.

    Handles:
    - Risk/Reward ratio validation (FR-006)
    - Leverage configuration (FR-007)
    - Entry/Take-Profit/Stop-Loss validation (FR-008)
    - Position size calculation based on risk amount

    Related Requirements:
    - FR-006: Risk/Reward Calculation
    - FR-007: Leverage Setting
    - FR-008: Entry/Take-Profit/Stop-Loss Setting

    Usage:
        strategy = TradingStrategy()

        # Validate an analysis result
        strategy.validate_analysis(analysis_result)

        # Calculate position from analysis
        position = strategy.create_position(
            analysis_result,
            symbol="BTC/USDT",
            balance=Decimal("10000"),
            leverage=10,
        )
    """

    def __init__(self, config: TradingStrategyConfig | None = None) -> None:
        """Initialize TradingStrategy.

        Args:
            config: Strategy configuration. Uses defaults from Settings if None.
        """
        if config is None:
            settings = get_settings()
            config = TradingStrategyConfig(
                max_leverage=settings.max_leverage,
                max_position_size_percent=settings.max_position_size_pct,
                default_risk_percent=settings.default_stop_loss_pct,
            )
        self.config = config

    def validate_prices(
        self,
        signal: Literal["long", "short", "neutral"],
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
    ) -> None:
        """Validate that prices are consistent with signal direction.

        For long positions:
        - Stop loss must be below entry price
        - Take profit must be above entry price

        For short positions:
        - Stop loss must be above entry price
        - Take profit must be below entry price

        Args:
            signal: Trading direction.
            entry_price: Entry price.
            stop_loss: Stop loss price.
            take_profit: Take profit price.

        Raises:
            TradingValidationError: If prices are inconsistent.
        """
        if signal == "neutral":
            return  # No validation needed for neutral

        if entry_price <= 0:
            raise TradingValidationError(
                "Entry price must be positive",
                field="entry_price",
                value=entry_price,
            )

        if stop_loss <= 0:
            raise TradingValidationError(
                "Stop loss must be positive",
                field="stop_loss",
                value=stop_loss,
            )

        if take_profit <= 0:
            raise TradingValidationError(
                "Take profit must be positive",
                field="take_profit",
                value=take_profit,
            )

        if signal == "long":
            if stop_loss >= entry_price:
                raise TradingValidationError(
                    f"For long position, stop_loss ({stop_loss}) must be below "
                    f"entry_price ({entry_price})",
                    field="stop_loss",
                    value=stop_loss,
                )
            if take_profit <= entry_price:
                raise TradingValidationError(
                    f"For long position, take_profit ({take_profit}) must be above "
                    f"entry_price ({entry_price})",
                    field="take_profit",
                    value=take_profit,
                )

        elif signal == "short":
            if stop_loss <= entry_price:
                raise TradingValidationError(
                    f"For short position, stop_loss ({stop_loss}) must be above "
                    f"entry_price ({entry_price})",
                    field="stop_loss",
                    value=stop_loss,
                )
            if take_profit >= entry_price:
                raise TradingValidationError(
                    f"For short position, take_profit ({take_profit}) must be below "
                    f"entry_price ({entry_price})",
                    field="take_profit",
                    value=take_profit,
                )

    def validate_risk_reward(
        self,
        analysis: AnalysisResult,
        min_ratio: float | None = None,
    ) -> float:
        """Validate that R/R ratio meets minimum threshold.

        Args:
            analysis: Analysis result with entry/SL/TP prices.
            min_ratio: Minimum required R/R ratio. Uses config default if None.

        Returns:
            float: The calculated R/R ratio.

        Raises:
            TradingValidationError: If R/R ratio is below minimum or invalid.
        """
        if min_ratio is None:
            min_ratio = self.config.min_risk_reward_ratio

        rr_ratio = analysis.risk_reward_ratio

        if rr_ratio is None:
            raise TradingValidationError(
                "Cannot calculate R/R ratio (risk may be zero)",
                field="risk_reward_ratio",
            )

        if rr_ratio < min_ratio:
            raise TradingValidationError(
                f"R/R ratio ({rr_ratio:.2f}) is below minimum ({min_ratio:.2f})",
                field="risk_reward_ratio",
                value=rr_ratio,
            )

        return rr_ratio

    def validate_analysis(
        self,
        analysis: AnalysisResult,
        min_risk_reward: float | None = None,
    ) -> None:
        """Validate an analysis result for trading.

        Performs all validations:
        - Price consistency (SL/TP relative to entry)
        - Risk/Reward ratio minimum

        Args:
            analysis: Analysis result to validate.
            min_risk_reward: Optional minimum R/R override.

        Raises:
            TradingValidationError: If any validation fails.
        """
        # Skip validation for neutral signals
        if analysis.signal == "neutral":
            logger.debug("Skipping validation for neutral signal")
            return

        # Validate prices are consistent with direction
        self.validate_prices(
            signal=analysis.signal,
            entry_price=analysis.entry_price,
            stop_loss=analysis.stop_loss,
            take_profit=analysis.take_profit,
        )

        # Validate R/R ratio
        self.validate_risk_reward(analysis, min_risk_reward)

        logger.debug(
            f"Analysis validated: {analysis.signal} signal, "
            f"R/R={analysis.risk_reward_ratio:.2f}"
        )

    def validate_leverage(self, leverage: int) -> int:
        """Validate and constrain leverage.

        Args:
            leverage: Requested leverage.

        Returns:
            int: Validated leverage (may be capped at max).

        Raises:
            TradingValidationError: If leverage is invalid.
        """
        if leverage < 1:
            raise TradingValidationError(
                "Leverage must be at least 1",
                field="leverage",
                value=leverage,
            )

        if leverage > self.config.max_leverage:
            logger.warning(
                f"Leverage {leverage} exceeds max {self.config.max_leverage}, "
                "capping to max"
            )
            return self.config.max_leverage

        return leverage

    def calculate_position_size(
        self,
        entry_price: Decimal,
        stop_loss: Decimal,
        balance: Decimal,
        risk_percent: float | None = None,
        leverage: int = 1,
    ) -> Decimal:
        """Calculate position size based on risk amount.

        Uses standard risk-based position sizing:
        - Risk amount = balance * risk_percent
        - Risk per unit = |entry_price - stop_loss|
        - Quantity = risk_amount / risk_per_unit

        Args:
            entry_price: Entry price.
            stop_loss: Stop loss price.
            balance: Available balance.
            risk_percent: Percentage of balance to risk. Uses config default if None.
            leverage: Leverage multiplier (affects margin requirement, not quantity).

        Returns:
            Decimal: Position quantity (size).

        Raises:
            TradingValidationError: If inputs are invalid.
        """
        if risk_percent is None:
            risk_percent = self.config.default_risk_percent

        # Validate inputs
        if balance <= 0:
            raise TradingValidationError(
                "Balance must be positive",
                field="balance",
                value=balance,
            )

        if risk_percent <= 0 or risk_percent > 100:
            raise TradingValidationError(
                "Risk percent must be between 0 and 100",
                field="risk_percent",
                value=risk_percent,
            )

        # Calculate risk amount
        risk_amount = balance * Decimal(str(risk_percent / 100))

        # Calculate risk per unit (price movement to stop loss)
        risk_per_unit = abs(entry_price - stop_loss)

        if risk_per_unit == 0:
            raise TradingValidationError(
                "Risk per unit is zero (entry equals stop loss)",
                field="stop_loss",
            )

        # Calculate base quantity
        quantity = risk_amount / risk_per_unit

        # Validate position doesn't exceed max position size
        notional_value = quantity * entry_price
        margin_required = notional_value / Decimal(leverage)
        max_position_value = balance * Decimal(
            str(self.config.max_position_size_percent / 100)
        )

        if margin_required > max_position_value:
            # Scale down quantity to fit max position size
            max_notional = max_position_value * Decimal(leverage)
            quantity = max_notional / entry_price
            logger.warning(
                f"Position size capped at {self.config.max_position_size_percent}% "
                f"of balance (margin={margin_required} > max={max_position_value})"
            )

        return quantity

    def create_position(
        self,
        analysis: AnalysisResult,
        symbol: str,
        balance: Decimal,
        leverage: int | None = None,
        risk_percent: float | None = None,
        validate: bool = True,
    ) -> Position:
        """Create a Position from an AnalysisResult.

        This is the main entry point for converting analysis to tradeable position.

        Args:
            analysis: Analysis result with signal and prices.
            symbol: Trading pair symbol.
            balance: Available balance for trading.
            leverage: Leverage multiplier. Uses config default if None.
            risk_percent: Risk percentage. Uses config default if None.
            validate: Whether to validate the analysis first.

        Returns:
            Position: Ready-to-trade position.

        Raises:
            TradingValidationError: If validation fails or signal is neutral.
        """
        if analysis.signal == "neutral":
            raise TradingValidationError(
                "Cannot create position from neutral signal",
                field="signal",
                value="neutral",
            )

        # Validate analysis if requested
        if validate:
            self.validate_analysis(analysis)

        # Set and validate leverage
        if leverage is None:
            leverage = self.config.default_leverage
        leverage = self.validate_leverage(leverage)

        # Calculate position size
        quantity = self.calculate_position_size(
            entry_price=analysis.entry_price,
            stop_loss=analysis.stop_loss,
            balance=balance,
            risk_percent=risk_percent,
            leverage=leverage,
        )

        # Create position
        position = Position(
            symbol=symbol,
            side=analysis.signal,  # "long" or "short"
            entry_price=analysis.entry_price,
            quantity=quantity,
            leverage=leverage,
            stop_loss=analysis.stop_loss,
            take_profit=analysis.take_profit,
            unrealized_pnl=Decimal("0"),
        )

        logger.info(
            f"Created position: {position.side} {symbol} @ {position.entry_price}, "
            f"qty={position.quantity:.8f}, leverage={leverage}x, "
            f"SL={position.stop_loss}, TP={position.take_profit}"
        )

        return position

    def calculate_trade_metrics(
        self,
        analysis: AnalysisResult,
        balance: Decimal,
        leverage: int = 1,
        risk_percent: float | None = None,
    ) -> dict:
        """Calculate detailed trade metrics without creating a position.

        Useful for displaying trade details before execution.

        Args:
            analysis: Analysis result.
            balance: Available balance.
            leverage: Leverage to use.
            risk_percent: Risk percentage.

        Returns:
            dict: Trade metrics including R/R, position size, margin, etc.
        """
        if risk_percent is None:
            risk_percent = self.config.default_risk_percent

        rr_ratio = analysis.risk_reward_ratio or 0.0

        quantity = self.calculate_position_size(
            entry_price=analysis.entry_price,
            stop_loss=analysis.stop_loss,
            balance=balance,
            risk_percent=risk_percent,
            leverage=leverage,
        )

        notional_value = quantity * analysis.entry_price
        margin_required = notional_value / Decimal(leverage)
        risk_amount = balance * Decimal(str(risk_percent / 100))
        potential_profit = quantity * abs(analysis.take_profit - analysis.entry_price)
        potential_loss = quantity * abs(analysis.entry_price - analysis.stop_loss)

        return {
            "signal": analysis.signal,
            "entry_price": analysis.entry_price,
            "stop_loss": analysis.stop_loss,
            "take_profit": analysis.take_profit,
            "risk_reward_ratio": rr_ratio,
            "quantity": quantity,
            "notional_value": notional_value,
            "margin_required": margin_required,
            "leverage": leverage,
            "risk_amount": risk_amount,
            "risk_percent": risk_percent,
            "potential_profit": potential_profit,
            "potential_loss": potential_loss,
            "potential_profit_percent": (
                float(potential_profit / margin_required) * 100
                if margin_required > 0
                else 0
            ),
            "potential_loss_percent": (
                float(potential_loss / margin_required) * 100
                if margin_required > 0
                else 0
            ),
        }

"""Strategy base classes and exceptions for Crypto Master.

This module provides the abstract base class for all analysis techniques,
along with supporting data models and exceptions.

Related Requirements:
- FR-001: Bitcoin Chart Analysis
- FR-002: Altcoin Chart Analysis
- FR-003: Chart Analysis Technique Definition
- NFR-005: Analysis Technique Storage
- NFR-010: Analysis Technique Extensibility
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.models import OHLCV, AnalysisResult


# =============================================================================
# Exceptions
# =============================================================================


class StrategyError(Exception):
    """Base exception for strategy errors.

    All strategy-related exceptions inherit from this class,
    allowing callers to catch all strategy errors with a single except clause.
    """

    pass


class StrategyValidationError(StrategyError):
    """Strategy validation failed.

    Raised when strategy input data or configuration is invalid.

    Attributes:
        field: The field that failed validation, if applicable.
    """

    def __init__(self, message: str, field: str | None = None) -> None:
        """Initialize validation error.

        Args:
            message: Error message describing the validation failure.
            field: The field that failed validation.
        """
        super().__init__(message)
        self.field = field


class StrategyExecutionError(StrategyError):
    """Strategy execution failed.

    Raised when a strategy fails during analysis execution.

    Attributes:
        strategy_name: Name of the strategy that failed.
    """

    def __init__(self, message: str, strategy_name: str | None = None) -> None:
        """Initialize execution error.

        Args:
            message: Error message describing the failure.
            strategy_name: Name of the strategy that failed.
        """
        super().__init__(message)
        self.strategy_name = strategy_name


class StrategyLoadError(StrategyError):
    """Strategy file could not be loaded.

    Raised when a strategy file cannot be read or parsed.

    Attributes:
        file_path: Path to the file that could not be loaded.
    """

    def __init__(self, message: str, file_path: str | None = None) -> None:
        """Initialize load error.

        Args:
            message: Error message describing the load failure.
            file_path: Path to the file that could not be loaded.
        """
        super().__init__(message)
        self.file_path = file_path


# =============================================================================
# Data Models
# =============================================================================


class TechniqueInfo(BaseModel):
    """Metadata for an analysis technique.

    Contains all metadata about a technique including identification,
    versioning, and categorization information.

    Related Requirements:
    - NFR-005: Techniques stored as .md or .py files
    - NFR-010: Technique versioning with version history

    Attributes:
        name: Unique technique identifier.
        version: Semantic version string (e.g., "1.0.0").
        description: Brief description of what the technique does.
        author: Creator of the technique.
        technique_type: Whether this is a prompt-based or code-based technique.
        symbols: Trading pairs this technique is designed for.
        timeframes: Recommended candlestick timeframes.
        status: Lifecycle status of the technique.
        created_at: When the technique was created.
        updated_at: When the technique was last updated.
        changelog: Notes about the current version.
    """

    name: str = Field(min_length=1, description="Unique technique identifier")
    version: str = Field(
        pattern=r"^\d+\.\d+\.\d+$",
        description="Semantic version (e.g., 1.0.0)",
    )
    description: str = Field(min_length=1, description="Brief description")
    author: str = Field(default="system", description="Technique creator")

    technique_type: Literal["prompt", "code"] = Field(
        description="Whether this is a prompt-based (.md) or code-based (.py) technique"
    )

    symbols: list[str] = Field(
        default=["BTC/USDT"],
        description="Symbols this technique is designed for",
    )
    timeframes: list[str] = Field(
        default=["1h", "4h", "1d"],
        description="Recommended timeframes",
    )

    status: Literal["experimental", "active", "deprecated"] = Field(
        default="experimental",
        description="Technique lifecycle status",
    )

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None)
    changelog: str | None = Field(default=None, description="Version change notes")

    model_config = {"frozen": True}


# =============================================================================
# Abstract Base Class
# =============================================================================


class BaseStrategy(ABC):
    """Abstract base class for analysis technique implementations.

    All strategy implementations must inherit from this class and implement
    the abstract methods. This ensures a consistent interface across all
    analysis techniques.

    Related Requirements:
    - FR-001: Bitcoin Chart Analysis
    - FR-002: Altcoin Chart Analysis
    - FR-003: Chart Analysis Technique Definition
    - NFR-010: Analysis Technique Extensibility

    Usage:
        class MyStrategy(BaseStrategy):
            async def analyze(self, ohlcv, symbol, timeframe="1h"):
                # Implementation here
                return AnalysisResult(...)

        strategy = MyStrategy(info=technique_info)
        result = await strategy.analyze(ohlcv_data, symbol="BTC/USDT")
    """

    def __init__(self, info: TechniqueInfo) -> None:
        """Initialize strategy with metadata.

        Args:
            info: Technique metadata containing name, version, etc.
        """
        self._info = info

    @property
    def name(self) -> str:
        """Get technique name.

        Returns:
            The unique identifier for this technique.
        """
        return self._info.name

    @property
    def version(self) -> str:
        """Get technique version.

        Returns:
            The semantic version string.
        """
        return self._info.version

    @property
    def info(self) -> TechniqueInfo:
        """Get full technique metadata.

        Returns:
            Complete TechniqueInfo object.
        """
        return self._info

    @abstractmethod
    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
    ) -> AnalysisResult:
        """Analyze chart data and produce trading signal.

        This is the core method that all strategies must implement.
        It takes OHLCV candlestick data and returns an analysis result
        with trading signals.

        Args:
            ohlcv: List of OHLCV candlestick data, sorted by timestamp ascending.
                   Must contain at least the minimum required candles.
            symbol: Trading pair symbol (e.g., "BTC/USDT").
            timeframe: Candle timeframe (e.g., "1h", "4h", "1d").

        Returns:
            AnalysisResult with signal, confidence, entry/exit prices.

        Raises:
            StrategyValidationError: If input data is invalid.
            StrategyExecutionError: If analysis fails.
        """
        pass

    def validate_input(self, ohlcv: list[OHLCV], min_candles: int = 20) -> None:
        """Validate input data before analysis.

        Helper method to validate OHLCV data. Strategies should call this
        at the beginning of their analyze() method.

        Args:
            ohlcv: Input candlestick data to validate.
            min_candles: Minimum required number of candles.

        Raises:
            StrategyValidationError: If validation fails.
        """
        if not ohlcv:
            raise StrategyValidationError("OHLCV data is empty", field="ohlcv")

        if len(ohlcv) < min_candles:
            raise StrategyValidationError(
                f"Insufficient data: {len(ohlcv)} candles, need at least {min_candles}",
                field="ohlcv",
            )

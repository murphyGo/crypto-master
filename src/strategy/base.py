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
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from src.exceptions import StrategyError
from src.models import OHLCV, AnalysisResult
from src.utils.time import now_utc

# =============================================================================
# Exceptions
# =============================================================================

# ``StrategyError`` is defined in the neutral ``src.exceptions`` module
# (LAYER-F2) so the AI adapter can root ``ClaudeTimeoutError`` off it
# without importing the strategy domain. It is re-exported here so the
# canonical ``from src.strategy.base import StrategyError`` path — and
# every ``except StrategyError`` site — is unchanged.
__all__ = [
    "StrategyError",
    "StrategyValidationError",
    "StrategyDataInsufficient",
    "StrategyExecutionError",
    "StrategyLoadError",
    "TechniqueInfo",
    "BaseStrategy",
    "default_max_bars_held",
]


class StrategyValidationError(StrategyError):
    """Strategy validation failed.

    Raised when strategy input data or configuration is invalid. Two
    sub-meanings collide on this class historically — warmup / "not
    enough data yet" and structural strategy contract failures (bad
    placeholder, banned imports, malformed metadata). The backtest
    engine wants to skip the former and breaker-count the latter, so
    new code should raise :class:`StrategyDataInsufficient` for the
    warmup case and reserve this base class for structural failures.

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


class StrategyDataInsufficient(StrategyValidationError):
    """Strategy received OHLCV that is too short for warmup.

    Distinct subclass so the backtest engine can skip the bar without
    counting it toward the per-strategy parse-failure breaker
    (consistency-hardening CH-04). Other ``StrategyValidationError``
    subclasses — bad prompt placeholders, banned imports, malformed
    metadata — are structural contract failures and must reach the
    breaker so a broken candidate cannot quietly trade for thousands
    of bars and emerge with a "0-trade pass" verdict.
    """

    pass


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

    requires_multi_timeframe: bool = Field(
        default=False,
        description=(
            "When True, ``timeframes`` lists every timeframe the strategy "
            "consumes simultaneously (top-down analysis). The proposal "
            "engine fetches all of them and passes the dict via "
            "``ohlcv_by_timeframe``. When False (default), ``timeframes`` "
            "is just the list of compatible/recommended timeframes — the "
            "engine picks one and runs the strategy single-TF."
        ),
    )

    status: Literal["experimental", "active", "deprecated"] = Field(
        default="experimental",
        description="Technique lifecycle status",
    )

    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime | None = Field(default=None)
    changelog: str | None = Field(default=None, description="Version change notes")

    claude_timeout_seconds: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Phase 14.1: per-strategy override for the Claude CLI base "
            "timeout. When ``None`` (default), ``PromptStrategy`` falls "
            "back to ``Settings.claude_cli_timeout_seconds`` so existing "
            "strategies are unaffected. Useful for prompt-heavy "
            "strategies (e.g. multi-TF ICT/SMC analysis) that need a "
            "longer leash than baselines like ``rsi_4h``."
        ),
    )
    prompt_trigger: Literal[
        "none",
        "ict_smc_setup",
        "ict_smc_context",
        "trend_context",
    ] = Field(
        default="none",
        description=(
            "Optional pre-Claude market-condition filter for prompt strategies. "
            "'none' preserves historical behaviour. Context filters are broad "
            "gates that only reject clearly uninteresting market states; the "
            "prompt still makes the final long/short/neutral decision."
        ),
    )

    min_warmup_candles: int = Field(
        default=0,
        ge=0,
        description=(
            "Minimum candles this strategy needs before analysis should "
            "be called. BacktestConfig.warmup_candles remains the engine "
            "default; the backtester uses max(config.warmup_candles, "
            "strategy.minimum_candles). Strategies with dynamic tunables "
            "can override BaseStrategy.minimum_candles instead."
        ),
    )

    counter_trend: bool = Field(
        default=False,
        description=(
            "When True, this strategy fades the prevailing trend by design "
            "(mean-reversion class). Engine applies an HTF trend filter at "
            "the proposal gate: shorts are rejected when 1D close > SMA200, "
            "longs rejected when 1D close < SMA200. Trend-following and "
            "balanced LLM strategies leave this False."
        ),
    )

    max_bars_held: int | None = Field(
        default=None,
        ge=1,
        le=200,
        description=(
            "Optional time-stop: close the trade after this many candles "
            "of the strategy's primary timeframe. None falls back to a "
            "timeframe-based default (15m=48 bars=12h, 1h=48 bars=2d, "
            "4h=42 bars=7d, 1d=30 bars=30d). Hard ceiling 200 bars."
        ),
    )

    strategy_family: str | None = Field(
        default=None,
        description=(
            "Optional grouping key for sibling strategies (e.g. cadence "
            "variants of the same logic). When two strategies share a "
            "non-None strategy_family AND propose the same (symbol, "
            "signal-side) within the same cycle, the engine accepts only "
            "the first one and rejects the rest with reason "
            "'sibling_strategy_dedup'. Strategies with strategy_family=None "
            "are never deduped against any other strategy."
        ),
    )

    model_config = {"frozen": True}


# =============================================================================
# Time-stop helpers
# =============================================================================


# Per-timeframe default bar counts for the time-stop fallback. Picked
# so the wall-clock window scales with the strategy's natural cadence:
# fast intraday strategies get a short leash (a missed thesis decays
# in hours), slow swing strategies a longer one (multi-day theses can
# need a week to play out). Anything not in this map falls back to
# 48 bars — the same value 1h gets — and the absolute ceiling is 200
# bars per the ``TechniqueInfo.max_bars_held`` schema.
_DEFAULT_MAX_BARS_HELD: dict[str, int] = {
    "5m": 96,
    "15m": 48,
    "30m": 48,
    "1h": 48,
    "2h": 42,
    "4h": 42,
    "8h": 30,
    "12h": 30,
    "1d": 30,
    "1w": 12,
}

# Hard ceiling shared with the ``TechniqueInfo.max_bars_held`` ``le``
# constraint. Even if the table or a future override yields a larger
# value, the resolved default is clamped here so monitor never sits on
# a position past the documented ceiling.
_MAX_BARS_HELD_CEILING = 200


def default_max_bars_held(timeframe: str) -> int:
    """Default time-stop in bars for a primary timeframe.

    Args:
        timeframe: Primary timeframe label (e.g. ``"15m"``, ``"1h"``,
            ``"4h"``, ``"1d"``).

    Returns:
        The number of bars after which the runtime should force-close
        a trade that has neither hit its stop-loss nor its take-profit.
        Unknown timeframes return ``48`` (matches 1h/15m default), and
        the result is always clamped to the 200-bar ceiling that
        :class:`TechniqueInfo` enforces on explicit overrides.
    """
    bars = _DEFAULT_MAX_BARS_HELD.get(timeframe, 48)
    return min(bars, _MAX_BARS_HELD_CEILING)


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

    @property
    def minimum_candles(self) -> int:
        """Minimum OHLCV candles needed before analysis should run.

        The default comes from metadata so prompt/code strategies can
        declare static warmup needs without subclass code. Strategies
        whose warmup depends on constructor tunables should override
        this property.
        """
        return self._info.min_warmup_candles

    @abstractmethod
    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
        current_price: Decimal | None = None,
    ) -> AnalysisResult:
        """Analyze chart data and produce trading signal.

        This is the core method that all strategies must implement.
        It takes OHLCV candlestick data and returns an analysis result
        with trading signals.

        Args:
            ohlcv: List of OHLCV candlestick data, sorted by timestamp ascending.
                   Must contain at least the minimum required candles. For
                   multi-TF strategies this is the *primary* (smallest /
                   highest-resolution) timeframe.
            symbol: Trading pair symbol (e.g., "BTC/USDT").
            timeframe: Candle timeframe (e.g., "1h", "4h", "1d").
            ohlcv_by_timeframe: For strategies declaring
                ``requires_multi_timeframe=True``, the full ``{tf: [OHLCV]}``
                dict the engine fetched. Single-TF strategies ignore this
                kwarg.
            current_price: Latest spot price (typically the close of the
                primary timeframe's last candle). Provided for templates
                that reference the live price separately from the candle
                stream. Single-TF strategies ignore this kwarg.

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
            raise StrategyDataInsufficient("OHLCV data is empty", field="ohlcv")

        if len(ohlcv) < min_candles:
            raise StrategyDataInsufficient(
                f"Insufficient data: {len(ohlcv)} candles, need at least {min_candles}",
                field="ohlcv",
            )

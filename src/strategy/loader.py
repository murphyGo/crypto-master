"""Strategy loader for Crypto Master.

Loads analysis techniques from .md (prompt) and .py (code) files.

Related Requirements:
- FR-003: Chart Analysis Technique Definition
- FR-004: Analysis Technique Storage/Management
- NFR-005: Analysis Technique Storage
- NFR-010: Analysis Technique Extensibility
"""

import decimal
import importlib.util
import re
from decimal import Decimal
from pathlib import Path

import yaml

from src.models import OHLCV, AnalysisResult
from src.strategy.base import (
    BaseStrategy,
    StrategyExecutionError,
    StrategyLoadError,
    StrategyValidationError,
    TechniqueInfo,
)

# Default strategies directory
DEFAULT_STRATEGIES_DIR = Path("strategies")

# YAML frontmatter pattern for .md files
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# ``{identifier}`` style placeholder. Matches ``{ohlcv_4h}``,
# ``{current_price}``, etc. but NOT JSON-shaped ``{"foo": ...}``
# fragments inside example blocks.
_TEMPLATE_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class PromptStrategy(BaseStrategy):
    """Strategy implementation for prompt-based (.md) techniques.

    Wraps a markdown prompt template for use with Claude CLI.
    Actual Claude integration will be added in Phase 3.3.

    Attributes:
        prompt: The prompt template content.
    """

    def __init__(self, info: TechniqueInfo, prompt_content: str) -> None:
        """Initialize prompt strategy.

        Args:
            info: Technique metadata.
            prompt_content: The prompt template (markdown content after frontmatter).
        """
        super().__init__(info)
        self._prompt_content = prompt_content

    @property
    def prompt(self) -> str:
        """Get the prompt template.

        Returns:
            The markdown prompt content.
        """
        return self._prompt_content

    def format_prompt(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str,
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
        current_price: Decimal | None = None,
    ) -> str:
        """Format the prompt template with actual data.

        Substitutes placeholders in the prompt template with real values:

        Always:
        - ``{symbol}`` → trading pair symbol
        - ``{timeframe}`` → candle timeframe (the primary TF for multi-TF)
        - ``{ohlcv_data}`` → formatted primary-TF OHLCV data

        For multi-timeframe templates (when the kwargs are provided):
        - ``{ohlcv_<tf>}`` → per-TF OHLCV CSV for each key in
          ``ohlcv_by_timeframe`` (e.g. ``{ohlcv_4h}``, ``{ohlcv_15m}``)
        - ``{current_price}`` → ``current_price`` formatted as a plain
          (non-scientific) decimal string

        Uses simple string replacement to avoid conflicts with JSON
        braces in the template.

        Any remaining ``{identifier}`` placeholders after substitution
        are treated as a template / framework mismatch and raise
        :class:`StrategyValidationError`. Sending them through to
        Claude unfilled produces conversational responses rather than
        parseable JSON, which manifests downstream as a confusing
        ``Failed to parse JSON`` error far from the actual cause.

        Args:
            ohlcv: Primary-TF OHLCV candlestick data.
            symbol: Trading pair symbol.
            timeframe: Primary candle timeframe.
            ohlcv_by_timeframe: For multi-TF templates, the full
                ``{tf: [OHLCV]}`` dict. ``{ohlcv_<tf>}`` placeholders
                are filled from this. Optional.
            current_price: Latest spot price. Substitutes
                ``{current_price}``. Optional.

        Returns:
            Formatted prompt string ready for Claude.

        Raises:
            StrategyValidationError: If the template contains
                placeholders this method does not know how to fill
                (e.g. a multi-TF template with placeholders missing
                from ``ohlcv_by_timeframe``).
        """
        ohlcv_text = self._format_ohlcv_data(ohlcv)
        result = self._prompt_content
        result = result.replace("{symbol}", symbol)
        result = result.replace("{timeframe}", timeframe)
        result = result.replace("{ohlcv_data}", ohlcv_text)

        if ohlcv_by_timeframe:
            for tf, candles in ohlcv_by_timeframe.items():
                placeholder = "{ohlcv_" + tf + "}"
                result = result.replace(placeholder, self._format_ohlcv_data(candles))

        if current_price is not None:
            # ``f"{x:f}"`` forces fixed-point so very small / very large
            # decimals don't render in scientific notation, which is
            # confusing when the template asks Claude to compare against
            # a literal price.
            result = result.replace("{current_price}", f"{current_price:f}")

        # Any leftover ``{identifier}`` is a template hole the
        # framework didn't know how to fill. Match identifier-like
        # names only so JSON examples in the template (which contain
        # ``{`` immediately followed by ``"`` or whitespace) are not
        # flagged.
        unfilled = sorted(set(_TEMPLATE_PLACEHOLDER.findall(result)))
        if unfilled:
            placeholders = ", ".join(f"{{{name}}}" for name in unfilled)
            raise StrategyValidationError(
                f"Prompt template for '{self.info.name}' has unfilled "
                f"placeholders: {placeholders}. "
                "PromptStrategy.format_prompt fills {symbol}, {timeframe}, "
                "{ohlcv_data}, {ohlcv_<tf>} (per timeframe key in "
                "ohlcv_by_timeframe), and {current_price}; the template "
                "appears to expect data the engine did not provide.",
                field="prompt_content",
            )
        return result

    def _format_ohlcv_data(self, ohlcv: list[OHLCV], max_candles: int = 50) -> str:
        """Format OHLCV data as CSV text for Claude.

        Args:
            ohlcv: OHLCV candlestick data.
            max_candles: Maximum number of candles to include.

        Returns:
            CSV-formatted OHLCV data string.
        """
        lines = ["timestamp,open,high,low,close,volume"]
        for candle in ohlcv[-max_candles:]:
            lines.append(
                f"{candle.timestamp.isoformat()},"
                f"{candle.open},{candle.high},{candle.low},"
                f"{candle.close},{candle.volume}"
            )
        return "\n".join(lines)

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
        current_price: Decimal | None = None,
    ) -> AnalysisResult:
        """Analyze using Claude CLI with the prompt template.

        Args:
            ohlcv: Primary-TF OHLCV candlestick data.
            symbol: Trading pair symbol.
            timeframe: Primary candle timeframe.
            ohlcv_by_timeframe: For multi-TF templates, full per-TF dict.
            current_price: Latest spot price; fills ``{current_price}``.

        Returns:
            AnalysisResult from Claude analysis.

        Raises:
            StrategyValidationError: If input data is invalid.
            StrategyExecutionError: If Claude analysis fails.
        """
        from src.ai import ClaudeCLI, ClaudeError
        from src.ai.exceptions import ClaudeTimeoutError

        # Validate input
        self.validate_input(ohlcv)

        # Format the prompt with actual data
        prompt = self.format_prompt(
            ohlcv,
            symbol,
            timeframe,
            ohlcv_by_timeframe=ohlcv_by_timeframe,
            current_price=current_price,
        )

        # Execute Claude CLI. Phase 14.1: per-strategy timeout
        # override — when ``info.claude_timeout_seconds`` is set, pass
        # it to ``ClaudeCLI`` directly so prompt-heavy strategies
        # (e.g. multi-TF ICT/SMC analysis) get a longer leash without
        # forcing every other strategy onto the same global timeout.
        # ``None`` (default) lets ``ClaudeCLI`` resolve from
        # ``Settings.claude_cli_timeout_seconds`` as before.
        timeout_override = self.info.claude_timeout_seconds
        try:
            if timeout_override is not None:
                client = ClaudeCLI(timeout=float(timeout_override))
            else:
                client = ClaudeCLI()
            response = await client.analyze(prompt)
        except ClaudeTimeoutError:
            # Phase 12.3: ClaudeTimeoutError is a StrategyError, so it
            # propagates uncaught through the proposal engine's
            # existing ``except StrategyError`` clause as a clean
            # neutral-fallback. Wrapping it in StrategyExecutionError
            # would erase the type and prevent the engine from logging
            # an LLM_TIMEOUT activity event.
            raise
        except ClaudeError as e:
            raise StrategyExecutionError(
                f"Claude analysis failed: {e}",
                strategy_name=self.name,
            ) from e

        # Validate and convert response to AnalysisResult. Neutral
        # signals from chasulang_ict_smc-style templates carry None
        # for the price fields (no actionable setup). AnalysisResult's
        # entry_price/stop_loss/take_profit have gt=0 validators, so
        # we substitute a small placeholder when the price is None for
        # a neutral signal — the engine drops neutral analyses at
        # ProposalEngine._build_proposal_for_strategy before any
        # pricing logic touches them, so the placeholder is never used.
        try:
            signal = response["signal"]
            confidence = float(response["confidence"])
            entry_raw = response.get("entry_price")
            stop_raw = response.get("stop_loss")
            tp_raw = response.get("take_profit")
            placeholder = Decimal("0.00000001")
            entry_price = (
                placeholder
                if entry_raw is None and signal == "neutral"
                else Decimal(str(entry_raw))
            )
            stop_loss = (
                placeholder
                if stop_raw is None and signal == "neutral"
                else Decimal(str(stop_raw))
            )
            take_profit = (
                placeholder
                if tp_raw is None and signal == "neutral"
                else Decimal(str(tp_raw))
            )
            return AnalysisResult(
                signal=signal,
                confidence=confidence,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reasoning=response.get("reasoning", ""),
            )
        except (KeyError, ValueError, TypeError, decimal.InvalidOperation) as e:
            raise StrategyExecutionError(
                f"Invalid Claude response format: {e}. Response: {response}",
                strategy_name=self.name,
            ) from e


def load_technique_info_from_md(file_path: Path) -> tuple[TechniqueInfo, str]:
    """Load technique info and content from a markdown file.

    Parses YAML frontmatter from the markdown file to extract metadata,
    and returns the remaining content as the prompt template.

    Args:
        file_path: Path to the .md file.

    Returns:
        Tuple of (TechniqueInfo, prompt_content).

    Raises:
        StrategyLoadError: If file cannot be read or parsed.
        StrategyValidationError: If metadata is invalid.
    """
    if not file_path.exists():
        raise StrategyLoadError(f"File not found: {file_path}", str(file_path))

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise StrategyLoadError(f"Failed to read file: {e}", str(file_path)) from e

    # Extract YAML frontmatter
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        raise StrategyLoadError("Missing YAML frontmatter (---...---)", str(file_path))

    frontmatter_yaml = match.group(1)
    prompt_content = content[match.end() :].strip()

    try:
        metadata = yaml.safe_load(frontmatter_yaml)
    except yaml.YAMLError as e:
        raise StrategyLoadError(f"Invalid YAML frontmatter: {e}", str(file_path)) from e

    if not isinstance(metadata, dict):
        raise StrategyLoadError("Frontmatter must be a YAML mapping", str(file_path))

    # Ensure technique_type is prompt
    metadata["technique_type"] = "prompt"

    try:
        info = TechniqueInfo(**metadata)
    except Exception as e:
        raise StrategyValidationError(f"Invalid technique metadata: {e}") from e

    return info, prompt_content


def load_technique_info_from_py(
    file_path: Path,
) -> tuple[TechniqueInfo, type[BaseStrategy]]:
    """Load technique info and strategy class from a Python file.

    The Python file must define:
    - TECHNIQUE_INFO: dict with technique metadata
    - A class that inherits from BaseStrategy

    Args:
        file_path: Path to the .py file.

    Returns:
        Tuple of (TechniqueInfo, strategy_class).

    Raises:
        StrategyLoadError: If file cannot be loaded or is invalid.
        StrategyValidationError: If metadata is invalid.
    """
    if not file_path.exists():
        raise StrategyLoadError(f"File not found: {file_path}", str(file_path))

    # Load module dynamically
    module_name = file_path.stem
    spec = importlib.util.spec_from_file_location(module_name, file_path)

    if spec is None or spec.loader is None:
        raise StrategyLoadError(f"Cannot load module spec: {file_path}", str(file_path))

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise StrategyLoadError(f"Failed to execute module: {e}", str(file_path)) from e

    # Get TECHNIQUE_INFO
    if not hasattr(module, "TECHNIQUE_INFO"):
        raise StrategyLoadError("Module missing TECHNIQUE_INFO dict", str(file_path))

    info_dict = module.TECHNIQUE_INFO
    if not isinstance(info_dict, dict):
        raise StrategyLoadError("TECHNIQUE_INFO must be a dict", str(file_path))

    # Ensure technique_type is code
    info_dict = dict(info_dict)  # Make a copy to avoid modifying original
    info_dict["technique_type"] = "code"

    try:
        info = TechniqueInfo(**info_dict)
    except Exception as e:
        raise StrategyValidationError(f"Invalid TECHNIQUE_INFO: {e}") from e

    # Find strategy class
    strategy_class: type[BaseStrategy] | None = None
    for name in dir(module):
        obj = getattr(module, name)
        if (
            isinstance(obj, type)
            and issubclass(obj, BaseStrategy)
            and obj is not BaseStrategy
        ):
            strategy_class = obj
            break

    if strategy_class is None:
        raise StrategyLoadError(
            "No BaseStrategy subclass found in module", str(file_path)
        )

    return info, strategy_class


def load_strategy(file_path: Path) -> BaseStrategy:
    """Load a strategy from a file.

    Automatically detects file type (.md or .py) and loads accordingly.

    Args:
        file_path: Path to strategy file.

    Returns:
        Initialized BaseStrategy instance.

    Raises:
        StrategyLoadError: If file type is unsupported or loading fails.
    """
    suffix = file_path.suffix.lower()

    if suffix == ".md":
        info, prompt_content = load_technique_info_from_md(file_path)
        return PromptStrategy(info=info, prompt_content=prompt_content)

    elif suffix == ".py":
        info, strategy_class = load_technique_info_from_py(file_path)
        return strategy_class(info=info)

    else:
        raise StrategyLoadError(
            f"Unsupported file type: {suffix}. Use .md or .py",
            str(file_path),
        )


def discover_strategies(
    directory: Path = DEFAULT_STRATEGIES_DIR,
    include_subdirs: bool = True,
) -> list[Path]:
    """Discover all strategy files in a directory.

    Args:
        directory: Directory to search.
        include_subdirs: Whether to include subdirectories like experimental/.

    Returns:
        List of paths to strategy files (.md and .py).
    """
    if not directory.exists():
        return []

    strategies: list[Path] = []

    # Find .md and .py files in root
    for pattern in ["*.md", "*.py"]:
        strategies.extend(directory.glob(pattern))

    # Include subdirectories if requested
    if include_subdirs:
        for subdir in directory.iterdir():
            if subdir.is_dir() and not subdir.name.startswith("_"):
                for pattern in ["*.md", "*.py"]:
                    strategies.extend(subdir.glob(pattern))

    # Filter out private files, test files, and __init__.py
    strategies = [
        p
        for p in strategies
        if not p.name.startswith("_")
        and not p.name.startswith("test_")
        and p.name != "__init__.py"
    ]

    return sorted(strategies, key=lambda p: p.name)


def load_all_strategies(
    directory: Path = DEFAULT_STRATEGIES_DIR,
) -> dict[str, BaseStrategy]:
    """Load all strategies from a directory.

    Args:
        directory: Directory containing strategy files.

    Returns:
        Dict mapping strategy name to strategy instance.

    Note:
        Strategies that fail to load are logged but not included.
    """
    from src.logger import get_logger

    logger = get_logger("crypto_master.strategy")
    strategies: dict[str, BaseStrategy] = {}

    for file_path in discover_strategies(directory):
        try:
            strategy = load_strategy(file_path)
            if strategy.name in strategies:
                logger.warning(
                    f"Duplicate strategy name '{strategy.name}' from {file_path}, "
                    "skipping"
                )
                continue
            strategies[strategy.name] = strategy
            logger.info(f"Loaded strategy: {strategy.name} v{strategy.version}")
        except (StrategyLoadError, StrategyValidationError) as e:
            logger.error(f"Failed to load {file_path}: {e}")

    return strategies

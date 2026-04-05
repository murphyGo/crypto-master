"""Strategy loader for Crypto Master.

Loads analysis techniques from .md (prompt) and .py (code) files.

Related Requirements:
- FR-003: Chart Analysis Technique Definition
- FR-004: Analysis Technique Storage/Management
- NFR-005: Analysis Technique Storage
- NFR-010: Analysis Technique Extensibility
"""

import importlib.util
import re
from pathlib import Path

import yaml

from src.models import OHLCV, AnalysisResult
from src.strategy.base import (
    BaseStrategy,
    StrategyLoadError,
    StrategyValidationError,
    TechniqueInfo,
)

# Default strategies directory
DEFAULT_STRATEGIES_DIR = Path("strategies")

# YAML frontmatter pattern for .md files
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


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
    ) -> str:
        """Format the prompt template with actual data.

        Substitutes placeholders in the prompt template with real values:
        - {symbol} -> Trading pair symbol
        - {timeframe} -> Candle timeframe
        - {ohlcv_data} -> Formatted OHLCV data

        Uses simple string replacement to avoid conflicts with JSON
        braces in the template.

        Args:
            ohlcv: OHLCV candlestick data.
            symbol: Trading pair symbol.
            timeframe: Candle timeframe.

        Returns:
            Formatted prompt string ready for Claude.
        """
        ohlcv_text = self._format_ohlcv_data(ohlcv)
        result = self._prompt_content
        result = result.replace("{symbol}", symbol)
        result = result.replace("{timeframe}", timeframe)
        result = result.replace("{ohlcv_data}", ohlcv_text)
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
    ) -> AnalysisResult:
        """Analyze using Claude CLI with the prompt template.

        Note: Claude integration will be implemented in Phase 3.3.
        This method currently raises NotImplementedError.

        Args:
            ohlcv: OHLCV candlestick data.
            symbol: Trading pair symbol.
            timeframe: Candle timeframe.

        Returns:
            AnalysisResult from Claude analysis.

        Raises:
            NotImplementedError: Claude integration not yet implemented.
        """
        self.validate_input(ohlcv)
        raise NotImplementedError(
            "Claude integration not yet implemented. See Phase 3.3."
        )


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
        raise StrategyLoadError(f"Failed to read file: {e}", str(file_path))

    # Extract YAML frontmatter
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        raise StrategyLoadError(
            "Missing YAML frontmatter (---...---)", str(file_path)
        )

    frontmatter_yaml = match.group(1)
    prompt_content = content[match.end() :].strip()

    try:
        metadata = yaml.safe_load(frontmatter_yaml)
    except yaml.YAMLError as e:
        raise StrategyLoadError(f"Invalid YAML frontmatter: {e}", str(file_path))

    if not isinstance(metadata, dict):
        raise StrategyLoadError("Frontmatter must be a YAML mapping", str(file_path))

    # Ensure technique_type is prompt
    metadata["technique_type"] = "prompt"

    try:
        info = TechniqueInfo(**metadata)
    except Exception as e:
        raise StrategyValidationError(f"Invalid technique metadata: {e}")

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
        raise StrategyLoadError(f"Failed to execute module: {e}", str(file_path))

    # Get TECHNIQUE_INFO
    if not hasattr(module, "TECHNIQUE_INFO"):
        raise StrategyLoadError("Module missing TECHNIQUE_INFO dict", str(file_path))

    info_dict = getattr(module, "TECHNIQUE_INFO")
    if not isinstance(info_dict, dict):
        raise StrategyLoadError("TECHNIQUE_INFO must be a dict", str(file_path))

    # Ensure technique_type is code
    info_dict = dict(info_dict)  # Make a copy to avoid modifying original
    info_dict["technique_type"] = "code"

    try:
        info = TechniqueInfo(**info_dict)
    except Exception as e:
        raise StrategyValidationError(f"Invalid TECHNIQUE_INFO: {e}")

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

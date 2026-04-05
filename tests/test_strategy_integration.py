"""Integration tests for strategy loading and execution.

Tests the full workflow of loading strategies from the strategies/ directory
and executing them with real OHLCV data.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.models import OHLCV, AnalysisResult
from src.strategy import (
    PromptStrategy,
    StrategyExecutionError,
    StrategyValidationError,
    clear_strategy_cache,
    get_available_strategies,
    get_strategy,
    load_strategies_from_directory,
    load_strategy,
)
from src.strategy.loader import DEFAULT_STRATEGIES_DIR


@pytest.fixture(autouse=True)
def clean_cache() -> None:
    """Clear strategy cache before each test."""
    clear_strategy_cache()


@pytest.fixture
def strategies_dir() -> Path:
    """Get the real strategies directory."""
    return DEFAULT_STRATEGIES_DIR


@pytest.fixture
def sample_ohlcv_neutral() -> list[OHLCV]:
    """Create OHLCV data that should produce neutral signal (no crossover)."""
    base_time = datetime.now() - timedelta(hours=30)
    candles = []
    # Stable prices around 100 - no crossover expected
    for i in range(30):
        price = Decimal("100") + Decimal(str(i % 3 - 1))  # Fluctuate: 99, 100, 101
        candles.append(
            OHLCV(
                timestamp=base_time + timedelta(hours=i),
                open=price,
                high=price + Decimal("1"),
                low=price - Decimal("1"),
                close=price,
                volume=Decimal("1000"),
            )
        )
    return candles


@pytest.fixture
def sample_ohlcv_bullish() -> list[OHLCV]:
    """Create OHLCV data that should produce bullish crossover signal."""
    base_time = datetime.now() - timedelta(hours=30)
    candles = []
    # First 20 candles: downtrend (long MA will be higher)
    for i in range(20):
        price = Decimal("110") - Decimal(str(i))  # 110, 109, 108, ... 91
        candles.append(
            OHLCV(
                timestamp=base_time + timedelta(hours=i),
                open=price,
                high=price + Decimal("1"),
                low=price - Decimal("1"),
                close=price,
                volume=Decimal("1000"),
            )
        )
    # Last 10 candles: sharp upturn (short MA crosses above long MA)
    for i in range(10):
        price = Decimal("92") + Decimal(str(i * 3))  # 92, 95, 98, 101, ...
        candles.append(
            OHLCV(
                timestamp=base_time + timedelta(hours=20 + i),
                open=price - Decimal("1"),
                high=price + Decimal("2"),
                low=price - Decimal("2"),
                close=price,
                volume=Decimal("1500"),
            )
        )
    return candles


@pytest.fixture
def sample_ohlcv_bearish() -> list[OHLCV]:
    """Create OHLCV data that should produce bearish crossover signal."""
    base_time = datetime.now() - timedelta(hours=30)
    candles = []
    # First 20 candles: uptrend (long MA will be lower)
    for i in range(20):
        price = Decimal("90") + Decimal(str(i))  # 90, 91, 92, ... 109
        candles.append(
            OHLCV(
                timestamp=base_time + timedelta(hours=i),
                open=price,
                high=price + Decimal("1"),
                low=price - Decimal("1"),
                close=price,
                volume=Decimal("1000"),
            )
        )
    # Last 10 candles: sharp downturn (short MA crosses below long MA)
    for i in range(10):
        price = Decimal("108") - Decimal(str(i * 3))  # 108, 105, 102, 99, ...
        candles.append(
            OHLCV(
                timestamp=base_time + timedelta(hours=20 + i),
                open=price + Decimal("1"),
                high=price + Decimal("2"),
                low=price - Decimal("2"),
                close=price,
                volume=Decimal("1500"),
            )
        )
    return candles


class TestLoadRealStrategies:
    """Tests for loading strategies from the real strategies/ directory."""

    def test_strategies_directory_exists(self, strategies_dir: Path) -> None:
        """Test that strategies directory exists."""
        assert strategies_dir.exists(), f"Strategies directory not found: {strategies_dir}"

    def test_load_sample_code_strategy(self, strategies_dir: Path) -> None:
        """Test loading the sample code strategy."""
        strategy_path = strategies_dir / "sample_code.py"
        assert strategy_path.exists(), "sample_code.py not found"

        strategy = load_strategy(strategy_path)

        assert strategy.name == "ma_crossover"
        assert strategy.version == "1.0.0"
        assert strategy.info.technique_type == "code"

    def test_load_sample_prompt_strategy(self, strategies_dir: Path) -> None:
        """Test loading the sample prompt strategy."""
        strategy_path = strategies_dir / "sample_prompt.md"
        assert strategy_path.exists(), "sample_prompt.md not found"

        strategy = load_strategy(strategy_path)

        assert strategy.name == "simple_trend_analysis"
        assert strategy.version == "1.0.0"
        assert strategy.info.technique_type == "prompt"
        assert isinstance(strategy, PromptStrategy)

    def test_load_all_strategies(self, strategies_dir: Path) -> None:
        """Test loading all strategies from directory."""
        load_strategies_from_directory(strategies_dir, force_reload=True)
        available = get_available_strategies()

        assert "ma_crossover" in available
        assert "simple_trend_analysis" in available

    def test_get_strategy_by_name(self, strategies_dir: Path) -> None:
        """Test getting a strategy by name."""
        load_strategies_from_directory(strategies_dir, force_reload=True)

        strategy = get_strategy("ma_crossover")

        assert strategy.name == "ma_crossover"

    def test_get_strategy_case_insensitive(self, strategies_dir: Path) -> None:
        """Test getting strategy with different case."""
        load_strategies_from_directory(strategies_dir, force_reload=True)

        strategy = get_strategy("MA_CROSSOVER")

        assert strategy.name == "ma_crossover"


class TestMACrossoverExecution:
    """Tests for MACrossoverStrategy execution."""

    @pytest.fixture
    def ma_strategy(self, strategies_dir: Path):
        """Load the MA crossover strategy."""
        return load_strategy(strategies_dir / "sample_code.py")

    @pytest.mark.asyncio
    async def test_analyze_returns_analysis_result(
        self, ma_strategy, sample_ohlcv_neutral: list[OHLCV]
    ) -> None:
        """Test analyze returns proper AnalysisResult."""
        result = await ma_strategy.analyze(sample_ohlcv_neutral, "BTC/USDT", "1h")

        assert isinstance(result, AnalysisResult)
        assert result.signal in ["long", "short", "neutral"]
        assert 0.0 <= result.confidence <= 1.0
        assert result.entry_price > 0
        assert result.stop_loss > 0
        assert result.take_profit > 0
        assert result.reasoning is not None

    @pytest.mark.asyncio
    async def test_neutral_signal(
        self, ma_strategy, sample_ohlcv_neutral: list[OHLCV]
    ) -> None:
        """Test neutral signal when no crossover."""
        result = await ma_strategy.analyze(sample_ohlcv_neutral, "BTC/USDT", "1h")

        assert result.signal == "neutral"
        assert result.confidence < 0.5

    @pytest.mark.asyncio
    async def test_bullish_trend_analysis(
        self, ma_strategy, sample_ohlcv_bullish: list[OHLCV]
    ) -> None:
        """Test analysis on bullish trending data."""
        result = await ma_strategy.analyze(sample_ohlcv_bullish, "BTC/USDT", "1h")

        # Strategy should produce valid result for trending data
        assert result.signal in ["long", "short", "neutral"]
        assert isinstance(result, AnalysisResult)
        # For long signals, take_profit should be above entry
        if result.signal == "long":
            assert result.take_profit > result.entry_price

    @pytest.mark.asyncio
    async def test_bearish_trend_analysis(
        self, ma_strategy, sample_ohlcv_bearish: list[OHLCV]
    ) -> None:
        """Test analysis on bearish trending data."""
        result = await ma_strategy.analyze(sample_ohlcv_bearish, "BTC/USDT", "1h")

        # Strategy should produce valid result for trending data
        assert result.signal in ["long", "short", "neutral"]
        assert isinstance(result, AnalysisResult)
        # For short signals, take_profit should be below entry
        if result.signal == "short":
            assert result.take_profit < result.entry_price

    @pytest.mark.asyncio
    async def test_insufficient_data_raises_error(self, ma_strategy) -> None:
        """Test that insufficient data raises StrategyValidationError."""
        short_ohlcv = [
            OHLCV(
                timestamp=datetime.now(),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("1000"),
            )
            for _ in range(10)  # Less than required 21 candles
        ]

        with pytest.raises(StrategyValidationError) as exc_info:
            await ma_strategy.analyze(short_ohlcv, "BTC/USDT", "1h")

        assert "insufficient" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_result_has_valid_prices(
        self, ma_strategy, sample_ohlcv_neutral: list[OHLCV]
    ) -> None:
        """Test that result prices are reasonable."""
        result = await ma_strategy.analyze(sample_ohlcv_neutral, "BTC/USDT", "1h")

        last_close = sample_ohlcv_neutral[-1].close

        # Entry should be close to current price
        assert abs(result.entry_price - last_close) < last_close * Decimal("0.1")

        # Stop loss and take profit should be within reasonable range
        assert result.stop_loss < result.entry_price * Decimal("1.5")
        assert result.take_profit < result.entry_price * Decimal("2.0")

    @pytest.mark.asyncio
    async def test_reasoning_includes_ma_values(
        self, ma_strategy, sample_ohlcv_neutral: list[OHLCV]
    ) -> None:
        """Test that reasoning includes MA values."""
        result = await ma_strategy.analyze(sample_ohlcv_neutral, "BTC/USDT", "1h")

        assert "MA(" in result.reasoning


class TestPromptStrategyFormatting:
    """Tests for PromptStrategy prompt formatting."""

    @pytest.fixture
    def prompt_strategy(self, strategies_dir: Path) -> PromptStrategy:
        """Load the prompt strategy."""
        strategy = load_strategy(strategies_dir / "sample_prompt.md")
        assert isinstance(strategy, PromptStrategy)
        return strategy

    @pytest.fixture
    def sample_ohlcv(self) -> list[OHLCV]:
        """Create sample OHLCV data."""
        return [
            OHLCV(
                timestamp=datetime(2024, 1, 1, i),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100.5"),
                volume=Decimal("1000"),
            )
            for i in range(10)
        ]

    def test_format_prompt_includes_symbol(
        self, prompt_strategy: PromptStrategy, sample_ohlcv: list[OHLCV]
    ) -> None:
        """Test that formatted prompt includes symbol."""
        formatted = prompt_strategy.format_prompt(sample_ohlcv, "BTC/USDT", "4h")

        assert "BTC/USDT" in formatted

    def test_format_prompt_includes_timeframe(
        self, prompt_strategy: PromptStrategy, sample_ohlcv: list[OHLCV]
    ) -> None:
        """Test that formatted prompt includes timeframe."""
        formatted = prompt_strategy.format_prompt(sample_ohlcv, "BTC/USDT", "4h")

        assert "4h" in formatted

    def test_format_prompt_includes_ohlcv_data(
        self, prompt_strategy: PromptStrategy, sample_ohlcv: list[OHLCV]
    ) -> None:
        """Test that formatted prompt includes OHLCV data."""
        formatted = prompt_strategy.format_prompt(sample_ohlcv, "BTC/USDT", "4h")

        # Should have CSV header
        assert "timestamp,open,high,low,close,volume" in formatted
        # Should have data rows
        assert "100" in formatted
        assert "100.5" in formatted

    def test_format_ohlcv_limits_to_50_candles(
        self, prompt_strategy: PromptStrategy
    ) -> None:
        """Test that OHLCV data is limited to 50 candles."""
        # Create 100 candles
        ohlcv = [
            OHLCV(
                timestamp=datetime(2024, 1, 1, i % 24),
                open=Decimal(str(100 + i)),
                high=Decimal(str(101 + i)),
                low=Decimal(str(99 + i)),
                close=Decimal(str(100 + i)),
                volume=Decimal("1000"),
            )
            for i in range(100)
        ]

        formatted = prompt_strategy._format_ohlcv_data(ohlcv)
        lines = formatted.strip().split("\n")

        # 1 header + 50 data lines
        assert len(lines) == 51

    def test_format_ohlcv_uses_last_candles(
        self, prompt_strategy: PromptStrategy
    ) -> None:
        """Test that _format_ohlcv_data uses the last N candles."""
        ohlcv = [
            OHLCV(
                timestamp=datetime(2024, 1, 1, i % 24),
                open=Decimal(str(i)),  # Use index as price for easy verification
                high=Decimal(str(i + 1)),
                low=Decimal(str(i - 1)),
                close=Decimal(str(i)),
                volume=Decimal("1000"),
            )
            for i in range(100)
        ]

        formatted = prompt_strategy._format_ohlcv_data(ohlcv, max_candles=10)
        lines = formatted.strip().split("\n")

        # Last line should contain price 99 (index 99)
        assert "99" in lines[-1]
        # First data line should contain price 90 (index 90)
        assert "90" in lines[1]

    def test_prompt_property_returns_raw_template(
        self, prompt_strategy: PromptStrategy
    ) -> None:
        """Test that prompt property returns raw template."""
        template = prompt_strategy.prompt

        assert "{symbol}" in template
        assert "{timeframe}" in template
        assert "{ohlcv_data}" in template

    @pytest.mark.asyncio
    async def test_analyze_calls_claude_cli(
        self, prompt_strategy: PromptStrategy, sample_ohlcv: list[OHLCV]
    ) -> None:
        """Test that analyze calls Claude CLI and returns AnalysisResult."""
        from unittest.mock import AsyncMock, patch

        # Need at least 20 candles
        ohlcv = sample_ohlcv * 3  # 30 candles

        mock_response = {
            "signal": "long",
            "confidence": 0.85,
            "entry_price": 100.5,
            "stop_loss": 98.0,
            "take_profit": 105.0,
            "reasoning": "Strong uptrend detected",
        }

        mock_client = AsyncMock()
        mock_client.analyze.return_value = mock_response

        with patch("src.ai.ClaudeCLI", return_value=mock_client):
            result = await prompt_strategy.analyze(ohlcv, "BTC/USDT", "4h")

        assert isinstance(result, AnalysisResult)
        assert result.signal == "long"
        assert result.confidence == 0.85
        assert result.reasoning == "Strong uptrend detected"

    @pytest.mark.asyncio
    async def test_analyze_raises_strategy_error_on_claude_failure(
        self, prompt_strategy: PromptStrategy, sample_ohlcv: list[OHLCV]
    ) -> None:
        """Test that analyze raises StrategyExecutionError when Claude fails."""
        from unittest.mock import AsyncMock, patch

        from src.ai.exceptions import ClaudeTimeoutError

        # Need at least 20 candles
        ohlcv = sample_ohlcv * 3  # 30 candles

        mock_client = AsyncMock()
        mock_client.analyze.side_effect = ClaudeTimeoutError(
            "Timeout", timeout_seconds=120.0
        )

        with patch("src.ai.ClaudeCLI", return_value=mock_client):
            with pytest.raises(StrategyExecutionError) as exc_info:
                await prompt_strategy.analyze(ohlcv, "BTC/USDT", "4h")

            assert "Claude analysis failed" in str(exc_info.value)

"""Tests for the strategy base classes and exceptions."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.models import OHLCV, AnalysisResult
from src.strategy.base import (
    BaseStrategy,
    StrategyError,
    StrategyExecutionError,
    StrategyLoadError,
    StrategyValidationError,
    TechniqueInfo,
)


class TestStrategyErrors:
    """Tests for strategy exception classes."""

    def test_strategy_error_is_exception(self) -> None:
        """Test StrategyError is a proper exception."""
        error = StrategyError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_strategy_validation_error_inherits(self) -> None:
        """Test StrategyValidationError inherits from StrategyError."""
        error = StrategyValidationError("Invalid", field="name")
        assert isinstance(error, StrategyError)
        assert error.field == "name"

    def test_strategy_validation_error_field_is_optional(self) -> None:
        """Test StrategyValidationError field is optional."""
        error = StrategyValidationError("Invalid")
        assert error.field is None

    def test_strategy_execution_error_inherits(self) -> None:
        """Test StrategyExecutionError inherits from StrategyError."""
        error = StrategyExecutionError("Failed", strategy_name="test")
        assert isinstance(error, StrategyError)
        assert error.strategy_name == "test"

    def test_strategy_execution_error_strategy_name_is_optional(self) -> None:
        """Test StrategyExecutionError strategy_name is optional."""
        error = StrategyExecutionError("Failed")
        assert error.strategy_name is None

    def test_strategy_load_error_inherits(self) -> None:
        """Test StrategyLoadError inherits from StrategyError."""
        error = StrategyLoadError("Not found", file_path="/path/to/file")
        assert isinstance(error, StrategyError)
        assert error.file_path == "/path/to/file"

    def test_strategy_load_error_file_path_is_optional(self) -> None:
        """Test StrategyLoadError file_path is optional."""
        error = StrategyLoadError("Not found")
        assert error.file_path is None


class TestTechniqueInfo:
    """Tests for TechniqueInfo model."""

    def test_create_technique_info(self) -> None:
        """Test creating a valid TechniqueInfo."""
        info = TechniqueInfo(
            name="test_strategy",
            version="1.0.0",
            description="A test strategy",
            technique_type="code",
        )
        assert info.name == "test_strategy"
        assert info.version == "1.0.0"
        assert info.technique_type == "code"

    def test_technique_info_defaults(self) -> None:
        """Test TechniqueInfo default values."""
        info = TechniqueInfo(
            name="test",
            version="1.0.0",
            description="Test",
            technique_type="prompt",
        )
        assert info.author == "system"
        assert info.status == "experimental"
        assert info.symbols == ["BTC/USDT"]
        assert info.timeframes == ["1h", "4h", "1d"]
        assert info.updated_at is None
        assert info.changelog is None

    def test_technique_info_is_frozen(self) -> None:
        """Test TechniqueInfo is immutable."""
        info = TechniqueInfo(
            name="test",
            version="1.0.0",
            description="Test",
            technique_type="code",
        )
        with pytest.raises(ValidationError):
            info.name = "changed"

    def test_version_format_validation(self) -> None:
        """Test version must be semantic version format."""
        with pytest.raises(ValidationError):
            TechniqueInfo(
                name="test",
                version="invalid",
                description="Test",
                technique_type="code",
            )

    def test_version_format_valid(self) -> None:
        """Test valid semantic version formats."""
        info = TechniqueInfo(
            name="test",
            version="2.10.123",
            description="Test",
            technique_type="code",
        )
        assert info.version == "2.10.123"

    def test_technique_type_validation(self) -> None:
        """Test technique_type must be prompt or code."""
        with pytest.raises(ValidationError):
            TechniqueInfo(
                name="test",
                version="1.0.0",
                description="Test",
                technique_type="invalid",  # type: ignore[arg-type]
            )

    def test_status_validation(self) -> None:
        """Test status must be valid value."""
        with pytest.raises(ValidationError):
            TechniqueInfo(
                name="test",
                version="1.0.0",
                description="Test",
                technique_type="code",
                status="invalid",  # type: ignore[arg-type]
            )

    def test_name_cannot_be_empty(self) -> None:
        """Test name must have at least one character."""
        with pytest.raises(ValidationError):
            TechniqueInfo(
                name="",
                version="1.0.0",
                description="Test",
                technique_type="code",
            )

    def test_created_at_defaults_to_now(self) -> None:
        """Test created_at defaults to current time."""
        before = datetime.now()
        info = TechniqueInfo(
            name="test",
            version="1.0.0",
            description="Test",
            technique_type="code",
        )
        after = datetime.now()
        assert before <= info.created_at <= after


class TestBaseStrategyAbstract:
    """Tests for BaseStrategy abstract class."""

    def test_cannot_instantiate_directly(self) -> None:
        """Test abstract class cannot be instantiated."""
        info = TechniqueInfo(
            name="test",
            version="1.0.0",
            description="Test",
            technique_type="code",
        )
        with pytest.raises(TypeError) as exc_info:
            BaseStrategy(info=info)  # type: ignore[abstract]
        assert "abstract" in str(exc_info.value).lower()

    def test_must_implement_analyze(self) -> None:
        """Test subclass must implement analyze method."""

        class IncompleteStrategy(BaseStrategy):
            pass

        info = TechniqueInfo(
            name="test",
            version="1.0.0",
            description="Test",
            technique_type="code",
        )
        with pytest.raises(TypeError):
            IncompleteStrategy(info=info)  # type: ignore[abstract]


# Mock implementation for testing
class MockStrategy(BaseStrategy):
    """Mock strategy for testing."""

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
    ) -> AnalysisResult:
        """Mock analyze method."""
        self.validate_input(ohlcv)
        return AnalysisResult(
            signal="neutral",
            confidence=0.5,
            entry_price=ohlcv[-1].close,
            stop_loss=ohlcv[-1].close * Decimal("0.98"),
            take_profit=ohlcv[-1].close * Decimal("1.02"),
            reasoning="Mock analysis",
        )


class TestBaseStrategyImplementation:
    """Tests for BaseStrategy with concrete implementation."""

    @pytest.fixture
    def technique_info(self) -> TechniqueInfo:
        """Create test technique info."""
        return TechniqueInfo(
            name="mock_strategy",
            version="1.0.0",
            description="Mock strategy for testing",
            technique_type="code",
        )

    @pytest.fixture
    def mock_strategy(self, technique_info: TechniqueInfo) -> MockStrategy:
        """Create mock strategy instance."""
        return MockStrategy(info=technique_info)

    @pytest.fixture
    def sample_ohlcv(self) -> list[OHLCV]:
        """Create sample OHLCV data."""
        return [
            OHLCV(
                timestamp=datetime.now(),
                open=Decimal("100"),
                high=Decimal("105"),
                low=Decimal("95"),
                close=Decimal("102"),
                volume=Decimal("1000"),
            )
            for _ in range(25)
        ]

    def test_strategy_name_property(self, mock_strategy: MockStrategy) -> None:
        """Test name property returns technique name."""
        assert mock_strategy.name == "mock_strategy"

    def test_strategy_version_property(self, mock_strategy: MockStrategy) -> None:
        """Test version property returns technique version."""
        assert mock_strategy.version == "1.0.0"

    def test_strategy_info_property(
        self, mock_strategy: MockStrategy, technique_info: TechniqueInfo
    ) -> None:
        """Test info property returns full technique info."""
        assert mock_strategy.info == technique_info

    @pytest.mark.asyncio
    async def test_analyze_returns_analysis_result(
        self, mock_strategy: MockStrategy, sample_ohlcv: list[OHLCV]
    ) -> None:
        """Test analyze returns AnalysisResult."""
        result = await mock_strategy.analyze(sample_ohlcv, "BTC/USDT")
        assert isinstance(result, AnalysisResult)
        assert result.signal == "neutral"
        assert result.confidence == 0.5

    def test_validate_input_empty_ohlcv(self, mock_strategy: MockStrategy) -> None:
        """Test validate_input raises on empty data."""
        with pytest.raises(StrategyValidationError) as exc_info:
            mock_strategy.validate_input([])
        assert "empty" in str(exc_info.value).lower()
        assert exc_info.value.field == "ohlcv"

    def test_validate_input_insufficient_data(
        self, mock_strategy: MockStrategy
    ) -> None:
        """Test validate_input raises on insufficient data."""
        ohlcv = [
            OHLCV(
                timestamp=datetime.now(),
                open=Decimal("100"),
                high=Decimal("105"),
                low=Decimal("95"),
                close=Decimal("102"),
                volume=Decimal("1000"),
            )
            for _ in range(5)
        ]
        with pytest.raises(StrategyValidationError) as exc_info:
            mock_strategy.validate_input(ohlcv, min_candles=20)
        assert "insufficient" in str(exc_info.value).lower()
        assert exc_info.value.field == "ohlcv"

    def test_validate_input_custom_min_candles(
        self, mock_strategy: MockStrategy
    ) -> None:
        """Test validate_input with custom min_candles."""
        ohlcv = [
            OHLCV(
                timestamp=datetime.now(),
                open=Decimal("100"),
                high=Decimal("105"),
                low=Decimal("95"),
                close=Decimal("102"),
                volume=Decimal("1000"),
            )
            for _ in range(10)
        ]
        # Should not raise with min_candles=10
        mock_strategy.validate_input(ohlcv, min_candles=10)

    def test_validate_input_passes_with_enough_data(
        self, mock_strategy: MockStrategy, sample_ohlcv: list[OHLCV]
    ) -> None:
        """Test validate_input passes with sufficient data."""
        # Should not raise
        mock_strategy.validate_input(sample_ohlcv, min_candles=20)

"""Tests for the strategy loader module."""

from pathlib import Path
from textwrap import dedent

import pytest

from src.strategy.base import (
    BaseStrategy,
    StrategyLoadError,
    StrategyValidationError,
    TechniqueInfo,
)
from src.strategy.loader import (
    PromptStrategy,
    discover_strategies,
    load_all_strategies,
    load_strategy,
    load_technique_info_from_md,
    load_technique_info_from_py,
)


class TestPromptStrategy:
    """Tests for PromptStrategy class."""

    @pytest.fixture
    def technique_info(self) -> TechniqueInfo:
        """Create test technique info."""
        return TechniqueInfo(
            name="test_prompt",
            version="1.0.0",
            description="Test prompt strategy",
            technique_type="prompt",
        )

    def test_prompt_strategy_stores_content(
        self, technique_info: TechniqueInfo
    ) -> None:
        """Test PromptStrategy stores prompt content."""
        strategy = PromptStrategy(info=technique_info, prompt_content="Test prompt")
        assert strategy.prompt == "Test prompt"

    def test_prompt_strategy_inherits_base(
        self, technique_info: TechniqueInfo
    ) -> None:
        """Test PromptStrategy inherits from BaseStrategy."""
        strategy = PromptStrategy(info=technique_info, prompt_content="Test")
        assert isinstance(strategy, BaseStrategy)
        assert strategy.name == "test_prompt"

    @pytest.mark.asyncio
    async def test_prompt_strategy_analyze_calls_claude(
        self, technique_info: TechniqueInfo
    ) -> None:
        """Test analyze calls Claude CLI and returns AnalysisResult."""
        from datetime import datetime
        from decimal import Decimal
        from unittest.mock import AsyncMock, patch

        from src.models import OHLCV, AnalysisResult

        strategy = PromptStrategy(
            info=technique_info,
            prompt_content="Analyze {symbol} on {timeframe}: {ohlcv_data}",
        )
        ohlcv = [
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

        mock_response = {
            "signal": "long",
            "confidence": 0.8,
            "entry_price": 102,
            "stop_loss": 95,
            "take_profit": 110,
            "reasoning": "Test reasoning",
        }
        mock_client = AsyncMock()
        mock_client.analyze.return_value = mock_response

        with patch("src.ai.ClaudeCLI", return_value=mock_client):
            result = await strategy.analyze(ohlcv, "BTC/USDT")

        assert isinstance(result, AnalysisResult)
        assert result.signal == "long"
        assert result.confidence == 0.8


class TestLoadTechniqueInfoFromMd:
    """Tests for loading .md technique files."""

    def test_load_valid_md_file(self, tmp_path: Path) -> None:
        """Test loading a valid markdown file."""
        md_content = dedent("""
            ---
            name: test_prompt
            version: 1.0.0
            description: Test prompt strategy
            symbols: ["BTC/USDT"]
            ---

            # Analysis Prompt

            Analyze this data...
        """).strip()

        md_file = tmp_path / "test.md"
        md_file.write_text(md_content)

        info, content = load_technique_info_from_md(md_file)

        assert info.name == "test_prompt"
        assert info.version == "1.0.0"
        assert info.technique_type == "prompt"
        assert "Analyze this data" in content

    def test_load_md_file_not_found(self, tmp_path: Path) -> None:
        """Test loading non-existent file raises error."""
        with pytest.raises(StrategyLoadError) as exc_info:
            load_technique_info_from_md(tmp_path / "nonexistent.md")
        assert "not found" in str(exc_info.value).lower()
        assert exc_info.value.file_path is not None

    def test_load_md_missing_frontmatter(self, tmp_path: Path) -> None:
        """Test loading file without frontmatter raises error."""
        md_file = tmp_path / "no_frontmatter.md"
        md_file.write_text("# Just content\nNo frontmatter here")

        with pytest.raises(StrategyLoadError) as exc_info:
            load_technique_info_from_md(md_file)
        assert "frontmatter" in str(exc_info.value).lower()

    def test_load_md_invalid_yaml(self, tmp_path: Path) -> None:
        """Test loading file with invalid YAML raises error."""
        md_content = dedent("""
            ---
            name: [invalid yaml
            ---

            Content
        """).strip()

        md_file = tmp_path / "invalid.md"
        md_file.write_text(md_content)

        with pytest.raises(StrategyLoadError) as exc_info:
            load_technique_info_from_md(md_file)
        assert "yaml" in str(exc_info.value).lower()

    def test_load_md_invalid_metadata(self, tmp_path: Path) -> None:
        """Test loading file with invalid metadata raises error."""
        md_content = dedent("""
            ---
            name: test
            version: invalid_version
            description: Test
            ---

            Content
        """).strip()

        md_file = tmp_path / "invalid_meta.md"
        md_file.write_text(md_content)

        with pytest.raises(StrategyValidationError):
            load_technique_info_from_md(md_file)

    def test_load_md_frontmatter_not_dict(self, tmp_path: Path) -> None:
        """Test loading file with non-dict frontmatter raises error."""
        md_content = dedent("""
            ---
            - list item
            - another item
            ---

            Content
        """).strip()

        md_file = tmp_path / "list_frontmatter.md"
        md_file.write_text(md_content)

        with pytest.raises(StrategyLoadError) as exc_info:
            load_technique_info_from_md(md_file)
        assert "mapping" in str(exc_info.value).lower()


class TestLoadTechniqueInfoFromPy:
    """Tests for loading .py technique files."""

    def test_load_valid_py_file(self, tmp_path: Path) -> None:
        """Test loading a valid Python file."""
        py_content = dedent("""
            from src.strategy.base import BaseStrategy, TechniqueInfo
            from src.models import OHLCV, AnalysisResult
            from decimal import Decimal
            from datetime import datetime

            TECHNIQUE_INFO = {
                "name": "test_code",
                "version": "1.0.0",
                "description": "Test code strategy",
            }

            class TestCodeStrategy(BaseStrategy):
                async def analyze(self, ohlcv, symbol, timeframe="1h"):
                    return AnalysisResult(
                        signal="neutral",
                        confidence=0.5,
                        entry_price=Decimal("100"),
                        stop_loss=Decimal("98"),
                        take_profit=Decimal("102"),
                        reasoning="Test",
                    )
        """)

        py_file = tmp_path / "test_code.py"
        py_file.write_text(py_content)

        info, strategy_class = load_technique_info_from_py(py_file)

        assert info.name == "test_code"
        assert info.technique_type == "code"
        assert issubclass(strategy_class, BaseStrategy)

    def test_load_py_file_not_found(self, tmp_path: Path) -> None:
        """Test loading non-existent file raises error."""
        with pytest.raises(StrategyLoadError) as exc_info:
            load_technique_info_from_py(tmp_path / "nonexistent.py")
        assert "not found" in str(exc_info.value).lower()

    def test_load_py_missing_technique_info(self, tmp_path: Path) -> None:
        """Test loading file without TECHNIQUE_INFO raises error."""
        py_content = dedent("""
            # No TECHNIQUE_INFO defined
            pass
        """)

        py_file = tmp_path / "missing_info.py"
        py_file.write_text(py_content)

        with pytest.raises(StrategyLoadError) as exc_info:
            load_technique_info_from_py(py_file)
        assert "TECHNIQUE_INFO" in str(exc_info.value)

    def test_load_py_technique_info_not_dict(self, tmp_path: Path) -> None:
        """Test TECHNIQUE_INFO must be a dict."""
        py_content = dedent("""
            TECHNIQUE_INFO = "not a dict"
        """)

        py_file = tmp_path / "not_dict.py"
        py_file.write_text(py_content)

        with pytest.raises(StrategyLoadError) as exc_info:
            load_technique_info_from_py(py_file)
        assert "dict" in str(exc_info.value).lower()

    def test_load_py_no_strategy_class(self, tmp_path: Path) -> None:
        """Test file must have a BaseStrategy subclass."""
        py_content = dedent("""
            TECHNIQUE_INFO = {
                "name": "test",
                "version": "1.0.0",
                "description": "Test",
            }
            # No BaseStrategy subclass
        """)

        py_file = tmp_path / "no_strategy.py"
        py_file.write_text(py_content)

        with pytest.raises(StrategyLoadError) as exc_info:
            load_technique_info_from_py(py_file)
        assert "BaseStrategy" in str(exc_info.value)


class TestLoadStrategy:
    """Tests for the unified load_strategy function."""

    def test_load_md_strategy(self, tmp_path: Path) -> None:
        """Test loading a markdown strategy file."""
        md_content = dedent("""
            ---
            name: prompt_test
            version: 1.0.0
            description: Prompt test
            ---

            Prompt content
        """).strip()

        md_file = tmp_path / "test.md"
        md_file.write_text(md_content)

        strategy = load_strategy(md_file)

        assert isinstance(strategy, PromptStrategy)
        assert strategy.name == "prompt_test"
        assert "Prompt content" in strategy.prompt

    def test_load_py_strategy(self, tmp_path: Path) -> None:
        """Test loading a Python strategy file."""
        py_content = dedent("""
            from src.strategy.base import BaseStrategy, TechniqueInfo
            from src.models import OHLCV, AnalysisResult
            from decimal import Decimal

            TECHNIQUE_INFO = {
                "name": "code_test",
                "version": "1.0.0",
                "description": "Code test",
            }

            class CodeTestStrategy(BaseStrategy):
                async def analyze(self, ohlcv, symbol, timeframe="1h"):
                    return AnalysisResult(
                        signal="neutral",
                        confidence=0.5,
                        entry_price=Decimal("100"),
                        stop_loss=Decimal("98"),
                        take_profit=Decimal("102"),
                        reasoning="Test",
                    )
        """)

        py_file = tmp_path / "test.py"
        py_file.write_text(py_content)

        strategy = load_strategy(py_file)

        assert isinstance(strategy, BaseStrategy)
        assert strategy.name == "code_test"

    def test_load_unsupported_extension(self, tmp_path: Path) -> None:
        """Test loading unsupported file type raises error."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("content")

        with pytest.raises(StrategyLoadError) as exc_info:
            load_strategy(txt_file)
        assert "unsupported" in str(exc_info.value).lower()


class TestDiscoverStrategies:
    """Tests for strategy discovery."""

    def test_discover_in_empty_directory(self, tmp_path: Path) -> None:
        """Test discover returns empty list for empty directory."""
        result = discover_strategies(tmp_path)
        assert result == []

    def test_discover_in_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test discover returns empty list for non-existent directory."""
        result = discover_strategies(tmp_path / "nonexistent")
        assert result == []

    def test_discover_finds_md_and_py_files(self, tmp_path: Path) -> None:
        """Test discover finds both .md and .py files."""
        (tmp_path / "strat1.md").write_text("---\nname: a\nversion: 1.0.0\n---\n")
        (tmp_path / "strat2.py").write_text("TECHNIQUE_INFO = {}")
        (tmp_path / "readme.txt").write_text("ignore")

        result = discover_strategies(tmp_path)

        assert len(result) == 2
        assert any(p.suffix == ".md" for p in result)
        assert any(p.suffix == ".py" for p in result)

    def test_discover_excludes_private_files(self, tmp_path: Path) -> None:
        """Test discover excludes files starting with underscore."""
        (tmp_path / "__init__.py").write_text("")
        (tmp_path / "_private.py").write_text("")
        (tmp_path / "public.md").write_text("---\nname: a\nversion: 1.0.0\n---\n")

        result = discover_strategies(tmp_path)

        assert len(result) == 1
        assert result[0].name == "public.md"

    def test_discover_excludes_test_files(self, tmp_path: Path) -> None:
        """Test discover excludes test files."""
        (tmp_path / "test_strategy.py").write_text("")
        (tmp_path / "strategy.py").write_text("TECHNIQUE_INFO = {}")

        result = discover_strategies(tmp_path)

        assert len(result) == 1
        assert result[0].name == "strategy.py"

    def test_discover_includes_subdirectories(self, tmp_path: Path) -> None:
        """Test discover includes subdirectory strategies."""
        (tmp_path / "root.md").write_text("---\nname: a\nversion: 1.0.0\n---\n")
        subdir = tmp_path / "experimental"
        subdir.mkdir()
        (subdir / "exp.md").write_text("---\nname: b\nversion: 1.0.0\n---\n")

        result = discover_strategies(tmp_path, include_subdirs=True)

        assert len(result) == 2

    def test_discover_excludes_subdirectories_when_disabled(
        self, tmp_path: Path
    ) -> None:
        """Test discover excludes subdirectories when disabled."""
        (tmp_path / "root.md").write_text("---\nname: a\nversion: 1.0.0\n---\n")
        subdir = tmp_path / "experimental"
        subdir.mkdir()
        (subdir / "exp.md").write_text("---\nname: b\nversion: 1.0.0\n---\n")

        result = discover_strategies(tmp_path, include_subdirs=False)

        assert len(result) == 1

    def test_discover_returns_sorted_list(self, tmp_path: Path) -> None:
        """Test discover returns sorted list of paths."""
        (tmp_path / "z_last.md").write_text("---\nname: a\nversion: 1.0.0\n---\n")
        (tmp_path / "a_first.md").write_text("---\nname: b\nversion: 1.0.0\n---\n")

        result = discover_strategies(tmp_path)

        assert result[0].name == "a_first.md"
        assert result[1].name == "z_last.md"


class TestLoadAllStrategies:
    """Tests for load_all_strategies function."""

    def test_load_all_from_empty_directory(self, tmp_path: Path) -> None:
        """Test loading from empty directory returns empty dict."""
        result = load_all_strategies(tmp_path)
        assert result == {}

    def test_load_all_returns_dict(self, tmp_path: Path) -> None:
        """Test load_all_strategies returns dict with strategy names as keys."""
        md_content = dedent("""
            ---
            name: test_strategy
            version: 1.0.0
            description: Test
            ---

            Prompt
        """).strip()

        (tmp_path / "test.md").write_text(md_content)

        result = load_all_strategies(tmp_path)

        assert "test_strategy" in result
        assert isinstance(result["test_strategy"], BaseStrategy)

    def test_load_all_skips_invalid_files(self, tmp_path: Path) -> None:
        """Test load_all_strategies skips invalid files."""
        # Valid file
        md_content = dedent("""
            ---
            name: valid_strategy
            version: 1.0.0
            description: Valid
            ---

            Prompt
        """).strip()
        (tmp_path / "valid.md").write_text(md_content)

        # Invalid file (missing frontmatter)
        (tmp_path / "invalid.md").write_text("No frontmatter here")

        result = load_all_strategies(tmp_path)

        assert "valid_strategy" in result
        assert len(result) == 1

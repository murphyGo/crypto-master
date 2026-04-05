"""Tests for the strategy factory module."""

from pathlib import Path
from textwrap import dedent

import pytest

from src.strategy.base import BaseStrategy, StrategyError, TechniqueInfo
from src.strategy.factory import (
    clear_strategy_cache,
    clear_strategy_registry,
    get_available_strategies,
    get_strategies_by_status,
    get_strategies_by_symbol,
    get_strategy,
    load_strategies_from_directory,
    register_strategy,
)
from src.strategy.loader import PromptStrategy


@pytest.fixture(autouse=True)
def clean_registry() -> None:
    """Clear registry and cache before each test."""
    clear_strategy_cache()
    clear_strategy_registry()


class TestRegisterStrategy:
    """Tests for the register_strategy decorator."""

    def test_register_strategy_decorator(self) -> None:
        """Test registering a strategy with decorator."""

        @register_strategy("test_registered")
        class TestStrategy(BaseStrategy):
            async def analyze(self, ohlcv, symbol, timeframe="1h"):
                pass

        # Force load to include registered strategies
        strategies = load_strategies_from_directory(Path("nonexistent"), force_reload=True)
        assert "test_registered" in strategies

    def test_register_strategy_case_insensitive(self) -> None:
        """Test registration is case-insensitive."""

        @register_strategy("TestMixed")
        class TestStrategy(BaseStrategy):
            async def analyze(self, ohlcv, symbol, timeframe="1h"):
                pass

        strategies = load_strategies_from_directory(Path("nonexistent"), force_reload=True)
        assert "testmixed" in strategies

    def test_register_strategy_returns_class(self) -> None:
        """Test decorator returns the original class."""

        @register_strategy("returns_class")
        class TestStrategy(BaseStrategy):
            async def analyze(self, ohlcv, symbol, timeframe="1h"):
                pass

        assert TestStrategy.__name__ == "TestStrategy"
        assert issubclass(TestStrategy, BaseStrategy)


class TestGetStrategy:
    """Tests for get_strategy function."""

    def test_get_strategy_not_found(self) -> None:
        """Test getting non-existent strategy raises error."""
        with pytest.raises(StrategyError) as exc_info:
            get_strategy("nonexistent")
        assert "not found" in str(exc_info.value).lower()

    def test_get_strategy_shows_available(self) -> None:
        """Test error message shows available strategies."""

        @register_strategy("available_one")
        class TestStrategy(BaseStrategy):
            async def analyze(self, ohlcv, symbol, timeframe="1h"):
                pass

        load_strategies_from_directory(Path("nonexistent"), force_reload=True)

        with pytest.raises(StrategyError) as exc_info:
            get_strategy("nonexistent")
        assert "available_one" in str(exc_info.value).lower()

    def test_get_strategy_from_registry(self) -> None:
        """Test getting a registered strategy."""

        @register_strategy("get_test")
        class TestStrategy(BaseStrategy):
            async def analyze(self, ohlcv, symbol, timeframe="1h"):
                pass

        load_strategies_from_directory(Path("nonexistent"), force_reload=True)
        strategy = get_strategy("get_test")

        assert strategy is not None
        assert strategy.name == "get_test"

    def test_get_strategy_case_insensitive(self) -> None:
        """Test get_strategy is case-insensitive."""

        @register_strategy("case_test")
        class TestStrategy(BaseStrategy):
            async def analyze(self, ohlcv, symbol, timeframe="1h"):
                pass

        load_strategies_from_directory(Path("nonexistent"), force_reload=True)

        strategy = get_strategy("CASE_TEST")
        assert strategy is not None


class TestLoadStrategiesFromDirectory:
    """Tests for load_strategies_from_directory function."""

    def test_load_from_directory(self, tmp_path: Path) -> None:
        """Test loading strategies from directory."""
        md_content = dedent("""
            ---
            name: dir_strategy
            version: 1.0.0
            description: Test
            ---

            Prompt
        """).strip()

        (tmp_path / "test.md").write_text(md_content)

        strategies = load_strategies_from_directory(tmp_path, force_reload=True)

        assert "dir_strategy" in strategies

    def test_load_uses_cache(self, tmp_path: Path) -> None:
        """Test load uses cache when not force_reload."""
        md_content = dedent("""
            ---
            name: cached_strategy
            version: 1.0.0
            description: Test
            ---

            Prompt
        """).strip()

        (tmp_path / "test.md").write_text(md_content)

        # First load
        strategies1 = load_strategies_from_directory(tmp_path, force_reload=True)

        # Delete file
        (tmp_path / "test.md").unlink()

        # Second load should use cache
        strategies2 = load_strategies_from_directory(tmp_path, force_reload=False)

        assert "cached_strategy" in strategies2

    def test_force_reload_clears_cache(self, tmp_path: Path) -> None:
        """Test force_reload clears cache."""
        md_content = dedent("""
            ---
            name: old_strategy
            version: 1.0.0
            description: Test
            ---

            Prompt
        """).strip()

        (tmp_path / "test.md").write_text(md_content)
        load_strategies_from_directory(tmp_path, force_reload=True)

        # Delete file
        (tmp_path / "test.md").unlink()

        # Force reload should not find the strategy
        strategies = load_strategies_from_directory(tmp_path, force_reload=True)

        assert "old_strategy" not in strategies


class TestGetAvailableStrategies:
    """Tests for get_available_strategies function."""

    def test_returns_empty_for_empty_directory(self, tmp_path: Path) -> None:
        """Test returns empty list when loading from empty directory."""
        # Load from empty temp directory
        load_strategies_from_directory(tmp_path, force_reload=True)
        result = get_available_strategies()
        assert result == []

    def test_returns_registered_strategies(self) -> None:
        """Test returns registered strategies."""

        @register_strategy("avail_test")
        class TestStrategy(BaseStrategy):
            async def analyze(self, ohlcv, symbol, timeframe="1h"):
                pass

        load_strategies_from_directory(Path("nonexistent"), force_reload=True)
        result = get_available_strategies()

        assert "avail_test" in result

    def test_returns_sorted_list(self) -> None:
        """Test returns sorted list of names."""

        @register_strategy("z_last")
        class TestStrategy1(BaseStrategy):
            async def analyze(self, ohlcv, symbol, timeframe="1h"):
                pass

        @register_strategy("a_first")
        class TestStrategy2(BaseStrategy):
            async def analyze(self, ohlcv, symbol, timeframe="1h"):
                pass

        load_strategies_from_directory(Path("nonexistent"), force_reload=True)
        result = get_available_strategies()

        assert result == ["a_first", "z_last"]


class TestGetStrategiesBySymbol:
    """Tests for get_strategies_by_symbol function."""

    def test_filter_by_symbol(self, tmp_path: Path) -> None:
        """Test filtering strategies by symbol."""
        md_content = dedent("""
            ---
            name: btc_only
            version: 1.0.0
            description: BTC only strategy
            symbols: ["BTC/USDT"]
            ---

            Prompt
        """).strip()

        (tmp_path / "btc.md").write_text(md_content)

        md_content2 = dedent("""
            ---
            name: eth_only
            version: 1.0.0
            description: ETH only strategy
            symbols: ["ETH/USDT"]
            ---

            Prompt
        """).strip()

        (tmp_path / "eth.md").write_text(md_content2)

        load_strategies_from_directory(tmp_path, force_reload=True)

        btc_strategies = get_strategies_by_symbol("BTC/USDT")
        eth_strategies = get_strategies_by_symbol("ETH/USDT")

        assert len(btc_strategies) == 1
        assert btc_strategies[0].name == "btc_only"

        assert len(eth_strategies) == 1
        assert eth_strategies[0].name == "eth_only"

    def test_wildcard_symbol(self, tmp_path: Path) -> None:
        """Test strategy with wildcard symbol matches all."""
        md_content = dedent("""
            ---
            name: all_symbols
            version: 1.0.0
            description: All symbols strategy
            symbols: ["*"]
            ---

            Prompt
        """).strip()

        (tmp_path / "all.md").write_text(md_content)

        load_strategies_from_directory(tmp_path, force_reload=True)

        result = get_strategies_by_symbol("ANY/SYMBOL")

        assert len(result) == 1
        assert result[0].name == "all_symbols"


class TestGetStrategiesByStatus:
    """Tests for get_strategies_by_status function."""

    def test_filter_by_status(self, tmp_path: Path) -> None:
        """Test filtering strategies by status."""
        md_content = dedent("""
            ---
            name: active_strat
            version: 1.0.0
            description: Active strategy
            status: active
            ---

            Prompt
        """).strip()

        (tmp_path / "active.md").write_text(md_content)

        md_content2 = dedent("""
            ---
            name: experimental_strat
            version: 1.0.0
            description: Experimental strategy
            status: experimental
            ---

            Prompt
        """).strip()

        (tmp_path / "experimental.md").write_text(md_content2)

        load_strategies_from_directory(tmp_path, force_reload=True)

        active = get_strategies_by_status("active")
        experimental = get_strategies_by_status("experimental")

        assert len(active) == 1
        assert active[0].name == "active_strat"

        assert len(experimental) == 1
        assert experimental[0].name == "experimental_strat"


class TestClearStrategyCache:
    """Tests for clear_strategy_cache function."""

    def test_clear_cache(self, tmp_path: Path) -> None:
        """Test clearing the strategy cache."""
        md_content = dedent("""
            ---
            name: to_clear
            version: 1.0.0
            description: Test
            ---

            Prompt
        """).strip()

        (tmp_path / "test.md").write_text(md_content)
        load_strategies_from_directory(tmp_path, force_reload=True)

        assert "to_clear" in get_available_strategies()

        clear_strategy_cache()

        # Should still be able to load
        load_strategies_from_directory(tmp_path, force_reload=True)
        assert "to_clear" in get_available_strategies()

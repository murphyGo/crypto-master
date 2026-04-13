"""Tests for StrategyImprover."""

from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.ai.claude import ClaudeCLI
from src.ai.improver import (
    GeneratedTechnique,
    GeneratedTechniqueError,
    StrategyImprover,
    StrategyImproverError,
)
from src.strategy.base import TechniqueInfo
from src.strategy.performance import (
    PerformanceRecord,
    TechniquePerformance,
    TradeOutcome,
)

# =============================================================================
# Helpers
# =============================================================================


def make_claude_mock(
    response: str | Exception,
) -> ClaudeCLI:
    """Build a ClaudeCLI-shaped mock where complete() returns `response`."""
    mock = AsyncMock(spec=ClaudeCLI)
    if isinstance(response, Exception):
        mock.complete.side_effect = response
    else:
        mock.complete.return_value = response
    return mock


def make_improver(
    tmp_path: Path,
    response: str | Exception = "```markdown\n---\nname: test\n---\nbody\n```",
) -> tuple[StrategyImprover, AsyncMock]:
    """Build a StrategyImprover with a mocked ClaudeCLI."""
    claude = make_claude_mock(response)
    improver = StrategyImprover(
        claude=claude,
        experimental_dir=tmp_path / "strategies" / "experimental",
    )
    return improver, claude


def sample_technique() -> TechniqueInfo:
    return TechniqueInfo(
        name="rsi_divergence",
        version="1.0.0",
        description="RSI divergence-based technique",
        technique_type="prompt",
    )


def sample_performance() -> TechniquePerformance:
    return TechniquePerformance(
        technique_name="rsi_divergence",
        technique_version="1.0.0",
        total_trades=10,
        wins=4,
        losses=5,
        breakevens=1,
        win_rate=0.4,
        avg_pnl_percent=-0.5,
        total_pnl_percent=-5.0,
        best_trade_pnl=3.0,
        worst_trade_pnl=-2.5,
    )


def sample_records() -> list[PerformanceRecord]:
    return [
        PerformanceRecord(
            technique_name="rsi_divergence",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.7,
            outcome=TradeOutcome.LOSS,
            exit_price=Decimal("49000"),
            pnl_percent=-2.0,
        )
    ]


# A well-formed Claude response with proper frontmatter + fenced block.
GOOD_RESPONSE = """\
Here is a proposed improvement:

```markdown
---
name: rsi_divergence_v2
version: 1.1.0
description: Tighter confirmation + ATR-adaptive stops
technique_type: prompt
---

# RSI Divergence v2

Analyze the last 50 candles and look for a bullish divergence
confirmed by a volume spike of at least 1.5x the 20-period
average. Only trade when RSI < 30 at the divergence point.
```
"""

# Response without a fenced block — improver should still accept it.
RAW_RESPONSE = """\
---
name: bare_markdown
version: 0.2.0
description: A bare response with no fences
technique_type: prompt
---

Some body content here.
"""

# Response with a fenced block but no frontmatter — fallback_name used.
NO_FRONTMATTER_RESPONSE = """\
```markdown
# A technique without frontmatter

Enter long when price crosses above SMA(50).
```
"""

# Empty block — should raise GeneratedTechniqueError.
EMPTY_BLOCK_RESPONSE = "```markdown\n\n```"


# Response with a hypothesis field — verifies it's parsed into the model.
HYPOTHESIS_RESPONSE = """\
```markdown
---
name: funding_reversion
version: 0.1.0
description: Mean revert when funding hits extremes
technique_type: code
hypothesis: Funding rate above 0.05% per 8h predicts negative 24h returns due to over-leveraged longs
---
body
```
"""


# =============================================================================
# suggest_improvement
# =============================================================================


class TestSuggestImprovement:
    """Tests for the improvement flow (FR-022)."""

    @pytest.mark.asyncio
    async def test_returns_generated_technique(
        self, tmp_path: Path
    ) -> None:
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        generated = await improver.suggest_improvement(
            technique=sample_technique(),
            original_source="Enter long on RSI divergence.",
            performance=sample_performance(),
            records=sample_records(),
        )
        assert isinstance(generated, GeneratedTechnique)
        assert generated.kind == "improvement"
        assert generated.name == "rsi_divergence_v2"
        assert generated.version == "1.1.0"
        assert "ATR-adaptive" in generated.description
        assert generated.parent_technique == "rsi_divergence"
        assert generated.saved_path is not None
        assert generated.saved_path.exists()
        assert "RSI Divergence v2" in generated.content

    @pytest.mark.asyncio
    async def test_prompt_includes_performance_data(
        self, tmp_path: Path
    ) -> None:
        """The improvement prompt must carry perf stats and source."""
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        await improver.suggest_improvement(
            technique=sample_technique(),
            original_source="ORIGINAL_SOURCE_MARKER",
            performance=sample_performance(),
            records=sample_records(),
        )
        # Inspect the prompt that was passed to claude.complete
        prompt = claude.complete.await_args.args[0]
        assert "rsi_divergence" in prompt
        assert "Win rate" in prompt
        assert "40.00%" in prompt
        assert "ORIGINAL_SOURCE_MARKER" in prompt
        assert "BTC/USDT" in prompt  # from records
        # Output format boilerplate
        assert "fenced markdown code block" in prompt

    @pytest.mark.asyncio
    async def test_no_records_still_works(
        self, tmp_path: Path
    ) -> None:
        """Records list is optional; prompt uses a fallback line."""
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        await improver.suggest_improvement(
            technique=sample_technique(),
            original_source="src",
            performance=sample_performance(),
        )
        prompt = claude.complete.await_args.args[0]
        assert "no detailed records" in prompt

    @pytest.mark.asyncio
    async def test_save_false_does_not_write(self, tmp_path: Path) -> None:
        improver, _ = make_improver(tmp_path, GOOD_RESPONSE)
        generated = await improver.suggest_improvement(
            technique=sample_technique(),
            original_source="src",
            performance=sample_performance(),
            save=False,
        )
        assert generated.saved_path is None
        assert not improver.experimental_dir.exists() or not any(
            improver.experimental_dir.iterdir()
        )


# =============================================================================
# generate_idea
# =============================================================================


class TestGenerateIdea:
    """Tests for the new-idea flow (FR-023)."""

    @pytest.mark.asyncio
    async def test_returns_generated_technique(self, tmp_path: Path) -> None:
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        generated = await improver.generate_idea(context="mean reversion on 1h")
        assert generated.kind == "new_idea"
        assert generated.parent_technique is None
        assert generated.saved_path is not None

    @pytest.mark.asyncio
    async def test_context_embedded_in_prompt(self, tmp_path: Path) -> None:
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        await improver.generate_idea(context="MEAN_REVERSION_MARKER")
        prompt = claude.complete.await_args.args[0]
        assert "MEAN_REVERSION_MARKER" in prompt

    @pytest.mark.asyncio
    async def test_empty_context_ok(self, tmp_path: Path) -> None:
        """No context is fine — prompt just omits the steering line."""
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        await improver.generate_idea()
        prompt = claude.complete.await_args.args[0]
        assert "Context / steering" not in prompt


# =============================================================================
# generate_from_user_idea
# =============================================================================


class TestGenerateFromUserIdea:
    """Tests for the user-idea flow (FR-024)."""

    @pytest.mark.asyncio
    async def test_user_idea_in_prompt(self, tmp_path: Path) -> None:
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        await improver.generate_from_user_idea(
            "Scalp ETH on RSI(3) oversold bounces"
        )
        prompt = claude.complete.await_args.args[0]
        assert "Scalp ETH on RSI(3)" in prompt

    @pytest.mark.asyncio
    async def test_empty_user_idea_raises(self, tmp_path: Path) -> None:
        improver, _ = make_improver(tmp_path, GOOD_RESPONSE)
        with pytest.raises(StrategyImproverError, match="must not be empty"):
            await improver.generate_from_user_idea("")
        with pytest.raises(StrategyImproverError, match="must not be empty"):
            await improver.generate_from_user_idea("   \n  ")

    @pytest.mark.asyncio
    async def test_kind_is_user_idea(self, tmp_path: Path) -> None:
        improver, _ = make_improver(tmp_path, GOOD_RESPONSE)
        generated = await improver.generate_from_user_idea("some idea")
        assert generated.kind == "user_idea"


# =============================================================================
# Response parsing
# =============================================================================


class TestResponseParsing:
    """Tests for the markdown / frontmatter parser."""

    @pytest.mark.asyncio
    async def test_bare_markdown_without_fence(
        self, tmp_path: Path
    ) -> None:
        """Claude sometimes replies with no fence; improver accepts it."""
        improver, _ = make_improver(tmp_path, RAW_RESPONSE)
        generated = await improver.generate_idea()
        assert generated.name == "bare_markdown"
        assert generated.version == "0.2.0"

    @pytest.mark.asyncio
    async def test_missing_frontmatter_uses_fallback_name(
        self, tmp_path: Path
    ) -> None:
        improver, _ = make_improver(tmp_path, NO_FRONTMATTER_RESPONSE)
        generated = await improver.generate_idea()
        # Fallback name for new_idea flow is "new_idea"
        assert generated.name == "new_idea"
        assert generated.version == "0.1.0"
        # Content still carried verbatim
        assert "SMA(50)" in generated.content

    @pytest.mark.asyncio
    async def test_empty_block_raises(self, tmp_path: Path) -> None:
        improver, _ = make_improver(tmp_path, EMPTY_BLOCK_RESPONSE)
        with pytest.raises(GeneratedTechniqueError):
            await improver.generate_idea()

    @pytest.mark.asyncio
    async def test_malformed_frontmatter_ignored(
        self, tmp_path: Path
    ) -> None:
        """Broken YAML in frontmatter → use fallback instead of crashing."""
        response = (
            "```markdown\n"
            "---\n"
            "name: [unclosed\n"
            "---\n"
            "body\n"
            "```"
        )
        improver, _ = make_improver(tmp_path, response)
        generated = await improver.generate_idea()
        assert generated.name == "new_idea"  # fallback


# =============================================================================
# Persistence
# =============================================================================


class TestPersistence:
    @pytest.mark.asyncio
    async def test_saved_filename_includes_timestamp(
        self, tmp_path: Path
    ) -> None:
        """Filename has a timestamp suffix so repeat saves don't clash."""
        improver, _ = make_improver(tmp_path, GOOD_RESPONSE)
        gen = await improver.generate_idea()
        assert gen.saved_path is not None
        stem = gen.saved_path.stem
        # e.g. rsi_divergence_v2_20260413_094255
        assert stem.startswith("rsi_divergence_v2_")
        assert gen.saved_path.suffix == ".md"

    @pytest.mark.asyncio
    async def test_saved_file_contents(self, tmp_path: Path) -> None:
        improver, _ = make_improver(tmp_path, GOOD_RESPONSE)
        gen = await improver.generate_idea()
        assert gen.saved_path is not None
        content = gen.saved_path.read_text(encoding="utf-8")
        assert content == gen.content
        assert "rsi_divergence_v2" in content

    @pytest.mark.asyncio
    async def test_filename_slug_strips_unsafe_chars(
        self, tmp_path: Path
    ) -> None:
        """Names with spaces / slashes become safe filename stems."""
        response = (
            "```markdown\n"
            "---\n"
            "name: Weird/Name With Spaces!\n"
            "version: 0.1.0\n"
            "description: test\n"
            "technique_type: prompt\n"
            "---\n"
            "body\n"
            "```"
        )
        improver, _ = make_improver(tmp_path, response)
        gen = await improver.generate_idea()
        assert gen.saved_path is not None
        assert "/" not in gen.saved_path.name
        assert " " not in gen.saved_path.name
        assert "!" not in gen.saved_path.name


# =============================================================================
# Error propagation
# =============================================================================


class TestPromptQualityGuards:
    """Verify the prompts steer Claude away from overfitting and toward
    falsifiable, structurally-grounded techniques."""

    @pytest.mark.asyncio
    async def test_improvement_prompt_demands_failure_analysis(
        self, tmp_path: Path
    ) -> None:
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        await improver.suggest_improvement(
            technique=sample_technique(),
            original_source="src",
            performance=sample_performance(),
        )
        prompt = claude.complete.await_args.args[0]
        # Forces structural reasoning, not surface-level patching.
        assert "Failure Analysis" in prompt
        assert "structural" in prompt.lower()
        # Explicit anti-overfit guardrails.
        assert "overfit" in prompt.lower()
        assert "do not add more than 2" in prompt.lower()

    @pytest.mark.asyncio
    async def test_new_idea_prompt_rejects_indicator_mashups(
        self, tmp_path: Path
    ) -> None:
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        await improver.generate_idea()
        prompt = claude.complete.await_args.args[0]
        # Steers toward market-structure hypotheses.
        assert "falsifiable" in prompt.lower()
        assert "funding rate" in prompt.lower()  # one of the example kinds
        # Explicitly warns off generic indicator combos.
        assert "indicator mashup" in prompt.lower() or (
            "RSI + MACD" in prompt
        )

    @pytest.mark.asyncio
    async def test_user_idea_prompt_extracts_hypothesis(
        self, tmp_path: Path
    ) -> None:
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        await improver.generate_from_user_idea("buy when RSI < 30")
        prompt = claude.complete.await_args.args[0]
        assert "hypothesis" in prompt.lower()
        assert "Caveats" in prompt

    @pytest.mark.asyncio
    async def test_output_format_requires_hypothesis_field(
        self, tmp_path: Path
    ) -> None:
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        await improver.generate_idea()
        prompt = claude.complete.await_args.args[0]
        assert "hypothesis:" in prompt
        assert "falsifi" in prompt.lower()

    @pytest.mark.asyncio
    async def test_hypothesis_field_parsed_into_model(
        self, tmp_path: Path
    ) -> None:
        improver, _ = make_improver(tmp_path, HYPOTHESIS_RESPONSE)
        gen = await improver.generate_idea()
        assert "Funding rate above 0.05%" in gen.hypothesis

    @pytest.mark.asyncio
    async def test_hypothesis_defaults_empty_when_missing(
        self, tmp_path: Path
    ) -> None:
        """Existing techniques without hypothesis still parse cleanly."""
        improver, _ = make_improver(tmp_path, GOOD_RESPONSE)
        gen = await improver.generate_idea()
        assert gen.hypothesis == ""


class TestErrorPropagation:
    @pytest.mark.asyncio
    async def test_claude_error_surfaces(self, tmp_path: Path) -> None:
        from src.ai.exceptions import ClaudeExecutionError

        improver, _ = make_improver(
            tmp_path,
            ClaudeExecutionError("boom", exit_code=1, stderr="oops"),
        )
        with pytest.raises(ClaudeExecutionError):
            await improver.generate_idea()

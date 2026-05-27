"""Tests for StrategyImprover."""

from datetime import datetime, timezone
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
from src.strategy.trade_autopsy import TradeAutopsy, TradeAutopsyOutcome

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
    response: str | Exception = (
        "```markdown\n"
        "---\n"
        "name: test\n"
        "version: 0.1.0\n"
        "description: test\n"
        "technique_type: prompt\n"
        "hypothesis: A test setup predicts a measurable next-bar move.\n"
        "---\n"
        "body\n\n"
        "## Output Contract\n"
        "Return JSON keys: signal, entry_price, stop_loss, take_profit.\n"
        "```"
    ),
    catalog_path: Path | None = None,
) -> tuple[StrategyImprover, AsyncMock]:
    """Build a StrategyImprover with a mocked ClaudeCLI.

    By default the improver is pointed at a non-existent catalog file
    under ``tmp_path``, so prompt-content assertions in unrelated tests
    aren't affected by accidental catalog injection from cwd.
    """
    claude = make_claude_mock(response)
    effective_catalog = (
        catalog_path if catalog_path is not None else tmp_path / "no_catalog.md"
    )
    improver = StrategyImprover(
        claude=claude,
        experimental_dir=tmp_path / "strategies" / "experimental",
        catalog_path=effective_catalog,
    )
    return improver, claude


def test_prompt_section_helpers_are_isolated() -> None:
    # AI-F4: the pure prompt-text builders now live in src/ai/prompts.py
    # as module-level functions, isolated from the improver's
    # parse/validate/persist core.
    from src.ai import prompts

    assert "## Required Reasoning Process" in prompts.failure_analysis_section()
    assert "## Hard Constraints" in prompts.hard_constraints_section()
    assert "## Required file shape" in prompts.code_shape_requirements()
    assert "## Hard constraints" in prompts.code_hard_constraints()
    assert "## Output format" in prompts.code_output_format()


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


def sample_autopsies() -> list[TradeAutopsy]:
    return [
        TradeAutopsy(
            trade_id="autopsy-1",
            symbol="BTC/USDT",
            side="long",
            mode="paper",
            entry_time=datetime(2026, 5, 7, 1, tzinfo=timezone.utc),
            exit_time=datetime(2026, 5, 7, 3, tzinfo=timezone.utc),
            entry_price=Decimal("50000"),
            exit_price=Decimal("49000"),
            quantity=Decimal("0.1"),
            leverage=1,
            pnl=Decimal("-100"),
            pnl_percent=-2.0,
            close_reason="stop_loss",
            holding_seconds=7200,
            outcome=TradeAutopsyOutcome.LOSS,
            max_favorable_excursion_percent=1.5,
            max_adverse_excursion_percent=3.0,
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
hypothesis: RSI divergence with volume confirmation predicts short-term reversal after exhaustion.
---

# RSI Divergence v2

Analyze the last 50 candles and look for a bullish divergence
confirmed by a volume spike of at least 1.5x the 20-period
average. Only trade when RSI < 30 at the divergence point.

## Output Contract

Return one fenced JSON object with keys: signal, entry_price, stop_loss,
take_profit.
```
"""

# Response without a fenced block — improver should still accept it.
RAW_RESPONSE = """\
---
name: bare_markdown
version: 0.2.0
description: A bare response with no fences
technique_type: prompt
hypothesis: SMA breakouts after compression predict continuation over the next hour.
---

Some body content here.

## Output Contract

Return one fenced JSON object with keys: signal, entry_price, stop_loss,
take_profit.
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

## Output Contract

Return JSON with keys: signal, entry_price, stop_loss, take_profit.
```
"""

MARKDOWN_CODE_WITHOUT_OUTPUT_CONTRACT = """\
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

ORIGINAL_WITH_OUTPUT_CONTRACT = """\
---
name: chasulang_fixture
version: 1.0.0
description: Prompt strategy with runtime contract
technique_type: prompt
---

# Chasulang Fixture

## Output Contract

Return JSON with:

{
  "signal": "long" | "short" | "neutral",
  "entry_price": <decimal> | null,
  "stop_loss": <decimal> | null,
  "take_profit": <decimal> | null
}
"""

IMPROVEMENT_WITH_OUTPUT_CONTRACT = """\
```markdown
---
name: chasulang_fixture_v2
version: 1.1.0
description: Refined prompt preserving runtime contract
technique_type: prompt
hypothesis: Preserving the runtime JSON contract keeps prompt outputs parseable.
---

# Chasulang Fixture v2

## Failure Analysis

The original strategy overreacted to weak structure shifts.

## Output Contract

Return JSON with:

{
  "signal": "long" | "short" | "neutral",
  "entry_price": <decimal> | null,
  "stop_loss": <decimal> | null,
  "take_profit": <decimal> | null
}
```
"""

IMPROVEMENT_WITHOUT_OUTPUT_CONTRACT = """\
```markdown
---
name: chasulang_fixture_v2
version: 1.1.0
description: Refined prompt that accidentally dropped the contract
technique_type: prompt
hypothesis: Preserving structure filters should improve reversals after liquidity sweeps.
---

# Chasulang Fixture v2

## Failure Analysis

The original strategy overreacted to weak structure shifts.
```
"""

IMPROVEMENT_WITH_OUTPUT_CONTRACT_MISSING_KEY = """\
```markdown
---
name: chasulang_fixture_v2
version: 1.1.0
description: Refined prompt with incomplete runtime contract
technique_type: prompt
hypothesis: Structure confirmation should reduce false positive prompt reversals.
---

# Chasulang Fixture v2

## Output Contract

Return JSON with:

{
  "signal": "long" | "short" | "neutral",
  "entry_price": <decimal> | null,
  "stop_loss": <decimal> | null
}
```
"""


# =============================================================================
# suggest_improvement
# =============================================================================


class TestSuggestImprovement:
    """Tests for the improvement flow (FR-022)."""

    @pytest.mark.asyncio
    async def test_returns_generated_technique(self, tmp_path: Path) -> None:
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
    async def test_prompt_includes_performance_data(self, tmp_path: Path) -> None:
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
    async def test_prompt_includes_trade_autopsies(self, tmp_path: Path) -> None:
        """Autopsy summaries should feed the improvement prompt."""
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        await improver.suggest_improvement(
            technique=sample_technique(),
            original_source="ORIGINAL_SOURCE_MARKER",
            performance=sample_performance(),
            records=sample_records(),
            autopsies=sample_autopsies(),
        )

        prompt = claude.complete.await_args.args[0]
        assert "Trade Autopsies" in prompt
        assert "close=stop_loss" in prompt
        assert "mfe=1.50%" in prompt
        assert "mae=3.00%" in prompt

    @pytest.mark.asyncio
    async def test_no_records_still_works(self, tmp_path: Path) -> None:
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
        await improver.generate_from_user_idea("Scalp ETH on RSI(3) oversold bounces")
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
    async def test_bare_markdown_without_fence(self, tmp_path: Path) -> None:
        """Claude sometimes replies with no fence; improver accepts it."""
        improver, _ = make_improver(tmp_path, RAW_RESPONSE)
        generated = await improver.generate_idea()
        assert generated.name == "bare_markdown"
        assert generated.version == "0.2.0"

    @pytest.mark.asyncio
    async def test_missing_frontmatter_rejected_for_missing_hypothesis(
        self,
        tmp_path: Path,
    ) -> None:
        improver, _ = make_improver(tmp_path, NO_FRONTMATTER_RESPONSE)
        with pytest.raises(GeneratedTechniqueError, match="hypothesis"):
            await improver.generate_idea()

    @pytest.mark.asyncio
    async def test_empty_block_raises(self, tmp_path: Path) -> None:
        improver, _ = make_improver(tmp_path, EMPTY_BLOCK_RESPONSE)
        with pytest.raises(GeneratedTechniqueError):
            await improver.generate_idea()

    @pytest.mark.asyncio
    async def test_malformed_frontmatter_rejected(self, tmp_path: Path) -> None:
        """Broken YAML cannot satisfy the generated-technique contract."""
        response = "```markdown\n" "---\n" "name: [unclosed\n" "---\n" "body\n" "```"
        improver, _ = make_improver(tmp_path, response)
        with pytest.raises(GeneratedTechniqueError, match="hypothesis"):
            await improver.generate_idea()


# =============================================================================
# Persistence
# =============================================================================


class TestPersistence:
    @pytest.mark.asyncio
    async def test_saved_filename_includes_timestamp(self, tmp_path: Path) -> None:
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
    async def test_save_uses_atomic_write(self, tmp_path: Path) -> None:
        """`_save` must route through ``atomic_write_text`` (CH-02).

        A torn write would otherwise leave a half-formed candidate that
        the loader could either reject as invalid or silently parse as a
        partial strategy on the next pass.
        """
        from unittest.mock import patch

        improver, _ = make_improver(tmp_path, GOOD_RESPONSE)
        with patch("src.ai.improver.atomic_write_text") as mock_atomic:
            await improver.generate_idea()
            assert mock_atomic.called
            call_args = mock_atomic.call_args
            assert isinstance(call_args[0][0], Path)
            assert call_args[0][0].suffix == ".md"
            assert "name:" in call_args[0][1] or "rsi_divergence_v2" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_filename_slug_strips_unsafe_chars(self, tmp_path: Path) -> None:
        """Names with spaces / slashes become safe filename stems."""
        response = (
            "```markdown\n"
            "---\n"
            "name: Weird/Name With Spaces!\n"
            "version: 0.1.0\n"
            "description: test\n"
            "technique_type: prompt\n"
            "hypothesis: Strange names still represent a falsifiable reversal setup.\n"
            "---\n"
            "body\n\n"
            "## Output Contract\n"
            "Return JSON keys: signal, entry_price, stop_loss, take_profit.\n"
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
        assert "indicator mashup" in prompt.lower() or ("RSI + MACD" in prompt)

    @pytest.mark.asyncio
    async def test_user_idea_prompt_extracts_hypothesis(self, tmp_path: Path) -> None:
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
    async def test_hypothesis_field_parsed_into_model(self, tmp_path: Path) -> None:
        improver, _ = make_improver(tmp_path, HYPOTHESIS_RESPONSE)
        gen = await improver.generate_idea()
        assert "Funding rate above 0.05%" in gen.hypothesis

    @pytest.mark.asyncio
    async def test_missing_hypothesis_is_rejected(self, tmp_path: Path) -> None:
        """Generated techniques without a falsifiable hypothesis are rejected."""
        response = GOOD_RESPONSE.replace(
            "hypothesis: RSI divergence with volume confirmation predicts "
            "short-term reversal after exhaustion.\n",
            "",
        )
        improver, _ = make_improver(tmp_path, response)
        with pytest.raises(GeneratedTechniqueError, match="hypothesis"):
            await improver.generate_idea()


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


# =============================================================================
# Catalog injection (priority matrix integration)
# =============================================================================


CATALOG_MARKER = "RANK_1_CATALOG_TECHNIQUE_42"
SAMPLE_CATALOG = (
    "# Strategy Priority Matrix\n\n"
    "| rank | technique | composite |\n"
    "|---|---|---|\n"
    f"| 1 | {CATALOG_MARKER} | 20 |\n"
    "| 2 | Donchian System 2 | 19 |\n"
)


def _write_catalog(tmp_path: Path, content: str = SAMPLE_CATALOG) -> Path:
    catalog = tmp_path / "00-priority-matrix.md"
    catalog.write_text(content, encoding="utf-8")
    return catalog


class TestCatalogInjection:
    """The reference catalog should reach the new_idea prompt when the
    file exists, and be silently omitted otherwise. The user_idea and
    improvement prompts are intentionally untouched: user_idea is
    structured around the user's described idea (the catalog would
    redirect Claude away from the user's intent), and improvement
    (FR-022) is a focused failure-mode analysis on one specific
    technique."""

    @pytest.mark.asyncio
    async def test_catalog_injected_in_new_idea(self, tmp_path: Path) -> None:
        catalog = _write_catalog(tmp_path)
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE, catalog_path=catalog)
        await improver.generate_idea(context="anything")
        prompt = claude.complete.await_args.args[0]
        assert CATALOG_MARKER in prompt
        assert "Reference Catalog" in prompt

    @pytest.mark.asyncio
    async def test_catalog_not_in_user_idea_prompt(self, tmp_path: Path) -> None:
        """User-idea is anchored on the user's text; injecting the
        catalog would push Claude toward catalog entries instead of
        the user's intent. Regression guard."""
        catalog = _write_catalog(tmp_path)
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE, catalog_path=catalog)
        await improver.generate_from_user_idea("scalp BTC")
        prompt = claude.complete.await_args.args[0]
        assert CATALOG_MARKER not in prompt
        assert "Reference Catalog" not in prompt

    @pytest.mark.asyncio
    async def test_catalog_absent_graceful(self, tmp_path: Path) -> None:
        """Missing catalog file → empty section, prompt still works."""
        improver, claude = make_improver(
            tmp_path,
            GOOD_RESPONSE,
            catalog_path=tmp_path / "does_not_exist.md",
        )
        await improver.generate_idea()
        prompt = claude.complete.await_args.args[0]
        assert "Reference Catalog" not in prompt
        assert CATALOG_MARKER not in prompt

    @pytest.mark.asyncio
    async def test_catalog_not_in_improvement_prompt(self, tmp_path: Path) -> None:
        """Improvement is targeted at one technique; the catalog menu
        would be off-topic and waste the prompt budget."""
        catalog = _write_catalog(tmp_path)
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE, catalog_path=catalog)
        await improver.suggest_improvement(
            technique=sample_technique(),
            original_source="ORIGINAL_SOURCE_MARKER",
            performance=sample_performance(),
            records=sample_records(),
        )
        prompt = claude.complete.await_args.args[0]
        assert CATALOG_MARKER not in prompt
        assert "Reference Catalog" not in prompt

    @pytest.mark.asyncio
    async def test_catalog_not_in_code_type_prompt(self, tmp_path: Path) -> None:
        """Code-type picks already carry selected catalog context.

        Injecting the full priority matrix makes the Fly operator prompt
        large enough to timeout before candidate generation starts.
        """
        catalog = _write_catalog(tmp_path)
        improver, claude = make_improver(
            tmp_path,
            GOOD_CODE_RESPONSE,
            catalog_path=catalog,
        )
        await improver.generate_idea(context="Donchian System 2", code_type=True)

        prompt = claude.complete.await_args.args[0]
        assert "Donchian System 2" in prompt
        assert CATALOG_MARKER not in prompt
        assert "Reference Catalog" not in prompt

    @pytest.mark.asyncio
    async def test_catalog_cached_on_repeated_calls(self, tmp_path: Path) -> None:
        """The catalog file is read at most once per improver instance."""
        catalog = _write_catalog(tmp_path)
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE, catalog_path=catalog)
        await improver.generate_idea()
        # Mutate the file on disk; cache should still serve old content.
        catalog.write_text("MUTATED_CONTENT", encoding="utf-8")
        await improver.generate_idea()
        second_prompt = claude.complete.await_args.args[0]
        assert CATALOG_MARKER in second_prompt
        assert "MUTATED_CONTENT" not in second_prompt

    def test_default_catalog_path_constant(self) -> None:
        """The default path matches the repo's matrix location."""
        from src.ai.improver import DEFAULT_CATALOG_PATH

        assert DEFAULT_CATALOG_PATH == Path(
            "docs/research/strategies/00-priority-matrix.md"
        )


class TestNewIdeaOutputContract:
    """Phase 17.2 / DEBT-019 — ``_build_new_idea_prompt`` must mandate
    the runtime JSON Output Contract so generated ``prompt``-type
    technique bodies are actually runnable. The user-idea and
    improvement prompts are intentionally untouched: user-idea is
    anchored on the user's text, and improvement is a focused
    failure-mode analysis on one specific technique. Mirrors the
    structure of ``TestCatalogInjection``."""

    @pytest.mark.asyncio
    async def test_new_idea_prompt_contains_output_contract(
        self, tmp_path: Path
    ) -> None:
        """The Output Contract instruction and all four mandatory JSON
        schema keys (signal, entry_price, stop_loss, take_profit)
        must appear in the new-idea prompt so Claude produces a
        body that the per-bar parser can actually consume."""
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        await improver.generate_idea(context="anything")
        prompt = claude.complete.await_args.args[0]
        assert "Output Contract" in prompt
        # The four schema keys the runtime parser requires verbatim.
        assert '"signal"' in prompt
        assert '"entry_price"' in prompt
        assert '"stop_loss"' in prompt
        assert '"take_profit"' in prompt

    @pytest.mark.asyncio
    async def test_user_idea_prompt_contains_output_contract(
        self, tmp_path: Path
    ) -> None:
        """User-idea generations still need the runtime JSON contract."""
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        await improver.generate_from_user_idea("scalp BTC")
        prompt = claude.complete.await_args.args[0]
        assert "Output Contract" in prompt
        assert '"signal"' in prompt
        assert '"entry_price"' in prompt
        assert '"stop_loss"' in prompt
        assert '"take_profit"' in prompt

    @pytest.mark.asyncio
    async def test_markdown_code_type_still_requires_output_contract(
        self, tmp_path: Path
    ) -> None:
        """Markdown output is runtime prompt input even if frontmatter says code."""
        improver, _ = make_improver(tmp_path, MARKDOWN_CODE_WITHOUT_OUTPUT_CONTRACT)

        with pytest.raises(GeneratedTechniqueError, match="Output Contract"):
            await improver.generate_idea(context="anything")

    @pytest.mark.asyncio
    async def test_improvement_prompt_omits_output_contract(
        self, tmp_path: Path
    ) -> None:
        """Improvement is targeted failure-mode analysis on one
        existing technique; the original technique already carries
        its own runtime contract, so re-injecting the new-idea
        Output Contract here would be off-topic. Regression guard."""
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        await improver.suggest_improvement(
            technique=sample_technique(),
            original_source="ORIGINAL_SOURCE_MARKER",
            performance=sample_performance(),
            records=sample_records(),
        )
        prompt = claude.complete.await_args.args[0]
        assert "Output Contract" not in prompt


class TestImprovementOutputContract:
    """DEBT-023 — improvement generations must preserve an existing
    runtime Output Contract instead of silently accepting a body that
    reintroduces prompt-type parse failures."""

    @pytest.mark.asyncio
    async def test_improvement_preserves_existing_output_contract(
        self, tmp_path: Path
    ) -> None:
        improver, _ = make_improver(tmp_path, IMPROVEMENT_WITH_OUTPUT_CONTRACT)

        generated = await improver.suggest_improvement(
            technique=sample_technique(),
            original_source=ORIGINAL_WITH_OUTPUT_CONTRACT,
            performance=sample_performance(),
            records=sample_records(),
            save=False,
        )

        assert "## Output Contract" in generated.content
        assert '"signal"' in generated.content
        assert '"entry_price"' in generated.content
        assert '"stop_loss"' in generated.content
        assert '"take_profit"' in generated.content

    @pytest.mark.asyncio
    async def test_improvement_rejects_dropped_output_contract(
        self, tmp_path: Path
    ) -> None:
        improver, _ = make_improver(tmp_path, IMPROVEMENT_WITHOUT_OUTPUT_CONTRACT)

        with pytest.raises(GeneratedTechniqueError, match="Output Contract"):
            await improver.suggest_improvement(
                technique=sample_technique(),
                original_source=ORIGINAL_WITH_OUTPUT_CONTRACT,
                performance=sample_performance(),
                records=sample_records(),
            )

        assert not improver.experimental_dir.exists()

    @pytest.mark.asyncio
    async def test_improvement_rejects_missing_contract_key(
        self, tmp_path: Path
    ) -> None:
        improver, _ = make_improver(
            tmp_path, IMPROVEMENT_WITH_OUTPUT_CONTRACT_MISSING_KEY
        )

        with pytest.raises(GeneratedTechniqueError, match="take_profit"):
            await improver.suggest_improvement(
                technique=sample_technique(),
                original_source=ORIGINAL_WITH_OUTPUT_CONTRACT,
                performance=sample_performance(),
                records=sample_records(),
            )


# =============================================================================
# Phase 17.5 / DEBT-019 Option B — code-type generation branch
# =============================================================================


# A Claude response that emits a Python ``BaseStrategy`` subclass under
# a fenced ``python`` block. Mirrors the canonical shape of
# ``strategies/rsi.py`` (TECHNIQUE_INFO dict + class with async analyze).
GOOD_CODE_RESPONSE = '''\
```python
"""Donchian breakout — code-type fixture (Phase 17.5)."""

from datetime import datetime
from decimal import Decimal

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, TechniqueInfo

TECHNIQUE_INFO = {
    "name": "donchian_fixture",
    "version": "0.1.0",
    "description": "Donchian breakout fixture",
    "author": "system",
    "hypothesis": "Donchian channel compression predicts continuation breakouts in liquid crypto pairs.",
    "symbols": ["BTC/USDT"],
    "timeframes": ["1h"],
    "status": "experimental",
    "changelog": "fixture",
}


class DonchianFixtureStrategy(BaseStrategy):
    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
    ) -> AnalysisResult:
        self.validate_input(ohlcv, min_candles=20)
        price = float(ohlcv[-1].close)
        return AnalysisResult(
            signal="neutral",
            confidence=0.3,
            entry_price=Decimal(str(round(price, 2))),
            stop_loss=Decimal(str(round(price * 0.99, 2))),
            take_profit=Decimal(str(round(price * 1.01, 2))),
            reasoning="fixture",
            timestamp=datetime.now(),
        )
```
'''


class TestCodeTypeNewIdea:
    """Phase 17.5 / DEBT-019 Option B — ``generate_idea(code_type=True)``
    must select the Python ``BaseStrategy`` code-generation prompt and
    write a ``.py`` file. The default (``code_type=False``) still rides
    the historical markdown path so the 17.4-hardened prompt is the
    default.
    """

    @pytest.mark.asyncio
    async def test_code_type_prompt_targets_basestrategy_subclass(
        self, tmp_path: Path
    ) -> None:
        """The code-type prompt must instruct Claude to emit a Python
        ``BaseStrategy`` subclass with the canonical shape. The async
        ``analyze`` method (NOT a sync ``signal()``) is the actual
        ``BaseStrategy`` interface — the prompt must ask for that.
        References to the canonical baseline files steer Claude toward
        the in-repo template rather than inventing a foreign shape.
        """
        improver, claude = make_improver(tmp_path, GOOD_CODE_RESPONSE)
        await improver.generate_idea(context="Donchian", code_type=True)
        prompt = claude.complete.await_args.args[0]
        assert "BaseStrategy" in prompt
        assert "analyze" in prompt
        # Canonical baseline file references — the prompt names them so
        # Claude mirrors their TECHNIQUE_INFO + class shape rather than
        # inventing a foreign one.
        assert "strategies/rsi.py" in prompt
        assert "strategies/ma_crossover.py" in prompt
        assert "strategies/bollinger_bands.py" in prompt
        # Code-only fence instruction: response must be a ``python``
        # block, not a ``markdown`` one.
        assert "python" in prompt.lower()
        assert "TECHNIQUE_INFO" in prompt

    @pytest.mark.asyncio
    async def test_default_path_omits_code_only_strings(self, tmp_path: Path) -> None:
        """``code_type=False`` (the default) keeps the historical
        markdown path; the code-only instruction strings must NOT
        appear there. Regression guard against accidental cross-
        contamination of the two prompt branches.
        """
        improver, claude = make_improver(tmp_path, GOOD_RESPONSE)
        await improver.generate_idea(context="anything")
        prompt = claude.complete.await_args.args[0]
        # Markdown path mentions the format in passing ("technique_type:
        # either prompt or code"), but it MUST NOT instruct Claude to
        # emit a BaseStrategy subclass or reference the canonical .py
        # baselines — those belong to the code branch.
        assert "BaseStrategy" not in prompt
        assert "strategies/rsi.py" not in prompt
        assert "strategies/ma_crossover.py" not in prompt
        assert "strategies/bollinger_bands.py" not in prompt
        assert "TECHNIQUE_INFO" not in prompt

    @pytest.mark.asyncio
    async def test_code_type_writes_py_file(self, tmp_path: Path) -> None:
        """A ``code_type=True`` generation must land on disk as a
        ``.py`` file, with the Python source body — not a ``.md``
        wrapping. The ``output_kind`` field on the returned
        ``GeneratedTechnique`` mirrors that.
        """
        improver, _ = make_improver(tmp_path, GOOD_CODE_RESPONSE)
        gen = await improver.generate_idea(code_type=True)
        assert gen.output_kind == "python"
        assert gen.saved_path is not None
        assert gen.saved_path.suffix == ".py"
        body = gen.saved_path.read_text(encoding="utf-8")
        assert "class DonchianFixtureStrategy(BaseStrategy)" in body
        assert "TECHNIQUE_INFO" in body
        # Metadata extracted from the literal TECHNIQUE_INFO dict via
        # ast.literal_eval — never executes the module.
        assert gen.name == "donchian_fixture"
        assert gen.version == "0.1.0"

    @pytest.mark.asyncio
    async def test_code_type_rejects_top_level_side_effect(
        self, tmp_path: Path
    ) -> None:
        """Generated code with top-level side effects is rejected before save."""
        hostile_response = (
            "```python\n"
            "raise RuntimeError('module-level side effect')\n\n"
            "TECHNIQUE_INFO = {\n"
            '    "name": "hostile",\n'
            '    "version": "0.1.0",\n'
            '    "description": "should still parse",\n'
            '    "hypothesis": "Side effects should never be needed for a signal.",\n'
            "}\n"
            "```\n"
        )
        improver, _ = make_improver(tmp_path, hostile_response)
        with pytest.raises(GeneratedTechniqueError, match="top-level"):
            await improver.generate_idea(code_type=True)

    @pytest.mark.asyncio
    async def test_code_type_rejects_banned_io_import(self, tmp_path: Path) -> None:
        hostile_response = GOOD_CODE_RESPONSE.replace(
            "from decimal import Decimal\n",
            "from decimal import Decimal\nimport subprocess\n",
        )
        improver, _ = make_improver(tmp_path, hostile_response)
        with pytest.raises(GeneratedTechniqueError, match="banned import"):
            await improver.generate_idea(code_type=True)

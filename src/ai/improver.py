"""Claude-based analysis technique improvement and generation.

Turns performance data or a user's idea into a new candidate
technique file under ``strategies/experimental/``. Subsequent
backtests and the feedback loop can then promote or discard
candidates.

Related Requirements:
- FR-022: Technique Improvement Suggestion (Claude)
- FR-023: New Technique Idea Generation
- FR-024: User Idea Input
- NFR-002: Claude CLI Integration (never Anthropic API directly)
- NFR-005: Analysis Technique Storage (md / py files)
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from src.ai.claude import ClaudeCLI
from src.ai.exceptions import ClaudeParseError
from src.logger import get_logger
from src.strategy.base import TechniqueInfo
from src.strategy.performance import PerformanceRecord, TechniquePerformance

logger = get_logger("crypto_master.ai.improver")


DEFAULT_EXPERIMENTAL_DIR = Path("strategies/experimental")

# Matches a fenced code block whose info string is ``markdown`` /
# ``md`` / empty. Captures the body.
_MARKDOWN_BLOCK_PATTERN = re.compile(
    r"```(?:markdown|md)?\s*\n(.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)

# Matches YAML frontmatter at the start of a markdown document.
_FRONTMATTER_PATTERN = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n",
    re.DOTALL,
)

GenerationKind = Literal["improvement", "new_idea", "user_idea"]


class StrategyImproverError(Exception):
    """Base exception for StrategyImprover errors."""

    pass


class GeneratedTechniqueError(StrategyImproverError):
    """Raised when Claude's response cannot be parsed into a technique."""

    pass


class GeneratedTechnique(BaseModel):
    """A candidate technique produced by Claude.

    Attributes:
        name: Technique name (from frontmatter, falls back to
            ``fallback_name`` if absent).
        version: Version string from frontmatter (defaults to "0.1.0").
        description: Description from frontmatter (may be empty).
        kind: Why this was generated (improvement vs. new idea).
        parent_technique: For improvements, the name of the original.
        content: Full markdown content (including any frontmatter).
        suggested_filename: File stem + extension relative to
            ``experimental_dir``.
        saved_path: Path the file was written to, or None if ``save``
            was False.
        raw_response: Unparsed CLI output, kept for debugging.
    """

    name: str
    version: str = "0.1.0"
    description: str = ""
    hypothesis: str = ""
    kind: GenerationKind
    parent_technique: str | None = None
    content: str
    suggested_filename: str
    saved_path: Path | None = None
    raw_response: str = Field(default="", repr=False)

    model_config = {"arbitrary_types_allowed": True}


class StrategyImprover:
    """Drives Claude to propose technique improvements and new ideas.

    All three flows share the same pipeline:

    1. Build a prompt tailored to the flow (improvement / new idea /
       user idea).
    2. Call ``ClaudeCLI.complete`` for a raw markdown response.
    3. Extract the fenced ``markdown`` block, parse its frontmatter.
    4. Optionally save the result to
       ``strategies/experimental/{slug}_{timestamp}.md`` so multiple
       generations never clobber each other.

    Related Requirements:
    - FR-022, FR-023, FR-024, NFR-002, NFR-005
    """

    def __init__(
        self,
        claude: ClaudeCLI | None = None,
        experimental_dir: Path | None = None,
    ) -> None:
        """Initialize the improver.

        Args:
            claude: Optional pre-built ClaudeCLI instance (useful for
                tests). Defaults to a fresh ``ClaudeCLI()``.
            experimental_dir: Directory where generated techniques are
                written. Defaults to ``strategies/experimental/``.
        """
        self.claude = claude or ClaudeCLI()
        self.experimental_dir = experimental_dir or DEFAULT_EXPERIMENTAL_DIR

    # ------------------------------------------------------------------
    # Public flows
    # ------------------------------------------------------------------

    async def suggest_improvement(
        self,
        technique: TechniqueInfo,
        original_source: str,
        performance: TechniquePerformance,
        records: list[PerformanceRecord] | None = None,
        save: bool = True,
    ) -> GeneratedTechnique:
        """Ask Claude to propose an improved revision of a technique.

        Args:
            technique: Metadata for the technique being revised.
            original_source: The current technique file's text.
            performance: Aggregate stats for the technique.
            records: Optional recent performance records for context.
            save: If True, write the result to ``experimental_dir``.

        Returns:
            The parsed ``GeneratedTechnique``.

        Raises:
            GeneratedTechniqueError: If the response cannot be parsed.
            ClaudeError: If the CLI call fails.
        """
        prompt = self._build_improvement_prompt(
            technique=technique,
            original_source=original_source,
            performance=performance,
            records=records or [],
        )
        return await self._run(
            prompt=prompt,
            kind="improvement",
            parent=technique.name,
            fallback_name=f"{technique.name}_improved",
            save=save,
        )

    async def generate_idea(
        self,
        context: str = "",
        save: bool = True,
    ) -> GeneratedTechnique:
        """Ask Claude to invent a brand-new technique.

        Args:
            context: Optional steering context (e.g. "focus on mean
                reversion on 1h timeframes"). Empty = fully open.
            save: If True, write to ``experimental_dir``.

        Returns:
            The parsed ``GeneratedTechnique``.
        """
        prompt = self._build_new_idea_prompt(context)
        return await self._run(
            prompt=prompt,
            kind="new_idea",
            parent=None,
            fallback_name="new_idea",
            save=save,
        )

    async def generate_from_user_idea(
        self,
        user_idea: str,
        save: bool = True,
    ) -> GeneratedTechnique:
        """Turn free-form user text into a structured technique file.

        Args:
            user_idea: The user's natural-language description.
            save: If True, write to ``experimental_dir``.

        Returns:
            The parsed ``GeneratedTechnique``.

        Raises:
            StrategyImproverError: If ``user_idea`` is empty/whitespace.
        """
        if not user_idea.strip():
            raise StrategyImproverError("user_idea must not be empty")
        prompt = self._build_user_idea_prompt(user_idea)
        return await self._run(
            prompt=prompt,
            kind="user_idea",
            parent=None,
            fallback_name="user_idea",
            save=save,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _run(
        self,
        prompt: str,
        kind: GenerationKind,
        parent: str | None,
        fallback_name: str,
        save: bool,
    ) -> GeneratedTechnique:
        """Execute a prompt + parse + optionally save."""
        raw = await self.claude.complete(prompt)
        generated = self._parse_response(
            raw=raw,
            kind=kind,
            parent=parent,
            fallback_name=fallback_name,
        )
        if save:
            path = self._save(generated)
            generated = generated.model_copy(update={"saved_path": path})
            logger.info(
                f"Saved generated technique '{generated.name}' ({kind}) "
                f"to {path}"
            )
        return generated

    def _parse_response(
        self,
        raw: str,
        kind: GenerationKind,
        parent: str | None,
        fallback_name: str,
    ) -> GeneratedTechnique:
        """Extract the markdown block and parse frontmatter."""
        match = _MARKDOWN_BLOCK_PATTERN.search(raw)
        if match is None:
            # Fall back to using the whole body verbatim if there's no
            # fenced block — Claude sometimes replies with bare markdown.
            content = raw.strip()
        else:
            content = match.group(1).strip()

        if not content:
            raise GeneratedTechniqueError(
                "Claude returned no technique content"
            )

        fm = self._parse_frontmatter(content)
        name = fm.get("name") or fallback_name
        version = fm.get("version", "0.1.0")
        description = fm.get("description", "")
        hypothesis = fm.get("hypothesis", "")

        suggested_filename = self._build_filename(name)

        return GeneratedTechnique(
            name=str(name),
            version=str(version),
            description=str(description),
            hypothesis=str(hypothesis),
            kind=kind,
            parent_technique=parent,
            content=content,
            suggested_filename=suggested_filename,
            raw_response=raw,
        )

    @staticmethod
    def _parse_frontmatter(content: str) -> dict[str, object]:
        """Extract YAML frontmatter from a markdown document.

        Returns an empty dict if no frontmatter is present or if YAML
        parsing fails. The improver only reads the frontmatter for
        metadata — the file content is always preserved verbatim.
        """
        match = _FRONTMATTER_PATTERN.match(content)
        if match is None:
            return {}
        try:
            parsed = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse generated frontmatter: {e}")
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    def _build_filename(self, name: str) -> str:
        """Build a filesystem-safe filename for a generated technique.

        Includes a UTC timestamp so repeated generations don't clobber
        earlier outputs. Slugification strips everything except
        alphanumerics, hyphens, and underscores.
        """
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_") or "technique"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{slug}_{timestamp}.md"

    def _save(self, generated: GeneratedTechnique) -> Path:
        """Write a generated technique to disk."""
        self.experimental_dir.mkdir(parents=True, exist_ok=True)
        path = self.experimental_dir / generated.suggested_filename
        path.write_text(generated.content, encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    @staticmethod
    def _output_format_instructions() -> str:
        """Boilerplate telling Claude how to format its reply."""
        return (
            "OUTPUT FORMAT\n"
            "Respond ONLY with a single fenced markdown code block "
            "labeled ``markdown`` containing the full technique file. "
            "The file must start with YAML frontmatter delimited by "
            "`---` lines and containing at minimum:\n"
            "- name: short snake_case identifier\n"
            "- version: semantic version string\n"
            '- description: single line of description\n'
            '- technique_type: either "prompt" or "code"\n'
            "- hypothesis: ONE sentence stating the specific market "
            "inefficiency or behavior this technique exploits, phrased "
            "so it could be falsified by data (e.g. \"funding rate "
            "above the 95th percentile predicts a mean-reverting move "
            "within 8 hours\"). This is mandatory — a technique with "
            "no falsifiable hypothesis will be rejected.\n"
            "\nAfter the frontmatter, include the prompt/logic body. "
            "Do not wrap it in additional commentary."
        )

    def _build_improvement_prompt(
        self,
        technique: TechniqueInfo,
        original_source: str,
        performance: TechniquePerformance,
        records: list[PerformanceRecord],
    ) -> str:
        """Construct the improvement prompt (FR-022)."""
        perf_summary = (
            f"- Total trades: {performance.total_trades}\n"
            f"- Wins: {performance.wins}\n"
            f"- Losses: {performance.losses}\n"
            f"- Win rate: {performance.win_rate:.2%}\n"
            f"- Average P&L %: {performance.avg_pnl_percent:.2f}\n"
            f"- Total P&L %: {performance.total_pnl_percent:.2f}\n"
            f"- Best trade P&L %: {performance.best_trade_pnl:.2f}\n"
            f"- Worst trade P&L %: {performance.worst_trade_pnl:.2f}"
        )

        records_block = self._format_records(records[-10:]) if records else (
            "(no detailed records supplied)"
        )

        suggested_name = f"{technique.name}_v2"
        return (
            "You are a quantitative trading strategy engineer "
            "diagnosing why an existing technique is underperforming. "
            "Your goal is NOT to fit the historical losses away — that "
            "produces overfit garbage. Your goal is to identify the "
            "structural reason the technique fails, then propose a "
            "principled change that addresses that root cause.\n\n"
            f"## Original Technique\n"
            f"- Name: {technique.name}\n"
            f"- Version: {technique.version}\n"
            f"- Description: {technique.description}\n\n"
            "### Source\n"
            f"{original_source.strip()}\n\n"
            "## Performance\n"
            f"{perf_summary}\n\n"
            "## Recent Trades\n"
            f"{records_block}\n\n"
            "## Required Reasoning Process\n"
            "Before writing the revised technique, work through these "
            "steps in your reply (inside the markdown body, as a "
            "## Failure Analysis section at the top):\n"
            "1. Identify 2-3 SPECIFIC failure modes visible in the "
            "losing trades (e.g. \"entered counter-trend during strong "
            "momentum\", \"stops too tight relative to ATR\", "
            "\"signal fires equally in trending and ranging regimes\").\n"
            "2. For each failure mode, state the structural reason it "
            "happens — not just the symptom.\n"
            "3. Propose ONE targeted change per failure mode. Avoid "
            "stacking many small filters (that is overfitting); prefer "
            "one principled rule per problem.\n\n"
            "## Hard Constraints\n"
            "- Do NOT add lookback-specific thresholds tuned to the "
            "exact trades shown (e.g. \"avoid trading on Tuesdays\" "
            "because two losses happened on a Tuesday).\n"
            "- Do NOT add more than 2 new conditions total. Simpler "
            "rules generalize better.\n"
            "- Every new rule must be justifiable from a market-"
            "structure argument, not just \"it would have avoided the "
            "losses above.\"\n"
            "- The hypothesis in frontmatter must reflect what the "
            "REVISED technique exploits, not the original.\n\n"
            f"Use name=\"{suggested_name}\" (or similar) and bump the "
            "version above the original.\n\n"
            + self._output_format_instructions()
        )

    def _build_new_idea_prompt(self, context: str) -> str:
        """Construct the new-idea prompt (FR-023)."""
        context_line = (
            f"Context / steering: {context.strip()}\n\n"
            if context.strip()
            else ""
        )
        return (
            "You are a quantitative trading strategy engineer "
            "designing a new technique for crypto markets (BTC/USDT "
            "and major altcoins). Your standard is high: most "
            "indicator-combination strategies (RSI + MACD + moving "
            "average crossovers, etc.) have no edge after fees and "
            "slippage because they exploit nothing the rest of the "
            "market hasn't already arbitraged. Do not propose those.\n\n"
            "## What constitutes a valid technique\n"
            "Start from a SPECIFIC, FALSIFIABLE hypothesis about a "
            "structural inefficiency or behavioral pattern in crypto "
            "markets. Examples of the KIND of hypothesis that is "
            "acceptable (do not copy these — invent your own):\n"
            "- Funding rate extremes on perpetuals predict short-term "
            "mean reversion because over-leveraged longs/shorts get "
            "liquidated.\n"
            "- After a large liquidation cascade, price tends to "
            "overshoot and revert within N hours.\n"
            "- Open interest divergence vs. price signals positioning "
            "changes by informed traders.\n"
            "- Cross-exchange basis spreads above a threshold revert "
            "as arbitrageurs close the gap.\n"
            "- Stablecoin supply changes precede directional moves on "
            "BTC due to capital inflow/outflow.\n\n"
            "## What to AVOID\n"
            "- Generic indicator mashups (RSI + MACD + Bollinger, etc.) "
            "with no underlying market-structure reason.\n"
            "- Pattern-recognition heuristics (\"head and shoulders\", "
            "\"triangle breakout\") without a quantified edge.\n"
            "- More than 3 conditions for entry — complexity is a "
            "red flag for overfitting risk.\n"
            "- Hypotheses you cannot describe a falsifying experiment "
            "for.\n\n"
            "## Output requirement\n"
            "If your hypothesis requires data the system may not have "
            "(e.g. funding rate, on-chain flows, liquidation feed), "
            "say so explicitly in the body under a ## Data Requirements "
            "section, naming the data source. Do not silently assume "
            "it is available.\n\n"
            f"{context_line}"
            + self._output_format_instructions()
        )

    def _build_user_idea_prompt(self, user_idea: str) -> str:
        """Construct the user-idea prompt (FR-024)."""
        return (
            "You are a quantitative trading strategy engineer. "
            "A user has proposed the following idea:\n\n"
            '"""\n'
            f"{user_idea.strip()}\n"
            '"""\n\n'
            "Expand this idea into a complete analysis technique "
            "suitable for automated execution. Fill in any missing "
            "specifics (entry, stop-loss, take-profit logic) while "
            "staying faithful to the user's intent.\n\n"
            "## Required: extract the hypothesis\n"
            "Before writing the technique body, articulate the "
            "underlying hypothesis the user's idea implicitly assumes "
            "— what market behavior or inefficiency must be true for "
            "this to be profitable? Put it in the frontmatter "
            "`hypothesis` field as one falsifiable sentence.\n\n"
            "If the user's idea has no plausible underlying edge "
            "(e.g. it's a generic indicator mashup), still produce "
            "the technique faithfully but say so honestly in a "
            "## Caveats section at the end of the body, naming the "
            "specific concern. Do not silently \"fix\" their idea.\n\n"
            "## Constraints\n"
            "- Do not add filters or conditions the user did not ask "
            "for, beyond the minimum needed for safe execution "
            "(stop-loss, position sizing).\n"
            "- If the idea requires data the system may not have, "
            "list it in a ## Data Requirements section.\n\n"
            + self._output_format_instructions()
        )

    @staticmethod
    def _format_records(records: list[PerformanceRecord]) -> str:
        """Render performance records as a compact list."""
        if not records:
            return "(none)"
        lines = []
        for r in records:
            outcome = r.outcome.value if hasattr(r.outcome, "value") else r.outcome
            pnl = f"{r.pnl_percent:.2f}%" if r.pnl_percent is not None else "pending"
            lines.append(
                f"- {r.symbol} {r.timeframe} signal={r.signal} "
                f"outcome={outcome} pnl={pnl}"
            )
        return "\n".join(lines)


# Re-export the ClaudeParseError so callers only need to import from
# this module for the improver flow.
__all__ = [
    "StrategyImprover",
    "StrategyImproverError",
    "GeneratedTechniqueError",
    "GeneratedTechnique",
    "DEFAULT_EXPERIMENTAL_DIR",
    "ClaudeParseError",
]

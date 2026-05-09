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

import ast
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from src.ai.claude import ClaudeCLI
from src.ai.exceptions import ClaudeParseError
from src.logger import get_logger
from src.strategy.base import StrategyValidationError, TechniqueInfo
from src.strategy.loader import validate_python_strategy_source
from src.strategy.performance import PerformanceRecord, TechniquePerformance
from src.strategy.trade_autopsy import TradeAutopsy
from src.utils.io import atomic_write_text
from src.utils.time import now_utc

logger = get_logger("crypto_master.ai.improver")


DEFAULT_EXPERIMENTAL_DIR = Path("strategies/experimental")
DEFAULT_CATALOG_PATH = Path("docs/research/strategies/00-priority-matrix.md")

# Matches a fenced code block whose info string is ``markdown`` /
# ``md`` / empty. Captures the body.
_MARKDOWN_BLOCK_PATTERN = re.compile(
    r"```(?:markdown|md)?\s*\n(.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)

# Matches a fenced code block whose info string is ``python`` / ``py``.
# Captures the body for the Phase 17.5 code-type generation path.
_PYTHON_BLOCK_PATTERN = re.compile(
    r"```(?:python|py)\s*\n(.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)

# Matches YAML frontmatter at the start of a markdown document.
_FRONTMATTER_PATTERN = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n",
    re.DOTALL,
)

GenerationKind = Literal["improvement", "new_idea", "user_idea"]

# Phase 17.5 / DEBT-019 Option B — file kind the improver should write.
# ``markdown`` is the historical path (prompt-type ``.md`` techniques);
# ``python`` is the code-type ``BaseStrategy`` subclass path used for
# deterministic catalog picks (Donchian, Supertrend, Z-score, …) so the
# resulting backtest never invokes the Claude CLI per bar.
OutputKind = Literal["markdown", "python"]


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
    # Phase 17.5: ``markdown`` for the historical prompt-type ``.md``
    # path; ``python`` for the code-type ``.py`` (``BaseStrategy``
    # subclass) path. Defaults to ``markdown`` to keep all existing call
    # sites byte-identical.
    output_kind: OutputKind = "markdown"

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
        catalog_path: Path | None = None,
    ) -> None:
        """Initialize the improver.

        Args:
            claude: Optional pre-built ClaudeCLI instance (useful for
                tests). Defaults to a fresh ``ClaudeCLI()``.
            experimental_dir: Directory where generated techniques are
                written. Defaults to ``strategies/experimental/``.
            catalog_path: Path to the strategy priority matrix
                (synthesis of researched techniques). Injected into the
                ``new_idea`` and ``user_idea`` prompts so Claude can
                draw from a curated, scored menu rather than inventing
                from scratch. Optional — if the file is missing, the
                improver still works, the prompts just omit the
                catalog. Defaults to
                ``docs/research/strategies/00-priority-matrix.md``.
        """
        self.claude = claude or ClaudeCLI()
        self.experimental_dir = experimental_dir or DEFAULT_EXPERIMENTAL_DIR
        self.catalog_path = catalog_path or DEFAULT_CATALOG_PATH
        self._catalog_cache: str | None = None

    # ------------------------------------------------------------------
    # Public flows
    # ------------------------------------------------------------------

    async def suggest_improvement(
        self,
        technique: TechniqueInfo,
        original_source: str,
        performance: TechniquePerformance,
        records: list[PerformanceRecord] | None = None,
        autopsies: list[TradeAutopsy] | None = None,
        save: bool = True,
    ) -> GeneratedTechnique:
        """Ask Claude to propose an improved revision of a technique.

        Args:
            technique: Metadata for the technique being revised.
            original_source: The current technique file's text.
            performance: Aggregate stats for the technique.
            records: Optional recent performance records for context.
            autopsies: Optional post-trade diagnostic summaries.
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
            autopsies=autopsies or [],
        )
        generated = await self._run(
            prompt=prompt,
            kind="improvement",
            parent=technique.name,
            fallback_name=f"{technique.name}_improved",
            save=False,
        )
        self._validate_improvement_preserves_output_contract(
            original_source=original_source,
            generated_content=generated.content,
        )
        if save:
            path = self._save(generated)
            generated = generated.model_copy(update={"saved_path": path})
            logger.info(
                "Saved generated technique "
                f"'{generated.name}' (improvement) to {path}"
            )
        return generated

    async def generate_idea(
        self,
        context: str = "",
        save: bool = True,
        *,
        code_type: bool = False,
    ) -> GeneratedTechnique:
        """Ask Claude to invent a brand-new technique.

        Args:
            context: Optional steering context (e.g. "focus on mean
                reversion on 1h timeframes"). Empty = fully open.
            save: If True, write to ``experimental_dir``.
            code_type: Phase 17.5 / DEBT-019 Option B — when ``True``,
                instruct Claude to produce a Python ``BaseStrategy``
                subclass (``.py`` file) rather than a markdown prompt
                template (``.md`` file). Code-type strategies run
                locally per bar with no LLM in the hot path —
                deterministic and immune to JSON-contract drift, the
                cleanest path for catalog picks like Donchian /
                Supertrend / Z-score / NR7 / Connors RSI(2). Defaults
                to ``False`` so the historical prompt-type path is the
                default.

        Returns:
            The parsed ``GeneratedTechnique``.
        """
        if code_type:
            prompt = self._build_new_idea_code_prompt(context)
            output_kind: OutputKind = "python"
        else:
            prompt = self._build_new_idea_prompt(context)
            output_kind = "markdown"
        return await self._run(
            prompt=prompt,
            kind="new_idea",
            parent=None,
            fallback_name="new_idea",
            save=save,
            output_kind=output_kind,
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
        output_kind: OutputKind = "markdown",
    ) -> GeneratedTechnique:
        """Execute a prompt + parse + optionally save."""
        raw = await self.claude.complete(prompt)
        generated = self._parse_response(
            raw=raw,
            kind=kind,
            parent=parent,
            fallback_name=fallback_name,
            output_kind=output_kind,
        )
        if save:
            path = self._save(generated)
            generated = generated.model_copy(update={"saved_path": path})
            logger.info(
                f"Saved generated technique '{generated.name}' ({kind}) " f"to {path}"
            )
        return generated

    def _parse_response(
        self,
        raw: str,
        kind: GenerationKind,
        parent: str | None,
        fallback_name: str,
        output_kind: OutputKind = "markdown",
    ) -> GeneratedTechnique:
        """Extract the response block and metadata.

        For ``markdown`` output_kind the response is a fenced markdown
        block with YAML frontmatter at the top. For ``python`` output
        (Phase 17.5) the response is a fenced Python block whose source
        defines a ``TECHNIQUE_INFO`` dict and a ``BaseStrategy``
        subclass — metadata is read from the ``TECHNIQUE_INFO`` literal
        via :mod:`ast`, so no module is ever executed at parse time.
        """
        if output_kind == "python":
            match = _PYTHON_BLOCK_PATTERN.search(raw)
            if match is None:
                # Claude sometimes replies with bare Python and no
                # fence; treat the whole body as the source. Best-
                # effort: the loader will raise a clean error if it's
                # genuinely not Python.
                content = raw.strip()
            else:
                content = match.group(1).strip()
            if not content:
                raise GeneratedTechniqueError("Claude returned no technique content")
            try:
                validate_python_strategy_source(content)
            except StrategyValidationError as e:
                raise GeneratedTechniqueError(str(e)) from e
            metadata = self._extract_technique_info_from_python(content)
        else:
            match = _MARKDOWN_BLOCK_PATTERN.search(raw)
            if match is None:
                # Fall back to using the whole body verbatim if there's
                # no fenced block — Claude sometimes replies with bare
                # markdown.
                content = raw.strip()
            else:
                content = match.group(1).strip()
            if not content:
                raise GeneratedTechniqueError("Claude returned no technique content")
            metadata = self._parse_frontmatter(content)

        name = str(metadata.get("name") or fallback_name)
        version = str(metadata.get("version", "0.1.0"))
        description = str(metadata.get("description", ""))
        hypothesis = str(metadata.get("hypothesis", ""))
        if not hypothesis.strip():
            raise GeneratedTechniqueError(
                "Generated technique must include a falsifiable hypothesis."
            )
        self._validate_generated_runtime_contract(
            content=content,
            kind=kind,
            output_kind=output_kind,
            technique_type=str(metadata.get("technique_type", "")),
        )

        suggested_filename = self._build_filename(name, output_kind=output_kind)

        return GeneratedTechnique(
            name=name,
            version=version,
            description=description,
            hypothesis=hypothesis,
            kind=kind,
            parent_technique=parent,
            content=content,
            suggested_filename=suggested_filename,
            raw_response=raw,
            output_kind=output_kind,
        )

    @staticmethod
    def _validate_generated_runtime_contract(
        *,
        content: str,
        kind: GenerationKind,
        output_kind: OutputKind,
        technique_type: str,
    ) -> None:
        """Reject markdown techniques that cannot run per bar.

        Markdown files are executed through the prompt-strategy runtime path.
        A generated markdown technique that claims ``technique_type: code`` is
        still markdown on disk, so it must carry the same output contract.
        """
        if output_kind != "markdown" or kind not in {"new_idea", "user_idea"}:
            return
        required = (
            "## Output Contract",
            "signal",
            "entry_price",
            "stop_loss",
            "take_profit",
        )
        missing = [key for key in required if key not in content]
        if missing:
            keys = ", ".join(missing)
            raise GeneratedTechniqueError(
                f"Prompt technique missing runtime Output Contract keys: {keys}."
            )

    @staticmethod
    def _extract_technique_info_from_python(source: str) -> dict[str, object]:
        """Pull the ``TECHNIQUE_INFO`` dict literal out of a Python source.

        Uses :mod:`ast` so the file is *parsed*, never *executed* —
        there's no risk of a malformed (or hostile) generated file
        running side effects at metadata-extraction time. Returns an
        empty dict if the assignment is absent or its value is not a
        literal dict; the improver falls back to ``fallback_name`` /
        defaults in that case, mirroring the existing markdown
        frontmatter behavior.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            logger.warning(f"Failed to parse generated Python source: {e}")
            return {}
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
            if not any(t.id == "TECHNIQUE_INFO" for t in targets):
                continue
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                logger.warning(
                    "TECHNIQUE_INFO is not a literal dict; metadata "
                    "extraction fell back to defaults."
                )
                return {}
            if isinstance(value, dict):
                return {str(k): v for k, v in value.items()}
        return {}

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

    def _build_filename(self, name: str, output_kind: OutputKind = "markdown") -> str:
        """Build a filesystem-safe filename for a generated technique.

        Includes a UTC timestamp so repeated generations don't clobber
        earlier outputs. Slugification strips everything except
        alphanumerics, hyphens, and underscores. Phase 17.5 — the
        extension is ``.py`` for code-type output, ``.md`` otherwise,
        so :func:`src.strategy.loader.load_strategy`'s suffix dispatch
        picks the right loader without any extra plumbing.
        """
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_") or "technique"
        timestamp = now_utc().strftime("%Y%m%d_%H%M%S")
        extension = ".py" if output_kind == "python" else ".md"
        return f"{slug}_{timestamp}{extension}"

    @staticmethod
    def _validate_improvement_preserves_output_contract(
        *,
        original_source: str,
        generated_content: str,
    ) -> None:
        """Ensure improvement generations do not drop runtime contracts."""
        if "## Output Contract" not in original_source:
            return

        if "## Output Contract" not in generated_content:
            raise GeneratedTechniqueError(
                "Improved technique dropped the existing ## Output Contract block."
            )

        contract_keys = (
            "signal",
            "entry_price",
            "stop_loss",
            "take_profit",
            "take_profit_1",
            "take_profit_2",
        )
        missing = [
            key
            for key in contract_keys
            if key in original_source and key not in generated_content
        ]
        if missing:
            keys = ", ".join(missing)
            raise GeneratedTechniqueError(
                f"Improved technique dropped Output Contract keys: {keys}."
            )

    def _save(self, generated: GeneratedTechnique) -> Path:
        """Write a generated technique to disk atomically.

        Routed through :func:`src.utils.io.atomic_write_text` so a crash
        mid-write cannot leave a torn ``.py``/``.md`` candidate that the
        loader would later either reject as invalid or — worse — parse
        as a half-strategy (consistency-hardening CH-02).
        """
        self.experimental_dir.mkdir(parents=True, exist_ok=True)
        path = self.experimental_dir / generated.suggested_filename
        atomic_write_text(path, generated.content)
        return path

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _load_catalog(self) -> str:
        """Load the strategy priority matrix for prompt injection.

        Returns the file content, or an empty string if the file is
        absent (the catalog is optional). The result is cached on the
        instance — the file is read at most once per improver
        lifetime.
        """
        if self._catalog_cache is not None:
            return self._catalog_cache
        if not self.catalog_path.exists():
            logger.info(
                f"Strategy catalog not found at {self.catalog_path}; "
                "proceeding without it."
            )
            self._catalog_cache = ""
            return ""
        self._catalog_cache = self.catalog_path.read_text(encoding="utf-8")
        return self._catalog_cache

    def _catalog_section(self) -> str:
        """Wrap the catalog in framing text for prompt injection.

        Returns the empty string when the catalog file is absent so the
        caller can concatenate unconditionally.
        """
        catalog = self._load_catalog()
        if not catalog:
            return ""
        return (
            "\n## Reference Catalog (researched technique menu)\n"
            "The following matrix synthesizes ~146 trading techniques "
            "from 6 research documents (ICT/SMC, classic patterns, "
            "breakout/range, mean-reversion, trend indicators, "
            "crypto-native). Each technique is scored on automation-"
            "fit, reliability, crypto-fit, and combo-potential. Use it "
            "as a menu — pick from it, recombine entries, or invent "
            "something not listed. If you propose a technique already "
            "in the catalog, name it explicitly and cite its rank/"
            "category. The constraints above (especially the AVOID "
            "list and falsifiable hypothesis requirement) still apply.\n\n"
            f"{catalog}\n\n"
        )

    @staticmethod
    def _new_idea_output_contract() -> str:
        """Runtime Output Contract instruction for ``prompt``-type techniques.

        Phase 17.2 / DEBT-019 — the new-idea flow's body MUST tell
        Claude to embed the chasulang-style runtime JSON schema in the
        generated technique. Without this, Claude defaults to a human-
        readable rule list and the resulting ``technique_type: prompt``
        candidate produces unparseable per-bar output, which the
        backtester loops on for hours. The schema mirrors the trade
        block of ``strategies/chasulang_ict_smc.md`` (the canonical
        production-hardened template) plus the four keys the
        ``PromptStrategy`` parser hard-requires.
        """
        return (
            "## Output Contract\n"
            "If `technique_type: prompt`, the technique body MUST "
            "include an explicit `## Output Contract` section telling "
            "Claude how to respond at *runtime* (per-bar). The "
            "technique body's contract section must require ONE fenced "
            "JSON object per bar, no prose around the block, with at "
            "minimum these four keys (mirror "
            "`strategies/chasulang_ict_smc.md` for the canonical "
            "shape):\n"
            "```json\n"
            "{\n"
            '  "signal": "long" | "short" | "neutral",\n'
            '  "entry_price": <decimal> | null,\n'
            '  "stop_loss": <decimal> | null,\n'
            '  "take_profit": <decimal> | null\n'
            "}\n"
            "```\n"
            "Additional keys (confidence, reasoning, structured "
            "context) are encouraged when they help the technique, but "
            "the four keys above are mandatory and must keep their "
            "names verbatim — the backtest engine parses them by key. "
            "A `prompt`-type technique that omits this contract section "
            "will be rejected as unrunnable.\n\n"
        )

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
            "- description: single line of description\n"
            '- technique_type: either "prompt" or "code"\n'
            "- hypothesis: ONE sentence stating the specific market "
            "inefficiency or behavior this technique exploits, phrased "
            'so it could be falsified by data (e.g. "funding rate '
            "above the 95th percentile predicts a mean-reverting move "
            'within 8 hours"). This is mandatory — a technique with '
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
        autopsies: list[TradeAutopsy],
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

        records_block = (
            self._format_records(records[-10:])
            if records
            else ("(no detailed records supplied)")
        )
        autopsy_block = (
            self._format_autopsies(autopsies[-10:])
            if autopsies
            else ("(no trade autopsies supplied)")
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
            "## Trade Autopsies\n"
            f"{autopsy_block}\n\n"
            + self._failure_analysis_section()
            + self._hard_constraints_section()
            + f'Use name="{suggested_name}" (or similar) and bump the '
            "version above the original.\n\n" + self._output_format_instructions()
        )

    @staticmethod
    def _failure_analysis_section() -> str:
        return (
            "## Required Reasoning Process\n"
            "Before writing the revised technique, work through these "
            "steps in your reply (inside the markdown body, as a "
            "## Failure Analysis section at the top):\n"
            "1. Identify 2-3 SPECIFIC failure modes visible in the "
            'losing trades (e.g. "entered counter-trend during strong '
            'momentum", "stops too tight relative to ATR", '
            '"signal fires equally in trending and ranging regimes").\n'
            "2. For each failure mode, state the structural reason it "
            "happens — not just the symptom.\n"
            "3. Propose ONE targeted change per failure mode. Avoid "
            "stacking many small filters (that is overfitting); prefer "
            "one principled rule per problem.\n\n"
        )

    @staticmethod
    def _hard_constraints_section() -> str:
        return (
            "## Hard Constraints\n"
            "- Do NOT add lookback-specific thresholds tuned to the "
            'exact trades shown (e.g. "avoid trading on Tuesdays" '
            "because two losses happened on a Tuesday).\n"
            "- Do NOT add more than 2 new conditions total. Simpler "
            "rules generalize better.\n"
            "- Every new rule must be justifiable from a market-"
            'structure argument, not just "it would have avoided the '
            'losses above."\n'
            "- The hypothesis in frontmatter must reflect what the "
            "REVISED technique exploits, not the original.\n\n"
        )

    def _build_new_idea_prompt(self, context: str) -> str:
        """Construct the new-idea prompt (FR-023)."""
        context_line = (
            f"Context / steering: {context.strip()}\n\n" if context.strip() else ""
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
            '- Pattern-recognition heuristics ("head and shoulders", '
            '"triangle breakout") without a quantified edge.\n'
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
            + self._catalog_section()
            + self._new_idea_output_contract()
            + self._output_format_instructions()
        )

    def _build_new_idea_code_prompt(self, context: str) -> str:
        """Construct the code-type new-idea prompt (Phase 17.5 / DEBT-019 B).

        The code-generation branch instructs Claude to emit a Python
        ``BaseStrategy`` subclass whose ``analyze`` coroutine computes
        the per-bar signal from OHLCV alone — no Claude CLI in the hot
        path. Used for deterministic catalog picks (Donchian,
        Supertrend, Z-score, Connors RSI(2), NR7, BB %B+RSI, Larry
        Williams, Golden Cross, TTM Squeeze) so backtests are orders
        of magnitude faster, deterministic, and immune to JSON-contract
        drift entirely.

        References ``strategies/rsi.py``, ``strategies/ma_crossover.py``
        and ``strategies/bollinger_bands.py`` as the canonical shape
        Claude must mirror: ``TECHNIQUE_INFO`` dict + module-level
        parameter constants + ``class XxxStrategy(BaseStrategy)`` with
        an async ``analyze`` method (NOT a sync ``signal()`` — the
        ``BaseStrategy`` interface is async per
        :class:`src.strategy.base.BaseStrategy.analyze`).
        """
        context_line = (
            f"Context / steering: {context.strip()}\n\n" if context.strip() else ""
        )
        return (
            "You are a quantitative trading strategy engineer. The "
            "operator has selected a deterministic technique from the "
            "catalog and wants it implemented as a Python "
            "``BaseStrategy`` subclass — NOT a Claude-driven prompt "
            "template. The strategy will run locally per bar with no "
            "LLM in the hot path: this is the only acceptable shape "
            "for catalog picks because it is deterministic, fast, and "
            "immune to JSON-contract drift.\n\n"
            + self._code_shape_requirements()
            + self._code_hard_constraints()
            + f"{context_line}"
            + self._code_output_format()
        )

    @staticmethod
    def _code_shape_requirements() -> str:
        return (
            "## Required file shape\n"
            "Mirror the canonical baselines under the project's "
            "``strategies/`` directory:\n"
            "- ``strategies/rsi.py``\n"
            "- ``strategies/ma_crossover.py``\n"
            "- ``strategies/bollinger_bands.py``\n\n"
            "Concretely, the file MUST contain:\n"
            "1. A module docstring describing the strategy.\n"
            "2. Imports from the project (`from src.models import "
            "OHLCV, AnalysisResult`, `from src.strategy.base import "
            "BaseStrategy, StrategyExecutionError, TechniqueInfo`). "
            "You may also import indicators from "
            "``src.strategy.indicators`` (``rsi``, ``sma``, "
            "``bollinger_bands``, etc.) — prefer these over reinventing "
            "the math.\n"
            "3. A module-level ``TECHNIQUE_INFO`` dict with keys "
            "``name``, ``version``, ``description``, ``author``, "
            "``hypothesis``, ``symbols``, ``timeframes``, ``status``, "
            "``changelog``. "
            "Use a short snake_case ``name``, semantic ``version`` "
            '(e.g. ``"1.0.0"``), and one-line ``description``. The '
            "``technique_type`` key is set automatically by the loader "
            "— do NOT include it.\n"
            "4. Module-level parameter constants (period lengths, "
            "thresholds, SL/TP percentages) so a future tuning pass is "
            "a one-line change.\n"
            "5. A class ``class XxxStrategy(BaseStrategy)`` whose "
            "``__init__`` accepts ``info: TechniqueInfo`` plus the "
            "tunables (with the module-level constants as defaults), "
            "and whose ``analyze`` method matches the abstract "
            "signature exactly:\n\n"
            "```python\n"
            "async def analyze(\n"
            "    self,\n"
            "    ohlcv: list[OHLCV],\n"
            "    symbol: str,\n"
            '    timeframe: str = "1h",\n'
            ") -> AnalysisResult:\n"
            "    ...\n"
            "```\n\n"
            "The body computes the signal from ``ohlcv`` alone and "
            "returns an ``AnalysisResult`` with ``signal`` "
            '(``"long" | "short" | "neutral"``), ``confidence``, '
            "``entry_price``, ``stop_loss``, ``take_profit``, and "
            "``reasoning``. It MUST NOT import or call ``ClaudeCLI``, "
            "``subprocess``, ``requests``, or any other I/O — all "
            "decisions come from OHLCV.\n\n"
        )

    @staticmethod
    def _code_hard_constraints() -> str:
        return (
            "## Hard constraints\n"
            "- Stay deterministic. No randomness, no wall-clock-"
            "dependent branches, no network calls.\n"
            "- Use ``Decimal`` for prices in the returned "
            "``AnalysisResult`` (the engine and risk model assume "
            "``Decimal`` money math).\n"
            "- Validate input via ``self.validate_input(ohlcv, "
            "min_candles=...)`` at the top of ``analyze``, with "
            "``min_candles`` set high enough for the longest lookback "
            "the strategy needs.\n"
            "- Surface unexpected failures by raising "
            '``StrategyExecutionError(f"…: {e}", '
            "strategy_name=self.name)``; surface insufficient-history "
            "cases by returning a neutral ``AnalysisResult`` with "
            "valid placeholder prices (mirror the canonical "
            "``_neutral_result`` helper in the baseline files).\n"
            "- ``hypothesis`` in ``TECHNIQUE_INFO`` is mandatory: one "
            "falsifiable sentence stating the structural inefficiency "
            "the technique exploits.\n"
            "- Do not import or call file/network/process APIs "
            "(``open``, ``pathlib``, ``os``, ``subprocess``, "
            "``requests``, ``urllib``, sockets, or dynamic execution); "
            "the loader rejects those before execution.\n\n"
        )

    @staticmethod
    def _code_output_format() -> str:
        return (
            "## Output format\n"
            "Respond ONLY with a single fenced code block labeled "
            "``python`` containing the full ``.py`` file body. No "
            "prose around the block, no markdown frontmatter, no "
            "additional commentary — the operator pipeline writes the "
            "block verbatim to ``strategies/experimental/<slug>.py`` "
            "and loads it with ``src.strategy.loader.load_strategy``."
        )

    def _build_user_idea_prompt(self, user_idea: str) -> str:
        """Construct the user-idea prompt (FR-024).

        Deliberately omits the strategy catalog: the user has already
        described the idea they want built, and Claude's job is to
        extract THEIR hypothesis and structure THEIR technique — not
        redirect the prompt onto the closest catalog entry. The
        new-idea flow is the only place catalog injection makes sense
        (broadens the search space when no idea is supplied).
        """
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
            'specific concern. Do not silently "fix" their idea.\n\n'
            "## Constraints\n"
            "- Do not add filters or conditions the user did not ask "
            "for, beyond the minimum needed for safe execution "
            "(stop-loss, position sizing).\n"
            "- If the idea requires data the system may not have, "
            "list it in a ## Data Requirements section.\n\n"
            + self._new_idea_output_contract()
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

    @staticmethod
    def _format_autopsies(autopsies: list[TradeAutopsy]) -> str:
        """Render trade autopsies as compact improvement context."""
        if not autopsies:
            return "(none)"
        lines = []
        for autopsy in autopsies:
            pnl = (
                f"{autopsy.pnl_percent:.2f}%"
                if autopsy.pnl_percent is not None
                else str(autopsy.pnl)
            )
            mfe = (
                f"{autopsy.max_favorable_excursion_percent:.2f}%"
                if autopsy.max_favorable_excursion_percent is not None
                else "n/a"
            )
            mae = (
                f"{autopsy.max_adverse_excursion_percent:.2f}%"
                if autopsy.max_adverse_excursion_percent is not None
                else "n/a"
            )
            lines.append(
                f"- {autopsy.symbol} {autopsy.side} "
                f"outcome={autopsy.outcome.value} close={autopsy.close_reason} "
                f"pnl={pnl} mfe={mfe} mae={mae} "
                f"hold={autopsy.holding_seconds:.0f}s"
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
    "DEFAULT_CATALOG_PATH",
    "ClaudeParseError",
]

"""Prompt-text builders for the strategy improver (AI-F4).

Pure functions producing the static instruction text the
:class:`src.ai.improver.StrategyImprover` sends to Claude. Extracted
from ``improver.py`` so the *volatile* "what we ask Claude" axis is
isolated from the stable parse/validate/persist core — the two change
for different reasons (prompt wording iterates often; the parser is
contract-stable).

Each function returns a fixed string (or composes fixed strings); none
touch instance state, the filesystem, or any domain object — they are
the prompt boilerplate only. The improver's instance-method
orchestrators (``_build_*_prompt``) compose these with the
per-invocation context (performance summaries, catalog, records).

Related Requirements:
- FR-022, FR-023, FR-024
- NFR-002: Claude CLI Integration
"""

from __future__ import annotations


def new_idea_output_contract() -> str:
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


def output_format_instructions() -> str:
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


def failure_analysis_section() -> str:
    """Required reasoning-process block for the improvement prompt."""
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


def hard_constraints_section() -> str:
    """Hard-constraints block for the improvement prompt."""
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


def code_shape_requirements() -> str:
    """Required-file-shape block for the code-type new-idea prompt."""
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


def code_hard_constraints() -> str:
    """Hard-constraints block for the code-type new-idea prompt."""
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


def code_output_format() -> str:
    """Output-format block for the code-type new-idea prompt."""
    return (
        "## Output format\n"
        "Respond ONLY with a single fenced code block labeled "
        "``python`` containing the full ``.py`` file body. No "
        "prose around the block, no markdown frontmatter, no "
        "additional commentary — the operator pipeline writes the "
        "block verbatim to ``strategies/experimental/<slug>.py`` "
        "and loads it with ``src.strategy.loader.load_strategy``."
    )

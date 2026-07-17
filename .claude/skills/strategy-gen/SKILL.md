---
name: strategy-gen
description: Generate new deterministic trading strategies from market data. Orchestrates chartist (market-structure analysis) and quant-trader-expert (hypothesis design) subagents to derive evidence-backed setups, then authors a new BaseStrategy .py candidate (like rsi_universal) under strategies/experimental/, wires tests + the robustness gate, and reports pass/fail. Never auto-promotes (CON-003).
---

# Crypto Master Strategy Generation Skill

Turn market data into a **new strategy candidate**: chartist lanes read the
charts and produce measured setups, quant lanes turn the survivors into
structural hypotheses, the lead verifies, and only then is a
`strategies/experimental/*.py` candidate authored, tested, and run through the
Robustness Validation Gate.

This skill is for requests like:

- "create a new strategy from current data"
- "make a stronger strategy like rsi_universal"
- "have the chartist/quant agents design a new setup"
- "research what edge exists in recent BTC/alt price action and encode it"

It is **generation-focused**. For diagnosing/improving *existing deployed*
strategies, use `/strategy-improvement` instead; this skill may consume that
skill's findings (a `strategy-add` DEBT unit is a perfect input).

## Non-Negotiable Ground Rules

1. **Hypothesis-first (Phase 5.3a).** No strategy is authored without a
   one-sentence structural hypothesis (*what market behavior, why does it
   persist*) and a falsifiability statement. Generic indicator mashups
   ("RSI + MACD + BB confluence") are rejected at the lead gate — an indicator
   is a *measurement* of a hypothesis, never the hypothesis itself.
2. **OHLCV reality check.** This project's own evidence (12-day Fly paper run,
   backtest baselines) shows OHLCV-only strategies cluster around breakeven.
   Expectations must be calibrated: the goal is a candidate that *passes the
   four robustness sub-gates and beats a named baseline's Sharpe*, not a
   +100% moonshot (observed +100%/90d results were leverage artifacts, not
   edge). Any apparent large edge is treated as a bug (look-ahead, fees,
   window selection) until proven otherwise. Hypotheses needing funding/OI/
   liquidation data are recorded as future candidates — `BaseExchange` only
   exposes OHLCV/ticker today.
3. **No auto-promotion (CON-003).** Candidates stop at
   `status: experimental` in `strategies/experimental/`. Promotion to the
   active pool happens only via `FeedbackLoop.approve()` / operator review.
   This skill never moves a file from `strategies/experimental/` to
   `strategies/`.
4. **Lead orchestrates; subagents cannot nest.** The top-level agent captures
   data once, fans out lanes, and verifies findings itself. Lanes report
   follow-up questions; the lead spawns follow-up lanes.

## Required Context

Read before dispatching (skip-and-note any that moved):

1. `strategies/rsi.py` — the canonical `TECHNIQUE_INFO` + `BaseStrategy` shape
2. `src/strategy/base.py`, `src/strategy/indicators.py`
3. `src/backtest/validator.py` (`RobustnessGate` — the four sub-gates)
4. `scripts/run_robustness_gate.py` (`StrategySpec` registration pattern)
5. `scripts/backtest_baselines.py` (`fetch_ohlcv_window` — OHLCV custody)
6. `docs/baselines.md` — the Sharpe/win-rate/MDD bar to beat
7. `docs/TECH-DEBT.md` — open `strategy-add` units (may be the input brief)
8. `docs/research/strategies/00-priority-matrix.md` if present — prior
   hypothesis catalog; do not re-derive what is already cataloged

## Workflow

### 1. State the mode

- `research-only`: chartist + quant fan-out, hypothesis report, no files
  written.
- `generate` (default): everything through authoring, tests, and the
  robustness gate.

Also fix the **universe** up front: symbols and timeframes to study (default:
BTC/USDT + 2-3 liquid alts the engine already trades, on 15m/1h/4h), and the
lookback window (default ≥ 180 days so the regime sub-gate sees bull, bear,
and sideways buckets).

### 2. Acquire data once (lead only)

Two evidence surfaces, captured by the lead and passed read-only to lanes:

- **OHLCV windows** — fetch via `scripts.backtest_baselines.fetch_ohlcv_window`
  (Binance public API, read-only) and persist each window as an artifact in
  the session scratchpad (one file per `(symbol, timeframe)`, with since/limit
  recorded). Lanes read these files; they do not re-fetch. Persisted windows
  make replays and gate runs reproducible.
- **Performance context (optional)** — if the request references deployed
  results ("our RSI strategies keep losing"), reuse the Fly `/data` snapshot
  procedure from `/strategy-improvement` (single lead-captured snapshot,
  fail-loudly preflight). Do not re-implement it here; do not let lanes call
  `flyctl`.

### 3. Fan out analysis lanes

Default 3-5 lanes; confirm with the user before exceeding 8. Every lane prompt
embeds: the artifact paths, "read-only, no Edit/Write, no fetching beyond the
given artifacts", the mode, and the structured return contract from its agent
definition.

- **chartist lanes** (`chartist` agent): one per symbol-cohort or timeframe
  band, per its report contract — regime map, structure, candidate setups with
  base rates, MFE/MAE-in-ATR follow-through, sample-size labels, anti-findings.
- **quant lane** (`quant-trader-expert` agent): receives the chartist reports
  plus the baseline metrics; for each surviving setup produces the design
  block from its agent definition — hypothesis, falsifiability, expected
  robustness-gate profile (which sub-gate is the likely failure), named
  baseline + expected Sharpe delta, implementation hints (which
  `src/strategy/indicators.py` primitives, tunables for the sensitivity grid).
- **gap lane** (optional, `Explore`): what do existing `strategies/*.py`
  already cover? A new candidate must not be a sibling of an existing
  `strategy_family` unless it has a distinct hypothesis — else it's a retune,
  route to `/strategy-improvement`.

### 4. Lead hypothesis gate (mandatory)

For each proposed candidate, the lead verifies before any code is written:

- re-check the cited statistics against the persisted OHLCV artifacts (open
  the data, recompute the headline number; do not trust lane summaries);
- **no look-ahead**: every trigger feature is computable from candles closed
  before the decision bar — including derived features (ATR/VWAP/percentiles);
- base rate + sample size honest: reject setups whose edge rests on `<30`
  occurrences or a single regime bucket (single-regime setups may proceed
  only *with the regime filter as part of the design*);
- hypothesis is structural, falsifiable, and not already covered by an
  existing family;
- **selection-bias note**: if N candidate setups were screened to pick this
  one, record N — the robustness gate's OOS bar must be read with that
  multiplicity in mind (deflated-Sharpe mindset; a marginal OOS pass on the
  best-of-8 is not a pass).

Verdicts: `approved` (proceed to §5), `needs-data` (spawn one follow-up lane,
max 2 rounds), `rejected` (record in report; no code). In `research-only`
mode, stop here and report.

### 5. Author the candidate

One file per candidate: `strategies/experimental/<name>.py`, modeled on
`strategies/rsi.py`:

- Module docstring: hypothesis, falsifiability, evidence pointers (artifact
  paths + the statistics that motivated it), related FRs.
- `TECHNIQUE_INFO` dict: `name`, `version: "1.0.0"`, `description` (include
  SL/TP and nominal R/R), `author: "system"`, `symbols` (empty = universal),
  `timeframes`, `status: "experimental"`, `changelog`, `counter_trend`,
  `max_bars_held` (derived from the measured mean-reversion half-life /
  follow-through horizon, not guessed), `strategy_family` (new family name;
  reuse an existing family only if signals could duplicate a sibling's).
- A `BaseStrategy` subclass whose tunables are **constructor kwargs with
  module-level round-number defaults** (no magic 27.34 thresholds) — this is
  what lets the sensitivity gate run instead of skipping.
- SL/TP such that nominal R/R ≥ 2.5:1 — the proposal layer fail-closes below
  2.0 and ATR-driven SL widening eats margin (the rsi_universal v1.1.0
  lesson; read its changelog).
- Neutral path returns a valid `AnalysisResult` (Pydantic requires positive
  prices even on neutral — see `_neutral_result` in `strategies/rsi.py`).
- Prefer primitives from `src/strategy/indicators.py`; add a new indicator
  there (with tests) rather than inlining math in the strategy file.

Plus tests in `tests/test_<name>_strategy.py`: clear long trigger, clear short
trigger, neutral case, threshold edges, insufficient-data path — mirror an
existing strategy test file's fixtures.

### 6. Validate

1. `uv run pytest tests/test_<name>_strategy.py tests/test_strategy_loader.py -q`
2. Register the candidate in `scripts/run_robustness_gate.py`: add a
   `StrategySpec` with a `param_grid` (2-3 values per tunable, bracketing the
   defaults) and `factory_kwargs` matching the constructor.
3. Run the gate on the **same persisted windows** used for research *plus* a
   fresh extension if available:
   `uv run python -m scripts.run_robustness_gate --live --strategy <name>`
4. Report all four sub-gate verdicts (OOS / walk-forward / regime /
   sensitivity) honestly. A failed gate is a *finding*, not a reason to tune
   until green — re-tuning against the same window is the guardrail-violating
   move; one predeclared-bounded retune round max, then park the candidate
   with its failure recorded.
5. `uv run black strategies tests scripts && uv run ruff check strategies tests scripts --fix`

In autonomous/multi-candidate sessions, commit and push after each candidate
completes §5-6 (one candidate = one slice).

### 7. Guardrails

- No editing existing `strategies/*.py` from this skill — that is
  `/strategy-improvement` (`strategy-modify`) territory.
- No live/paper deployment changes, no `config/sub_accounts.yaml` edits, no
  promotion out of `experimental/`.
- Fees and slippage: never quote an edge from a fee-free calculation; the
  backtester applies them — hand-rolled research math in lanes must too
  (taker fee both sides minimum).
- Max 2 candidates authored per invocation unless the user asks for more —
  each additional candidate raises the selection-bias multiplicity.
- Stop and ask when chartist and quant lanes disagree on whether a setup is
  real; do not average opinions.

## Report Format

End with:

- universe + windows studied (artifact paths, bars, gaps)
- fan-out used (lanes + agent types)
- hypothesis gate log: every candidate setup with verdict
  (`approved` / `needs-data` / `rejected`) and reason
- for each authored candidate: file path, hypothesis, falsifiability, family,
  tunables + grid, nominal R/R
- robustness gate results: four sub-gate verdicts + baseline Sharpe comparison
- tests/lint run or not run
- selection-bias multiplicity (N setups screened → k authored)
- next operator decisions (approve for paper via `FeedbackLoop.approve()`,
  park, or gather more data) — explicitly not taken by this skill

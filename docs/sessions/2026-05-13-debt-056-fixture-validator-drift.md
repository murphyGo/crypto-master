# Session: DEBT-056 fixture-validator drift + I001 lint sweep

## Unit

- `ai-feedback-loop` (primary — improver fixture drift)
- Secondary units: `dashboard-operator-ui`, `backtesting-validation` (the 2
  pre-existing `I001` lint files)

## Related Requirements

- FR-033: Require falsifiable hypotheses for Claude-generated techniques —
  closest mapping in
  `aidlc-docs/inception/requirements/requirements.md` for the hypothesis gate
  at `src/ai/improver.py:374`.
- FR-024 / FR-026: Generate techniques from operator ideas / Automate the
  backtest-analysis-improvement loop — adjacent surface for the runtime
  Output Contract gate at `src/ai/improver.py:425`. No requirement names the
  Output Contract block directly; the closest framing is "generated
  techniques must be runnable against the runtime contract", which is
  intent-mapped to FR-024/FR-026 rather than spelled out.

## Scope

Resolved DEBT-056 — pre-existing `ruff` `I001` lint hits at 2 files plus 6
fixture-vs-validator drift failures in
`tests/test_scripts_auto_research_candidates.py`. Fixture-only + lint-only
diff; no production code touched.

## Changes

- `src/dashboard/pages/engine.py` — `ruff check --fix` import-order sort
  (pre-existing `I001`).
- `tests/test_backtest_validator.py` — `ruff check --fix` import-order sort
  (pre-existing `I001`).
- `tests/test_scripts_auto_research_candidates.py` — three fixture updates
  aligning the script-orchestration fixtures with the runtime-validator
  contracts introduced in commit `85a33b0` (2026-05-08, "Harden runtime
  consistency followups"):
  1. `GOOD_RESPONSE` markdown body gained a `## Output Contract` block
     listing `signal`, `entry_price`, `stop_loss`, `take_profit` — fixes 4
     markdown-pick tests failing at `src/ai/improver.py:425`
     (`_validate_generated_runtime_contract`).
  2. `GOOD_PYTHON_STRATEGY::TECHNIQUE_INFO` gained `"hypothesis"` — fixes 1
     code-type test failing at `src/ai/improver.py:374` (falsifiable-
     hypothesis gate).
  3. `TRADE_PRODUCING_PYTHON_STRATEGY::TECHNIQUE_INFO` gained `"hypothesis"`
     — fixes 1 code-type test failing at `src/ai/improver.py:374`.

## Root Cause

The fixtures predate the `85a33b0` validator hardening shipped 2026-05-08.
Gate `:374` (`_validate_generated_metadata`) requires a non-empty
`metadata["hypothesis"]` field; gate `:425`
(`_validate_generated_runtime_contract`) requires the substring tokens
`## Output Contract`, `signal`, `entry_price`, `stop_loss`, `take_profit` in
the rendered markdown body. After `85a33b0` landed, every fixture missing
those tokens started raising `GeneratedTechniqueError` from inside the
improver, which surfaced as the same exception in 6 different orchestration
tests that all funnel through the script-pick path.

Failure split (correcting the prior over-correction in TECH-DEBT.md
`Change History`, which had attributed all 6 failures to `:374`):

- **2 failures at `src/ai/improver.py:374`** (code-type tests, hypothesis
  gate):
  - `test_code_type_pick_runs_without_per_bar_claude_calls`
  - `test_code_type_pick_produces_backtest_trade_without_claude_analyze`
- **4 failures at `src/ai/improver.py:425`** (markdown-pick tests, runtime
  Output Contract gate):
  - `test_run_picks_orchestrates_each_candidate`
  - `test_run_picks_threads_sub_account_id`
  - `test_dry_run_skips_backtest`
  - `test_pick_failure_captured_not_raised`

The original 2026-05-09 DEBT-056 entry's `:425` citation was actually
correct for the longest-running failure
(`test_run_picks_orchestrates_each_candidate`). The 2026-05-13 refresh
narrowed all 6 to `:374`, which was a partial mis-read; the accurate split
is restored in the Resolved DEBT-056 entry.

## Verification

- `pytest -q` → **1808 passed** (was 1802 + 6 failing; net +6 fixes, zero
  regressions).
- `pytest tests/test_scripts_auto_research_candidates.py -v` → **23 passed**
  (was 17/6).
- `ruff check src tests` → fully clean.
- `mypy src` → 3 pre-existing errors remain at
  `src/dashboard/app.py:268,852,865` (untouched, out of scope; see Future
  Work).

## Risks

- None. The diff is fixtures-only plus 2 mechanical import-sort lints; no
  production code paths were modified. The validators being exercised
  (`_validate_generated_metadata` at `:374`,
  `_validate_generated_runtime_contract` at `:425`) are the contracts the
  fixtures are now aligned with — bringing fixtures into compliance with
  validators that have been live since 2026-05-08 cannot regress production
  behaviour.

## Reviewer Notes

- qa-reviewer: 🟢. No quant-trader-expert review requested — fixture work,
  no trading correctness at stake.

## Future Work

- 3 pre-existing `mypy` errors at `src/dashboard/app.py:268,852,865`
  surfaced by the senior-developer during this cycle. Clean fix path per
  dev: `Sequence` for covariance + `Literal` cast on the `mode` parameter
  default. Captured as future-work here; no separate DEBT filed — search of
  `docs/TECH-DEBT.md` found no pre-existing entry mentioning
  `src/dashboard/app.py` for these specific lines, but the surface is small
  enough that promoting it to its own DEBT row was judged churn. Surface to
  team-lead if/when the next dashboard-app cycle wants a clean mypy gate.

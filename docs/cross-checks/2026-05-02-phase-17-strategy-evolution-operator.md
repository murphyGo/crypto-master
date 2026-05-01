# Phase 17 Cross-Check: Strategy-Evolution Operator Workflow

- **Date**: 2026-05-02
- **Phase**: Phase 17 — Strategy-Evolution Operator Workflow
- **Verdict**: ✅ PASS
- **Cross-check author**: docs-auditor (lead-orchestrated)

## Scope

Phase 17 closes the strategy-evolution operator workflow that the
2026-04-28 production review surfaced as missing — auto-research
candidate generation, portfolio snapshot recording, closed-trade
performance persistence, and the per-bar circuit breaker + code-type
steering for deterministic catalog picks. Spans 5 sub-tasks shipped
across 4 commits + 1 numbering-reconciliation cycle (Phase 23.2).

## Sub-task Status

| Sub-task | Status | Closure |
|----------|--------|---------|
| 17.1 Auto-Research Operator Workflow + Catalog-Aware Improver | ✅ Complete | Cycle 28 (commit `10bbd7f`) |
| 17.2 Portfolio Snapshot Recording in Runtime Cycle | ✅ Complete | commit `094a79d` (backfilled spec via Phase 23.2) |
| 17.3 Closed-Trade Performance Records | ✅ Complete | commit `ab9dc32` (backfilled spec via Phase 23.2) |
| 17.4 Auto-Research Workflow Unblock — Runtime Contract + Backtest Circuit Breaker | ✅ Complete | commit `41f9212` (was originally 17.2-planned; Phase 23.2 reconciliation) |
| 17.5 Code-Type Steering for Deterministic Catalog Picks (DEBT-019 Option B) | ✅ Complete | this cycle (2026-05-02) |

## DEBT Closures

- **DEBT-019** (High) ✅ Resolved 2026-04-30 by 17.4 (Options A+C — symptomatic fix); **Option B (root-cause cleanup) shipped 2026-05-02 by 17.5**.
- **DEBT-020** ✅ Resolved by 17.4 (chasulang per-bar timeout fix).

## Phase 17.5 Implementation Summary (this cycle)

- `Pick.code_type: bool = False` field on `scripts/auto_research_candidates.py` Pick model.
- `code_type` plumbed through `loop.propose_new` and dry-run path.
- `src/ai/improver.py::_build_new_idea_code_prompt` instructs Claude
  to emit Python `BaseStrategy` subclass with `async analyze`
  (matching actual abstract interface, NOT spec's mistaken sync
  `signal()`).
- File extension dispatch: `.py` for code-type, `.md` otherwise.
- `src/strategy/loader.py` already supported `.py` files via
  existing `load_technique_info_from_py` — no loader changes needed.
- All 9 catalog TOP_PICKS flagged `code_type=True`: Donchian
  System 2, Supertrend, Connors RSI(2), Z-score Mean Reversion,
  Larry Williams Volatility Breakout, TTM Squeeze, BB %B+RSI Combo,
  Golden Cross (SMA 50/200), NR7 Breakout.

## Tests

| Sub-task | Tests added |
|----------|-------------|
| 17.5 unit (TestCodeTypeNewIdea) | +4 |
| 17.5 integration | +1 (the load-bearing invariant test) |
| 17.5 regression (TOP_PICKS pinned) | +1 |
| **Phase 17.5 total** | **+6** |

**Critical Phase 17.5 invariant** pinned by
`test_code_type_pick_runs_without_per_bar_claude_calls`:
- Real `Backtester.run_for_strategy` against 300 synthetic candles.
- `claude.complete.call_count == 1` (single code-generation call).
- `claude.analyze.call_count == 0` (zero per-bar LLM calls during
  backtest — the entire point of Phase 17.5).

## Gates (final)

| Gate | Result |
|------|--------|
| pytest | **1367 passed** (+6 from 1361) |
| ruff `check src tests scripts` | ✅ clean |
| mypy `src` | ✅ clean (58 source files) |
| black `--check` (touched files) | ✅ clean |

## Reviewers (Phase 17.5)

- **quant-trader-expert**: 🟡 ship-with-note. All 9 catalog flags
  correct (deterministic indicator-driven, no discretionary chart
  reading). `async analyze` interface matches `BaseStrategy`. Catalog
  injection retained on code branch. Zero-per-bar-LLM invariant
  proven. **Non-blocking note**: integration test fixture uses
  `signal="neutral"` — exercises load/dispatch path but not the
  actual trade-producing branch. Recorded as DEBT-049 (Low).
- **qa-reviewer**: 🟢 ship. All gate counts match. `ast.literal_eval`
  metadata extraction confirmed safe. Acceptance checkbox left for
  operator (real Claude run required) per Phase 17.4 precedent.

## Compliance Matrix

| Requirement | Status |
|-------------|--------|
| FR-021 Strategy Performance Tracking (17.3) | ✅ Complete |
| FR-022 Strategy Improvement Generation (17.1) | ✅ Complete |
| FR-023 New Technique Idea Generation (17.5 code branch) | ✅ Complete |
| FR-025 Backtesting Execution (17.4 circuit breaker, 17.5 code-type bypass) | ✅ Complete |
| FR-027 Performance-Driven Improvement Trigger (17.1) | ✅ Complete |
| FR-031 Portfolio / Asset History (17.2) | ✅ Complete |
| FR-005 Position Persistence (17.3) | ✅ Complete |
| NFR-001 Operational Maturity (LLM-in-hot-path eliminated for deterministic strategies) | ✅ Complete |
| NFR-008 Asset/PnL History storage (17.2/17.3 atomic via Phase 22.1) | ✅ Complete |

0 ⚠️ Partial. 0 ❌ Gap.

## DEBT Residue

- **DEBT-026** (Medium — Donchian truncated experimental file) —
  obsolete on next regenerate post-17.5; the artefact remains on
  disk untracked. Auditor may close on next cycle if regenerate
  produces a clean replacement, or carry forward as a simple "delete
  the leftover" cleanup.
- **DEBT-049** (Low, NEW) — Phase 17.5 fixture uses `signal="neutral"`
  so trade-producing path not exercised in the per-bar-LLM-zero
  integration test. Trivial follow-up.

## Verdict

**✅ PASS.** Phase 17 sealed cleanly across all 5 sub-tasks. The
9-hour-hang failure mode (DEBT-019, the original audit's most
operationally painful debt) is now closed at root: deterministic
catalog strategies bypass the LLM hot path entirely, and the
fallback prompt path is hardened with per-bar circuit breakers.
The strategy-evolution operator workflow is now usable end-to-end:
auto-research generates candidates → backtester runs deterministic
ones in seconds (not 9 hours) → robustness gate evaluates → operator
promotes from `strategies/experimental/` to active.

## Open Items

None blocking. Phase 17.5 acceptance checkbox left for operator (real
Claude run + 5 generated `.py` files in `strategies/experimental/`)
matches Phase 17.4 precedent. Non-blocking.

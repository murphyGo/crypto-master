# Phase 5 Cross-Check: Feedback Loop System

**Date**: 2026-04-25
**Phase**: 5 - Feedback Loop System
**Status**: All sub-tasks complete (5.1, 5.2, 5.3, 5.3a, 5.4, 5.5)

## Scope

Phase 5 delivered the closed-loop technique-evolution system:

- **5.1 Backtesting Engine** — historical simulation of any
  `BaseStrategy` against OHLCV with fee/slippage modeling and JSON
  result storage.
- **5.2 Performance Analyzer** — win rate, return, max-drawdown,
  Sharpe, profit factor, expectancy from a `BacktestResult`, plus a
  markdown report.
- **5.3 Strategy Improver** — `claude -p` driven improvement, new-idea,
  and user-idea generation, saving candidates to
  `strategies/experimental/`.
- **5.3a Hypothesis-driven prompt redesign** — added mandatory
  `hypothesis` frontmatter, structural Failure Analysis on
  improvements, indicator-mashup rejection on new ideas, ≤ 2
  added-conditions cap.
- **5.4 Robustness Validation Gate** — out-of-sample / walk-forward /
  regime / parameter-sensitivity gates with per-gate diagnostics and
  an aggregate `RobustnessReport`.
- **5.5 Automated Feedback Loop** — `FeedbackLoop` orchestrator wiring
  the above into a single `improvement → backtest → robustness gate →
  decision → user approval → promotion` flow with append-only audit
  log and per-candidate state persistence.

## Compliance Matrix

### Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| FR-021 | Technique Performance Analysis | ✅ Complete | `PerformanceAnalyzer.analyze` returns `PerformanceMetrics` with win rate, return, MDD, Sharpe, profit factor, expectancy. `analyze_to_markdown` produces a human-readable report. Tests: `tests/test_backtest_analyzer.py`. |
| FR-022 | Technique Improvement Suggestion (Claude) | ✅ Complete | `StrategyImprover.suggest_improvement` (`src/ai/improver.py`) builds a Claude prompt that requires structural Failure Analysis (FR-035) and produces a revised technique saved to `strategies/experimental/`. Tests: `tests/test_ai_improver.py`. |
| FR-023 | New Technique Idea Generation | ✅ Complete | `StrategyImprover.generate_idea`. Prompt explicitly rejects indicator mashups and steers toward falsifiable market-structure hypotheses (FR-033). Tests: `tests/test_ai_improver.py`. |
| FR-024 | User Idea Input | ✅ Complete | `StrategyImprover.generate_from_user_idea` extracts the implicit hypothesis and notes caveats when the idea has no plausible edge. Tests: `tests/test_ai_improver.py::test_generate_from_user_idea_*`. |
| FR-025 | Backtesting Execution | ✅ Complete | `Backtester.run` (`src/backtest/engine.py`) walks candles forward with no look-ahead, applies fees/slippage, persists results under `data/backtest/{run_id}/`. Tests: `tests/test_backtest_engine.py`. |
| FR-026 | Automated Feedback Loop | ✅ Complete | `FeedbackLoop.improve_existing` / `propose_new` / `from_user_idea` / `reevaluate` (`src/feedback/loop.py`) chain improver → backtester → analyzer → robustness gate → decision in one call. Tests: `tests/test_feedback_loop.py`. |
| FR-027 | Technique Adoption | ✅ Complete | `FeedbackLoop.approve(candidate_id, approver)` is the only path that moves a candidate from `experimental/` to active and rewrites frontmatter `status: active`. Refuses non-`AWAITING_APPROVAL` candidates and refuses to overwrite an existing active file. Tests: `test_approve_moves_file_and_flips_status`, `test_approve_rejects_non_pending_candidate`, `test_approve_refuses_to_overwrite_existing_active`. |
| FR-033 | Hypothesis-Driven Generation | ✅ Complete | All three improver prompts mandate a `hypothesis` frontmatter field (single falsifiable sentence). New-idea prompt explicitly refuses generic indicator mashups. Tests: `tests/test_ai_improver.py::test_*_hypothesis_*`. |
| FR-034 | Robustness Validation Gate | ✅ Complete | `RobustnessGate.evaluate` (`src/backtest/validator.py`) runs four gates and returns a `RobustnessReport`; `FeedbackLoop` blocks promotion when `overall_passed=False`. Tests: 18 tests in `tests/test_backtest_validator.py` + 4 gate-decision tests in `tests/test_feedback_loop.py`. |
| FR-035 | Failure-Mode Improvement | ✅ Complete | `_build_improvement_prompt` requires a Failure Analysis section (root-cause enumeration) and caps added conditions at ≤ 2 per revision. |

### Non-Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| NFR-002 | Claude CLI Integration | ✅ Complete | Improver routes every Claude call through `ClaudeCLI.complete` (i.e. `claude -p`). No direct Anthropic API usage anywhere in `src/feedback/`. |
| NFR-006 | Backtesting Result Storage | ✅ Complete | `Backtester.save_result` writes JSON under `data/backtest/{run_id}/result.json`. `RobustnessReport` and `CandidateRecord` also serialize as JSON. |

### Constraints

| ID | Constraint | Status | Evidence |
|----|------------|--------|----------|
| CON-001 | No Anthropic API | ✅ Complete | Verified: no `anthropic` import, no direct API client. |
| CON-003 | User Approval Required | ✅ Complete | `FeedbackLoop.approve` is the sole promotion path; the gate alone cannot promote a candidate (it only flips status to `AWAITING_APPROVAL`). Tests: `test_improve_existing_gate_passed_awaits_approval` confirms PASSED candidates stay in experimental until `approve()` is called. |

## Phase-Adjacent Requirements Touched

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| NFR-005 | Analysis Technique Storage | ✅ Complete | Generated candidates live as `.md` with YAML frontmatter under `strategies/experimental/`; promotion moves them to `strategies/` root and rewrites `status: active`. |
| NFR-007 | Trading History Storage | ✅ Complete | `BacktestResult` records entry/exit prices, quantities, leverage, fees, P&L, timestamps per simulated trade. |

## Test Summary

- **Phase 5-related tests at phase completion**:
  - 5.1: `test_backtest_engine.py`
  - 5.2: `test_backtest_analyzer.py`
  - 5.3: `test_ai_improver.py`
  - 5.4: `test_backtest_validator.py` (18 tests)
  - 5.5: `test_feedback_audit.py` (8 tests) + `test_feedback_loop.py` (15 tests) = **23 new tests**.
- **Full suite at phase completion**: **780 passing, 0 failing**.
- **Lint/format**: `ruff check` and `black --check` clean for all
  Phase 5 source and tests.

## Gaps

None. Every FR/NFR/CON mapped to Phase 5 has implementation + tests.

## Risks Carried Forward

Documented in per-task session logs:

1. **Sensitivity gate is opt-in.** Most strategies in this codebase
   are prompt-based and have no tunable numeric parameters; without
   a `param_grid` and `strategy_factory`, the sensitivity gate is
   SKIPPED. Operators should treat SKIPPED as "you didn't give me
   what I needed to check this" — not as a silent pass. (5.4 session log)

2. **Robustness thresholds are heuristic defaults.** `RobustnessConfig`
   defaults (OOS retention 70%, walk-forward positive fraction 60%,
   sensitivity profitable fraction 60%) are conservative but
   un-validated against real Phase-6/7 promotions. Adjust as
   evidence accumulates. (5.4 session log)

3. **Promotion is not transactional.** The `approve()` flow writes
   the new file then unlinks the source. An OS crash between those
   two operations leaves the candidate in both directories.
   Operators can resolve this manually via frontmatter `status`.
   A future phase may want atomic-rename semantics. (5.5 session log)

4. **No automated cleanup of state files.** `data/feedback/state/`
   grows monotonically. Not a problem at current scale; a retention
   policy can be added when the dashboard (Phase 7) starts surfacing
   pending candidates. (5.5 session log)

5. **Manual resumption only.** State is persisted after every
   transition, but auto-resume from a crashed cycle is not
   implemented. Operators inspect state files and rerun the
   appropriate entry point. (5.5 session log)

## Cross-Check Result

- ✅ Complete: 14 requirements (10 FR + 2 NFR + 2 CON)
- ⚠️ Partial: 0 requirements
- ❌ Gap: 0 requirements

**Phase 5 is cleared for Phase 6 (Trading Proposal System).**

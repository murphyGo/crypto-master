# Session Log: 2026-05-05 - ai-feedback-loop - DEBT-014 Sensitivity Grid Wiring

## Overview

- **Date**: 2026-05-05
- **Primary Unit**: `ai-feedback-loop`
- **Secondary Unit**: `backtesting-validation`
- **Stage**: Code Generation
- **Task**: Close DEBT-014 by giving auto-research catalog picks parameter grids and wiring them into robustness sensitivity gating.

## Work Summary

Auto-research catalog picks now declare `param_grid` values and pass them to
`FeedbackLoop.propose_new`. For code-type generated strategies, the feedback
loop automatically builds a sensitivity `strategy_factory` from the saved
Python strategy class so `RobustnessGate` can instantiate parameter variants
instead of skipping sensitivity for missing grid/factory inputs.

## Files Changed

- Modified: `scripts/auto_research_candidates.py`
- Modified: `src/feedback/loop.py`
- Modified: `tests/test_scripts_auto_research_candidates.py`
- Modified: `tests/test_feedback_loop.py`
- Modified: `docs/TECH-DEBT.md`
- Modified: `aidlc-docs/construction/plans/ai-feedback-loop-code-generation-plan.md`
- Modified: `aidlc-docs/construction/plans/backtesting-validation-code-generation-plan.md`
- Created: `docs/cross-checks/2026-05-05-debt-014-sensitivity-grid.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Use pick-level `param_grid` declarations | This closes the current operator gap without requiring a broader strategy metadata API. |
| Add exact tunable names to generation context | Claude-generated code must expose constructor names that the sensitivity factory can sweep. |
| Build the factory from the saved generated `.py` file | The generated path is only known after `StrategyImprover.generate_idea`; `FeedbackLoop.propose_new` is the narrowest place with both the file and the grid. |
| Keep grids below the default 64-combo cap | Prevents normal auto-research runs from failing sensitivity before evaluating variants. |

## Verification

- `uv run pytest tests/test_scripts_auto_research_candidates.py tests/test_feedback_loop.py -q`
- Result: 40 passed.

## Code Review Results

| Category | Status |
|----------|--------|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Potential Risks

- Generated code must honor the named constructor tunables. The prompt now states the exact names, and tests pin the context contract, but a badly formed generated file can still fail during gating rather than silently skip sensitivity.

## TECH-DEBT Items

- Resolved: DEBT-014.

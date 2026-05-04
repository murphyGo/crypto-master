# Cross-Check: DEBT-014 Sensitivity Grid Wiring

## Scope

Verify that auto-research catalog candidates no longer skip the robustness
sensitivity gate solely because `param_grid` and `strategy_factory` are absent.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Auto-research picks declare sensitivity grids | Complete | `scripts/auto_research_candidates.py` adds `Pick.param_grid` and populates every `TOP_PICKS` entry. |
| Generation context names swept tunables | Complete | `Pick.generation_context` appends the exact constructor keyword names when a grid is present. |
| Feedback loop receives the grid | Complete | `run_picks` passes `param_grid=pick.param_grid` into `FeedbackLoop.propose_new`. |
| Code-type candidates provide a sensitivity factory | Complete | `FeedbackLoop.propose_new` builds a generated-code factory from the saved `.py` strategy when `code_type=True` and a grid is supplied. |
| Regression tests cover the contract | Complete | `tests/test_scripts_auto_research_candidates.py` covers grid presence/cap and generation context; `tests/test_feedback_loop.py` covers generated-code factory creation and gate arguments. |

## Implementation Evidence

- `scripts/auto_research_candidates.py`
- `src/feedback/loop.py`
- `tests/test_scripts_auto_research_candidates.py`
- `tests/test_feedback_loop.py`

## Test Evidence

- `uv run pytest tests/test_scripts_auto_research_candidates.py tests/test_feedback_loop.py -q`
- Result: 40 passed.

## Gaps and Risks

- A generated Python strategy can still fail if it ignores the requested
  constructor tunable names. This is a hard failure during gating, not a silent
  sensitivity SKIP. The prompt contract and tests reduce the risk.

## Unit and Debt Mapping

- **Primary Unit**: `ai-feedback-loop`
- **Secondary Unit**: `backtesting-validation`
- **Related Debt**: DEBT-014 resolved
- **Legacy Phase Context**: Phase 17.1 auto-research operator workflow

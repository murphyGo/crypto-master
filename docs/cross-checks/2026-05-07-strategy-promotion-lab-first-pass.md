# Cross-Check: Strategy Promotion Lab First Pass

## Scope

Verify that the six product-intelligence ideas are represented as AI-DLC units
and that Strategy Promotion Lab has a first-pass implementation with focused
test coverage.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Six new product units are registered | Complete | `unit-of-work.md`, `unit-of-work-story-map.md`, `execution-plan.md`, and `aidlc-state.md` list the six units. |
| Requirements and stories are traceable | Complete | FR-039 through FR-044 and US-017 through US-022 cover the six units. |
| Strategy Promotion Lab has a construction plan | Complete | `aidlc-docs/construction/plans/strategy-promotion-lab-code-generation-plan.md` tracks first-pass scoring and follow-up work. |
| Promotion scoring is side-effect free | Complete | `evaluate_promotion_candidate` returns `PromotionEvaluation` and does not mutate `CandidateRecord` or approval state. |
| Hard blockers reject candidates | Complete | Tests cover failed robustness and liquidated backtests. |
| Weak but non-blocking evidence stays under observation | Complete | Tests cover small trade samples and stricter Sharpe policy thresholds. |
| Observation state is persisted atomically | Complete | `PromotionObservationStore` writes per-candidate JSON snapshots using `atomic_write_text`. |
| Repeated evaluations preserve observation history | Complete | Tests cover first-seen preservation, evaluation count increment, and most-recent-first listing. |
| Dashboard surfaces lab recommendations | Complete | `build_candidates_dataframe` merges promotion decision/score and candidate detail renders factors/blockers. |

## Implementation Evidence

- `src/feedback/promotion_lab.py`
- `src/feedback/__init__.py`
- `tests/test_feedback_promotion_lab.py`
- `aidlc-docs/construction/strategy-promotion-lab/code/implementation-summary.md`

## Test Evidence

- `uv run pytest tests/test_feedback_promotion_lab.py -q`
- `uv run pytest tests/test_dashboard_feedback.py tests/test_feedback_promotion_lab.py -q`
- `uv run ruff check src/feedback/promotion_lab.py src/feedback/__init__.py tests/test_feedback_promotion_lab.py`
- `uv run ruff check src/dashboard/pages/feedback.py tests/test_dashboard_feedback.py`
- `uv run black --check src/feedback/promotion_lab.py src/feedback/__init__.py tests/test_feedback_promotion_lab.py`
- `uv run black --check src/dashboard/pages/feedback.py tests/test_dashboard_feedback.py`

## Gaps and Risks

- Recommendations are still computed only from supplied evidence in this pass.
  Operator actions remain an explicit follow-up step in the construction plan.

## Unit Mapping

- **Primary Unit**: `strategy-promotion-lab`
- **Related Units**: `ai-feedback-loop`, `backtesting-validation`, `dashboard-operator-ui`
- **Registered Future Units**: `sub-account-experiment-marketplace`, `trade-quality-autopsy`, `runtime-safety-score`, `proposal-replay-simulator`, `strategy-correlation-governor`

# Code Generation Plan: strategy-promotion-lab

## Migration Status

New product-intelligence unit. No legacy phase owns this workflow end to end.

## Source Components

| Component | Primary Unit | Secondary Unit |
|-----------|--------------|----------------|
| Feedback candidate state | `strategy-promotion-lab` | `ai-feedback-loop` |
| Robustness gate evidence | `strategy-promotion-lab` | `backtesting-validation` |
| Dashboard review workflow | `strategy-promotion-lab` | `dashboard-operator-ui` |

## Planned Code Generation Steps

- [x] Register the strategy promotion lab unit and construction plan.
- [x] Add a first-pass promotion scoring model for candidate evidence.
- [x] Persist observation-period state for watched candidates.
- [x] Surface promote / reject / keep-watching recommendations in the dashboard.
- [ ] Add operator actions that call existing approval/rejection paths.

## Evidence

- Requirements: FR-027, FR-034, FR-039.
- Primary paths: `src/feedback/`, `src/backtest/`, `src/dashboard/pages/feedback.py`, `tests/test_feedback_*`.

## Future Work

Extend this plan as promotion scoring becomes operational rather than only
computed from in-memory candidate evidence.

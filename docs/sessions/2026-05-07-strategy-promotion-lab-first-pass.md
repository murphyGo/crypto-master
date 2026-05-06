# Session Log: 2026-05-07 - strategy-promotion-lab - First Pass

## Overview

- **Date**: 2026-05-07
- **Primary Unit**: `strategy-promotion-lab`
- **Stage**: Inception Registration / Code Generation
- **Task**: Register six product-intelligence units and start Strategy Promotion Lab development.

## Work Summary

This cycle registered six new AI-DLC units for product-intelligence expansion:
`strategy-promotion-lab`, `sub-account-experiment-marketplace`,
`trade-quality-autopsy`, `runtime-safety-score`,
`proposal-replay-simulator`, and `strategy-correlation-governor`.

The first implementation step adds a side-effect-free promotion scoring model
for feedback-loop candidates. The lab evaluates existing candidate, backtest,
robustness, and performance evidence, then recommends `promote`, `reject`, or
`keep_watching` without changing candidate state.

The second implementation step adds atomic observation persistence. Repeated
candidate evaluations now update a per-candidate snapshot while preserving the
original first-seen timestamp and tracking evaluation count.

## Files Changed

- Modified: `aidlc-docs/aidlc-state.md`
- Modified: `aidlc-docs/inception/application-design/unit-of-work-story-map.md`
- Modified: `aidlc-docs/inception/plans/execution-plan.md`
- Modified: `aidlc-docs/inception/requirements/requirements.md`
- Modified: `aidlc-docs/inception/units/unit-of-work.md`
- Modified: `aidlc-docs/inception/user-stories/stories.md`
- Modified: `src/feedback/__init__.py`
- Created: `aidlc-docs/construction/plans/*-code-generation-plan.md` for the six units
- Created: `aidlc-docs/construction/*/code/implementation-summary.md` for the six units
- Created: `src/feedback/promotion_lab.py`
- Created: `tests/test_feedback_promotion_lab.py`
- Created: `docs/cross-checks/2026-05-07-strategy-promotion-lab-first-pass.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Register six units before coding | Keeps the new product ideas traceable through AI-DLC requirements, stories, plans, and unit maps. |
| Start with a pure scoring function | Avoids mutating strategy state before persistence, dashboard, and operator-action wiring are designed. |
| Keep hard blockers separate from score factors | Failed robustness, wrong candidate state, and liquidation should reject even if other metrics are strong. |
| Default promotion threshold is 90 | A candidate with one meaningful warning should remain in observation rather than receive an immediate promote recommendation. |
| Persist observations outside candidate state | Promotion lab recommendations are operator workflow state, so they live under `feedback/promotion_lab` without mutating `CandidateRecord`. |

## Verification

- `uv run pytest tests/test_feedback_promotion_lab.py -q`
- `uv run ruff check src/feedback/promotion_lab.py src/feedback/__init__.py tests/test_feedback_promotion_lab.py`
- `uv run black --check src/feedback/promotion_lab.py src/feedback/__init__.py tests/test_feedback_promotion_lab.py`

## Follow-Up

- Surface promotion recommendations in the dashboard feedback workflow.
- Wire operator promote/reject actions through existing approval and rejection paths.

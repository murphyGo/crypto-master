# Session Log: 2026-05-07 - runtime-safety-score - Contract

## Overview

- **Date**: 2026-05-07
- **Primary Unit**: `runtime-safety-score`
- **Stage**: Code Generation
- **Task**: Define safety score inputs and status bands.

## Work Summary

This cycle starts Runtime Safety Score with a stable model contract. The new
module defines bounded input counters, score threshold policy, operator-facing
bands, and the final score shape without yet extracting events from the
activity log.

The follow-up step adds pure activity aggregation and score computation.
Runtime activity events now map into `RuntimeSafetyInputs`, and
`compute_runtime_safety_score` applies capped penalties with explanatory
factors.

The dashboard surfacing step adds a Runtime Safety section to the Engine page,
showing score, band, and factors from the same pure scoring helper.

The notification summary step adds a compact formatter and lets proposal
notifications carry an optional `RuntimeSafetyScore`. Slack, Telegram, and
email payloads now surface `runtime_safety: <score>/100 <band>` when the
dispatcher is given a score.

Review follow-up wiring now passes the current runtime safety score from
`TradingEngine` into proposal notifications. Correlation-warning activity
events also feed the safety inputs as concentration warnings.

## Files Changed

- Created: `src/runtime/safety_score.py`
- Created: `tests/test_runtime_safety_score.py`
- Modified: `src/runtime/__init__.py`
- Modified: `src/proposal/notification.py`
- Modified: `tests/test_proposal_notification.py`
- Modified: `aidlc-docs/construction/plans/runtime-safety-score-code-generation-plan.md`
- Modified: `aidlc-docs/construction/runtime-safety-score/code/implementation-summary.md`
- Created: `docs/cross-checks/2026-05-07-runtime-safety-score-contract.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Separate inputs from score computation | Event extraction can evolve while the operator-facing score contract stays stable. |
| Use explicit status bands | Operators need scan-friendly states, not only a raw number. |
| Validate threshold ordering | Misordered score thresholds would silently invert operator semantics. |
| Keep scoring pure | Dashboard and notification surfaces can call the same deterministic function without side effects. |
| Surface dashboard before notifications | The dashboard already consumes activity events, so it is the lowest-risk first surface. |
| Make notification safety optional | Existing proposal notification callers continue to work until runtime paths decide when to attach the latest score. |
| Count correlation warnings in safety | Concentration is a runtime safety signal and is now visible before hard rejection is enabled. |

## Verification

- `uv run pytest tests/test_runtime_safety_score.py -q`
- `uv run pytest tests/test_dashboard_engine.py tests/test_runtime_safety_score.py -q`
- `uv run ruff check src/runtime/safety_score.py src/runtime/__init__.py tests/test_runtime_safety_score.py`
- `uv run ruff check src/dashboard/pages/engine.py tests/test_dashboard_engine.py`
- `uv run black --check src/runtime/safety_score.py src/runtime/__init__.py tests/test_runtime_safety_score.py`
- `uv run black --check src/dashboard/pages/engine.py tests/test_dashboard_engine.py`
- `uv run pytest tests/test_proposal_notification.py tests/test_runtime_safety_score.py -q`
- `uv run ruff check src/proposal/notification.py src/runtime/safety_score.py tests/test_proposal_notification.py tests/test_runtime_safety_score.py`
- `uv run black --check src/proposal/notification.py src/runtime/safety_score.py tests/test_proposal_notification.py tests/test_runtime_safety_score.py`
- `uv run pytest tests/test_runtime_correlation_governor.py tests/test_runtime_safety_score.py tests/test_runtime_engine.py::test_notification_receives_runtime_safety_score tests/test_runtime_engine.py::test_correlation_warning_is_advisory_by_default tests/test_runtime_engine.py::test_correlation_gate_rejects_when_enabled -q`

## Follow-Up

- Decide which signals become hard pause gates versus advisory warnings.

# Session Log: 2026-05-07 - strategy-correlation-governor - Inputs

## Overview

- **Date**: 2026-05-07
- **Primary Unit**: `strategy-correlation-governor`
- **Stage**: Code Generation
- **Task**: Define strategy and asset correlation inputs from backtest and runtime data.

## Work Summary

This cycle starts Strategy Correlation Governor with a shared exposure input
contract. `CorrelationExposure` normalizes backtest trades and runtime
`TradeHistory` records into the same shape: source, exposure id, sub-account,
strategy id, symbol, side, open/close time, entry price, quantity, notional, and
PnL.

`CorrelationInputSet` can be built from backtest result trade ledgers or
runtime trade history and includes simple sub-account and symbol filters for the
next duplicate-exposure warning step.

The warning step adds `compute_duplicate_exposure_warnings`, which groups
normalized exposures by `symbol+side` and `strategy+symbol+side` across
sub-accounts. Warnings include the involved sub-account ids, exposure ids, total
notional, and an operator-readable message. Thresholds are configurable through
`CorrelationWarningPolicy`.

The gate step adds `evaluate_correlation_gate`. The gate is disabled by default,
so correlated candidates are allowed with advisory warnings. When
`CorrelationGateConfig.enabled` is true, candidates that participate in
duplicate-exposure warnings are rejected with the relevant warning list attached.

Review follow-up wiring now connects the pure gate to `TradingEngine`. The
engine emits `correlation_warning` activity events in advisory mode and rejects
only when the opt-in gate flag is enabled. Correlation inputs now allow an empty
existing exposure set and expose an `open_only` filter so closed historical
trades do not block new candidates.

## Files Changed

- Created: `src/runtime/correlation_governor.py`
- Created: `tests/test_runtime_correlation_governor.py`
- Modified: `src/runtime/__init__.py`
- Modified: `aidlc-docs/construction/plans/strategy-correlation-governor-code-generation-plan.md`
- Modified: `aidlc-docs/construction/strategy-correlation-governor/code/implementation-summary.md`
- Modified: `aidlc-docs/aidlc-state.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Normalize backtest and runtime trades into one exposure model | Warning and gate logic should not fork by data source. |
| Use strategy lookup for runtime history | `TradeHistory` stores `performance_record_id`, so strategy names remain an optional enrichment. |
| Keep this step advisory-input only | Correlation blocking semantics belong in the later gate step. |
| Avoid runtime imports of backtest classes | `runtime.__init__` is imported by trading modules; type-only imports prevent a circular import. |
| Count distinct sub-accounts, not repeated trades alone | The unit target is cross-account duplicate exposure; repeated trades inside one account are a separate sizing concern. |
| Default the gate to disabled | The unit plan calls for optional gating; advisory mode avoids surprising live/paper rejection until operators opt in. |
| Log warnings even when not rejecting | Operators and the runtime safety score need concentration visibility before hard blocking is enabled. |

## Verification

- `uv run pytest tests/test_runtime_correlation_governor.py -q`
- `uv run ruff check src/runtime/correlation_governor.py src/runtime/__init__.py tests/test_runtime_correlation_governor.py`
- `uv run black --check src/runtime/correlation_governor.py src/runtime/__init__.py tests/test_runtime_correlation_governor.py`
- `uv run mypy src`
- `uv run pytest tests/test_runtime_correlation_governor.py tests/test_runtime_safety_score.py tests/test_runtime_engine.py::test_notification_receives_runtime_safety_score tests/test_runtime_engine.py::test_correlation_warning_is_advisory_by_default tests/test_runtime_engine.py::test_correlation_gate_rejects_when_enabled -q`

## Follow-Up

- Add dashboard controls if operators need to tune correlation policy from UI.

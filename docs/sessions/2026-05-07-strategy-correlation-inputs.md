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

## Verification

- `uv run pytest tests/test_runtime_correlation_governor.py -q`
- `uv run ruff check src/runtime/correlation_governor.py src/runtime/__init__.py tests/test_runtime_correlation_governor.py`
- `uv run black --check src/runtime/correlation_governor.py src/runtime/__init__.py tests/test_runtime_correlation_governor.py`
- `uv run mypy src`

## Follow-Up

- Add optional runtime rejection gate for excessive correlated exposure.

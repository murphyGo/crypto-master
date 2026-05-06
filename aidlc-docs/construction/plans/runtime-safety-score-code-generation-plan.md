# Code Generation Plan: runtime-safety-score

## Migration Status

New product-intelligence unit for operator safety rollups.

## Planned Code Generation Steps

- [x] Register the runtime safety score unit and construction plan.
- [x] Define safety score inputs and status bands.
- [x] Compute score from activity, notification, LLM, quote freshness, drawdown, and liquidation signals.
- [x] Surface score in engine dashboard and notification summaries.

## Evidence

- Requirements: FR-014, FR-015, FR-042, NFR-007.
- Primary paths: `src/runtime/`, `src/proposal/`, `src/dashboard/pages/engine.py`.

## Future Work

Decide which signals become hard pause gates versus advisory warnings.

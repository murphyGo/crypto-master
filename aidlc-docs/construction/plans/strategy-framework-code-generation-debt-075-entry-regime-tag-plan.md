# Code Generation Plan: strategy-framework DEBT-075

## Task

Resolve DEBT-075 by stamping proposals/performance records with an entry-time
market regime label and aggregating per-regime expectancy from performance
records.

## Related Context

- Unit: `strategy-framework`
- Secondary unit: `strategy-tuning`
- Stage: Code Generation
- Debt: DEBT-075
- Requirements: FR-005, FR-027, FR-034, FR-039, NFR-006, NFR-007
- Related Stories: US-002, US-003, US-017, US-015, US-016
- Existing classifier evidence: `src/backtest/validator.py::_classify_regimes`

## Steps

- [x] Add a public entry-regime helper that reuses the trailing-SMA classifier
      without look-ahead.
- [x] Stamp every generated `Proposal` with the regime from the primary OHLCV
      stream used for analysis.
- [x] Persist that label onto closed-trade `PerformanceRecord` rows.
- [x] Add `TechniquePerformance` per-regime expectancy aggregates.
- [x] Add targeted tests for proposal stamping, performance persistence, legacy
      default loading, and per-regime aggregation.
- [x] Update TECH-DEBT, debt-unit-map, session log, cross-check, and AI-DLC
      state notes.

## Completion Checklist

- [x] Code implemented.
- [x] Tests pass.
- [x] DEBT-075 marked resolved or narrowed.
- [x] Session log and cross-check added.
- [x] Work committed and pushed as one unit slice.

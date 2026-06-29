# Code Generation Plan: strategy-framework DEBT-076

## Task

Resolve DEBT-076 by making regime-gate score/threshold telemetry match the
average-expectancy criterion when `regime_require_positive_in_all=False`.

## Related Context

- Unit: `strategy-framework`
- Stage: Code Generation
- Debt: DEBT-076
- Requirements: FR-005, FR-027, FR-034, FR-039, NFR-006
- Related Stories: US-002, US-003, US-015, US-016
- Target: `src/backtest/validator.py::_gate_regime`

## Steps

- [x] Keep all-positive mode reporting as evaluable-pass count over evaluable
      count.
- [x] Change average mode to report `score=avg` and `threshold=0.0`.
- [x] Add a targeted regression test pinning average-mode telemetry.
- [x] Update TECH-DEBT, debt-unit-map, session log, cross-check, and AI-DLC
      state notes.

## Completion Checklist

- [x] Code implemented.
- [x] Tests pass.
- [x] DEBT-076 marked resolved.
- [x] Session log and cross-check added.
- [x] Work committed and pushed as one unit slice.

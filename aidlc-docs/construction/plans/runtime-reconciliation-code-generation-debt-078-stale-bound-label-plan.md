# Code Generation Plan: runtime-reconciliation DEBT-078

## Task

Resolve DEBT-078: prevent old, backfilled monitorable trades from being
recorded as fresh `stop_loss` / `take_profit` exits when the monitor first sees
a bound breach after a long unmonitored gap, and consolidate duplicate bounds
lookup walks used by runtime reconciliation tooling.

## Related Context

- Unit: `runtime-reconciliation`
- Stage: Code Generation
- Debt: DEBT-078
- Requirements: FR-010, FR-014, FR-029, FR-036, NFR-007, NFR-008, NFR-012
- Related Stories: US-007, US-009, US-012, US-015, US-016
- Likely files:
  - `src/runtime/position_monitor.py`
  - `src/strategy/performance.py`
  - `src/tools/backfill_paper_sl_tp.py`
  - `src/tools/repair_paper_trade_bounds_from_proposals.py`
  - targeted tests under `tests/`

## Steps

- [x] Gate stale normal SL/TP exits: if a monitorable trade is older than the
      always-on reconciliation age wall, close with `orphan_force_close` rather
      than `stop_loss` / `take_profit`.
- [x] Extract shared performance-record bounds indexing so the runtime resolver
      and `backfill_paper_sl_tp` use the same raw-JSON implementation.
- [x] Extract shared proposal-history bounds indexing so
      `repair_paper_trade_bounds_from_proposals` no longer owns a private
      proposal walk.
- [x] Add targeted tests for stale-backfilled SL/TP labeling and bounds-index
      reuse behavior.
- [x] Run targeted tests and formatting/lint/type checks appropriate to the
      changed files.
- [x] Update TECH-DEBT, debt-unit-map, session log, cross-check, and AI-DLC
      state notes.

## Completion Checklist

- [x] Code implemented.
- [x] Tests pass.
- [x] DEBT-078 marked resolved or narrowed.
- [x] Session log and cross-check added.
- [x] Work committed and pushed as one unit slice.

# Code Generation Plan: proposal-funnel-audit DEBT-079

## Task

Resolve DEBT-079 by emitting candidate-level deselection evidence before
per-symbol dedup drops non-winning strategy proposals.

## Related Context

- Unit: `proposal-funnel-audit`
- Secondary unit: `proposal-runtime`
- Stage: Code Generation
- Debt: DEBT-079
- Requirements: FR-011, FR-012, FR-014, FR-036, NFR-007, NFR-012
- Related Stories: US-002, US-003, US-015
- Predecessor: DEBT-074

## Steps

- [x] Add a stable activity event type for candidate deselection.
- [x] Emit one event per non-winning candidate after per-symbol dedup in
      `propose_bitcoin` and `propose_altcoins`.
- [x] Include losing/winning technique names, proposal ids, composite scores,
      sub-account, symbol, and reason in the payload.
- [x] Add targeted tests for lower-composite deselection and no-event single
      candidate behavior.
- [x] Update TECH-DEBT, debt-unit-map, session log, cross-check, and AI-DLC
      state notes.

## Completion Checklist

- [x] Code implemented.
- [x] Tests pass.
- [x] DEBT-079 marked resolved.
- [x] Session log and cross-check added.
- [x] Work committed and pushed as one unit slice.

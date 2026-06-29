# Code Generation Plan: proposal-funnel-audit DEBT-074

## Task

Resolve DEBT-074 by making the `vcp_breakout` emitted-but-zero-open anomaly
reproducible from runtime data and filing the concrete follow-up when the
terminating point is identified.

## Related Context

- Unit: `proposal-funnel-audit`
- Secondary unit: `strategy-framework`
- Stage: Code Generation
- Debt: DEBT-074
- Requirements: FR-011, FR-012, FR-014, FR-036, NFR-007, NFR-012
- Related Stories: US-002, US-003, US-015
- Existing surfaces: `src/proposal/fail_closed_metrics.py`,
  `src/proposal/funnel.py`, `src/proposal/interaction.py`

## Steps

- [x] Add a read-only audit helper/tool that counts fail-closed emissions,
      persisted proposal records, and opened/linked funnel states for one
      `(sub_account, technique)` pair.
- [x] Classify the emitted/no-proposal/no-trade pattern as a pre-funnel
      candidate-selection/history gap instead of a downstream gate rejection.
- [x] Add targeted tests for the vcp-shaped gap and a healthy opened proposal
      path.
- [x] Register the concrete follow-up debt for candidate-level deselection
      observability.
- [x] Update TECH-DEBT, debt-unit-map, session log, cross-check, and AI-DLC
      state notes.

## Completion Checklist

- [x] Code implemented.
- [x] Tests pass.
- [x] DEBT-074 marked resolved with concrete follow-up.
- [x] Session log and cross-check added.
- [x] Work committed and pushed as one unit slice.

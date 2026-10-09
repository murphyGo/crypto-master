# DEBT-084 economic win-rate correction

- Unit: `strategy-framework`; secondary `strategy-tuning`, `dashboard-operator-ui`.
- Stages: bounded Functional Design, Code Generation, Build and Test.
- Requirements: FR-005, FR-029, NFR-007; stories US-002, US-012, US-019.
- Legacy: DEBT-073 fee aggregates, DEBT-069 recommendation evidence.
- Authorization: operator approved the registered bounded fixes and requested implementation with a separate commit/push per completed item on 2026-10-09.
- [Answer]: preserve exit-label statistics; add economic outcomes; keep applied trading policy unchanged. No additional policy choice is required for this correction.

## Steps

- [x] Define the additive economic outcome contract in the design addendum.
- [x] Add economic aggregates in `src/strategy/performance.py`; use them for recommendation win rate and the strategy dashboard.
- [x] Verify positive/negative/zero time-stop, fee-flipped TP, actual entry, unknown legacy fees, pending/synthetic exclusion and old-summary compatibility.
- [x] Run focused pytest, changed-file Black/Ruff and source mypy.
- [x] Update debt/map/state, session and cross-check.

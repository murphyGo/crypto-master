# DEBT-078 explicit bound-recovery provenance

- Unit: runtime-reconciliation; secondary strategy-framework, trading-core.
- Requirements: FR-010, FR-014, FR-029, NFR-007, NFR-008, NFR-012; US-007, US-008, US-019, US-020.
- Stages: bounded Functional Design, NFR Requirements/Design, Code Generation, Build and Test.
- Authorization: operator approved this registered repair and requested item-by-item implementation, commit and push.
- [Answer]: normal aged positions retain actual SL/TP reasons; genuinely recovered stale first observations retain conservative labeling; execution prices and PnL stay unchanged.

- [x] Specify additive recovery provenance and first healthy observation semantics.
- [x] Define restart, persistence-failure, backwards-compatibility and paper/live parity rules.
- [x] Wire recovery writers, tracker, paper/live acknowledgement and monitor reason selection.
- [x] Test normal 26h paper/live opens with null reverse links, recovered-first-breach protection, healthy observation/restart, young repairs and unchanged PnL.
- [x] Run runtime/trading/tool tests, changed-file Black/Ruff and source mypy.
- [x] Close debt/map/state and record session/cross-check.

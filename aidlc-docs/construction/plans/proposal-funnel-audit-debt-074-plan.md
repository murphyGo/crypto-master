# DEBT-074 neutral-aware funnel audit

- Unit: proposal-funnel-audit; secondary proposal-runtime.
- Requirements: FR-011, FR-012, FR-013, FR-014, NFR-007; US-005, US-006, US-012.
- Legacy: DEBT-061 attempt denominator, DEBT-079 deselection events.
- Authorization: operator approved the registered correction and requested implementation/commit/push per item.
- [Answer]: do not infer neutral or deselection from absent proposals; retain the legacy fail-closed denominator.

- [x] Specify attempt/result/candidate/selection stages and legacy coverage.
- [x] Add additive stage counters and instrument existing decisions without changing selection.
- [x] Update read-only audit classification/help to distinguish proven neutral-only observations from unknown pre-funnel gaps.
- [x] Test legacy and partial coverage, neutral-only, strategy/sizing failure, candidate deselection, top-K selection, opened rows and persistence failure.
- [x] Run proposal/audit/consumer tests and static checks; close debt/map/state with session/cross-check.

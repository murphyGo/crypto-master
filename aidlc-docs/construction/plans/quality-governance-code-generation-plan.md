# Code Generation Plan: quality-governance

## Migration Status

Legacy Phase work is migrated as brownfield-complete. This plan is not a queue
of unfinished historical tasks.

## Source Legacy Components

| Component | Phase | Secondary Unit |
|-----------|-------|----------------|
| Project Setup | 1 | `persistence-data-integrity` |
| Pre-Existing Lint/Type Sweep | 11 | |
| Residual mypy Sweep | 12 | |
| Cleanup Batch | 13 | |
| AIDLC Hygiene Backfill | 23 | |
| Phase 17.2 / 17.3 / 17.4 / 17.5 Numbering Reconciliation | 23 | |
| Code Hygiene Sweep | 26 | |
| Observability + Logger Test-Friendliness | 26 | `notifications-ops` |
| Black Sweep | 26 | |

## Completed Code Generation Steps

- [x] Establish project structure, packaging, tests, and repository hygiene.
- [x] Complete lint/type sweeps and cleanup batches.
- [x] Backfill AIDLC session/cross-check/drift documentation.
- [x] Reconcile legacy phase numbering.
- [x] Complete code hygiene, observability testability, and formatting sweeps.
- [x] Migrate legacy development plan into AI-DLC construction unit plans.

## Evidence

- Requirements: cross-cutting traceability and process controls.
- Primary paths: `docs/`, `.agents/`, `aidlc-docs/`, `aidlc-workflows/`.
- Cross-checks: phase 11, phase 12, phase 13, phase 23, and phase 26 reports.
- Session logs: related Phase 1, 11, 12, 13, 23, and 26 entries under `docs/sessions/`.

## Future Work

Add future AI-DLC workflow, quality gate, documentation migration, or agent
skill updates as new unchecked steps here.

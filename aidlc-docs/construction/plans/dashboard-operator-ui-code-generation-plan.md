# Code Generation Plan: dashboard-operator-ui

## Migration Status

Legacy Phase work is migrated as brownfield-complete. This plan is not a queue
of unfinished historical tasks.

## Source Legacy Components

| Component | Phase | Secondary Unit |
|-----------|-------|----------------|
| UI Dashboard | 7 | |
| Engine Status Dashboard Page | 8 | `proposal-runtime` |
| Trade-Quality Diagnostic | 18 | `proposal-runtime` |
| Multi-Paper-Account Support + YAML Config + Dashboard | 19 | `sub-account-capital-segmentation` |

## Completed Code Generation Steps

- [x] Implement Streamlit dashboard shell and operator pages.
- [x] Add engine status dashboard behavior.
- [x] Add trade-quality diagnostic visibility.
- [x] Add multi-paper-account and sub-account dashboard support.
- [x] Route Feedback Loop dashboard and Home command-center candidate reads
      through `Settings.data_dir` so Fly runtime state under `/data` is visible.

## Evidence

- Requirements: FR-028, FR-029, FR-030, FR-031, FR-032, FR-036, FR-038, NFR-003.
- Primary paths: `src/dashboard/`, `tests/test_dashboard_*`.
- Cross-checks: phase 7, phase 8, phase 18, and phase 19 reports.
- Session logs: related Phase 7, 8, 18, and 19 entries under `docs/sessions/`.
  Runtime data-dir follow-up:
  `docs/sessions/2026-05-07-dashboard-feedback-runtime-data-dir.md`.

## Future Work

Add future operator UI, dashboard metric, monitoring, or workflow changes as new
unchecked steps here.

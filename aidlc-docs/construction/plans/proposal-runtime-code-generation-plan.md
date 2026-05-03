# Code Generation Plan: proposal-runtime

## Migration Status

Legacy Phase work is migrated as brownfield-complete. This plan is not a queue
of unfinished historical tasks.

## Source Legacy Components

| Component | Phase | Secondary Unit |
|-----------|-------|----------------|
| Trading Proposal | 6 | |
| Trading Engine Runtime | 8 | `trading-core` |
| Engine Status Dashboard Page | 8 | `dashboard-operator-ui` |
| Multi-Technique Per-Symbol Scan | 10 | `strategy-framework` |
| OHLCV Cache for Multi-Technique Scan | 11 | `exchange-integration` |
| Notification Push Backend | 11 | `notifications-ops` |
| ProposalHistory.purge_old Wiring | 11 | `persistence-data-integrity` |
| Cross-Cycle Position Cap | 12 | `trading-core` |
| Diagnostic Clarity | 15 | `notifications-ops` |
| Portfolio Snapshot Recording in Runtime Cycle | 17 | `trading-core` |
| Stale-Quote Sanity Gate at Proposal Fill | 18 | `trading-core` |
| Trade-Quality Diagnostic | 18 | `dashboard-operator-ui` |
| Sub-Account Engine Integration | 19 | `sub-account-capital-segmentation` |
| Stale-Quote Payload Timestamp Coherence | 21 | `persistence-data-integrity` |

## Completed Code Generation Steps

- [x] Implement proposal generation, accept/reject flow, and history persistence.
- [x] Implement runtime cycle orchestration and dashboard-facing status behavior.
- [x] Add multi-technique scan, OHLCV cache use, and notification dispatch hooks.
- [x] Add purge wiring, cross-cycle cap, diagnostic clarity, and stale-quote gates.
- [x] Integrate portfolio snapshots, trade-quality diagnostics, and sub-account runtime behavior.

## Evidence

- Requirements: FR-011, FR-012, FR-013, FR-014, FR-015, FR-026, NFR-012.
- Primary paths: `src/proposal/`, `src/runtime/`, `src/main.py`, `tests/test_proposal_*`, `tests/test_runtime_*`.
- Cross-checks: phase 6, phase 8, phase 10, phase 11, phase 12, phase 15, phase 17, phase 18, phase 19, and phase 21 reports.
- Session logs: related Phase 6, 8, 10, 11, 12, 15, 17, 18, 19, and 21 entries under `docs/sessions/`.

## Future Work

Add future proposal lifecycle, runtime, activity-log, cap, stale-quote, or
operator diagnostic changes as new unchecked steps here.

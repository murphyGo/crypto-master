# Code Generation Plan: persistence-data-integrity

## Migration Status

Legacy Phase work is migrated as brownfield-complete. This plan is not a queue
of unfinished historical tasks.

## Source Legacy Components

| Component | Phase | Secondary Unit |
|-----------|-------|----------------|
| Project Setup | 1 | `quality-governance` |
| Log Retention Policy | 10 | `notifications-ops` |
| Volume-Aware Default Paths | 10 | `backtesting-validation` |
| ProposalHistory.purge_old Wiring | 11 | `proposal-runtime` |
| UTC-Aware Timestamp Helper + Adapter Migration | 21 | `exchange-integration` |
| `JsonlRotator` UTC Month Boundary | 21 | |
| Stale-Quote Payload Timestamp Coherence | 21 | `proposal-runtime` |
| Atomic JSON Persistence Helper | 22 | |
| Snapshot Dataset + Format | 25 | `backtesting-validation` |
| Atomic-Write Completion | 26 | |

## Completed Code Generation Steps

- [x] Establish project/test persistence structure.
- [x] Add log retention, volume-aware defaults, and purge wiring.
- [x] Implement UTC timestamp helpers and JSONL rotation month-boundary behavior.
- [x] Align stale-quote payload timestamp coherence.
- [x] Implement atomic JSON persistence helper and snapshot data format support.

## Evidence

- Requirements: NFR-006, NFR-007, NFR-008.
- Primary paths: `src/utils/io.py`, `src/utils/time.py`, `src/runtime/jsonl_rotator.py`, `tests/test_utils_*`, `tests/test_jsonl_rotator.py`.
- Cross-checks: phase 10, phase 11, phase 21, phase 22, phase 25, and phase 26 reports.
- Session logs: related Phase 1, 10, 11, 21, 22, 25, and 26 entries under `docs/sessions/`.

## Future Work

Add future atomicity, timestamp, rotation, path, or persistence contract changes
as new unchecked steps here.

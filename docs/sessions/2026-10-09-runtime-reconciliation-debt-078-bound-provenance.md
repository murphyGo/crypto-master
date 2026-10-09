# Implementation session: DEBT-078

- Unit: `runtime-reconciliation`
- Requirements / stories: FR-010, FR-014, FR-029, NFR-007, NFR-008, NFR-012; US-007, US-008, US-019, US-020
- Plan: `aidlc-docs/construction/plans/runtime-reconciliation-debt-078-plan.md`
- Authorization: operator requested implementation of the five registered findings, a separate worktree, and commit/push after each completed item.

## Result

Replaced null reverse-performance-link inference with explicit pending bound-recovery provenance. Paper/live rehydration and repair tools mark actual recovered bounds; a successful non-breaching monitor observation clears the marker persistently. Normal aged SL/TP exits retain their trigger and genuine stale first observations remain conservative.

## Verification

559 runtime/trading/tool/performance/import tests pass; changed-file Black/Ruff and source mypy pass (123 files). Real paper and mocked-live 26h normal-open cases retain SL/TP with null reverse links and unchanged PnL/order counts; recovery, restart, IO-failure and concurrent-repair cases pass.

## Scope and remaining work

The new boolean is additive and defaults false for old ledgers. Historical repairs without explicit provenance cannot be retroactively identified; no existing runtime data was migrated or repair tool run against production. Persistence failure logs and preserves monitoring/conservative attribution. No sizing, bound prices, fee/PnL math, live safeguards, configured policy or deployment change.

DEBT-078 is resolved in source. Deployment is outside this task; no current production behavior change is claimed.

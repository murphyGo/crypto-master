# Unit cross-check: DEBT-074

- Unit: `proposal-funnel-audit`
- Requirements / stories: FR-011, FR-012, FR-013, FR-014, NFR-007; US-005, US-006, US-012
- Plan: `aidlc-docs/construction/plans/proposal-funnel-audit-debt-074-plan.md`
- Authorization: operator requested implementation of the five registered findings, a separate worktree, and commit/push after each completed item.

## Result

Added observed-attempt, neutral/non-neutral, built-candidate and final-selection counters without changing the legacy fail-closed denominator. The read-only audit identifies fully observed neutral-only history and otherwise explicitly preserves no-signal/selection/history uncertainty instead of asserting missing candidates.

## Verification

515 proposal/runtime/dashboard/audit tests, CLI help, changed-file Black/Ruff and mypy (123 source files) pass. Cases include legacy/partial stage coverage, neutral-only, strategy/sizing failure, symbol dedup, top-K, per-account routing, counter-write failure and read-only audit. Frozen VCP replay remains opened (25383 attempts, one persisted linked proposal, no historical stage coverage).

## Scope and remaining work

New stage counters cover only new observations and cannot reconstruct legacy neutral results. Existing candidate-deselection events, selection order, sizing, fail-closed rate, proposal persistence, final states and live controls remain unchanged. No production data was written or migrated and no deployment was performed.

DEBT-074 is resolved in source. Deployment is outside this task; no current production behavior change is claimed.

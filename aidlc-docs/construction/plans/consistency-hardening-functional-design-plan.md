# Functional Design Plan: consistency-hardening

## Task

Create a first-class unit for refactor and code-consistency hardening items
surfaced by the 2026-05-08 five-subagent review. The unit should turn
cross-cutting findings into bounded implementation slices without losing the
owning functional units.

## Related Context

- Unit: `consistency-hardening`
- Stage: Functional Design
- Source review: 2026-05-08 five-subagent refactor/code-consistency review
- Primary related units:
  - `exchange-integration`
  - `trading-core`
  - `proposal-runtime`
  - `runtime-safety-score`
  - `notifications-ops`
  - `ai-feedback-loop`
  - `strategy-framework`
  - `backtesting-validation`
  - `dashboard-operator-command-center`
  - `quality-governance`
- Related debt anchors:
  - `DEBT-053`: persisted open-position hydration after runtime restart
  - `DEBT-054`: account-scoped exchange router for sub-account runtime

## Steps

- [x] Capture the unit boundary and triage categories.
- [x] Create a construction functional-design artifact for future
      implementation.
- [x] Sync unit indexes:
      `aidlc-docs/inception/units/unit-of-work.md` and
      `aidlc-docs/aidlc-state.md`.
- [ ] Implement the first hardening slice in a later code-generation stage.

## Candidate Implementation Slices

1. Live exchange credential-mode alignment.
2. Generated strategy promotion and atomic artifact writes.
3. Runtime sub-account failure isolation and notification failure visibility.
4. Dashboard command-center account-scope and aggregate equity consistency.
5. Backtest validation and multi-timeframe harness contract hardening.
6. Timestamp, JSONL, and proposal lifecycle persistence consistency.

## Verification

- [ ] Each code-generation slice should run targeted tests for its owning unit.
- [ ] Cross-cutting slices should update session logs and cross-check evidence.
- [ ] When runtime or dashboard behavior changes, add regression tests before
      implementation is considered complete.

## Completion Checklist

- [x] Unit registered.
- [x] Functional design created.
- [x] Active construction plan created.
- [ ] Code intentionally deferred.

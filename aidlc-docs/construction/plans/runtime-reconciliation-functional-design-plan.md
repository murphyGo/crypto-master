# Functional Design Plan: runtime-reconciliation

## Task

Define deployed paper-runtime reconciliation so open trades, SL/TP bounds,
proposal/performance links, balance snapshots, monitor state, and dashboard
position views stay consistent after restarts and migrations.

## Related Context

- Unit: `runtime-reconciliation`
- Stage: Functional Design
- Requirements: FR-010, FR-014, FR-029, FR-036, NFR-007, NFR-008, NFR-012
- Source evidence: 2026-05-13 Fly snapshot showed 49 open paper trades, 44
  without persisted SL/TP, 6,148 monitor errors, and portfolio snapshots showing
  zero positions while ledger rows remained open.
- Related units: `trading-core`, `persistence-data-integrity`,
  `proposal-runtime`, `dashboard-operator-command-center`, `notifications-ops`

## Steps

- [ ] Specify monitorable vs reconciliation-required open trade states.
- [ ] Specify operator repair flow for `src.tools.backfill_paper_sl_tp` and any
      follow-up close/reconcile command.
- [ ] Specify startup health checks for open trades missing SL/TP, proposal ids,
      performance links, or balance snapshots.
- [ ] Specify dashboard/runtime health signals that block silent cash-only
      reporting when ledger trades are open.
- [ ] Create implementation plan covering runtime, tools, dashboard, and tests.

## Verification

- [ ] Design artifact under `aidlc-docs/construction/runtime-reconciliation/`.
- [ ] Target tests identified for paper trading, runtime engine, tools, and
      dashboard health views.

## Completion Checklist

- [ ] Functional design complete.
- [ ] Code-generation plan created.
- [ ] Session log and cross-check added when implemented.

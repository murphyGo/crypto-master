# Functional Design Plan: proposal-funnel-audit

## Task

Define a single operator-visible proposal funnel from generation through score
thresholds, post-approval gates, cap/correlation/stale-quote decisions, trade
open, close, and outcome linkage.

## Related Context

- Unit: `proposal-funnel-audit`
- Stage: Functional Design
- Requirements: FR-011, FR-012, FR-013, FR-014, FR-015, FR-029, FR-043,
  NFR-007, NFR-012
- Source evidence: 2026-05-13 Fly snapshot had 2,624 proposal files, 773
  runtime accepted events, 118 final accepted proposal files, and 100 opened
  positions, with many post-approval cap rejections.
- Related units: `proposal-runtime`, `dashboard-operator-ui`,
  `dashboard-operator-command-center`, `strategy-correlation-governor`

## Steps

- [x] Specify canonical funnel states and transition semantics.
- [x] Specify how post-approval rejections are recorded without making accepted
      and rejected counters ambiguous.
- [x] Specify cap diagnostics: blocking trade id, entry time, age, unrealized
      PnL, monitorability, cap, and open count.
- [x] Specify dashboard summaries by account, strategy, symbol, gate, and time.
- [x] Create implementation plan covering proposal records, activity events,
      runtime counters, dashboard views, and tests.

## Verification

- [x] Design artifact under `aidlc-docs/construction/proposal-funnel-audit/`.
- [x] Target tests identified for proposal interaction, runtime engine, and
      dashboard funnel rendering.

## Completion Checklist

- [x] Functional design complete.
- [x] Code-generation plan created.
- [ ] Session log and cross-check added when implemented.

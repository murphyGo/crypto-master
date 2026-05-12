# Code Generation Plan: proposal-funnel-audit

## Task

Implement the existing `proposal-funnel-audit` functional design: canonical
funnel states on `ProposalRecord`, `record_id` join field on every
post-acceptance gate event, cap-rejection diagnostic payload with blocking
trades, derived funnel-conversion aggregator, and operator dashboard views.

## Related Context

- Unit: `proposal-funnel-audit`
- Stage: Code Generation
- Requirements: FR-011, FR-012, FR-013, FR-014, FR-015, FR-029, FR-043,
  NFR-007, NFR-012
- Functional design: `aidlc-docs/construction/proposal-funnel-audit/functional-design/spec.md`
- Source evidence: 2026-05-13 Fly snapshot showed 2,624 proposal files,
  773 runtime-accepted events, 118 final-accepted proposal files, and
  100 opened positions — the drop-off is invisible on today's dashboard.
- Related units: `proposal-runtime`, `runtime-reconciliation`,
  `strategy-correlation-governor`, `market-regime`,
  `dashboard-operator-ui`, `dashboard-operator-command-center`

## Steps

- [ ] Add `final_state` enum + field to `ProposalRecord` with legacy-record
      backfill inference on read.
- [ ] Thread `record_id` into every post-acceptance gate event payload
      (`market_regime`, `correlation`, `trend_filter`, `sibling_family`,
      `runtime_safety_pause`, `total_cap`, `symbol_cap`, `stale_quote`).
- [ ] Update `_handle_proposal` so every gate rejection rewrites
      `final_state` via `record.model_copy(update={...})`; accept path
      sets `proposal_opened`, `_execute` success path sets `trade_opened`.
- [ ] Build `_build_cap_blocker_payload` helper with the §3 blocking-trades
      shape and the `runtime-reconciliation` `monitorable` flag.
- [ ] Wire `attach_outcome` to set `final_state=outcome_linked` and
      propagate `proposal_id` / `record_id` into `POSITION_CLOSED` details.
- [ ] Add `src/proposal/funnel.py` with `FunnelCounts` Pydantic model and
      `compute_funnel_counts(records, window)` pure function.
- [ ] Add dashboard views: conversion table, per-gate volume + sample,
      per-strategy heatmap, drill-through panel, and command-center
      single-line summary.
- [ ] Add fixtures/tests per spec §5: gate transition tests,
      `ProposalRecord` schema round-trip, cap-diagnostic payload, record_id
      join, funnel aggregator, dashboard rendering.

## Verification

- [ ] `uv run pytest tests/test_runtime_engine.py tests/test_proposal_interaction.py -q`
- [ ] Targeted dashboard tests for the funnel views.
- [ ] Targeted aggregator tests for `compute_funnel_counts`.
- [ ] `ruff check src tests` clean and `mypy` clean on changed files.

## Completion Checklist

- [ ] Code implemented.
- [ ] Tests pass.
- [ ] Session log and cross-check added.
- [ ] `aidlc-docs/aidlc-state.md` updated.

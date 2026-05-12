# Code Generation Plan: runtime-reconciliation

## Task

Implement the existing `runtime-reconciliation` functional design: open-trade
state taxonomy, startup health check + `RECONCILIATION_HEALTH_REPORT` event,
backfill-tool activity event, new close-unrecoverable tool, and dashboard
status banner / drill-through / cash-only suppression rule.

## Related Context

- Unit: `runtime-reconciliation`
- Stage: Code Generation
- Requirements: FR-010, FR-014, FR-029, FR-036, NFR-007, NFR-008, NFR-012
- Functional design:
  `aidlc-docs/construction/runtime-reconciliation/functional-design/spec.md`
- Source evidence: 2026-05-13 Fly snapshot — 49 open paper trades, 44 missing
  SL/TP, 6,148 monitor errors, Trading dashboard reporting zero positions
  while ledger held 49 open rows.
- Related units: `trading-core`, `persistence-data-integrity`,
  `proposal-runtime`, `dashboard-operator-command-center`, `notifications-ops`

## Steps

- [x] Add `src/runtime/reconciliation.py` with `OpenTradeState`,
      `classify_open_trade`, and `compute_health_report`.
- [x] Wire `TradingEngine._run_reconciliation_health_check` into
      `run_forever` before the cycle loop; emit
      `RECONCILIATION_HEALTH_REPORT` and (conditionally)
      `RECONCILIATION_LOCKED_INCONSISTENT`.
- [x] Add new `ActivityEventType` members:
      `RECONCILIATION_HEALTH_REPORT`,
      `RECONCILIATION_LOCKED_INCONSISTENT`,
      `BACKFILL_PAPER_SL_TP_RAN`,
      `RECONCILIATION_CLOSED_UNRECOVERABLE`.
- [x] Update `src/tools/backfill_paper_sl_tp.py` to emit
      `BACKFILL_PAPER_SL_TP_RAN` on live runs only.
- [x] Add `src/tools/close_unrecoverable_paper_trades.py` with
      `--dry-run` / `--sub-account` matching the existing backfill CLI shape;
      emit one `RECONCILIATION_CLOSED_UNRECOVERABLE` per closed row.
- [x] Add `build_reconciliation_status_banner` and
      `build_reconciliation_drilldown_dataframe` on the Engine page; render
      banner on Engine + Trading pages.
- [x] Add cash-only suppression rule on the Trading page when
      `totals.open_trade_count > 0`.
- [x] Add fixtures/tests across runtime, tools, and dashboard.

## Verification

- [x] `uv run pytest tests/test_runtime_reconciliation.py tests/test_runtime_engine.py -q`
- [x] `uv run pytest tests/test_tools_backfill_paper_sl_tp.py tests/test_tools_close_unrecoverable_paper_trades.py -q`
- [x] `uv run pytest tests/test_dashboard_engine.py tests/test_dashboard_trading.py -q`

## Completion Checklist

- [x] Code implemented.
- [x] Tests pass.
- [x] Session log and cross-check added.
- [x] `aidlc-docs/aidlc-state.md` updated.

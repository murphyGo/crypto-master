# Cross-Check: runtime-reconciliation DEBT-078

## Scope

Verify that DEBT-078 is resolved without changing unrelated monitor behavior.

## Requirements

- FR-010: Paper trading remains safe and locally persistent.
- FR-014: Proposal/trade outcomes remain durable and auditable.
- FR-029: Runtime position status remains visible.
- FR-036: Sub-account trade state remains isolated.
- NFR-007 / NFR-008: Trade history and PnL history keep reliable labels.
- NFR-012: Live trading controls remain conservative.

## Evidence

- Stale weak-provenance bound hits are relabeled to `orphan_force_close`.
- Healthy old rows with persisted SL/TP and a performance link keep `stop_loss`
  / `take_profit`.
- Performance-record bounds lookup is shared by runtime resolver and
  `backfill_paper_sl_tp`.
- Proposal-history bounds lookup is shared by
  `repair_paper_trade_bounds_from_proposals`.

## Verification Commands

- `uv run pytest tests/test_runtime_engine.py::test_monitor_pass_closes_position_on_sl_hit tests/test_runtime_engine.py::test_monitor_pass_uses_sub_account_trader_for_exit_check tests/test_runtime_engine.py::test_monitor_pass_relabels_stale_weak_provenance_sl_hit tests/test_runtime_engine.py::test_monitor_pass_keeps_fresh_sl_label_for_healthy_old_trade tests/test_strategy_performance.py::TestResolveBoundsFromPerformanceRecord tests/test_tools_backfill_paper_sl_tp.py tests/test_tools_repair_paper_trade_bounds_from_proposals.py -q`
- `uv run ruff check src/runtime/position_monitor.py src/strategy/performance.py src/proposal/bounds.py src/tools/backfill_paper_sl_tp.py src/tools/repair_paper_trade_bounds_from_proposals.py tests/test_runtime_engine.py tests/test_strategy_performance.py tests/test_tools_repair_paper_trade_bounds_from_proposals.py`

## Result

Pass. DEBT-078 is resolved. Residual limitation is explicit: without a
`last_seen_at`/monitor freshness field, classification remains conservative and
uses provenance plus age instead of exact monitor gap duration.

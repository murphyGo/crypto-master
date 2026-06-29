# Session: runtime-reconciliation DEBT-078 stale bound labeling

## Unit

- Primary: `runtime-reconciliation`
- Secondary: `strategy-framework`, `proposal-funnel-audit`
- Debt: DEBT-078
- Requirements: FR-010, FR-014, FR-029, FR-036, NFR-007, NFR-008, NFR-012

## Summary

Resolved the residual backfilled-then-stale SL/TP mislabel edge. A monitorable
trade that is older than the always-on reconciliation age wall and has weak
reconciliation provenance now closes with `orphan_force_close` instead of a
fresh-looking `stop_loss` / `take_profit` label. Healthy old rows with both
persisted bounds and a performance link keep normal SL/TP analytics labels.

Also consolidated the duplicate raw bounds lookup implementations:

- `src.strategy.performance.load_performance_record_bounds_index` is now the
  shared raw JSON index for runtime rehydration and `backfill_paper_sl_tp`.
- `src.proposal.bounds.load_proposal_trade_bounds_index` is now the shared
  proposal-history index for `repair_paper_trade_bounds_from_proposals`.

## Files Changed

- `src/runtime/position_monitor.py`
- `src/strategy/performance.py`
- `src/proposal/bounds.py`
- `src/tools/backfill_paper_sl_tp.py`
- `src/tools/repair_paper_trade_bounds_from_proposals.py`
- `tests/test_runtime_engine.py`
- `tests/test_strategy_performance.py`
- `tests/test_tools_repair_paper_trade_bounds_from_proposals.py`
- `docs/TECH-DEBT.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/inception/units/debt-unit-map.md`
- `aidlc-docs/construction/plans/runtime-reconciliation-code-generation-debt-078-stale-bound-label-plan.md`

## Verification

- `uv run pytest tests/test_runtime_engine.py::test_monitor_pass_closes_position_on_sl_hit tests/test_runtime_engine.py::test_monitor_pass_uses_sub_account_trader_for_exit_check tests/test_runtime_engine.py::test_monitor_pass_relabels_stale_weak_provenance_sl_hit tests/test_runtime_engine.py::test_monitor_pass_keeps_fresh_sl_label_for_healthy_old_trade tests/test_strategy_performance.py::TestResolveBoundsFromPerformanceRecord tests/test_tools_backfill_paper_sl_tp.py tests/test_tools_repair_paper_trade_bounds_from_proposals.py -q`
- `uv run ruff check src/runtime/position_monitor.py src/strategy/performance.py src/proposal/bounds.py src/tools/backfill_paper_sl_tp.py src/tools/repair_paper_trade_bounds_from_proposals.py tests/test_runtime_engine.py tests/test_strategy_performance.py tests/test_tools_repair_paper_trade_bounds_from_proposals.py`

## Decisions

- The relabeling predicate is intentionally narrow: age beyond
  `ORPHAN_MAX_AGE` plus weak provenance (`stop_loss` missing, `take_profit`
  missing, or no `performance_record_id`). This avoids relabeling a healthy,
  continuously monitored old position that still has full persisted provenance.
- The close path still uses the normal trader close method for monitorable
  positions. Only the close reason changes, so live monitorable positions still
  go through the live close implementation rather than the persistence-only
  orphan hook.

## Risks

- `TradeHistory` still has no `last_seen_at`, so the runtime cannot perfectly
  distinguish a continuously monitored old position from a newly repaired old
  one. The weak-provenance predicate keeps the blast radius bounded until a
  future schema adds an explicit monitor freshness timestamp.

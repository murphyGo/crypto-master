# Session: runtime-reconciliation unit shipped

## Unit

- `runtime-reconciliation` (primary)
- Secondary units: `proposal-runtime`, `dashboard-operator-ui`, `ai-feedback-loop`

## Related Requirements

- FR-010
- FR-014
- FR-029
- FR-036
- NFR-007
- NFR-008
- NFR-012

## Scope

Shipped the `runtime-reconciliation` unit end-to-end: open-trade state taxonomy, async startup health check wired into `run_forever`, persistent dashboard banner (green/yellow/red) with drill-through table and cash-only suppression rule, `close_unrecoverable_paper_trades` CLI emitting synthetic `PerformanceRecord` rows with `synthetic`/`reconciliation_close` markers, hybrid locked-consistency tolerance, and `RECONCILIATION_HEALTH_CHECK_FAILED` meta-event closing the silent-disable visibility loop. Combined deliverable across R1 (initial) and R2 (post-quant-review fixes for Q2 🔴 + Q3 🟡 + Q4 🔴).

## Changes

- `src/runtime/reconciliation.py` (NEW) — `OpenTradeState` enum (`monitorable`/`degraded`/`unrecoverable`/`legacy_no_perf_link`); `OpenTradeClassification` Pydantic model; `classify_open_trade()` + `compute_health_report()` pure-functional classifier surface.
- `src/tools/close_unrecoverable_paper_trades.py` (NEW) — CLI with `--dry-run` / `--sub-account` mirroring the `backfill_paper_sl_tp` shape; writes synthetic `PerformanceRecord` with `synthetic=True` / `reconciliation_close=True`; emits one `RECONCILIATION_CLOSED_UNRECOVERABLE` per closed row.
- `src/runtime/engine.py` — `_run_reconciliation_health_check` invoked from `run_forever` after STARTUP and before the cycle loop; async log-and-continue per resolution; R2 `except` branch now emits `RECONCILIATION_HEALTH_CHECK_FAILED` (Q4 fix) so silent-disable on the meta-path is operator-visible.
- `src/runtime/activity_log.py` — 5 new event types: `RECONCILIATION_HEALTH_REPORT`, `RECONCILIATION_LOCKED_INCONSISTENT`, `BACKFILL_PAPER_SL_TP_RAN`, `RECONCILIATION_CLOSED_UNRECOVERABLE`, and the R2-added `RECONCILIATION_HEALTH_CHECK_FAILED`.
- `src/tools/backfill_paper_sl_tp.py` — gained `activity_log` kwarg; emits `BACKFILL_PAPER_SL_TP_RAN` on live runs only.
- `src/dashboard/pages/engine.py` + `src/dashboard/pages/trading.py` — persistent banner (green/yellow/red), drill-through table, and cash-only suppression rule at `trading.py:589-598` (gates on `banner.open_trade_count > 0 AND open_df.empty`); R2 banner additionally renders yellow with an "investigate logs" CTA when `RECONCILIATION_HEALTH_CHECK_FAILED` fires.
- `src/models.py` — `PerformanceRecord` gains `synthetic: bool = False` + `reconciliation_close: bool = False` fields (Q2 🔴 fix) so the flags survive the round-trip.
- `src/strategy/performance.py` — `TechniquePerformance.from_records` filters synthetic rows out of win-rate / breakeven / avg-pnl / total-pnl / best-pnl / worst-pnl aggregates; new `synthetic_count` aggregate exposed separately (Q2 fix). `LOCKED_CONSISTENCY_EPSILON` raised to 0.01 floor; new `_locked_consistency_tolerance(locked_sum) = max(0.01, locked_sum × 0.001)` hybrid (Q3 🟡 fix).
- `src/dashboard/pages/strategies.py::build_trend_dataframe` and `src/ai/improver.py::_format_records` — both filter synthetic rows (Q2 fix; improver-prompt scope means synthetic-close noise no longer feeds the Claude feedback loop).
- Tests — `+46` in R1 (1882 → 1928) across `tests/test_runtime_reconciliation.py`, `tests/test_runtime_engine.py`, `tests/test_tools_backfill_paper_sl_tp.py`, `tests/test_tools_close_unrecoverable_paper_trades.py`, `tests/test_dashboard_engine.py`, `tests/test_dashboard_trading.py`. R2 added `+14` more (1928 → 1942) covering `PerformanceRecord` round-trip, aggregation filtering, the hybrid tolerance, and the `RECONCILIATION_HEALTH_CHECK_FAILED` payload.

## Quant adjudications (Q1-Q5)

- **Q1** (taxonomy completeness): 🟡 — `monitorable`/`degraded`/`unrecoverable`/`legacy_no_perf_link` covers ledger-shape but misses (a) stale-but-valid rows (monitor loop hasn't ticked in >N days, currently flagged `monitorable`) and (b) half-closed rows (`status="closed"` with no `exit_price`/`exit_time`). Deferred to **DEBT-064**.
- **Q2** (synthetic-record marker): 🔴 — flags lost on `PerformanceRecord` round-trip. Fixed in Round 2 by adding `synthetic` + `reconciliation_close` fields to the model and filtering aggregation sites in `TechniquePerformance.from_records`, `dashboard.pages.strategies.build_trend_dataframe`, and `ai.improver._format_records`. New `synthetic_count` aggregate kept separate so operator counting still works.
- **Q3** (locked-consistency tolerance): 🟡 — absolute $0.0001 too tight for $49k accounts. Fixed in Round 2 with hybrid `max(0.01, locked_sum × 0.001)`.
- **Q4** (health-check error visibility): 🔴 — silent swallow on the `_run_reconciliation_health_check` `except` branch was the DEBT-061 anti-pattern recurring on a meta-path. Fixed in Round 2 with `RECONCILIATION_HEALTH_CHECK_FAILED` event + yellow banner with "investigate logs" CTA; log-and-continue semantics preserved.
- **Q5** (cash-only suppression rule): 🟢 ratified-as-shipped. `trading.py:589-598` correctly gates on `banner.open_trade_count > 0 AND open_df.empty`.

## 🔴-and-fix

Two 🔴 verdicts in the quant review, both caught before ship and both fixed in R2:

R1 added `synthetic=True` / `reconciliation_close=True` markers when writing the synthetic `PerformanceRecord` rows from `close_unrecoverable_paper_trades`, but `PerformanceRecord` itself didn't carry the fields — they were lost on Pydantic round-trip, so every aggregation site (win-rate, total PnL, improver-prompt history) treated synthetic operator-reconciliation closes as real trade outcomes. R2 added both fields to the model with `default=False` and updated `TechniquePerformance.from_records` to exclude synthetic rows from every aggregation while exposing a new `synthetic_count` for operator-facing counting. Dashboard trend-DF and improver-prompt formatter also filter.

R1 left the `_run_reconciliation_health_check`'s `except` branch swallowing exceptions with only a debug log — silent-disable on a money-handling visibility surface, the exact DEBT-061 anti-pattern that DEBT-061 (per-strategy fail-closed counters) and the `market-regime` Q3 fix established as a project-wide ban. R2 added `RECONCILIATION_HEALTH_CHECK_FAILED` activity event emission in the `except` block (log-and-continue preserved — the failure is reported, not raised), and the dashboard banner renders yellow with an "investigate logs" CTA when the event fires within the last cycle window.

## QA follow-up gap

QA flagged a third gap separate from the Q1-Q5 thread: `TechniquePerformance.total_trades = len(records)` (`src/strategy/performance.py:244`) includes synthetic rows even after the R2 filters, and `ProposalEngine._cold_start_blocks_live` (`src/proposal/engine.py:1061-1064`) and `_score`'s `sample_size` (`src/proposal/engine.py:1200`) consume `total_trades` directly. So a strategy with 9 real + 2 synthetic closes could pass `threshold=10` live promotion — even though `src/strategy/performance.py:214`'s comment explicitly says synthetic rows "must not feed CON-003 promotion gating." Different defect from Q1 taxonomy gaps and not in scope for this cycle; filed as **DEBT-065** (Medium) for follow-up.

## Verification

- `pytest -q` — **1942 passed** (was 1882; net +60 across R1+R2, zero regressions).
- `ruff check src tests` — fully clean.
- `mypy` on 10 changed modules — clean; 3 pre-existing `src/dashboard/app.py` errors remain (out of scope).

## Risks

- Cash-only suppression rule has a possible false-positive edge case: if disk error makes `_load_open_trade_rows` raise mid-cycle and the banner has not yet been refreshed, the Trading page could suppress the open-positions table while the ledger still holds rows. Quant ratified the green-path rule as-shipped; the disk-error edge case is deferred — the `RECONCILIATION_HEALTH_CHECK_FAILED` event (R2 fix) means operators have a visible signal that the banner data is suspect.
- Taxonomy gaps (DEBT-064): stale-but-valid rows (>N day monitor-loop silence) and half-closed rows (`status="closed"` with `exit_price IS NULL`) are not currently surfaced through the health-check warning path. Operators relying on the banner as the single source of truth will miss those shapes until the auxiliary signals land.
- Synthetic-row leak into live-promotion gating (DEBT-065): narrow blast radius (operator-driven path, conservative threshold) but the contract gap is real and grows with each operator reconciliation event.

## Reviewer notes

- quant-trader-expert: 🟢 on R2 final diff after Q2 + Q3 + Q4 fixes; Q1 deferred to DEBT-064; Q5 ratified-as-shipped.
- qa-reviewer: 🟡 — approved-with-follow-up. Q1-Q5 fixes accepted; flagged the `total_trades` synthetic-inclusion gap separately, filed as DEBT-065.

## Future work

- **DEBT-064** (taxonomy gaps): per-row warning counter for stale-but-valid rows (computed from `last_seen_at` vs `now`); separate sweep pass for half-closed rows iterating `status="closed"` with `exit_price IS NULL`. Auxiliary signals on the existing classifier output rather than new enum states.
- **DEBT-065** (synthetic-row leak into live-promotion gating): smaller-diff resolution is option (b) — switch `_cold_start_blocks_live` and `_score.sample_size` to read `perf.total_trades - perf.synthetic_count` (or a new `real_trade_count` property); update `tests/test_strategy_performance.py:2066` to match.

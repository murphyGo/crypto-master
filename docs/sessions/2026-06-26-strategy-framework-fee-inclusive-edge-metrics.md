# Session: DEBT-073 fee-inclusive edge metrics

- **Date**: 2026-06-26
- **Unit**: `strategy-framework` (secondary: `strategy-tuning`)
- **Stage**: Code Generation
- **Workflow**: `/dev-crypto` (single-agent)
- **Construction plan**: `aidlc-docs/construction/plans/strategy-framework-code-generation-fee-inclusive-edge-metrics-plan.md`

## Related requirements / debt

- NFR-008 (fee-accurate P&L tracking)
- DEBT-073 (resolved here); relates to DEBT-024 / Phase 20.1-20.2 (intentional
  gross price-move convention — preserved) and DEBT-069(g) (threshold
  calibration — net shift noted there)

## Problem

`PerformanceRecord.pnl_percent` is, by design (DEBT-024), a leverage-neutral
*price-move* percent — **gross of fees**. `TechniquePerformance.from_records`
aggregated it into `gross_win_pct`/`gross_loss_pct` (→ profit factor) and
`total_pnl_percent` (→ closed-PnL), and `evidence_from_performance` fed those to
the tuning recommender. So the **edge** metrics that drive
keep/retune/scout recommendations omitted realized fee drag (~0.07 pct-pts per
trade, one-directional; 2 of 148 closed records flip win/loss sign once netted).
On ~breakeven strategies a systematic fee omission can tip a marginal call.

## Change

Fee-netting is derived at the aggregation layer from data already on
`PerformanceRecord` (`pnl_percent`, `fees`, `entry_price`, `quantity`) — no
change to trade/record persistence or to the gross convention.

- `src/strategy/performance.py`:
  - `_net_pnl_pct_for_record(record)` — `net = pnl_percent - fees/notional*100`,
    `notional = entry_price * quantity`; falls back to gross when `quantity` is
    missing or `notional <= 0` (backtest rows often lack quantity), and when
    `fees == 0`. Round-trip fees are already on the record.
  - `TechniquePerformance` gains `net_total_pnl_percent`, `net_avg_pnl_percent`,
    `net_win_pct`, `net_loss_pct` (default `0.0`).
  - `from_records` computes the four net aggregates over the same non-synthetic
    `closed_real_records` filter as gross. Winners/losers split on the **net**
    value, so a gross winner that turns net-negative after fees lands in
    `net_loss_pct`.
- `src/strategy/tuning_recommender.py`: `evidence_from_performance` now computes
  `profit_factor = net_win_pct / net_loss_pct` and
  `closed_pnl_pct = net_total_pnl_percent`. `win_rate` is fee-independent
  (outcome classified by close-reason, not magnitude) — not reclassified.
- `src/strategy/trade_history.py`: `calculate_pnl` docstring formula corrected
  (said `pnl /`, code uses `gross_pnl`); now states the gross-of-fees intent
  and points at the DEBT-073 net derivation.

## Files changed

- `src/strategy/performance.py`
- `src/strategy/tuning_recommender.py`
- `src/strategy/trade_history.py` (docstring only)
- `tests/test_strategy_performance.py` (+`TestNetFeeInclusiveMetrics`, 6 tests)
- `tests/test_strategy_tuning_recommender.py` (+1 net-vs-gross test; 2 existing
  `evidence_from_performance` tests updated to the net semantics)
- `tests/test_dashboard_strategies.py` (`_keep_band_perf` / `_pause_band_perf`
  now set `net_*` mirroring gross — zero-fee scenarios)
- `aidlc-docs/construction/plans/strategy-framework-code-generation-fee-inclusive-edge-metrics-plan.md` (new)
- `docs/TECH-DEBT.md` (DEBT-073 → ✅, Statistics, Change History)
- `aidlc-docs/inception/units/debt-unit-map.md`

## Tests / checks

- `uv run pytest tests/test_strategy_performance.py tests/test_strategy_tuning_recommender.py tests/test_dashboard_strategies.py -q` → 176 passed
- `uv run pytest` → **2376 passed**
- `uv run ruff check` (touched files) → clean
- `uv run mypy src` → clean (105 files)
- `uv run black --check` (touched files) → clean

## Decisions

- **Derive at aggregation, not persistence.** Keeps the DEBT-024 gross
  price-move convention and the on-disk schema intact; net is recomputed live by
  `from_records` (the gating path), so new fields never need a backfill.
- **Net default `0.0` is safe.** `get_performance` always recomputes via
  `from_records`, so the recommender never reads a stale summary's zero net
  fields. A deserialized old summary would read net=0, but nothing gates on a
  deserialized summary.
- **Scope: edge only.** Display/chart fields stay gross. Only the dashboard
  Recommended column consumes the change; the live `_strategy_action_gate` reads
  applied YAML actions (DEBT-069(f)), so live trade gating is unchanged.
- **Did NOT reclassify outcomes.** Flipping a gross-winner-net-loser's
  `outcome`/`win_rate` would touch `snapshot_recorder` and the win-rate
  contract — out of scope. Net PF already routes such a trade to the loss
  bucket.

## Risks

- Switching `closed_pnl_pct`/`profit_factor` to net shifts recommendations
  slightly more conservative. Magnitude is small (fee drag ~0.07 pct-pts/trade)
  and in the correct direction (fees are real costs), but it interacts with the
  still-open **DEBT-069(g)** threshold calibration — flagged there.

## Debt

- Resolved: DEBT-073.
- No new debt.

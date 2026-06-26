# Code Generation Plan: strategy-framework - DEBT-073 fee-inclusive edge metrics

## Task

Make strategy **edge** metrics fee-inclusive without disturbing the gross
price-move display. `PerformanceRecord.pnl_percent` is intentionally a
leverage-neutral *price-move* percent (gross of fees, per DEBT-024 /
Phase 20.1-20.2). `TechniquePerformance.from_records` aggregates it into
`gross_win_pct`/`gross_loss_pct` → `profit_factor` and `total_pnl_percent` →
`closed_pnl_pct`, which `evidence_from_performance` feeds to the tuning
recommender. Net result: profit factor, expectancy, and closed-PnL used for
`keep`/`retune`/`scout` recommendations omit realized fee drag (~0.07 pct-pts
per trade, one-directional; can tip a marginal call on ~breakeven strategies).

## Unit / Stage / Slice

- Unit: `strategy-framework`
- Stage: Code Generation
- Slice ID: DEBT-073 fee-inclusive edge metrics
- Secondary unit: `strategy-tuning` (recommender evidence)

## Related Requirements / Debt

- NFR-008 fee-accurate P&L tracking
- DEBT-073 (this); relates to DEBT-024 (intentional gross price-move
  convention — preserved) and DEBT-069(g) (threshold calibration — net shift is
  small and conservative; flagged there)

## Design Decisions

- Net is derived at the **aggregation** layer from data already on
  `PerformanceRecord` (`pnl_percent`, `fees`, `entry_price`, `quantity`); no
  change to trade/record persistence or to the gross `pnl_percent` convention.
- Per closed real record: `net_pct = pnl_percent - fee_pct`,
  `fee_pct = float(fees) / notional * 100`, `notional = entry_price * quantity`.
  When `quantity` is absent or `notional <= 0`, fall back to `net_pct = gross`
  (cannot net without a notional — backtest rows often lack quantity).
- `fees` on a closed record is the round-trip total (entry+exit), so the full
  drag is netted once.
- New `TechniquePerformance` fields default to `0.0` → old on-disk summaries
  load unchanged; the gating path always recomputes via `from_records`
  (`get_performance`), so net fields are always populated when the recommender
  reads them (no stale-summary mis-gate).
- **Edge** consumers switch to net: `profit_factor = net_win_pct/net_loss_pct`,
  `closed_pnl_pct = net_total_pnl_percent`. **Display** keeps gross
  (`gross_win_pct`/`gross_loss_pct`/`total_pnl_percent` untouched).
- `win_rate` is fee-independent (outcome is classified by close-reason, not
  magnitude) — NOT reclassified here. Reclassifying gross-winner-turned-net-
  loser *outcomes* is out of scope (bigger change; would touch
  snapshot_recorder). The net PF already routes such a trade to the loss bucket
  because PF is computed on net values.

## Steps

- [x] Add a module-level `_net_pnl_pct_for_record(record) -> float | None`
      helper in `src/strategy/performance.py`.
- [x] Add `net_total_pnl_percent`, `net_avg_pnl_percent`, `net_win_pct`,
      `net_loss_pct` (default `0.0`) to `TechniquePerformance` + docstrings.
- [x] Compute the four net aggregates in `from_records` over the same
      `closed_real_records` filter as gross.
- [x] `evidence_from_performance` (`src/strategy/tuning_recommender.py`):
      profit_factor from `net_win_pct`/`net_loss_pct`; `closed_pnl_pct` from
      `net_total_pnl_percent`.
- [x] Fix the `calculate_pnl` docstring formula at
      `src/strategy/trade_history.py:126-129` (said `pnl /` but uses
      `gross_pnl`; now clarifies it is the gross price-move).
- [x] Tests: net aggregation (fee-only flat-price trade → negative net pct),
      gross-winner-turned-net-loser flips PF bucket, gross fields unchanged,
      `evidence_from_performance` consumes net, missing-quantity falls back to
      gross. Updated 2 recommender tests + 2 dashboard band-perf helpers
      (gross-only fixtures now set net mirroring gross for their zero-fee
      scenarios).

## Verification

- [x] `uv run pytest tests/test_strategy_performance.py
      tests/test_strategy_tuning_recommender.py tests/test_dashboard_strategies.py -q`
      → 176 passed
- [x] `uv run pytest` → 2376 passed
- [x] `uv run ruff check ...` → clean
- [x] `uv run mypy src` → clean (105 files)
- [x] `uv run black --check` on touched files → clean

## Completion Checklist

- [x] Code shipped under `src/`.
- [ ] `aidlc-docs/aidlc-state.md` touched if stage state changes. (n/a — no
      stage boundary; unit stays CONSTRUCTION - Brownfield Ready)
- [x] `docs/TECH-DEBT.md` DEBT-073 → resolved; `debt-unit-map.md` refreshed.
- [x] Session log under `docs/sessions/`.

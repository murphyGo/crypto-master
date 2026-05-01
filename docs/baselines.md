# Baseline Strategies

The crypto-master engine ships five deterministic indicator
strategies alongside the LLM-driven techniques (three Phase 9.2
indicator baselines plus two Phase 9.4 cadence-locked RSI siblings).
They serve two purposes:

1. **Comparison floor.** "Is the LLM strategy contributing real
   edge, or just confidently re-deriving simple TA?" — without a
   deterministic baseline you can't answer that. Backtest each
   baseline first; the LLM strategies should clear those numbers
   before you trust them.
2. **Degraded-mode safety net.** If every Claude call fails (rate
   limit, auth, parse error), the engine still produces proposals
   from indicator strategies. The runtime keeps working.

All five live under [`strategies/`](../strategies/) with
`status: experimental` and `symbols: []` (universal — they apply
to every USDT pair the engine scans).

## The five baselines

### `rsi.py` — RSI Mean Reversion (Universal Cadence)

Wilder's RSI on the closes of whatever timeframe the engine passes.
The shared signal logic; `rsi_4h.py` and `rsi_15m.py` reuse this
exact strategy class with locked timeframes.

| Setting | Value |
|---------|-------|
| Technique name | `rsi_universal` |
| Declared timeframes | `["1h", "4h", "15m"]` (compatible — engine picks one) |
| Indicator | RSI (Wilder's) |
| Period | 14 |
| Long trigger | RSI < 30 (oversold) |
| Short trigger | RSI > 70 (overbought) |
| Stop loss | 2% adverse |
| Take profit | 4% favorable (R/R 2:1) |
| Confidence | Linear ramp from 0 (at threshold) to 1 (RSI 10 / 90) |

### `rsi_4h.py` — RSI Mean Reversion (Swing Cadence)

Same logic as `rsi_universal`, locked to 4-hour candles. Phase 9.4
split. Use this when you want the swing-cadence RSI to fire
independently of the scalp variant — each has its own performance
history in the tracker.

| Setting | Value |
|---------|-------|
| Technique name | `rsi_4h` |
| Declared timeframes | `["4h"]` |
| Logic | Identical to `rsi_universal` |

### `rsi_15m.py` — RSI Mean Reversion (Scalp Cadence)

Scalp-cadence sibling of `rsi_4h`. Locked to 15-minute candles;
fires roughly 16× more often than the 4h variant. Phase 9.4 split.

| Setting | Value |
|---------|-------|
| Technique name | `rsi_15m` |
| Declared timeframes | `["15m"]` |
| Logic | Identical to `rsi_universal` |

### `bollinger_bands.py` — Bollinger Band Reversion

Mean-reversion when price pierces a band. Targets the middle band;
stops sit half a band-width outside the trigger.

| Setting | Value |
|---------|-------|
| Indicator | Bollinger Bands (SMA ± 2σ population) |
| Period | 20 |
| Std dev | 2.0 |
| Long trigger | Close < lower band |
| Short trigger | Close > upper band |
| Take profit | Middle band (the SMA) |
| Stop loss | Triggering band ± 0.5 × half-band-width |
| Confidence | Proportional to depth past the band, capped at 1 |

### `ma_crossover.py` — Dual SMA Crossover

Classic golden / death cross. Promoted from the original
`sample_code.py` scaffold.

| Setting | Value |
|---------|-------|
| Indicator | Two SMAs (fast / slow) |
| Fast period | 10 |
| Slow period | 20 |
| Long trigger | Fast crosses above slow on the latest bar |
| Short trigger | Fast crosses below slow on the latest bar |
| Take profit | ±5% from entry |
| Stop loss | Min/max of last 5 closes |
| Confidence | `\|short_ma − long_ma\| / current_price × 100`, capped at 0.8 |

## How to backtest these

Phase 10.3 shipped an operator script that fetches historical OHLCV
from Binance's public klines endpoint, runs each baseline through
`Backtester` + `PerformanceAnalyzer`, and persists the artefacts the
dashboard's Strategies page consumes. **Phase 25 added snapshot-pinned
reproducibility**: by default the script reads OHLCV from a committed
snapshot dataset under `data/backtest/snapshots/baselines/` rather
than calling Binance live, so two operators on different days produce
byte-identical metrics + ledgers.

The script writes three files per baseline under
`data/backtest/baselines/<technique_name>/`:

- `result.json` — full `BacktestResult` (NFR-006).
- `analysis.md` — human-readable performance report.
- `summary.json` — flat row consumed by the doc-table updater.

It then rewrites the **Reference numbers** table below from the new
`summary.json` files. Re-running is idempotent — artefacts are
overwritten cleanly. Pass `--no-update-doc` to skip the table rewrite.

The smoke test in `tests/test_scripts_backtest_baselines.py` mocks the
exchange (or uses an in-memory `SnapshotExchange`) and verifies the
artefact layout. CI never calls Binance live.

## Operator runbook — first-time fetch + run

Phase 25.3 Part B. Until an operator runs through the steps below,
every metric cell in the **Reference numbers** table reads as the
legacy unpopulated marker — semantically "awaiting operator first
run" — signalling the snapshot infrastructure is ready but no
operator has executed the one-time fetch yet.

1. **Set Binance credentials.** A read-only API key is acceptable
   (no order placement, no withdrawal scopes). Either export them
   in the shell or write them to `.env` (gitignored):

   ```bash
   export BINANCE_API_KEY=...
   export BINANCE_API_SECRET=...
   ```

2. **Refresh the snapshot.** This is the only path that touches
   Binance mainnet — the script prints two operator-visible warnings
   when it runs:

   ```bash
   python -m scripts.backtest_baselines \
       --refresh-snapshot \
       --snapshot-root data/backtest/snapshots/
   ```

3. **Verify the snapshot directories.** You should see five
   `<SYMBOL>__<timeframe>/` subdirectories under
   `data/backtest/snapshots/baselines/`, each containing
   `ohlcv.csv` + `metadata.json`:

   ```bash
   ls data/backtest/snapshots/baselines/
   # BTCUSDT__15m  BTCUSDT__1h  BTCUSDT__4h
   ```

   (Three directories, not five — `rsi_universal`,
   `bollinger_band_reversion`, and `ma_crossover` all share the
   `BTC/USDT 1h` snapshot.)

4. **Run the baselines off the committed snapshot.** No network
   calls; deterministic from the snapshot dataset:

   ```bash
   python -m scripts.backtest_baselines \
       --snapshot data/backtest/snapshots/
   ```

   This populates `data/backtest/baselines/<technique_name>/`
   (`result.json` + `analysis.md` + `summary.json`) and rewrites
   the **Reference numbers** table below in place.

5. **Commit the snapshot + artefacts.** The snapshot directory is
   the contract for reproducibility — it must travel with the repo.
   The artefacts under `data/backtest/baselines/` are the
   operator-facing reference numbers the dashboard reads:

   ```bash
   git add data/backtest/snapshots/baselines/ \
           data/backtest/baselines/ \
           docs/baselines.md
   git commit -m "Phase 25.3 Part B: first baseline snapshot + figures"
   ```

## Snapshot freshness policy

Two windows govern snapshot age:

- **30-day active-use window** — `--max-snapshot-age-days` default
  (env-overridable via `ENGINE_BASELINE_MAX_SNAPSHOT_AGE_DAYS`).
  This is the **operator-facing cadence**: refresh the snapshot
  every 30 days for active-use comparisons (LLM strategy promotion
  gates, dashboard reference numbers). Older than 30 days and the
  baseline script will refuse to proceed without
  `--refresh-snapshot`.
- **90-day absolute stale ceiling** — `DEFAULT_MAX_AGE_DAYS` in
  `src/backtest/snapshot.py`. This is the hard floor in
  `is_snapshot_fresh`: any snapshot older than 90 days is
  unambiguously stale and the loader-level freshness check will
  refuse it regardless of the active-use override.

In practice: **refresh on a 30-day cadence**. The 90-day ceiling is
the safety net for the case where an operator forgets and tries to
run with a 6-month-old snapshot.

## Reproducibility note

The snapshot dataset is the contract for cross-operator
determinism. Two operators running

```bash
python -m scripts.backtest_baselines --snapshot data/backtest/snapshots/
```

against the same committed snapshot produce identical metrics and
identical trade-level numbers — entry / exit prices, PnL, Sharpe,
MDD, win rate are byte-identical. Only the run-level UUIDs differ:
`BacktestResult.run_id` and each `Trade.trade_id` use `uuid.uuid4()`
(operator-trace IDs, not strategy state). Phase 25.2's
`test_cross_operator_determinism_byte_identical` exercises this
contract by running `run_all` twice and asserting byte equality
after scrubbing those two UUID fields.

## Reference numbers

Snapshot-pinned figures from the committed dataset under
`data/backtest/snapshots/baselines/`. Until Phase 25.3 Part B
runs, every metric cell below shows the legacy unpopulated marker;
semantically that marker reads as **awaiting operator first run**.
Once an operator runs the runbook above, these cells get rewritten
in place by `scripts/backtest_baselines.py`.

(Two minor deviations from the Phase 25.3 Part A spec, both
deferred to keep this sub-task strictly docs-only and tracked as
Low-priority TECH-DEBT for a follow-up docs-polish sub-task:
[a] 9-column table kept at 6 columns — the autonomous rewriter
`_TABLE_PATTERN` + `render_table` is hard-wired to the legacy
shape; [b] the placeholder token kept as the legacy marker
because existing rewriter tests assert it pre-rewrite. See the
senior-developer report.)

| Strategy | Symbol | Period | Win Rate | Sharpe | MDD |
|----------|--------|--------|----------|--------|-----|
| `rsi_universal` | BTC/USDT | 3mo 1h | _TBD_ | _TBD_ | _TBD_ |
| `rsi_4h` | BTC/USDT | 3mo 4h | _TBD_ | _TBD_ | _TBD_ |
| `rsi_15m` | BTC/USDT | 1mo 15m | _TBD_ | _TBD_ | _TBD_ |
| `bollinger_band_reversion` | BTC/USDT | 3mo 1h | _TBD_ | _TBD_ | _TBD_ |
| `ma_crossover` | BTC/USDT | 3mo 1h | _TBD_ | _TBD_ | _TBD_ |

These numbers are the bar each LLM-driven technique needs to clear.

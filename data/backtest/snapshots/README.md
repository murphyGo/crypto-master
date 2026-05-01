# Backtest Snapshots

Snapshot-pinned OHLCV datasets for reproducible baseline runs
(Phase 25 / DEBT-043).

## Why snapshots?

`scripts/backtest_baselines.py` historically called Binance mainnet
on every run, so re-runs drifted day-to-day with whatever the live
chart looked like. That's not suitable for reproducible operator
artefacts or autonomous cycles. Phase 25 replaces the live dependence
with snapshot-pinned files committed to the repo: every (symbol,
timeframe) baseline has a fixed CSV of OHLCV rows plus a metadata
sidecar. Re-runs hit the snapshot, not the network.

## Layout

```
data/backtest/snapshots/
└── baselines/
    └── <SYMBOL>__<timeframe>/      # e.g. BTCUSDT__1h
        ├── ohlcv.csv               # header + one row per candle
        └── metadata.json           # fetch sidecar
```

Symbols use the no-slash filesystem-safe spelling (`BTCUSDT`, not
`BTC/USDT`); the canonical `BTC/USDT` form lives inside
`metadata.json`.

## File formats

See `src/backtest/snapshot.py` module docstring for the full spec.
Summary:

- **`ohlcv.csv`** — header
  `timestamp,open,high,low,close,volume`. `timestamp` is ISO-8601
  UTC; price/volume cells are decimal strings (preserved by
  `Decimal` round-trip).
- **`metadata.json`** — `symbol`, `timeframe`, `source`,
  `fetched_at`, `candle_count`, `first_timestamp`, `last_timestamp`,
  `fetcher_version`.

The loader (`src.backtest.snapshot.load_snapshot`) validates the full
schema on read and raises `SnapshotValidationError` on any breach
(header mismatch, candle-count drift, unparseable cell, etc.).

## Freshness policy

Snapshots are considered fresh for **90 days** from `fetched_at`.
After that, the baseline run will fail loud and the operator must
explicitly opt in to refreshing the snapshot via the Phase 25.2
`--refresh-snapshot` flag (operator-gated; writes to this directory).

## .gitignore exception

The repo's `.gitignore` ignores `data/` wholesale, but carves
`data/backtest/snapshots/` back in. These files **must** travel with
the repo — that's the whole point of the snapshot dataset.

## Status

Phase 25.1 lands the format spec, loader, and tests; this directory
is empty (`.gitkeep`-only) until Phase 25.2 wires the CLI flag and
populates the first baselines.

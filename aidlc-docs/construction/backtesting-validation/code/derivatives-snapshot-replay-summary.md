# Derivatives Data Slice 4 Code Generation Summary

**Primary unit:** `backtesting-validation`

**Secondary units:** `exchange-integration`, `strategy-framework`,
`persistence-data-integrity`, `quality-governance`

**Stage:** Code Generation Part 2

**Status:** Generated; explicit operator review pending

## Scope generated

Slice 4 implements LC-11: immutable Snapshot v1/v2 replay, per-primary-bar
Funding/OI context, backtest and robustness propagation, and an explicit
collector-to-Snapshot-v2 refresh command. Promotion evidence now comes from one
pinned generation and records its identity, canonical configuration digest,
seed, and context coverage.

The ordinary robustness path remains offline and snapshot-first. It never
falls through to Binance when a snapshot is absent or invalid. Live reads are
available only through the explicit exploratory `--live` mode, while snapshot
publication requires the separate explicit `--refresh-snapshot` command.

## Replay and reproducibility contract

- `SnapshotReplaySource` loads `CURRENT` once or an exact generation id and
  retains that validated bundle for the run. A later `CURRENT` change cannot
  alter the loaded source.
- OHLCV and derivatives context come from the same bundle. Schema v1 remains
  usable for OHLCV but represents required Funding/OI as unavailable.
- Each decision uses the primary candle close as `as_of`; later Funding/OI
  observations and predicted funding are excluded.
- Series conversion delegates freshness, slicing, and requirement evaluation
  to the existing sealed `MarketContextBuilder` rather than reproducing live
  context logic.
- An explicitly uncovered prefix is neutral. Structural internal/suffix gaps
  fail loudly, and an unusable or too-short required-context suffix becomes
  promotion-blocking `INSUFFICIENT_DATA`.
- `ReplayIdentity` and `canonical_configuration_digest` provide stable,
  serializable provenance for individual and combined backtests.

## Backtest, gate, and harness behavior

- `BacktestEngine.run`, `run_multi_timeframe`, and `run_for_strategy` accept an
  optional context provider, replay identity, and seed. Existing callers that
  omit them preserve the OHLCV-only path.
- Required strategies skip analysis neutrally while context requirements are
  unmet. Optional strategies and legacy `analyze` signatures are unchanged.
- `BacktestResult` records replay identity, digest, seed, eligible-bar count,
  and unmet-bar count; JSON serialization carries the same evidence.
- `RobustnessGate.evaluate_snapshot` uses the same replay source for baseline,
  out-of-sample, walk-forward, and sensitivity runs.
- `GateStatus.INSUFFICIENT_DATA` is distinct from compatible `SKIPPED` results
  and always blocks `overall_passed`.
- `BacktestHarness` accepts an optional `(symbol, timeframe)` replay map,
  propagates the source into backtest and robustness evaluation, preserves a
  compatible generation identity, and rejects mixed generations.

## Explicit refresh and CLI behavior

- `--refresh-snapshot [ROOT]` deduplicates requested pairs, fetches the full
  OHLCV window plus settled Funding and retained OI for its exact bounds,
  validates metadata, writes immutable Snapshot v2 generations, prints their
  ids, and exits without running promotion gates.
- Default/`--snapshot [ROOT]` evaluates offline snapshots. Repeated
  `--generation-id STRATEGY=<id>` arguments select exact generations.
- `--live` remains explicitly exploratory and unpinned; a context-required
  unpinned evaluation cannot be reported as promotion-passed.
- CLI/collector tests use fakes and temporary directories. Code Generation
  performed no live network call and did not write repository `data/`.

## Files

Created:

- `src/backtest/reproducibility.py`
- `src/backtest/snapshot_replay.py`
- `tests/test_backtest_snapshot_replay.py`
- `aidlc-docs/construction/backtesting-validation/code/derivatives-snapshot-replay-summary.md`
- `docs/sessions/2026-07-19-backtesting-validation-derivatives-snapshot-replay.md`

Modified for application behavior and tests:

- `src/backtest/__init__.py`
- `src/backtest/engine.py`
- `src/backtest/validator.py`
- `src/backtest/harness.py`
- `scripts/run_robustness_gate.py`
- `tests/test_backtest_engine.py`
- `tests/test_backtest_multi_timeframe.py`
- `tests/test_backtest_validator.py`
- `tests/test_backtest_harness.py`
- `tests/test_run_robustness_gate.py`

Modified for lifecycle tracking:

- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/plans/backtesting-validation-code-generation-plan.md`
- `aidlc-docs/audit.md`

Intentionally unchanged by Slice 4:

- Runtime cache persistence and production `data/`
- Proposal filtering, Funding-Extreme MR, strategy thresholds, and funding-cost
  math
- Dependencies, lockfile, credentials, migrations, deployment, and production
  enablement

## Code Generation verification evidence

- Pre-edit focused baseline: 182 passed.
- Snapshot v1/v2 plus replay/engine/gate/harness/CLI regression: 204 passed.
- Core replay/engine/gate/harness/CLI coverage run: 120 passed; 96% combined
  statement coverage (`engine` 98%, `harness` 94%, `reproducibility` 80%,
  `snapshot_replay` 93%, `validator` 97%).
- Shared live/replay builder compatibility: 103 passed.
- Existing backtest script consumers: 46 passed.
- Complete repository regression: 2579 passed in 43.80 seconds.
- Changed-file Black and Ruff: clean.
- `uv run mypy src`: 113 source files, zero issues.
- `uv lock --check`, compile checks, and `git diff --check`: passed.
- Duplicate/TODO/dependency/credential/deployment/runtime-data scans: clean.
- No actual exchange/network call or repository `data/` write occurred.

## Compatibility, debt, and remaining work

No new technical debt was introduced. DEBT-081 continues to own unrelated
repository-wide Black/Ruff drift and was not mixed into this slice.

FR-046, US-025, and LC-11 remain Partial at this boundary. They become eligible
for completion only after the operator approves generated code and independent
Construction Build & Test plus cross-check pass. Slice 5 proposal-layer
Funding+OI filtering and the later evidence-gated Funding-Extreme MR strategy
remain separate work.

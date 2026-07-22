# Unit Test Instructions: market-regime Funding+OI Crowding Shadow Filter

## Focused command

```bash
uv run pytest -q \
  tests/test_runtime_funding_oi_filter.py \
  tests/test_runtime_gate_reason.py \
  tests/test_trading_sub_account.py \
  tests/test_runtime_engine.py \
  tests/test_dashboard_engine.py
```

Verified result: 317 passed in 3.75 seconds. The same set with
`--cov=src.runtime.funding_oi_filter --cov-report=term-missing` passed in 5.62
seconds and measured 91% statement coverage for the classifier module.

Primary assertions cover deterministic long/short/neutral/unavailable
classification, predicted-Funding exclusion, evidence qualification, frozen
shadow-only policy, disabled zero work, unchanged fill/rejection outcome,
exact safe event fields, provider-error sanitization, and honest dashboard
counts/order/labels.

---

# Prior Unit Test Instructions: backtesting-validation Derivatives Data Slice 4

## Focused command

```bash
uv run pytest \
  tests/test_backtest_snapshot.py \
  tests/test_backtest_snapshot_v2.py \
  tests/test_backtest_snapshot_replay.py \
  tests/test_backtest_engine.py \
  tests/test_backtest_multi_timeframe.py \
  tests/test_backtest_validator.py \
  tests/test_backtest_harness.py \
  tests/test_run_robustness_gate.py -q
```

Verified result: 210 passed in 11.69 seconds.

## Generated-path coverage

The v2/replay/engine/validator/harness/CLI subset passed 183 tests in 17.80
seconds with 92% combined statement coverage across the measured modules:

| Module | Coverage |
|--------|----------|
| `src.backtest.snapshot_v2` | 85% |
| `src.backtest.reproducibility` | 82% |
| `src.backtest.snapshot_replay` | 95% |
| `src.backtest.engine` | 98% |
| `src.backtest.validator` | 97% |
| `src.backtest.harness` | 94% |

The repository defines no coverage fail-under threshold; these values are
recorded evidence, not a new acceptance floor.

## Primary assertions

- Exact v1/v2 negotiation, generation pinning, moved-`CURRENT` stability,
  identity/digest/seed serialization, and deterministic repeated reports.
- Primary-candle `as_of`, no future Funding/OI, predicted funding absent, and
  identical shared-builder output.
- Explained prefix neutralization, unexplained Funding prefix rejection,
  structural suffix rejection, and required-context `INSUFFICIENT_DATA`.
- Optional/legacy strategy signatures, OHLCV-only callers, multi-timeframe
  boundaries, and unrelated `SKIPPED` behavior remain compatible.
- Runner failure reports serialize only a stable exception type, never raw
  exception text, local paths, signatures, or key-like data.

---

# Prior Unit Test Instructions: exchange-integration Derivatives Data Slice 3

## Core command

```bash
uv run pytest \
  tests/test_exchange_derivatives.py \
  tests/test_strategy_market_context.py \
  tests/test_runtime_derivatives_context.py \
  --cov=src.exchange.derivatives \
  --cov=src.strategy.market_context \
  --cov=src.runtime.derivatives_context \
  --cov-report=term-missing -q
```

## Verified core result

- 45 tests passed in 7.59 seconds.
- Combined generated-module statement coverage: 89% (726 statements, 78
  missed).
- Per module: derivatives domain 90%, runtime service 91%, pure context builder
  80%.
- The repository declares no coverage fail-under threshold; these exact values
  are evidence, not a newly invented acceptance floor.

## Modified-component regression

```bash
uv run pytest \
  tests/test_exchange_derivatives.py \
  tests/test_strategy_base.py \
  tests/test_strategy_loader.py \
  tests/test_strategy_market_context.py \
  tests/test_proposal_engine.py \
  tests/test_runtime_derivatives_context.py \
  tests/test_runtime_engine.py \
  tests/test_main_dispatch.py \
  tests/test_runtime_activity_log.py \
  tests/test_dashboard_ops.py \
  tests/test_config.py -q
```

Verified result: 562 passed in 7.97 seconds after the canonical request-budget
error-code repair.

## Primary unit assertions

- Frozen UTC/finite-Decimal domain contracts and availability coherence.
- Pure `as_of` slicing, future exclusion, hard expiry, partial series, stable
  requirement evaluation, and predicted-funding restrictions.
- Bounded concurrency, request budgets, retry/circuit transitions, deadlines,
  cancellation/await, atomic last-known-good cache replacement, and close.
- Backward-compatible strategy metadata/signatures and neutral required-context
  behavior.
- Disabled-default configuration, engine prefetch/fail-open/shutdown, safe
  events, and Ops projection.

---

# Prior Unit Test Instructions: backtesting-validation Derivatives Snapshot Schema v2

## Current command

```bash
uv run pytest \
  tests/test_backtest_snapshot.py \
  tests/test_backtest_snapshot_v2.py \
  --cov=src.backtest.snapshot_v2 \
  --cov-report=term-missing
```

## Verified result

- 84 tests passed in 3.05 seconds.
- `src/backtest/snapshot_v2.py` statement coverage: 84% (474 statements,
  74 missed).
- The repository declares no coverage fail-under threshold. The exact report is
  recorded without inventing one.

## Behaviors exercised

- Frozen v2 metadata/manifest/bundle contracts, UTC/Decimal fidelity, and
  explicit v1 derivatives unavailability.
- Canonical CSV/JSON, content-derived generation identity, exact file
  allowlist, SHA-256, byte-size, row-count, and provenance validation.
- OHLCV/Funding/OI time-grid, order, uniqueness, gap, count, range, future-point,
  and OI retention contracts.
- Staged publication, finalized validation, atomic `CURRENT`, pinned reads,
  same-id reuse/race behavior, and every pre-pointer rollback phase.
- Corruption, invalid UTF-8, traversal/absolute ids, direct/dangling symlinks,
  missing/unknown files, and noncanonical byte rejection.
- Schema-v1 reader/writer compatibility and no-mutation fallback.

## Failure interpretation

Any failure is a Slice 2 blocker. Do not loosen canonical encoding, manifest,
path, atomicity, timestamp, coverage, or v1-compatibility contracts to make a
candidate pass.

---

# Prior Unit Test Instructions: exchange-integration Derivatives Data Slice 1

## Command

```bash
uv run pytest \
  tests/test_exchange_base.py \
  tests/test_exchange_ccxt_base.py \
  tests/test_exchange_binance.py \
  tests/test_exchange_bybit.py \
  tests/test_exchange_derivatives.py \
  --cov=src.exchange \
  --cov-report=term-missing
```

## Verified result

- 221 tests passed in 1.95 seconds.
- `src.exchange` statement coverage: 87% (718 statements, 91 missed).
- New `src/exchange/derivatives.py` statement coverage: 92% (142 statements,
  12 missed).
- The repository has no declared coverage fail-under threshold, so the exact
  report is recorded without inventing one.

## Behaviors exercised

- Frozen Funding/OI models, Decimal constraints, UTC normalization, naive-time
  rejection, symbol validation, and exact history metadata.
- Capability defaults and stable unsupported-venue behavior for existing
  adapters.
- Binance current Funding/OI mapping without exposing raw CCXT payloads.
- Funding 8h and OI 1h interval enforcement.
- Page caps, movement from the last actual record, inclusive `until`, overlap
  de-duplication, empty responses, and loud gap detection.
- Explicit OI retention-truncated prefix metadata.
- Typed and sanitized exchange error classification.
- Public Binance construction without empty credential keys.

## Failure interpretation

A failure in these five suites is a Slice 1 blocker. Do not compensate by
loosening timestamp, continuity, retention, validation, or error-code
contracts.

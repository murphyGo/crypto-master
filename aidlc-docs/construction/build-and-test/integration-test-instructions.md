# Integration Test Instructions: market-regime Funding+OI Crowding Shadow Filter

## Current boundary

```text
existing cycle derivatives refresh/cache
  -> context_for(proposal.symbol, as_of=proposal.created_at)
  -> pure Funding/OI classifier
  -> shadow observed/skipped activity event
  -> unchanged proposal fill/rejection outcome
  -> Engine Market Regime dashboard projection
```

The focused 317-test run verifies this boundary, including one cache read and
no hot-path refresh. A `would_block=true` long still opens in paper mode and
does not increment rejection counters. Disabled policy performs no lookup or
event. Provider failure emits a sanitized fail-open skip.

The complete repository regression passed 2604 tests in 45.09 seconds. All
tests use typed fixtures/mocks and local temporary state; no live endpoint,
credential, order, deployment, or repository `data/` path is involved.

---

# Prior Integration Test Instructions: backtesting-validation Derivatives Data Slice 4

## Current boundaries under test

```text
fake normalized exchange history
  -> explicit Snapshot v2 publication
  -> exact generation reload
  -> SnapshotReplaySource
  -> shared MarketContextBuilder at each primary candle
  -> Backtester / BacktestHarness
  -> RobustnessGate baseline + OOS + walk-forward + regime + sensitivity
  -> deterministic operator report
```

## Hermetic E2E

`test_refresh_reload_replay_report_is_hermetic_and_deterministic` executes the
full fake collector-to-report chain twice with one exact generation and seed.
It passed in 1.27 seconds and produced identical normalized reports. No network,
credential, service, live order, or repository `data/` path is involved.

## Cross-component compatibility

```bash
uv run pytest \
  tests/test_strategy_market_context.py \
  tests/test_runtime_derivatives_context.py \
  tests/test_proposal_engine.py -q
```

Verified result: 103 passed in 4.59 seconds.

Existing backtest baseline/combination/auto-research consumers passed 46 tests
in 17.77 seconds.

## Complete repository regression

```bash
uv run pytest -qq
```

Verified result: 2585 passed in 46.89 seconds.

## Isolation and cleanup

- Collector and E2E paths use a fake exchange and pytest `tmp_path`.
- Snapshot load failure has no live fallback.
- The real `--refresh-snapshot` and `--live` paths were not invoked.
- No deployment, credential, process, order, or repository runtime-data action
  occurred.

---

# Prior Integration Test Instructions: exchange-integration Derivatives Data Slice 3

## Current boundaries under test

```text
credential-free fake/public source
  -> DerivativesContextService
  -> immutable SeriesSnapshot cache
  -> MarketContextBuilder
  -> ProposalEngine requirements/signature boundary
  -> TradingEngine prefetch/fail-open/shutdown
  -> activity log -> Ops Diagnostics read model
```

`src/main.py` composition is verified separately to inject the same dedicated
service into proposal and runtime consumers while never reusing the account
trading exchange.

## Focused runtime integration

```bash
uv run pytest \
  tests/test_proposal_engine.py \
  tests/test_runtime_engine.py \
  tests/test_main_dispatch.py \
  tests/test_runtime_activity_log.py \
  tests/test_dashboard_ops.py \
  -k 'context or derivatives' -q
```

Verified result: 11 passed, 341 deselected in 1.81 seconds.

The selected cases prove one final-candle context lookup shared across
techniques, required-missing neutral behavior, legacy signature compatibility,
one stable-union prefetch before scanning, outage fail-open, exactly-once
shutdown, dedicated empty-credential composition, stable event values, and
newest-event Ops folding.

## Complete repository regression

```bash
uv run pytest -q
```

Verified result after the Build & Test contract repair: 2557 passed in 46.74
seconds.

## Isolation and cleanup

- All service and integration boundaries use deterministic fakes/mocks.
- No real Binance request, credential, live order, deployment, or production
  enablement is used.
- Runtime cache is process-local only; tests write no repository `data/`.
- LC-11 snapshot replay, proposal filtering, and Funding-Extreme MR remain
  outside Slice 3.

---

# Prior Integration Test Instructions: backtesting-validation Derivatives Snapshot Schema v2

## Current boundaries under test

```text
SnapshotV2 bundle
  -> canonical codecs
  -> same-root staged generation
  -> production reader validation
  -> immutable generation + atomic CURRENT
  -> pinned/current VersionedSnapshot

schema v1 snapshot -> unchanged legacy loader and script consumers
```

## Atomic persistence integration

```bash
uv run pytest \
  tests/test_backtest_snapshot.py \
  tests/test_backtest_snapshot_v2.py \
  tests/test_utils_atomic_write.py
```

Verified result: 102 passed in 3.26 seconds.

## Existing consumer compatibility

```bash
uv run pytest \
  tests/test_scripts_backtest_baselines.py \
  tests/test_run_robustness_gate.py \
  tests/test_scripts_backtest_combinations.py \
  tests/test_scripts_auto_research_candidates.py
```

Verified result: 54 passed in 28.36 seconds.

## Isolation and cleanup

- All generated v2 storage tests use pytest `tmp_path`.
- No external service, Binance request, credential, or live order is used.
- No repository runtime `data/` is written; pytest cleans temporary state.
- LC-11 replay/context integration remains intentionally outside this slice.

---

# Prior Integration Test Instructions: exchange-integration Derivatives Data Slice 1

## Boundary under test

The Slice 1 integration boundary is:

```text
BaseExchange -> CcxtExchange -> BinanceExchange / BybitExchange -> mocked CCXT client
```

It deliberately stops before snapshot persistence, runtime collection,
proposal filters, strategies, dashboards, and trading execution.

## Command

```bash
uv run pytest \
  tests/test_exchange_base.py \
  tests/test_exchange_ccxt_base.py \
  tests/test_exchange_binance.py \
  tests/test_exchange_bybit.py
```

The full five-suite command in `unit-test-instructions.md` is the canonical
combined unit/integration run and passed 221 tests.

## Integration scenarios

- Existing adapters remain instantiable because derivatives methods have
  concrete unsupported defaults instead of new abstract requirements.
- The shared CCXT protocol declares only the calls consumed by the adapter.
- Binance advertises derivatives-data capability and maps unified CCXT
  responses to normalized immutable contracts.
- Bybit remains explicitly unsupported for v1 derivatives data.
- CCXT calls are mocked with deterministic async fakes, including multi-page,
  short-page, overlap, gap, retention, malformed-payload, and exchange-error
  responses.

## Isolation and cleanup

- No real Binance/Bybit request is made.
- No API key or secret is required.
- No service process is started and no cleanup process is needed.
- Tests use pytest-managed temporary/mocked state and do not write repository
  runtime `data/`.

Live public endpoint compatibility and runtime service behavior belong to a
later service/operations slice and are not represented as verified here.

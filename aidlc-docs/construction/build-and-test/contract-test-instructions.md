# Contract Test Instructions: backtesting-validation Derivatives Data Slice 4

## Contract assertions

- One loaded replay uses `CURRENT` once or an exact 64-hex generation id and
  preserves that identity for the run.
- OHLCV and Funding/OI context originate from the same generation; multi-TF
  primary OHLCV must match it exactly.
- Every context record timestamp is at or before the primary candle `as_of`;
  predicted funding is absent.
- Schema v1 maps required derivatives to explicit unavailability.
- An explained/retained prefix can be neutral, but an unexplained Funding
  prefix, internal gap, or uncovered suffix fails closed.
- Required context cannot pass an unpinned, v1, missing, too-short, or
  post-coverage-gap robustness run. `INSUFFICIENT_DATA` blocks promotion and
  remains distinct from legacy `SKIPPED`.
- Backtest and robustness artifacts record replay identity, canonical
  configuration digest, seed, and coverage; repeated identical inputs produce
  identical reports.
- Snapshot mode is default/offline, refresh and live modes are explicit, and
  snapshot failure never falls through to live Binance.

Verified by the 210 focused tests, 103 shared-builder/runtime/proposal tests,
46 legacy script-consumer tests, and 2585 complete repository tests.

## Completion boundary

LC-11, FR-046, and US-025 are complete after this independent verification
when read with the already sealed Slice 1 acquisition, Slice 2 persistence, and
Slice 3 runtime-context evidence. Proposal-layer Funding+OI filtering and
Funding-Extreme MR remain separate product slices, not missing LC-11 contract.

---

# Prior Contract Test Instructions: exchange-integration Derivatives Data Slice 3

## Current command

```bash
uv run pytest \
  tests/test_exchange_derivatives.py \
  tests/test_strategy_market_context.py \
  tests/test_runtime_derivatives_context.py -q
```

Verified as part of the coverage run: 45 passed in 7.59 seconds.

## Contract assertions

- `DerivativesDataSource` exposes only the normalized current/history funding
  and OI calls used by the service.
- Context/state models are frozen, UTC-normalized, finite, symbol-consistent,
  chronological, and explicit about partial/unavailable series.
- Stable request-budget exhaustion is exactly
  `request_budget_exhausted`; Build & Test corrected the generated shortened
  value and reran all regression layers.
- `MarketContext` contains no record newer than its decision `as_of` and
  predicted funding never satisfies requirements or survives degradation.
- `TechniqueInfo` remains backward compatible by default; required context has
  non-empty typed requirements.
- Proposal dispatch passes context only to a declared keyword/`**kwargs`
  signature and never retries a strategy-body `TypeError`.
- Activity events expose exactly the approved eleven safe keys and stable
  degraded/recovered values.
- Disabled configuration constructs no service/client and issues no request;
  enabled composition shares one dedicated service without sharing a trading
  exchange.

## Completion boundary

These tests verify LC-04..09 and LC-12..13. LC-10 persistence is already
verified by Slice 2; LC-11 snapshot-only replay remains Slice 4. Therefore
FR-046 and US-025 remain Partial.

---

# Prior Contract Test Instructions: backtesting-validation Derivatives Snapshot Schema v2

## Current command

```bash
uv run pytest tests/test_backtest_snapshot.py tests/test_backtest_snapshot_v2.py
```

Verified result: 84 passed.

## Contract assertions

- Layout is `CURRENT` plus
  `generations/<64-lowercase-hex-id>/{ohlcv.csv,funding.csv,open_interest.csv,metadata.json,manifest.json}`.
- `CURRENT` contains exactly one validated id plus LF and changes only after
  staged/finalized production-reader validation.
- Manifest keys are exactly the four data files; each entry records SHA-256,
  byte size, and CSV row count (`null` for metadata).
- Canonical UTC ISO-8601, finite Decimal strings, UTF-8, LF, fixed CSV headers,
  and sorted compact JSON feed stable content identity.
- Only settled `FundingRate` and normalized OI history are accepted. Predicted
  funding and raw venue payloads have no persistence contract.
- Pinned generations remain stable after `CURRENT` advances; readers never
  infer latest by mtime.
- `CURRENT` absence alone delegates to the unchanged schema-v1 loader and
  reports derivatives unavailable. Corrupt v2 never falls through to v1.

## Completion boundary

These tests verify LC-10 persistence and version negotiation. They are not
evidence for LC-11 per-bar `MarketContext` slicing or runtime collection.

---

# Prior Contract Test Instructions: exchange-integration Derivatives Data Slice 1

## Command

```bash
uv run pytest \
  tests/test_exchange_base.py \
  tests/test_exchange_ccxt_base.py \
  tests/test_exchange_binance.py \
  tests/test_exchange_bybit.py \
  tests/test_exchange_derivatives.py
```

## Contract assertions

- Funding and OI public values use finite `Decimal` values and UTC-aware
  timestamps.
- Public models are frozen and exclude venue-specific raw payloads.
- `BaseExchange` defaults `supports_derivatives_data` to false and raises the
  stable `unsupported_venue` error for all four derivatives methods.
- Binance alone advertises support in v1; Bybit compatibility is preserved.
- Stable domain error codes are `derivatives_data_error`,
  `unsupported_venue`, `invalid_payload`, `timestamp_gap`, and
  `unsupported_interval`.
- Funding history is a strict 8h contiguous sequence.
- OI history is a strict 1h returned suffix with exact actual bounds and
  explicit retention truncation.
- CCXT protocol additions are limited to the unified derivatives calls used by
  the adapter.

## Compatibility rule

Any later change to persisted snapshot schema, service envelopes, cache
metadata, or strategy inputs must be tested in its own slice. Slice 1 must not
be treated as proof for those later contracts.

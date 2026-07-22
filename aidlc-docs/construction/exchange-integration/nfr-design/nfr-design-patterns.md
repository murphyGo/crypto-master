# NFR Design Patterns: Derivatives Market Context — v1

## Status and decision basis

This design converts DD-NFR-001..012 and TS-01..09 into implementation
patterns for FR-046 / US-025. The operator accepted every recommended NFR
Design choice (Q1-Q10) on 2026-07-18.

The design is intentionally in-process. It adds no external cache, queue,
database, credential store, worker, or deployment topology. It also does not
authorize a live proposal veto or a Funding-Extreme MR trade: those consumers
retain their separate hypothesis, replay-evidence, and rollout gates.

## Architectural shape

```text
TradingEngine cycle
    |
    | union of active public symbols, cycle_id, deadline
    v
DerivativesContextService (one per public venue / engine process)
    |-- RefreshScheduler        semaphore + deadline + in-flight dedupe
    |-- RequestBudget          rolling endpoint windows
    |-- RetryPolicy            transient-only, bounded full jitter
    |-- CircuitRegistry        state per venue/symbol/series
    |-- SeriesCache            process-local last-known-good records
    |-- MarketContextBuilder   pure as_of slicing + requirement evaluation
    |-- HealthEventEmitter     degraded/recovered state transitions
    |
    v
Binance public derivatives adapter (dedicated credential-free ccxt client)

Snapshot refresh ----------------> immutable schema-v2 generation
Backtest/replay <---------------- atomic CURRENT pointer + verified manifest
```

## Non-negotiable invariants

1. The service never places orders or reads account data.
2. Raw ccxt dictionaries never escape the adapter boundary.
3. No historical record newer than the requested `as_of` enters a
   `MarketContext`.
4. Missing, stale, unsupported, and retention-truncated data are distinguishable;
   no zero-fill, forward-fill, interpolation, or silent truncation is allowed.
5. A derivatives failure cannot stop consumers that do not require derivatives.
6. The runtime cache is process-local and disposable. Durable replay input is
   an immutable, validated snapshot generation, never the cache.
7. One deployment has one active public derivatives collector in v1.
8. Existing deployments perform no new derivatives calls until explicitly
   enabled; proposal enforcement remains separately disabled.

## NDP-01 — Shared-service bulkhead and public-client isolation

**Pattern:** Engine-scoped shared service + narrow public data port + bulkhead.

- Build one `DerivativesContextService` for Binance public USDⓈ-M data and
  inject the same instance into runtime/proposal paths that need context.
- All sub-accounts share public series by `(venue, symbol, series)`, regardless
  of their credential reference or trading exchange instance.
- The service receives a narrow `DerivativesDataSource` protocol. It cannot
  call balance, order, position, or private-account methods.
- The source uses a dedicated long-lived `binanceusdm` ccxt client created
  without `apiKey` or `secret`, with `enableRateLimit=True`.
- A service-level `asyncio.Semaphore(4)` bulkheads derivatives calls from the
  rest of the event loop. Symbol/series failures remain isolated.

**Why:** Public data does not vary by sub-account. Sharing removes duplicate
traffic and prevents a credential-bearing trading client from entering the
public-data trust boundary.

**Traceability:** DD-NFR-001, 006, 007, 011, 012; Q1, Q9.

## NDP-02 — Batch prefetch, monotonic deadline, and in-flight dedupe

**Pattern:** Cycle-start batch prefetch with deadline propagation.

1. `TradingEngine.run_cycle()` computes the stable union of the BTC symbol and
   configured altcoin symbols across active sub-accounts.
2. If collection is enabled, it calls one `refresh_cycle()` before the first
   sub-account scan.
3. The service schedules only refreshes that are due:
   - settled funding history when a new settlement may exist;
   - OI history when the next 1h observation may exist;
   - current OI and predicted funding at most once for the cycle when requested.
4. Canonical request keys
   `(venue, endpoint_group, symbol, timeframe, since, until)` share one task.
5. The batch uses one `time.monotonic()` deadline:
   - <= 4 symbols: 5 seconds;
   - 5..20 symbols: 15 seconds;
   - > 20 symbols: rejected by validated configuration until a new review.
6. Every request/retry receives the remaining deadline. At exhaustion, pending
   tasks are cancelled, awaited with exception collection, and excluded from
   the cycle result so no background task mutates cache after the decision.
7. Completed validated results are committed per series. One cancelled series
   cannot roll back another healthy series.

The service returns a `RefreshSummary`; it does not throw a batch-level error
for ordinary per-series degradation. An internal programming/invariant error
may still fail the refresh call, but the engine catches it, emits a service
degradation, and continues the OHLCV path.

**Traceability:** DD-NFR-001, 002, 004, 006, 007; Q4.

## NDP-03 — Last-known-good cache and explicit partial availability

**Pattern:** Stale-while-revalidate with hard freshness expiry and typed state.

Each `(venue, symbol, series)` cache entry contains immutable normalized
records plus `fetched_at`, `last_observed_at`, retention metadata, and the last
health/error state. Cache mutation occurs only after full response validation.

At context-build time, a series is projected into one of these statuses:

| Status | Records exposed | Meaning |
|---|---|---|
| `fresh` | Yes | Current refresh/history is valid and within age policy |
| `cached` | Yes | Refresh degraded, but last-known-good is still eligible |
| `stale` | No | Cache exists but exceeds Funding 9h or OI 2h age |
| `unavailable` | No | No eligible cache after a transient/non-retryable failure |
| `unsupported` | No | Venue does not implement the series |
| `unsupported_interval` | No | Funding interval is not canonical 8h in v1 |

`truncated_at_venue_retention` is orthogonal metadata, not a health failure:
the retained OI suffix can be `fresh` and explicitly truncated at the same
time. Predicted funding is eligible only in the fetch cycle and is excluded
from promotion-relevant decision features and every replay.

For a wired/supported Binance provider, `context_for()` returns a
`MarketContext` with per-series status even if both series are unavailable.
`None` is reserved for collection disabled, provider absent, or venue-level
unsupported wiring. This lets consumers distinguish an outage from “feature
not configured.”

Consumers evaluate an immutable `MarketContextRequirements` declaration:

- optional/required funding and OI flags;
- minimum point counts per series;
- maximum accepted age per series, bounded by the global hard ceilings.

Requirement failure never synthesizes data:

- ordinary strategy: neutral;
- proposal Funding+OI filter: skip/fail-open plus stable gate reason;
- robustness/promotion gate: `INSUFFICIENT_DATA`.

**Traceability:** DD-NFR-003, 004, 007, 009; Q2.

## NDP-04 — Bounded retry and isolated circuit state machine

**Pattern:** Typed retry classifier + per-series circuit breaker.

### Retry classification

| Class | Examples | Retry? | Circuit failure? |
|---|---|---:|---:|
| Transient network | timeout, connection reset, DNS/network unavailable | Yes | Yes after attempts exhausted |
| Venue transient | HTTP 429, exchange unavailable, HTTP 5xx | Yes | Yes after attempts exhausted |
| Unsupported | venue capability false, adjusted funding interval | No | No |
| Validation | malformed field, timestamp gap, wrong symbol/order | No | No |
| Security/auth | authentication error on credential-free client | No | No; emit stable security-safe error |
| Budget/deadline | local request budget or cycle deadline exhausted | No | No; availability degrades for cycle |

An operation has one initial attempt plus at most two retries. Before retry 1,
sleep `uniform(0, 0.25s)`; before retry 2, sleep `uniform(0, 0.50s)`. Both the
sleep and next attempt are skipped if insufficient cycle time remains. Clock,
sleep, and random sources are injected for deterministic tests.

### Circuit state

State is keyed by `(venue, symbol, series)`. A *refresh failure* means all
allowed attempts for one scheduled refresh were exhausted; individual attempts
do not each increment the consecutive count.

```text
CLOSED
  | 3 consecutive transient refresh failures
  v
OPEN_FOR_NEXT_CYCLE
  | skip exactly one full cycle
  v
HALF_OPEN
  |-- one probe succeeds ------------------> CLOSED, count=0, recovered event
  |-- one transient probe fails -----------> OPEN_FOR_NEXT_CYCLE
  `-- non-transient result ----------------> CLOSED circuit, series remains degraded
```

The circuit controls remote retry pressure only. Fresh eligible cache may still
be exposed while the circuit is open. A failure for BTC OI never opens ETH OI,
BTC funding, or the venue as a whole.

**Traceability:** DD-NFR-004, 005, 007, 010; Q3.

## NDP-05 — Conservative endpoint request budget

**Pattern:** Monotonic rolling-window admission guard above ccxt throttling.

- Keep independent configurable endpoint groups for the Binance funding
  shared window and OI-history window.
- Record admitted call timestamps/costs in monotonic deques and evict entries
  older than 300 seconds before every admission decision.
- Verified v1 ceilings are funding shared <= 250 calls/5min/IP and OI history
  <= 500 calls/5min/IP. Configuration may only reduce these defaults.
- Current-OI weight and other public calls remain represented by endpoint
  metadata rather than being assumed free.
- A tighter `Retry-After`, ccxt `RateLimitExceeded`, or venue signal blocks new
  admission for the indicated interval; it cannot raise the configured budget.
- Budget denial is a typed local result. It is not retried and does not consume
  circuit failures.
- One active collector process per deployment is a v1 invariant. Multiple
  processes on the same IP require a new shared-limiter design and capacity
  review; each process must not independently assume it owns 50%.

**Traceability:** DD-NFR-001, 002, 006, 012; Q5.

## NDP-06 — Immutable snapshot generations and atomic visibility pointer

**Pattern:** Copy-on-write immutable generation + atomic pointer commit.

Schema-v1 directories remain readable unchanged. The first schema-v2 refresh
adds this layout under the same symbol/timeframe directory:

```text
BTCUSDT__1h/
├── ohlcv.csv                 # optional existing v1 files remain untouched
├── metadata.json
├── CURRENT                   # atomically written generation id
└── generations/
    └── <generation-id>/
        ├── ohlcv.csv
        ├── funding.csv
        ├── open_interest.csv
        ├── metadata.json
        └── manifest.json
```

### Writer protocol

1. Fetch all requested pages and normalize records in memory.
2. Validate symbol, timestamp order, grids, coverage/truncation, and no future
   records before any publication.
3. Write files into an unreferenced staging generation using canonical UTF-8,
   LF newlines, and normalized Decimal/UTC encodings.
4. Compute SHA-256, byte size, and row count for every normalized data file;
   write `manifest.json` with `schema_version=2` and a generation id derived
   from stable content/provenance.
5. Load and validate the staged generation through the same reader used by
   replay.
6. Move/finish it as an immutable directory under `generations/`.
7. Atomically replace `CURRENT` with the validated generation id using the
   existing atomic-write utility. This is the only visibility change.

Any failure before step 7 leaves `CURRENT` untouched. Unreferenced staging
directories are ignored by readers and may be removed only by explicit safe
maintenance. Committed generations are not automatically deleted because
gate reports may pin their identities.

### Reader protocol

1. Read `CURRENT` once. Reject non-canonical generation ids/path traversal.
2. If absent, use the existing schema-v1 `ohlcv.csv`/`metadata.json` loader and
   expose derivatives as unavailable.
3. If present, load only the referenced generation.
4. Validate manifest/schema, file allowlist, hashes, sizes, counts, metadata,
   contiguity, coverage, and requested consumer requirements.
5. Never scan for “latest” directory by mtime and never fall through to a
   partially written generation.

This guarantees application-level crash atomicity. It does not claim storage
hardware durability beyond the semantics of the existing atomic-write stack.

**Traceability:** DD-NFR-008, 009, 011, 012; Q6.

## NDP-07 — Deterministic context construction and replay

**Pattern:** One pure context builder for live cached data and snapshot data.

`MarketContextBuilder.build(symbol, as_of, series_snapshots)` performs:

1. UTC-normalize `as_of`.
2. Select only settled funding/OI records with `timestamp <= as_of`.
3. Revalidate ascending order and duplicate-free timestamps.
4. Compute age and availability from the selected tail, not from an element
   beyond `as_of`.
5. Produce immutable lists/status metadata in deterministic order.
6. Evaluate consumer requirements without side effects.

Live runtime supplies cache snapshots; backtests supply immutable snapshot-v2
series. The same input values therefore create the same normalized context.
Promotion reports record snapshot generation id, configuration digest, and
seed. Network calls are impossible in snapshot mode. Predicted funding is
always `None` in replay and is not a v1 filter/MR decision input.

Non-8h funding is detected through cached Binance funding-info capability data
and observed history spacing. v1 marks it `unsupported_interval`; it never
drops, aggregates, or fabricates records onto an 8h grid. OI remains usable.

**Traceability:** DD-NFR-003, 004, 008, 009; Q2, Q7.

## NDP-08 — Allowlist security and error sanitization

**Pattern:** Credential-free transport + normalized allowlist + fail-closed
serialization.

- The public client configuration contains no credential keys at all; empty
  credentials are not logged or persisted either.
- Adapter mapping accepts only documented fields required by `FundingRate`,
  `OpenInterestPoint`, and capability metadata. The raw `info` dictionary is
  discarded after mapping.
- Typed boundary errors expose stable internal code, exception class category,
  and sanitized short message. A sanitizer removes URL query strings,
  authorization material, signatures, key-like tokens, and raw payload reprs.
- Activity event details and snapshot metadata use explicit Pydantic fields /
  dictionaries assembled from an allowlist; they never serialize
  `exception.__dict__`, ccxt client configuration, or raw response objects.
- Snapshot hashes cover normalized files, not raw venue responses.
- An unexpected authentication error on the credential-free public source is
  non-retryable and operator-visible without including request material.

**Traceability:** DD-NFR-010, 011, 012; Q9.

## NDP-09 — State-transition health telemetry

**Pattern:** Service-owned event state machine and read-model projection.

The service adds two stable activity types:

- `derivatives_data_degraded`
- `derivatives_data_recovered`

The allowlisted payload contains:

```text
exchange, symbol, series, status, error_code,
data_timestamp, data_age_seconds, cache_status,
attempt_count, circuit_state, truncated_at_venue_retention
```

Within a cycle, degradation is deduplicated by `(symbol, series, cycle_id)`.
Recovery is emitted only when the service's previous cross-cycle health state
was degraded and the series becomes fresh again. Consumers do not repeat
endpoint events; they record only decision outcomes such as
`gate_skipped_missing_market_context`.

Ops Diagnostics folds recent events into one latest row per symbol/series and
shows healthy/degraded status, age/cache state, and the operator next step. No
new dashboard route is created.

**Traceability:** DD-NFR-004, 007, 010, 011; Q8.

## NDP-10 — Conservative feature rollout

**Pattern:** Separate data-collection and decision-enforcement flags.

- `DerivativesDataConfig.enabled` defaults `False`, preserving existing network
  traffic, timing, and strategy behavior on upgrade.
- Enabling collection only builds/cache/exposes context; it does not change a
  proposal decision by itself.
- The future proposal filter has `off | observe | enforce`, default `off`:
  - `off`: no filter evaluation;
  - `observe`: record what would have happened, never alter proposal;
  - `enforce`: allow an evidence-approved consumer to down-weight/veto.
- Snapshot refresh is an explicit operator action and may run independently of
  runtime collection.
- Funding-Extreme MR remains a separately registered experimental strategy and
  returns neutral without satisfied context requirements.

**Traceability:** DD-NFR-002, 007, 010, 012; Q10.

## Failure outcome matrix

| Failure | Cache eligible? | Runtime output | Circuit | Snapshot refresh |
|---|---:|---|---|---|
| transient fetch exhausted | Yes | `cached` context + degraded event | increment/open at 3 | abort candidate |
| transient fetch exhausted | No | unavailable series + degraded event | increment/open at 3 | abort candidate |
| deadline/budget exhausted | Yes | cached context | unchanged | abort candidate |
| deadline/budget exhausted | No | unavailable series | unchanged | abort candidate |
| schema/grid validation | Yes | cached context + typed degradation | unchanged | abort candidate |
| unsupported venue | No | provider/context absent | unchanged | reject requested derivatives |
| non-8h funding | OI only | funding unsupported, OI preserved | unchanged | explicit unsupported/truncated metadata; no resample |
| snapshot file/hash gap | N/A | runtime unaffected | N/A | replay fails loudly; prior CURRENT intact |

## Verification obligations carried to Code Generation

- Fake-load measurement over >=100 cycles at 4 and 20 symbols, including
  cancellation cleanup and peak semaphore count.
- Exact fake-clock/random retry and circuit-transition tests.
- Cross-sub-account request dedupe and one-public-client assertions.
- TTL boundary and partial-context requirement evaluation tests.
- Secret/raw-response negative assertions for errors, events, and snapshots.
- Snapshot-v1 compatibility, v2 commit/rollback, pointer traversal rejection,
  hash corruption, OI retention, and replay determinism tests.
- Engine outage/recovery test proving OHLCV-only cycle continuity.
- Proposal filter remains `off`/`observe` until its own hypothesis evidence is
  approved.

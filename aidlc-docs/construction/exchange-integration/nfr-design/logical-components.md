# Logical Components: Derivatives Market Context — v1

## Purpose

This document assigns the approved NFR patterns to bounded logical components
and defines their contracts, dependency direction, lifecycle, state keys,
configuration, event schema, snapshot protocol, and Code Generation handoff.

## Dependency direction

```text
domain models / errors / requirements
          ^
          |
exchange adapter ---- runtime context service ---- engine/proposal consumers
          |                    |
          |                    +---- activity event port
          |
snapshot reader/writer ---- pure MarketContextBuilder ---- backtest/gates
```

The pure domain/context builder cannot import runtime IO, dashboard, ccxt, or
configuration singletons. The runtime service depends on narrow source/event
ports. Dashboard code reads events and never imports the live service.

## Component catalog

| ID | Logical component | Responsibility | Likely implementation paths |
|---|---|---|---|
| LC-01 | Derivatives domain | Normalized records, series state, requirements, typed errors | `src/exchange/derivatives.py`, `src/models.py` only if shared-model precedent requires |
| LC-02 | Derivatives data port | Narrow public fetch/capability protocol; capability default/typed unsupported behavior | `src/exchange/base.py`, `src/exchange/derivatives.py` |
| LC-03 | Binance public adapter | ccxt public client mapping, paging, interval/retention/contiguity validation | `src/exchange/binance.py`, `src/exchange/ccxt_base.py` |
| LC-04 | Refresh scheduler | Symbol-union batch, due checks, semaphore, deadline, task cancellation/dedupe | `src/runtime/derivatives_context.py` |
| LC-05 | Request budget | Endpoint rolling windows and Retry-After admission blocks | `src/runtime/derivatives_context.py` or focused `src/exchange/request_budget.py` if size warrants |
| LC-06 | Retry/circuit registry | Typed transient retry and per-series state transitions | `src/runtime/derivatives_context.py` or focused resilience module |
| LC-07 | Series cache | Process-local immutable last-known-good entries and health state | `src/runtime/derivatives_context.py` |
| LC-08 | Market context builder | Pure `as_of` slicing, freshness projection, requirement evaluation | `src/strategy/market_context.py` |
| LC-09 | Runtime integration | Build/close shared public service, prefetch once/cycle, inject context access | `src/main.py`, `src/runtime/engine.py`, `src/proposal/engine.py` |
| LC-10 | Snapshot v2 store | Immutable generations, manifest/hash validation, CURRENT commit, v1 negotiation | `src/backtest/snapshot.py` plus helper module if needed |
| LC-11 | Backtest/replay integration | Snapshot-only series source and identical context slicing per bar | `src/backtest/`, robustness scripts |
| LC-12 | Health projection | Activity vocabulary/emission and Ops Diagnostics latest-state fold | `src/runtime/activity_events.py`, `src/dashboard/pages/ops.py` |
| LC-13 | Configuration | Conservative bounded collection and future filter rollout settings | `src/config.py`, `.env.example` |

The path list is a Code Generation target map, not permission for broad
refactoring. A component may stay in one module until size/ownership evidence
justifies extraction.

## LC-01 — Domain types and error vocabulary

### Normalized records

```text
FundingRate
  symbol: str
  timestamp: UTC datetime
  rate: Decimal

OpenInterestPoint
  symbol: str
  timestamp: UTC datetime
  open_interest: Decimal
  open_interest_value: Decimal | None
```

Both are frozen/immutable. Constructors reject empty symbol, naive timestamp,
negative OI, and non-finite/invalid Decimal input. Funding remains signed.

### Series state

```text
SeriesKind = funding | open_interest
SeriesStatus = fresh | cached | stale | unavailable | unsupported |
               unsupported_interval

SeriesAvailability
  series: SeriesKind
  status: SeriesStatus
  data_timestamp: UTC datetime | None
  fetched_at: UTC datetime | None
  age_seconds: int | None
  from_cache: bool
  point_count: int
  truncated_at_venue_retention: bool
  error_code: StableDerivativesErrorCode | None
```

`truncated_at_venue_retention` may be true only for OI in v1. A status exposing
no records must have `point_count=0`; a `fresh`/`cached` status must have a data
timestamp and positive point count.

### Market context

```text
MarketContext
  symbol: str
  as_of: UTC datetime
  funding_rates: tuple[FundingRate, ...]
  open_interest: tuple[OpenInterestPoint, ...]
  funding_availability: SeriesAvailability
  open_interest_availability: SeriesAvailability
  predicted_funding_rate: Decimal | None
```

Pydantic serialization may use lists on disk/API boundaries, but the in-memory
frozen model exposes immutable sequences. Model validation rejects a symbol
mismatch, unsorted/duplicate timestamps, or any record newer than `as_of`.

Predicted funding is live metadata only. It is `None` in snapshot replay and
cannot satisfy a v1 strategy/filter requirement.

### Consumer declaration

```text
MarketContextRequirements
  funding_required: bool = False
  funding_min_points: int = 0
  funding_max_age_seconds: int | None
  open_interest_required: bool = False
  open_interest_min_points: int = 0
  open_interest_max_age_seconds: int | None
```

Maximum ages cannot exceed global Funding 32400s / OI 7200s ceilings. A
required series must request at least one point. Evaluation returns a typed
result with missing series/reasons; it does not raise for normal insufficiency.

`TechniqueInfo.requires_market_context: bool = False` remains the broad
metadata flag approved in Functional Design. A context-aware technique also
provides non-empty typed requirements; validation prevents
`requires_market_context=True` with no requirements. Existing techniques
remain unchanged.

### Stable error codes

The minimum vocabulary is:

```text
network_transient, rate_limited, venue_unavailable, remote_5xx,
deadline_exceeded, request_budget_exhausted, invalid_payload,
timestamp_gap, unsupported_venue,
unsupported_interval, authentication_unexpected, internal_error
```

Exceptions keep causes for local debugging but public serialization uses only
the stable code, safe category, and sanitized message.

## LC-02/03 — Data port and Binance adapter

### Narrow source protocol

The context service is typed against only these capabilities:

```text
DerivativesDataSource
  name: str
  supports_derivatives_data: bool
  connect() -> None
  disconnect() -> None
  get_funding_info() -> capability map
  get_funding_rate(symbol) -> current/predicted scalar view
  get_funding_rate_history(symbol, since, limit) -> list[FundingRate]
  get_open_interest(symbol) -> OpenInterestPoint
  get_open_interest_history(symbol, timeframe, since, limit)
      -> retained series result[OpenInterestPoint]
```

`BaseExchange` gains backward-compatible default derivatives methods that
raise a typed `DerivativesDataNotSupportedError`; it does not make every
existing adapter implement new abstract methods immediately. Binance sets
`supports_derivatives_data=True`; Bybit remains false in this v1 scope.

The shared `CCXTClient` protocol gains only the ccxt calls the adapter invokes.
History pagination advances from the final timestamp actually received plus
one grid step, never requested page size. Results are de-duplicated, sorted,
and then checked for the covered grid.

### Dedicated public instance

The application builder constructs a mainnet USDⓈ-M Binance adapter/source
whose ccxt configuration omits `apiKey` and `secret`. It is independent of:

- paper/testnet trading clients;
- live credential sets;
- a sub-account's spot/futures trading selection.

The service never exposes this broad adapter to consumers; the narrow protocol
prevents accidental order use. `connect()` may load public market metadata but
must not validate through a private endpoint.

### Interval and retention behavior

- Funding-info capability data is cached and refreshed conservatively within
  the funding shared budget.
- History spacing is a second validation boundary. Any observed/capability
  interval other than the canonical 8h returns `unsupported_interval` rather
  than resampling.
- OI history uses 1h canonical granularity, page max 500, and returns a result
  containing requested/actual range plus explicit venue-retention truncation.
- A page-level failure returns no partially stitched result to the cache or
  snapshot writer.

## LC-04..07 — `DerivativesContextService`

### Public contract

```text
async refresh_cycle(
    *, cycle_id: str, cycle_index: int, symbols: Sequence[str]
) -> RefreshSummary

context_for(
    symbol: str, *, as_of: datetime,
    requirements: MarketContextRequirements | None = None
) -> ContextEvaluation

async close() -> None
```

`RefreshSummary` contains requested/completed/cached/unavailable/cancelled
counts and per-series outcomes for tests/metrics; it contains no raw responses.
`ContextEvaluation` contains `MarketContext | None`, whether requirements are
satisfied, and stable unmet reasons.

### Internal keys

```text
CacheKey       = (venue, canonical_symbol, SeriesKind)
CircuitKey     = CacheKey
HealthKey      = CacheKey
InFlightKey    = (venue, endpoint_group, canonical_symbol,
                  timeframe, since, until)
BudgetKey      = (venue, endpoint_group)
EventDedupeKey = (cycle_id, canonical_symbol, SeriesKind)
```

Symbol canonicalization occurs before key construction. Mutable dictionaries
are service-private; cache values and returned summaries are immutable.

### Refresh transaction boundary

Per series, the transaction is:

1. Check feature enabled, due time, circuit, request budget, and remaining
   deadline.
2. Reuse/create the in-flight task.
3. Perform bounded retry through semaphore.
4. Normalize and validate the complete response/page set.
5. Atomically replace the in-memory `SeriesCacheEntry` reference.
6. Update circuit/health state and emit at most one transition event.

Steps 4-5 ensure malformed or partial data never displaces last-known-good.
The service takes a shallow immutable cache snapshot before building context so
concurrent refresh completion cannot mix two series generations inside one
context decision.

### Lifecycle

- Built only when `DerivativesDataConfig.enabled=True`.
- One public source connection per engine/application lifecycle.
- `refresh_cycle()` is called once before sub-account scanning.
- `close()` cancels/awaits remaining tasks and closes the public ccxt client on
  shutdown.
- No cache hydration from disk occurs on startup. The first cycle fetches
  public data; an outage immediately after restart produces explicit
  unavailable state rather than silently treating a backtest snapshot as live
  cache.

## LC-08 — Pure `MarketContextBuilder`

The builder receives already-normalized immutable `SeriesSnapshot` values. It
has no network, cache, event, settings, or filesystem dependency.

Algorithm per series:

1. Filter records to `timestamp <= as_of`.
2. Reassert order/uniqueness as a defensive boundary.
3. Select the last record and compute age against `as_of`.
4. If age exceeds the hard/configured ceiling, expose no records and return
   `stale`.
5. Otherwise retain the configured bounded history independently of the
   requesting consumer and project `fresh` or `cached` plus
   provenance/truncation metadata.
6. Evaluate typed requirements against that same context and return every
   unmet reason in stable order. Requirements never change context contents.

Live and replay callers use this exact algorithm. Tests pin normalized JSON
output and decisions for equal inputs.

## LC-09 — Runtime/proposal integration

### Engine cycle sequence

```text
run_cycle
  1. create cycle_id / reset ordinary per-cycle caches
  2. resolve active sub-accounts and union their BTC + altcoin symbols
  3. await derivatives_service.refresh_cycle(...) within its own deadline
  4. scan each sub-account using shared context lookups
  5. run proposal/risk gates
  6. monitor positions and record portfolio snapshot
  7. emit cycle completed
```

A service exception is caught before step 4 and converted into an operator
event; it does not enter the existing per-sub-account `CYCLE_ERRORED` path.

The proposal engine obtains context after its OHLCV fetch using the actual
decision boundary supplied by the final closed candle. It passes
`market_context=` as an optional keyword-only argument. Existing strategy
implementations remain callable unchanged during the plumbing slice by a
compatibility dispatch path until all code strategies adopt the widened base
signature; the Code Generation plan must choose one centralized compatibility
point, not per-strategy reflection scattered across callers.

The first Funding+OI proposal filter is a later consumer slice. Its mode is
`off` by default and `observe` before `enforce`; missing requirements produce
`gate_skipped_missing_market_context` and do not block proposals.

## LC-10/11 — Snapshot-v2 store and replay source

### Manifest contract

`manifest.json` contains only normalized provenance:

```text
schema_version: 2
generation_id: str
created_at: UTC datetime
source: "binance"
symbol: canonical symbol
timeframe: OHLCV timeframe
files:
  <filename>:
    sha256: lowercase hex
    byte_size: int
    row_count: int | null
```

The allowlist is exactly `ohlcv.csv`, `funding.csv`, `open_interest.csv`, and
`metadata.json`. Manifest generation uses canonical JSON ordering/encoding so
the same normalized inputs yield the same digest.

`metadata.json` schema v2 contains requested/actual range and granularity per
series, timestamps, point counts, funding interval, and OI retention flag.
Predicted funding is never serialized.

### Visibility and replay

- `CURRENT` contains only a validated generation id plus newline and is written
  atomically.
- The reader validates a conservative id pattern and resolves the path beneath
  `generations/`; path traversal/symlinks escaping the root are rejected.
- A gate/backtest result pins `generation_id`, not merely `CURRENT`, so a later
  refresh cannot change the identity of an earlier result.
- `SnapshotExchange`/replay source serves OHLCV and derivatives from the same
  committed generation and uses `MarketContextBuilder` per simulated bar.
- If schema v1 is loaded, OHLCV remains available and derivatives are explicit
  unavailable; a context-required robustness run returns
  `INSUFFICIENT_DATA`.
- No live fallback exists in a promotion-relevant snapshot run.

### Publication failure handling

Any fetch, page, validation, serialization, hash, staged-read, or pointer-write
failure aborts publication and leaves the prior `CURRENT` readable. Application
tests inject failure after each writer phase and assert the old generation is
still selected.

## LC-12 — Activity and Ops Diagnostics

Add enum values:

```text
DERIVATIVES_DATA_DEGRADED = "derivatives_data_degraded"
DERIVATIVES_DATA_RECOVERED = "derivatives_data_recovered"
```

Both share the allowlisted details specified by NDP-09. `error_code` is present
on degraded events and absent/cleared on recovered events. `cycle_id` is always
set for runtime refresh transitions.

Ops Diagnostics adds derived rows after the existing data-directory/activity
rows. It reads recent activity and folds the newest transition per
`(exchange, symbol, series)`. It does not instantiate the context service or
call Binance. Suggested status mapping:

| Latest health | Ops status | Next step |
|---|---|---|
| recovered/fresh | pass | Monitor derivatives data |
| cached within TTL | watch | Check Binance refresh and cache age |
| stale/unavailable/circuit open | stop | Check endpoint/rate limit; preserve OHLCV-only operation |
| unsupported interval | watch | Exclude symbol from funding consumer or design dynamic interval support |

## LC-13 — Configuration contract

Use one nested/bounded configuration model with environment mapping consistent
with existing `Settings` conventions:

| Field | Default | Validation / meaning |
|---|---:|---|
| `enabled` | `False` | No public derivatives client/calls when false |
| `max_symbols` | `20` | `1..20` for v1 |
| `max_concurrency` | `4` | `1..4` |
| `deadline_4_symbols_seconds` | `5.0` | positive, <= cycle interval |
| `deadline_20_symbols_seconds` | `15.0` | >= small deadline, <= cycle interval |
| `funding_max_age_seconds` | `32400` | hard maximum 9h |
| `oi_max_age_seconds` | `7200` | hard maximum 2h |
| `retry_count` | `2` | exactly approved maximum; configuration may reduce, not increase above 2 |
| `retry_base_seconds` | `0.25` | non-negative; jittered and deadline-bound |
| `funding_budget_5m` | `250` | may reduce, cannot exceed approved ceiling |
| `oi_history_budget_5m` | `500` | may reduce, cannot exceed approved ceiling |
| `funding_interval_hours` | `8` | v1 canonical constant; other venue value becomes unsupported |
| `oi_timeframe` | `1h` | v1 canonical granularity |

The later proposal-filter configuration is separate:

```text
funding_oi_filter_mode = off | observe | enforce   # default off
```

Configuration validators reject invalid envelopes at startup. They never
silently clamp an operator value upward/downward because an apparent safe
configuration could otherwise differ from what the operator believes is live.

## Code Generation slice handoff

The implementation remains split by the Functional Design sequence. Each slice
gets its own plan, targeted tests, session evidence, and review boundary.

### Slice 1 — Exchange/domain foundation

- Add domain types, typed errors, capability defaults, ccxt protocol methods,
  dedicated public Binance source, history pagination/contiguity/interval and
  retention handling.
- Primary tests: `tests/test_exchange_base.py`,
  `tests/test_exchange_binance.py`, new derivatives adapter tests.
- No runtime wiring or consumer behavior change.

### Slice 2 — Snapshot schema v2

- Add immutable generation writer/reader, manifest hashes, atomic `CURRENT`,
  v1 negotiation, and snapshot derivatives source.
- Primary tests: `tests/test_backtest_snapshot.py` and focused snapshot-v2
  failure-injection/replay tests.
- No live runtime network change.

### Slice 3 — Runtime context plumbing

- Add config, service/scheduler/cache/retry/circuit/budget, shared context
  builder, engine prefetch/injection, health events, and Ops projection.
- Primary tests: runtime service tests, `tests/test_runtime_engine.py`,
  activity/ops tests, strategy base/loader compatibility tests.
- Feature remains disabled by default.

### Slice 4 — Backtest and robustness integration

- Slice snapshot series per bar through the shared builder, pin generation id,
  and make context-required absence produce `INSUFFICIENT_DATA`.
- Primary tests: backtest snapshot/harness and robustness-gate suites.

### Slice 5 — Proposal-layer Funding+OI filter

- File a separate falsifiable hypothesis and threshold plan, implement
  `off/observe/enforce`, default off, and produce funnel telemetry.
- Activate `observe` only after snapshot evidence; `enforce` requires explicit
  evidence review. Funding-Extreme MR follows in a separate strategy slice.

## Verification matrix

| Components | Required tests/evidence |
|---|---|
| LC-01..03 | Pydantic invariants, empty-credential client config, mapping/error sanitization, actual-page pagination, grids/retention/interval |
| LC-04..07 | 4/20-symbol load, semaphore peak, deadline cancellation, dedupe, retry jitter, circuit transitions, TTL/partial cache |
| LC-08/11 | no-look-ahead slices, exact requirement outcomes, live/snapshot normalized parity, predicted funding absent in replay |
| LC-10 | v1 read, v2 round trip, every-phase rollback, CURRENT traversal, hash/count corruption, pinned generation replay |
| LC-12 | event allowlist/dedupe/recovery and Ops latest-state projection |
| LC-13 | defaults preserve existing behavior and reject bounds above v1 ceilings |

## Infrastructure and debt decision

Infrastructure Design is N/A for v1: all components live in the existing
process and filesystem, use public Binance endpoints, and add no service,
credential, volume, worker, or deployment-process topology.

No technical-debt item is created by this design. Dynamic funding intervals,
multi-process shared limiting, additional vendors, and filter/MR thresholds are
explicitly excluded future capabilities with safe v1 behavior, not unfinished
implementation hidden behind TODOs.

The unit cross-check remains deferred until Code Generation and Build/Test
provide implementation evidence.

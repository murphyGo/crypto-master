# NFR Requirements: Derivatives Market Context — v1

## Scope and locked inputs

This stage defines the non-functional contract for Binance USDⓈ-M perpetual
funding-rate and open-interest (OI) collection, runtime `MarketContext`
delivery, snapshot-v2 persistence, and deterministic replay. It applies to
FR-046 / US-025 and the `exchange-integration` unit, with bounded spillover to
`persistence-data-integrity`, `strategy-framework`,
`backtesting-validation`, and `proposal-runtime`.

The operator accepted every recommended answer in
`exchange-integration-nfr-requirements-plan.md` on 2026-07-18. Functional
semantics remain those already locked in the Functional Design: Binance-only
v1, optional `MarketContext`, snapshot schema v2, no look-ahead, explicit
missing data, and proposal-layer Funding+OI regime filter before a standalone
Funding-Extreme mean-reversion strategy.

## Current venue constraints verified for this stage

The NFR budgets are based on the Binance and ccxt primary documentation
reviewed on 2026-07-18:

- Binance `GET /fapi/v1/fundingRate` returns settled history, accepts at most
  1000 records per page, and shares a 500 requests / 5 minutes / IP limit with
  `GET /fapi/v1/fundingInfo`.
- Binance `GET /futures/data/openInterestHist` accepts 1h granularity, at most
  500 records per page, exposes only the latest one month, and publishes a
  1000 requests / 5 minutes / IP limit.
- Binance current OI (`GET /fapi/v1/openInterest`) has IP weight 1.
- ccxt exposes unified funding-history and OI-history methods and enables its
  built-in rate limiter by default. The application keeps it explicitly
  enabled and adds its own smaller concurrency and call budget.

These values are external operational inputs, not constants guaranteed by the
domain model. The implementation must keep endpoint limits configurable and
must re-verify the official venue documentation before raising capacity above
20 symbols or changing page size, concurrency, or refresh cadence.

## Measurable requirements

### DD-NFR-001 — Capacity envelope

- The implementation must pass deterministic load tests at the current four
  symbols and at a 20-symbol ceiling without changing code or timing policy.
- Expansion beyond 20 symbols requires a new load, latency, and official
  endpoint-rate-limit review before rollout.
- Per-symbol state must be isolated: one slow, unsupported, or invalid symbol
  cannot suppress healthy context for other symbols.

### DD-NFR-002 — Runtime latency budget

- Additional wall-clock time attributable to derivatives refresh must be p95
  <= 5 seconds for four symbols and p95 <= 15 seconds for 20 symbols, measured
  over at least 100 deterministic test cycles with latency-injecting fakes.
- Once the cycle-level budget is exhausted, unfinished derivatives work is
  cancelled or ignored for that cycle and the engine continues with eligible
  last-known-good or missing context. It must not delay the 300-second trading
  cadence indefinitely.

### DD-NFR-003 — Freshness and cache expiry

- A settled funding observation is eligible as last-known-good only while its
  age at decision `as_of` is <= 9 hours.
- An OI observation is eligible only while its age is <= 2 hours.
- Predicted funding is live/paper-only and eligible only within the engine
  cycle in which it was fetched (currently five minutes). It is never persisted
  as replay input or reused by a later cycle.
- Expired data is reported as unavailable; no consumer receives it as though
  it were fresh.

### DD-NFR-004 — Partial availability and consumer declaration

- `MarketContext` must carry explicit availability, age/freshness, and error
  state per series so healthy funding can survive an OI outage and vice versa.
- Every derivatives-aware consumer must declare the series and minimum history
  it requires.
- A strategy whose declared input is unavailable returns neutral. The
  proposal-layer regime filter skips and emits telemetry (fail-open). A
  promotion-relevant robustness gate returns `INSUFFICIENT_DATA`; it cannot
  convert absence into a pass.
- Zero, forward-fill, or unchanged-value substitution for a missing series is
  prohibited.

### DD-NFR-005 — Retry and circuit behavior

- Only transient network errors, HTTP 429, and HTTP 5xx failures are retryable.
- A refresh gets one initial attempt plus at most two retries using exponential
  delay with full jitter, bounded by DD-NFR-002.
- Unsupported capability, schema/validation, authentication, and contiguity
  errors are not retried.
- After three consecutive failed refreshes for the same `(exchange, symbol,
  series)`, the collector skips remote refresh for one full engine cycle, uses
  eligible cache if present, and makes a probe on the following cycle.
- A successful probe closes the circuit, clears the consecutive-failure count,
  and emits one recovery event.

### DD-NFR-006 — Rate-limit safety and request deduplication

- ccxt `enableRateLimit` remains true for the lifetime of the reused Binance
  exchange instance.
- At most four Binance derivatives calls may be in flight concurrently per
  process, enforced by a per-exchange semaphore.
- Identical `(exchange, endpoint, symbol, timeframe, since, until)` refreshes
  within a cycle share one in-flight/result future.
- The derivatives collector must enforce a configurable rolling request budget
  no greater than 50% of the lowest applicable published endpoint allowance.
  Under the verified v1 endpoints, funding-history calls are therefore capped
  at 250 per 5 minutes per IP and OI-history calls at 500 per 5 minutes per IP;
  tighter venue headers or configuration always win.
- Budget exhaustion degrades through DD-NFR-004; it never triggers an
  unbounded queue or aggressive retry loop.

### DD-NFR-007 — Runtime availability and recovery

- A derivatives endpoint outage must not stop OHLCV collection, strategy
  evaluation, risk controls, or execution paths that do not require
  derivatives context.
- Recovery is automatic on later cycles and requires no process restart.
- No secondary derivatives vendor or separate DR service is required in v1.
  The recovery objective is restoration on the first successful scheduled
  probe, not cross-vendor failover.

### DD-NFR-008 — Snapshot integrity, retention, and compatibility

- Snapshot schema v2 must include the entire requested settled-funding range
  available from Binance and the contiguous OI suffix Binance retains.
- OI retention truncation must record requested start, actual first timestamp,
  last timestamp, granularity, and
  `truncated_at_venue_retention=true`. It must never be hidden by interpolation.
- Any page failure, required-grid gap, schema validation failure, or write
  failure aborts the candidate snapshot and leaves the last known-good
  snapshot readable and unchanged.
- Snapshot publication is all-or-nothing at the snapshot-generation level;
  readers must never observe metadata v2 paired with a missing or partially
  written derivatives file.
- Schema v1 remains readable and maps to unavailable derivatives context.
  A required-series gap or corruption fails replay loudly; optional consumers
  receive missing context according to DD-NFR-004.

### DD-NFR-009 — Determinism and no look-ahead

- Every context element and derived feature used at decision time must have a
  timestamp <= `MarketContext.as_of`.
- Promotion-relevant tests consume only immutable snapshot-v2 inputs and
  record the snapshot identity. Network access is prohibited in those runs.
- Replaying the same code, configuration, snapshot identity, and random seed
  must produce byte-equivalent normalized context and identical gate/strategy
  decisions.
- Predicted funding must be `None` in replay.

### DD-NFR-010 — Observability and operator usability

- Degradation and recovery produce structured activity events containing at
  least exchange, symbol, series, event time, data timestamp/age, cache status,
  attempt count, circuit state, and a stable error code. Raw response payloads
  are excluded.
- Identical degradation is deduplicated to one activity event per
  `(symbol, series, engine cycle)` while counters may still increment.
- Existing Ops Diagnostics summarizes the latest funding/OI state; no new
  dashboard page is required.
- Proposal filter skips must use the stable
  `gate_skipped_missing_market_context` reason so funnel impact is measurable.

### DD-NFR-011 — Public-data security boundary

- All v1 derivatives reads must succeed without exchange credentials and must
  use public endpoints only.
- Logs, activity events, exceptions, and snapshots must never serialize API
  keys, signatures, signed-query material, secret-bearing URLs, or full raw
  exchange responses.
- Persistence is limited to normalized public fields defined by the domain
  model and provenance/availability metadata. No new personal-data or
  compliance scope is introduced.

### DD-NFR-012 — Maintainability and test isolation

- Implementation uses the existing ccxt, asyncio, Pydantic, CSV/JSON, logging,
  and atomic-write stack; it adds no production dependency.
- Network-free tests use deterministic fake ccxt clients and fixtures for
  paging, short pages, duplicate timestamps, gaps, venue retention, retries,
  rate exhaustion, circuit transitions, stale cache, partial context,
  cancellation, and snapshot rollback.
- A live Binance smoke test may be documented and opt-in, but is never a
  normal CI prerequisite and never requires credentials.
- Endpoint limits, cache ages, concurrency, and cycle budgets have named
  configuration with conservative validated bounds rather than scattered
  literals.

## Acceptance and verification matrix

| Requirement | Required evidence before unit completion |
|---|---|
| DD-NFR-001/002 | 4- and 20-symbol fake-load tests with recorded p50/p95/max added latency and no leaked tasks |
| DD-NFR-003/004 | Boundary tests at 9h/2h/cycle TTL plus partial-funding/OI and expired-cache cases |
| DD-NFR-005/006 | Fake clock/random tests for retry count, jitter bounds, circuit state, dedupe, semaphore peak, and rolling budgets |
| DD-NFR-007 | End-to-end engine test proving OHLCV-only cycle completion during derivatives outage and later automatic recovery |
| DD-NFR-008/009 | Snapshot-v2 round trip, v1 read, staged-write rollback, retention metadata, gap failure, and identical replay tests |
| DD-NFR-010/011 | Structured-event schema/dedup tests plus secret/raw-response negative assertions |
| DD-NFR-012 | Dependency diff review, offline targeted suite, formatting/lint, and full `uv run pytest` when practical |

## Explicit v1 limits and design follow-ups

- Binance may advertise symbol-specific funding interval adjustments. The v1
  domain model uses a canonical settled 8h grid. NFR Design must choose a
  typed unsupported/availability result for a non-8h interval rather than
  silently applying 8h contiguity to incompatible data. Generalized dynamic
  interval support is outside this bounded v1 scope.
- Thresholds for a Funding+OI regime filter and the Funding-Extreme MR strategy
  are not NFR constants. Each consumer requires a predeclared, falsifiable
  hypothesis and snapshot-v2 evidence before it may veto proposals or trade.
- This stage creates no new technical-debt item: the venue-retention and
  funding-interval constraints are explicit v1 scope limits with required
  safe behavior, not untracked TODOs.

## Traceability

- Canonical requirement/story: FR-046 / US-025.
- Existing NFRs/constraints: NFR-006, NFR-009, NFR-011, CON-002.
- Functional rules: R1-R7 in
  `aidlc-docs/construction/exchange-integration/functional-design/business-rules.md`.
- Cross-check remains deferred until the complete derivatives-data unit has
  implementation and verification evidence.

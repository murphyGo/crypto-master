# Tech Stack Decisions: Derivatives Market Context — v1

## Decision status

These decisions implement the operator-approved NFR choices for FR-046 /
US-025. They constrain the upcoming NFR Design; they do not authorize the
proposal filter or Funding-Extreme MR strategy to veto or trade without their
own hypothesis and replay evidence.

## TS-01 — Keep ccxt as the venue transport boundary

**Decision:** Reuse the long-lived Binance ccxt client with
`enableRateLimit=True`. Prefer ccxt unified `fetchFundingRateHistory`,
`fetchOpenInterest`, and `fetchOpenInterestHistory` capabilities behind the
repository's `BaseExchange` contract. A thin Binance-specific adapter may read
exchange-specific pagination/retention metadata, but raw ccxt payloads cannot
escape the adapter.

**Why:** ccxt is already a production dependency and exposes the required
contract-market methods. Keeping normalization at the exchange boundary avoids
leaking Binance field names into strategies, snapshots, and gates.

**Rejected:** Direct HTTP client calls as the primary path; a second market-data
SDK; credentialed private endpoints for public data.

## TS-02 — Use asyncio primitives for concurrency, timeout, and deduplication

**Decision:** Use one `asyncio.Semaphore(4)` per Binance exchange instance, an
engine-cycle deadline, and an in-memory map of canonical request keys to shared
tasks/results. Reuse the exchange instance rather than constructing a client
per call.

**Why:** These primitives satisfy the 4/20-symbol envelope without a new
dependency and preserve ccxt's rate-limiter state. Cycle-scoped deduplication
prevents strategy count from multiplying venue traffic.

**Rejected:** Unbounded `gather`; one client per request; Redis/distributed
locks; production task-queue infrastructure.

## TS-03 — Implement a small bounded retry/circuit policy locally

**Decision:** Add a typed transient-error classifier, at most two exponential
full-jitter retries, and per-`(exchange, symbol, series)` consecutive-failure /
one-cycle-open circuit state. Inject clock, sleep, and random functions in
tests. All waits are subordinate to the cycle deadline.

**Why:** The state machine is intentionally small and its exact behavior is a
trading-availability contract. Local typed code is easier to audit and test
deterministically than adding a general retry framework.

**Rejected:** Retrying every exception; five-or-more attempts; permanent-open
circuits; a new retry/circuit-breaker dependency.

## TS-04 — Add an application request-budget guard above ccxt

**Decision:** Keep endpoint metadata for request-window allowance and cost,
apply a rolling-window budget capped at 50% of the lowest relevant published
allowance, and honor any tighter observed venue header/configuration. Funding
history and OI history use separate endpoint budgets, while the exchange-level
semaphore remains shared.

**Why:** ccxt throttles request pacing, but the application also needs a
predictable share ceiling so derivatives refresh cannot starve existing
OHLCV/trading traffic or overrun a venue-specific window.

**Rejected:** Consuming the full published allowance; relying on concurrency
alone; hard-coding one generic cost for all Binance endpoints.

## TS-05 — Model normalized immutable data with existing Pydantic/domain types

**Decision:** Implement normalized `FundingRate`, `OpenInterestPoint`, series
availability metadata, and `MarketContext` as validated immutable domain
models consistent with existing repository conventions. Decimal values and
UTC-aware timestamps cross the exchange boundary; consumers never receive raw
strings or unbounded `info` dictionaries.

**Why:** Validation at the trust boundary makes timestamp, sign, freshness,
and no-look-ahead invariants explicit and serializable.

**Rejected:** Passing ccxt dictionaries into strategies; pandas DataFrames as
the runtime domain contract; float-only financial values.

## TS-06 — Use process-local last-known-good state only

**Decision:** Store latest validated series and failure/circuit metadata in the
runtime process, keyed by exchange/symbol/series. Apply the approved funding
9h, OI 2h, and predicted-funding one-cycle TTLs when constructing context.
Snapshots, not the cache, are the durable replay source.

**Why:** The engine is a single-process v1 runtime. A distributed cache would
add operational state without improving deterministic replay or outage safety.

**Rejected:** Redis; database-backed cache; reusing expired observations;
persisting predicted funding as replay truth.

## TS-07 — Publish snapshot v2 through a staged generation commit

**Decision:** Continue using CSV for normalized series and JSON for metadata,
but write every candidate generation into a sibling staging directory. Validate
all pages, grids, files, checksums/manifest metadata, and schema before a final
filesystem replacement/commit makes the generation visible. Readers select
only a committed generation. Preserve schema-v1 negotiation.

**Why:** Per-file atomic writes cannot by themselves guarantee a consistent
multi-file generation. Staging plus one visibility/commit boundary satisfies
the last-known-good and all-or-nothing NFR without changing data formats.

**Rejected:** Overwriting live files sequentially; accepting partial
derivatives files; interpolating venue-retention gaps; introducing a database
solely for snapshot v2.

**NFR Design obligation:** Select the exact repository-compatible directory
replacement or manifest-pointer protocol after inspecting current snapshot
writer/reader paths and platform semantics.

## TS-08 — Extend existing activity log and Ops Diagnostics

**Decision:** Emit typed degraded/recovered events into the existing activity
event pipeline and add the latest per-series state to the existing Ops
Diagnostics aggregation. Reuse stable gate-reason conventions for filter
skips. Do not add a dashboard route/page.

**Why:** Operators need durable, deduplicated health state in the surface they
already use; raw logs alone are insufficient, while a dedicated page is excess
scope for v1.

**Rejected:** Logs-only visibility; raw-payload logging; a new derivatives
health service or dashboard.

## TS-09 — Keep CI deterministic and offline

**Decision:** Build fake ccxt capabilities and fixed fixtures that can emulate
short pages, duplicate/out-of-order records, gaps, 429/5xx/network faults,
retention truncation, delayed responses, and cancellation. Use fake clock and
random sources for exact retry/circuit assertions. Document an opt-in public
Binance smoke test separately.

**Why:** Promotion evidence must be reproducible and cannot depend on current
network/venue state. The optional smoke test detects adapter drift without
making CI flaky or requiring credentials.

**Rejected:** Mandatory live Binance CI calls; time-based sleeps in unit tests;
fixtures containing full raw venue responses or credentials.

## Technology fit summary

| Concern | Selected v1 mechanism | Production dependency added |
|---|---|---|
| Venue access/normalization | Existing ccxt + `BaseExchange` adapter | No |
| Concurrency/deadline | asyncio semaphore/tasks/timeouts | No |
| Retry/circuit/budget | Small typed repository modules | No |
| Domain validation | Existing Pydantic + Decimal/UTC types | No |
| Runtime cache | Process-local validated LKG | No |
| Durable replay | CSV/JSON snapshot v2 + staged commit | No |
| Operator health | Existing activity log + Ops Diagnostics | No |
| Test isolation | Fake ccxt, fixtures, fake clock/random | No |

## Primary-document verification record (2026-07-18)

- Binance USDⓈ-M Market Data REST API: funding history, current OI, and OI
  statistics sections.
- ccxt Manual: rate-limit lifecycle, unified funding-rate history, and unified
  open-interest history sections.

Official values must be rechecked during implementation if the installed ccxt
version, Binance endpoint catalog, page sizes, or published limits differ from
this record.

# NFR Design Plan: exchange-integration — Derivatives Market Context

## Development Target

- **Unit:** `exchange-integration`
- **Stage:** NFR Design
- **Task:** Convert the approved funding/OI NFRs into concrete in-process
  resilience, scheduling, caching, snapshot-publication, security, and
  observability patterns.
- **Related Requirements:** FR-016 - FR-020, FR-046, NFR-006, NFR-009,
  NFR-011, CON-002.
- **Related Stories:** US-008, US-014, US-025.
- **Secondary Units:** `strategy-framework`, `backtesting-validation`,
  `proposal-runtime`, `persistence-data-integrity`, `notifications-ops`.
- **Related Legacy / Debt:** Legacy exchange Phases 2 and 13.3; Phase 25
  snapshot format; resolved DEBT-080 pagination/contiguity incident. No active
  technical debt is mapped to the unit.
- **Prerequisite Artifacts:**
  `aidlc-docs/construction/exchange-integration/nfr-requirements/`.
- **Outputs:**
  - `aidlc-docs/construction/exchange-integration/nfr-design/nfr-design-patterns.md`
  - `aidlc-docs/construction/exchange-integration/nfr-design/logical-components.md`

## Brownfield evidence informing the questions

- `TradingEngine.run_cycle()` currently scans sub-accounts sequentially, and
  multiple sub-accounts may bind distinct exchange instances while requesting
  the same public symbol data.
- `BinanceExchange` uses one long-lived async ccxt client with
  `enableRateLimit=True`, but the client can also hold trading credentials.
- `save_snapshot()` atomically writes each file independently; it does not
  provide a multi-file generation commit boundary.
- Runtime activity uses a stable `ActivityEventType` enum plus structured
  JSONL details, and Ops Diagnostics reads the existing activity surface.
- The approved NFRs require partial per-series context, a 4/20-symbol latency
  envelope, process-local last-known-good state, one-cycle circuit recovery,
  public credential-free reads, and deterministic snapshot-v2 replay.

## Category applicability

- **Resilience Patterns:** Applicable because endpoint failure, stale cache,
  retry/circuit transitions, partial context, and snapshot rollback affect
  trading availability and replay integrity.
- **Scalability Patterns:** Applicable because public data must be deduplicated
  across sub-accounts and validated at 4 and 20 symbols under IP-scoped venue
  limits.
- **Performance Patterns:** Applicable because derivatives refresh has a hard
  p95/cycle budget and must not serialize the existing scan loop.
- **Security Patterns:** Applicable because existing trading clients may carry
  credentials while FR-046 is explicitly public-only and forbids secret/raw
  payload persistence.
- **Logical Components:** Applicable because cache, scheduler, request budget,
  circuit state, snapshot commit protocol, consumer requirements, and health
  projection need explicit ownership boundaries.

## NFR Design Clarification Questions

Replying **"all recommended"** accepts option (a) for every question.

### Q1 — Public context service ownership and sharing

Where should public funding/OI refresh, cache, and deduplication live when
several sub-accounts scan the same symbols through different trading clients?

- **(a) Recommended:** one engine-scoped `DerivativesContextService` per public
  venue, shared across all sub-accounts and strategies; exchange adapters only
  fetch/normalize, while the service owns cache, scheduling, dedupe, budgets,
  and context slicing.
- (b) one service/cache per credential-bound `BaseExchange` instance.
- (c) each strategy fetches and caches its own derivatives data.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q2 — Partial `MarketContext` and consumer requirements shape

How should a consumer distinguish healthy, stale, unavailable, unsupported,
and retention-truncated series without breaking the already approved raw-list
contract?

- **(a) Recommended:** retain `funding_rates` and `open_interest` raw lists and
  add immutable parallel `SeriesAvailability` records for each; consumers
  declare a typed `MarketContextRequirements` value (minimum points, required
  series, maximum age). A supported venue returns a context even when one
  series is unavailable; `None` remains for an unsupported/unwired provider.
- (b) use only empty lists plus log messages; consumers infer the reason.
- (c) make funding and OI all-or-nothing and return `None` if either fails.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q3 — Circuit-breaker state machine and isolation

What exact state machine should implement the approved “three failures, skip
one cycle, then probe” policy?

- **(a) Recommended:** isolated state per `(venue, symbol, series)` with
  `CLOSED -> OPEN_FOR_NEXT_CYCLE -> HALF_OPEN`; allow exactly one half-open
  probe, close and emit recovery on success, or reopen for one cycle on
  transient failure. Validation/unsupported failures update availability but
  do not increment the transient circuit counter.
- (b) one venue-wide circuit where any symbol failure pauses all derivatives
  refreshes.
- (c) track only a failure count and retry normally every cycle.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q4 — Cycle scheduling, deadline, and cancellation

Where should the derivatives refresh batch run relative to the current
per-sub-account scan loop?

- **(a) Recommended:** at cycle start, compute the union of public symbols for
  all active sub-accounts, start one shared refresh batch under semaphore 4,
  and enforce one monotonic cycle deadline (5s at <=4 symbols, 15s at <=20).
  Build per-symbol results from completed tasks, cancel/ignore unfinished
  tasks, then let every scan consume the same cached snapshot sliced to its
  decision `as_of`.
- (b) lazily refresh each symbol when the first strategy asks for context.
- (c) synchronously complete all funding/OI calls for each sub-account before
  scanning the next one, even beyond the deadline.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q5 — Request-budget topology and multi-process boundary

Binance allowances are IP-scoped, while the approved implementation budget is
process-local. What deployment assumption should v1 enforce?

- **(a) Recommended:** one active derivatives collector process per deployment;
  use monotonic rolling-window counters per endpoint group, honor tighter
  `Retry-After`/venue signals, and cap at the approved 50% allowance. Starting
  multiple collectors on one IP requires a new design with a shared limiter.
- (b) allow any number of processes, each independently consuming 50%.
- (c) add Redis or another distributed rate limiter in v1.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q6 — Snapshot-v2 multi-file commit protocol

How should schema v2 guarantee readers never observe a mixed generation while
preserving schema-v1 compatibility?

- **(a) Recommended:** write and validate immutable generation directories
  containing OHLCV, funding, OI, metadata, and a checksum manifest; atomically
  replace a small `CURRENT` pointer only after validation. A v2 reader resolves
  only `CURRENT`; directories without it follow the existing schema-v1 layout.
- (b) overwrite the canonical CSV files sequentially and write metadata last.
- (c) replace the non-empty canonical directory directly with a staged
  directory and rely on platform-specific directory-rename behavior.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q7 — Non-canonical Binance funding intervals

Binance can publish symbol-specific funding interval adjustments, while the v1
domain contract uses an 8h settled grid. How should v1 behave?

- **(a) Recommended:** detect interval adjustments from cached funding-info
  capability data and observed history spacing; mark funding
  `unsupported_interval` for that symbol, preserve healthy OI, emit one
  degradation transition, and never resample. Dynamic interval support remains
  a separately designed extension.
- (b) coerce every interval onto an 8h grid by dropping or aggregating records.
- (c) ignore the adjustment and validate all history as if it were 8h.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q8 — Degradation/recovery event ownership

Which component should emit and deduplicate operator health events?

- **(a) Recommended:** the shared context service owns two stable activity
  transitions, `DERIVATIVES_DATA_DEGRADED` and
  `DERIVATIVES_DATA_RECOVERED`, with an allowlisted detail schema. It emits at
  most once per `(symbol, series, cycle)` and only emits recovery after a prior
  degraded state; consumers emit only their own gate/neutral decision reasons.
- (b) every strategy and proposal gate emits its own endpoint errors.
- (c) reuse only generic `SCAN_ERRORED` events without series state.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q9 — Credential-free transport and response sanitization

How should the public-only security boundary be enforced when existing Binance
trading clients may contain API keys?

- **(a) Recommended:** the shared service owns a dedicated long-lived public
  `binanceusdm` ccxt client created without `apiKey`/`secret`; raw responses are
  normalized inside the adapter and discarded. Exceptions cross the boundary
  only as typed, allowlisted code/class/message fields with URL/query redaction;
  snapshot checksums cover normalized files only.
- (b) reuse whichever credential-bound trading client the first sub-account
  provides.
- (c) archive complete raw responses in debug mode for incident analysis.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q10 — Safe rollout and configuration boundary

What default activation policy should preserve existing runtime behavior while
the wiring and first consumer accumulate evidence?

- **(a) Recommended:** add a bounded `DerivativesDataConfig`; collection is
  disabled by default for existing deployments and enabled explicitly per
  environment. The proposal filter has a separate `off | observe | enforce`
  mode defaulting to `off`; code generation first proves collection/replay,
  then the consumer slice starts in `observe` before any enforcement.
- (b) enable collection and hard proposal veto by default on upgrade.
- (c) expose no configuration and always collect, leaving behavior to each
  consumer.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

## Plan Steps

- [x] Confirm approved NFR Requirements and execution-plan applicability.
- [x] Inspect current engine, ccxt client, snapshot writer, activity event, and
  configuration boundaries.
- [x] Evaluate all mandatory NFR Design question categories and record explicit
  applicability.
- [x] Generate targeted questions with recommended brownfield-safe defaults.
- [x] Collect Q1-Q10 answers and reject vague/ambiguous responses.
- [x] Generate `nfr-design-patterns.md` covering bulkhead, deadline,
  stale-while-revalidate/LKG, circuit, rate budget, snapshot commit, and
  deterministic replay patterns.
- [x] Generate `logical-components.md` with responsibilities, dependency
  direction, state keys, lifecycle, sequence flows, configuration, events, and
  code-generation/test handoff.
- [x] Verify traceability and formatting with `rg` and `git diff --check`.
- [x] Present NFR Design artifacts for explicit operator approval.
- [x] After approval, record `nfr-design/audit.md`, update AI-DLC state and the
  parent functional-design plan, then hand off to Code Generation. Infrastructure
  Design remains N/A because v1 adds no external service, credential topology,
  or deployment process.

## Completion Checklist

- [x] All Q1-Q10 answers are explicit and internally consistent.
- [x] Resilience, scalability, performance, security, and logical-component
  patterns satisfy DD-NFR-001..012.
- [x] Brownfield runtime behavior and public-only security defaults remain
  conservative.
- [x] NFR Design artifacts and approval audit are complete.
- [x] Documentation/session log records decisions and checks.
- [x] No application code changes occur during this design stage.
- [x] Technical debt is added only for a real deferred gap.
- [x] Cross-check remains deferred until implementation evidence exists.
- [x] AI-DLC state advances only after explicit NFR Design approval.

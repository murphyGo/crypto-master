# NFR Requirements Plan: exchange-integration — Derivatives Data Wiring

## Target

- **Unit**: `exchange-integration`
- **Stage**: NFR Requirements
- **Task**: Define the scalability, performance, availability, reliability,
  security, maintainability, and operator-usability requirements for Binance
  perpetual funding-rate/open-interest ingestion and snapshot replay.
- **Related Requirements**: FR-016 - FR-020, FR-046, NFR-006, NFR-009,
  NFR-011, CON-002.
- **Related Stories**: US-008, US-014, US-025.
- **Secondary Units**: `strategy-framework`, `backtesting-validation`,
  `proposal-runtime`, `persistence-data-integrity`.
- **Related Legacy / Debt**: Legacy exchange Phases 2 and 13.3; Phase 25
  snapshot reproducibility; resolved DEBT-080 pagination/contiguity incident.
- **Functional Design**:
  `aidlc-docs/construction/exchange-integration/functional-design/`.
- **Outputs**:
  - `aidlc-docs/construction/exchange-integration/nfr-requirements/nfr-requirements.md`
  - `aidlc-docs/construction/exchange-integration/nfr-requirements/tech-stack-decisions.md`

## Existing Baseline

- Runtime default: one BTC symbol plus three altcoin symbols, one cycle every
  300 seconds (`src/config.py`, `src/runtime/engine.py`).
- Existing ccxt clients use `enableRateLimit=True`; there is no derivatives
  request budget, application semaphore, derivatives cache, or circuit breaker.
- Functional decisions are already locked: Binance-only v1, optional
  `MarketContext`, snapshot schema v2, proposal regime filter first.
- Functional invariants remain non-negotiable: no look-ahead, actual-record
  pagination, loud gap detection, explicit venue-retention truncation,
  fail-open proposal filter, and non-vacuous robustness-gate outcomes.

## NFR Clarification Questions

All questions require an unambiguous answer. Replying **"all recommended"**
accepts option (a) for every question.

### Q1 — Scalability envelope

What symbol-count envelope must v1 satisfy without reconfiguration or material
cycle-latency degradation?

- **(a) Recommended**: validate the current 4-symbol runtime and a 20-symbol
  capacity ceiling; expanding beyond 20 requires a fresh load/rate-limit review.
- (b) Validate up to 50 symbols in v1.
- (c) Support only the current 4 symbols with no declared growth headroom.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q2 — Performance budget

How much wall-clock latency may derivatives refresh add to a normal 300-second
runtime cycle before the engine stops waiting and degrades to cached/missing
context?

- **(a) Recommended**: p95 added latency <= 5 seconds at 4 symbols and <= 15
  seconds at 20 symbols; exhaust the budget by failing open for that cycle.
- (b) p95 <= 15 seconds at 4 symbols and <= 45 seconds at 20 symbols.
- (c) No explicit budget; wait for every request/retry to finish.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q3 — Freshness and last-known-good cache

May runtime consumers use cached derivatives observations during a temporary
fetch failure, and when must cached data become unavailable?

- **(a) Recommended**: use last-known-good settled funding up to 9 hours old,
  OI up to 2 hours old, and predicted funding only within the current
  5-minute cycle; older data is unavailable and never silently reused.
- (b) Any refresh failure makes the affected series unavailable immediately.
- (c) Allow a longer degraded window: funding 24 hours, OI 6 hours, predicted
  funding 30 minutes.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q4 — Partial-outage semantics

If funding is available while OI is unavailable (or vice versa), should the
runtime preserve the healthy series?

- **(a) Recommended**: return a partial `MarketContext` with explicit
  per-series availability/freshness metadata; each consumer declares which
  series it requires and skips/returns neutral when requirements are unmet.
- (b) Treat the context as all-or-nothing; either missing series makes the
  entire `MarketContext` unavailable.
- (c) Substitute zero/unchanged values for the missing series.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q5 — Retry, backoff, and circuit breaking

What recovery policy should apply to transient network/rate-limit failures?

- **(a) Recommended**: retry only transient network/429/5xx failures, at most
  two retries after the first attempt with exponential full jitter; after
  three consecutive refresh failures for a `(symbol, series)`, skip remote
  refresh for one engine cycle and probe again next cycle. Do not retry typed
  unsupported, validation, authentication, or contiguity failures.
- (b) Rely only on ccxt rate limiting; no application retries or circuit state.
- (c) Retry up to five times and keep trying every cycle without a circuit.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q6 — Rate-limit and concurrency posture

How conservative should the application be relative to Binance's published
public endpoint allowances?

- **(a) Recommended**: retain `ccxt enableRateLimit`, add a per-exchange
  application semaphore capped at 4 concurrent derivatives calls, de-duplicate
  identical refreshes, and configure the derivatives budget at no more than
  50% of the lowest applicable published allowance after verifying official
  endpoint weights.
- (b) Use the full published allowance with concurrency 10.
- (c) Keep only `ccxt enableRateLimit` and add no explicit application budget.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q7 — Availability, recovery, and snapshot safety

What must remain available when Binance derivatives endpoints are down?

- **(a) Recommended**: the trading cycle continues with OHLCV-only behavior;
  recovery is automatic on a later cycle; snapshot refresh is atomic and must
  retain the last known-good snapshot if any funding/OI page, validation, or
  write fails. No secondary vendor or separate disaster-recovery service in v1.
- (b) Fail the whole runtime cycle so missing derivatives data cannot go
  unnoticed.
- (c) Add a secondary external derivatives vendor in v1.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q8 — Observability and operator usability

What operator surface is required for degraded and recovered derivatives data?

- **(a) Recommended**: structured activity-log degraded/recovered events with
  symbol, series, data age, cache status, and stable error code; summarize the
  latest state in the existing Ops Diagnostics surface; no new dashboard page.
  De-duplicate repeated identical degradation to once per symbol/series/cycle.
- (b) Application logs only; no durable activity event or dashboard summary.
- (c) Build a dedicated derivatives-health dashboard page in v1.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q9 — Security and data-handling boundary

What security boundary should v1 enforce for public derivatives data?

- **(a) Recommended**: derivatives reads must work without credentials and
  never serialize API keys, signed query material, full raw responses, or
  secret-bearing URLs into logs/snapshots; store only normalized public market
  fields. No new personal-data or compliance scope.
- (b) Reuse configured exchange credentials for all calls and permit debug raw
  payload logging.
- (c) Add encrypted raw-response archival for audit.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q10 — Tech stack and maintainability

May this feature add production dependencies or integration-test network
requirements?

- **(a) Recommended**: use existing ccxt, asyncio, Pydantic, CSV/JSON snapshot,
  and atomic-write utilities; add no production dependency. CI tests use
  deterministic fake ccxt clients and fixtures; an opt-in live Binance smoke
  test is documented but never required in the normal test suite.
- (b) Add a cache/retry library if it reduces custom code; CI remains offline.
- (c) Require live Binance integration tests in CI.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

### Q11 — Snapshot retention and deterministic replay

What is the persistence contract when venue retention cannot cover the full
requested OI period?

- **(a) Recommended**: store the full requested settled-funding range and the
  contiguous OI suffix Binance actually retains, with explicit truncation
  metadata; schema-v2 writes are atomic, schema-v1 remains readable, and a
  required-series gap/corruption fails the replay rather than interpolating.
- (b) Interpolate missing OI records to create a full requested range.
- (c) Reject every snapshot whose OI history does not cover the full OHLCV
  period, even when venue retention makes that impossible.

[Answer]: **(a) Recommended — confirmed by operator 2026-07-18.**

## Plan Steps

- [x] Confirm Functional Design prerequisites and execution-plan applicability.
- [x] Analyze current runtime/exchange defaults and all NFR categories.
- [x] Generate context-specific questions with recommended bounded defaults.
- [x] Collect Q1-Q11 answers and reject vague/ambiguous responses.
- [x] Verify selected rate-limit assumptions and endpoint retention against
  current official Binance/ccxt primary documentation.
- [x] Generate `nfr-requirements.md` with measurable acceptance criteria.
- [x] Generate `tech-stack-decisions.md` with chosen technologies and rejected
  alternatives.
- [x] Verify traceability and formatting:
  `rg -n "FR-046|US-025" aidlc-docs/construction/exchange-integration/nfr-requirements aidlc-docs/inception docs/requirements.md`;
  `git diff --check`.
- [x] Present the NFR artifacts for explicit operator approval.
- [x] After approval, record the response/timestamp in
  `aidlc-docs/construction/exchange-integration/nfr-requirements/audit.md`,
  mark the NFR Requirements stage complete in `aidlc-docs/aidlc-state.md`, and
  update the parent functional-design plan.

## Completion Checklist

- [x] All answers are explicit and internally consistent.
- [x] Scalability, performance, availability, reliability, security,
  maintainability, and usability requirements are measurable.
- [x] Tech-stack choices preserve brownfield compatibility and public-only v1.
- [x] NFR artifacts are written and reviewed.
- [x] Documentation/session log updated; no untracked TODO remains.
- [x] Tests/checks recorded; any skipped check has a reason.
- [x] Technical debt added only for a real deferred gap.
- [x] Unit cross-check deferred until the full derivatives-data unit completes.
- [x] AI-DLC state updated after explicit NFR Requirements approval.

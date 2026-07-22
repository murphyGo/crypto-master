# Code Generation Plan: exchange-integration

## Migration Status

Legacy Phase work is migrated as brownfield-complete. This plan is not a queue
of unfinished historical tasks.

## Source Legacy Components

| Component | Phase | Secondary Unit |
|-----------|-------|----------------|
| Configuration Management | 1 | `notifications-ops` |
| Exchange Abstraction | 2 | |
| Binance Integration | 2 | |
| Bybit Integration | 2 | |
| Exchange Testnet Support | 4 | `trading-core` |
| Live Trading | 4 | `trading-core` |
| Live Trading Wiring | 10 | `trading-core` |
| OHLCV Cache for Multi-Technique Scan | 11 | `proposal-runtime` |
| BaseExchange.get_ohlcv `since` Parameter | 13 | `backtesting-validation` |
| Multi-Credential Live Mode | 19 | `sub-account-capital-segmentation` |
| UTC-Aware Timestamp Helper + Adapter Migration | 21 | `persistence-data-integrity` |

## Completed Code Generation Steps

- [x] Implement exchange abstraction and shared market/order models.
- [x] Implement Binance and Bybit adapters with OHLCV, ticker, balance, and order interfaces.
- [x] Add testnet-aware exchange configuration and tests.
- [x] Wire exchange behavior into live trading and runtime paths.
- [x] Add OHLCV cache and `since` parameter support for scan/backtest flows.
- [x] Preserve multi-credential live-mode and timestamp adapter behavior.

## Evidence

- Requirements: FR-016, FR-017, FR-018, FR-019, FR-020, NFR-009, NFR-011.
- Primary paths: `src/exchange/`, `src/config.py`, `tests/test_exchange_*`.
- Cross-checks: `docs/cross-checks/phase2-exchange-integration.md`, phase 10, phase 13, phase 19 reports.
- Session logs: related Phase 2, 4, 10, 11, 13, 19, and 21 entries under `docs/sessions/`.

## Future Work

Add new unchecked steps here only for future exchange integration changes.

## Active Future Work: Derivatives Data Slice 1

## Plan authority

This document is the single source of truth for the first bounded Code
Generation task in the FR-046 / US-025 derivatives-data sequence. Source code
must remain in the workspace root. Only implementation summaries belong under
`aidlc-docs/construction/exchange-integration/code/`.

The wider sequence remains:

1. **Current plan:** exchange/domain foundation.
2. Snapshot schema v2 (`persistence-data-integrity` spillover).
3. Runtime `DerivativesContextService` and strategy plumbing.
4. Snapshot-only backtest/robustness integration.
5. Separately designed proposal Funding+OI filter, then Funding-Extreme MR.

This plan implements item 1 only so each slice can be reviewed and verified
without mixing exchange trust-boundary code with persistence/runtime/strategy
behavior.

## Unit generation context

- **Unit:** `exchange-integration`
- **Stage:** Code Generation — Part 1 planning / Slice 1 generation
- **Task:** Add normalized Funding/OI domain contracts and Binance public
  derivatives adapter methods with safe pagination, interval, retention, and
  unsupported-venue behavior.
- **Workspace Root:** `/Users/user/Desktop/Projects/crypto-master`
- **Project Type:** Brownfield Python modular monolith.
- **Related Requirements:** FR-016, FR-019, FR-020, FR-046, NFR-009, NFR-011,
  CON-002, DD-NFR-004, DD-NFR-008, DD-NFR-009, DD-NFR-011, DD-NFR-012.
- **Related Stories:** US-008, US-014, US-025. Slice 1 supplies the exchange
  source boundary for US-025; it does not complete runtime/replay consumption.
- **Related Legacy / Debt:** Legacy Phases 2 and 13.3, Phase 25 snapshot
  precedent, resolved DEBT-080 actual-page pagination/contiguity rule. No
  active debt item.
- **Design Inputs:**
  - `aidlc-docs/construction/exchange-integration/functional-design/`
  - `aidlc-docs/construction/exchange-integration/nfr-requirements/`
  - `aidlc-docs/construction/exchange-integration/nfr-design/`

## Ownership and dependencies

- **Owned domain entities:** `FundingRate`, current funding view,
  `OpenInterestPoint`, retained history metadata, derivatives capability and
  typed error vocabulary. No database entity or migration is introduced.
- **Inbound dependencies:** existing Pydantic/Decimal/UTC utilities; existing
  ccxt async client; `BaseExchange` / `CcxtExchange` adapter hierarchy.
- **Outbound contract:** later runtime and snapshot slices receive only
  normalized immutable domain values, never raw ccxt `info` dictionaries.
- **Security boundary:** public calls must work with no credentials. When
  credentials are empty, the Binance client configuration must omit
  `apiKey`/`secret` keys rather than serialize empty placeholders.
- **Compatibility boundary:** existing OHLCV, ticker, balance, and order
  behavior and signatures remain unchanged. Bybit reports typed unsupported
  derivatives capability rather than gaining partial Binance behavior.

## Expected source and test paths

### Create

- `src/exchange/derivatives.py`
- `tests/test_exchange_derivatives.py`
- `aidlc-docs/construction/exchange-integration/code/derivatives-slice-1-summary.md`
- `docs/sessions/2026-07-18-exchange-integration-derivatives-slice-1.md`

### Modify in place

- `src/exchange/base.py`
- `src/exchange/ccxt_base.py`
- `src/exchange/binance.py`
- `tests/test_exchange_base.py`
- `tests/test_exchange_binance.py`
- `tests/test_exchange_ccxt_base.py`
- `tests/test_exchange_bybit.py` only if compatibility assertions need a
  concrete venue fixture; no Bybit runtime implementation is planned.
- `aidlc-docs/aidlc-state.md`
- this plan

### Explicitly not touched in Slice 1

- `src/runtime/`, `src/proposal/`, `src/strategy/`, `src/backtest/`
- `src/dashboard/`, `strategies/`, `data/`, deployment files
- snapshot schema, runtime cache/retry/circuit, proposal filters, strategy
  thresholds, and order execution behavior

## Executable generation steps

### Step 1 — Approval and baseline guard

- [x] Record explicit operator approval of this plan in `aidlc-docs/audit.md`.
- [x] Capture the pre-generation `git status --short` and preserve unrelated
  `.claude/settings.local.json` / `.claude/scheduled_tasks.lock` changes.
- [x] Run the existing exchange baseline tests before source edits:
  `uv run pytest tests/test_exchange_base.py tests/test_exchange_ccxt_base.py tests/test_exchange_binance.py tests/test_exchange_bybit.py`.

### Step 2 — Generate normalized derivatives domain

- [x] Create frozen validated Funding/OI/current-view/history metadata models
  in `src/exchange/derivatives.py` using Decimal and UTC-aware timestamps.
- [x] Add typed errors for unsupported capability, invalid payload,
  contiguity, unsupported funding interval, and venue-retention metadata.
- [x] Pin invariants in `tests/test_exchange_derivatives.py`: symbol,
  timestamp awareness, ordering/duplicates, non-negative OI, signed funding,
  and explicit retention truncation.

### Step 3 — Extend exchange and ccxt contracts compatibly

- [x] Add `supports_derivatives_data=False` and concrete default derivatives
  methods on `BaseExchange` that raise the typed unsupported error; do not add
  new abstract requirements to existing adapters.
- [x] Extend `CCXTClient` only with the unified funding/OI methods actually
  called by Binance.
- [x] Add/adjust base and structural protocol tests without changing existing
  order/OHLCV behavior.

### Step 4 — Generate Binance public current-value mappings

- [x] Set Binance derivatives capability true.
- [x] Make `_build_client` omit credential keys when both credentials are
  absent while preserving credentialed client configuration exactly.
- [x] Implement current funding and current OI normalization with strict symbol,
  Decimal, and UTC mapping; discard raw `info`.
- [x] Map ccxt transport/rate/venue errors to sanitized existing/typed exchange
  errors without raw response or secret-bearing URL serialization.
- [x] Add empty-credential config, current-value success, malformed-payload,
  and error-ladder tests.

### Step 5 — Generate funding history pagination and interval validation

- [x] Implement Binance settled funding history with page cap 1000, inclusive
  `since`/optional `until`, chronological de-duplication, and cursor advancement
  from the last record actually received.
- [x] Validate the canonical 8h grid for supported v1 history and return typed
  `unsupported_interval` for capability/observed spacing mismatches; never
  aggregate or resample.
- [x] Add capped-short-page, multi-page, duplicate, gap, interval, empty, and
  end-boundary tests proving no requested-page-size cursor math.

### Step 6 — Generate OI history pagination and retention metadata

- [x] Implement 1h Binance OI history with page cap 500, inclusive
  `since`/optional `until`, actual-record cursor advancement, chronological
  de-duplication, and grid validation for the returned suffix.
- [x] Return explicit requested/actual bounds and
  `truncated_at_venue_retention` when Binance cannot cover an older requested
  prefix; never synthesize/interpolate points.
- [x] Add multi-page, capped-short-page, duplicate, gap, no-data,
  retention-truncation, and exact-boundary tests.

### Step 7 — Verify compatibility and targeted quality

- [x] Run the focused derivatives and exchange suites.
- [x] Run `uv run black` on changed Python source/tests and
  `uv run ruff check` on the same paths.
- [x] Run `uv run mypy src/exchange` or the repository-supported narrow mypy
  equivalent; record any broader pre-existing issue separately.
- [x] Run the complete existing exchange test group again and confirm no
  duplicate `_new`/`_modified` source files were created.
- [x] Use `git diff --check` and inspect the exact source/test diff for raw
  payload, credentials, unrelated refactors, and data/deployment changes.

### Step 8 — Generate summaries and handoff

- [x] Write `derivatives-slice-1-summary.md` with contracts, files, test
  evidence, compatibility, risks, and Slice 2 interface assumptions.
- [x] Write the implementation session log with decisions, tests, debt, and
  remaining slices.
- [x] Update AI-DLC state to Slice 1 generated / Build & Test review pending.
- [x] Mark every completed step here and present the generated code for
  explicit approval before advancing to Build & Test or Slice 2.

## Story and requirement completion boundary

| Story / requirement | Slice 1 outcome |
|---|---|
| US-008 / FR-016 | Binance public derivatives source capability added without altering trading behavior |
| US-014 / FR-019 / NFR-009 | Backward-compatible exchange capability/default unsupported contract |
| US-025 / FR-046 | Normalized Funding/OI acquisition boundary only; runtime context and replay remain pending |
| NFR-011 | Dedicated empty-credential-compatible public transport and sanitized normalized output |
| CON-002 | Existing ccxt limiter retained; application rolling budget belongs to Slice 3 |

US-025 and FR-046 must not be marked fully implemented after this slice.

## Completion checklist

- [x] Plan explicitly approved and approval recorded.
- [x] Domain, port, Binance adapter, pagination, interval, and retention scope
  generated exactly as planned.
- [x] Existing exchange behavior preserved and targeted tests generated.
- [x] No application code outside the declared Slice 1 paths changed.
- [x] No production dependency, migration, deployment artifact, or runtime data
  change introduced.
- [x] Tests/format/lint/type evidence recorded; skipped checks have reasons.
- [x] Documentation/session/state updated.
- [x] No untracked TODO or real deferred gap left without technical debt.
- [x] Cross-check deferred until the full derivatives-data implementation has
  Build & Test evidence.
- [x] Generated code presented for explicit approval.

## Active Future Work: Derivatives Data Slice 3

## Plan authority

This section is the single source of truth for Code Generation Slice 3 of the
FR-046 / US-025 derivatives-data sequence. It supersedes the completed Slice 1
section only for the runtime-context task below; the completed Slice 1 evidence
remains immutable history.

The bounded sequence is now:

1. Exchange/domain foundation — complete and cross-checked.
2. Snapshot schema v2 / LC-10 — complete and cross-checked.
3. **Current plan:** runtime `DerivativesContextService`, shared context
   builder, strategy/proposal plumbing, health telemetry, and Ops projection.
4. Snapshot-only backtest/robustness integration / LC-11.
5. Separately designed proposal Funding+OI filter, then Funding-Extreme MR.

This plan implements item 3 only. It exposes derivatives context but does not
add a proposal veto, trading signal, strategy threshold, snapshot refresh,
backtest replay consumer, or live-order behavior change.

## Unit generation context

- **Primary unit:** `exchange-integration`
- **Secondary units:** `strategy-framework`, `proposal-runtime`,
  `dashboard-operator-ui`, `quality-governance`
- **Stage:** Code Generation — Part 2 generated / review pending
- **Task:** Add an engine-scoped, credential-free derivatives context service
  with bounded refresh, retry/circuit/budget/cache behavior; construct
  no-look-ahead `MarketContext`; inject it into compatible strategies; and
  project health to existing runtime events and Ops Diagnostics.
- **Workspace Root:** `/Users/user/Desktop/Projects/crypto-master`
- **Project Type:** Brownfield Python modular monolith.
- **Related Requirements:** FR-016, FR-019, FR-046, NFR-003, NFR-006,
  NFR-009, NFR-011, CON-002, DD-NFR-001..007, DD-NFR-009..012.
- **Related Stories:** US-005, US-015, US-016, US-025. Slice 3 supplies the
  live/paper runtime-consumption boundary for US-025; deterministic replay is
  still owned by Slice 4.
- **Related Legacy / Debt:** Legacy Phases 2, 8, 11, 13, 21, and 25; resolved
  DEBT-080 actual-record pagination/contiguity precedent. Active DEBT-081 is
  unrelated formatter/lint drift and must not be mixed into this slice.
- **Logical components:** LC-04..09 and LC-12..13. LC-01 receives additive
  context/state contracts; LC-02/03 and LC-10 are consumed unchanged.
- **Design Inputs:** approved Functional Design, NFR Requirements, and NFR
  Design under `aidlc-docs/construction/exchange-integration/`.

## Ownership, boundaries, and dependencies

- **Owned domain values:** `SeriesKind`, `SeriesStatus`,
  `SeriesAvailability`, `MarketContext`, `MarketContextRequirements`,
  `SeriesSnapshot`, `ContextEvaluation`, immutable refresh summaries, and
  stable unmet/error codes. No database entity or migration is introduced.
- **Owned runtime service:** one process-local `DerivativesContextService`
  for the dedicated public Binance source. It owns the semaphore, monotonic
  rolling budgets, in-flight tasks, retry/circuit state, last-known-good cache,
  and transition-event dedupe.
- **Pure boundary:** `MarketContextBuilder` accepts immutable normalized
  series snapshots and has no filesystem, network, settings, dashboard, ccxt,
  or global-singleton dependency.
- **Inbound dependencies:** Slice 1 normalized Binance Funding/OI methods and
  typed errors; existing asyncio, Pydantic, UTC helpers, activity log, and
  composition root.
- **Outbound contracts:** `TradingEngine` invokes one refresh before the first
  sub-account scan; `ProposalEngine` requests context at the final primary
  OHLCV timestamp and forwards it only through one centralized compatibility
  dispatcher; Ops Diagnostics derives state only from activity events.
- **Security boundary:** when enabled, composition creates a dedicated
  mainnet USD-M `BinanceExchange` with all credential fields explicitly empty.
  The service is typed to a narrow public-data protocol and never receives a
  trading client through ordinary composition.
- **Compatibility boundary:** `DerivativesDataConfig.enabled=False` by
  default means no public client construction, connection, request, timing,
  event, strategy call, or proposal behavior change. Existing code strategies
  without a `market_context` keyword remain callable through one centralized
  signature check; runtime `TypeError` from strategy bodies is never swallowed
  as compatibility fallback.
- **Persistence boundary:** the runtime cache is memory-only and disposable.
  No cache hydration, JSON/CSV write, `data/` mutation, or Snapshot v2 write is
  part of Slice 3.
- **Consumer boundary:** no Funding+OI gate or Funding-Extreme MR strategy is
  generated. `requires_market_context=True` only enforces explicit
  neutral/no-proposal behavior when typed requirements are unmet.

## Configuration contract selected for generation

`src/config.py` owns one nested frozen `DerivativesDataConfig` with the
approved defaults and hard envelopes:

| Field | Default / bound |
|---|---|
| `enabled` | `False` |
| `max_symbols` | `20`, range `1..20` |
| `max_concurrency` | `4`, range `1..4` |
| `deadline_4_symbols_seconds` | `5.0`, positive |
| `deadline_20_symbols_seconds` | `15.0`, >= small deadline |
| `funding_max_age_seconds` | `32400`, cannot exceed 9h |
| `oi_max_age_seconds` | `7200`, cannot exceed 2h |
| `retry_count` | `2`, range `0..2` |
| `retry_base_seconds` | `0.25`, non-negative |
| `funding_budget_5m` | `250`, range `1..250` |
| `oi_history_budget_5m` | `500`, range `1..500` |
| `funding_interval_hours` | literal `8` |
| `oi_timeframe` | literal `"1h"` |

Environment mapping uses Pydantic nested settings with the
`DERIVATIVES_DATA__*` prefix and is documented in `.env.example`. Deadline
validation also checks the resolved `EngineConfig.cycle_interval_seconds`;
invalid operator values fail startup and are never silently clamped.

## Expected source and test paths

### Create

- `src/runtime/derivatives_context.py`
- `src/strategy/market_context.py`
- `tests/test_runtime_derivatives_context.py`
- `tests/test_strategy_market_context.py`
- `aidlc-docs/construction/exchange-integration/code/derivatives-runtime-context-summary.md`
- `docs/sessions/2026-07-19-exchange-integration-derivatives-runtime-context.md`

### Modify in place

- `src/config.py`
- `.env.example`
- `src/exchange/derivatives.py`
- `src/strategy/base.py`
- `src/strategy/loader.py`
- `src/proposal/engine.py`
- `src/runtime/activity_events.py`
- `src/runtime/engine.py`
- `src/main.py`
- `src/dashboard/pages/ops.py`
- `tests/test_config.py`
- `tests/test_exchange_derivatives.py`
- `tests/test_strategy_base.py`
- `tests/test_strategy_loader.py`
- `tests/test_proposal_engine.py`
- `tests/test_runtime_activity_log.py`
- `tests/test_runtime_engine.py`
- `tests/test_main_dispatch.py`
- `tests/test_dashboard_ops.py`
- `aidlc-docs/aidlc-state.md`
- this plan

### Explicitly not touched in Slice 3

- `src/backtest/`, Snapshot v1/v2 storage, robustness scripts, and baseline
  artifacts
- `src/exchange/binance.py`, `src/exchange/base.py`, and Slice 1 pagination
  behavior unless a directly failing contract test proves an integration bug
- `strategies/`, Funding+OI proposal-filter logic/configuration, threshold
  tuning, promotion decisions, and order/trader/risk math
- `data/`, dependency/lock files, deployment files, credentials, Fly state,
  migrations, and production runtime configuration

## Executable generation steps

### Step 1 — Approval and baseline guard

- [x] Record explicit operator approval of this Slice 3 plan in
  `aidlc-docs/audit.md` with the exact response and timestamp.
- [x] Capture `git status --short`; preserve all prior derivatives Slice 1/2
  work and unrelated `.claude/settings.local.json` /
  `.claude/scheduled_tasks.lock` changes.
- [x] Run the existing targeted baseline before source edits:
  `uv run pytest tests/test_exchange_derivatives.py tests/test_strategy_base.py tests/test_strategy_loader.py tests/test_proposal_engine.py tests/test_runtime_engine.py tests/test_main_dispatch.py tests/test_runtime_activity_log.py tests/test_dashboard_ops.py tests/test_config.py -q`.

### Step 2 — Generate immutable context/state contracts

- [x] Extend `src/exchange/derivatives.py` with the approved series/status,
  availability, requirements, context, snapshot, evaluation, refresh-summary,
  stable error-code, and narrow `DerivativesDataSource` protocol contracts.
- [x] Enforce frozen values, UTC normalization, symbol equality, ascending
  duplicate-free records, `timestamp <= as_of`, per-series point/status
  coherence, OI-only retention truncation, required-series minimum points,
  and 9h/2h maximum requirement ages.
- [x] Add focused domain tests including invalid mixed/future/duplicate data,
  unavailable/fresh status coherence, stable unmet-reason ordering, and
  serialization free of raw payloads/credentials.

### Step 3 — Generate the pure `MarketContextBuilder`

- [x] Create `src/strategy/market_context.py` with deterministic UTC `as_of`
  slicing from immutable snapshots, defensive order/uniqueness checks, tail
  age computation, hard-expiry removal, `fresh`/`cached`/`stale` projection,
  bounded normalized context, and side-effect-free requirements evaluation.
- [x] Keep predicted funding as a live-cycle scalar only; never use it to
  satisfy requirements and never forward a value outside its originating
  cycle.
- [x] Add boundary tests at exactly/just beyond funding 9h and OI 2h, partial
  funding/OI availability, future-record exclusion, cached provenance,
  retention metadata, stable unmet reasons, and byte-equivalent results for
  equal normalized live/snapshot inputs.

### Step 4 — Generate request budget, retry, circuit, and cache core

- [x] Create cohesive private helpers in
  `src/runtime/derivatives_context.py` for monotonic 300-second rolling
  endpoint budgets, one-initial-plus-`0..2` transient retries with injected
  jitter/clock/sleep, per-`(venue,symbol,series)` circuits, immutable cache
  replacement, and safe typed error classification.
- [x] Treat `ExchangeAPIError.code` transient classes as retryable; treat
  unsupported/validation/auth/budget/deadline results as non-retryable; keep
  causes local while events/summaries expose only stable allowlisted fields.
- [x] Open a circuit after three exhausted transient refreshes, skip exactly
  one full cycle, allow one half-open probe, recover on success, and keep
  eligible last-known-good data readable while remote calls are blocked.
- [x] Add deterministic fake-clock/random tests for admission/eviction,
  exhausted budget, retry count/jitter/deadline, circuit transitions,
  per-series isolation, cache non-displacement on invalid/partial responses,
  and no secret/raw-response leakage.

### Step 5 — Generate cycle refresh scheduler and lifecycle

- [x] Implement the public `refresh_cycle`, `context_for`, and `close`
  contracts with canonical keys, stable symbol ordering, a semaphore capped at
  four, one in-flight task per canonical request, 5s/15s monotonic deadlines,
  due-only Funding 8h and OI 1h refreshes, per-cycle current Funding/OI reads,
  task cancellation/await, and per-series immutable commit.
- [x] Lazily connect the dedicated source on the first enabled refresh; close
  it exactly once; cancel/await every owned task so no completion can mutate
  cache after the cycle decision or shutdown.
- [x] Bootstrap a bounded recent cache from normalized adapter history, append
  only validated later observations, de-duplicate timestamps, retain the
  latest bounded source result, and preserve explicit OI retention metadata.
- [x] Add 4- and 20-symbol deterministic load tests over at least 100 fake
  cycles, semaphore peak/in-flight dedupe assertions, 5s/15s cancellation,
  one-symbol failure isolation, unsupported interval with OI preserved,
  last-known-good expiry, recovery, and leaked-task checks.

### Step 6 — Generate strategy metadata and centralized proposal plumbing

- [x] Add `requires_market_context=False` plus optional typed requirements to
  `TechniqueInfo`; validate that a required context declaration is non-empty
  and within global age ceilings. Existing metadata files remain valid.
- [x] Widen `BaseStrategy.analyze` and `PromptStrategy.analyze` with optional
  keyword-only `market_context`; preserve every existing caller and prompt
  output when absent. Allowlisted normalized context may fill a
  `{market_context}` prompt placeholder; raw exchange data is never rendered.
- [x] Add one `ProposalEngine` context-provider seam. After the primary OHLCV
  fetch, use `primary_ohlcv[-1].timestamp` as the decision `as_of`, evaluate
  the strategy's typed requirements, and return neutral/no proposal without
  calling analysis when required inputs are unmet.
- [x] Route all strategy calls through one compatibility helper that passes
  `market_context` only when the concrete method declares it or accepts
  `**kwargs`; legacy methods are called unchanged, while genuine `TypeError`
  raised inside a strategy remains a strategy failure and is not retried.
- [x] Add tests for legacy metadata/signatures, context-aware code and prompt
  strategies, required-missing neutral behavior, optional partial context,
  final-candle `as_of`, future-record exclusion, and one context lookup shared
  across multi-technique calls for the same symbol/decision boundary.

### Step 7 — Generate composition, prefetch, and shutdown wiring

- [x] Add nested `DerivativesDataConfig` plus environment tests and
  `.env.example` documentation; wire it into `EngineConfig` without changing
  disabled defaults.
- [x] In `src/main.py`, construct no derivatives object when disabled. When
  enabled, build a separate mainnet futures Binance source with explicit empty
  live/testnet credentials, then inject one shared service into
  `ProposalEngine` and `TradingEngine`.
- [x] In `TradingEngine.run_cycle`, compute the stable union of every active
  account's BTC and altcoin symbols, refresh once before the first account
  scan, catch a batch-internal service failure outside per-account errors, and
  continue the existing OHLCV-only scan/monitor/snapshot path.
- [x] Close the shared service from the `run_forever` shutdown `finally`
  boundary without closing/replacing any account trading exchange.
- [x] Add tests proving disabled zero-construction/zero-call behavior,
  enabled empty-credential composition, union/dedupe and one-prefetch-per-cycle,
  outage fail-open cycle completion, recovery next cycle, sub-account
  isolation, and exact single close on shutdown.

### Step 8 — Generate health events and existing Ops projection

- [x] Add stable `DERIVATIVES_DATA_DEGRADED` and
  `DERIVATIVES_DATA_RECOVERED` activity enum values and service-owned
  transition emission with the exact allowlist: `exchange`, `symbol`,
  `series`, `status`, `error_code`, `data_timestamp`, `data_age_seconds`,
  `cache_status`, `attempt_count`, `circuit_state`, and
  `truncated_at_venue_retention`.
- [x] De-duplicate degradation by `(cycle_id,symbol,series)` and emit recovery
  only after cross-cycle degraded-to-fresh transition. Consumers must not
  repeat endpoint events.
- [x] Extend the existing Ops Diagnostics builder to fold recent activity into
  the newest row per `(exchange,symbol,series)` after the existing filesystem
  rows. It must never instantiate the service or call Binance.
- [x] Add event schema/dedupe/recovery tests, safe serialization negative
  assertions, and Ops mappings for fresh/recovered=`pass`, cached=`watch`,
  stale/unavailable/open-circuit=`stop`, unsupported-interval=`watch`, while
  preserving the current no-event dashboard shape.

### Step 9 — Verify generated scope and compatibility

- [x] Run new focused domain/builder/service tests first, then all modified
  component suites.
- [x] Run Black and Ruff on Slice 3 touched Python files only; do not absorb
  unrelated DEBT-081 global drift.
- [x] Run repository `uv run mypy src` and the full `uv run pytest` when the
  targeted suites pass; record exact counts/timing and any skipped check.
- [x] Run `git diff --check`; inspect the exact diff for credentials, raw ccxt
  payloads, network-at-import, background task leaks, context look-ahead,
  order/risk behavior, new dependencies, deployment changes, and `data/`
  mutation.
- [x] Confirm no `_new`/`_modified` duplicate files and no real deferred gap
  remains as an untracked TODO; file debt only for a verified residual gap.

### Step 10 — Generate summaries and review handoff

- [x] Write `derivatives-runtime-context-summary.md` with contracts, lifecycle,
  files, compatibility, security, tests, NFR evidence, and Slice 4 assumptions.
- [x] Write the implementation session log with decisions, checks, risks, debt,
  and remaining sequence.
- [x] Update AI-DLC state to Slice 3 generated / Code Generation review
  pending; keep FR-046 and US-025 Partial until LC-11 replay ships.
- [x] Mark completed steps here and present generated code for explicit
  approval before Build & Test.

## Layer applicability

| Layer / artifact | Slice 3 decision |
|---|---|
| Business/domain logic | Required: domain state, pure builder, service policies |
| API layer | N/A: no HTTP/API endpoint is added |
| Repository/database | N/A: cache is process-local; no durable repository or entity |
| Frontend | Minimal in-place Ops Diagnostics read-model extension only |
| Migration scripts | N/A: no persisted schema or runtime-data migration |
| Deployment artifacts | N/A: disabled-by-default in-process feature, no topology change |
| Documentation | Config example, code summary, session/state/audit updates |

## Story and requirement completion boundary

| Story / requirement | Slice 3 planned outcome |
|---|---|
| US-025 / FR-046 | Runtime Funding/OI context becomes consumable without look-ahead; deterministic replay remains pending Slice 4 |
| FR-016 / FR-019 / NFR-009 | Existing normalized Binance public adapter is consumed through a narrow optional service port |
| DD-NFR-001..007 | Bounded load, latency, freshness, retry/circuit, rate budget, and runtime recovery implemented/tested |
| DD-NFR-009 | Runtime `as_of` parity half implemented; snapshot per-bar replay remains pending |
| DD-NFR-010..012 / NFR-011 | Safe events, empty-credential composition, offline tests, and no new production dependency |
| US-005 / proposal behavior | Unchanged until a separate filter plan; collection alone cannot veto/down-weight |

FR-046 and US-025 must remain Partial after Slice 3 because deterministic
Snapshot v2 replay and context-required robustness outcomes are Slice 4.

## Completion checklist

- [x] Plan explicitly approved and approval recorded.
- [x] LC-04..09 and LC-12..13 generated exactly within the declared paths.
- [x] Feature-disabled behavior is byte/decision compatible and performs no
  public derivatives work.
- [x] Enabled runtime uses only a dedicated credential-free public source and
  never blocks OHLCV-only operation on ordinary derivatives degradation.
- [x] No-look-ahead, freshness, partial availability, retry/circuit/budget,
  cancellation, and recovery contracts are pinned by deterministic tests.
- [x] Health events and Ops projection use allowlisted safe fields only.
- [x] No consumer threshold, trade signal, proposal veto, replay, migration,
  dependency, deployment, credential, or `data/` change is introduced.
- [x] Tests/format/lint/type evidence and load timing are recorded.
- [x] Documentation/session/state updated and genuine gaps tracked as debt.
- [x] Generated code presented for explicit approval before Build & Test.

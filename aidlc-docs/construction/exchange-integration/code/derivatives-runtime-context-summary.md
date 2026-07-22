# Derivatives Data Slice 3 Runtime Context Summary

**Primary unit:** `exchange-integration`

**Secondary units:** `strategy-framework`, `proposal-runtime`,
`dashboard-operator-ui`, `quality-governance`

**Stage:** Code Generation Part 2

**Status:** Generated; Build & Test approved PASS; Operations N/A

## Scope generated

Slice 3 adds the disabled-by-default runtime consumption boundary for normalized
Binance Funding and Open Interest data. One engine-scoped service refreshes a
credential-free public source, retains only immutable process-local state,
constructs no-look-ahead `MarketContext`, and exposes it to compatible
strategies through the proposal boundary. It does not add a Funding/OI proposal
filter, trading signal, threshold, replay consumer, snapshot writer, or order
behavior change.

## Domain and pure context contracts

- `src/exchange/derivatives.py` now owns stable series/status enums,
  availability, requirements, context, service snapshots, evaluations, refresh
  outcomes, summaries, error codes, and a narrow public-data protocol.
- Values are frozen, UTC-normalized, finite, symbol-consistent, chronological,
  duplicate-free, and safe to serialize. Funding requirements cannot exceed
  9h; OI requirements cannot exceed 2h.
- `MarketContextBuilder` slices records at the final primary OHLCV timestamp,
  excludes future data, removes hard-expired values, preserves cached and OI
  retention provenance, and emits unmet reasons in funding-then-OI order.
- Predicted funding is a live-cycle scalar only. It is cleared on degraded
  refresh, never satisfies requirements, and is not persisted or replayed.

## Runtime service lifecycle

- `DerivativesContextService` owns one lazy source connection, a semaphore
  capped at four, canonical per-series in-flight tasks, 5s/15s cycle deadlines,
  cancellation/await, and exactly-once shutdown.
- Funding history is due on its 8h settled grid, OI history has an independent
  1h cursor, and current Funding/OI is read once per cycle. Source calls use the
  existing Slice 1 millisecond-boundary adapter contract.
- A 300-second monotonic rolling budget admits Funding and OI groups
  independently. Transient stable exchange codes receive one initial attempt
  plus at most two jittered retries; optional rate-limit retry-after metadata is
  honored when present.
- Three exhausted transient series refreshes open only that symbol/series
  circuit, one complete cycle is skipped, and the following half-open probe can
  recover it.
- Cache replacement is per-series and atomic. Invalid or partial responses do
  not displace last-known-good records; eligible data is projected as cached,
  then stale and removed at its hard expiry. The cache is memory-only and no
  `data/` or snapshot path is read or written.

## Strategy, proposal, and engine plumbing

- `TechniqueInfo` defaults to `requires_market_context=False`; required
  declarations need non-empty typed requirements. Existing strategy metadata
  remains valid.
- `BaseStrategy` and `PromptStrategy` accept optional normalized context.
  `{market_context}` renders deterministic normalized JSON only.
- `ProposalEngine` queries one context per symbol/final-candle decision
  boundary and shares it across multi-technique candidates. Required missing
  context returns neutral before `analyze`; optional and legacy consumers
  continue.
- One signature dispatcher passes `market_context` only when the concrete
  strategy declares it or accepts `**kwargs`. It performs no `TypeError`
  retry/fallback, so errors raised inside strategy code remain visible.
- `TradingEngine` computes one stable union of every active account's BTC and
  altcoin symbols, refreshes before the first account scan, fails open to the
  existing OHLCV path on an internal batch fault, and closes only the dedicated
  derivatives service at shutdown.

## Configuration and security

- `DerivativesDataConfig` is frozen and nested under `Settings` with
  `DERIVATIVES_DATA__*` environment names. `enabled=False` is the default and
  performs zero client construction, connection, request, timing, or event
  work.
- Enabled composition creates a separate Binance USD-M mainnet source with all
  live and testnet credential fields explicitly empty. The account trading
  exchange is never passed to the service or closed by it.
- Events expose only the approved eleven fields. They never contain exception
  text, credentials, URLs, raw ccxt payloads, or response bodies.
- No dependency, lock, deployment, migration, credential, production config,
  strategy threshold, order/risk, or runtime-data change was introduced.

## Health and Ops projection

- Stable `derivatives_data_degraded` and `derivatives_data_recovered` activity
  values were added. Degradation is deduplicated per cycle/symbol/series and
  recovery emits only after a prior degraded state.
- Existing Ops Diagnostics folds the newest event per exchange/symbol/series
  after its current filesystem/health rows. No-event output remains the same
  three rows, and the dashboard never constructs the service or calls Binance.

## Files

Created:

- `src/runtime/derivatives_context.py`
- `src/strategy/market_context.py`
- `tests/test_runtime_derivatives_context.py`
- `tests/test_strategy_market_context.py`
- this summary
- `docs/sessions/2026-07-19-exchange-integration-derivatives-runtime-context.md`

Modified in place:

- `.env.example`, `src/config.py`, `src/exchange/derivatives.py`
- `src/strategy/base.py`, `src/strategy/loader.py`, `src/proposal/engine.py`
- `src/runtime/activity_events.py`, `src/runtime/engine.py`, `src/main.py`
- `src/dashboard/pages/ops.py`
- the nine focused existing test modules plus the two new suites named in the approved plan
- the Slice 3 construction plan, audit log, and AI-DLC state

## Verification evidence

- Pre-edit targeted baseline: 523 passed in 4.84s.
- Domain and pure builder: 31 passed.
- Deterministic service suite: 12 passed in 1.52s, including 4- and 20-symbol runs over
  100 fake cycles each, deadline cancellation, per-series circuit recovery,
  budget exhaustion, hard expiry, and OI hourly cursor refresh.
- Slice 3 modified-component suite: 560 passed in 5.34s.
- Full repository regression: 2555 passed in 42.06s.
- Changed-file Black: clean (22 Python files).
- Changed-file Ruff: all checks passed.
- Repository mypy: no issues in 111 source files.
- `git diff --check`: clean; no `_new.py`/`_modified.py` duplicates, raw
  derivatives payload fields, new production dependencies, deployment files,
  or tracked `data/` mutations were found.

## NFR evidence

- DD-NFR-001..007: bounded symbol/concurrency envelopes, cycle deadlines,
  freshness ceilings, rolling budgets, retry/circuit behavior, cache expiry,
  cancellation, and recovery are implementation- and test-pinned.
- DD-NFR-009: runtime `as_of` construction is complete; deterministic
  snapshot-per-bar replay remains intentionally pending.
- DD-NFR-010..012 / NFR-011: safe allowlisted telemetry, explicit
  empty-credential composition, offline deterministic tests, and no new
  production dependency are preserved.

## Remaining Slice 4 boundary

FR-046 and US-025 remain **Partial**. Slice 4 must consume Snapshot v2 only,
reconstruct the same context at each historical decision boundary, verify
live/snapshot parity, and exercise context-required robustness outcomes before
any separate Funding+OI regime filter or Funding-Extreme mean-reversion
strategy is designed.

No new technical debt was filed. The remaining work is already bounded by the
approved derivatives-data sequence rather than an untracked implementation gap.

## Build and Test follow-up

Construction Build & Test subsequently found and repaired the generated stable
error-code mismatch `budget_exhausted` -> `request_budget_exhausted` and added
the missing DD-NFR-001/002 latency-injecting p50/p95/max evidence. Final
evidence is 45 core tests at 89% combined generated-module coverage, 562
modified-component tests, 2557 full repository tests, 4/20-symbol p95 of
0.005630s/0.027393s, and clean Slice Black/Ruff plus repository mypy. See
`aidlc-docs/construction/build-and-test/build-and-test-summary.md`.

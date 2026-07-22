# Build and Test Plan: Derivatives Snapshot Replay and Robustness

## Plan authority

This plan independently builds and tests the operator-approved Derivatives
Data Slice 4 generated under `backtesting-validation`. It verifies LC-11
snapshot-only Funding/OI replay and promotion-gate integration. It does not
authorize live collection, production snapshot refresh, proposal-layer regime
filtering, Funding-Extreme MR, strategy thresholds, deployment, credentials,
or repository runtime-data mutation.

## Context

- **Primary unit:** `backtesting-validation`
- **Secondary units:** `exchange-integration`, `strategy-framework`,
  `persistence-data-integrity`, `quality-governance`
- **Stage:** Construction Build and Test
- **Task:** Independently verify pinned v1/v2 replay, no-lookahead derivatives
  context, engine/harness/gate propagation, deterministic provenance,
  promotion-blocking insufficient evidence, and explicit refresh boundaries.
- **Related requirements:** FR-025, FR-026, FR-027, FR-034, FR-046, NFR-006,
  DD-NFR-008, DD-NFR-009, DD-NFR-011, DD-NFR-012.
- **Related stories:** US-002, US-003, US-025.
- **Legacy/debt context:** Legacy Phases 5, 9, 19, 24, and 25; resolved
  DEBT-043 and DEBT-080 precedents; unrelated DEBT-081 remains owned by
  `quality-governance`.
- **Approved code plan:**
  `aidlc-docs/construction/plans/backtesting-validation-code-generation-plan.md`
- **Code summary:**
  `aidlc-docs/construction/backtesting-validation/code/derivatives-snapshot-replay-summary.md`

## Testing classification

- **Build:** locked dependency validation, Python compile/import, public-model
  construction, and CLI parser/import verification.
- **Unit:** replay identity/digest, v1/v2 negotiation, pinned source,
  coverage classification, no-lookahead context, engine counters, and result
  serialization.
- **Integration:** Snapshot v2 -> `SnapshotReplaySource` -> shared
  `MarketContextBuilder` -> engine/harness -> robustness gates -> CLI report.
- **Contract:** exact generation pinning, same-source OHLCV/context,
  `INSUFFICIENT_DATA` versus `SKIPPED`, deterministic report provenance,
  legacy strategy signatures, and snapshot-default/no-live-fallback behavior.
- **Security:** invalid identity/range/gap rejection, predicted-funding and raw
  payload exclusion, safe reports, no implicit network, no credentials, and no
  repository `data/` mutation.
- **Performance:** no production latency/throughput acceptance target is
  defined for offline replay. Record bounded deterministic test observations
  without inventing a threshold.
- **E2E:** hermetic snapshot publication/reload/replay/report flow using fake
  exchange data and temporary directories; no live endpoint or order path.

## Executable steps

### Step 1 — Transition and baseline

- [x] Record the exact operator approval and Build & Test transition in
  `aidlc-docs/audit.md`.
- [x] Preserve prior Slice 1-3 changes and user-owned `.claude` worktree state.
- [x] Confirm generated scope, current diff integrity, and no tracked `data/`,
  dependency, credential, migration, or deployment mutation.

### Step 2 — Build verification

- [x] Verify `uv.lock` against `pyproject.toml` without mutation.
- [x] Compile/import replay, v2 snapshot, engine, validator, harness, and CLI
  surfaces; record runtime/tool versions.
- [x] Confirm imports are offline and construct no exchange connection,
  service task, credentialed client, or data write.

### Step 3 — Unit, contract, and security verification

- [x] Run snapshot v1/v2, replay, reproducibility, engine, multi-timeframe,
  validator, harness, and CLI suites with exact counts.
- [x] Run focused generated-path coverage and record per-module results without
  inventing a repository fail-under threshold.
- [x] Verify no future records/predicted funding, stable moved-`CURRENT`
  pinning, exact identity/digest/seed serialization, and legacy optional path.
- [x] Verify v1/missing/short/gapped required context cannot produce a vacuous
  promotion pass and that unrelated `SKIPPED` behavior remains compatible.

### Step 4 — Integration, E2E, and deterministic replay

- [x] Run shared live/replay `MarketContextBuilder` parity and proposal/runtime
  compatibility suites.
- [x] Run existing backtest script consumers and hermetic collector-to-v2
  refresh/reload/replay/report integration.
- [x] Repeat a fixed pinned replay and confirm byte-identical context,
  decisions, provenance, and report verdict.
- [x] Confirm snapshot absence/corruption never falls through to live Binance;
  all exchange-facing tests use fakes and temporary paths.

### Step 5 — Static, regression, and bounded performance evidence

- [x] Run changed-file Black/Ruff, repository-wide mypy, compile, lock, diff,
  duplicate/TODO/credential/dependency/deployment/data-mutation scans.
- [x] Run the complete repository pytest suite.
- [x] Record focused/full runtimes only as observations; classify production
  performance and live-network E2E as N/A because no requirement authorizes a
  threshold or live operation.
- [x] Keep repository-wide DEBT-081 Black/Ruff drift isolated from Slice 4.

### Step 6 — Requirements cross-check and evidence

- [x] Cross-check FR-025/026/027/034/046, NFR-006, US-002/003/025, and
  DD-NFR-008/009/011/012 against source, tests, and documentation.
- [x] Register any introduced defect or deferred gap in `docs/TECH-DEBT.md`;
  otherwise record that no new debt was found.
- [x] Update shared Build & Test instruction/summary artifacts, the Slice 4
  session log, AI-DLC state, and audit evidence.
- [x] Present Build & Test results for explicit operator review before the
  Operations disposition boundary.

## Completion checklist

- [x] Build/import/lock checks pass without dependency mutation.
- [x] Unit, integration, E2E, contract, security, and complete regression
  checks pass.
- [x] Pinned no-lookahead replay and promotion-blocking insufficient evidence
  are independently verified.
- [x] Legacy OHLCV-only, v1 snapshot, optional-strategy, and `SKIPPED`
  compatibility remain intact.
- [x] Deterministic identity/digest/seed/coverage evidence is serialized.
- [x] Performance/live-network/deployment applicability is stated honestly.
- [x] No live request, order, credential, deployment, or repository `data/`
  mutation occurs.
- [x] Cross-check, session, Build & Test artifacts, state, and audit are
  complete with no untracked debt.
- [x] Results are presented for explicit operator approval.

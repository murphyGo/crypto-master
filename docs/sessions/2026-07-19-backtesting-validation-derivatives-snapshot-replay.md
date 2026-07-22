# Session: backtesting-validation Derivatives Snapshot Replay

**Date:** 2026-07-19

**Primary unit:** `backtesting-validation`

**Secondary units:** `exchange-integration`, `strategy-framework`,
`persistence-data-integrity`, `quality-governance`

**Stage:** Construction Build and Test

**Status:** Build & Test PASS; explicit operator review pending

## Scope

Implemented the approved Derivatives Data Slice 4 LC-11 plan. The slice joins
immutable Snapshot v2 data to historical strategy decisions without lookahead,
propagates one pinned replay through backtests and robustness gates, introduces
a promotion-blocking insufficient-evidence outcome, and adds an explicit
collector-to-v2 refresh command.

It does not implement a proposal regime filter, a Funding-Extreme MR strategy,
runtime cache persistence, funding-cost math, production data refresh, or
deployment.

## Decisions implemented

- Load one exact replay generation for the whole run; do not re-read `CURRENT`.
- Keep schema v1 OHLCV compatible while treating required derivatives context
  as explicitly unavailable.
- Reuse `MarketContextBuilder` for both live-normalized and snapshot-normalized
  values, anchoring every replay decision to the primary candle close.
- Neutralize only the known missing-context prefix. Reject structural gaps and
  block promotion when the remaining evidence is missing, discontinuous, or
  too short.
- Add optional engine/harness seams so existing OHLCV-only callers and legacy
  strategy signatures keep their behavior.
- Record replay identity, canonical configuration digest, seed, and context
  coverage on backtest and robustness results.
- Keep snapshot mode offline and fail closed. Make live exploration and live
  snapshot refresh two separate explicit commands.
- Preserve predicted funding, raw exchange responses, credentials, and paths
  outside replay reports and snapshot publication.

## Validation

- Pre-change baseline: 182 focused tests passed.
- Final focused Slice 4 plus snapshot v1/v2 regression: 204 passed.
- Generated-path coverage run: 120 passed with 96% combined statement
  coverage; per module: engine 98%, harness 94%, reproducibility 80%, snapshot
  replay 93%, validator 97%.
- Shared `MarketContextBuilder` proposal/runtime compatibility: 103 passed.
- Existing backtest baseline/combination/research script consumers: 46 passed.
- Complete repository regression: 2579 passed in 43.80 seconds.
- Changed-file Black and Ruff passed.
- `uv run mypy src`: 113 source files, zero issues.
- `uv lock --check`, Python compile, `git diff --check`, and import integrity
  passed.
- Duplicate-file, TODO, hard-coded credential, dependency, deployment, and
  `data/` mutation scans were clean.

All collector tests used fake exchanges and temporary directories. No live
Binance request or repository runtime-data write occurred.

## Compatibility and safety

The engine context/provider arguments are optional. When they are absent,
existing strategy decisions and results retain the legacy path. A strategy
that declares required market context cannot pass promotion from an unpinned
generic run or a v1/missing/short/gapped context replay. Optional strategies
retain existing `SKIPPED` semantics for unrelated low-trade or missing-grid
gates.

The user-owned `.claude/settings.local.json` change and
`.claude/scheduled_tasks.lock` were preserved. Earlier Slice 1-3 worktree
changes were not reverted or folded into a new unrelated cleanup. DEBT-081
remains separate; no new debt item was required.

## Handoff boundary

Code Generation is complete and awaiting explicit operator review. Independent
Construction Build & Test and cross-check have not started. FR-046, US-025,
and LC-11 remain Partial until those stages pass.

## Independent Build & Test evidence — 2026-07-22

- Exact transition approval: `승인, 다음단계 진행`.
- Lock/build: 91 packages resolved without mutation; replay/snapshot/backtest/
  CLI compile and offline imports passed under a socket connection guard.
- Focused unit/contract/security/integration: 210 passed in 11.69 seconds.
- Generated path: 183 passed in 17.80 seconds with 92% combined coverage;
  replay 95%, engine 98%, validator 97%, harness 94%, snapshot v2 85%, and
  reproducibility 82%.
- Shared builder/proposal/runtime compatibility: 103 passed in 4.59 seconds.
- Existing backtest script consumers: 46 passed in 17.77 seconds.
- Hermetic fake collector -> v2 -> exact generation -> replay -> report flow:
  passed twice with identical normalized reports.
- Complete repository: 2585 passed in 46.89 seconds.
- All 13 Slice 4 files pass Black/Ruff; repository mypy passes 113 source
  files; compile, lock, diff, duplicate, TODO, dependency, credential,
  deployment, and `data/` scope checks pass.

## Build & Test repairs

1. An unexplained Funding prefix longer than one 8h interval is now rejected
   even when requested bounds are present. Only explicitly retained OI prefixes
   can bypass this structural check.
2. Runner failure reports no longer serialize raw exception text. They retain
   only a stable exception-class field while local logs keep diagnostic detail.

Regression tests also pin symbol mismatch rejection, exact generation
selection forwarding, repeated-report determinism, and the full hermetic E2E.
No new technical debt was introduced.

## Cross-check and handoff

Cross-check PASS is recorded at
`docs/cross-checks/2026-07-22-backtesting-validation-derivatives-snapshot-replay.md`.
LC-11 and the full FR-046/US-025 chain are independently verified Complete
across Slices 1-4. Proposal filtering and Funding-Extreme MR remain separate
later slices.

Build & Test now awaits explicit operator review. No Operations, production
refresh, deployment, credential, live network, order, or runtime `data/`
action has occurred.

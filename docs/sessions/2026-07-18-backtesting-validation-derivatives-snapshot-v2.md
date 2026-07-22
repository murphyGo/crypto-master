# Session: backtesting-validation Derivatives Snapshot Schema v2

**Date:** 2026-07-18 through 2026-07-19

**Primary unit:** `backtesting-validation`

**Secondary units:** `exchange-integration`, `persistence-data-integrity`

**Stage:** Build and Test

**Status:** Build & Test approved; Operations N/A; Slice 2 cross-checked PASS

## Scope

Implemented the approved Derivatives Data Slice 2 plan for LC-10 only. The new
store persists one deterministic OHLCV/Funding/OI bundle as an immutable,
content-addressed generation and exposes either a pinned/current v2 view or an
explicit schema-v1 fallback. Live collection, runtime context, replay
consumers, proposal filters, and strategy behavior remain out of scope.

## Decisions implemented

- Kept the Phase 25 schema-v1 module and its files untouched; v2 lives in the
  focused `src/backtest/snapshot_v2.py` module.
- Used frozen Pydantic contracts with UTC-aware timestamps and `Decimal`
  financial values. OHLCV follows its declared timeframe grid, Funding is a
  settled contiguous UTC 8h series, and OI is a contiguous UTC 1h series with
  explicit venue-retention coverage.
- Derived generation identity from canonical normalized data/provenance bytes.
  The manifest itself is non-recursive and cross-checks hashes, sizes, and row
  counts for the four allowlisted data files.
- Made visibility copy-on-write: stage, production-read validate, finalize,
  validate, then atomically replace `CURRENT`. Same-content concurrent commits
  are validated and reused; committed generations are never overwritten or
  automatically deleted.
- Made reads fail closed on corrupted/noncanonical content, partial or unknown
  files, traversal-like ids, direct or dangling symlinks, bad grids/ranges, and
  manifest/metadata provenance mismatch.
- Kept predicted funding, raw exchange responses, credentials, and live
  fallback outside the persistence model.

## Validation

- Before source edits: `tests/test_backtest_snapshot.py` — 27 passed.
- Final schema-v1/v2 snapshot regression — 84 passed.
- Focused v2 suite — 57 passed; `src/backtest/snapshot_v2.py` 84% coverage.
- Existing snapshot-script consumers — 54 passed.
- Full repository regression — 2518 passed in 43.52 seconds.
- Generated-file Black and Ruff checks passed.
- `uv run mypy src` — 109 source files, zero issues.
- `git diff --check` passed; no generated duplicate or new-file trailing
  whitespace was found.
- Changed-path review confirmed no `data/`, dependency, configuration,
  credential, migration, deployment, runtime, proposal, strategy, or dashboard
  mutation from this slice.

## Compatibility and safety

Existing `load_snapshot`, `save_snapshot`, `SnapshotExchange`, directory
naming, freshness, and error behavior are unchanged. Existing v1 root files are
neither modified nor automatically upgraded. A present but corrupt v2
generation fails loudly; absence of `CURRENT` alone selects the v1 reader.

The user-owned `.claude/settings.local.json` modification and
`.claude/scheduled_tasks.lock` file were preserved and excluded. DEBT-081
continues to own unrelated repository-wide Black/Ruff drift; no new debt item
was required.

## Remaining sequence

1. Runtime `DerivativesContextService` and `MarketContext` plumbing.
2. LC-11 snapshot-backed no-lookahead replay/robustness integration.
3. Proposal Funding+OI regime filter, then separately evidence-gated
   Funding-Extreme MR.

FR-046 and US-025 remain Partial until the later runtime and replay consumer
slices are complete.

## Independent Build & Test evidence — 2026-07-19

- Code Generation approval recorded as `승인, 다음단계 진행`.
- `uv lock --check`: 91 packages resolved; no lock/dependency mutation.
- `python -m compileall -q src/backtest`: passed.
- Generated `SnapshotV2`, manifest, reader, and writer imports: passed.
- Schema-v1/v2 unit/contract/security suite: 84 passed in 3.05 seconds;
  generated module statement coverage 84% (474 statements, 74 missed).
- Snapshot plus atomic-write integration: 102 passed in 3.26 seconds.
- Existing v1 snapshot-script consumers: 54 passed in 28.36 seconds.
- Full repository regression: 2518 passed in 44.72 seconds.
- Generated-file Black/Ruff: passed; repository-wide mypy: 109 source files,
  zero issues.
- Repository-wide Black/Ruff still reports exactly the DEBT-081 baseline:
  20 format candidates and 22 findings in four scripts. Neither generated
  Slice 2 file overlaps.
- Diff, new-file whitespace, duplicate-file, network-import, sensitive-source,
  dependency, configuration, deployment, and `data/` scope scans passed.
- The test-only `secret.json` string is an unknown-file allowlist rejection
  sentinel, not a credential or persisted secret.

## Build & Test applicability and handoff

- Performance acceptance benchmark: N/A because LC-10 has no defined
  latency/throughput target.
- E2E: N/A until LC-11 provides a snapshot-backed promotion/robustness
  consumer.
- Operations/deployment: N/A; no deployable artifact, process, migration,
  infrastructure, production configuration, or runtime data refresh exists.
- No new technical debt was found. DEBT-081 remains the only active unrelated
  quality item.
- Build & Test approval: `승인, 다음단계 진행` on 2026-07-19.
- Cross-check: PASS for LC-10 at
  `docs/cross-checks/2026-07-19-backtesting-validation-derivatives-snapshot-v2.md`.
- Next bounded slice: runtime `DerivativesContextService`.

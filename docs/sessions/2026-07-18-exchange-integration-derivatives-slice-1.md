# Session: exchange-integration Derivatives Data Slice 1

**Date:** 2026-07-18

**Unit:** `exchange-integration`

**Stage:** Build and Test

**Status:** Build & Test approved; Slice 1 sealed and cross-checked

## Scope

Generated the first bounded FR-046 / US-025 implementation slice: immutable
Funding/OI domain contracts, backward-compatible exchange capability methods,
and Binance public current/history normalization. Runtime collection,
persistence, consumer logic, deployment, and live trading behavior were kept
out of scope.

## Decisions implemented

- Existing venues remain source compatible through concrete default
  unsupported methods rather than new abstract requirements.
- Binance is the only v1 supporting venue; Bybit fails with the stable
  `unsupported_venue` code.
- Public Binance construction omits empty credential keys while preserving the
  existing credentialed configuration shape.
- Funding accepts signed finite Decimal values and requires a contiguous UTC
  8h history grid.
- OI accepts non-negative finite Decimal values and requires a contiguous UTC
  1h returned suffix. Older unavailable prefixes are explicit retention
  metadata, not fabricated points.
- Pagination advances from the last record actually received plus one grid
  step, de-duplicates overlaps, respects inclusive `until`, and does not infer
  progress from the requested page size.
- Raw ccxt payloads are adapter-local; public errors are sanitized and carry
  stable codes.

## Validation

- Exchange baseline before edits: 165 passed.
- Focused Binance/domain tests: 105 passed.
- Complete exchange tests: 221 passed.
- Full repository tests: 2461 passed in 38.61 seconds.
- Black and Ruff passed for all changed Python files.
- `uv run mypy src/exchange`: 7 files, zero issues.
- `uv run mypy src`: 108 files, zero issues.
- `git diff --check` passed; no duplicate generated Python files were found.

## Independent Build & Test evidence

- `uv lock --check`: passed; 91 packages resolved without lock mutation.
- `python -m compileall -q src/exchange` and generated imports: passed.
- Verified environment: Python 3.13.0, uv 0.7.15, ccxt 4.5.51,
  Pydantic 2.13.3, pytest 9.0.2, Black 26.3.1, Ruff 0.15.9, mypy 1.20.0.
- Five exchange suites with coverage: 221 passed in 1.95 seconds;
  `src.exchange` 87%, `src/exchange/derivatives.py` 92%.
- Full repository regression: 2461 passed in 36.39 seconds.
- Slice 1 changed-file Black and Ruff: passed for all nine Python files.
- Repository-wide `mypy src`: 108 source files, zero issues.
- `git diff --check`: passed; no duplicate generated file, raw `info` boundary
  access, `data/`, or `strategies/` change found.
- No live network, credential, order, runtime-data, migration, dependency, or
  deployment action was used.

## Compatibility and debt

No runtime/proposal/strategy/backtest/dashboard/data/deployment path changed.
No dependency, migration, or production configuration was introduced. Existing
trading operations are unaffected because this slice only adds an opt-in data
boundary and does not instantiate or schedule a collector.

Repository-wide Black/Ruff checks exposed committed baseline drift unrelated
to this slice: 20 files would be reformatted and four scripts contain 22 Ruff
findings. The nine Slice 1 files are clean. The existing gap is registered as
DEBT-081 under `quality-governance` rather than mixed into this trading slice.

The existing user-owned `.claude/settings.local.json` modification and
`.claude/scheduled_tasks.lock` untracked file were preserved.

## Remaining sequence

1. Snapshot schema v2 — Code Generation plan pending approval.
2. Runtime `DerivativesContextService` and strategy plumbing.
3. Snapshot-only replay/robustness integration.
4. Separately designed proposal Funding+OI filter, then Funding-Extreme MR.

## Approval and cross-check

- Build & Test approval: `승인, 다음단계 진행` on 2026-07-18.
- Operations is N/A: the repository Operations rule is a placeholder and this
  Slice has no deployable service, migration, or runtime process.
- Unit cross-check:
  `docs/cross-checks/2026-07-18-exchange-integration-derivatives-slice-1.md`.
- Cross-check verdict: PASS for Slice 1; FR-046 / US-025 remain Partial across
  the planned later slices.

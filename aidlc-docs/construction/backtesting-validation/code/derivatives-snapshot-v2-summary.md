# Derivatives Data Slice 2 Code Generation Summary

**Primary unit:** `backtesting-validation`

**Secondary units:** `exchange-integration`, `persistence-data-integrity`

**Stage:** Code Generation Part 2

**Status:** Generated; explicit operator review pending

## Scope generated

Slice 2 implements LC-10: a deterministic schema-v2 snapshot store for one
coherent OHLCV, settled Funding, and Open Interest bundle. It adds immutable
content-addressed generations, manifest validation, atomic visibility, pinned
reads, and schema-v1 negotiation. It does not collect live data or wire replay,
runtime context, proposal filters, or strategies.

## Storage contract

```text
<symbol-timeframe-directory>/
├── CURRENT
└── generations/
    └── <64-lowercase-hex-generation-id>/
        ├── ohlcv.csv
        ├── funding.csv
        ├── open_interest.csv
        ├── metadata.json
        └── manifest.json
```

- `CURRENT` is one validated generation id plus LF and is replaced only through
  `atomic_write_text` after the staged and finalized generation both validate.
- The generation id is derived from canonical data/provenance bytes. Identical
  inputs produce the same id and byte-identical files.
- `manifest.json` records the exact four-file allowlist, SHA-256, byte size,
  and CSV row counts; `metadata.json` records schema version 2 and per-series
  coverage/provenance.
- CSV/JSON readers fail closed on noncanonical bytes, corrupt integrity,
  unknown/missing files, incoherent ranges/counts, off-grid/duplicate/gapped
  timestamps, future records, invalid ids, and symlink/path violations.
- Existing root-level schema-v1 files are never rewritten. With no `CURRENT`,
  the versioned reader delegates to the unchanged v1 loader and reports
  derivatives as explicitly unavailable.
- Only settled `FundingRate` values are accepted; predicted funding and raw
  exchange payloads have no serialization path.

## Publication and replay behavior

- Writers publish to an unreferenced same-root staging directory, validate it
  with the production reader, finalize it under its content id, validate again,
  and then update `CURRENT`.
- Every injected failure before pointer replacement preserves the prior
  selected generation. Unreferenced staging/finalized directories are ignored.
- A valid same-id generation is reused, including a concurrent same-content
  commit; a corrupt same-id generation is rejected rather than overwritten.
- Readers select only the pinned id or the single id read from `CURRENT`; they
  never scan by mtime or silently fall back from a corrupt v2 generation.

## Files

Created:

- `src/backtest/snapshot_v2.py`
- `tests/test_backtest_snapshot_v2.py`
- `aidlc-docs/construction/backtesting-validation/code/derivatives-snapshot-v2-summary.md`
- `docs/sessions/2026-07-18-backtesting-validation-derivatives-snapshot-v2.md`

Modified for lifecycle tracking:

- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/plans/backtesting-validation-code-generation-plan.md`
- `aidlc-docs/audit.md`

Intentionally unchanged:

- `src/backtest/snapshot.py` and `tests/test_backtest_snapshot.py`
- `data/`, runtime, proposal, strategy, dashboard, configuration, dependency,
  migration, credential, and deployment paths

## Code Generation verification evidence

- Pre-edit schema-v1 baseline: 27 passed.
- Schema-v1 plus v2 snapshot suites: 84 passed.
- Snapshot-v2 focused suite: 57 passed; generated module coverage 84%.
- Unchanged v1 snapshot-script consumers: 54 passed.
- Complete repository suite: 2518 passed in 43.52 seconds.
- Black and Ruff: clean on both generated Python files.
- Mypy: 109 source files, zero issues.
- `git diff --check`: clean; new files also have no trailing whitespace.
- No `_new.py` / `_modified.py` duplicate, runtime `data/`, dependency,
  credential, migration, deployment, or production configuration change.

## Compatibility, debt, and remaining work

No current backtest or trading behavior changes because existing consumers
still use the unchanged schema-v1 API. FR-046 and US-025 remain Partial.
LC-11 must later add snapshot-backed derivatives replay and per-bar no-lookahead
context construction. Runtime `DerivativesContextService`, proposal-layer
Funding+OI filtering, and Funding-Extreme MR remain later separately reviewed
slices.

No new technical debt was introduced. Repository-wide Black/Ruff baseline
drift remains isolated under DEBT-081 and was not mixed into this slice. After
independent Build & Test approval, the Slice 2 cross-check recorded PASS for
LC-10 while retaining FR-046/US-025 Partial.

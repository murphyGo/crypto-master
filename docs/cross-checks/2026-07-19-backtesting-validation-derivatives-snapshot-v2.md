# Cross-Check: backtesting-validation Derivatives Snapshot Schema v2

## Verdict

**PASS for the approved Slice 2 / LC-10 boundary.**

Snapshot Schema v2 implements and verifies the immutable persistence,
integrity, atomic visibility, pinned identity, strict read, and schema-v1
negotiation contract. FR-046 and US-025 correctly remain Partial because live
context collection and LC-11 per-bar replay are later slices.

## Scope

- **Primary unit:** `backtesting-validation`
- **Secondary units:** `exchange-integration`, `persistence-data-integrity`
- **Implementation:** `src/backtest/snapshot_v2.py`
- **Tests:** `tests/test_backtest_snapshot_v2.py`, legacy snapshot and
  atomic-write/consumer regression suites
- **Approved boundary:** LC-10 persistence only; no live collector, runtime
  `MarketContext`, proposal/strategy consumer, LC-11 replay, dashboard,
  deployment, or runtime-data change

## Requirements matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| FR-046 | Partial as planned | Settled Funding/OI persistence and deterministic identity are complete; runtime decision context and historical per-bar replay remain later slices. |
| NFR-006 | Complete for Slice 2 | Structured canonical CSV/JSON generations, manifest integrity, immutable identity, and reproducible pinned reads are implemented and tested. |
| DD-NFR-008 | Complete for LC-10 | Staged production-reader validation, all-or-nothing `CURRENT`, exact allowlist, hash/size/count checks, rollback, corruption failure, OI retention metadata, and v1 fallback are verified. Full fetch-to-snapshot requested-range integration remains with the later collector wiring. |
| DD-NFR-009 | Partial as planned | Canonical bytes, content id, future-point rejection, pinned generations, and offline tests are complete. `MarketContext.as_of` slicing and identical strategy/gate decisions remain LC-11. |
| DD-NFR-011 | Complete for persistence boundary | Only normalized OHLCV/settled Funding/OI and provenance are serialized; source contains no credential, raw venue payload, venue `info`, or predicted-funding path. |
| DD-NFR-012 | Complete for Slice 2 | Focused v2 module/tests, unchanged schema-v1 API, temporary-directory isolation, Black/Ruff/mypy compliance, and no dependency/configuration change. |

## Story matrix

| Story | Status | Evidence |
|-------|--------|----------|
| US-002 | Complete for Slice 2 contribution | Backtest input artifacts gain integrity-checked, reproducible versioned identity without changing existing consumers. |
| US-025 | Partial as planned | Snapshot persistence is complete; runtime `MarketContext` consumption and LC-11 replay are explicitly deferred. |

## Implementation evidence

- Frozen `SnapshotSeriesMetadata`, `SnapshotV2Metadata`, manifest, bundle, and
  versioned view contracts validate exact series provenance and availability.
- Canonical CSV/JSON codecs feed a 64-lowercase-hex content-derived generation
  id; the manifest records the exact four-file allowlist and integrity values.
- `save_snapshot_v2` uses same-root unreferenced staging, production-reader
  validation before and after finalization, and `atomic_write_text` for the
  sole `CURRENT` visibility transition.
- `load_snapshot_versioned` reads one pinned/current generation, rejects
  malformed paths/content, never scans by mtime, and delegates to the unchanged
  v1 loader only when `CURRENT` is absent.
- Same-id concurrent content is revalidated before reuse; corrupt same-id
  content fails rather than being overwritten.

## Test evidence

- Cross-check rerun: schema-v1/v2 snapshots — 84 passed in 1.68 seconds.
- Build & Test focused run: 84 passed in 3.05 seconds; generated module 84%
  statement coverage.
- Snapshot plus shared atomic-write integration: 102 passed in 3.26 seconds.
- Existing schema-v1 script consumers: 54 passed in 28.36 seconds.
- Complete repository regression: 2518 passed in 44.72 seconds.
- Generated-file Black/Ruff passed; repository-wide mypy passed for 109 source
  files; lock, compilation, imports, diff/path/security scans passed.

## Gaps and risks

- No blocking gap exists inside the approved LC-10 boundary.
- The later fetch/refresh integration must prove the complete requested settled
  Funding range flows from the Slice 1 adapter into the snapshot without loss;
  this cannot be an end-to-end assertion before a collector is wired.
- LC-11 must prove `MarketContext.as_of` excludes every future Funding/OI record
  and pins the generation id in promotion-relevant output.
- No performance acceptance target exists for the offline store; no latency or
  throughput claim is made.
- Repository-wide Black/Ruff drift remains the unrelated active DEBT-081. The
  generated Slice 2 files are clean and no new debt was found.

## Unit and debt mapping

- **Primary unit:** `backtesting-validation`
- **Secondary units:** `exchange-integration`, `persistence-data-integrity`
- **Related debt:** DEBT-081 is unrelated and remains active under
  `quality-governance`; no Slice 2 debt added.
- **Legacy phase context:** Phase 21 UTC/Decimal contracts, Phase 22 atomic
  writes, Phase 25 deterministic schema-v1 snapshots, resolved DEBT-043 and
  DEBT-080 precedents.

## Operations applicability

Operations is N/A. The repository Operations rule is a placeholder and ends
the current workflow after Construction Build & Test. Slice 2 adds no
deployable service, process, migration, credentials, infrastructure, runtime
data refresh, or production configuration.

## Recommendations

1. Seal Slice 2 as PASS for LC-10 while retaining FR-046/US-025 Partial.
2. Generate the runtime `DerivativesContextService` slice with its approved
   cache/deadline/budget/degradation contracts.
3. Follow with LC-11 snapshot-backed no-lookahead replay and end-to-end
   requested-range/pinned-result tests.
4. Keep proposal Funding+OI filtering and Funding-Extreme MR as later,
   separately evidence-gated consumer slices.

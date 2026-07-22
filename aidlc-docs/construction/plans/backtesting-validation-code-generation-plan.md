# Code Generation Plan: backtesting-validation

## Migration Status

Legacy Phase work is migrated as brownfield-complete. This plan is not a queue
of unfinished historical tasks.

## Source Legacy Components

| Component | Phase | Secondary Unit |
|-----------|-------|----------------|
| Backtesting | 5 | |
| Performance Analyzer | 5 | `strategy-framework` |
| Robustness Validation Gate | 5 | `strategy-framework` |
| Feedback Loop | 5 | `ai-feedback-loop` |
| Multi-Timeframe Strategy Support | 9 | `strategy-framework` |
| Multi-Timeframe Backtester | 9 | `strategy-framework` |
| Baseline Reference Numbers | 10 | |
| Volume-Aware Default Paths | 10 | `persistence-data-integrity` |
| BaseExchange.get_ohlcv `since` Parameter | 13 | `exchange-integration` |
| Auto-Research Operator Workflow + Catalog-Aware Improver | 17 | `ai-feedback-loop` |
| Auto-Research Workflow Unblock | 17 | `ai-feedback-loop` |
| Strategy-Combination A/B Backtest Harness | 19 | `sub-account-capital-segmentation` |
| PnL Convention Single Source | 20 | `trading-core` |
| Backtest / Portfolio Leverage Math Alignment | 20 | `trading-core` |
| Phase 5.4+ Baseline Re-computation | 20/25 | |
| Strategy Robustness Polish | 24 | `strategy-framework` |
| Snapshot Dataset + Format | 25 | `persistence-data-integrity` |
| `--snapshot` CLI Flag + Script Changes | 25 | |
| First Run + Populate `docs/baselines.md` | 25 | |
| Backtester Liquidation Parity | 26 | `trading-core` |

## Completed Code Generation Steps

- [x] Implement backtest engine, analyzer, robustness validator, and baseline reporting.
- [x] Add multi-timeframe and per-strategy backtest support.
- [x] Add deterministic snapshot dataset format and `--snapshot` CLI support.
- [x] Align backtest leverage/liquidation behavior with trading and portfolio math.
- [x] Add strategy-combination A/B harness and operator baseline runbook behavior.
- [x] Enable auto-research catalog picks to exercise the robustness sensitivity gate.
- [x] Verify code-type auto-research strategies can emit signals that produce backtest trades.
- [x] Add cumulative parse-failure-rate breaker for intermittent LLM parse failures.

## Evidence

- Requirements: FR-005, FR-025, FR-026, FR-034, FR-038, NFR-006.
- Primary paths: `src/backtest/`, `scripts/backtest_*`, `data/backtest/`, `docs/baselines.md`, `tests/test_backtest_*`.
- Cross-checks: phase 5, phase 9, phase 10, phase 17, phase 19, phase 20, phase 24, phase 25, and phase 26 reports.
- Session logs: related Phase 5, 9, 10, 13, 17, 19, 20, 24, 25, and 26 entries under `docs/sessions/`.

## Future Work

Add future backtest, reproducibility, baseline, robustness, or validation work
as new unchecked steps here.

### DEBT-080: `fetch_ohlcv_window` pagination holes (2026-07-17)

Related: DEBT-080 (`docs/TECH-DEBT.md`), FR-025/FR-026/FR-034, NFR-006.
Discovery: 2026-07-17 `/strategy-gen` sweep — `since`-anchored Binance pages
return at most 1000 bars while the paginator assumes the full 1500-bar request
is honored, leaving ~500-bar holes per backward page on >1500-bar windows.

- [x] Fix backward pagination in `scripts/backtest_baselines.py::fetch_ohlcv_window`
      to advance by bars actually received (span-fill walk), so >1500-bar
      windows come back contiguous. Verify:
      `uv run pytest tests/test_scripts_backtest_baselines.py -q`.
- [x] Add a loud contiguity check (`ValueError` naming symbol/timeframe/first
      hole) applied to both the single-page and paginated return paths.
- [x] Regression tests in `tests/test_scripts_backtest_baselines.py`: a fake
      exchange capping `since` pages at 1000 (mirrors real Binance) must yield
      a full contiguous window; venue-side data holes must raise; short
      history must return all available bars without raising.
- [x] Consumer regression: `uv run pytest tests/test_run_robustness_gate.py
      tests/test_scripts_backtest_combinations.py tests/test_scripts_auto_research_candidates.py -q`.
- [x] Docs/debt closeout: TECH-DEBT resolution entry, debt-unit-map cleanup,
      session log `docs/sessions/2026-07-17-backtesting-validation-debt-080-pagination-fix.md`.

## Completed Future Work: Derivatives Data Slice 2 — Snapshot Schema v2

## Plan authority

This section is the single source of truth for Snapshot Schema v2 Code
Generation. It implements LC-10 only: immutable snapshot generations,
manifest validation, atomic visibility, and schema-v1 negotiation. It does not
wire live collection, runtime `MarketContext`, snapshot-backed strategy replay,
robustness consumers, proposal filters, or new strategies.

## Unit generation context

- **Primary Unit:** `backtesting-validation`
- **Secondary Units:** `exchange-integration`, `persistence-data-integrity`
- **Stage:** Code Generation — Part 1 planning / Slice 2 generation
- **Task:** Extend the Phase 25 OHLCV snapshot format with deterministic,
  immutable Funding/OI generations while preserving schema-v1 readers.
- **Workspace Root:** `/Users/user/Desktop/Projects/crypto-master`
- **Project Type:** Brownfield Python modular monolith.
- **Related Requirements:** FR-046, NFR-006, DD-NFR-008, DD-NFR-009,
  DD-NFR-011, DD-NFR-012.
- **Related Stories:** US-002, US-025.
- **Related Legacy / Debt:** Legacy Phases 21, 22, and 25; resolved DEBT-043
  deterministic snapshot foundation; resolved DEBT-080 actual-record
  pagination precedent; active DEBT-081 is unrelated quality-governance work.
- **Design Inputs:** NDP-06/NDP-07 and LC-10/11 under
  `aidlc-docs/construction/exchange-integration/nfr-design/`, plus the approved
  snapshot-v2 entity contract in `functional-design/domain-entities.md`.

## Ownership, dependencies, and boundaries

- Existing schema-v1 `Snapshot`, `SnapshotMetadata`, `load_snapshot`,
  `save_snapshot`, and `SnapshotExchange` behavior remains compatible.
- Slice 1 `FundingRate`, `OpenInterestPoint`, and `OpenInterestHistory` are the
  only derivatives values accepted at the persistence boundary.
- `atomic_write_text` is the only visibility-pointer write mechanism.
- Snapshot publication writes only caller-selected directories. Tests use
  `tmp_path`; repository `data/` is not created, migrated, refreshed, or
  deleted.
- Predicted funding is never accepted or serialized.
- No network/exchange call belongs in the v2 store. A later collector/refresh
  slice assembles normalized values and calls this store.
- No automatic committed-generation retention or deletion is introduced.

## Expected source and test paths

### Create

- `src/backtest/snapshot_v2.py` — focused v2 models, canonical codecs,
  immutable generation reader/writer, and version-negotiating read view.
- `tests/test_backtest_snapshot_v2.py` — v2 round-trip, integrity, security,
  rollback, determinism, and v1 fallback tests.
- `aidlc-docs/construction/backtesting-validation/code/derivatives-snapshot-v2-summary.md`
- `docs/sessions/2026-07-18-backtesting-validation-derivatives-snapshot-v2.md`

### Modify in place

- `src/backtest/snapshot.py` — narrow public export/legacy adapter seam only if
  needed; existing v1 functions and `SnapshotExchange` semantics stay intact.
- `tests/test_backtest_snapshot.py` only for explicit v1 compatibility pins.
- `aidlc-docs/aidlc-state.md`
- this construction plan

### Explicitly not touched

- `src/runtime/`, `src/proposal/`, `src/strategy/`, `src/dashboard/`
- `strategies/`, `data/`, configuration, deployment, and credentials
- live snapshot refresh/fetch orchestration, `MarketContextBuilder`,
  `SnapshotExchange` derivatives consumption, robustness/report pinning,
  proposal filters, and Funding-Extreme MR

## On-disk contract

Under an existing Phase 25 `<SYMBOL>__<timeframe>/` directory, schema v2 adds:

```text
CURRENT
generations/<64-lowercase-hex-generation-id>/
  ohlcv.csv
  funding.csv
  open_interest.csv
  metadata.json
  manifest.json
```

- Existing root-level v1 `ohlcv.csv` and `metadata.json` are never rewritten by
  the v2 writer.
- `CURRENT` contains one validated generation id plus LF.
- Manifest file keys are exactly `ohlcv.csv`, `funding.csv`,
  `open_interest.csv`, and `metadata.json`; entries include SHA-256, byte size,
  and CSV row count (`null` for metadata).
- CSV headers are fixed and ordered: existing OHLCV header,
  `timestamp,rate`, and
  `timestamp,open_interest,open_interest_value`.
- Metadata schema version is exactly 2 and records normalized source/symbol/
  timeframe/created time plus requested/actual bounds, fetched time,
  granularity, point count, funding interval, and OI retention state per
  series.
- Canonical UTF-8, LF, Decimal string, UTC ISO-8601, sorted-key JSON encodings
  feed the content-derived generation id.

## Executable generation steps

### Step 1 — Approval and baseline guard

- [x] Record explicit operator approval of this entire Slice 2 plan in
  `aidlc-docs/audit.md` before application code changes.
- [x] Preserve the existing `.claude/settings.local.json` modification and
  `.claude/scheduled_tasks.lock` file.
- [x] Run the v1 snapshot baseline:
  `uv run pytest tests/test_backtest_snapshot.py`.
- [x] Inspect the exact starting diff and confirm no `data/` mutation.

### Step 2 — Generate frozen schema-v2 contracts

- [x] Add frozen manifest, manifest-entry, per-series metadata, v2 metadata,
  and versioned snapshot bundle models in `src/backtest/snapshot_v2.py`.
- [x] Accept immutable OHLCV, settled funding, and OI sequences only; reject
  symbol/range/count/granularity mismatches, duplicates, gaps, future points,
  non-8h funding, and non-1h OI before publication.
- [x] Represent v1 derivatives as explicitly unavailable, never as fabricated
  empty-success context.

### Step 3 — Generate canonical codecs and stable identity

- [x] Serialize the three fixed CSV files with canonical headers, UTC ISO-8601,
  Decimal strings, empty optional OI value cells, and LF newlines.
- [x] Serialize metadata/manifest as canonical UTF-8 JSON with sorted keys and
  deterministic separators/newline policy.
- [x] Derive a 64-character lowercase hexadecimal generation id from normalized
  data/provenance bytes; identical inputs must produce byte-identical files and
  the same id.
- [x] Compute and record SHA-256, byte size, and row count for every allowlisted
  normalized file; never include `manifest.json` recursively in its own map.

### Step 4 — Generate staged immutable publication

- [x] Write all files into an unreferenced, same-root staging generation and
  validate it with the production reader before visibility changes.
- [x] Finalize only to `generations/<generation-id>` without overwriting a
  different committed generation; an existing same-id generation must validate
  identically before reuse.
- [x] Atomically replace `CURRENT` through `atomic_write_text` only after the
  committed generation validates.
- [x] On every pre-pointer failure, leave the previous `CURRENT` readable and
  never fall back to or expose staging content.

### Step 5 — Generate strict v2 reader and path security

- [x] Read `CURRENT` once or accept an explicitly pinned generation id; validate
  the 64-hex pattern and resolve beneath `generations/`.
- [x] Reject traversal, absolute paths, symlinks escaping the root, unknown or
  missing files, schema mismatch, hash/size/count mismatch, noncanonical
  metadata, bad grids/ranges, and partial generations with one bounded
  `SnapshotValidationError` surface.
- [x] Load only the selected generation; never scan by mtime or choose a latest
  directory implicitly.
- [x] Return the validated generation id with the bundle so later reports can
  pin identity.

### Step 6 — Preserve schema-v1 negotiation

- [x] When `CURRENT` is absent, delegate to the existing v1 loader and return a
  versioned view with OHLCV available and derivatives explicitly unavailable.
- [x] Keep existing `load_snapshot`, `save_snapshot`, `SnapshotExchange`, Phase
  25 directory naming, freshness, and error behavior unchanged.
- [x] Do not modify or auto-upgrade existing v1 files during reads.

### Step 7 — Generate exhaustive storage tests

- [x] Add v2 round-trip tests for full data, empty Funding/OI series, OI null
  notional, exact metadata bounds/counts, and UTC/Decimal fidelity.
- [x] Add deterministic-byte/id, v1 fallback/no-mutation, explicitly pinned
  generation, and newer-CURRENT-does-not-change-pinned-read tests.
- [x] Add corruption tests for every allowlist, manifest, hash, size, row-count,
  metadata, order, duplicate, gap, range, and interval branch.
- [x] Add traversal/absolute/symlink escape tests for both `CURRENT` and pinned
  generation ids.
- [x] Inject failure after each writer phase and prove the prior `CURRENT`
  remains selected; prove staging/partial generations are ignored.

### Step 8 — Verify bounded compatibility and quality

- [x] Run `uv run pytest tests/test_backtest_snapshot.py
  tests/test_backtest_snapshot_v2.py`.
- [x] Run snapshot-script consumer regressions only where the unchanged v1 seam
  warrants them; record exact suites/counts.
- [x] Run Black and Ruff on changed Python files and `uv run mypy src`.
- [x] Run the complete repository pytest suite.
- [x] Run `git diff --check`, duplicate-file search, changed-path review, and
  confirm no runtime `data/`, credential, dependency, migration, or deployment
  mutation.
- [x] Classify unrelated DEBT-081 global Black/Ruff findings separately; do not
  mix its mechanical cleanup into this plan.

### Step 9 — Generate summaries and handoff

- [x] Write the code summary and implementation session log with exact storage
  contract, files, tests, compatibility, and remaining LC-11 integration.
- [x] Update AI-DLC state without marking FR-046 or US-025 complete.
- [x] Complete the unit cross-check after independent Build & Test evidence;
      PASS report recorded at
      `docs/cross-checks/2026-07-19-backtesting-validation-derivatives-snapshot-v2.md`.
- [x] Mark every completed generation step and present generated code for
  explicit review before Build & Test.

## Story and requirement completion boundary

| Story / requirement | Slice 2 planned outcome |
|---------------------|-------------------------|
| US-002 / NFR-006 | Versioned, integrity-checked structured snapshot artifact foundation |
| US-025 / FR-046 | Funding/OI deterministic persistence and version negotiation only; replay consumer remains pending |
| DD-NFR-008 | Immutable generations, manifest validation, atomic `CURRENT`, v1 fallback |
| DD-NFR-009 | Deterministic normalized bytes and pinned generation identity; per-bar no-look-ahead slicing remains LC-11 |
| DD-NFR-011 | Allowlisted normalized files only; no credential/raw response/predicted funding persistence |
| DD-NFR-012 | New focused module/tests, unchanged v1 interface, offline test isolation |

FR-046 and US-025 must remain Partial after this slice.

## Completion checklist

- [x] Entire Slice 2 generation plan explicitly approved and recorded.
- [x] Schema-v1 read/write/adapter compatibility preserved.
- [x] Schema-v2 contracts, canonical codecs, manifest, immutable writer, strict
  reader, and atomic visibility generated exactly as planned.
- [x] Hash/size/count, allowlist, path security, interval/range, deterministic
  identity, pinned-read, and phase-failure tests generated.
- [x] No live network, runtime, consumer, strategy, proposal, dashboard,
  configuration, deployment, dependency, migration, or `data/` mutation.
- [x] Targeted/full tests and format/lint/type evidence recorded.
- [x] Documentation, session, state, and Slice 2 PASS cross-check updated;
      DEBT-081 remains isolated.
- [x] Generated code presented for explicit approval before Build & Test.

## Active Future Work: Derivatives Data Slice 4 — Snapshot-Only Replay

## Plan authority

This section is the single source of truth for LC-11 Code Generation. It wires
the already sealed Snapshot Schema v2 and runtime `MarketContextBuilder` into
the backtester, combination harness, and robustness/promotion path. It also
closes the bounded Slice 2 collector-to-snapshot gap through an explicit
operator refresh command. It does not add Funding/OI signal thresholds, a
proposal filter, a new strategy, funding-cost accounting, live runtime
persistence, or automatic snapshot refresh.

## Unit generation context

- **Primary Unit:** `backtesting-validation`
- **Secondary Units:** `exchange-integration`, `strategy-framework`,
  `persistence-data-integrity`, `quality-governance`
- **Stage:** Code Generation — Part 1 planning / Slice 4 generation
- **Task:** Reconstruct deterministic Funding/OI `MarketContext` from one
  pinned Snapshot v2 generation at every historical decision boundary and
  fail promotion closed when a context-required strategy cannot be evaluated.
- **Workspace Root:** `/Users/user/Desktop/Projects/crypto-master`
- **Project Type:** Brownfield Python modular monolith.
- **Related Requirements:** FR-025, FR-026, FR-027, FR-046, NFR-006,
  NFR-009, DD-NFR-008, DD-NFR-009, DD-NFR-011, DD-NFR-012.
- **Related Stories:** US-002, US-025.
- **Related Legacy / Debt:** Legacy Phases 5, 9, 19, 25, and 26; resolved
  DEBT-043 deterministic snapshots and DEBT-080 actual-record pagination;
  active DEBT-081 remains unrelated repository-wide formatting/lint drift.
- **Design Inputs:** functional-design Flows 1 and 3, business rules R1-R4 and
  R7, NDP-06/NDP-07, LC-08/10/11, and the approved Slice 2/3 cross-check
  follow-ups.

## Locked behavior and service boundaries

- A new read-only replay source loads `load_snapshot_versioned(...)` once,
  serves OHLCV and derivatives from that same selected generation, and exposes
  the exact schema version and generation id. It never scans by mtime and never
  calls an exchange.
- Snapshot v2 Funding/OI values are converted to immutable `SeriesSnapshot`
  inputs and passed to the existing pure `MarketContextBuilder`; the builder is
  not forked or reimplemented in `src/backtest/`.
- Every bar uses its UTC candle close as `as_of`. Records newer than that close
  are excluded; replay always supplies `predicted_funding_rate=None`.
- Schema v1 remains readable for legacy OHLCV-only strategies. It exposes no
  fabricated derivatives context, and a context-required robustness run ends
  as `INSUFFICIENT_DATA`.
- A context-required standalone backtest stays neutral while its declared
  requirements are unmet. An explicitly covered prefix may therefore be
  skipped until the first satisfiable bar. Once coverage becomes satisfiable,
  a later missing/stale gap is a loud replay failure for promotion use.
- The robustness gate evaluates only the contiguous context-covered suffix for
  a context-required strategy. If no sufficiently long suffix exists, or if a
  later required-context gap appears, it returns `INSUFFICIENT_DATA` and
  `overall_passed=False`; this status is never treated like neutral `SKIPPED`.
- Existing optional/OHLCV-only strategies, legacy analyze signatures,
  single-/multi-timeframe routing, PnL, fees, slippage, liquidation, and gate
  thresholds remain behavior-compatible.
- Every promotion-relevant report records the pinned generation id, canonical
  configuration digest, and deterministic seed. A later `CURRENT` update
  cannot change an already loaded replay or its report identity.
- Snapshot refresh is an explicit CLI action. It fetches normalized OHLCV,
  settled Funding, and OI through the existing Binance adapter, validates the
  complete requested span/retention metadata, and calls `save_snapshot_v2`.
  Ordinary replay has no live fallback.
- No runtime `DerivativesContextService` cache is serialized. No background
  writer, scheduler, database, migration, dependency, credentialed endpoint,
  or production enablement is introduced.

## Expected source and test paths

### Create

- `src/backtest/snapshot_replay.py` — immutable Snapshot v1/v2 replay source,
  coverage validation, pinned provenance, and `MarketContextProvider` adapter.
- `src/backtest/reproducibility.py` — canonical configuration hashing and
  replay identity helpers shared by backtest results and gate reports.
- `tests/test_backtest_snapshot_replay.py` — source/coverage/no-look-ahead,
  v1 unavailability, parity, pinning, and deterministic metadata tests.
- `aidlc-docs/construction/backtesting-validation/code/derivatives-snapshot-replay-summary.md`
- `docs/sessions/2026-07-19-backtesting-validation-derivatives-snapshot-replay.md`

### Modify in place

- `src/backtest/__init__.py` — public replay exports only.
- `src/backtest/engine.py` — optional replay/provider plumbing, per-bar context
  evaluation, neutral-on-unmet accounting, and result provenance.
- `src/backtest/validator.py` — snapshot evaluation entry point,
  `INSUFFICIENT_DATA`, context-covered suffix selection, and report identity.
- `src/backtest/harness.py` — pass one pinned replay source through each
  strategy backtest and robustness call without changing legacy callers.
- `scripts/run_robustness_gate.py` — snapshot-default promotion mode, pinned
  generation selection, explicit v2 refresh mode, live exploratory labeling,
  and provenance-aware rendering.
- `tests/test_backtest_engine.py`
- `tests/test_backtest_multi_timeframe.py`
- `tests/test_backtest_validator.py`
- `tests/test_backtest_harness.py`
- `tests/test_run_robustness_gate.py`
- `tests/test_scripts_backtest_baselines.py` only if the shared OHLCV paginator
  needs a new collector regression; its v1 snapshot behavior remains intact.
- `aidlc-docs/aidlc-state.md`
- this construction plan

### Explicitly not touched

- `src/runtime/derivatives_context.py`, `src/runtime/engine.py`,
  `src/proposal/`, `src/dashboard/`, and existing runtime event contracts
- `strategies/`, proposal filter modes/thresholds, Funding-Extreme MR, and any
  other entry/exit or ranking logic
- funding payment/carry modeling in `src/backtest/engine.py`
- repository `data/`, deployment files, environment defaults, credentials,
  dependencies, database/schema migrations, and committed snapshot artifacts

## Public interfaces and entities to generate

### `SnapshotReplaySource`

- `from_directory(directory, *, generation_id=None)` loads one immutable
  `VersionedSnapshot` and validates replay coverage once.
- `schema_version`, `generation_id`, `symbol`, `timeframe`, and immutable
  `ohlcv` expose the selected dataset identity without mutable filesystem reads.
- `context_for(symbol, *, as_of, requirements=None)` implements the existing
  `MarketContextProvider` protocol through `MarketContextBuilder`.
- A schema-v1 source returns explicit no-context evaluation; schema v2 builds
  Funding/OI `SeriesSnapshot` inputs with replay-only predicted funding absent.
- The source rejects symbol/timeframe mismatch, required unflagged range gaps,
  post-OHLCV derivatives tails, and any contradictory retention/coverage
  metadata through the existing bounded snapshot validation surface.

### Replay and report provenance

- A frozen replay identity records schema version, optional 64-hex generation
  id, symbol, timeframe, and source.
- `BacktestResult` adds backward-compatible optional provenance fields plus
  context eligible/unmet bar counts; direct legacy model construction remains
  valid.
- `RobustnessReport` adds optional replay identity, configuration digest, seed,
  and ignored-prefix/context-coverage counts.
- The canonical digest is SHA-256 over sorted, normalized JSON containing the
  strategy identity, backtest config, robustness config, profile, symbol,
  timeframe, parameter grid, seed, and pinned replay identity. No absolute
  local path, wall-clock time, UUID, or secret enters the digest.

### Gate outcome

- `GateStatus.INSUFFICIENT_DATA = "insufficient_data"` is a promotion-blocking
  terminal outcome distinct from `SKIPPED`.
- The gate emits a `market_context` result naming stable unmet reasons and
  counts when a required strategy cannot obtain a contiguous usable replay
  suffix.
- `overall_passed` is true only when no gate is `FAILED` or
  `INSUFFICIENT_DATA`; existing optional-strategy `SKIPPED` behavior stays
  neutral.

## Executable generation steps

### Step 1 — Approval and baseline guard

- [x] Record explicit operator approval of this entire Slice 4 plan in
  `aidlc-docs/audit.md` before application code changes.
- [x] Preserve all current Slice 1-3 changes and the unrelated
  `.claude/settings.local.json` / `.claude/scheduled_tasks.lock` worktree state.
- [x] Capture `git status --short`, confirm no tracked `data/` mutation, and
  run the pre-change baselines:
  `uv run pytest tests/test_backtest_snapshot.py
  tests/test_backtest_snapshot_v2.py tests/test_backtest_engine.py
  tests/test_backtest_multi_timeframe.py tests/test_backtest_validator.py
  tests/test_backtest_harness.py tests/test_run_robustness_gate.py`.

### Step 2 — Generate the pinned replay source

- [x] Add `SnapshotReplaySource` and frozen replay identity models in
  `src/backtest/snapshot_replay.py`; load `CURRENT` once or the exact requested
  generation id and retain the validated bundle in memory for the whole run.
- [x] Serve primary OHLCV and Funding/OI only from that bundle; schema v1 keeps
  OHLCV but represents derivatives as unavailable without mutation or upgrade.
- [x] Validate requested/actual range relationships against the OHLCV replay
  span, allow only explicitly described prefix truncation, and reject silent
  internal/suffix gaps before a promotion run.
- [x] Convert v2 series to `SeriesSnapshot` values and delegate every
  `as_of` slice/age/requirement decision to the sealed
  `MarketContextBuilder`; never duplicate builder logic.

### Step 3 — Generate no-look-ahead replay semantics

- [x] At each primary candle close, exclude all later Funding/OI values and
  construct deterministic ascending context with predicted funding absent.
- [x] Preserve an explicitly uncovered prefix as neutral context until the
  first requirements-satisfied decision boundary; expose first eligible,
  eligible, and unmet counts for downstream validation.
- [x] Prove a source loaded with a pinned generation is unchanged after
  `CURRENT` moves, and prove identical normalized live-cache inputs and
  snapshot inputs produce byte-equivalent context payloads and identical
  context-required strategy decisions.

### Step 4 — Wire the backtest engine without legacy drift

- [x] Add an optional replay/provider seam through `run`,
  `run_multi_timeframe`, `run_for_strategy`, and `_execute_bar`; default `None`
  must preserve every existing call and output.
- [x] Use the strategy's typed `market_context_requirements`; skip analysis
  neutrally while required context is unmet, pass the optional keyword only to
  compatible analyze signatures, and keep existing parse/time-out breakers
  unchanged.
- [x] Attach pinned replay identity, stable backtest configuration digest,
  seed, and context coverage counters to `BacktestResult` and serialized JSON.
- [x] Keep multi-timeframe OHLCV slicing anchored to the primary candle while
  deriving derivatives `as_of` from the same primary close.

### Step 5 — Make robustness promotion fail honest

- [x] Add a snapshot-backed evaluation entry point that derives OHLCV and
  context from the same replay source and propagates it into baseline, OOS,
  walk-forward, and sensitivity sub-runs.
- [x] For a context-required strategy, find the first satisfied bar, trim only
  that explicit prefix, and reject no usable suffix, too-short coverage, v1
  context, or any later requirement gap as `INSUFFICIENT_DATA`.
- [x] Make `INSUFFICIENT_DATA` block `overall_passed`, surface stable unmet
  reason/count diagnostics, and preserve legacy `SKIPPED` semantics for
  unrelated low-trade/missing-grid checks.
- [x] Record generation id, canonical full gate configuration digest, seed,
  and context coverage in every snapshot-backed `RobustnessReport`.

### Step 6 — Carry replay through the combination harness

- [x] Add a backward-compatible optional replay-source map keyed by
  `(symbol, primary_timeframe)` to `BacktestHarness.run_sub_accounts`.
- [x] Pass the same pinned source into each selected strategy's backtest and
  robustness call; preserve the current OHLCV-only script/caller path when the
  map is absent.
- [x] Preserve generation identity on compatible combined results and fail
  loudly if an attempted combination mixes conflicting primary generations.

### Step 7 — Generate explicit collector-to-v2 refresh and snapshot CLI

- [x] Extend `scripts/run_robustness_gate.py` with mutually exclusive
  snapshot-default, explicit `--refresh-snapshot`, and explicit exploratory
  `--live` modes; snapshot load failure never falls through to live Binance.
- [x] In refresh mode, deduplicate `(symbol, timeframe)` specs, fetch the full
  OHLCV window, fetch settled Funding and OI for its requested replay bounds
  through existing actual-record pagination, validate OI retention metadata,
  assemble `SnapshotV2`, call `save_snapshot_v2`, print generation ids, and
  exit without running promotion gates.
- [x] Support exact pinned generation selection per strategy/pair and render
  generation id, configuration digest, seed, context coverage, and a distinct
  overall `INSUFFICIENT_DATA` label.
- [x] Keep live mode available only as clearly labeled exploratory evidence;
  a context-required live/unpinned run cannot be reported as promotion-passed.

### Step 8 — Generate focused unit, integration, and compatibility tests

- [x] Add replay-source tests for v1/v2 negotiation, exact generation pinning,
  moved `CURRENT`, coverage prefixes, OI retention, missing/suffix gaps,
  symbol/timeframe mismatch, predicted-funding absence, and no-look-ahead
  boundary timestamps.
- [x] Add engine tests for required neutral behavior, optional-strategy parity,
  legacy signature compatibility, context counters/provenance serialization,
  and single-/multi-timeframe identical decision boundaries.
- [x] Add robustness tests proving v1/missing/too-short/post-coverage gaps are
  `INSUFFICIENT_DATA`, that this outcome blocks promotion, that valid v2 replay
  reaches all gates, and that `SKIPPED` compatibility remains unchanged.
- [x] Add harness tests for source propagation, generation preservation,
  conflicting-generation rejection, and context-required false promotion.
- [x] Add hermetic CLI/collector tests with fake Binance reads for complete
  requested Funding/OI range transfer, OI retention, v2 publication, pinned
  selection, no live fallback, exploratory labeling, rendering, and no network.

### Step 9 — Verify deterministic and bounded quality

- [x] Run the focused Slice 4 suites and snapshot v1/v2 compatibility suites;
  record exact counts and generated-module coverage.
- [x] Run relevant proposal/runtime parity regressions to ensure the shared
  builder contract stayed sealed:
  `tests/test_strategy_market_context.py`,
  `tests/test_runtime_derivatives_context.py`, and
  `tests/test_proposal_engine.py`.
- [x] Run changed-file Black/Ruff, `uv run mypy src`, the complete repository
  pytest suite, `git diff --check`, compile/import checks, and duplicate/TODO/
  dependency/credential/deployment/data-mutation scans.
- [x] Classify unrelated DEBT-081 global Black/Ruff findings separately and do
  not mix mechanical cleanup into Slice 4.

### Step 10 — Generate evidence and stop at the review boundary

- [x] Write the code summary and implementation session log with exact replay,
  collector, provenance, compatibility, tests, and no-network evidence.
- [x] Update AI-DLC state and plan checkboxes. FR-046/US-025 and LC-11 become
  eligible for Complete only after independent Build & Test and cross-check,
  never merely because Code Generation finished.
- [x] Present the generated code and verification evidence for explicit review
  before entering Construction Build & Test.

## Story and requirement completion boundary

| Story / requirement | Slice 4 planned outcome |
|---------------------|-------------------------|
| US-002 / NFR-006 | Structured results pin replay identity, canonical configuration digest, seed, and context coverage |
| US-025 / FR-046 | Explicit collector-to-v2 path plus runtime/replay parity and context-required historical decisions; eligible for completion after independent verification |
| FR-025 / FR-026 / FR-027 | Backtests and promotion gates consume the same immutable source; insufficient derivatives evidence blocks promotion honestly |
| DD-NFR-008 | Strict v1/v2 negotiation and exact committed generation pinning carried into consumers |
| DD-NFR-009 | Per-bar no-look-ahead, deterministic context/decision parity, no live fallback, stable digest/seed evidence |
| DD-NFR-011 | Normalized allowlisted values only; no predicted funding, credential, raw response, or path leakage in reports |
| DD-NFR-012 / NFR-009 | Focused replay module and optional seams preserve legacy callers and avoid new dependencies |

Slice 5 proposal filtering and the later Funding-Extreme MR strategy remain
separate hypothesis/evidence-gated work even if FR-046/US-025 close after this
slice.

## Completion checklist

- [x] Entire Slice 4 generation plan explicitly approved and recorded.
- [x] One immutable source serves OHLCV and derivatives from an exact pinned
  generation with no future records or predicted funding in replay.
- [x] Backtester and harness preserve optional/OHLCV-only behavior while
  context-required strategies neutralize honest missing-prefix decisions.
- [x] Robustness promotion distinguishes and blocks `INSUFFICIENT_DATA`.
- [x] Report generation id, canonical config digest, seed, and coverage are
  deterministic and serialized.
- [x] Explicit refresh proves adapter-to-Snapshot-v2 requested-range transfer;
  ordinary replay remains offline with no live fallback.
- [x] No proposal filter, strategy threshold, Funding-Extreme MR, funding-cost
  math, runtime cache persistence, data artifact, dependency, migration,
  credential, or deployment change.
- [x] Targeted/full tests, formatting, lint, type, security, and generated-code
  evidence recorded; DEBT-081 remains isolated. Independent cross-check stays
  in Build & Test.
- [x] Generated code presented for explicit approval before Build & Test.

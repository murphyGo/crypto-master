# Build and Test Plan: backtesting-validation Derivatives Snapshot Schema v2

## Plan authority

This plan is the single source of truth for independently building and testing
the operator-approved Derivatives Data Slice 2 generated under
`backtesting-validation`. It validates LC-10 snapshot storage only and does not
authorize live collection, runtime `MarketContext`, LC-11 replay consumers,
proposal filters, strategies, dashboards, deployment, or runtime-data changes.

## Context

- **Primary unit:** `backtesting-validation`
- **Secondary units:** `exchange-integration`, `persistence-data-integrity`
- **Stage:** Build and Test
- **Task:** Verify deterministic Snapshot Schema v2 persistence, atomic
  publication, strict reading, pinned identity, and schema-v1 compatibility.
- **Related requirements:** FR-046, NFR-006, DD-NFR-008, DD-NFR-009,
  DD-NFR-011, DD-NFR-012.
- **Related stories:** US-002, US-025. FR-046 and US-025 remain Partial because
  LC-11 replay and runtime context are later slices.
- **Legacy/debt context:** Legacy Phases 21, 22, and 25; resolved DEBT-043 and
  DEBT-080 precedents. Unrelated repository-wide Black/Ruff drift remains
  DEBT-081 under `quality-governance`.
- **Approved code plan:**
  `aidlc-docs/construction/plans/backtesting-validation-code-generation-plan.md`

## Testing classification

- **Build:** locked dependency validation, Python compilation, and generated
  model/reader/writer imports.
- **Unit:** frozen models, codecs, range/grid/count contracts, deterministic
  identity, v1/v2 negotiation, and error surface.
- **Integration:** schema-v2 writer → filesystem generation → production reader,
  plus unchanged schema-v1 backtest-script consumers and the shared atomic-write
  utility.
- **Contract:** fixed CSV/JSON/manifest shape, exact allowlist, generation id,
  `CURRENT`, pinned reads, and explicit v1 derivatives unavailability.
- **Security:** traversal/absolute id rejection, direct and dangling symlink
  rejection, canonical UTF-8/LF enforcement, integrity/provenance checks, and
  exclusion of credentials/raw payloads/predicted funding.
- **Performance:** no latency/throughput requirement applies to this offline
  LC-10 store. Deterministic bounded file processing is exercised, but no
  unsupported benchmark target is invented.
- **E2E:** N/A until LC-11 wires snapshot-backed `MarketContext` replay into a
  promotion-relevant backtest/robustness workflow.

## Executable steps

### Step 1 — Transition and scope baseline

- [x] Record explicit Code Generation approval and Build & Test transition in
  `aidlc-docs/audit.md`.
- [x] Preserve user-owned `.claude/settings.local.json` and
  `.claude/scheduled_tasks.lock` changes.
- [x] Inspect generated source/test/docs and confirm the declared Slice 2 file
  boundary with no `data/`, dependency, configuration, runtime, proposal,
  strategy, dashboard, migration, credential, or deployment mutation.

### Step 2 — Build verification

- [x] Verify `uv.lock` is current for `pyproject.toml` without mutation.
- [x] Compile `src/backtest` and import the generated v2 contracts, writer, and
  reader.
- [x] Record Python, uv, Pydantic, pytest, pytest-cov, Black, Ruff, and mypy
  versions.

### Step 3 — Unit, contract, and security verification

- [x] Run schema-v1 and schema-v2 snapshot suites and record exact counts.
- [x] Run focused coverage for `src.backtest.snapshot_v2` without inventing a
  repository fail-under threshold.
- [x] Confirm deterministic bytes/id, manifest hash/size/count, canonical
  codecs, exact allowlists, range/grid/order checks, v1 fallback, pinned reads,
  every-phase rollback, corruption failure, and concurrent same-id reuse.
- [x] Confirm traversal, absolute ids, direct/dangling symlinks, invalid UTF-8,
  unknown/missing files, raw payload/predicted funding exclusion, and bounded
  `SnapshotValidationError` behavior.

### Step 4 — Integration and regression verification

- [x] Run unchanged v1 snapshot-script consumer regressions.
- [x] Run snapshot suites with the shared atomic-write utility tests.
- [x] Run the complete repository pytest suite and confirm no test uses live
  exchange credentials/network, performs order actions, or writes repository
  runtime `data/`.

### Step 5 — Static quality and artifact inspection

- [x] Run Black and Ruff on generated Python files and repository-wide mypy.
- [x] Run repository-wide Black/Ruff only to classify the known DEBT-081
  baseline separately; do not mix mechanical cleanup into Slice 2.
- [x] Run `git diff --check`, new-file whitespace and duplicate-generated-file
  searches, sensitive/raw/predicted-funding scan, and exact changed-path review.
- [x] Classify failures as introduced, pre-existing, environmental, or N/A and
  register any real deferred gap in `docs/TECH-DEBT.md`.

### Step 6 — Build/Test artifacts and state

- [x] Update the shared build, unit, integration, performance, contract, and
  security instruction artifacts while retaining prior Slice 1 evidence.
- [x] Update `build-and-test-summary.md` with exact Slice 2 evidence and
  applicability decisions.
- [x] Update the implementation session log, AI-DLC state, and audit record.
- [x] Mark all completed steps here and present Build & Test results for
  explicit review.

## Completion checklist

- [x] Code Generation approval and Build & Test transition recorded exactly.
- [x] Lock/build/import checks pass without dependency mutation.
- [x] Unit, integration, contract, security, and complete regression checks
  pass.
- [x] Performance and E2E applicability are documented honestly.
- [x] Generated-file Black/Ruff, repository-wide mypy, and integrity/path
  checks pass; global Black/Ruff drift remains isolated as DEBT-081.
- [x] No live trading, network, deployment, runtime data, dependency,
  configuration, migration, or credential mutation occurs.
- [x] No untracked gap remains without debt or a bounded later-slice owner.
- [x] Build & Test artifacts, session evidence, state, and audit are complete.
- [x] Results presented for explicit operator approval.

## Approval and closeout

- [x] Operator approved Build & Test with `승인, 다음단계 진행` on
  2026-07-19.
- [x] Operations classified N/A under the repository placeholder rule; no
  deployment or operational mutation performed.
- [x] Unit cross-check completed with PASS for LC-10 at
  `docs/cross-checks/2026-07-19-backtesting-validation-derivatives-snapshot-v2.md`.

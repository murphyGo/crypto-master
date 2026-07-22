# Build and Test Plan: exchange-integration Derivatives Data

## Current plan: Derivatives Data Slice 3 Runtime Context

### Plan authority

This section is the single source of truth for independently building and
testing the operator-approved Derivatives Data Slice 3 generated under
`exchange-integration`. It verifies the runtime context service and its narrow
strategy, proposal, engine, configuration, activity-event, and Ops seams. It
does not authorize a Funding/OI proposal filter, Funding-Extreme strategy,
snapshot replay, deployment, production enablement, credentials, or `data/`
mutation.

### Context

- **Unit:** `exchange-integration`
- **Secondary units:** `strategy-framework`, `proposal-runtime`,
  `dashboard-operator-ui`, `quality-governance`
- **Stage:** Build and Test
- **Task:** Verify the disabled-by-default runtime `DerivativesContextService`
  and normalized no-look-ahead `MarketContext` plumbing before sealing Slice 3.
- **Related requirements:** FR-016, FR-019, FR-046, NFR-006, NFR-009,
  NFR-011, DD-NFR-001..012.
- **Related stories:** US-005, US-008, US-025. FR-046/US-025 remain Partial
  because LC-11 snapshot-only replay is Slice 4.
- **Legacy/debt context:** Legacy Phases 2 and 13.3; unrelated repository-wide
  quality drift remains isolated as DEBT-081.
- **Approved code plan:**
  `aidlc-docs/construction/plans/exchange-integration-code-generation-plan.md`

### Testing classification

- **Build:** locked dependency resolution, Python compilation, and generated
  contract/service/composition imports.
- **Unit:** immutable domain validation, pure context slicing/evaluation,
  service retry/circuit/budget/cache/deadline behavior, and configuration.
- **Integration:** mocked source through service, proposal, engine prefetch and
  shutdown, event log, and Ops read-model boundaries; no external network.
- **Contract:** source protocol, strategy signature compatibility, typed
  availability/error codes, event allowlist, and disabled-default behavior.
- **Security:** empty public credentials, no raw payload/secret serialization,
  no account-exchange reuse, and no network-at-import.
- **Performance:** deterministic latency-injecting fake runs at 4 and 20 symbols
  for 100 cycles, recording p50/p95/max and semaphore/task-leak evidence.
- **E2E:** N/A for live operator/trading execution because no derivatives-aware
  strategy or filter is enabled in this slice; mocked runtime-cycle integration
  is the highest applicable boundary.

### Executable steps

#### Step 1 — Transition and scope baseline

- [x] Record explicit generated-code approval and Build & Test transition in
  `aidlc-docs/audit.md`.
- [x] Preserve user-owned `.claude/settings.local.json` and
  `.claude/scheduled_tasks.lock` changes and inspect the exact Slice 3 boundary.
- [x] Confirm the Code Generation verification baseline before independent
  Build & Test execution.

#### Step 2 — Build verification

- [x] Verify `uv.lock` is current without mutating dependencies.
- [x] Compile and import the generated derivatives domain, builder, service,
  configuration, proposal/runtime, and Ops modules.
- [x] Record Python, uv, ccxt, Pydantic, pytest, pytest-cov, Black, Ruff, and
  mypy versions.

#### Step 3 — Unit, contract, security, and coverage verification

- [x] Run focused generated-module suites with coverage and record exact
  counts plus module coverage without inventing a global threshold.
- [x] Run all Slice 3 modified-component tests and verify no-look-ahead,
  partial availability, retry/circuit/budget/cache/deadline, compatibility,
  safe telemetry, and disabled-default branches.
- [x] Inspect protocol/config/event schemas and negative scans for credentials,
  raw responses, signed URLs, network-at-import, or unsafe serialization.

#### Step 4 — Integration, performance, and regression verification

- [x] Verify mocked source-to-service-to-proposal/engine/Ops interactions,
  outage fail-open behavior, later recovery, and exact single shutdown.
- [x] Run 4- and 20-symbol latency-injecting fake loads for 100 cycles; record
  p50/p95/max, semaphore peak, cancellation, and owned-task cleanup.
- [x] Run the complete repository pytest suite and confirm no live order,
  credential, external Binance call, or repository `data/` mutation.

#### Step 5 — Static quality and artifact inspection

- [x] Run Black and Ruff on Slice 3 touched Python files, repository-wide mypy,
  `git diff --check`, duplicate-file search, and exact changed-path review.
- [x] Classify every failure as introduced, pre-existing, environmental, or
  N/A; file only verified residual gaps in `docs/TECH-DEBT.md`.

#### Step 6 — Build/Test artifacts and state

- [x] Update build, unit, integration, performance, security, and contract
  instructions under `aidlc-docs/construction/build-and-test/` for Slice 3.
- [x] Update `build-and-test-summary.md` with exact evidence and applicability
  decisions.
- [x] Create the Build & Test session log and Slice 3 cross-check; update
  AI-DLC state and mandatory audit completion record.
- [x] Mark all completed steps here and present results for explicit operator
  approval before Operations applicability is decided.

### Completion checklist

- [x] Generated-code approval is recorded exactly.
- [x] Build/import/lock checks pass.
- [x] Unit, integration, contract, security, performance, and regression checks
  pass at every applicable boundary.
- [x] DD-NFR-001/002 p50/p95/max and no-leak evidence is recorded for 4 and 20
  symbols across at least 100 latency-injecting fake cycles.
- [x] Slice-scoped Black/Ruff, repository-wide mypy, whitespace, duplicate,
  secret/raw-payload, and path checks pass.
- [x] No live trading, deployment, runtime-data, dependency, production-enable,
  or credential mutation occurs.
- [x] FR-046/US-025 remain Partial and LC-11 remains owned by Slice 4.
- [x] No verified gap remains without debt or a bounded later-slice owner.
- [x] Build & Test artifacts, session evidence, cross-check, state, and audit
  are complete.
- [x] Results are presented for explicit operator approval.

### Post-review closeout

- [x] Operator approved Build & Test with `승인, 다음단계 진행`.
- [x] Operations recorded N/A: the current rule is a placeholder, the feature
  remains disabled by default, and no deployment/configuration/credential/
  dependency/runtime-data operation exists.
- [x] Slice 3 sealed while FR-046/US-025 remain Partial for Slice 4 LC-11.

---

## Prior completed plan: Derivatives Data Slice 1

### Plan authority

This plan is the single source of truth for independently building and testing
the operator-approved Derivatives Data Slice 1 generated under
`exchange-integration`. It validates only the exchange/domain foundation and
does not authorize snapshot, runtime service, proposal filter, strategy,
dashboard, data, or deployment changes.

## Context

- **Unit:** `exchange-integration`
- **Stage:** Build and Test
- **Task:** Verify normalized Funding/OI domain contracts and the Binance
  public derivatives adapter before sealing Slice 1.
- **Related requirements:** FR-016, FR-019, FR-020, FR-046, NFR-006, NFR-009,
  NFR-011, CON-002.
- **Related stories:** US-008, US-014, US-025. Slice 1 remains partial support
  for US-025 because runtime context and deterministic snapshots are later
  slices.
- **Legacy/debt context:** Legacy Phases 2 and 13.3; resolved DEBT-080
  actual-record pagination/contiguity precedent. Build & Test discovered the
  unrelated repository-wide quality-gate drift now tracked as DEBT-081.
- **Approved code plan:**
  `aidlc-docs/construction/plans/exchange-integration-code-generation-plan.md`

## Testing classification

- **Build:** locked dependency resolution plus Python compilation/import.
- **Unit:** immutable domain validation and adapter mapping/error branches.
- **Integration:** `BaseExchange` → `CcxtExchange` → Binance/Bybit compatibility
  using mocked unified ccxt boundaries; no external network or credentials.
- **Contract:** capability defaults, method signatures, stable error codes,
  UTC/Decimal/history metadata, CCXT protocol surface.
- **Security:** empty public credentials omitted, raw payload discarded, error
  messages sanitized.
- **Performance:** runtime latency, concurrency, rolling request budgets, and
  live endpoint throughput are N/A for Slice 1 because they belong to the
  later `DerivativesContextService`; pagination caps/progress are verified
  deterministically.
- **E2E:** N/A because no runtime consumer or operator workflow is wired.

## Executable steps

### Step 1 — Transition and scope baseline

- [x] Record explicit Code Generation approval and Build & Test transition in
  `aidlc-docs/audit.md`.
- [x] Preserve user-owned `.claude/settings.local.json` and
  `.claude/scheduled_tasks.lock` changes.
- [x] Inspect generated source/test diff and confirm the declared Slice 1 file
  boundary remains intact.

### Step 2 — Build verification

- [x] Verify `uv.lock` is current for `pyproject.toml` without changing
  production dependencies.
- [x] Compile `src/exchange` and import the generated contracts/adapters.
- [x] Record Python, uv, ccxt, Pydantic, pytest, Ruff, Black, and mypy versions.

### Step 3 — Unit, contract, and security verification

- [x] Run all five exchange suites and record exact counts.
- [x] Run focused coverage for `src.exchange` and record the report without
  inventing a repository coverage threshold.
- [x] Confirm pagination caps, actual-record cursor movement, inclusive bounds,
  duplicate handling, gaps, unsupported intervals/venues, retention metadata,
  empty credentials, raw-payload isolation, and sanitized errors are exercised.

### Step 4 — Integration and regression verification

- [x] Run the complete repository pytest suite.
- [x] Confirm no test performs live trading, uses real credentials, writes
  runtime `data/`, or requires a real Binance network call.

### Step 5 — Static quality and artifact inspection

- [x] Run Black in check mode, Ruff, and repository-wide mypy; confirm all nine
  Slice 1 files and mypy pass, and classify unrelated global Black/Ruff drift.
- [x] Run `git diff --check`, duplicate-generated-file search, secret/raw-payload
  scan, and exact changed-path review.
- [x] Classify any failure as introduced, pre-existing, environmental, or N/A;
  file real deferred gaps in `docs/TECH-DEBT.md`.

### Step 6 — Build/Test artifacts and state

- [x] Generate build, unit, integration, performance, security, and contract
  test instructions under `aidlc-docs/construction/build-and-test/`.
- [x] Generate `build-and-test-summary.md` with exact evidence and applicability
  decisions.
- [x] Update the implementation session log, AI-DLC state, and audit record.
- [x] Mark all completed steps here and present Build & Test results for
  explicit review.

## Completion checklist

- [x] Code Generation approval recorded exactly.
- [x] Build/import/lock checks pass.
- [x] Unit, integration, contract, security, and regression checks pass.
- [x] Performance and E2E applicability are documented honestly.
- [x] Slice-scoped Black/Ruff, repository-wide mypy, and whitespace/path checks
  pass; unrelated global Black/Ruff baseline drift is tracked as DEBT-081.
- [x] No live trading, deployment, runtime data, dependency, or credential
  mutation occurs.
- [x] No untracked gap remains without debt or a bounded later-slice owner.
- [x] Build & Test artifacts, session evidence, state, and audit are complete.
- [x] Results presented for explicit operator approval.

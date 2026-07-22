# Build and Test Plan: Funding+OI Crowding Shadow Filter

## Scope

- **Primary unit:** `market-regime`
- **Secondary units:** `proposal-runtime`, `exchange-integration`,
  `dashboard-operator-ui`, `quality-governance`
- **Stories:** US-024, US-025, US-026
- **Requirements:** FR-045, FR-046, FR-011, FR-012, FR-014, NFR-003,
  NFR-006, NFR-007 and CFO-NFR-001..012
- **Boundary:** verify the disabled-by-default shadow observer only. No veto,
  live order, strategy threshold, production enablement, deployment,
  credential, migration, snapshot refresh, or repository `data/` mutation.

## Testing classification

- **Build:** lock, compile, offline imports, Black, Ruff, mypy.
- **Unit/contract:** classifier, evidence qualifier, frozen policy, exact safe
  event fields, honest dashboard read models.
- **Integration:** proposal -> existing context service -> shadow event ->
  unchanged paper fill and dashboard projection.
- **Performance:** pure classifier p95 <=5ms at 90 Funding/500 OI.
- **Security:** disabled zero work, fail-open missing/error context, exception
  message exclusion, no network/data/dependency/deploy change.
- **E2E:** complete repository regression; live trading is N/A.

## Executed steps

### Step 1 — Build and static verification

- [x] Verify `uv.lock` without mutation and compile the affected packages.
- [x] Import generated surfaces with socket connections forced to fail.
- [x] Pass Black/Ruff on all 12 changed Python files and `mypy src`.

### Step 2 — Unit, contract, and security

- [x] Verify long/short/neutral/unavailable, deterministic Decimal percentile,
  no predicted Funding, explicit `as_of`, invalid policy, and evidence states.
- [x] Verify disabled zero work, provider-error sanitization, exact observed
  field allowlist, and structurally unavailable veto.
- [x] Verify dashboard counts, skip separation, ordering, malformed/empty
  safety, and explicit non-enforcing label.

### Step 3 — Integration and compatibility

- [x] Verify shadow `would_block=true` still opens the paper position and does
  not increment rejection counters.
- [x] Verify one cache read at `proposal.created_at` and no hot-path refresh.
- [x] Run the focused 317-test component suite and full repository suite.

### Step 4 — Performance and scope integrity

- [x] Measure 100 classifier runs at the 90 Funding/500 OI envelope and meet
  p95 <=0.005s.
- [x] Check whitespace, dependency/lock, credential, deployment, runtime-data,
  duplicate/TODO, and changed-path scope.
- [x] Reproduce only the unrelated DEBT-081 global Black/Ruff baseline.

### Step 5 — Evidence and closeout

- [x] Write code summary, Build & Test instructions/summary, session log,
  cross-check, state, and audit records.
- [x] Confirm no blocking gap or new debt exists for the shadow release.
- [x] Classify Infrastructure Design and Operations as N/A.

## Completion

- [x] All applicable build, unit, integration, contract, security,
  performance, static, and full-regression gates pass.
- [x] US-026 shadow observation acceptance signals are complete.
- [x] Veto remains unavailable until real dual-lane evidence is accumulated
  and qualified in a later construction slice.

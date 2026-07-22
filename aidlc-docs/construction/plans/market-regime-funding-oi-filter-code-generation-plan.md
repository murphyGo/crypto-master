# Code Generation Plan: Funding+OI Crowding Filter

## Unit context

- Primary unit: `market-regime`
- Secondary units: `proposal-runtime`, `exchange-integration`,
  `dashboard-operator-ui`, `proposal-replay-simulator`, `quality-governance`
- Stories: US-024, US-025, US-026
- Requirements: FR-045, FR-046, FR-011, FR-012, FR-014, NFR-003,
  NFR-006, NFR-007, NFR-011
- Dependencies: sealed `MarketContext`, runtime context service, activity log,
  existing market-regime dashboard page
- Database/migration/deployment: N/A

This plan is the single source of truth for the bounded shadow-first release.
It does not implement veto or change any trading decision.

## Steps

### Step 1 — Pure classifier and evidence contract

- [x] Create `src/runtime/funding_oi_filter.py` with immutable classification,
  deterministic nearest-rank percentile logic, side matching, and dual-lane
  evidence validation.
- [x] Add exhaustive classifier/evidence unit tests.

### Step 2 — Per-account policy

- [x] Add disabled-by-default frozen `FundingOiFilterPolicy` to
  `src/trading/sub_account.py`; initial action is shadow-only.
- [x] Add parsing, validation, default, and immutability tests.

### Step 3 — Runtime shadow gate and telemetry

- [x] Add allowlisted activity event types for observation and skip.
- [x] Evaluate after existing market-regime gating using proposal-symbol
  context at `proposal.created_at`; emit one sanitized event and pass through.
- [x] Add integration tests proving disabled/shadow/missing/error paths cannot
  change proposal outcome or execute an extra network read.

### Step 4 — Dashboard read models

- [x] Add pure crowding summary/recent-event DataFrame builders and render them
  under Market Regime with `SHADOW — NOT ENFORCING` labeling.
- [x] Add empty/malformed/order/count/dashboard tests.

### Step 5 — Quality and lifecycle

- [x] Run targeted tests, changed-file Black/Ruff, repository mypy, complete
  pytest, diff/lock/dependency/data/deployment scans.
- [x] Write code summary, Build & Test evidence, cross-check, session, state,
  and audit records; add debt only for a real unresolved gap.

## Completion

- [x] US-026 shadow observation acceptance signals implemented.
- [x] No veto, strategy threshold, order, credential, deployment, migration,
  production refresh, or runtime `data/` mutation.

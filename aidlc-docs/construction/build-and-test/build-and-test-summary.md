# Build and Test Summary: backtesting-validation Derivatives Data Slice 4

## Current outcome

**Slice 4 status: PASS; explicit operator review pending.**

Pinned Snapshot v1/v2 replay, no-lookahead Funding/OI context, backtest and
robustness propagation, deterministic provenance, explicit collector-to-v2
refresh, and promotion-blocking insufficient evidence build and pass all
applicable verification layers.

## Build evidence

| Check | Result |
|-------|--------|
| `uv lock --check` | Pass; 91 packages, no lock mutation |
| Python compile | Pass for `src/backtest` and robustness CLI |
| Generated imports | Pass |
| Offline import guard | Pass with socket connect forced to fail |
| Runtime | Python 3.13.0, uv 0.7.15 |
| Key libraries | Pydantic 2.13.3, pytest 9.0.2, coverage 7.13.5 |
| Quality tools | Black 26.3.1, Ruff 0.15.9, mypy 1.20.0 |

## Test execution summary

| Test class | Scope | Result |
|------------|-------|--------|
| Focused unit/contract/security/integration | v1/v2 snapshot, replay, engine, multi-TF, gate, harness, CLI | 210 passed in 11.69s |
| Generated-path coverage | Six v2/replay/backtest modules | 183 passed in 17.80s; 92% combined |
| Shared builder compatibility | strategy context, runtime service, proposal engine | 103 passed in 4.59s |
| Existing script consumers | baseline, combination, auto-research | 46 passed in 17.77s |
| Hermetic E2E | fake refresh -> exact reload -> replay -> report twice | 1 passed in 1.27s; identical reports |
| Complete repository regression | `uv run pytest -qq` | 2585 passed in 46.89s |
| Type safety | `uv run mypy src` | 113 source files, zero issues |
| Slice formatting/lint | Black/Ruff over 13 files | Pass |
| Integrity/scope | lock, compile, diff, duplicate, TODO, dependency, credential, deploy, `data/` | Pass |

## Defects found and corrected in Build & Test

1. Replay coverage allowed a Funding series to begin more than one 8h interval
   after the OHLCV start without retention metadata. The source now rejects
   every unexplained prefix gap; OI retention-truncated prefixes remain the
   only explicit exception.
2. Runner placeholder reports serialized raw exception text. Reports now keep
   only the exception class in a stable `error_type` field and direct local
   diagnosis to logs, preventing local path/query/key/raw-payload leakage.

Regression tests also now pin symbol mismatch rejection, exact CLI generation
selection forwarding, repeated-report determinism, and the complete hermetic
collector-to-report flow. No deferred debt was required.

## Requirement and risk coverage

- FR-025/026/027/034 and US-002/003: immutable source propagation and honest
  promotion blocking are verified while legacy OHLCV-only behavior remains.
- FR-046 / US-025: Complete when combined with sealed Slices 1-3; acquisition,
  immutable persistence, runtime consumption, and identical historical replay
  now all have independent evidence.
- DD-NFR-008: v1 compatibility, exact v2 identity, retention metadata, and
  fail-closed gap/coverage behavior pass.
- DD-NFR-009: per-bar no-lookahead, predicted-funding absence, exact identity,
  stable digest/seed, deterministic context/report, and no network fallback
  pass.
- DD-NFR-011/012: normalized allowlists, sanitized reports, offline fakes, no
  new dependency, and isolated tests pass.

## Applicability decisions

- **Production performance:** N/A; no LC-11 latency/throughput target exists.
- **Live endpoint smoke:** Not run; opt-in and not a CI prerequisite.
- **Live trading E2E:** N/A; no order path or strategy threshold changed.
- **Deployment/production refresh:** Not authorized and not performed.
- **Operations:** Pending operator disposition; expected N/A because no
  deployment/configuration/process/migration surface changed.

## Existing baseline issue

DEBT-081 remains unrelated: repository-wide Black lists 19 existing candidates
and Ruff reports the same 22 findings in four existing scripts. No Slice 4 file
appears in either set. Slice-scoped Black/Ruff, repository mypy, and all tests
pass.

## Overall status

- **Build:** Success
- **All applicable tests:** Pass
- **Cross-check:** PASS for LC-11 and the completed FR-046/US-025 chain
- **New technical debt:** None
- **Network/data/deployment action:** None
- **Operator Build & Test approval:** Pending
- **Next boundary:** Explicit review, then Operations applicability disposition

---

# Prior Build and Test Summary: exchange-integration Derivatives Data Slice 3

## Current outcome

**Slice 3 status: PASS and operator-approved on 2026-07-19.**

The disabled-by-default runtime derivatives context service and its domain,
strategy, proposal, engine, configuration, activity-event, and Ops seams build
and pass the applicable unit, contract, security, integration, performance,
and repository regression checks. Build & Test found and corrected one stable
error-code mismatch: request-budget exhaustion now emits the design-defined
`request_budget_exhausted` value instead of `budget_exhausted`.

## Build evidence

| Check | Result |
|-------|--------|
| `uv lock --check` | Pass; 91 packages resolved, no lock mutation |
| Python compilation | Pass for exchange, strategy, proposal, runtime, dashboard, config, and main modules |
| Generated imports | Pass after correcting one verification-command symbol typo; no product import defect |
| Offline import guard | Pass with socket connect forced to fail |
| Runtime | Python 3.13.0, uv 0.7.15 |
| Key libraries | ccxt 4.5.51, Pydantic 2.13.3, pytest 9.0.2, pytest-cov 7.1.0 |
| Quality tools | Black 26.3.1, Ruff 0.15.9, mypy 1.20.0 |

## Test execution summary

| Test class | Command/scope | Result |
|------------|---------------|--------|
| Core unit/contract/coverage | Derivatives domain, builder, and service | 45 passed in 7.59s; 89% combined statement coverage |
| Modified-component regression | Eleven Slice 3 suites | 562 passed in 7.97s |
| Focused runtime integration | Proposal/engine/composition/activity/Ops context cases | 11 passed in 1.81s |
| Focused security | Disabled mode, empty credentials, safe errors/events | 5 passed in 0.97s |
| Deterministic performance | 4 and 20 symbols, 100 latency-injecting cycles each | Pass; p95 0.005630s / 0.027393s |
| Complete repository regression | `uv run pytest -q` after the contract repair | 2557 passed in 46.74s |
| Type safety | `uv run mypy src` | 111 source files, zero issues |
| Slice formatting/lint | Black/Ruff over 22 Python files | Pass |
| Diff/path integrity | whitespace, duplicate, dependency, TODO, and `data/` scans | Pass |

## Performance evidence

| Symbols | Cycles | p50 | p95 | Max | Semaphore peak | Budget |
|---------|--------|-----|-----|-----|----------------|--------|
| 4 | 100 | 0.005066s | 0.005630s | 0.007676s | 4 | p95 <= 5s |
| 20 | 100 | 0.020101s | 0.027393s | 0.034632s | 4 | p95 <= 15s |

Both runs completed every requested series, cancelled none, left the fake
source inactive, and left no service-owned in-flight task after close. These
are deterministic offline fake-load acceptance measurements, not claims about
public Binance network latency.

## Requirement and risk coverage

- FR-046 / US-025 remains Partial exactly as planned: runtime no-look-ahead
  context is verified; LC-11 snapshot-only per-bar replay remains Slice 4.
- DD-NFR-001..007 are covered by 4/20-symbol load, deadline/cancellation,
  freshness/partial availability, retry/circuit, rolling budgets, cache expiry,
  outage fail-open, and recovery tests.
- DD-NFR-009 is complete for the runtime `as_of` half and remains Partial
  overall until identical snapshot replay decisions are verified.
- DD-NFR-010..012 and NFR-011 are covered by exact allowlisted events, newest
  Ops-state folding, credential-free public composition, offline imports,
  deterministic fakes, and no new dependency.
- Existing proposal/live-trading gates, order/risk behavior, and account
  exchange ownership are unchanged; the complete repository suite passes.

## Security and integrity result

The feature constructs no object or request while disabled. Enabled
composition uses a separate Binance USD-M mainnet source with all four
credential fields explicitly empty. Events contain only the approved eleven
fields, exception text/raw responses are excluded, imports perform no network
access, and the service never persists cache content. No dependency, lock,
deployment, migration, production enablement, credential, or repository
`data/` change occurred.

## Defect found and corrected in Build & Test

The approved NFR design names `request_budget_exhausted` as the stable error
code. Generated code and its test had shortened it to `budget_exhausted`.
Build & Test aligned the domain literal, service classifier, and contract test
to the canonical value, then reran 40 focused, 562 component, and 2557 full
tests successfully. No technical-debt deferral was needed.

## Applicability decisions

- **Live endpoint smoke:** Not run; public network behavior is adapter-owned
  Slice 1 evidence and normal CI remains offline.
- **E2E live trading:** N/A; no derivatives-aware filter/strategy is enabled
  and no order path changed.
- **Deployment/production enablement:** Not authorized and not performed.
- **Operations:** N/A under the current placeholder rule. The feature remains
  disabled by default and no deployment/configuration operation exists.

## Existing baseline issue

Repository-wide Black/Ruff drift remains the unrelated DEBT-081 scope. Every
Slice 3 Python file passes Black and Ruff, repository-wide mypy passes, and no
new debt item was found.

## Generated/updated instructions

- `build-instructions.md`
- `unit-test-instructions.md`
- `integration-test-instructions.md`
- `performance-test-instructions.md`
- `contract-test-instructions.md`
- `security-test-instructions.md`
- `build-and-test-summary.md`

## Overall status

- **Build:** Success
- **All applicable Slice 3 and repository tests:** Pass
- **Operator Build & Test approval:** Recorded as `승인, 다음단계 진행`
- **Operations:** N/A; no deployment or production action executed
- **Production enablement/deployment:** Not performed
- **Cross-check:** PASS for the Slice 3 runtime-context boundary
- **FR-046 / US-025:** Partial until Slice 4 LC-11 replay
- **Next bounded slice:** Separately plan Slice 4 LC-11 snapshot-only replay

---

# Prior Build and Test Summary: backtesting-validation Derivatives Snapshot Schema v2

## Current outcome

**Slice 2 status: PASS and operator-approved on 2026-07-19.**

The approved LC-10 Snapshot Schema v2 source builds and passes focused
unit/integration/contract/security checks plus the complete repository
regression suite. Existing schema-v1 behavior remains compatible. Runtime
collection, LC-11 snapshot-backed `MarketContext` replay, proposal filtering,
and strategies remain intentionally outside this result.

## Build evidence

| Check | Result |
|-------|--------|
| `uv lock --check` | Pass; 91 packages resolved, no lock mutation |
| `python -m compileall -q src/backtest` | Pass |
| Generated v2 imports | Pass |
| Build verification wall time | Commands completed within the 2.2s verification batch; no packaging step |
| Runtime | Python 3.13.0, uv 0.7.15 |
| Key libraries | Pydantic 2.13.3, pytest 9.0.2, pytest-cov 7.1.0 |
| Quality tools | Black 26.3.1, Ruff 0.15.9, mypy 1.20.0 |

## Test execution summary

| Test class | Command/scope | Result |
|------------|---------------|--------|
| Unit + contract + security | Schema-v1/v2 snapshot suites | 84 passed in 3.05s |
| Focused coverage | `src.backtest.snapshot_v2` | 84% (474 statements, 74 missed) |
| Atomic persistence integration | Snapshot suites + atomic-write utility | 102 passed in 3.26s |
| Existing consumer compatibility | Four v1 snapshot-script suites | 54 passed in 28.36s |
| Complete repository regression | `uv run pytest -q` | 2518 passed in 44.72s |
| Type safety | `uv run mypy src` | 109 source files, zero issues |
| Generated formatting | Black check over 2 generated Python files | Pass |
| Generated lint | Ruff over 2 generated Python files | Pass |
| Diff/path integrity | Whitespace, duplicate, sensitive/network, scope scans | Pass |

## Requirement and risk coverage

- FR-046 / US-025 remains Partial exactly as planned: deterministic
  Funding/OI persistence and version negotiation are verified; runtime context
  and LC-11 replay consumers remain later slices.
- DD-NFR-008 is covered by immutable generations, same-root staging,
  production-reader validation, atomic `CURRENT`, corruption/rollback tests,
  OI retention metadata, and unchanged v1 fallback.
- DD-NFR-009 is covered by canonical bytes, stable content identity, pinned
  reads, strict future/grid checks, and no network fallback. Per-bar
  no-lookahead slicing remains LC-11.
- DD-NFR-011 is covered by the exact normalized allowlist and absence of
  credentials, raw responses, venue `info`, and predicted funding.
- DD-NFR-012 is covered by focused modules, offline temporary-directory tests,
  and unchanged v1 interfaces.

## Security and integrity result

Traversal/absolute ids, direct/dangling symlinks, invalid UTF-8,
unknown/missing files, noncanonical CSV/JSON, manifest/schema/provenance
corruption, hash/size/count mismatches, bad time grids/ranges, and partial
publication all fail closed. Every injected pre-pointer failure leaves the
prior `CURRENT` selected. A concurrent same-content generation is validated
before reuse; a corrupt same-id generation is rejected.

## Applicability decisions

- **Performance:** N/A for acceptance benchmarking because LC-10 has no defined
  latency/throughput target. Focused runtimes are observations only.
- **E2E:** N/A until LC-11 wires a snapshot-backed promotion/robustness
  consumer.
- **Live network/credentials:** N/A and deliberately not used.
- **Operations:** N/A. No deployable service, migration, runtime process, data
  refresh, infrastructure, or production configuration is introduced.

## Existing baseline issue

Repository-wide Black still identifies the same 20 pre-existing files and
Ruff the same 22 findings in four scripts registered by DEBT-081. Neither
generated Slice 2 file is in those findings; both generated files pass Black
and Ruff. Repository-wide mypy and all tests pass. No Slice 2 defect or new
debt item was found.

## Generated/updated instructions

- `build-instructions.md`
- `unit-test-instructions.md`
- `integration-test-instructions.md`
- `performance-test-instructions.md`
- `contract-test-instructions.md`
- `security-test-instructions.md`
- `build-and-test-summary.md`

## Overall status

- **Build:** Success
- **All Slice 2 and repository tests:** Pass
- **Ready for deployment:** N/A; no deployable artifact
- **Operator Build & Test approval:** Recorded as `승인, 다음단계 진행`
- **Operations:** N/A under the repository placeholder rule
- **Cross-check:** PASS for LC-10
- **Next bounded slice:** Runtime `DerivativesContextService`; FR-046/US-025
  remain Partial for later runtime/replay consumers

---

# Prior Build and Test Summary: exchange-integration Derivatives Data Slice 1

## Outcome

**Slice 1 status: PASS and operator-approved on 2026-07-18.**

The approved Funding/OI exchange/domain foundation builds, passes its focused
unit/integration/contract/security coverage, and introduces no regression in
the complete repository test suite. Runtime service, cache, persistence,
snapshot v2, proposal filters, strategies, dashboard, live endpoint smoke,
deployment, and operations remain outside this slice.

## Build evidence

| Check | Result |
|-------|--------|
| `uv lock --check` | Pass; 91 packages resolved, no lock mutation |
| `python -m compileall -q src/exchange` | Pass |
| Generated imports | Pass |
| Runtime | Python 3.13.0, uv 0.7.15 |
| Key libraries | ccxt 4.5.51, Pydantic 2.13.3, pytest 9.0.2 |

## Test evidence

| Test class | Command/scope | Result |
|------------|---------------|--------|
| Unit + mocked integration + contract + security | Five exchange suites | 221 passed in 1.95s |
| Coverage | `--cov=src.exchange` | 87% exchange total; 92% derivatives domain |
| Repository regression | `uv run pytest` | 2461 passed in 36.39s |
| Type safety | `uv run mypy src` | 108 source files, zero issues |
| Slice formatting | Black check over 9 changed Python files | Pass |
| Slice lint | Ruff over 9 changed Python files | Pass |
| Diff integrity | `git diff --check` | Pass |
| Duplicate generation | `*_new.py`, `*_modified.py` search | None |

## Requirement and risk coverage

- FR-016 / FR-019 / FR-020 compatibility is preserved across Base, shared
  CCXT, Binance, and Bybit exchange boundaries.
- FR-046 / US-025 is partially implemented exactly as planned: normalized
  Binance Funding/OI acquisition contracts only.
- UTC/Decimal immutability, interval and contiguity enforcement, actual-record
  pagination, inclusive bounds, overlap de-duplication, OI retention metadata,
  unsupported venue behavior, raw-payload isolation, public no-credential
  construction, and sanitized typed errors are covered.
- No live network, real credential, live order, runtime-data write, dependency
  mutation, migration, deployment, or production configuration was used.

## Applicability decisions

- **Performance:** N/A for service latency/throughput because the service does
  not exist in Slice 1. Deterministic page caps/progress are tested.
- **E2E:** N/A because no runtime/operator consumer is wired.
- **Live public Binance smoke:** Not run; integration is mocked and repeatable.
- **Operations:** No deployable service or operational migration in Slice 1.

## Existing baseline issue

The repository-wide commands exposed an unrelated committed-state quality-gate
regression: Black would reformat 20 pre-existing files and Ruff reports 22
pre-existing findings in four scripts. None overlaps the nine Slice 1 Python
files, which pass both tools. Full tests and repository-wide mypy pass. The
existing gap is tracked as DEBT-081 under `quality-governance`; it is not hidden
or treated as a Slice 1 defect.

## Generated instructions

- `build-instructions.md`
- `unit-test-instructions.md`
- `integration-test-instructions.md`
- `performance-test-instructions.md`
- `contract-test-instructions.md`
- `security-test-instructions.md`

## Recommendation

Slice 1 Build & Test was approved with operator response
`승인, 다음단계 진행`. Preserve the slice as the validated exchange/domain
foundation and continue the already-designed product sequence with snapshot
schema v2 before adding the runtime context service.

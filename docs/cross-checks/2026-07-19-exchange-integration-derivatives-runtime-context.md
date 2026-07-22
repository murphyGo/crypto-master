# Cross-Check: exchange-integration Derivatives Data Slice 3

## Verdict

**PASS for the approved Slice 3 runtime-context boundary.**

LC-04..09 and LC-12..13 implement and verify bounded runtime Funding/OI
refresh, explicit in-memory availability, no-look-ahead context construction,
optional strategy/proposal consumption, engine lifecycle integration, safe
health events, and Ops projection. FR-046 and US-025 remain **Partial** overall
because LC-11 snapshot-only per-bar replay is Slice 4.

## Scope

- **Primary unit:** `exchange-integration`
- **Secondary units:** `strategy-framework`, `proposal-runtime`,
  `dashboard-operator-ui`, `quality-governance`
- **Implementation:** derivatives domain/builder/service plus optional
  configuration, proposal, engine, activity, composition, and Ops seams
- **Approved boundary:** no proposal Funding/OI regime filter, Funding-Extreme
  strategy, snapshot reader/writer, replay consumer, deployment, production
  enablement, credential, order/risk, or `data/` change

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| FR-016 | Complete / preserved | Enabled composition uses the normalized Binance public adapter through a narrow source contract; existing Binance tests and full regression pass. |
| FR-019 / NFR-009 | Complete for Slice 3 | The service depends on `DerivativesDataSource`; feature-disabled callers and legacy strategy signatures remain compatible. |
| FR-046 | Partial as planned | Runtime current/history context, decision-time `as_of`, explicit missing data, and optional consumers are verified. LC-11 snapshot replay remains pending. |
| NFR-006 | Partial overall | Slice 2 owns structured snapshot persistence; Slice 3 mutates no persistence and LC-11 replay still remains. |
| NFR-011 | Complete for Slice 3 | Dedicated source credentials are empty; events/prompts exclude secrets and raw responses; offline import guard passes. |
| CON-002 | Complete for Slice 3 | Four-way semaphore, configurable rolling budgets, one in-flight result per series, retries, deadlines, and cancellation are verified. |
| DD-NFR-001 | Complete | Four and 20 symbols complete 100 fake cycles independently with semaphore peak four. |
| DD-NFR-002 | Complete | Latency-injecting 100-cycle runs record p95 0.005630s / 0.027393s against 5s / 15s budgets with no leaked owned task. |
| DD-NFR-003/004 | Complete for runtime | 9h/2h expiry ceilings, partial Funding/OI, explicit statuses, required-consumer neutral behavior, and no zero/forward fill are tested. |
| DD-NFR-005/006 | Complete | Transient-only retry, at-most-two retries, per-series circuit skip/probe/recovery, budget exhaustion, and concurrency bounds are deterministic. |
| DD-NFR-007 | Complete | Derivatives outage fails open to existing OHLCV cycle behavior and later service probes recover without restart. |
| DD-NFR-008 | Preserved / Slice 2-owned | Runtime cache is deliberately non-durable and does not alter validated Snapshot v2 or schema-v1 behavior. |
| DD-NFR-009 | Partial as planned | Runtime builder excludes future records and uses final primary-candle `as_of`; snapshot per-bar parity is LC-11. |
| DD-NFR-010 | Complete for Slice 3 | Degraded/recovered events use an exact allowlist/dedupe contract and Ops folds the newest series state. Filter-skip telemetry is outside this no-filter slice. |
| DD-NFR-011/012 | Complete | Public empty-credential source, normalized-only values, no new dependency, deterministic offline fakes, scoped quality checks, and full regression are verified. |

## Story Matrix

| Story | Status | Evidence |
|-------|--------|----------|
| US-005 | Complete / preserved | Optional context reaches compatible proposal strategies; existing proposal output and gates remain unchanged when absent/disabled. |
| US-008 | Complete / preserved | The public context client has no credentials and does not change live intent, live credential checks, or account exchange ownership. |
| US-012 | Complete for contribution | Existing Ops Diagnostics displays newest Funding/OI health without constructing a service or calling Binance. |
| US-025 | Partial as planned | Runtime `MarketContext` is time-bounded and explicit; deterministic historical replay remains Slice 4. |
| US-015/016 | Complete for Slice 3 | Plan, approval, test evidence, session, cross-check, state, and audit surfaces are aligned. |

## Implementation Evidence

- `src/exchange/derivatives.py` owns immutable typed series state,
  requirements, context/evaluation, refresh outcomes, and stable error codes.
- `src/strategy/market_context.py` is a pure, IO-free `as_of` slicer and
  requirement evaluator.
- `src/runtime/derivatives_context.py` owns bounded lifecycle, retry/circuit,
  rolling budgets, per-series cache, cancellation, safe events, and close.
- `src/proposal/engine.py` shares one provider lookup at the final primary
  candle and preserves legacy signatures without masking body `TypeError`.
- `src/runtime/engine.py` refreshes one stable symbol union before scans,
  preserves OHLCV operation on service faults, and closes the shared service.
- `src/main.py` constructs nothing while disabled and otherwise builds one
  dedicated empty-credential public source shared by proposal/runtime.
- `src/dashboard/pages/ops.py` reads activity events only and maps the newest
  normalized state without any exchange call.

## Test Evidence

- Core unit/contract/coverage: 45 passed in 7.59 seconds; generated modules 89%
  combined statement coverage.
- Modified-component suite: 562 passed in 7.97 seconds.
- Focused runtime integration: 11 passed in 1.81 seconds.
- Focused security: 5 passed in 0.97 seconds.
- Deterministic performance: 4/20 symbols x 100 cycles; p95
  0.005630s/0.027393s, peak concurrency four, no owned-task leak.
- Complete repository regression after repair: 2557 passed in 46.74 seconds.
- Black/Ruff pass on all 22 Slice 3 Python files; repository mypy passes for
  111 source files; lock, compile, import, offline-import, diff, duplicate,
  dependency, TODO, and runtime-data checks pass.

## Gaps and Risks

- No blocking gap exists inside the approved Slice 3 boundary.
- Build & Test found and fixed the generated stable-code mismatch
  `budget_exhausted` -> `request_budget_exhausted`; no compatibility surface
  had shipped and all test layers were rerun.
- LC-11 must consume Snapshot v2 only, pin generation identity, reproduce the
  same context at every historical decision boundary, and prove identical
  context-required decisions. This is bounded Slice 4 work, not debt.
- Public Binance latency is not claimed; normal CI remains deterministic and
  network-free.
- DEBT-081 remains unrelated repository-wide Black/Ruff drift. Slice 3 files
  are clean and no new debt was added.

## Unit and Debt Mapping

- **Primary Unit:** `exchange-integration`
- **Secondary Units:** `strategy-framework`, `proposal-runtime`,
  `dashboard-operator-ui`, `quality-governance`; later
  `backtesting-validation` for LC-11
- **Related Debt:** active DEBT-081 is quality-governance-only and non-blocking;
  no Slice 3 debt added
- **Legacy Phase Context:** Phases 2, 10.1, 13.3, 21, 22, and 25

## Operations Applicability

Operations is N/A. No deployment, production configuration, credential,
process topology, migration, dependency, or runtime-data operation is present;
the feature remains disabled by default. The current Operations rule is a
placeholder and ends this workflow after Construction Build & Test.

## Recommendations

1. Preserve the approved Slice 3 PASS while retaining FR-046/US-025 Partial.
2. Proceed to a separately planned Slice 4 for LC-11 snapshot-only replay.
3. Keep the proposal Funding+OI filter and Funding-Extreme MR as later,
   separately hypothesis- and evidence-gated consumer work.

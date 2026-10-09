# Session: Dashboard Bounded Loading NFR Requirements and Design

- **Date:** 2026-10-09
- **Unit:** `dashboard-operator-ui`; command-center, persistence, operations secondary
- **Debt:** DEBT-083 (Critical, active)
- **Requirements/stories:** FR-029/031/032/036/042; NFR-003/007/008/011/012; US-012/014/020/023; BDL-NFR-01..08
- **Stage:** Functional Design approved; approved-target NFR Requirements formalized; NFR Design draft ready for review

## Authorization and Scope

The operator responded `진행시켜` to the presented design and explicit request
to continue NFR Requirements/Design. Recorded in `aidlc-docs/audit.md` at
2026-10-09T22:37:27+09:00. That authorizes the requested documentation stages
and previously presented acceptance targets without another identical prompt.
It does not preapprove unseen numeric reader/cache algorithms or deployment.

Existing concurrent image/provider/financial-metric changes remain outside
this slice. No production load/recovery or runtime-data change was performed.
The preceding incident is historical evidence, not a current health claim.

## Decisions and Source Corrections

- Corrected Home's nested funnel provenance: `load_funnel_summary()` reads
  global proposal history only; the standalone Funnel reads activity too.
- Preserved explicit per-consumer scope/metric contracts: global proposal
  threshold/funnel fields, global reconciliation, Home's capped actionable
  card, Home summed equity and Trading's current single-latest summary. This
  resource fix does not silently absorb separate economic metric corrections.
- Formalized peak RSS/guest memory and complete data-readiness measurements;
  partial/error shells cannot be counted as complete performance passes.
- Proposed one in-process worker, four admitted rebuilds, 16 MiB result cache,
  16 MiB reducer pool, 4 MiB provenance, 1 MiB record guard and 4s wait/work
  quantum. Limits are global, not per session; actual RSS remains authoritative.
- Specified source-generation/order/tie compatibility, mutable-record rebuild,
  bounded checkpoint/cold bootstrap, stale fallback and stuck-worker behavior.
- Selected source-only stdlib/Streamlit design with no durable index; Infra
  Design N/A for this candidate. Later rollout/recovery remains separately scoped.

## Artifacts and Verification

New NFR requirement/design plans and task folders contain formal requirements,
stack decisions, patterns, logical components and qualification procedures.
Functional artifacts, approval audit, unit state and DEBT-083/map were narrowly
updated; other active debt and its statistics were preserved.

Documentation checks passed: tracked/new-file whitespace, relative links,
approved targets/new budget constants, approval/traceability, source-contract
corrections, preserved evidence digest and internally consistent current
debt statistics. Actual results are recorded in the matching NFR cross-check.
Python tests, parser/resource benchmarks, complete-data p95 and
native/production acceptance are pending implementation, not passed by this
documentation. DEBT-083 remains active.

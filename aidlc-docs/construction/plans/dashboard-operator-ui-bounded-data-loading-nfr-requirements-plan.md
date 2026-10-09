# NFR Requirements Plan: Bounded Dashboard Data Loading

- **Date:** 2026-10-09
- **Unit:** `dashboard-operator-ui`; secondary command-center, persistence, operations units
- **Stage:** Complete formalization of operator-approved targets; NFR Design authorized
- **Debt:** DEBT-083 (Critical, active)
- **Requirements/stories:** FR-029/031/032/036/042; NFR-003/007/008/011/012; US-012/014/020/023
- **Legacy context:** Phase 7, 8.2, 10.4, 19.3
- **Input:** Approved [Functional Design plan](dashboard-operator-ui-bounded-data-loading-functional-design-plan.md)
- **Approval:** `진행시켜`, recorded in `aidlc-docs/audit.md` at 2026-10-09T22:37:27+09:00

The response approved the already-presented design/targets and expressly
authorized NFR Requirements/Design continuation. This step formalizes that
input; it does not treat an unseen implementation design as approved.

## Context Assessment

| Category / question | [Answer]: |
|---------------------|-----------|
| Scalability: workload and users? | Approved incident-scale and >=1M activity-event fixtures; four concurrent read-only sessions. Archive payload growth must not produce proportional resident payload growth. |
| Performance: data readiness and memory? | Approved p95 cold <=5s, warm <=2s; <=256 MiB dashboard RSS increase; <=768 MiB VM use on 1024 MiB qualification allocation. Measurement definitions below make these falsifiable. |
| Availability: degraded behavior and recovery? | Approved visible partial/unavailable/stale state within 5s; health <5s and engine continuity in the concurrency run. Production recovery stays separate. |
| Security: data/credentials? | Existing read-only UI boundary and source-data preservation apply; no secret, arbitrary payload, or operator identifier enters metric labels. |
| Tech stack: replacement platform/service? | Existing Python/Streamlit and persisted JSON/JSONL remain. Proposed stdlib readers/cache/concurrency are NFR Design choices; no new stack or durable index is selected. |
| Reliability: corruption, races, restart? | Approved explicit coverage, legacy/monthly compatibility, timestamp parity, missing/incomplete distinction, and cold bootstrap. Concrete mechanisms belong to NFR Design. |
| Maintainability: verification and ownership? | Existing unit/test seams plus explicit bounded-query adapters; preserve pure builders. Source/control changes follow a Code Generation plan after NFR Design review. |
| Usability: apparent healthy/empty results? | Incomplete evidence cannot become a fresh SAFE score, exact zero, or authoritative no-position state; retain independently available ledger/snapshot data. |

## Steps and Artifacts

- [x] Read approved functional rules, entities, frontend behavior, incident limits, and current consumers.
- [x] Verify the nested Home funnel is proposal-only and correct earlier documentation.
- [x] Formalize BDL-NFR-01..08 and measurement definitions in [nfr-requirements.md](../dashboard-operator-ui/nfr-requirements/bounded-data-loading/nfr-requirements.md).
- [x] Record stack decisions and deferred alternatives in [tech-stack-decisions.md](../dashboard-operator-ui/nfr-requirements/bounded-data-loading/tech-stack-decisions.md).
- [x] Record the existing approval/continuation, advance state, and preserve other active debt.
- [x] Prepare the authorized NFR Design; its new budgets/algorithms await review before code.
- [ ] Run resource, latency, semantic, and runtime acceptance tests after implementation; no design-stage benchmark success is claimed.

## Verification and Completion

Validate Markdown links/whitespace, FR/NFR/story/debt references, unchanged
target values, timestamp/call-path claims, and pending code/operational status.
Update `docs/sessions/2026-10-09-dashboard-operator-ui-bounded-data-loading-nfr.md`
and the matching cross-check with actual documentation validation.

```bash
git diff --check
rg -n 'BDL-NFR-|DEBT-083|bounded-data-loading' aidlc-docs/construction/dashboard-operator-ui aidlc-docs/construction/plans docs/TECH-DEBT.md
```

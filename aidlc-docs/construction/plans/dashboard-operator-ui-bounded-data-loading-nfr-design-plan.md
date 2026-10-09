# NFR Design Plan: Bounded Dashboard Data Loading

- **Date:** 2026-10-09
- **Primary unit:** `dashboard-operator-ui`; secondary command-center, persistence and operations units
- **Stage:** NFR Design approved; Code Generation authorized
- **Debt:** DEBT-083 (Critical, active)
- **Requirements/stories:** FR-029/031/032/036/042; NFR-003/007/008/011/012; US-012/014/020/023; BDL-NFR-01..08
- **Legacy context:** Phase 7, 8.2, 10.4, 19.3
- **Authorization:** The latest `진행시켜` approves the presented NFR Design budgets/algorithms and requested code implementation and verification.

## Pattern Questions

| Category / question | [Answer]: proposed design for review |
|---------------------|-------------------------------------|
| Resilience: cold or damaged sources? | Bounded streaming bootstrap/rebuild with explicit per-section coverage, reusable complete results, cooperative checkpoints and no healthy/zero fallback. |
| Scalability: archive growth and concurrent users? | Compact reducers plus global byte/key/admission limits; one process worker and same-query coalescing; no per-session full archive. |
| Performance: latency, cache and invalidation? | 4s total foreground wait, bounded source reads, 2s cache lifetime, reusable source-generation projections; exact semantics qualify against the approved targets. |
| Security: what enters diagnostics and detail? | Allowlisted reason/count/timing metadata; raw persisted detail is available only through a bounded authorized query, not telemetry. |
| Logical components: service/queue/store? | One in-process query service, readers, reducers, encoded cache and existing page renderers. No new durable index or external service. |

## Steps

- [x] Verify current consumers, JSONL retention, mutable JSON storage and pure builders; correct the Home funnel call-path description.
- [x] Specify byte/work/cache/concurrency limits and read-result transitions in [nfr-design-patterns.md](../dashboard-operator-ui/nfr-design/bounded-data-loading/nfr-design-patterns.md).
- [x] Specify source coverage, UTC/tie/cycle algorithms, projection ownership and page integration in [logical-components.md](../dashboard-operator-ui/nfr-design/bounded-data-loading/logical-components.md).
- [x] Specify cold/warm, semantics, damaged-input and engine/resource qualification in [qualification-plan.md](../dashboard-operator-ui/nfr-design/bounded-data-loading/qualification-plan.md).
- [x] Assess Infrastructure Design: N/A for this selected source-only design; VM/process topology, mounts, runtime writers and dependencies stay as they are. A later resize/restart/rollout is a separately specified operations action.
- [x] Update approval audit, state/debt links, session and documentation cross-check.
- [x] Obtain explicit approval of these new NFR Design budgets and algorithms: operator `진행시켜`, recorded 2026-10-09T23:51:15+09:00.
- [x] Create/resume Code Generation plan; implement readers/service, activity pages, proposal/trade/snapshot projections, and meaningful tests in bounded slices. See [implementation and partial qualification](../dashboard-operator-ui/code/bounded-data-loading/implementation-and-qualification.md).
- [ ] Complete Build & Test and resource qualification; retain failed or incomplete results and keep DEBT-083 active until production acceptance is evidenced.

## Handoff and Validation

First implement the shared query/result contract and readers, then wire all
five activity pages together so no alternative page retains the OOM path.
Home's proposal-only funnel and Trading's threshold/history/curve paths are
separate projections required for full readiness. Preserve pure public
builders and verify equivalent reducers rather than feeding them sampled
history. Changes to financial metrics or legacy funnel classifications remain
in their own DEBT-084/085/086 tasks.

Validate document links/whitespace, budget consistency, requirement coverage,
source-path claims and pending approval/code/runtime state. Runtime tests and
performance targets are not claimed by documentation validation.

```bash
git diff --check
rg -n 'BDL-NFR-|DEBT-083|NFR Design' aidlc-docs/construction/dashboard-operator-ui aidlc-docs/construction/plans
```

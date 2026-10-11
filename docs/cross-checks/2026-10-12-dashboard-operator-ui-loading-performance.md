# Cross-check: Bounded Dashboard Loading Performance

**Verdict:** Functional parity and source regression PASS; incident query targets
PASS at query scope. Million-event cold target FAIL (10.546s >5s); requested
deployment source/health/engine checks PASS, first cold protocol readiness FAIL
under measured CPU quota throttling; later warm responses complete. Native NFR
acceptance remains pending; proposed CPU-class / cost change is deferred by
operator `보류` (2026-10-12). Existing v59 / shared CPU 1 / 2048 MiB are retained.
DEBT-083 stays Critical/active.

| Contract | Evidence / verdict |
|----------|--------------------|
| Validation and source coverage | All rows validate through the same models; historical invalid rows outside the tail fail. Bounded parsing and generation checks retained. PASS. |
| Financial/safety display semantics | Five complete incident projection outputs match main `352fb0f` at fixed UTC evaluation time, including sampled curves across 13 accounts. Exact totals, UTC, scope and tie tests pass. PASS. |
| Resource admission | Record/block/cache/state/manifest/queue budgets unchanged; measured retained snapshot charge slots included; state exhaustion and no-reread cache tests pass. PASS at source scope. |
| Source regression | 63 focused; 2732 full tests in 208.76s; changed-file Black/Ruff; source mypy 129 files. PASS. |
| Incident query latency | 20 samples per query, all complete; activity cold p95 1.737s, snapshots 3.746s, proposals 1.998s. All cached queries <2s. PASS for query-only measurement, not full page latency. |
| Local incident RSS | Initial 193.406 MiB, peak 205.062 MiB; increase 11.656 MiB. PASS at measured process scope; shared guest and four-session bounds unqualified. |
| Million-event query / RSS | All 20 samples complete; cold p95 10.546s FAIL; cached 0.000121s and revalidation 0.008977s PASS at query scope. Initial 202.359 MiB / peak 204.234 MiB; no shared-guest claim. |
| Deployed runtime | Fly v59 image/source `22abf3d`; 175 deployed hashes match. Paper/Codex/shared CPU 1/2 GiB/original volume retained. PASS. |
| Health / engine | HTTP 200 / `ok`, Fly check passing; first paper cycle starts 15:45:42Z and completes 15:47:03Z. PASS for observed scope. |
| First readiness / independent queries | Home incomplete at 240s; Trading probe timeout. Activity 75.926s / ledger 3.600s / proposals 44.882s complete; snapshots pending at 120s. Query verification exits 1. FAIL for readiness; observations overlap and are not a controlled comparison. |
| CPU quota | Baseline 0.0625 CPU, near-zero balance; quota throttling about 90.5%/90.9% in two 30s intervals, available memory >1.2 GB. Additional measured bottleneck; candidate performance CPU requires explicit cost/design approval. |
| Later warm protocol | Complete Home/Trading on first full run, 1.443s/1.251s render; totals 1.891s/2.063s. No exceptions / incomplete availability. PASS for this pair, not native/20-sample qualification. |
| Native visual / four sessions | Browser bootstrap again fails on its local missing service module; no viewport or four-native-session acceptance. PARTIAL. |
| Production capacity | Existing 2 GiB recovery allocation is retained; it cannot certify the original 1 GiB qualification. |

The [session](../sessions/2026-10-12-dashboard-operator-ui-loading-performance.md)
records authorization, evidence and the final rollout result. Changed sources
still rebuild the full compact projection; this optimization adds no durable
index or independently reusable monthly segments.

# Dashboard / runtime bounded reads: Code Generation and Build & Test

**Stage:** Code Generation Part 1 complete; implementation authorized.
**Approval:** Operator `gogo` in response to the combined concrete review and request
for implementation, verification and same-capacity rollout. Recorded 2026-10-25T13:57:43.066399+00:00.
This plan executes that presented component/test sequence; no new behavior or
infrastructure permission is introduced and no repeated permission is needed.

**Units:** runtime-safety-score first, dashboard-operator-ui second; related
proposal-runtime/persistence-data-integrity. DEBT-083 remains Critical/active.
**Requirements / stories:** FR-014/015/029/031/032/036/042, NFR-003/007/008/011/012;
US-012/014/020/023; original BDL-NFR-01..08.
**Workspace:** isolated checkout from1855781, rebased onto f0f3e52 to preserve the three separately authorized strategy/proposal corrections. Root unrelated configuration/lock preserved.
**Interfaces:** public chronological readers and list helpers retained; new bounded
runtime iterator/async score facade; existing data-service read results and
freshness/coverage contract. No DB migration/canonical writer changes.

1. [x] Load approved Functional amendment, both NFR patterns/components and current source/unit context. Infrastructure N/A: internal worker/existing namespace only.
2. [x] Add neutral bounded legacy text rows, retained source manifest and canonical runtime event iterator with complete validation/source proof.
3. [x] Add one-shot safety accumulator and process-owned one-worker/zero-queue async reader, exact state/work budgets and quarantined cancellation/lifecycle.
4. [x] Integrate both pre-order engine call sites, None-cache distinction and typed-failure monitor/snapshot isolation; targeted oracle/reader/engine tests.
5. [x] Add eligible lossless per-file dashboard states/codecs, bounded64 MiB private pack/index store and canonical fallback; integrate existing worker only.
6. [x] Verify all original output/window/tie/companion/curve/financial invariants, source/storage faults and global resource caps with independent targeted tests.
7. [x] Full pytest, changed-file Black/Ruff, mypy; independent >=1M event memory/runtime and representative cold/restart benchmarks. Preserve failures and original thresholds.
8. [ ] Update unit state, session, cross-check and debt, review final exact source, commit/push and verify remote; never alter concurrent root files.
9. [ ] Build exact-dependency minimal overlay, deploy to existing sharedCPU1/2048 MiB/original volume/paper-Codex; verify all runtime hashes, health and whole cycle. Record cold/warm/four-session/native/original-guest qualification honestly.

No new UI controls/API/database. Existing source layers own repository boundaries;
tests in corresponding reader/safety/engine/dashboard suites. All new failures
are stable/sanitized, no live activation or cost upgrade. Any unresolved acceptance
keeps DEBT-083 active. Implementation details follow the approved component sequence
in `dashboard-runtime-read-followup-nfr-review.md`; permission to run a tool is not
substituted for this recorded operator approval.

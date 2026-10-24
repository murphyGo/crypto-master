# Shared-CPU Performance Follow-up: Dashboard Loading

- **Unit / stage:** `dashboard-operator-ui`, Code Generation / Build and Test.
- **Task:** Continue UI read-side performance work on the existing shared CPU 1 / 2048 MiB machine. The performance-CPU / added-cost proposal remains deferred.
- **Requirements / stories:** FR-029/031/032/036/042, NFR-003/007/008/011/012, BDL-NFR-01..08; US-012/014/020/023.
- **History / debt:** Legacy Phase 7, 8.2, 10.4, 19.3; DEBT-083 remains Critical/active.
- **Authorization:** Operator `gogo` on 2026-10-25 resumes source improvements within the retained budget. Prior scoped deployment authorization continues; no CPU-class, memory, volume, provider or live-mode change is authorized by this continuation.
- **Baseline:** main `8ac6d66`, runtime `22abf3d` / Fly v59, shared CPU 1 / 2048 MiB confirmed. Existing foreground, state, result, cache and source-validation bounds remain unchanged.
- **Design:** Continue the approved [bounded read-side design](../dashboard-operator-ui/nfr-design/bounded-data-loading/nfr-design-patterns.md). Source invalidation must still validate each selected file and concurrent directory membership. No append cursor, durable index, writer or new infrastructure is introduced.

## Ordered work

1. [x] Revalidate current source, Fly capacity, approval boundary and remaining qualification. Isolate work from unrelated local configuration.
2. [x] Reduce repeated timestamp serialization in activity cycle reductions; directly validate bounded snapshot JSON objects without an intermediate raw dictionary. Preserve UTC normalization, exact source-order ties, every-record validation and financial/curve output.
3. [x] Reuse unchanged projections after irrelevant directory metadata changes, while retaining per-file generations and publication-time directory verification. Test relevant additions/removals/replacement and concurrent membership changes explicitly.
4. [x] Run focused reader/projection/service/page tests, full regression, changed-file Black/Ruff and source mypy. Review against the approved contracts and compare deterministic full projections with the baseline.
5. [x] Measure final-source cold queries and revalidation with twenty paired baseline/candidate samples on declared generated fixtures. All 120 complete outputs match business fields/coverage. Million cold p95 10.467→10.872s does not improve or meet 5s; snapshots 3.781→3.648s; unrelated-directory revalidation 0.773→0.00398s. Native/guest qualification remains separate.
6. [x] Commit/push the verified slice and deploy it to the existing machine, retaining shared CPU 1 / 2048 MiB, existing dependencies where practicable, original volume and paper/Codex settings. Verify actual deployed source/capacity, health, complete Home/Trading protocol responses and engine continuity.
7. [x] Update implementation evidence, session, cross-check, unit/debt state and outstanding acceptance. Keep the deferred CPU proposal and unresolved cold/native/resource targets explicit.

## Questions and constraints

- **Capacity / operating cost:** [Answer]: Retain existing shared CPU 1 / 2048 MiB; performance CPU proposal remains deferred by `보류` and is not resumed by this source-only continuation.
- **Data / trading:** [Answer]: Read-only queries, existing files and paper/Codex controls; no deletion/migration or live activation.

## Completion

- [x] Source implementation and meaningful tests complete
- [x] Performance and exact semantic comparison evidence recorded
- [x] Scoped rollout verified without a capacity change
- [x] Session, cross-check, debt and state reconciled

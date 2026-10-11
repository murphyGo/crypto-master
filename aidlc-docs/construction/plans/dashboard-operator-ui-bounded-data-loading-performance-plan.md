# Performance Follow-up: Bounded Dashboard Data Loading

- **Unit / stage:** `dashboard-operator-ui`, Code Generation / Build and Test
- **Task:** Reduce the remaining cold and changed-source read cost within the approved bounded read-side design.
- **Requirements:** FR-029/031/032/036/042; NFR-003/007/008/011/012; BDL-NFR-01..08
- **Stories / history:** US-012/014/020/023; legacy Phase 7, 8.2, 10.4, 19.3; DEBT-083 remains active.
- **Authorization:** The operator's `계속 진행시켜` continues implementation and verification; the earlier `배포도 해줘` authorizes the same scoped rollout. Preserve the current Codex CLI / Claude rollback, paper mode, 2 GiB machine and original volume.
- **Baseline:** main `352fb0f`, deployed runtime `785374b` / Fly v58. The earlier cold query targets and native multi-session acceptance are incomplete. Existing bounded caches, exact totals, failure semantics and budgets are unchanged.

## Ordered work

1. [x] Profile the captured incident archive and all 13 account snapshots. Activity: 214,686 reducer calls, 3,419,126 gate-match generator iterations and 214,687 serializer calls. Snapshots: about 30 million Python byte appends and 357,474 recursive size calculations. Profiler timings include instrumentation and are diagnostic only. Selected optimizations remain in `src/utils/bounded_read.py` and `src/dashboard/projections.py`.
2. [x] Implement allocation-checked parser scanning, direct bounded activity JSON validation, lazy rich event serialization / grouped gate classification and measured snapshot charge reuse. Preserve validation of every source record, timestamp ties, gate semantics and exact lifetime/window totals. Parser boundary/damage and reducer parity tests pass; five full incident projections match the baseline exactly.
3. [x] Run targeted dashboard tests (63), full regression (2732 passed in 208.76s), changed-file Black/Ruff and source mypy (129 files); review changed code against the approved contracts. No unresolved source correctness finding; cold/native/resource acceptance stays separate.
4. [x] Measure the final runtime inputs with 20 cold/cache/revalidation samples on the incident and existing million-record fixture; all complete, source hashes match. Incident activity/snapshot cold p95 1.737s/3.746s; million activity 10.546s still misses 5s. Local RSS evidence is separate from native/shared-guest acceptance.
5. [x] Commit/push `22abf3d`, deploy exact source on Fly v59; 175 source hashes, health and first paper cycle pass. Record partial/failing read-only query and first protocol observations under measured CPU throttling, and later complete warm Home/Trading responses. DEBT-083 remains active; CPU-class/cost candidate is a separate approval.
6. [x] Update implementation notes, session, cross-check, unit state, debt and original outstanding checklist from actual results, including the failed first readiness, measured CPU quota bottleneck and pending cost/design choice.

## Verification

```sh
python -m pytest tests/test_bounded_read.py tests/test_dashboard_projections.py tests/test_dashboard_data_service.py tests/test_dashboard_bounded_pages.py
python -m pytest
python -m black --check <changed Python files>
python -m ruff check <changed Python files>
python -m mypy src
python scripts/qualify_dashboard_loading.py --root <read-only-fixture> --samples 20 --output <evidence-json>
git diff --check
```

## Completion

- [x] Implementation and meaningful regression checks recorded
- [x] Exact-source performance evidence and deployed verification recorded, with explicit partial/failing acceptance
- [x] Session, cross-check, state, debt and plans reconciled
- [x] Unrelated dirty files and runtime data preserved

## Remaining acceptance

Native visual and four-session / 10-minute resource qualification requires a working Browser connection. Protocol integration and offline query benchmarks cannot satisfy that criterion. Do not infer the original 1 GiB shared-guest acceptance from the current 2 GiB deployment.

The million cold 5s target and first production readiness remain unmet. The
reviewed CPU-class / added-cost decision is in the
[Infrastructure Design plan](dashboard-operator-ui-cpu-quota-infrastructure-design-plan.md).
This source performance slice is documented and deployed; it does not close
DEBT-083 or approve a capacity change.

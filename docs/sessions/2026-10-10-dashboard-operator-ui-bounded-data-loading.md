# Session: Bounded Dashboard Data Loading

- **Unit:** `dashboard-operator-ui`; command-center, persistence and operations participation
- **Requirements/stories:** FR-029/031/032/036/042, NFR-003/007/008/011/012, BDL-NFR-01..08; US-012/014/020/023
- **Debt:** DEBT-083, Critical and active
- **Authorization:** Operator approved the presented NFR Design and implementation with `진행시켜`, then continued with `gogo`. Code planning preceded source changes; normal implementation verification follows that authorization without another identical approval request. Production rollout remains outside this checkpoint.

## Result

Default dashboard routes no longer materialize the full activity archive. One
bounded service streams data, keeps compact aggregates, verifies file generations
before cached reuse and separates complete/pending/stale/unavailable sections.
Trading keeps verified ledger/snapshot information when activity is damaged.
Home's proposal-only funnel, ledger/snapshot arrays and Feedback's catalog/audit
paths are also bounded. Pure builders and explicit fixture adapters are retained.

## Changed files

- `src/utils/bounded_read.py`: forward/reverse JSONL, object and array readers; record/block bounds and descriptor/path generation checks.
- `src/dashboard/{read_models,data_service,sources,projections,availability}.py`: contracts, single worker, global budgets, packed manifests, compact projections, bounded wait/availability and source-generation reuse.
- `src/dashboard/pages/{home,trading,engine,ops,proposals,feedback}.py`: default IO integration, controls and verified-section rendering.
- `tests/test_{bounded_read,dashboard_data_service,dashboard_projections,dashboard_bounded_pages}.py` and the existing Home loader test: failure, parity, concurrency and production-default regressions.
- `scripts/qualify_dashboard_loading.py`: isolated query/RSS measurements and representative million-event fixture generation.
- Construction plan, implementation/evidence, cross-check, audit, state and DEBT-083 records.

## Validation and limits

Functional verification includes default-route spies forbidding full-history
materializers, damaged activity with independently visible Trading data, cycle
interleaving/terminal/rejection rules, selected-account/global counts, windows,
mutable replacement, generation reuse, parser faults, admission/coalescing,
stale/root/cache limits and batch freshness. Final command results are recorded
in the [cross-check](../cross-checks/2026-10-10-dashboard-operator-ui-bounded-data-loading.md).

Final full regression: 2719 passed in 60.93s; changed-file Black/Ruff and mypy
(130 source files) passed. Publication-time incident expiry and reversed-clock
guards were added after the offline benchmark series and covered by the final
19-test focused run and full regression. Benchmark hashes are preserved rather
than relabeled as measurements of the final source.

Twenty-sample offline evidence covers the exact incident activity workload and
1,000,000 representative events. All queries complete without the former raw
archive collections; local process RSS remains bounded. **Cold performance is
not accepted:** incident activity p95 5.150s, million bootstrap p95 21.614s.
Cached/revalidated query results are quick, but these are not browser timings.
No native four-session/10-minute guest/engine acceptance is claimed.

See the full [implementation and qualification report](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/implementation-and-qualification.md)
for source hashes, samples, measured memory and the acceptance matrix.

## Decisions and remaining work

Encoded immutable cache and packed manifests avoid rich payload duplication.
Working states are single-owner bounded; timeout cannot terminate blocked kernel
IO or create another worker. Unchanged whole projections are re-evaluated from
verified compact descriptors. A changed source currently rebuilds that projection;
per-month reuse and cold bootstrap optimization remain DEBT-083 follow-up.

No runtime data was migrated, no engine writers/trading controls/credentials or
deployment topology were changed, and no commit/push/deployment was performed
for this slice. Concurrent source/operations debt resolutions and unrelated local
configuration changes were preserved. The debt remains active until performance
and authorized production acceptance are evidenced.

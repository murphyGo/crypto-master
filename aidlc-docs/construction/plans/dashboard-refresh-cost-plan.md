# Dashboard refresh cost — active 2026-11-16

- Unit: dashboard-operator-ui; related persistence-data-integrity.
- Debt: DEBT-083 Critical, still active after v72.
- Requirements: FR-028–032/036/038/042, NFR-003/007/008/011/012,
  BDL-NFR-02–08; stories US-012/014/020/023; legacy 7/8.2/19.3.
- Baseline: main51b8881, deployed source71c8787/Flyv72, 183 runtime paths.
- Stage: measured NFR refinement, implementation, verification and same-capacity
  delivery. No functional or infrastructure contract change is selected.

[Answer]: The user's renewed “진행시켜” continues the remaining DEBT-083 work
and established implementation/test/commit/push/same-capacity delivery workflow.
Reduce measured reconstruction cost without altering freshness, validation,
coverage, memory/admission budgets, retries, trading or canonical data. Existing
resilience/security contracts and one-worker/four-admission scaling remain.
No capacity/cost decision or new logical component is authorized by inference.
Any measured implementation refinement must preserve those constraints.

- [x] Refresh exact runtime/source/settings and profile direct snapshot/activity
  rebuilds with source/output digests; distinguish timing from profile overhead.
- [x] Select the measured narrow bottleneck and document its NFR amendment before
  editing application code. Preserve existing failed and slow observations.
- [x] Implement with meaningful parity/damage/budget regressions; benchmark the
  same inputs in alternating order and keep all trials.
- [x] Run targeted tests, broader pytest as warranted, changed-file Black/Ruff,
  full mypy and implementing-agent review; preserve deterministic payload parity.
- [ ] Commit/push verified source, deploy only changed runtime paths over exact
  v72 at unchanged capacity; verify hashes/settings, health and natural cycle.
- [ ] Retain bounded Home/Trading observation and update session, cross-check,
  state, debt/map and artifacts. Keep original native/cold/depleted/1GiB gates
  open unless their own evidence actually satisfies them.

Previous 277/277 complete requests pass the bounded warm protocol sample, but
four write-wave requests take13.19–15.18s. This overlap does not prove a specific
writer or projection caused the latency. Never replace slow/failed samples with
later successful responses or certify stale/partial data as complete.

Selected refinement (2026-11-17 KST): stop the codec-only size predicate after
32KiB is exceeded, preserving exact default accounting and identical split/byte
encoding. Direct and isolated checkpoint profiles retain all measurements;
36 focused cutoff/codec tests and110 existing projection/checkpoint tests pass.

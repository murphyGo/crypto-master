# Dashboard initial-read cost — bounded slice complete 2026-11-11

- Unit: dashboard-operator-ui; related persistence-data-integrity and
  dashboard-operator-command-center.
- Debt: DEBT-083 Critical remains active; DEBT-090 containment is complete.
- Requirements: FR-028–032/036/038/042; NFR-003/007/008/011/012;
  BDL-NFR-02–08. Stories US-012/014/020/023; legacy7/8.2/19.3.
- Stage: focused NFR refinement, Code Generation, Build & Test, same-capacity
  delivery and bounded operational evidence.
- Baseline: main21142a7; deployed v71/source0e14f9d,183 runtime paths.

[Answer]: “진행시켜” continues the proposed remaining initial-latency work and
existing implementation/commit/push/same-capacity delivery workflow. Optimize
measured CPU work while preserving complete output, validation, budgets and
source-generation proof. Do not change data, trading, credentials, dependencies,
capacity, CPU-cost decision or the original acceptance thresholds.
[Answer]: Resilience and security contracts stay unchanged; no retry/cache-policy
change is selected. Scaling keeps one worker/four admissions and existing caps.
Performance uses the current BDL-NFR targets, with comparable initial-read trials
and deterministic source/output parity before claiming improvement. Logical
components remain existing readers and projections; no infrastructure addition.

- [x] Measure current snapshot/activity initial reads and attribute CPU cost;
  retain bounded read-only production metadata/hashes and local representative
  fixtures. Separate profiling overhead from uninstrumented timings.
- [x] Record the measured narrow optimization in an NFR amendment under
  dashboard-operator-ui/nfr-design/initial-read-cost before application edits.
- [x] Add meaningful parity, damaged/boundary/source-change, cancellation and
  budget regressions appropriate to selected src/dashboard or src/utils files.
- [x] Implement the smallest measured improvement; compare same-input payloads,
  retained bounds and timings, then targeted dashboard/parser tests, full pytest,
  changed-file Black/Ruff and full mypy. Record implementing-agent review.
- [x] Commit/push verified source, overlay changed runtime files on exact v71
  image; verify all hashes/settings/health and a natural cycle. Preserve every
  failed sample; perform bounded Home/Trading readiness observation.
- [x] Update session/cross-check/state/debt/map and retain operational evidence.

The current5s cold/2s warm targets,20-observation/native/cold/depleted/original
1GiB gates and ten-minute/four-session gate remain independent. One faster
projection or normal cycle cannot resolve DEBT-083. No schema/content-validation
shortcut, stale-as-complete result, silent truncation or omitted history is allowed.

Completion: source71c8787/Flyv72, all183hashes/settings, native visual smoke and
1387.074688s four-session protocol sample pass (277/277complete,275/275health,
12-account natural cycle). Retain four13.19–15.18s tail responses and all historical
failures. Evidence is sealed under `code/initial-read-cost-20261111/operations/`.
DEBT-083 remains Critical for tail/initial latency and original qualification gates.

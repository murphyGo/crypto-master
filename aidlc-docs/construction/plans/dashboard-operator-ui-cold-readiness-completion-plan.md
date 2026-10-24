# Dashboard Cold Readiness and Concurrency Completion

- **Unit / stage:** `dashboard-operator-ui`, Code Generation / Build and Test under the approved bounded read-side design.
- **Task:** Continue remaining Home cold readiness, million-event query performance and actual browser/concurrency qualification.
- **Requirements / stories:** FR-029/031/032/036/042, NFR-003/007/008/011/012, BDL-NFR-01..08; US-012/014/020/023.
- **History / debt:** Legacy Phase 7, 8.2, 10.4, 19.3; DEBT-083 remains Critical/active.
- **Authorization:** Operator `나머지도 계속 진행해줘` resumes the outstanding work and previously authorized scoped rollout. Performance CPU / added cost remains deferred; retain shared CPU 1 / 2048 MiB, original volume, dependencies and paper/Codex safeguards. Preserve unrelated root configuration.
- **Baseline:** main `bf44822`, runtime `38876fc` / Fly v60. Previous Home/Trading protocol pair 17.502s / 2.480s; million query cold p95 10.872s. Native Browser connection fails to load its local runtime service.
- **Design boundary:** Existing bounded source/reducer/cache design applies. No durable index, append cursor, runtime-data writer or external topology change is introduced without revisiting its applicable design stage.

## Ordered work

1. [x] Revalidate live capacity/source, unit/debt state and browser connection; isolate work from unrelated dirty files. Ask for external Browser recovery asynchronously while independent source work continues.
2. [x] Profile the final v60 reducers on the existing generated million-event fixture and inspect page dependency/import cost. Selected typed activity loops/rank checks, compiled canonical JSON validation, bounded selected snapshot rows and measured fixed-shape accounting, native metadata capture/verification, shared lifetime threshold reuse, and one-time request canonicalization. No exchange/writer/persistence change.
3. [x] Implement bounded CPU reductions while preserving every-record validation, UTC/ties, exact lifetime/window totals, financial outputs and all existing limits. Add meaningful regression/negative tests.
4. [x] Verify full-output parity and twenty paired cold/warm observations at exact final source. Run targeted/full tests, changed-file Black/Ruff and source mypy; review correctness and resource bounds.
5. [ ] Deploy the verified source on the unchanged machine using the existing dependency image as base. Verify source hashes, health and complete Home/Trading responses.
6. [ ] Run four actual browser sessions alternating Home/Trading for at least ten minutes if Browser connection recovers. Independently exercise server protocol concurrency, guest/process memory, health <5s and a full engine cycle; label each evidence surface precisely.
7. [ ] Reconcile outstanding acceptance from actual measurements. If a target needs a new persistence/topology contract, prepare the applicable design and concrete approval decision instead of silently changing the approved boundary.
8. [ ] Update session, cross-check, unit state, debt and plans; commit/push scoped changes and preserve unrelated local work.

## Questions and constraints

- **CPU capacity:** [Answer]: Retain shared CPU 1 / 2048 MiB; prior performance CPU proposal remains deferred.
- **Browser:** [Answer]: Local runtime service is missing; connection recovery requested asynchronously. This does not block independent source/protocol work.
- **Data / trading:** [Answer]: Read-only runtime queries; preserve existing files, paper/Codex configuration and live confirmation controls.

## Completion

- [ ] Bounded implementation and source verification complete
- [ ] Exact performance / deployed / concurrency evidence recorded
- [ ] Native viewport qualification completed, or actual external blocker explicitly recorded
- [ ] Remaining NFR/design decisions and debt status reconciled without claiming incomplete acceptance
- [ ] Scoped commit/push and root preservation verified

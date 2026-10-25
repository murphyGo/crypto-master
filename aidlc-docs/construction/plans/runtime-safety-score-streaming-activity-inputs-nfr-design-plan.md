# runtime-safety-score: streaming-activity-inputs NFR Design Plan

- **Unit / stage:** `runtime-safety-score` / NFR Requirements formalization and NFR Design candidate.
- **Task:** Stream canonical safety inputs without archive-sized retention; bound work and preserve exact fixed-time math. A newly discovered per-account failure path skips monitoring; propose a clearly labelled isolation amendment before implementation.
- **Requirements / stories:** FR-014/015/042; NFR-007; US-020; shared DEBT-083 / original BDL-NFR-01..08 remain binding.
- **Baseline:** main `070fa96`, Fly v62 / source `d86f76f`, 2823 passing tests. Original shared CPU 1 / 2048 MiB / volume / paper-Codex stay. Performance CPU/cost remains deferred.
- **Authority:** Current operator continuation approves presented base Functional Designs. Formalization carries forward their rules and original BDL targets; no new acceptance target or runtime permission is invented. New design constants/amendment need explicit review before code.

1. [x] Revalidate source, accepted functional rules, unit ownership, actual v62 failures and current deployment/volume.
2. [x] Carry forward approved requirements/technology constraints without relaxing 5s/2s/256/768 targets or redefining 1 GiB qualification.
3. [x] Resolve concrete resource, failure, compatibility, invalidation, lifecycle and storage choices; evaluate every NFR question category.
4. [x] Write NFR patterns, logical components, implementation/test sequence and acceptance matrix.
5. [x] Cross-check safety flow, non-associative reductions, dynamic defaults, source proof and global resource accounting; validate docs/evidence.
6. [x] Present the concrete candidate and receive explicit NFR approval (plus runtime failure-isolation amendment where applicable).
7. [x] Only then enter Code Generation / Build & Test and previously authorized same-capacity rollout; preserve unrelated root edits.

## Questions / source of answers

- **Resilience:** [Answer]: Preserve verified siblings and legacy scoring math; hard incomplete safety reads cannot become SAFE. Propose monitoring isolation and bounded nonblocking worker ownership; final rules await review.
- **Scalability:** [Answer]: Original incident and >=1M-event fixtures; four sessions and existing capacity. Design limits are process-wide, not multiplied per session/account.
- **Performance:** [Answer]: Original complete-page cold p95 <=5s / warm <=2s and health <5s, no ignored failures. No-checkpoint and depleted conditions stay separate; proposed work budgets are not acceptance proof.
- **Security:** [Answer]: No credential/provider/exchange changes, no raw diagnostics, only private disposable cache when applicable. Existing canonical files and live intent remain intact.
- **Components:** [Answer]: Existing Python/stdlib and approved data service; no new Fly process/database/service/paid allocation. Detailed internal components and disk choices are proposed below.
- **Approval:** [Answer]: Operator `gogo` explicitly continues the combined review request covering both NFR designs, the failure amendment, implementation, verification and same-capacity rollout. Recorded 2026-10-25T13:57:43.066399+00:00. Cost/capacity deferral remains.

## Completion

- [x] Reviewable design and documentation QA complete
- [x] NFR design explicitly approved
- [ ] Implementation/verification/rollout completed after approval
- [ ] Original acceptance actually passed before debt closure

Verification: linked combined review, source-flow inspection and scoped documentation QA; see `docs/cross-checks/2026-10-25-dashboard-runtime-read-nfr-design.md`. Explicit approval and all implementation checks remain unchecked.

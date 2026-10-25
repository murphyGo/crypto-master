# DEBT-083: v64 operational qualification continuation

- Unit/stage: `dashboard-operator-ui` / Build & Test and Operations;
  secondary `runtime-safety-score` and `notifications-ops`.
- Requirements/stories: original BDL-NFR-01..08, FR-029/031/032/036/042,
  NFR-003/007/008/011/012; US-012/014/020/023.
- Authority: user `계속 진행` after runtime deployment verification on
  2026-10-26 KST. Continue existing acceptance and previously authorized
  same-capacity verification. CPU/cost, credentials, trading and resizing
  approvals are not changed.
- Baseline: main `458ef79`, deployed application `dca38fb`, Fly v64.
  Alternative `8053ae0` remains archived and is not a source candidate.
- Coordination: the existing dashboard worktree is collecting a four-session
  v64 run. Reuse and independently audit that evidence; do not start a second
  production load, restart the service or alter its sampled environment.

## Work

- [x] Refresh local/remote/worktree state and identify active measurement.
- [x] Read original requirements and qualification definitions without lowering
  targets or equating seeded restart with cacheless cold readiness.
- [x] Independently reconcile final starts/outcomes, p95, health, memory, CPU
  and one complete natural engine cycle from the existing four-session run.
- [x] Verify native Browser availability through its supported runtime;
  retain setup failures separately from application failures.
- [x] Profile the remaining cacheless-million cold miss locally on exact v64
  source with frozen output/source hashes; no production fixture mutation.
- [x] Classify each original acceptance item as passed, failed, blocked or
  unqualified with the measured environment. 2 GiB and buffered CPU cannot
  certify 1 GiB or depleted CPU conditions.
- [x] Record final evidence, session/cross-check and debt status; commit/push
  this bounded qualification result, preserving concurrent work.

## Ownership and completion

The lead owns this continuation record, supported Browser connection and final
reconciliation. Independent QA audits the existing measurement harness/output;
quant reviews acceptance semantics; the implementation specialist profiles local
cold work without changing source. Production measurement remains with its
existing owner. No duplicated implementation, deployment or acceptance claim.

Completion of this cycle means the available run and cold-path diagnosis are
audited and recorded. It does not mean DEBT-083 closes while original requirements
remain unmet. Native recovery and declared-resource qualification retain their
actual blockers; request any required operator action only with concrete evidence.

## Outcome

Final observation: 347/349 complete; two Home incomplete, so concurrency readiness
fails. A full natural monitor cycle, health and observed numeric memory ceilings
pass on the current 2048 MiB allocation. A separate full-window CPU supplement
shows positive balance and zero sampled throttle; depleted CPU remains open.
Post-run source/image/instance/health are unchanged. Browser bootstrap is blocked
before navigation by a missing packaged service; operator recovery is pending.
Cold profiling is complete and not a latency acceptance result. Session and
cross-check: `2026-10-26-dashboard-v64-qualification-continuation.md` under
`docs/sessions/` and `docs/cross-checks/` respectively.

Next source slice: retain exact bounded failure reasons and reproduce Home's
activity/snapshot failure and queue saturation interactions. Retry behavior must
not be changed solely from temporal overlap with the engine cycle. The shared
row-reduction cold cost also remains separate from optional codec sizing savings.

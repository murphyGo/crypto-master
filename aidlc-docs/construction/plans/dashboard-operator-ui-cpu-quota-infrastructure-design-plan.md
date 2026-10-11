# Infrastructure Design Plan: Dashboard CPU Quota Recovery

- **Unit / debt:** `dashboard-operator-ui` / DEBT-083, Critical and active.
- **Stage:** Infrastructure Design candidate deferred by the operator (`보류`, 2026-10-12 KST); not approved or activated.
- **Retained state:** Fly v59 / source `22abf3d`, shared CPU 1 / 2048 MiB, existing machine and volume. No CPU-kind change, additional deployment or incremental compute-cost change was made. Resume this proposal only after a new explicit operator decision.
- **Requirements / stories:** FR-029/031/032/036/042; NFR-003/007/008/011/012; BDL-NFR-01..08; US-012/014/020/023.
- **Evidence:** v59 source `22abf3d` is functionally verified; first protocol readiness and query deadlines fail while the shared CPU burst balance approaches zero. Warm Home/Trading responses later complete in 1.443s/1.251s. The infrastructure decision does not waive the remaining cold/memory/native targets.
- **Existing authorization:** Continued UI performance work and scoped deployment are authorized. The previous performance/rollout plan preserves shared CPU 1 / 2 GiB. An ongoing CPU-class cost increase is a new decision; do not activate it before the operator's answer.

## Steps

1. [x] Reconcile approved functional/NFR contracts and deployed source/process/engine evidence with measured CPU quota, balance and throttling.
2. [x] Prepare the exact candidate manifest and cost comparison under `construction/dashboard-operator-ui/infrastructure-design/cpu-quota-recovery/`; parse TOML and verify only CPU kind changes.
3. [ ] Collect operator choice on performance CPU 1 / 2 GiB and estimated +$26.55 per 30 days of continuous Tokyo compute. Record the answer and design approval in `audit.md`.
4. [ ] If approved, copy the reviewed CPU-kind change into root `fly.toml`, commit/push, deploy the existing v59 digest to the same machine with explicit `--vm-cpu-kind performance --vm-cpus 1 --vm-memory 2048`; preserve image, paper mode, provider, original volume and limits.
5. [ ] Verify actual guest capacity/source, cold/warm Home/Trading readiness, health, CPU metrics and a completed engine cycle. Continue remaining native/resource qualification separately.
6. [ ] Reconcile unit/debt/session/cross-check records from results. If the operator declines added cost, continue source/import/metadata/index design under the existing budget; do not promise the unchanged shared-CPU cold target is qualified.

## Questions and established constraints

- **Compute / cost choice:** Approve `performance-1x`, 2 GiB, with estimated Tokyo compute cost $43.16 vs current $16.61 per 30 continuous days (+$26.55), excluding tax/traffic/discounts? [Answer]: `보류` (2026-10-12 KST). Proposal deferred; existing capacity retained.
- **Deployment environment:** Existing Fly app, nrt region and machine `6835752b711958`. [Answer]: Existing authorized scope; no new provider/region/machine.
- **Storage:** Existing encrypted `/data` volume; no migration, index or deletion in this candidate. [Answer]: Existing brownfield constraint.
- **Messaging:** Existing process-local queue / one reader worker. [Answer]: No infrastructure messaging change.
- **Networking:** Existing hostname, ports, routing and health check. [Answer]: No network change.
- **Monitoring:** Existing Fly metrics and source/process/protocol checks. [Answer]: No external notifications or monitoring service.
- **Shared infrastructure:** Engine/dashboard stay together on the existing VM; memory 2048 MiB and paper/Codex configuration are preserved. [Answer]: Existing scope.

## Completion

- [x] Concrete design, manifest and pricing evidence prepared
- [x] Operator deferral recorded; activation and dependent qualification remain on hold
- [ ] Explicit CPU-class/cost approval recorded
- [ ] Approved activation verified and documented

See the [candidate design](../dashboard-operator-ui/infrastructure-design/cpu-quota-recovery/infrastructure-design.md).

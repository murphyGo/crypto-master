# Infrastructure Design: Claude CLI Node Compatibility

**Date:** 2026-10-09 · **Debt:** DEBT-082
**Status:** Approved local implementation and amd64 build complete; runtime acceptance PARTIAL
**Units:** `notifications-ops`; secondary `ai-feedback-loop`

## Scope and Topology

The [execution plan](../../../inception/plans/execution-plan.md) requires
Infrastructure Design for notifications-ops deployment/runtime changes. This
artifact records the infrastructure implications of the approved
[NFR design](../nfr-design/claude-node-compatibility.md); it adds no new operator
gate or application behavior.

The runtime stays one Fly Machine containing the engine and Streamlit
dashboard, supervised by `start.sh` through `tini`. The existing `/data`
persistent volume, port 8080, health endpoint, region, machine resources,
secrets, and paper/live controls retain their existing configuration.
Only Docker runtime packaging changes: digest-pinned Node 24.21.0 and Python
3.13.16 stages both use Debian Trixie, with Node/npm selectively copied into
the Python stage and the required shared libraries installed there. Claude
CLI remains the npm package at 2.1.295 with strict engine validation.

## Build and Acceptance Boundary

The preceding Fly image used Linux amd64. The approved local check therefore
targets `linux/amd64` despite the local Docker Desktop arm64 host. A successful
arm64-only build would not satisfy this acceptance. Record both base index
digests, the resulting local image ID and architecture, and build/runtime
check results in the session and cross-check.

Use a temporary build context containing only the explicitly selected tracked
runtime inputs plus the approved Dockerfile. Exclude `.env`, local `.claude`
configuration, runtime `data/`, and credentials. Local smoke containers use
no production volume or injected credentials; temporary data writes are
confined to disposable container storage. Check CLI versions/help, shared
libraries, and Python imports without launching trading or authenticated
inference. Mock-based Python tests supplement these image checks.

The local build and isolated Python/dashboard checks pass. Final CLI help
acceptance remains unverified because both the legacy local emulator and a
bounded modern-emulator attempt failed inconsistently. Complete that check
on native amd64 or a usable emulator. This is a tooling/evidence limitation,
not an additional operator approval condition; authenticated inference and
production rollout remain distinct.

## Operations and Rollback

The user approved local Dockerfile/runbook implementation and image validation
with “진행시켜”, then explicitly authorized commit, push, and Fly deployment
with “커밋 푸시 배포까지 해줘”. Native validation and rollout remain pending.
Successful local image validation does not replace production rollout evidence.
DEBT-082 remains active while final image acceptance or production remediation
is outstanding; its preceding v50 / Node 20.19.2 snapshot is explicitly dated,
not a fresh health observation.

For the now-authorized rollout, first refresh the live release/image identity
and record the previous immutable image as the rollback target. After rollout,
verify image identity, Node/Claude versions, dashboard health, and a completed
engine cycle with the existing configuration. Treat authenticated `claude -p`
inference as a separate check. Rollback restores the recorded prior image;
it must not delete or migrate the volume or alter trading settings.

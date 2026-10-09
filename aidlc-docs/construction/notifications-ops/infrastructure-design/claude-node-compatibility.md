# Infrastructure Design: Claude CLI Node Compatibility

**Date:** 2026-10-09 · **Debt:** DEBT-082
**Status:** Complete; current v55 native production compatibility PASS
**Units:** `notifications-ops`; secondary `ai-feedback-loop`

## Scope and Topology

The [execution plan](../../../inception/plans/execution-plan.md) requires
Infrastructure Design for notifications-ops deployment/runtime changes. This
artifact records the infrastructure implications of the approved
[NFR design](../nfr-design/claude-node-compatibility.md); it adds no new operator
gate or application behavior.

The runtime stays one Fly Machine containing the engine and Streamlit
dashboard, supervised by `start.sh` through `tini`. The existing `/data`
persistent volume, port 8080, health endpoint, region, secrets, and paper/live
controls retain their existing configuration. The recovery increased memory
to 2 GB as recorded below.
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

The local build and isolated Python/dashboard checks pass. Native remote
preflight resolved the local QEMU limitation: three retained help outputs,
required CLI flags, Node/Claude versions, and `ldd` pass. Integrated commit
`35e14b4` also passes 2,618 tests and repository quality checks.

Concurrent upstream Codex migration remains in source `35e14b4`, including
Codex 0.153.4. Our initial v53 rollout attempted to preserve Claude; another
session activated Codex with auth in v55 while our v54 rollback was underway.
Current provider/auth observations supersede the earlier login-pending
snapshot without claiming this team performed that activation or model call.

## Operations and Recovery

The user approved local repair with “진행시켜” and commit/push/deployment with
“커밋 푸시 배포까지 해줘”. The initial v53 acceptance failed after HTTP 200,
followed by hung SSH/health checks; v54 rollback overlapped concurrent v55.
No clean image comparison or incident root cause is established.

Current v55 image `9adffd34…` contains all 167 verified source35e14b4 runtime
artifacts and passes native Node/Claude help/library checks, service health,
and a completed paper cycle. Upstream changes through `3f4864f`
(DEBT-074/078/084/085/086) are not deployed. The final helper exited 0 with corrected Codex/paper assertions.
DEBT-082 is resolved on this native compatibility evidence.

Our recovery increased actual v55 memory from 1 GB to 2 GB. Source `fly.toml`
records the same temporary capacity to avoid a later implicit downgrade.
Separate bounded-loading DEBT-083 remains unresolved; this mitigation neither
proves that defect caused the incident nor establishes final capacity needs.
The volume, trading mode, and credential contents were not changed by this
repair. See the session/cross-check for complete image identities and times.

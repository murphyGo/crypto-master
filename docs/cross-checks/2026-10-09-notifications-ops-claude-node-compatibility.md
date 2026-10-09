# Cross-Check: Claude CLI / Node Compatibility Repair

**Date:** 2026-10-09 · **Units:** `notifications-ops` / `ai-feedback-loop`

**Status: PASS — DEBT-082 resolved.** Final read-only production verification
started at **2026-10-09T13:52:48.176970Z** and exited 0. Current v55 is healthy and paper
mode; its 167 runtime artifacts match source **`35e14b4`**. Upstream changes
through `3f4864f` for DEBT-074/078/084/085/086 were not deployed.

## Verification

| Check | Result |
|-------|--------|
| Current release/image | v55; `sha256:9adffd345d6a82d239d2c07b77a6112b4909a414bd12ca5fc0573f9383bcabfe` |
| Runtime versions | Node 24.21.0; Python 3.13.16; npm/npx 11.19.0; Claude 2.1.295; Codex 0.153.4 |
| Native Claude compatibility | Three help checks exit 0 with required print/model flags; `ldd` exits 0 with no missing Node libraries |
| Artifact identity | All 167 runtime file hashes match source `35e14b41b2a7b7844355edcaf42b41f160db4d71`; zero mismatches |
| Current operations | Codex provider, auth file present, paper mode, engine/dashboard running; Fly service check passing and HTTP 200 |
| Cycle after latest restart | `a387b999-cc45-48c3-bf3e-9d74ee636385` completed at 13:48:32Z after the 13:47:48Z start |
| Integrated source QA | 2,618 tests in 82.88s on Python 3.11.13; Black 222 files; Ruff; mypy 122 files pass |
| Native preflight | Three retained 22,108-byte help outputs plus flags, versions, and ldd pass; this resolved the earlier local QEMU limitation |

Initial focused QA also passed 171 tests and the original local image passed
packaging/import and isolated health checks. Those are earlier evidence, not
claims that the latest undeployed strategy change was tested or deployed here.

## Rollout Attribution and Limits

Our v53 image `51bb18b9…` initially returned HTTP 200, then SSH/health checks
hung and no completed first cycle was verified. Our v54 rollback to the
prior image ran, but another session deployed v55 at 13:43:09Z and activated
Codex with its dedicated auth. This overlap prevents a clean old/new-image
comparison or a proven cause for the v53 failure.

Our memory-only recovery raised the actual v55 machine from 1 GB to 2 GB.
The closeout records that capacity in `fly.toml` so a later normal deployment
does not silently restore 1 GB. This is a temporary operational mitigation;
separate bounded-loading DEBT-083 remains unresolved. It does not alter the
already verified runtime image or establish that issue as the failure cause.

The first verification helper exited 1 only because its old expected-Claude
provider assertion disagreed with concurrently activated Codex. The retained
checks were valid; corrected assertions against the observed Codex/paper
state then exited 0 with `DEBT082_PRODUCTION_VERIFICATION_PASS`. No
credential values were recorded, and this team lead made no authenticated
model call. A completed cycle is not presented as Claude inference proof.

## Scope and Closure

The user approved implementation with “진행시켜” and explicitly requested
“커밋 푸시 배포까지 해줘”. Node/Python image pins, strict Claude engine checks,
and runbook changes satisfy the runtime compatibility scope for US-014 /
NFR-004/NFR-011 and the installed CLI contract for US-004 / NFR-002/CON-001.
DEBT-082 closes on current native production evidence despite the failed
initial rollout. Upstream Codex work and DEBT-074/078/084/085/086 records are
preserved; root-workspace DEBT-083/dashboard design and `.claude` changes are
not absorbed into this change.

See the [plan](../../aidlc-docs/construction/plans/notifications-ops-claude-node-compatibility-plan.md),
[NFR design](../../aidlc-docs/construction/notifications-ops/nfr-design/claude-node-compatibility.md),
[Infrastructure Design](../../aidlc-docs/construction/notifications-ops/infrastructure-design/claude-node-compatibility.md),
and [session evidence](../sessions/2026-10-09-notifications-ops-claude-node-compatibility.md).

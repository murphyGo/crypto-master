# Operational Follow-up Plan: Claude CLI Node Compatibility

**Date:** 2026-10-09
**Primary unit:** `notifications-ops`
**Secondary unit:** `ai-feedback-loop`
**Stage:** Complete; native production compatibility verified on current v55
**Queue:** Session follow-up from the preceding Fly deployment
**Related debt:** DEBT-082 (resolved 2026-10-09)

## Task and Selection

Resolve the observed mismatch between the container's Node runtime and the
installed Claude CLI package's declared Node requirement. The initial cycle
completed diagnosis and a reviewable container-only
remediation. The operator then approved the specified local Dockerfile/runbook
implementation and image validation with “진행시켜”. That bounded implementation
is now applied. In the subsequent turn, the operator explicitly requested
“커밋 푸시 배포까지 해줘”, authorizing commit, push, and deployment of this
repair. Native production acceptance has since passed on current v55.

The queue survey at local HEAD `16eef0d` found:

- `docs/TECH-DEBT.md` reported zero active items; DEBT-081 is resolved.
- `docs/team-priorities.md` has no open item.
- The latest CAH-15 closeout cross-check is PASS. Slice 3 is a terminal NO-GO
  decision, not an unfinished extraction.
- Older functional-design checkboxes point to later completed construction.
  The unchecked `strategy-tuning` verification command remains in a plan whose
  completion checklist is closed; later repository verification passed 2,604
  tests. Historical consistency-hardening mypy blockers are superseded by
  DEBT-067 closure and the later clean 114-file mypy gate. They are not new
  implementation tasks.
- Existing DEBT-080 production snapshot/replay follow-up and Funding/OI
  empirical-observation gates remain separate operator/evidence work. This
  task does not refresh datasets, adopt a strategy, or activate enforcement.

The preceding deployment supplied a concrete operational warning: Claude Code
`2.1.295` declares Node `>=22.0.0`, while the deployed runtime reported Node
`v20.19.2`. Package metadata was rechecked this cycle. See the design artifact
for evidence provenance and the limited meaning of the successful CLI version
check.

## Requirement and Story Mapping

| Context | Application to this task |
|---------|--------------------------|
| US-014; `notifications-ops` | Maintain a deployable runtime with a supported CLI dependency and explicit operations evidence. |
| US-004; `ai-feedback-loop` | Preserve the existing Claude CLI invocation path used for strategy analysis and feedback. |
| NFR-002; CON-001 | Keep `claude -p` through the existing subprocess client; introduce no direct Anthropic API integration. |
| NFR-004; NFR-011 | Keep credentials in the existing runtime environment; place no credential values in image layers, artifacts, or logs. |

Canonical references: `aidlc-docs/inception/requirements/requirements.md`,
`aidlc-docs/inception/user-stories/stories.md`,
`aidlc-docs/inception/application-design/unit-of-work-story-map.md`, and
`aidlc-docs/inception/units/unit-of-work.md`.

## Current Cycle Deliverables

- [x] Audit the higher-priority queues and identify the concrete session
      follow-up without reopening completed historical work.
- [x] Confirm the baseline Dockerfile installed Debian `nodejs`/`npm` plus an
      unpinned Claude CLI package; distinguish package metadata from runtime
      execution evidence.
- [x] Design a pinned official Node 24 LTS and Python 3.13 Trixie image
      arrangement, retaining deployed Claude CLI `2.1.295` and enforcing its
      Node requirement during the build.
- [x] Specify implementation scope, build checks, runtime acceptance, rollback,
      and the explicit operator approval boundary in
      `aidlc-docs/construction/notifications-ops/nfr-design/claude-node-compatibility.md`.

These deliverables closed the initial diagnosis/design slice. The reviewed
proposal was subsequently approved and applied without expanding its scope.
Infrastructure Design is required by the notifications-ops execution matrix;
the approved topology and validation boundary are recorded in
`aidlc-docs/construction/notifications-ops/infrastructure-design/claude-node-compatibility.md`.

## Approved Implementation and Acceptance

- [x] Obtain explicit approval for the proposed `Dockerfile`/runbook change
      and its local image validation (operator: “진행시켜”).
- [x] Apply the reviewed official Node 24/Python 3.13 Trixie multistage
      arrangement; remove Debian's Node/npm packages, retain required shared
      libraries, and pin Claude CLI `2.1.295`.
- [x] Add build-time strict engine validation plus Node/npm/Claude version
      checks; narrowly update the deployment runbook with the version policy
      and verification commands.
- [x] Build and inspect the exact target Linux architecture image; record
      the local image identity, base platform manifests, strict engine gate,
      and Python/health smoke results.
- [x] Complete native amd64 CLI acceptance: three retained help outputs
      (22,108 bytes each) expose the required flags; Node/Claude versions and
      `ldd` pass.
- [x] Complete scoped static/regression QA and document actual results,
      keeping implementation status separate from future production verification.
- [x] Obtain explicit commit/push/deploy authorization (operator:
      “커밋 푸시 배포까지 해줘”).
- [x] Integrate current upstream safely and push scoped commit `35e14b4`;
      integrated QA passes 2,618 tests, Black, Ruff, and mypy.
- [x] Record the authorized rollout and recovery chronology; verify current
      deployed image, versions/help, artifacts, health, and completed cycle.

## Verification Outcome

**PASS / DEBT-082 resolved.** Integrated source `35e14b4` passed 2,618 tests,
Black 222 files, Ruff, and mypy 122 files. Native remote preflight passed
three CLI help/flag checks and `ldd`, resolving the earlier QEMU limitation.
Final read-only production verification started at 13:52:48Z and exited 0: current v55
has Node 24.21.0 / Claude 2.1.295, repeated help checks, no missing libraries,
167 matching source35e14b4 artifacts, HTTP 200/passing service health, and a
paper cycle completed at 13:48:32Z after the latest restart.

Our initial v53 rollout failed health/SSH acceptance; v54 rollback overlapped
another session's v55 deployment and Codex activation. The current provider
is Codex with auth present. The overlap prevents a clean causal comparison
of old/new images. Our memory recovery raised v55 to 2 GB, and that temporary
capacity is recorded in `fly.toml`; separate bounded-loading work remains
unresolved. Upstream changes through `3f4864f` for DEBT-074/078/084/085/086 were not
deployed.

The [cross-check](../../../docs/cross-checks/2026-10-09-notifications-ops-claude-node-compatibility.md)
and session retain image identities, failed attempts, corrected provider
assertions, and the final evidence. No authenticated model call by this team
lead or Claude inference success is claimed.

## Approval Boundary and Exclusions

The user-invoked [team skill](../../../.claude/skills/team/SKILL.md) explicitly
says to halt and ask when work touches "live trading credentials, mainnet
money, deployment config, or API keys." Applying the proposed `Dockerfile`
change crosses the deployment-config boundary. The operator explicitly
approved the presented local `Dockerfile`/runbook change and image validation
with “진행시켜”; that approval satisfies the implementation boundary. No
additional approval is needed to complete those checks. The subsequent
explicit instruction “커밋 푸시 배포까지 해줘” also authorizes commit, push, and
deployment of this repair. Native and current production checks passed; the
recorded recovery and concurrent rollout are part of the operational outcome.

The sole `fly.toml` change preserves the 2 GB recovery capacity.
Application code, trading settings, `start.sh`, runtime `data/`,
credentials, live controls, Python dependencies, and local `.claude` settings
are outside this slice. No trading hypothesis changes, so quant review is not
required. Existing focused regression tests supplement the image checks; no new
implementation-mirroring test is required. Image evidence is required rather
than reusing the earlier Python-suite result as proof of Node compatibility.

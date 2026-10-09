# Operational Follow-up Plan: Claude CLI Node Compatibility

**Date:** 2026-10-09
**Primary unit:** `notifications-ops`
**Secondary unit:** `ai-feedback-loop`
**Stage:** Commit/push/deploy authorized; native runtime acceptance and rollout pending
**Queue:** Session follow-up from the preceding Fly deployment
**Related debt:** DEBT-082 (active; CLI help acceptance and production rollout pending)

## Task and Selection

Resolve the observed mismatch between the container's Node runtime and the
installed Claude CLI package's declared Node requirement. The initial cycle
completed diagnosis and a reviewable container-only
remediation. The operator then approved the specified local Dockerfile/runbook
implementation and image validation with “진행시켜”. That bounded implementation
is now applied. In the subsequent turn, the operator explicitly requested
“커밋 푸시 배포까지 해줘”, authorizing commit, push, and deployment of this
repair. Runtime acceptance and rollout evidence remain pending.

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
- [ ] Complete the remaining final-image CLI help acceptance. The local amd64
      emulation is unstable; a retained, reliable help/flag smoke is required
      before full runtime acceptance can pass.
- [x] Complete scoped static/regression QA and document actual results,
      keeping implementation status separate from future production verification.
- [x] Obtain explicit commit/push/deploy authorization (operator:
      “커밋 푸시 배포까지 해줘”).
- [ ] Complete native target-image validation, scoped commit/push, authorized
      rollout, and production verification; record the actual result.

## Verification Outcome

The amd64 build, pinned versions, strict package engine check, 171 focused
tests, ten application/dependency imports, pip consistency, startup syntax,
159 runtime artifact hashes, and isolated dashboard health all pass. Node
libraries resolve through loader trace and the running process report; local
`ldd` reports a guest-emulation failure (wrapper exit 1, guest exit 139).

Overall runtime acceptance is **PARTIAL**. Claude CLI help is not reliably
verified: the old local emulator produced timeout/SIGSEGV outcomes and a
bounded modern-emulator retry failed with a JavaScriptCore MemoryExhaustion
assertion. The remaining help/flag gate needs a native amd64 runner or usable
amd64 emulation. No source defect or authenticated inference success is
claimed. This is a validation-environment limitation, not another approval
gate. DEBT-082 remains active. The operator has now authorized commit, push,
and rollout; this approval does not itself establish a passing native check
or completed deployment.

## Approval Boundary and Exclusions

The user-invoked [team skill](../../../.claude/skills/team/SKILL.md) explicitly
says to halt and ask when work touches "live trading credentials, mainnet
money, deployment config, or API keys." Applying the proposed `Dockerfile`
change crosses the deployment-config boundary. The operator explicitly
approved the presented local `Dockerfile`/runbook change and image validation
with “진행시켜”; that approval satisfies the implementation boundary. No
additional approval is needed to complete those checks. The subsequent
explicit instruction “커밋 푸시 배포까지 해줘” also authorizes commit, push, and
deployment of this repair. Native checks and actual rollout results remain
evidence gates; no completed deployment is claimed at this checkpoint.

Application code, trading settings, `fly.toml`, `start.sh`, runtime `data/`,
credentials, live controls, Python dependencies, and local `.claude` settings
are outside this slice. No trading hypothesis changes, so quant review is not
required. Existing focused regression tests supplement the image checks; no new
implementation-mirroring test is required. Image evidence is required rather
than reusing the earlier Python-suite result as proof of Node compatibility.

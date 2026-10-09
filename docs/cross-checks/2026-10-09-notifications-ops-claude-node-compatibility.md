# Cross-Check: Claude CLI / Node Compatibility Repair

**Date:** 2026-10-09 · **Units:** `notifications-ops` / `ai-feedback-loop`

**Scope:** Approved local Dockerfile/runbook repair and image validation.
**Status:** **PARTIAL** runtime acceptance. Implementation, static/regression
QA, amd64 build, packaging, and isolated health checks PASS. Repeatable CLI
help/flag acceptance remains unverified under local emulation. DEBT-082 stays
active (Medium). The operator has now authorized commit, push, and deployment;
native runtime checks and rollout verification remain pending.

## Traceability and Scope

| Contract | Result |
|----------|--------|
| US-014, NFR-004/NFR-011 operations and secrets | Approved Docker packaging change preserves runtime credential handling. The context excludes `.env`, `.claude`, and runtime `data/`; no secret or production volume change. |
| US-004, NFR-002/CON-001 Claude integration | Existing `claude -p` application contract is unchanged. Authenticated inference was not run. |
| Dependency compatibility | Baseline v50 snapshot used Node 20.19.2 with CLI 2.1.295 requiring Node >=22. The candidate uses pinned Node 24.21.0 / Python 3.13.16 / CLI 2.1.295 and strict engine installation. |
| Design and operations | Plan, NFR and Infrastructure Design, runbook, debt, and state distinguish passing local checks from remaining CLI acceptance and production rollout. |

The v50 production snapshot at 2026-10-09T09:37:06Z is historical. The
pre-rollout release listing is now v51; its runtime snapshot is being
validated, with no new health result yet. No outage or source defect is established by this
repair's local verification limits.

## Passing Checks

- `uv run pytest tests/test_ai_claude.py tests/test_main_dispatch.py tests/test_config.py`:
  **171 passed in 2.16s**, Darwin / Python 3.13.0.
- Independent static QA: exact reviewed Dockerfile candidate, all three RUN
  commands' `sh -n`, embedded JavaScript `node --check`, byte-identical
  `WORKDIR` onward versus HEAD, and `git diff --check` pass. No blocking
  source-review finding.
- `linux/amd64` image build: PASS. Local image ID
  `sha256:63d6cce6114b488ba24ae9b140caa305ae98b5a4f9db0fb26ad78ad3077ff061`;
  this is not a published registry manifest. Base index/platform digests,
  context provenance, and commands are recorded in the session.
- Node 24.21.0, npm/npx 11.19.0, Claude 2.1.295, strict engine installation,
  and no `EBADENGINE`: PASS. Package postinstall execution was independently
  verified after npm's install-script advisory.
- Node library resolution: PASS with qualification. `ldd` exits 1 with stderr
  reporting guest exit 139 on both candidate and official Node base under the
  legacy local emulator. Loader trace and the running Node process report
  resolve all seven libraries, with none missing. This is documented alternate
  evidence; a successful `ldd` command is not claimed.
- Read-only, network-disabled amd64 smoke with disposable tmpfs: Python
  3.13.16; all ten application/dependency imports; `pip check`; startup shell
  syntax; and `ClaudeCLI.is_available()` pass. All 159 runtime artifact hashes
  match the explicit clean context.
- Isolated Streamlit 1.65.0 loopback health: HTTP 200 / `ok`. The engine was
  not started, authenticated inference was not run, and the process was
  stopped afterward. No verification containers remain.

## Remaining CLI Acceptance

The old local Docker emulator produced SIGSEGV and 45–90 second timeouts for
`claude --help`. One exit-0 run did not retain help output and therefore cannot
prove repeatable flag availability. A bounded official QEMU 10.2.3 retry also
failed with a JavaScriptCore MemoryExhaustion assertion, including with
AVX-capable CPU emulation and JIT/gigacage disabled. The session records the
binary provenance and failure details. No further Dockerfile change was made.

Complete retained, repeatable `claude --help` output and the existing
`-p`/`--print`, `--model` flag checks on native amd64 or usable emulation before
full runtime acceptance. This unresolved validation limit is tracked in
DEBT-082; no additional debt or source defect is asserted.

## Authorization and Closeout

The operator approved the presented Dockerfile/runbook change and local image
validation with “진행시켜”. This satisfies the invoked
[team skill](../../.claude/skills/team/SKILL.md)'s deployment-configuration gate.
The remaining test limitation is not a new approval requirement. In the
subsequent turn, the operator explicitly requested “커밋 푸시 배포까지 해줘”,
authorizing commit, push, and deployment of this repair. Native checks and
rollout verification are still pending. Credentials, trading settings,
application code, and unrelated local `.claude` work remain unchanged by this
repair.

See the [construction plan](../../aidlc-docs/construction/plans/notifications-ops-claude-node-compatibility-plan.md),
[NFR design](../../aidlc-docs/construction/notifications-ops/nfr-design/claude-node-compatibility.md),
[Infrastructure Design](../../aidlc-docs/construction/notifications-ops/infrastructure-design/claude-node-compatibility.md),
and [session evidence](../sessions/2026-10-09-notifications-ops-claude-node-compatibility.md).

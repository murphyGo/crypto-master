# Session: Claude CLI / Node Compatibility Repair

**Date:** 2026-10-09 · **Baseline:** `16eef0d`

**Primary:** `notifications-ops` (US-014, NFR-004, NFR-011).
**Secondary:** `ai-feedback-loop` (US-004, NFR-002, CON-001).

**Current outcome:** The operator approved local Dockerfile/runbook repair and
image validation with “진행시켜”, then explicitly authorized commit, push, and
deployment with “커밋 푸시 배포까지 해줘”. The reviewed Dockerfile is applied; static QA
and 171 focused tests pass. Target amd64 build, packaging, and isolated health
checks pass; runtime acceptance is **PARTIAL** because CLI help remains
unverified under local emulation. A native amd64 runner or usable emulator
is required for the remaining help/flag check.
DEBT-082 remains active, Medium. No new deployment or authenticated inference
is claimed. The diagnosis entries below describe the initial pre-approval
slice; the approved continuation is recorded afterward.

## Initial Diagnosis: Selection and Evidence

The team selected a session follow-up from the preceding Fly v50 deployment
warning after finding no earlier blocking queue item or active debt. This is
not a new production outage investigation.

- **Prior operational snapshot, not refreshed this cycle:** v50 / `b1c88a2`,
  checked at 2026-10-09T09:37:06Z, reported Node `v20.19.2`, Claude CLI
  `2.1.295` (`--version` exit 0), and 159 consistent artifacts. A paper-engine
  cycle completed at 09:36:38.746809Z. Authenticated `claude -p` was not proved.
- **Current package evidence:**
  `npm view @anthropic-ai/claude-code@2.1.295 version engines dist.integrity --json`
  returned version `2.1.295`, `engines.node >=22.0.0`, and package integrity.
  [Versioned package metadata](https://registry.npmjs.org/@anthropic-ai/claude-code/2.1.295)
  confirms the engine mismatch with the prior snapshot.
- **Current repository:** `Dockerfile` uses floating `python:3.13-slim`,
  Debian Node/npm, and unversioned Claude installation; its Node 18+ comment
  is stale. [Node lifecycle](https://nodejs.org/en/about/previous-releases)
  lists Node 20 as EOL and Node 22/24 as LTS.

## Initial Proposal and Verification Limits

The planner recommends pinned official Node `24.21.0-trixie-slim` and Python
`3.13.16-slim-trixie` stages, selective Node/npm copies, required runtime
libraries, Claude `2.1.295`, engine-strict installation, and image version
assertions. The senior developer prepared an unapplied patch; its
`git apply --check` passed. Verified registry index digests and the complete
patch are preserved in the [design](../../aidlc-docs/construction/notifications-ops/nfr-design/claude-node-compatibility.md).

The initial npm-cache permission and registry certificate failures were
resolved by authorized read-only retries. They are not outstanding blockers.
The local Docker daemon remains unavailable: no candidate image was built or
run. No new Python regression test run, authenticated inference, or current
production-health claim is made. Final-image architecture/library/version
checks and mocked CLI tests remain implementation acceptance work in the
[plan](../../aidlc-docs/construction/plans/notifications-ops-claude-node-compatibility-plan.md).

## Independent Proposal QA

QA passed patch applicability, embedded/temp diff equality, in-memory
candidate equality, `sh -n` for three RUN commands, and `git diff --check`.
`ENV`/`WORKDIR`/`EXPOSE`/`ENTRYPOINT`/`CMD` are unchanged in the proposal;
`Dockerfile`, `fly.toml`, `start.sh`, and `src/ai/claude.py` have empty actual
diffs. No blocking proposal finding remains. These static checks do not prove
image execution, shared-library availability, or authenticated inference.

## Initial Approval Boundary and Diagnosis Closeout

The invoked [team skill](../../.claude/skills/team/SKILL.md) explicitly says
"Halt and ask the user when":

> The work touches live trading credentials, mainnet money, deployment config, or API keys.

Applying the candidate changes deployment configuration, so implementation
needs explicit approval after proposal review. Earlier permission to deploy
`b1c88a2` does not cover this new upgrade. This cycle's diagnosis and proposal
are complete; DEBT-082 remains active until implementation and acceptance.
No Docker/source/configuration/credential/runtime-data mutation, commit,
push, deployment, or live order occurred; unrelated `.claude` work remains.

Scoped [cross-check](../cross-checks/2026-10-09-notifications-ops-claude-node-compatibility.md)
and the debt map/state distinguish completed diagnosis from pending work.

## Approved Implementation Continuation

The following checkpoints preserve the verification sequence. Their pending
items are superseded by the final local acceptance section below.

The operator approved the concrete local Dockerfile/runbook change and image
validation with “진행시켜”. This satisfies the team skill's deployment-config
implementation gate. Commit, push, and deployment are outside this slice.

The senior developer applied the reviewed candidate exactly (Dockerfile
SHA-256 `525abf308f820840989b990f9ef7844a9b6575f76f4d23d0ffb10bc313e21678`).
The runtime uses official digest-pinned Node 24.21.0 and Python 3.13.16 Trixie
stages, required shared libraries, and engine-strict Claude 2.1.295. The
runbook now records pin updates and image checks. Required
[Infrastructure Design](../../aidlc-docs/construction/notifications-ops/infrastructure-design/claude-node-compatibility.md)
records unchanged topology, target architecture, isolated validation, and
rollback boundaries.

Independent implementation QA reported:

- `uv run pytest tests/test_ai_claude.py tests/test_main_dispatch.py tests/test_config.py`:
  **171 passed in 2.16s**, Darwin / Python 3.13.0.
- Exact reviewed-candidate Dockerfile hash, all three RUN commands' `sh -n`,
  embedded JavaScript `node --check`, and `git diff --check`: PASS.
- `WORKDIR` onward is byte-identical to HEAD, preserving the application
  packaging and startup contract. No blocking static review finding.

Docker Desktop 4.10.1 / Engine 20.10.17 was started on the arm64 host. The
build targets `linux/amd64`, matching the preceding Fly production image.
The context was constructed from an explicit archive of committed runtime
inputs plus the approved Dockerfile; `.env`, `.claude`, and runtime `data/`
were excluded. The initial build failed at the macOS credential helper before
base resolution; an authorized retry passed the strict Claude install/version
stage and is still building Python dependencies. Final image identity and
runtime smoke evidence are pending.

No authenticated `claude -p`, application source modification, credential or
trading-setting change, production volume write, commit, push, or deployment
was performed. The unrelated local `.claude` changes remain outside this work.

### Target Image Build Evidence

The authorized retry completed the `linux/amd64` build successfully. The image
is local only; no registry manifest was published and no Fly rollout occurred.

| Item | Result |
|------|--------|
| Local tag | `crypto-master:debt-082-node24` |
| Local image ID | `sha256:63d6cce6114b488ba24ae9b140caa305ae98b5a4f9db0fb26ad78ad3077ff061` |
| Platform / local size | `linux/amd64`; 1,221,523,906 bytes |
| Node amd64 manifest | `sha256:c83040f7e24bacea68e58a0b96a484ba430bf24abb2973eab7ba4701144b7b63` |
| Python amd64 manifest | `sha256:8fb4cfa1a2616d7b8e0c2175cc6ad68f5729c34ea8488c0b360d2934b7be9024` |
| Runtime versions | Node `24.21.0`; npm/npx `11.19.0`; Claude `2.1.295` |
| Engine installation | Strict installation passed; no `EBADENGINE`. The npm install-script advisory was checked independently: package postinstall was allowed and executed. |

Runtime acceptance is not yet passed. `ldd` exits 1 with stderr reporting guest exit 139 on both the candidate
and the official Node base in this local amd64 emulation environment; loader
trace and the running Node process report resolve all seven libraries. The
CLI help smoke separately exits with SIGSEGV (signal 11) and is under
investigation. Neither library evidence nor a successful CLI version check
substitutes for the pending help acceptance. Final Python/health checks are
also pending at this checkpoint.

### Isolated Python, Packaging, and Health Smoke

The following target-image check exited successfully:

```bash
docker run --rm -i --platform linux/amd64 --network none --read-only \
  --tmpfs /tmp --tmpfs /data --tmpfs /app/data --tmpfs /root \
  crypto-master:debt-082-node24 python - \
  < /private/tmp/crypto-master-debt082-smoke-non-help.py \
  > /private/tmp/crypto-master-debt082-smoke-non-help-tmpfs.log 2>&1
```

The temporary script/log are local verification artifacts, not shipped runtime
files. The check verified `x86_64`, absence of injected API credentials and
`/app/.env` / `/app/.claude`, Python 3.13.16, the pinned Node/npm/npx/Claude
versions, Streamlit 1.65.0, and Claude package engine metadata. It imported
`src.main`, `src.ai.claude`, `src.config`, `streamlit`, `ccxt`, `pandas`, `numpy`,
`dotenv`, `yaml`, and `dateutil`; `python -m pip check`, `bash -n /app/start.sh`,
and `ClaudeCLI.is_available()` passed.

The loader trace resolved all seven Node shared libraries without a missing
library. `ldd` itself reported its child exit 139 (wrapper exit 1), so that
original smoke remains explicitly qualified. The first read-only attempt
rejected the existing logger's relative `/app/data` writes; the completed
check supplied disposable tmpfs there as well as `/data`, without touching
host or production runtime data.

The isolated Streamlit process returned HTTP 200 / `ok` on
`127.0.0.1:18080/_stcore/health` with `--network none`; the engine was not
started, authenticated inference was not run, and the process was terminated
after checking health. All 159 runtime artifact hashes matched the clean
build context, with zero mismatches. CLI help acceptance is tracked separately
while the emulation issue is investigated.

## Final Local Acceptance: PARTIAL

Local implementation is complete and the approved target image builds.
Independent static/regression QA, strict engine installation, pinned runtime
versions, library resolution via loader trace/process report, Python/package
imports and consistency, startup syntax, 159 artifact hashes, and isolated
dashboard health all pass. The CLI help/flag gate is **not passed**.

The old Docker emulator produced SIGSEGV and 45–90 second timeouts for
`claude --help`. QA observed one exit-0 run without retained help output;
that does not satisfy reproducible flag evidence. A bounded retry used
verified official QEMU 10.2.3 for arm64, SHA-256
`ca19f8d202b977904f70fa6464b5ef9439740951d40f89730d2f2981f853bfaa`,
mounted read-only into a disposable container without replacing Docker's
emulator. Even with `-cpu max`, `GIGACAGE_ENABLED=0`, and `BUN_JSC_useJIT=0`,
the direct retry failed with JavaScriptCore `MemoryExhaustion` / SIGABRT in
110 ms at 28.61 MB peak memory. Cleanup exit 137 was not an OOM kill. No
verification containers remain, and no further source change was made.

These observations establish an unresolved local validation limit, not a
proven application or image defect. Complete retained `claude --help` output
and existing `-p`/`--print`, `--model` flag checks on native amd64 or a usable
emulator before declaring full runtime acceptance. The existing operator
approval already covers local validation; this limitation is not a new skill
approval gate.

DEBT-082 remains active with this evidence gap and the separately scoped
production rollout. No commit, push, deployment, production health refresh,
engine start, authenticated inference, credential change, trading-setting
change, or runtime volume mutation was performed in this continuation.

## Commit, Push, and Deployment Authorization

The subsequent user instruction “커밋 푸시 배포까지 해줘” explicitly authorizes
commit, push, and deployment of this DEBT-082 repair. It supersedes the earlier
local-only scope. Native runtime acceptance and production verification are
still pending; authorization alone does not resolve DEBT-082 or add a test
pass. Existing credential and trading-mode settings remain outside the change.

The pre-rollout Fly release listing has advanced from the historical v50
snapshot to **v51**, created at 09:58:31 on 2026-10-09. Root is validating the
current runtime snapshot before changing production. Its listed image is:

- Image: `registry.fly.io/crypto-master:deployment-01M4G0FW4FQV2VMX175K77DTWD`.
- Digest: `sha256:7deac463e936fe238077a6eae6695660fe7bf94320b1b068cd70308e3b49c9e5`.

This records the refreshed pre-rollout identity, not a new runtime health or
native CLI result. No DEBT-082 deployment success is claimed at this checkpoint.
The unrelated dashboard-operator-ui design work and local `.claude` changes
remain outside the scoped commit and are preserved.

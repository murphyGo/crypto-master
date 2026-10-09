# NFR Design: Claude CLI Node Compatibility

**Date:** 2026-10-09
**Status:** Approved Dockerfile applied; amd64 build PASS; runtime acceptance PARTIAL
**Owner:** `notifications-ops`; secondary `ai-feedback-loop`
**Stories / requirements:** US-014, US-004; NFR-002, NFR-004, NFR-011, CON-001
**Related debt:** DEBT-082

## Problem and Evidence Boundary

The baseline Dockerfile installed Debian's `nodejs` and `npm`, then executed
`npm install -g @anthropic-ai/claude-code` without a package version or strict
engine validation. Its comment described Node 18+ as sufficient. The
current npm package metadata and preceding deployment demonstrate that this
assumption no longer holds.

| Evidence | Observation | Provenance / limit |
|----------|-------------|--------------------|
| Baseline `Dockerfile` | `FROM python:3.13-slim`; Debian Node/npm; unpinned Claude install | Read at HEAD `16eef0d` before the approved local change. |
| Production Node and CLI versions | Node `v20.19.2`; Claude Code `2.1.295` | Preceding Fly v50 deployment snapshot at `2026-10-09T09:37:06Z`, associated with `b1c88a2`; not reread from production in this cycle. |
| npm `2.1.295` metadata | `engines.node` is `>=22.0.0` | Rechecked this cycle using `npm view @anthropic-ai/claude-code@2.1.295 version engines dist.integrity --json`. |
| Previous operational smoke | `claude --version` exited 0 and a paper engine cycle completed | Shows the CLI launches and the engine ran; does not establish authenticated `claude -p` inference or complete compatibility. |
| Local image tooling | Docker Desktop 4.10.1 / Engine 20.10.17 on an arm64 host; daemon started for validation | The authorized retry built `linux/amd64` successfully. Node/Claude versions pass; library loading is evidenced by loader trace/process report, while CLI help acceptance remains unresolved. |

The supported conclusion is a declared Node-engine mismatch and a build
reproducibility gap, with no proven runtime outage. The fix must eliminate the
mismatch while preserving the existing CLI contract; a working version command
does not waive the declared requirement.

The authoritative [npm package metadata](https://registry.npmjs.org/@anthropic-ai%2Fclaude-code/2.1.295)
and [Node release table](https://nodejs.org/en/about/previous-releases) were
checked by the team lead. The release table marks Node 20 as EOL and Node 22/24
as LTS. The official
[Node image manifest](https://github.com/docker-library/official-images/blob/master/library/node)
and [Python image manifest](https://github.com/docker-library/official-images/blob/master/library/python)
list the proposed tags. These mutable upstream references should be refreshed
at implementation time; listing a tag is not evidence of a successful image
build.

## Approved Design

Use an official Node 24 LTS image stage together with an explicit Python 3.13
Trixie runtime base. Node 24 meets the current `>=22.0.0` requirement and has
more support runway than selecting the minimum Node 22 major. Both stages use
the same Debian distribution to reduce shared-library compatibility risk.

| Component | Approved pin | Purpose |
|-----------|--------------|---------|
| Node image stage | `node:24.21.0-trixie-slim` | Supported Node 24 LTS plus its bundled npm. |
| Python runtime | `python:3.13.16-slim-trixie` | Retain Python 3.13 and explicitly match the Debian distribution. |
| Claude npm package | `@anthropic-ai/claude-code@2.1.295` | Retain the deployed CLI version while correcting its host runtime. |

These exact tags were found in the official image manifests during this cycle.
Read-only registry inspection also resolved their multi-platform index digests:

- Node: `sha256:173f125896c3b47ddf056734c7ea789d04595a6a08769a8f78e0df642781fb66`.
- Python: `sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c`.

Use the tag-plus-digest references in the review artifact. Record the selected
platform manifest and resulting image digest during the later build. Registry
inspection confirms image identity and platform availability; it does not
establish that the proposed combined runtime builds or works.

The approved Dockerfile change does the following:

1. Copy only the Node executable and npm module directory from the official
   Node stage; create the npm and npx symlinks explicitly.
2. Retain `ca-certificates`, `curl`, and `tini`; install the Node runtime shared
   library dependencies `libstdc++6` and `libatomic1`; remove Debian's
   `nodejs`/`npm` packages. The official Node image includes `libatomic1` for
   ARM support, so copying the executable alone is insufficient.
3. Install the pinned Claude package with `npm --engine-strict` so a declared
   incompatible engine fails the build.
4. Assert the selected Node major, record `node --version` and `npm --version`,
   assert the installed Claude package version and engine metadata, and run
   `claude --version` within the image build.
5. Update the outdated Node requirement comment and add a narrow deployment
   runbook section for the pin and validation policy.

The existing `src/ai/claude.py` subprocess call and its prompt, timeout, retry,
model, and output contracts remain unchanged. Authentication continues to use
the existing runtime environment. This proposal does not use a native CLI
installer, install new production credentials, or add a direct API client.

Node 22 would satisfy today's minimum but provides less support runway. A
native Claude installer would change the existing installation mechanism and
is not needed for this bounded repair. The selected pins require intentional
future updates. They narrow upstream version drift; they do not make the
entire image reproducible because Debian and Python dependency resolution
still have their existing behavior.

## Acceptance and Verification

### Reviewed Dockerfile Change

The senior developer prepared this patch at
`/private/tmp/crypto-master-node24-compatibility-candidate/Dockerfile.patch`.
The equivalent zero-context diff is retained here so review does not depend
on a temporary file; use `git apply --unidiff-zero` when applying this form.
The developer reported `git apply --check` PASS during diagnosis. After the
operator approved local implementation and image validation with “진행시켜”,
the senior developer applied this exact candidate to the repository Dockerfile.
Static applicability and source application are not image-build validation.

```diff
diff --git a/Dockerfile b/Dockerfile
index 1680275..1dd1a36 100644
--- a/Dockerfile
+++ b/Dockerfile
@@ -12 +12,8 @@
-FROM python:3.13-slim
+# Keep Node and Python on the same Debian release. Pin these upstream
+# inputs; review future updates through the same compatibility build gate.
+FROM node:24.21.0-trixie-slim@sha256:173f125896c3b47ddf056734c7ea789d04595a6a08769a8f78e0df642781fb66 AS node-runtime
+FROM python:3.13.16-slim-trixie@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c
+
+# Copy only Node/npm so the Python image's /usr/local stays intact.
+COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
+COPY --from=node-runtime /usr/local/lib/node_modules/npm/ /usr/local/lib/node_modules/npm/
@@ -15,4 +22 @@ FROM python:3.13-slim
-# - nodejs / npm: required for `@anthropic-ai/claude-code` (the
-#   CLI the project shells out to via `claude -p`). Debian Bookworm's
-#   nodejs package is 18.x which satisfies Claude Code's Node 18+
-#   requirement.
+# - libstdc++6 / libatomic1: Node's shared libraries, including ARM support.
@@ -22,0 +27,3 @@ FROM python:3.13-slim
+# Claude CLI 2.1.295 requires Node >=22; Node 24 LTS meets that requirement.
+# Keep the deployed CLI version while changing its runtime. engine-strict
+# turns future engine incompatibilities into build failures.
@@ -27,2 +34,2 @@ RUN apt-get update \
-        nodejs \
-        npm \
+        libstdc++6 \
+        libatomic1 \
@@ -30 +37,14 @@ RUN apt-get update \
- && npm install -g @anthropic-ai/claude-code \
+ && ln -s node /usr/local/bin/nodejs \
+ && ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
+ && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
+ && node --version \
+ && npm --version \
+ && npx --version \
+ && npm install --global --engine-strict @anthropic-ai/claude-code@2.1.295 \
+ && node -e 'const assert = require("node:assert/strict"); \
+       const p = require("/usr/local/lib/node_modules/@anthropic-ai/claude-code/package.json"); \
+       assert.equal(process.versions.node.split(".")[0], "24"); \
+       assert.equal(p.version, "2.1.295"); \
+       assert.equal(p.engines.node, ">=22.0.0"); \
+       console.log(JSON.stringify({node: process.version, cli: p.version, requiredNode: p.engines.node}));' \
+ && claude --version \
```

### Required Implementation Evidence

The candidate is applied under explicit operator approval. Build and Test must
supply the following evidence before repository acceptance can pass:

| Check | Required result |
|-------|-----------------|
| Scope review | Only the approved Dockerfile/runbook changes; no runtime data, credentials, trading settings, Fly configuration, or application behavior change. |
| Target image build | A Linux image for the production machine's architecture builds successfully from the approved base references. Capture image/base digests and build provenance. |
| Node/package compatibility | Node is the selected 24.x version; pinned Claude is `2.1.295`; strict engine installation passes with no `EBADENGINE`. |
| Shared-library and executable smoke | Node/npm/npx/Claude version commands exit 0 in the resulting runtime stage; Node libraries resolve (ldd or explicitly qualified loader/process evidence); `claude --help` exposes the flags used by the existing client. |
| Python/runtime packaging smoke | Existing application modules and dependency entry points remain importable in the candidate image without credentials or runtime volume writes. |
| Startup contract review | Existing `tini` entrypoint, `start.sh`, ports, data path, process supervision, and paper/live controls retain their current semantics. |
| Artifact hygiene | No secret values or credential files in the build context, layers, logs, or committed evidence. |

The local Docker daemon was started for target `linux/amd64` validation.
The initial macOS credential-helper failure was resolved by an authorized
retry; the image build passed. Loader trace and the running Node process report
resolve all seven libraries, but `ldd` itself reports guest-emulation failure.
Repeated CLI help checks are unstable under both the old local emulator and
a bounded modern-emulator retry. The [cross-check](../../../../docs/cross-checks/2026-10-09-notifications-ops-claude-node-compatibility.md)
records overall runtime acceptance as PARTIAL; a native amd64 runner or
usable emulator must complete the help/flag gate.

An authenticated `claude -p` invocation is a separate functional smoke. Run it
only in an approved environment with the existing credential mechanism and a
bounded, non-trading prompt; do not print credentials. Record whether this
check was performed or deferred. A version smoke and mock-based Python tests
must never be reported as successful authenticated inference.

## Operations and Rollback

The operator subsequently authorized commit, push, and deployment with
“커밋 푸시 배포까지 해줘”. Native acceptance and rollout verification are now
in scope and remain pending. Before rollout, refresh the deployed image/release
and record the corresponding rollback target. The current release listing is
v51 at 09:58:31; its runtime snapshot is being validated. The earlier v50
evidence is historical and is not the current rollback baseline. Image details
are recorded in the session.

After deployment, verify the deployed image identity, Node/Claude versions,
health endpoint, and a completed engine cycle with the existing mode/settings.
Keep authenticated inference status separate from health and cycle evidence.
If image startup, library loading, CLI execution, or health fails, restore the
recorded previous image through the established Fly rollback procedure. Do
not delete or migrate the persistent volume as a rollback mechanism.

## Approval Boundary

The user-invoked [team skill](../../../../.claude/skills/team/SKILL.md) says to
halt and ask when work touches "live trading credentials, mainnet money,
deployment config, or API keys." The operator has satisfied the implementation
approval point with “진행시켜” in response to the specified local Dockerfile/runbook change and image
validation. Complete that authorized scope without another approval request.
The subsequent explicit instruction “커밋 푸시 배포까지 해줘” authorizes commit,
push, and deployment of this repair. Credential changes and trading-mode
changes remain outside scope. Approval does not replace native acceptance or
production verification; those results remain pending.

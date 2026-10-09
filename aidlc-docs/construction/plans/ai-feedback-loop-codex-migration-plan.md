# AI feedback loop — Codex CLI migration

**Status:** Complete — actual Fly cutover and native model qualification passed on 2026-10-09.

## Scope and stage decision

User request: replace this project's Claude usage with Codex, followed by
explicit continuation after discovering its actual runtime is Fly.io, not GHA.
Primary unit: `ai-feedback-loop`; related units: `strategy-framework`,
`notifications-ops`. FR-001/002/022/023/024/026/027/033/035, NFR-002/004/007,
CON-001, US-004. Existing strategy prompts, trade math, approvals, profiles and
paper/live safeguards remain unchanged. No model-generated code is executed by
the transport; existing candidate validation remains responsible for generated
strategy artifacts.

Functional, reliability and infrastructure decisions are recorded in
`../ai-feedback-loop/codex-migration-design.md`. This bounded provider change
updates NFR-002 to allow Codex CLI and preserves the prohibition on direct paid
LLM API fallback. The user's continuation authorizes implementation and actual
deployment after validation; no new live-trading authorization is inferred.

[Answer]: Preserve current trading settings; production is observed `paper`.
Use the same qualified Codex 0.153.4 / `gpt-6-astra` policy as the other projects.
Obtain a distinct automation login for this always-on Fly process; never copy
the GHA or personal interactive refresh stream.

## Plan

- [x] Inspect deployment and code; dedicated worktree preserves local changes.
- [x] Record functional/NFR/infrastructure decisions and related requirements.
- [x] Add bounded, tool-free Codex CLI transport and a provider factory while
  retaining the existing `LLMClient` port and legacy exception compatibility.
- [x] Wire prompt strategies and improver through the provider factory; preserve
  per-strategy timeout overrides and existing Claude rollback support.
- [x] Pin native Codex download/checksum in the image. Add explicit Fly provider
  configuration and persistent, protected dedicated auth with cross-process lock.
- [x] Test parsing compatibility, timeout/cancellation cleanup, environment and
  tool isolation, auth persistence/serialization and provider routing. Run full
  tests and repository format/lint/type checks.
- [x] Prepare an independent automation login, read-only server qualification,
  capture current release/mode/config, then deploy without changing trading mode.
- [x] Verify image/health/provider/effective settings and real text/JSON calls
  without placing orders or sending manual notifications.
- [x] Update requirements, current docs, session/cross-check, state and debt;
  commit/push and verify exact remote revision and deployment.

## Rollback

Keep Claude installed and its credential setup untouched. Restore the previous
release or explicitly select `LLM_PROVIDER=claude` while preserving mode,
credentials, profiles and runtime `/data`. There is no automatic provider or
paid-API fallback.

## Build / review evidence

- Existing Claude/parser/loader/improver tests: 148 passed.
- Native transport regressions initially 13 passed; full suite 2617 passed.
  An earlier full run reported one process-cleanup failure (2616 passed); the
  related 66-test suite and subsequent full run passed. Added a fixed exception
  class diagnostic for cleanup failures, without raw stderr/credential content.
- Whole-repository Black 231 files, Ruff and mypy 122 source files passed.
- Review found and fixed a cleanup-quarantine persistence corner case: if a
  quarantine marker cannot be written, retain the file lock until process exit
  so another caller cannot race an unreaped child. A focused regression covers
  this fail-closed path; all 14 Codex tests plus format/lint/type checks pass.
- At the pre-deployment checkpoint, Fly v51 remained on Claude in paper mode
  and the dedicated device login was pending. The completed operations below
  supersede that checkpoint.

## Historical prepared release (superseded by the deployed image below)

- Implementation pushed: `d9bf77a263558364c0ef168f2d9f1d88bf62523b`.
- Final full suite including the quarantine-write regression: **2618 passed**
  (54.08 s); final focused Codex tests **14 passed**.
- Image built and pushed, without deployment:
  `registry.fly.io/crypto-master:codex-d9bf77a-20261009`, manifest
  `sha256:9c718ee4b5f73529a713a8563694476e4d6a028c2f955f1fdc35e3e4db65bf9a`.
- The app remains v51, paper mode, previous image, with health passing.
  Dedicated ChatGPT authorization is still required before neutral model
  qualification and actual deployment; do not deploy with missing auth.
- Local root gained other concurrent uncommitted Dockerfile/state/debt/design
  work. The fast-forward correctly refused to overwrite it; root is preserved.
  This work is committed/pushed from the isolated worktree. Recheck current
  origin/main and Fly release before deploying to preserve concurrent changes.

## Completed operations — 2026-10-09 UTC

- Dedicated device login succeeded on Fly; no personal or GHA refresh cache was
  copied. Protected persistent auth is `/data/codex-auth` (0700, auth.json 0600).
- Integrated the concurrent Node compatibility repair before building source
  `35e14b41b2a7b7844355edcaf42b41f160db4d71`. Final image:
  `registry.fly.io/crypto-master:codex-35e14b4-20261009`, manifest
  `sha256:9adffd345d6a82d239d2c07b77a6112b4909a414bd12ca5fc0573f9383bcabfe`.
- Pre-deployment text/JSON qualification passed at 13:36:23 / 13:36:26.
  Concurrent rollouts replaced the first deployment; the exact qualified digest
  was restored in **v55**, created at 13:43:09. The later source-only strategy,
  reconciliation and funnel fixes through `3f4864f` are not in this image.
- The existing 1 GiB machine exhausted available memory (Fly metrics reached
  zero) and stopped responding. Increased the same machine to **2 GiB** at
  approximately 13:47:48, restoring HTTP/SSH. Retained shared CPU 1, machine
  `6835752b711958`, region `nrt`, volume `vol_4m3l58dkk29y19zv`, data and paper
  mode. `fly.toml` now retains this verified capacity; the allocation source
  remains unidentified, so this is a capacity mitigation, not a code fix.
- Native post-deployment checks against actual `/app` passed: Codex 0.153.4,
  Node 24.21.0, Claude 2.1.295, Claude help/print/model flags, protected auth,
  factory selection, `LLM_PROVIDER=codex`, `gpt-6-astra`, and `paper` mode.
  Real text and JSON calls succeeded at **13:49:56 / 13:50:00**, exit 0.
  Qualification invoked no trading cycle, order or manual notification.
- Subsequent HTTP health returned `ok`; the same v55 image and volume remained
  started with a passing check and approximately 1.46 GiB available memory an
  hour after recovery. A Binance testnet klines timeout in one account was
  handled separately; this closeout does not claim all upstream requests pass.
- The 2618-test migration suite and 14 focused Codex tests qualify the migration
  implementation; later unrelated source commits retain their own evidence.
  Current docs, debt/state, session/cross-check and capacity configuration are
  closed out together. No further image deployment is needed for these docs or
  the already-applied memory setting.

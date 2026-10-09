# AI feedback loop — Codex CLI migration

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
- [ ] Prepare an independent automation login, read-only server qualification,
  capture current release/mode/config, then deploy without changing trading mode.
- [ ] Verify image/health/provider/effective settings and real text/JSON calls
  without placing orders or sending manual notifications.
- [ ] Update requirements, current docs, session/cross-check, state and debt;
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
- Auth and actual deployment qualification are still pending. Existing Fly v51
  remains on Claude in paper mode; the independent device login is in progress.

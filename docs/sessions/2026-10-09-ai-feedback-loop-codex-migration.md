# Codex migration — 2026-10-09

Unit: `ai-feedback-loop`; related `strategy-framework`, `notifications-ops`.
FR-001/002/022/023/024/026/027/033/035, NFR-002/004/007, CON-001, US-004.

The actual runtime is Fly, with no GHA workflows. Added a native Codex adapter,
provider factory, shared existing response parser and pinned image installation.
Fly configuration selects `gpt-6-astra`; Claude remains an explicit rollback.
No exchange adapter, order path, risk math, strategy, profile or trading mode was
changed. Existing `LLMClient` injection and exception handling remain compatible.

The transport is adapted from Investo 056dd8a1 (declared MIT). It uses tool-free
metadata, strict configuration, stdin prompts, empty work/home directories, a
constructed credential-free child environment, bounded output and process-group
cleanup. Native auth persists separately on `/data/codex-auth`; file locking
serializes dashboard/trader/research calls. Cancellation waits for cleanup.
Cleanup uncertainty quarantines the auth stream, including failure to write the
marker. API key auth and automatic paid API/provider fallback are rejected.

Validation: 148 existing targeted tests; native process/serialization/parser/
provider regressions; full suite 2617 passed. An initial full run had one
cleanup test failure that did not recur in related 66 tests or the full rerun;
fixed exception-class diagnostics were added. Black 231 files, Ruff and mypy
122 files passed. Final quarantine-write regression is recorded in the plan.

Operations: v51 image `deployment-01M4G0FW4FQV2VMX175K77DTWD` was observed in
`paper` mode before changes. Web and SSH later stopped responding; restarting
the same machine/image restored health. Cause was not established. Dedicated
Codex login and deployment qualification remain pending. No token values or
personal/GHA auth cache were copied. No debt item was added; the open
operational steps are tracked by this construction plan.

Final validation and build: **2618 full tests passed**, **14 Codex boundary
tests passed**, format/lint/type checks passed. Source commit
`d9bf77a263558364c0ef168f2d9f1d88bf62523b` is pushed. Built image
`registry.fly.io/crypto-master:codex-d9bf77a-20261009` (manifest
`sha256:9c718ee4b5f73529a713a8563694476e4d6a028c2f955f1fdc35e3e4db65bf9a`)
is prepared; no server deployment yet. Other concurrent local uncommitted work
prevented a root fast-forward and was preserved.

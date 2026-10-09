# Codex migration — 2026-10-09

**Current outcome:** Complete. Fly v55 runs Codex `gpt-6-astra`; real native
text/JSON calls and health passed. The earlier checkpoints below are historical;
final production evidence is recorded at the end.

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

## Actual deployment and qualification

The dedicated Fly device login completed. Pre-deployment neutral text and JSON
calls passed at 13:36:23 and 13:36:26 UTC. The final image combines migration
`d9bf77a` with Node compatibility source `35e14b4`:

- Tag: `registry.fly.io/crypto-master:codex-35e14b4-20261009`.
- Manifest: `sha256:9adffd345d6a82d239d2c07b77a6112b4909a414bd12ca5fc0573f9383bcabfe`.
- Final release: **v55**, 2026-10-09 13:43:09 UTC. Concurrent releases v53/v54
  had replaced the initial v52 rollout; v55 restores the exact qualified image.
- Unchanged machine `6835752b711958`, `nrt`, shared CPU 1, persistent volume
  `vol_4m3l58dkk29y19zv`, paper mode and existing trading configuration.

The 1 GiB machine repeatedly lost HTTP/SSH responsiveness, including before the
Codex deployment. Fly telemetry recorded zero available memory. Increasing the
same VM to 2 GiB around 13:47:48 UTC restored service; this setting is retained
in `fly.toml`. After approximately one hour the same image remained healthy,
with about 1.46 GiB available memory. The original allocation path was not
identified. This is a documented capacity mitigation and increases provisioned
Fly memory; it is not evidence of a repaired memory leak.

Post-deployment verification used the actual `/app` factory and source, not the
pre-deployment source archive. It confirmed Codex CLI 0.153.4, Node 24.21.0,
Claude 2.1.295 and credential-free `claude --help` with print/model flags.
`LLM_PROVIDER=codex`, `gpt-6-astra`, `paper`, auth-home permissions and valid
native auth all passed. Real text/JSON calls succeeded at **13:49:56 and
13:50:00 UTC**, exit 0. Qualification called no trading engine, orders or
manual notifications. Existing paper startup resumed normally; one Binance
testnet klines timeout was contained per account and is not a Codex error.
Public `/_stcore/health` subsequently returned `ok`.

The native help result closes DEBT-082's emulation-only acceptance gap; no
authenticated Claude inference is claimed. Source changes after `35e14b4`
through `3f4864f` concern separate strategy/reconciliation/funnel work and are
not deployed by this migration. Their docs and the dirty original checkout are
preserved. The final closeout changes docs and retained VM capacity only;
2618 full migration tests, 14 Codex boundary tests, Black/Ruff/mypy and image
checks remain the relevant implementation evidence.

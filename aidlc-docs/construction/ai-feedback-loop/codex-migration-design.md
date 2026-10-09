# Codex migration design

## Functional contract

The unchanged `LLMClient` port exposes `analyze(prompt) -> dict` and
`complete(prompt) -> str`. A provider factory chooses the explicitly configured
adapter. Local legacy callers default to Claude for compatibility; the Fly
deployment explicitly selects Codex. Existing injected fake/client objects and
the `claude_timeout_seconds` strategy metadata keep working. Codex responses use
the same JSON extraction, trade-key normalization and downstream strategy
validation as Claude. Legacy exception types remain catch-compatible so
timeouts continue to skip an individual strategy and surface `LLM_TIMEOUT`.

No new trading entity, order endpoint, strategy, risk limit, capital allocation,
promotion rule or UI control is introduced. The only new configuration is
provider/model/auth-directory selection for the existing AI transport.

## Reliability and security contract

Reuse the qualified Investo native-process, auth-file and tool-free policy
implementation as a small attributed local module (source revision
`056dd8a1b4a8e599f44519e54b5bf4f486275dbd`). Its dependency-free transport avoids
coupling the trading app to Investo's application package. Native CLI is pinned
to 0.153.4 and its published Linux archive checksum. Requests go over stdin;
the subprocess gets a constructed environment with no exchange, email, Fly,
GitHub or API credentials. Each invocation uses empty temporary work/home
directories, strict configuration, an explicit tool-free model catalog and
bounded output. Unexpected action/error events or secret-bearing outputs fail
closed. No shell/patch/browser/MCP tools are offered to the model.

Async cancellation must stop/reap the native process group before releasing
the auth lock. Preserve the refreshed auth file on disk on success, timeout,
failure and cancellation. A file lock serializes all processes using this
dedicated auth directory, including dashboard and research workers; admission
wait is bounded. Avoid retrying invalid auth, malformed output or arbitrary
nonzero exits. Retain existing timeout retry/backoff semantics where safe.

## Infrastructure and operation

Reuse app `crypto-master`, one Fly machine, existing image/start process,
networking, health check and `/data` volume. No additional server, database,
queue, public endpoint or paid API service. Store an independent ChatGPT login
under `/data/codex-auth` (directory 0700, auth.json 0600, same service user),
outside the application source and temporary per-call work. Obtain it using
official device/browser login and never fork the GHA/personal auth cache.
Tokens refresh in place; no long-lived auth JSON in image or immutable Fly
environment settings. Native runtime diagnostics log provider/model/status,
not credential bytes or raw stderr.

On 2026-10-09 the live app reported `TRADING_MODE=paper` and Claude `sonnet`;
the hashes of `src/ai/claude.py`, `src/config.py`, and `src/strategy/loader.py`
matched the reviewed local baseline. Capture current release/effective settings
again immediately before deployment, since other operational work can advance
them. Confirm real model access with a neutral text/JSON prompt; do not start a
trading cycle or create orders for acceptance testing.

Reference: https://learn.chatgpt.com/docs/auth (headless login and auth caching).

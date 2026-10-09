# Codex runtime operations

Fly's `crypto-master` app selects `LLM_PROVIDER=codex`, native CLI **0.153.4**
and **gpt-6-astra**. The image pins the release archive checksum; every call
also checks the native version. Prompt strategies and `StrategyImprover` use
the same provider factory. Existing timeout/retry names and per-strategy
`claude_timeout_seconds` remain compatible. Local configurations retain the
legacy Claude default until explicitly changed.

The shared Fly machine uses 2 GiB RAM. The preceding 1 GiB runtime exhausted
available memory and stopped responding to HTTP and SSH during rollout; the
capacity change retains the same CPU, machine, image, volume and trading mode.
Reduce it only after measuring startup and dashboard/model-call peaks. This is
a capacity mitigation; it does not identify the original allocating code path.

## Dedicated login

Create `/data/codex-auth` owned by the service user with mode 0700. Obtain a
new ChatGPT login for this runtime; never copy the personal Codex or GHA auth
cache. From a Fly SSH shell, run:

```sh
CODEX_HOME=/data/codex-auth codex -c 'cli_auth_credentials_store="file"' login --device-auth
chmod 600 /data/codex-auth/auth.json
```

Complete the displayed device authorization in your own browser. If device
login is disabled, enable it in ChatGPT security settings. Do not put auth JSON
in source, images, logs, clipboard messages or immutable Fly environment secrets.
The native CLI refreshes this file in place; `/data` survives machine updates.
The directory and file permissions are checked before every request.

The `.runtime.lock` file serializes all app processes before reading auth and
holds the lock through child cleanup. Do not run a separate raw Codex command
against the same auth directory while an app call is active. For manual login
renewal, pause AI callers first and hold this lock. Invalid/revoked refresh
credentials need a fresh device login; ordinary token expiry is handled by the
native CLI. No custom OAuth refresh or paid API fallback is implemented.

## Failure and rollback

Cancellation and timeout stop/reap the process group before unlocking; existing
strategy timeout handling is preserved. Native stderr and credential strings
are never included in adapter exceptions. Refreshed auth remains on the volume
even if parsing or execution fails. Output with unexpected tool events or an
auth secret is rejected. Generated strategies still pass the existing validation
and operator approval rules; transport migration grants no new trading authority.

If cleanup cannot establish quiescence, `.runtime-quarantined` blocks subsequent
calls. Stop/restart the affected runtime and verify no old Codex children remain
before removing that marker while holding `.runtime.lock`. Never delete the auth
file as generic error recovery. If the marker cannot be written, the process
retains its lock until restart; subsequent callers time out instead of racing.

For rollback, deploy the previous verified image/config or explicitly restore
`LLM_PROVIDER=claude`. Claude and its credentials remain available. Preserve
`TRADING_MODE`, exchange credentials, profiles and `/data` throughout. Provider
selection never falls back automatically on a Codex failure.

Reference: [OpenAI authentication documentation](https://learn.chatgpt.com/docs/auth).

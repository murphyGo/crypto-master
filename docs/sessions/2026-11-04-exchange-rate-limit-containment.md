# Exchange request-limit containment — 2026-10-30 to 2026-11-11

Unit `exchange-integration`, secondary `proposal-runtime`, `trading-core`,
`notifications-ops`. DEBT-090; FR-016–020/046, NFR-006/009/011, CON-002;
US-008/014/025; legacy 2/10.1/13.3. The user's “진행시켜” continues the bounded
repair and existing same-capacity delivery workflow. Work resumed on November 4
after the read-only Fly command approval. A server restart interrupted staging;
November6 recovery verified the seven tested source/test hashes unchanged and
confirmed no commit or deployment had occurred. Runtime is reverified before delivery.

## Behavior

CCXT's DDoSProtection/NetworkError hierarchy bypassed the core adapter's
ExchangeError catch ladder, allowing an OHLCV scan failure to skip the current
account's monitor. Every core request now normalizes transport failures into
ExchangeAPIError. Existing invalid-order, insufficient-funds, not-found and
missing-timestamp behavior remains. No strategy, engine or trader source changed.

Rate-limit/DDoS failures establish a shared monotonic cooldown by venue, endpoint
market family and testnet. Binance derivatives share the futures scope even when
called through a spot-configured adapter; Bybit uses its unified scope. All core
requests, both order types, cancellation, connect/load_markets and every funding/OI
history page are guarded. Adapters never sleep or resubmit a failed request.
An order timeout remains an error with uncertain remote outcome.

New response Retry-After seconds/HTTP dates and Binance's millisecond ban deadline
are honored; the longest positive finite hint wins. Missing/invalid hints use
60 seconds for rate-limit errors or120 seconds for DDoSProtection. Old response
headers are not reused. A later failure cannot shorten an existing deadline.
Reconnecting or replacing adapters cannot erase an active process-local ban.
At most64 active scopes are retained, with expired entries pruned and unknown
scopes refused when full. There is no timer, new dependency or network probe.

The existing core RATE_LIMIT and derivative rate_limited error codes are retained.
Optional retry_after_seconds metadata lets the existing derivatives service honor
the wait within its refresh deadline. New rate-limit/transport messages are
sanitized; metadata stores no credentials, raw URL or response body. Existing
non-network CCXT error messages and exception causes remain diagnostic context.

## Validation and review

- Initial regression:49 cases fail on the original source (eight core request
  paths, two venues, three transport subclasses plus shared-ban suppression).
- 73 fault tests now pass: hint parsing, exact expiry, wall-clock jumps, stale
  headers, sibling/replacement instances, reconnect, scope isolation, both order
  types, cancellation, concurrent failures, capacity, guarded pagination and the
  derivative service's bounded cancellation.
- 688 targeted exchange/runtime/derivatives/live/paper tests pass. A real Binance
  adapter with injected418 runs through a two-account engine cycle: four scan
  errors are contained, both monitor passes occur, no cycle-level error occurs,
  only one physical CCXT call occurs and no unpriced open/close order is attempted.
- Full regression: **3,127 passed**, five existing JUnit warnings,54.08s.
  Changed-file Black/Ruff and mypy across136 source files pass. Local CCXT4.5.51;
  production4.5.85 is preserved and gets a separate network-free smoke check.
- Test-development failures are retained. The first derivative-service test
  incorrectly injected only current-data calls although history is fetched first;
  the next assertion incorrectly expected no context instead of an explicit empty
  unavailable context. Corrected assertions verify empty funding/OI with
  deadline_exceeded, preserving the established context contract. An early targeted
  command also named a nonexistent test file; the corrected688-test run passes.
  A full sandbox run failed the existing Codex child-process cleanup test with
  PermissionError; the approved unsandboxed full rerun passes. Both failed full
  runs and the successful final run are retained; no test was skipped.

Implementing-agent review used `.agents/skills/code-review/SKILL.md`; this is not an
independent review. Reviewed exception hierarchy, live submit/no-retry behavior,
scan/monitor flow, per-page guards, reconnect persistence, finite metadata, bounded
state and untouched quote validation. No remaining blocking finding was identified.

## Delivery and limits

Preflight November4 verifies v70/sourceffe95b0,182 hashes, existing instance,
dependencies, paper/Codex mode, one shared CPU/2048MiB machine and existing volume.
Delivery uses an overlay on exact v70 image
`sha256:0527f83ff75272eb17f0c3b6e74ca40718d4787f27ecdc1d7a0c5fc602a8d1a7`,
copying only `base.py`, `ccxt_base.py`, `binance.py`, `request_backoff.py` under
`src/exchange/`.

Source **0e14f9d969bfaab2d400fb86c34a70ebef432146** is pushed to main and
now deployed as **Fly v71**, instance `01M73XWEEJT9000B4M3QC02MY7`, image
`sha256:32d706b6e7ea5ef9ba725749d429eca79a47cb8e5667837ce7c12c1016f27552`.
All183 hashes and unchanged env/init/guest/volume/services/restart/dependencies
match; health and postdeployment process continuity pass. CCXT4.5.85's isolated
mock-only smoke passes all five checks with zero exchange network calls.

The natural first cycle `9ce21abd-c3d1-458e-af4f-bf444ed70ea0` runs
2026-11-10T23:50:06.418372Z–23:50:20.979948Z (November11 KST),14.561576s.
It records12 monitor passes across12 distinct accounts and no error events,
proposals or orders. DEBT-090 is resolved for this bounded containment scope.

Approval/restart interruptions did not repeat mutations: registration completed
November8, source commit/push November10, deployment November11 KST. Preflight
November10/11 initially fails only old instance identity after a same-image v70
restart; source/settings remain identical. A fresh baseline check passes before
v71 deployment. The failed continuity checks are retained; no cause is inferred.
The console capture truncates part of a layer-upload chunk, while independent
image/source/configuration verification remains complete.

The cooldown is reactive and process-local. It does not cancel already in-flight
CCXT calls, persist through process restart, attribute the original IP ban, or
budget unrelated processes sharing the IP. A monitor attempt still cannot close
a position without available valid pricing. The all-source dashboard checkpoint
compatibility digest changes, so old checkpoints cannot be assumed warm after this
exchange-only source change. No production fault is deliberately
triggered. Mocked fault evidence and ordinary production-cycle evidence are separate.
DEBT-083 remains Critical: this repair does not establish dashboard cold/native/
depleted/original1GiB acceptance or resolve initial-read latency/cost questions.

Artifacts: `aidlc-docs/construction/exchange-integration/code/rate-limit-containment-20261030/`.

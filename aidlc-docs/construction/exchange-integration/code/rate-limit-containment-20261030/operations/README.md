# v71 delivery evidence — 2026-11-11 KST

`operation-summary.json` is the acceptance index; `manifest.json` hashes the
retained evidence. Source0e14f9d, image32d706b6, one existing shared CPU1/2048MiB
machine. No data migration, credential, dependency or trading-mode change.

Before snapshots retain November4/6/10/11 observations. The November10/11 initial
checks fail only historical instance identity: v70 had restarted since November6.
All182 source hashes, exact image and configuration still match. The fresh
`before-final` check uses that verified current instance and passes. These are
preflight continuity gaps, not failed deployments or source drift.

`postdeploy` and both `after-*` snapshots verify183 hashes, source label, exact
image, dependencies (including CCXT4.5.85), settings, health and process continuity.
The normal startup cycle completes in14.561576s, with12 distinct monitor accounts
and no error events. It generates no proposal or order. No production ban occurs
in this cycle, so it is not a live fault-branch acceptance claim.

`runtime-fault-smoke.json` records an isolated deployed Python process using only
AsyncMock exchange clients: DDoS normalization, ban deadline, sibling/derivative
suppression and order-timeout/no-retry pass. No exchange network call is made.
`verify_runtime_faults.py` contains the exact smoke code. The actual invocation
used direct `fly ssh` with this same embedded code; it did not run a new engine.

`Dockerfile` copies only the four changed exchange files from source0e14f9d over
the exact v70 image. `fly.toml` is the unchanged deployment configuration.
`deploy-console.txt` retains the tool-captured build/deploy output; one middle
layer-upload chunk was truncated by the tool output budget. Image digest, COPY
steps, deployment success, and independent postflight hashes are retained.

`capture_runtime.py` runs from the repository root and writes to the task's `.tmp`
directory. Its historical input snapshots and expected-runtime.json are retained
here. It reads bounded activity tails and hashes allowlisted source files; it does
not query exchanges or change runtime data. Local tests and failed attempts are
retained separately under `../validation/`.

# V67 operational evidence — FAIL_SAMPLE

The proposal-refresh CPU correction is deployed and its source/runtime integrity
is verified. The combined four-session readiness observation **fails**. This
directory closes the bounded correction/measurement record, not DEBT-083.

Runtime source is `120b4408dc0d3eedb241edf26f8f161c062cf126`, Fly release v67,
image `sha256:2aa60d27cf4aed283b9e4596e17cf3403f39b88794b3347f5abeb40462700382`,
machine `6835752b711958`, instance `01M5WNEGCGSRY9CE34VRT7K6X3`.
`postdeploy.json`, `postrun.json`, and `postrun-comparison.json` verify 182 runtime
hashes, unchanged dependencies/settings/volume/shared CPU/2048 MiB, stable
engine/dashboard PIDs and successful internal/public health. The immutable v66
image received only `projections.py`; the overlay Dockerfile is retained.
`rollout-output.txt` contains retained tool output; one intermediate image-layer
listing was truncated by the tool. Image/source verification does not depend on
that listing. The GitHub run query returned no runs and is not a CI pass.

One observer ran from 2026-10-26 17:54:18.225469 to 18:23:52.497955 UTC
(1,774.272486 s), with four real Streamlit WebSocket sessions. There was no
synthetic engine cycle, duplicate observation or capacity/cadence change.

| Check | Result |
|---|---|
| Requests | 356 starts and outcomes; 348 complete, eight terminal incomplete |
| Home / Trading | Each 174/178 complete; complete-only p95 0.576250 / 0.487714 s |
| Failure kinds | Four activity stale, then four snapshots unavailable; not timeouts/guard aborts |
| Health | 352/352 pass, max 0.661728 s |
| Natural cycle | 18:22:37.998358–18:23:12.286517 UTC, 34.288159 s, twelve monitors, zero errors |
| Guest / dashboard growth | Peak 663.171875 MiB / growth 31.578125 MiB on current 2048 MiB |
| Initial Home | Complete 12.956247 s / first incomplete receipt 5.507020 s; both miss five seconds |
| CPU history | 118 in-window samples per series, 15 s gaps; throttle counter/deltas zero; balance 932.008–4031.005 centiseconds |

Successful requests do not erase failures. Initial warmup is separate from the
main sample and does not qualify twenty cold samples. CPU history was published
37.055 s after observation and is restricted to the original interval; no
sampled depletion was observed and depleted-load qualification remains open.
Protocol receipt does not certify native rendering. Original 1024 MiB, cold,
native and depleted conditions remain independent, as do all prior failures.

`qa-ops-v67/` is an immutable copy of the independent audit package. Verify its
42-file `audit-package-manifest.json`; duplicate historical self-check payloads
are excluded, while adapter provenance and self-check results are retained.
The initial summary predates CPU collection: its CPU-pending flag is followed
by `cpu-window-proof.json` and `cpu-counter-interpretation.json`, without
changing FAIL_SAMPLE. `final-audit-outcome.json` gives the combined conclusion.
The lead replayed the audit and CPU proofs in a separate directory, retaining
identical conclusions in `root-replay/`; original captures were not overwritten.
The collector was stopped after observer exit; its explicit stop metadata and
capture helpers are retained. A stopped log-client exit is not an app failure.

`residual-analysis/` traces three emitted source-generation failures and their
error-cache echoes. Activity stays stale; snapshot cache ages around 24 s then
35 s explain the transition to unavailable. Current `source_changed` responses
finish without an automatic page watcher; later requests may retry after the
existing error TTL. The data producer and exact verification branch cannot be
identified from rate-limited asynchronous diagnostics without request IDs.
The next candidate is finite, coalesced recovery from a changed generation,
with fresh discovery/full verification, original cache ages, bounded attempts,
and unchanged worker/admission/freshness limits. This is a proposal, not shipped
behavior or proof that retries will meet latency targets under arbitrary churn.

No rollback was indicated by persistent runtime regression: health/processes,
canonical source proof and output correctness remain intact. The local paired
CPU improvement is supported; production percentage improvement and overall
readiness are not claimed. Deployment verification is complete while DEBT-083
remains Critical/active.

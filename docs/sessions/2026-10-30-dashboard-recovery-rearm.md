# Request-driven recovery after source-change exhaustion — 2026-10-30 KST

Unit `dashboard-operator-ui`; DEBT-083 remains Critical. FR-028–032/036/038/042,
NFR-003/007/008/011/012, BDL-NFR-02/03/04/06/07/08; US-012/014/020/023.
The user's continued-work request authorizes the recovery-policy refinement and
the existing same-configuration delivery workflow. Trading/live controls,
canonical data, dependencies, resources and CPU-cost deferral are unchanged.

## Source behavior and evidence

V68 permanently retained exhausted `source_changed` errors across normal
requests, even after writes stopped. The new immutable error token records an
eligibility time: `max(original admission + 30 s, failure + 2 s)`. A later
ordinary request can then start one new shared job. Each episode still has at
most three attempts, one original cooperative window, the same Future/progress
event, fair scheduling and full canonical-generation verification. There is no
timer or idle-page retry loop. Explicit retry can bypass the cooldown only for
its captured token; an old callback cannot erase a newer failure/job.

At most64 failure tokens plus active reservations remain. Unexpired source-error
tokens are protected from eviction; expired ones release capacity. Other errors
keep their existing2s TTL without in-job retries. Freshness/staleness ages never
renew on failure. This is an episode bound, not a sliding3-attempt/30s guarantee.

Three regression cases fail before the source change and pass afterward:
long writes followed by stability, a failure after the30s window retaining the2s
cooldown, and read-only progress plus four-client coalescing after eligibility.
Tests also cover exact boundary timing, old callback identity, bounded metadata,
manual retry, cache age, real file replacement/append and checkpoint behavior.

The protocol observer now retains a timed-out request as failed and closes its
socket before opening the next request's replacement. Reconnect time is included
in the next elapsed time, and replacement never overlaps the previous connection.
A regression test with a queued old response fails before this change. This
addresses the observed timeout contamination; it does not implement a general
server script-run-ID join or native browser acceptance.

## Checks

- Locked local Python3.13.18 environment, Streamlit1.57.0. Deployed1.65.0 remains
  unchanged. Frozen `uv sync --extra dev`; no lock/dependency edits.
- Initial targeted run:82pass/1fail. One tiny activity read exceeded its4s
  foreground wait on this first run; its XML is retained. Unchanged rerun83/83
  passes. This is not evidence that cold latency meets the production target.
- Recovery/observer targeted checks after final edits:80passed.
- Full regression: **3,053 passed**, five existing JUnit `record_property`
  compatibility warnings,86.20s. No failures/skips.
- Black on the four changed Python files, Ruff on those files, mypy across
 135 source files and `git diff --check` pass.

## Initial-load diagnosis

A separate read-only process on current v69 performed sequential initial
projections and then verified previous-result reuse at one fixed evaluation time.
No checkpoint or canonical data was written. It emits metadata/payload hashes,
not source rows. Python imports and OS caches are warm; this is neither process
cold nor browser timing and is a single trial per kind.

| Query | Initial wall seconds | Verified reuse seconds | Selected input |
|---|---:|---:|---|
| Activity |2.215596|0.007742|7files,97,438,217bytes,233,495events|
| Ledger |0.110500|0.002339|13files,1,110,717bytes|
| Snapshots |3.553279|0.011749|13files,34,432,056bytes|
| Candidates |0.012475|0.000338|1file,856bytes|
| Proposals |1.105970|0.115597|13,271files,16,469,074bytes|

All five initial/reuse payload hashes match and every source coverage is verified.
The sequential initial work totals about7s before rendering/network overhead,
already beyond Home's5s target. A separate instrumented activity trial attributes
most time to event reduction, with state-budget accounting and JSON validation
also material. Profiling overhead is not mixed into the unprofiled table.
No speculative parsing/proof shortcut is included. Snapshot initial reduction
and persisted verified summaries are follow-up candidates requiring parity and
source-generation evidence; DEBT-083 retains this performance gap.

Source review also confirms that `checkpoint_store.compatibility_digest()` hashes
all allowlisted `src/**/*.py` files, not only the projection reducer. This service
change therefore changes enabled-store query prefixes even though reducer output
is unchanged. That explains why existing compatible-cache timings cannot be
assumed for a new deployment. No per-query production checkpoint hit/miss trace
was captured, and the compatibility proof is not narrowed in this patch.

## Delivery

Source commit **`ffe95b0fb9ad06b1c1d0bd1df8edfd7a0c5344c2`** was pushed to main
and deployed as **Fly v70**, instance `01M64CFDQZJ5BPQ64306JXJWGC`, image
`sha256:0527f83ff75272eb17f0c3b6e74ca40718d4787f27ecdc1d7a0c5fc602a8d1a7`.
The minimal build context contains the unchanged Fly config, Dockerfile and only
the three runtime files changed from the exact v67 base: `data_service.py`,
`read_diagnostics.py` and the protocol observer. All182 deployed hashes match
this source; dependencies/env/guest/volume/services/restart match the previous
runtime. Internal health passes. Bounded observation is in progress.
All historical failed samples, native/cold/depleted/original1GiB requirements and
the shared CPU1/2048MiB configuration remain in force.

### Interrupted first operational sample

The first four-session run is retained as **FAIL_SAMPLE**, not counted as a pass:
17:53:54.694020–18:22:08.841929 UTC,1694.147909s,280/280 recorded requests
complete (140 each). Successful response p95 is Home0.587601s/Trading0.661508s.
Health is276/277 successful; the final request times out in5.761648s and trips
the existing guard. Memory samples end at18:17:14.100886,294.741043s before the
reported window end. Health capture has a278.306402s gap. No full engine cycle
appears in the collected memory stream. The later runtime tail confirms the
engine's18:19:51–18:20:07 cycle completed inside this missing-telemetry interval;
that does not repair the interrupted four-session qualification.

Local macOS power events show maintenance sleep at03:17:11 KST and wake at
03:21:46, followed by software sleep at03:21:50. These overlap the capture gap
and final failed probe. The sample is invalid for continuity; the timeout alone
does not establish a production health regression. Only finite power event
timestamps/types are retained, excluding unrelated application power logs.

The first postflight SSH lookup failed with an organization-authorization error.
A subsequent read-only retry succeeded: same v70 image/instance,182 source
hashes, config and engine/dashboard process identities. Public health separately
returned200/ok in0.181076s. The runtime tail includes the24.518127s startup cycle
and later completed cycles with no cycle-error events in the retained tail.

A **separate** repeated sample uses the same application source, limits, cadence
and workload, with task-bound `caffeinate -i -s -t2500 -w <runner-pid>` to prevent
automatic host sleep during observation. Its assertions were observed active.
The guard ends with the runner or after2500s; no persistent power setting or
production setting is changed. The first failed sample and all earlier failures
remain intact.

### Repeated sample and final disposition

The repeated sample is also **FAIL_SAMPLE**, for an engine error rather than
dashboard completion, health, collection continuity or resource bounds:

| Evidence | Result |
|---|---|
| UTC window |2026-10-29 19:39:38.902377–19:51:46.230325;727.327948s|
| Four-session requests |144starts/144outcomes, all complete;72each Home/Trading; no timeout reconnect|
| Complete-response p95 |Home0.605821s; Trading0.736413s; maxima5.870470s/5.514636s retained|
| Health |145/145 successful, maximum0.163994s|
| Memory |Guest peak662.925781MiB on2048MiB; dashboard RSS growth9.582031MiB|
| CPU |49in-window points,15s grid plus both brackets; burst balance280.322011–295.242035 CPU-seconds; no sampled throttle increase|
| Collection |Maximum health-start gap5.166193s, source-memory gap1.011515s, final memory trailing gap0.566558s|
| Engine cycle |`715a0736-f0bf-4d0f-b9b9-bcc39d790be2`,15.637191s, **one cycle error and11monitor passes**, then cycle_completed|

CPU balance/throttle are centiseconds in the retained raw metrics, converted
above using [Fly's metric units](https://docs.fly.io/monitoring/metrics).
The offline audit also rejects collection gaps beyond10s for health starts,
3s for source memory samples or5s at the end; these detect local suspension and
do not relax any application acceptance gate. These checks pass only for the
repeated sample. The earlier sample stays failed.

The engine event is `DDoSProtection`, Binance USD-M HTTP418/code-1003, reporting
an IP ban until2026-10-29 20:13:53.459UTC. Binance documents418 as an IP-ban
response following rate-limit violations; the observed request producer/weight
history is not available, so the cause of that ban is not attributed to this
application or a particular caller. See [Binance USD-M general information](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/general-info).
No exchange probe, ban bypass, forced engine cycle or trading-policy change was
performed. The observed Home/Trading paths read local state and have no exchange
API calls; deployed engine/exchange source hashes are unchanged from the base.

Local network-free fault injection confirms that `get_ohlcv` leaks the CCXT
`DDoSProtection` exception instead of wrapping it as `ExchangeAPIError`.
Its class hierarchy is `NetworkError → OperationFailed → BaseError`, outside the
adapter's `RateLimitExceeded`/`ExchangeError` catches. The runtime scan catches
domain exchange errors, while its broader account handler skips the failed
account's remaining work. This is a concrete containment gap consistent with
the observed raw exception and missing monitor pass; no exact live stack trace
or request-volume causal join is claimed. Registered as **DEBT-090 High** under
`exchange-integration`, with a bounded follow-up plan.

The retained diagnostics contain no `source_changed`/retry-exhaustion events in
this repeated window. Thus the run demonstrates current page availability,
not a live exercise of the new exhaustion/rearming branch; the regression tests
cover that branch. General server run-ID joining, native viewport/table-cell
parity and all original cold/depleted/1GiB gates remain open.

Later read-only checks on2026-10-30UTC are separate from both formal windows:
all182 hashes, v70 image/instance/config and engine/dashboard PID/start ticks
still match. The latest six captured cycles each have12monitor passes and no
cycle error. At05:29:11–05:29:31UTC, seven activity files/97,783,681bytes have
identical full content hashes and verified generations. Three fresh connections
complete Home7.382082s, Home0.585644s and Trading1.933210s. No manual retry or
cache clearing was used. Public health is200/ok in0.131398s. Both observers and
collectors ended; no task sampler remains, and the temporary sleep guard ended.

**Keep v70 deployed.** There is no observed persistent dashboard regression or
source/config/process drift requiring rollback. Restoring the unchanged exchange
code in v69 would not fix the reproduced adapter exception gap. This decision
does not convert either failed sample to a pass. DEBT-083 remains Critical;
DEBT-090 remains High. Next work is exchange exception/backoff containment and
initial-read cost, followed by the still-open acceptance gates.

Evidence: `aidlc-docs/construction/dashboard-operator-ui/code/recovery-rearm-20261030/`.
Plan: `aidlc-docs/construction/plans/dashboard-recovery-rearm-plan.md`.

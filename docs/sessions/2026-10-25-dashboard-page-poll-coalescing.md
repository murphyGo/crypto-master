# Session: One Loading Watcher per Dashboard Page

- **Unit / debt:** `dashboard-operator-ui` / DEBT-083 Critical/active.
- **Requirements / stories:** FR-032/036/042; NFR-003/011/012; BDL-NFR-03/04/06/08; US-012/014/020/023.
- **Authorization:** Remaining same-capacity software work/rollout continues. Shared CPU 1 / 2048 MiB, original volume/dependencies/paper/Codex and deferred performance-CPU/cost gate remain.
- **Baseline:** v61 / `7f185bc`, source/docs main `8ebcd1e`. Five-second and twenty-second four-session tests both fail public health deadlines; the latter includes a full engine cycle. Failures remain in [prior evidence](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/cold-readiness-20261025/README.md).

## Source change and verification

`availability.watch_loading` collects pending work during one page render and
registers one existing half-second background watcher at its end. Home, bounded
Trading and standalone Funnel use it. Their separate loading/stale/error messages
remain. Nested sections share the render's watcher; a ContextVar isolates
concurrent sessions and a finally block clears state on normal completion,
exceptions and Streamlit-style rerun/stop interruptions. No private Streamlit
context, persistent session flags, source/cache changes or runtime writes are added.
Standalone availability calls keep their original behavior.

Home five, Trading four and Funnel two pending sections each register **one**
watcher in integration tests. Mixed terminal/complete/stale state, nested calls,
concurrent renders and cleanup pass. 92 focused tests and **2823 full tests in
216.01s** pass. Changed-file Black/Ruff and source mypy across 129 files pass.
Code review found no unresolved correctness issue; actual shared-capacity
qualification remains necessary. The reader/service/source hashes exactly match
v61, so its twenty-pair semantic/query evidence remains tied to those unchanged
reader files. New page latency is not inferred from those query timings.

## CPU telemetry correction

The prior HTTP401 was resolved by correcting the scheme for the raw CLI JSON
token; no permission expansion, token creation, secret printing or storage occurs.
[Recovered raw metrics](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/cold-readiness-20261025/v61-cpu-metrics-retry.json)
show baseline 0.0625 CPU, five-second burst balance near zero at 19:52:45Z and
throttling rising from 0 to 2616.843 centiseconds over 19:52:30–19:53:00Z.
The twenty-second run's end window also shows burst depletion and additional
throttling (2616.843→4881.993 centiseconds by 20:18:45Z). Scrape timing is coarse;
this is evidence of a capacity bottleneck around failure, not an isolated causal
A/B test or proof that redundant polling is the only cause. [Official metric
units](https://docs.fly.io/monitoring/metrics#instance-load-and-cpu) distinguish host
quota counters from the unlimited guest-internal cgroup.

The deferred CPU upgrade is not activated. A separate Functional Design candidate
for durable file checkpoints remains awaiting approval and is not implemented.

## Rollout and final observation

Pending exact-source rollout and separate protocol/concurrency evidence. Original
cold, native, four-session and declared guest targets are retained. All failed
or aborted observations must remain; no completion claim is made at this checkpoint.

## Deployment / initial observation

Source `d86f76fda1b91bc337b06db2050722379c3f8701` is pushed and deployed on Fly
**v62**, image `sha256:648811287f22e13d85fe9b4f0f2743e23bdb905e56c0885a0251bf5911dbc868`.
All **175 runtime hashes** match. Machine/volume, shared CPU 1 / 2048 MiB,
Python/Streamlit/Pydantic/Pandas/NumPy versions and paper/Codex/Claude controls
remain. First complete post-deployment cycle runs
2026-10-25T03:47:14.646139Z–03:47:52.451427Z; later completed cycles are verified.
The root main checkout fast-forwards to `d86f76f`; unrelated settings/lock hashes
still match the original preservation snapshot.

The first observed app navigation after restart completes Home **12.180s** and
Trading **1.149s**, with full metrics/tables/chart coverage, no exception or
incomplete alert at completion. Actual Home background watchers peak at **one**;
Trading has none in that pair. This single pair includes app-script import work
but excludes earlier HTTP-server startup and is not twenty process-cold samples.
The 5s Home readiness target remains unmet.

Four twenty-second server sessions started at the recorded protocol timestamp
and are observing an existing full engine cycle. Initial host telemetry shows
about **459 CPU-seconds of burst credit and zero throttle**, unlike the depleted
v61 failure windows. The long idle period between tool permission confirmations
and UI observation changes capacity conditions. Any passing result is restricted
to that measured buffered condition; it is not a causal A/B or proof of depleted
shared-CPU acceptance. Exact timing, data/version and CPU conditions remain in
[raw evidence](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/page-poll-20261025/README.md).

The optional new checkpoint Functional Design still awaits an operator response;
no approval was inferred from execution permissions for deployment/read-only
qualification tools. No durable cache or extra CPU cost is active.

## Final observed result: acceptance not passed

The four-session twenty-second scenario lasts **1415.830s (23m36s)**. It records
**276/280 complete views** (138/140 on each page), plus four genuine **30s page
timeouts** during the engine cycle. All **280 health samples pass**, maximum
**1.286s**. Successful-only p95 Home **0.620s** / Trading **0.829s** is not a
passing readiness series because the failures remain. This is server-protocol
observation, not native viewport acceptance.

The full paper cycle runs **09:52:48.578812Z–09:53:33.020625Z** with twelve monitor
passes and a completed proposal path, without an errored event in the captured
cycle. Engine/dashboard PIDs stay 654/655. Actual background watchers never
exceed **one**. Dashboard RSS/HWM growth is **21.652 MiB**, below its 256 MiB
criterion; whole-guest peak is **1293.313 MiB**, above **768 MiB**, on the actual
2 GiB allocation. Engine RSS peaks at **899748 KiB (878.660 MiB)** during the run,
which alone exceeds that whole-guest budget. Do not sum process RSS to derive
VM use; the guest figure uses MemTotal minus MemAvailable.

Host metrics retain roughly 459 CPU-seconds initially and 410 seconds finally,
with **zero host throttle throughout this observation**. This run therefore
shows that quota exhaustion is not a sufficient explanation for every timeout.
It does not isolate source mutation, allocator or scheduling causes, and is not
a depleted-CPU A/B. The positive watcher/health observations do not close the
cold, failed-view, memory, native or original 1 GiB acceptance gaps.

At the deliberate normal end the harness cancels unfinished requests; this
version records completed/timeout views but may omit such boundary-censored
requests. They are not counted as successes. The four independent 30s timeouts
are retained, so this limitation cannot turn the failed run into acceptance.
The raw driver exits 1 for incomplete views; `qualification-verdict.json` also
checks the original memory ceiling rather than relying on process exit alone.

After load stops, a separate single-client recovery pair completes Home **0.597s**
and Trading **0.515s**, with no incomplete alert/exception. Final source checks
still match all 175 inputs, original volume/capacity/paper/Codex settings and
continued engine cycles. Public health is HTTP200. Existing v62 is retained;
no further engine algorithm, storage, allocation or trading-policy change is made.

## Follow-up boundary

A source trace confirms engine `_current_runtime_safety_score` still invokes
`ActivityLog.read_all()` before 24h reduction, including explicit replay-list
calls that bypass its `None`-only cache. The same score is consumed by an actual
runtime pause gate. This is a concrete archive-sized allocation path, consistent
with the peak but not an isolated allocation profile. Changing lazy evaluation
also changes when default UTC is acquired at the 24h edge. A separate
[runtime-safety-score Functional Design](../../aidlc-docs/construction/runtime-safety-score/functional-design/streaming-activity-inputs/business-logic-model.md)
proposes explicit request-time anchoring, same fixed-time math and guarded bounded
streaming. Its possible conservative pause difference is explicit and **not
implemented or approved**. The earlier persistent checkpoint candidate is also
still approval-pending. Tool permissions were not treated as design approvals.

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

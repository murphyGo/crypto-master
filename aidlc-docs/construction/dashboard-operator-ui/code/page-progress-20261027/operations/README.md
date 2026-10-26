# v66 delivery and failed observation

Source `ce5c4f5eb71a1954ec264c0380eaa7e5c4b0742d` is deployed on the existing
machine as Fly v66. Deployment and post-observation verification both match
all 182 tracked runtime hashes. Image digest is
`sha256:d9a234ff67bd9dd6b1fc1ea76cb1f302c049e677019ae8a388db7179e4c91709`.
The three-file overlay preserves the verified v65 base, installed dependencies,
one shared CPU, 2048 MiB, volume, paper/Codex configuration and engine cadence.
No forced cycles, additional orders, credential changes or capacity changes
were performed. GitHub returned no Actions runs for the requested branch; this
is not a CI pass. Source qualification is recorded in the parent directory.

## Final result

The unchanged four-session protocol observer ran once from
2026-10-26 16:39:23.994031 to 17:09:24.908115 UTC (1800.914084 s).
Its result is **FAIL_SAMPLE**. All 356 starts reconcile to outcomes: 352 complete
and four `aborted_after_guard_stop`. A health TimeoutError after 5.219426 s stops
the run; the four requests are censored at 22.012–23.958 s, not observed 30 s
timeouts. A full natural cycle is not captured within the closed window.
Successful-only p95 is Home 0.726289 s and Trading 0.703791 s; the incomplete
outcomes remain failures. Warm-up Home completion 10.777154 s and first
incomplete receipt 5.069114 s both miss 5 s. Native visual timing is unqualified.

`qa-v66-audit/` retains frozen raw data, the original independent failed audit,
and separately frozen supplements. CPU coverage spans the original window
with 120 samples per series, 15 s apart. The 17:09:00/15 samples show positive
throttle with balances 1.0000096/0.9868925 in raw units. It is not a buffered-only
or no-throttle observation. Exact zero between samples and request-level
causality are unproven; depleted-load qualification is not passed.

Dashboard RSS growth is 67.394531 MiB (conservative HWM growth 67.714844 MiB),
and guest peak is 694.718750 MiB on the current 2048 MiB guest. This does not
qualify the original 1024 MiB target. Diagnostic deliveries have no query or
request identifier and can be rate-limited/dropped; temporal overlap cannot
identify the exact failing verification branch or all page outcomes.

## Recovery and causal limits

`post-observation-runtime.json` at 17:10:21.712921 UTC independently confirms
public/internal HTTP 200, the same engine/dashboard PIDs 652/653, source identity,
and cycle `a78ac2c8-bca3-408e-8370-5d616ea9919c` completed at 17:10:20.751571
after 104.926402 s, 12 monitor passes and zero errors. It does not retroactively
pass the closed observation. No persistent health/process failure or bounds
loss is evidenced, so the deployed correction is retained without rollback.
Both observer and diagnostic collector have stopped; no repeat load was added.

`contention-analysis.json` is reproducible offline with `verify_contention.py`.
The 352 complete requests register no watcher; each interrupted request has one
rerun signal and at most one watcher. A rerender storm is not observed. Before
the natural cycle, dashboard CPU grows 105.63 s in 1745.739 wall seconds during
the four-session workload (about 6.05% of one core, not zero-load idle cost).
From cycle start to before the guard, engine and dashboard grow 9.51 and 6.63
CPU seconds in 27.422 wall seconds. These process counters support examining
shared-guest CPU contention, but do not profile functions, include every child
process, or establish the new watcher change as the cause.

The reproduced global-drain coupling is corrected and independently tested.
Persistent readiness issues are exposed by later operational conditions that
unit tests do not simulate: shared CPU throttling, concurrent sessions and
source writes during engine cycles. Fixing one mechanism cannot certify these
other conditions. Future bounded work should profile pre-cycle dashboard cost
and engine bursts, retain regression cases and rerun unchanged acceptance;
avoid another watcher patch without a causal reproduction. DEBT-083 remains
Critical/open, with cold/native/depleted/original-guest and cost gates unchanged.

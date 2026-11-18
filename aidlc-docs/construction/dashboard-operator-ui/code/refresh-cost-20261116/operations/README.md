# v73 checkpoint sizing delivery — operational evidence

Source `779b60e4131ae246b501425da458833dca051e34` was committed and pushed
before deployment. The four-file build context overlays only the two changed
runtime modules on exact v72; dependencies are unchanged.

- Release73, machine `6835752b711958`, instance `01M7JMF6WMA4MV26FCE1XFWRZ0`.
- Image `sha256:b1fb37ffbba7f93c387c4af4caee85c9c5d21de4b5cc59e3de9edbc1ab810281`.
- Rollback image `registry.fly.io/crypto-master@sha256:7f66519b0490a1610299ac2c75b44b2129201f97a8a71a55b60d4352294224ed`.
- Same shared CPU1/2048MiB, existing machine and volume, paper/Codex and1800s
  cadence. All183 hashes, settings, dependencies and health verified.
- Startup cycle `e462b543-2540-474e-ad23-ae4386228c13`,
  16:54:11.981137–16:54:26.800326UTC:14.819189s, no cycle error/proposals/opens/closes.

The first observed protocol pair precedes the four-session window: Home14.572192s,
first incomplete shell7.795116s; Trading0.971223s. **Home misses both5s targets**.
These remain explicit failed initial-readiness evidence. One initial pair is not
a20-sample cold/native percentile or proof of process/cache-cold isolation.
No cache clearing/manual refresh is used to remove this observation.

The four-session observer alternates Home/Trading every20s, samples health every5s
and guest/process memory every1s, and runs at least600s plus a full natural cycle,
up to2100s. Native browser actions and extra production profiles are excluded from
the measurement window. The sole task-owned temporary idle-sleep guard and
diagnostic collector are bounded and cleaned up by the runner.

The final audit is `PASS_BOUNDED_PROTOCOL_SAMPLE`: 1627.271215s from
2026-11-16 16:57:59.330571 to17:25:06.601786UTC. All325 starts have exactly one
complete outcome (Home162, Trading163), with no timeout/reconnect or shape
failure. Home/Trading p95 is0.628590/0.507615s. Five responses exceed2s:
one Trading2.338051s, plus four requests overlapping the natural cycle at
10.519957–12.306462s. The four incomplete shells arrive at4.189756–4.310148s;
all later complete automatically. These tails are retained, not causal proof
that a particular writer or projection produced the delay.

All323 health checks pass, maximum0.217347s. Guest peak649.605469MiB and dashboard
RSS growth17.582031MiB are measured on the unchanged2048MiB guest. Collection is
continuous: maximum health start gap5.231802s, memory gap1.014647s and memory
trailing gap0.675213s. The natural cycle
`77c32d78-f79a-42a9-9a82-73989f60624e` takes16.627561s
(17:24:26.890472–17:24:43.518033UTC), with12 distinct monitor accounts and no
cycle error, proposals, opens or closes. Startup also has12 distinct monitors.

Each CPU series has109 in-window samples,15s spacing and both surrounding
brackets. Balance remains28.372215–46.332249CPU-seconds; sampled throttle
increments and counter resets are zero. Depleted CPU remains unqualified.
All runner stages exit0; remote sampler cleanup is verified immediately after
observation. Local task/guard absence is verified after daemon recovery on
2026-11-18. A separate late runtime capture at2026-11-18 00:18:47.786825UTC
still matches all183 hashes, settings, image, instance and process start ticks.
This later check does not extend or replace the original observation window.

Files include before/postdeploy/after/late runtime captures, expected source hashes,
original starts/outcomes/health/memory/warmup, CPU history and both brackets,
allowlisted diagnostics, offline audit, runner exits and exact task probe cleanup.
CPU balance/throttle raw units are centiseconds (divide100 for CPU-seconds).
Diagnostic overlap is not causal attribution to an individual request/writer.
The finalizer waits at most35s after the observation for a following CPU bracket;
this is outside the page observation window.

`deploy.log` begins with a note that initial configuration validation passed,
followed by captured builder/deployment output. It is not claimed as a complete
raw terminal transcript. Terminal trailing whitespace is normalized before
hashing; source/JSON/JSONL/binary artifacts are preserved byte-for-byte.

Helpers expect repository-root execution and task scratch paths. The observer is
the source-commit version of `scripts/observe_dashboard_protocol.py`; diagnostics
and CPU capture reuse the retained `home-recovery-20261026/operations/` helpers.
Do not rerun collectors into sealed artifact paths; use a fresh directory.
Run the offline audit with `.venv/bin/python` (Python3.11). An initial attempt
with system `python3` failed parsing Fly's nanosecond timestamp; the project
interpreter completed the audit on the same unmodified data. A first process-list
tool response was truncated and was not accepted as cleanup evidence; the final
`local-cleanup.json` records an untruncated read. The retained cleanup helper is a
reproduction aid; the final check used the method recorded in that JSON.

DEBT-083 stays Critical. A warm protocol sample on2048MiB cannot establish native,
process/cache-cold, depleted-CPU or original1024MiB qualification. Prior failures,
v72 tail delays and this v73 first Home miss remain unchanged. No capacity/cost
or financial behavior change is selected.

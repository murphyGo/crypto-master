# Dashboard v64 qualification continuation — 2026-10-26 KST

Unit: `dashboard-operator-ui`; secondary `runtime-safety-score` and
`notifications-ops`. DEBT-083 remains Critical / active. User `계속 진행`
continues the approved verification after v64 delivery. Production application
source is `dca38fb`, local verification baseline `458ef79`.

The existing dashboard worktree owns the four-session production measurement.
This cycle independently audits its final artifacts and profiles the cold path
locally. There is no second production load, forced engine cycle, restart,
capacity change or trading-control change. Shared CPU 1 / 2048 MiB and the
deferred performance-CPU/cost decision remain.

## Final four-session result: failed complete-readiness acceptance

The observation spans 17:41:21.639–18:10:28.743 UTC (29m07s). Independent QA
reconciles all **349 starts with 349 outcomes**, without duplicate or orphan
requests. **347 complete; two Home requests are incomplete.** Home completes
172/174 and Trading 175/175. Successful-response p95 is 0.761 s / 0.724 s;
excluding the two failures does not turn this run into a pass.

The Home failures begin at 18:09:42.146 and 18:09:43.333 UTC and return after
12.094 s / 11.335 s. Both expose only Open Positions and Candidates metrics,
two dataframes and two incomplete-data alerts, with no exception and one
maximum background watcher. The raw protocol record does not retain the alert
reason text or first-shell timestamp, so it cannot identify the cause or certify
the incomplete shell appeared within 5 s. These requests overlap the natural
engine cycle, but overlap alone is not proof of CPU contention or source churn.

The complete natural cycle is 18:09:40.673–18:10:00.940 UTC (20.267 s), with no
`cycle_errored` event in the recorded cycle stream. All **347 health checks pass**
(maximum 0.269 s). Observed guest use peaks at **708.25 MiB** and dashboard RSS
growth/high-water increase at **83.902 MiB**. Engine/dashboard PIDs remain stable;
the dashboard thread count returns from a sampled maximum 37 to its initial 9.
Memory is sampled about once per second, with process high-water evidence
retained. These are current 2048 MiB observations, not original 1024 MiB acceptance.

Sixteen raw/context artifacts were frozen with file-generation checks and
SHA-256. Independent recomputation matches every declared summary field, and
replaying the auditor over the frozen set reproduces the result. The frozen CPU
snapshots end at 17:48:21 UTC, before the failures; neither full-window CPU
behavior nor depletion is established by that set.

A later CPU supplement is retained separately, without rewriting that initial
freeze. Its 15-second samples cover the full run (17:40:45–18:10:45 UTC), with
positive balance throughout sampled run points (1277–3076) and sampled throttle
zero. The run therefore does not qualify depleted CPU, and CPU exhaustion is
not evidenced as the cause of the two incomplete responses.

Post-run verification at 18:15:40 UTC confirms the same v64 machine instance,
image, resources, volume and all 180 deployed source hashes; public/internal
health remains 200/ok. The natural cycle has twelve `monitor_pass` events,
zero errors and zero proposals. DEBT-087/088/089 pure read-only replay again
passes eighteen account/version score checks and seven cap rows, with all
24 persisted input hashes unchanged. This is replay coverage, not newly emitted
proposal/safety decisions. No new deployment was required for this audit.

Source tracing maps the final Home shape to verified ledger/candidate sections
and incomplete activity/snapshot sections. The protocol terminal is a successful
script finish with no remaining registered fragment, not a 30 s timeout or an
exception. The maximum single watcher confirms coalescing, but does not prove
successful recovery. Possible source paths include a short cached read failure
followed by an immediate partial rerender, and `queue_full` being retried by
`request_many` while not registering the page's pending/rebuild watcher. Neither
is proven to be this incident's cause.

The next concrete diagnostic slice is to retain bounded query kind/status/reason,
cache age, admitted-job count and verification stage, plus protocol alert
classification and first-shell time. Reproduce Home's five-query interaction for
source-generation failure/error caching and queue saturation before changing
retry behavior. Keep diagnostics free of raw records, credentials and identifiers.
These are continuation work within DEBT-083, not newly registered strategy bugs.

## Cold-path diagnosis

The specialist profiled exact v64 code on a frozen 1,000,000-row / 640,453,970-byte
fixture. Canonical and new empty checkpoint-store paths produce identical full
payloads. All thirteen source and ten fixture hashes are unchanged. Reliable
single-thread profiles attribute the common cost to per-event aggregation and
canonical model validation. New checkpoint generation adds structural sizing
and encoding costs; 1.636 s of that instrumented run is spent in full size scans
used only for codec branch selection.

An exact early-exit threshold predicate is a concrete, bounded follow-up
candidate for that branch. Full admission accounting, codec bytes/schema,
fallback and semantic results must remain identical. It cannot alone resolve
the common canonical cold miss. A pure gate-vocabulary import also avoids an
unnecessary Streamlit/pandas page import. Neither change is implemented here.

The initial threaded cProfile attribution was contaminated and is retained as
rejected attribution evidence. It was replaced by single-thread profiling of the
exact production generator with equal import warm-up. These one-off instrumented
times are not latency percentiles. Existing twenty canonical no-store queries
have p95 7.817 s, exceeding 5 s; seeded restart p95 0.695 s excludes bootstrap and
native rendering. The historical 11.143 s `first_unseeded` observation did not
prove an initially empty store and is labelled accordingly.

## Native browser

Supported Browser runtime bootstrap fails before page selection because the
packaged `browser-service.mjs` is absent. Native acceptance is blocked by tool
setup; this is not evidence of a dashboard render failure. Available plugin
tools have no repair operation. The operator has been asked to restore Browser
through application plugin settings; no successful readiness reply is yet
available. No alternative-browser result substitutes for the native gate.

## Why additional issues appear during verification

The remaining work is primarily unfinished acceptance for the existing
DEBT-083, not three new strategy defects. Source tests and a healthy endpoint
do not establish complete page readiness under archive growth, a cold store,
concurrent sessions and engine activity. Runtime and dashboard share the same
VM; reducing one reader's memory cost does not prove every workload/resource
condition. Seeded reuse improves repeated requests while the first construction
still pays validation, aggregation and encoding costs. These distinctions explain
why broader operational checks reveal work after a local source gate passes.

The process correction is to declare the exact source, cold/cache state,
workload, resource envelope, complete engine-cycle window and acceptance owner
before claiming completion. Keep failures and unavailable conditions visible
instead of creating a new prerequisite issue for each observation. The three
strategy fixes DEBT-087/088/089 retain their delivered status and independent
coverage limits. The separate runtime candidate remains archived.

Evidence: `aidlc-docs/construction/dashboard-operator-ui/code/qualification-continuation-20261026/`.
Plan: `aidlc-docs/construction/plans/dashboard-v64-operational-qualification-continuation-plan.md`.

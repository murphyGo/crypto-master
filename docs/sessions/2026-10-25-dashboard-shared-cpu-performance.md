# Session: Dashboard Performance on Retained Shared CPU

- **Unit / debt:** `dashboard-operator-ui` / DEBT-083, Critical and active.
- **Requirements / stories:** FR-029/031/032/036/042, NFR-003/007/008/011/012, BDL-NFR-01..08; US-012/014/020/023.
- **Authorization:** `gogo` resumes source improvements and the previously authorized scoped deployment. The performance-CPU / incremental-cost proposal remains deferred by the operator's `보류`; shared CPU 1 / 2048 MiB, existing volume and paper/Codex settings are retained.
- **Baseline:** main `8ac6d66`, deployed runtime `22abf3d` / Fly v59. Unrelated root `.claude` configuration/lock are outside the isolated worktree.

## Changes

Activity cycle state retains normalized UTC datetimes until publication instead
of serializing every event timestamp and parsing the retained values again.
Started cycles still precede unstarted cycles, including the minimum representable
UTC timestamp. First/terminal source-order ties and all counters remain exact.

The bounded JSON array scanner exposes immutable raw object bytes. Its existing
dictionary reader remains a validating compatibility wrapper. Snapshot projections
validate those bytes directly into the existing model, eliminating an intermediate
dictionary while preserving model coercion, financial precision, latest-row ties,
curve sampling and every-record validation. Record/block bounds and generator
closure remain in force.

Source digests include the exact selected file membership and every captured
file's device, inode, size and nanosecond mtime. Directory metadata no longer
invalidates an otherwise identical selection solely because an unrelated sibling
or temporary writer file was created. Discovery still captures directory versions
and verifies them at publication, rejecting concurrent membership changes. No
append cursor, durable index, writer, cache-age or memory-limit change is made.

## Verification and evidence

Focused reader/projection/service/default-page checks: **72 passed**, followed
by two additional early-close descriptor tests included in final broad validation.
An initial broad run passed 2740 tests in 258.27s before the minimum-timestamp
sorting edge was covered; final broad validation passes **2743 tests in 237.50s** on source `38876fc`.
Final Black/Ruff pass for all five changed Python files; mypy passes for 129
source files. Code review has no unresolved source correctness finding. The
remaining performance/native/resource limitations are not waived.

Twenty alternating baseline/candidate samples use declared generated workloads,
fresh services and warmed imports/OS caches. UTC evaluation is fixed, and complete
canonical business payloads and coverage must match on every sample. Only the
internal `_source_digest` is excluded because directory generation is intentionally
removed from that digest. This is offline query evidence, not native page or
shared-guest acceptance. Final results and source hashes are in
[paired measurements](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/shared-cpu-20261025/paired-query-measurements.json).

| Generated workload / twenty samples per backend | Baseline p95 | Candidate p95 | Median reduction |
|------------------------------------------------|-------------:|--------------:|-----------------:|
| 1,000,000 activity events / ten files | 10.467s | 10.872s | 5.29% |
| 84,500 snapshots / thirteen accounts | 3.781s | 3.648s | 3.44% |
| 20,000 activity events, revalidation after unrelated directory insertion | 0.773s | 0.00398s | 99.50% |

All 120 complete results match the baseline's full business payload and coverage.
Activity median improves modestly but its p95 worsens in this series, so no
million-event tail-latency improvement or 5s acceptance is claimed. Snapshot
improvement is modest. The strong measured change is avoiding a full reread after
irrelevant directory changes. The same-process comparison loads both backends;
its peak RSS is not an isolated candidate or shared-guest measurement.

## Current production checkpoint

Read-only pre-rollout verification confirms 173 application/startup file hashes
against runtime `22abf3d`; paper mode, Codex/Astra and Claude rollback are intact.
The existing machine is started with shared CPU 1 / 2048 MiB; HTTP health returns
200 / `ok` in 0.184s. The latest captured engine cycle completes at
2026-10-24T17:15:03Z. Engine/dashboard RSS is 319636 / 227212 KiB; guest available
memory is 1300024 KiB at 17:15:54Z. This one observation does not qualify the
original shared-guest or four-session resource requirements.

An actual deployed-version protocol observation gets complete Home/Trading
responses in **14.702s / 2.504s**. Home has twelve metrics and four tables;
Trading has six metrics, three tables and a chart. No exception or incomplete
availability alert remains. Cache state is uncontrolled and the runs are sequential;
this is not a controlled deployment timing comparison or native percentile pass.

Browser connection was retried. Its runtime service cannot load from the current
local plugin path, so native viewport/four-session acceptance remains unqualified.
The protocol observation is distinct from that missing evidence.

## Rollout and remaining acceptance

Fly **v60** runs source **`38876fcda9bd5bedba5dd4465fb5905175e38dc2`**, image
`sha256:45d057bd3ee44f42651b68f78ea2c7256403f5abc5ae58fec692c7c000375745`.
Release `rel_59glz5g0o194y6k3`, instance `01M5QGN2SR1RKDXXRS1245EDM5`, existing
machine `6835752b711958` / nrt. Shared CPU 1 / 2048 MiB and encrypted original
volume `vol_4m3l58dkk29y19zv` are verified unchanged; Fly health is passing.

All **175 runtime input hashes match**. Python 3.13.16, Streamlit 1.65.0,
Pandas 3.0.6, Pydantic 2.14.0/core 2.50.0 and NumPy 2.5.4 remain in the pinned
v59 base. Only the three reviewed source files are copied. Fly's configured
`build.dockerfile` overrides the CLI Dockerfile flag and resolves relative to
its config directory; a build-only temporary manifest selects the overlay.
An initial default-Dockerfile build was cancelled and never deployed. Activation
uses the **unchanged root `fly.toml`** and exact prepared digest, restricted to
the existing machine with explicit shared / 1 / 2048 flags. Live controls,
runtime data, CLI provider/auth and the original volume remain unchanged.

At 2026-10-24T17:53:30Z, source/process verification confirms paper/Codex/Astra
and Claude rollback. Engine/dashboard RSS is 228592 / 239400 KiB; guest available
memory is 1418560 KiB. The first post-rollout paper cycle
`9455e92a-8dfe-4032-90c7-6da46583bab5` starts at 17:52:18.964249Z and completes
at **17:52:54.073751Z**. This is observed engine continuity, not full resource
or four-session qualification.

The first observed post-rollout Home/Trading protocol pair completes in
**17.502s / 2.480s**, with twelve/six metrics, four/three tables and the Trading
chart. There are no render exceptions or incomplete-availability alerts at
completion. The Home wait still exceeds the complete-readiness target; these
single sequential pre/post observations have different cache/startup conditions
and do not establish a page-latency improvement or native percentile pass.

[Release identity](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/shared-cpu-20261025/deployed-release.json),
[actual runtime verification](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/shared-cpu-20261025/after-runtime-verification.json)
and [post-rollout protocol observation](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/shared-cpu-20261025/after-protocol-observation.json)
retain the scoped operational evidence.

DEBT-083 stays active. Million-event cold latency, native viewport/four-session
and original guest/resource targets require separate successful evidence. The
deferred performance CPU proposal is not activated by this source continuation.

- [Construction plan](../../aidlc-docs/construction/plans/dashboard-operator-ui-shared-cpu-performance-plan.md)
- [Evidence directory](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/shared-cpu-20261025/)

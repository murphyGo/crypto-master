# Dashboard proposal refresh CPU cost — 2026-10-27 KST

Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
DEBT-083 remains Critical / active. Baseline main is `2eae9cf`, previously
source `ce5c4f5` / Fly v66; the correction is now `120b440` / Fly v67. Work is isolated in
`/private/tmp/crypto-master-cpu-cost-20261027`.

**Bounded correction committed, pushed and deployed; observation FAIL_SAMPLE.**
The implemented correction removes an unused checkpoint eligibility calculation
from unchanged proposal refreshes. The full suite passes 3,021 tests and
independent source QA is GREEN. All 182 deployed runtime hashes, both health
endpoints and natural cycles pass verification. The single concurrent
observation retains 348 complete and eight incomplete requests out of 356.
The measured hotspot correction is verified, but readiness is not qualified
and DEBT-083 remains Critical / active.

## Evidence and selected correction

The October 25 frozen Fly snapshot contains 13,084 proposal files. Baseline
profiling executes the actual `build_projection` path with warmed imports and
OS cache, fixed UTC evaluation time `2026-10-25T10:50:02Z`, and exact full-output
equality. Each repeated request revalidates source generations as an expired
service result would; it does not use the service's fresh-result shortcut.

Across five unchanged proposal refreshes, cProfile records 2.135347 s cumulative
elapsed time, including 1.215076 s in the optional average-source-size sum.
That calculation expands packed entries into 65,420 `Source`/`Path` objects
although unchanged whole-query reuse never consults its result. It also runs
when checkpoint preparation is disabled. The separately recorded process CPU
times total 2.067764 s across those five instrumented refreshes. Profile time
and process CPU time are different measurements; neither is a production
percentile or a measured production improvement.

The runtime change is only `src/dashboard/projections.py`: the average-size
eligibility check now follows the verified unchanged-digest return and runs
only when `cache_prepared` is true. It preserves the existing strict
`sum(size) < 16 * 1024 * max(1, file_count)` arithmetic on changed/cold inputs.
The threshold concerns optional per-source checkpoints, not source eligibility
or displayed trading data.

Every required path still discovers file membership, computes its digest,
charges retained state, refreshes time-dependent values and verifies all
selected file and directory generations. Replacement, append, membership
change or concurrent mutation must reject/rebuild exactly as before. No new
cache, schema, validation shortcut, source omission or metric definition is
introduced. One worker, four admitted jobs, four-second foreground wait,
two-second complete freshness, thirty-second explicit stale data and manual
terminal retry remain unchanged.

The current [plan](../../aidlc-docs/construction/plans/dashboard-cpu-cost-plan.md)
and [design](../../aidlc-docs/construction/dashboard-operator-ui/code/cpu-cost-20261027/design.md)
record this selection. The developer owns the source change and targeted
regressions; independent QA owns parity/bounds review. The lead owns source
gates, integration, operations and state/debt updates. This documentation slice
owns only this session and its cross-check.

## Separate engine context

Read-only source tracing confirms that each monitored account records a
portfolio snapshot by loading historical models and serializing the complete
snapshot list. A separate local five-trial replay of the frozen fixture's
twelve active accounts, 88,192 snapshots / 33,211,660 bytes, measures median
0.876439 s process CPU for JSON decode, model validation, dictionary conversion
and JSON encoding; range 0.829849–0.913210 s. Warm file-read CPU is measured
separately. The replay excludes PnL computation, new-row append, atomic writes,
imports and network work; fixture/source hashes and mtimes remain unchanged.

This establishes existing repeated work, not its production CPU fraction or
the cause of v66's failure. Local macOS/Python/Pydantic and warm-cache conditions
differ from production. No engine, portfolio, persistence or trading code is
selected for this correction. Runtime safety scoring is only invoked from
proposal handling; the failed v66 cycle's zero proposals do not support
attributing that cycle to runtime-safety archive scanning.

## Verification checkpoint

| Gate | Current evidence / status |
|---|---|
| Baseline profile | Actual frozen-source proposal refresh; five instrumented repeats; fixed-time 38,436-byte payload, SHA-256 `3ee8372c6bdf2a7391167929c72657ded3f536658e1bc127940f485ef50a32b0`. |
| Behavioral regression | Corrected baseline: three intended failures / ten passes in 2.23 s. Candidate: 153 focused tests pass in 5.21 s, including thirteen new cases. |
| Independent source QA | GREEN: 175 tests pass in 4.60 s; additional independent exact-24-hour boundary/+1 microsecond expiry proof passes with stores enabled/disabled. Mutation, malformed changed data, reversed clock and strict/mixed threshold behavior remain protected. |
| Paired performance measurement | Twenty alternating uninstrumented pairs in each of four scenarios; all forty output fingerprints match within each scenario, all twenty candidate CPU times are lower, fixture/source hashes unchanged. Independent light audit GREEN for local CPU comparison only. |
| Static source gate | Black/Ruff pass both changed Python files; source-wide mypy passes all 135 source files. |
| Full regression | 3,021 passed in 228.36 s, Python 3.13.0. `/Users/user/Desktop/Projects/crypto-master/.venv/bin/python -m pytest -q`; wrapper elapsed 229.657 s. All 262 `src`/`tests`/`scripts` input hashes remain unchanged during the run. |
| Commit/push and rollout | `120b4408dc0d3eedb241edf26f8f161c062cf126` confirmed on remote main; deployed as Fly v67. Root main fast-forwarded while preserving unrelated `.claude` work. |
| Initial deployed verification | Capture `2026-10-26T17:52:51.096640Z`: all 182 runtime hashes match; public/internal health 200/ok; first natural cycle 19.155882 s, twelve monitors, zero recorded errors and zero proposals. Dependencies, configuration, guest and volume are unchanged in `deployment-verification.json`. |
| Bounded production observation | **FAIL_SAMPLE**: 1,774.272486 s, 356 matched starts/outcomes, 348 complete and eight incomplete. All 352 health checks and one full natural cycle pass; incomplete requests and warm-up misses remain failures. |

The final runtime-file SHA-256 is
`0399e63c3f822ee381e2c6f6fa28ba56bb639521420cee2d5b0e6bc03d68704d`;
the only new test file is `tests/test_dashboard_proposal_refresh_cost.py`.
The developer's focused command runs that file plus
`test_dashboard_projections.py`, `test_dashboard_segment_checkpoints.py`,
`test_dashboard_data_service.py` and `test_dashboard_bounded_pages.py` with
the existing root `.venv/bin/python -m pytest ... -q`. QA independently runs
the first four files plus `test_bounded_read.py`.

| Controlled replay scenario | Baseline median CPU | Candidate median CPU | Reduction |
|---|---:|---:|---:|
| Direct proposal refresh, disabled store | 0.205778 s | 0.135030 s | 34.38% |
| Direct proposal refresh, enabled store | 0.205351 s | 0.133147 s | 35.16% |
| Home query-service replay, enabled store | 0.237497 s | 0.165783 s | 30.20% |
| Trading query-service replay, enabled store | 0.233254 s | 0.163973 s | 29.70% |

The service scenarios call actual `request_many` with one worker but use a
controlled builder and previously canonical-validated bytes primed twenty
seconds old. They isolate mandatory generation revalidation beyond the
two-second freshness limit; they are not full-page rendering or native browser
measurements. Trial order alternates, setup/output hashing is outside timing,
and enabled-store setup explicitly creates the root and asserts preparation.
Concurrent host test activity makes wall timings diagnostic only. Process CPU
does not measure Fly guest, engine or observer CPU and cannot establish live
health/throttle recovery.

Separate actual enabled-store AppTest baseline/candidate records execute the
real Home/Trading render functions: one bootstrap and two warm runs per page
per variant preserve each page's saved fingerprint. They are supplementary local functional
evidence, not twenty-sample page performance or native qualification. The
initial `service-page-baseline.json` incorrectly labelled an absent store root
as enabled; preparation actually returned false. Its raw values remain
unchanged, with `service-page-baseline-correction.json` identifying the mistake.
An initial test-fixture run similarly had six failures / seven passes; creating
the owned store root removed three setup failures before the corrected
three-failure baseline. No runtime source changed between those baseline runs.

Evidence is retained under
`aidlc-docs/construction/dashboard-operator-ui/code/cpu-cost-20261027/`:
`developer/baseline-profile.json`, `developer/input-manifest.json`,
`developer/developer-verification.json`, `developer/diagnosis-summary.json`,
`developer/paired-cpu-results.json`,
the enabled AppTest records and method correction, `qa/source-verdict.json`,
`qa/benchmark-light-audit.json`, `source-qualification.json`,
`source-input-sha256.json`, `full-pytest.txt`, and the separate
`engine-context/result.json` / `engine_snapshot_profile.py.txt`.
Temporary originals, including `engine-snapshot-profile/canonical-snapshot.prof`,
remain under `/private/tmp/crypto-master-cpu-cost-delivery-20261027/`.

## Deployment checkpoint

Source `120b4408dc0d3eedb241edf26f8f161c062cf126` is remotely confirmed and runs
on Fly v67, image
`sha256:2aa60d27cf4aed283b9e4596e17cf3403f39b88794b3347f5abeb40462700382`,
existing machine `6835752b711958`, instance `01M5WNEGCGSRY9CE34VRT7K6X3`.
The read-only `postdeploy.json` capture records engine/dashboard PIDs 652/653,
one shared CPU / 2048 MiB, existing `/data` volume, paper/Codex settings and
1,800-second engine cadence. `operations/deployment-verification.json` confirms
dependencies, configuration, guest and volume unchanged against the retained
baseline; no capacity, cadence or trading-policy change was made.

Cycle `bfb58896-6917-4a20-9523-ca4b5bf3c6ed` runs
`2026-10-26T17:52:18.752809Z`–`17:52:37.908691Z`, 19.155882 s, with twelve
monitor passes, zero recorded errors and zero generated/accepted/rejected/opened/
closed proposals or trades in its completion summary. This initial cycle
precedes the observer window. The subsequent observer captures the next full
natural cycle without forcing it; its result is recorded separately below.

There is no actual proposal or cap-event coverage in this initial cycle:
`proposal_checks` and `cap_checks` are empty. A separate pure deployed-method
replay checks eighteen strategy/version score rows across twelve accounts,
all matching current persisted sample counts, and eleven monitorable legacy
trade cap rows. Its twenty-four input hashes remain unchanged during that
read-only replay. Confidence is fixed to one, proposal joins are omitted and
market marks are unknown, so this is method/input corroboration rather than
emitted-proposal behavior. Funding remains unknown; the carry smoke is a
hypothetical scenario, not actual funding accounting. The capture is retained
as `operations/postdeploy.json` under the construction evidence directory.

## Final v67 operational observation

The unchanged four-session observer runs from
`2026-10-26T17:54:18.225469Z` to `18:23:52.497955Z`, 1,774.272486 s,
with twenty-second cadence and the existing minimum-600/maximum-2,100-second
limits. Independent QA reconciles all 356 starts to 356 outcomes, with no
duplicates, unmatched requests, classification failures or declared-summary
differences. **348 complete / eight incomplete is FAIL_SAMPLE**, even though
both page percentiles are below the warm latency target.

| Observation | Result |
|---|---|
| Home | 174/178 complete, four incomplete; complete-only p95 0.576250 s; all-outcome terminal-time p95 0.682332 s. |
| Trading | 174/178 complete, four incomplete; complete-only p95 0.487714 s; all-outcome terminal-time p95 1.026017 s. |
| Health | 352 checks, all successful; maximum 0.661728 s. |
| Full natural cycle | `54425221-0b58-4c65-bbec-573474aa4d00`, `18:22:37.998358Z`–`18:23:12.286517Z`, 34.288159 s wholly inside the window; twelve monitor passes, zero errors and zero proposals. |
| Memory | Guest peak 663.171875 MiB; dashboard RSS growth 31.578125 MiB on unchanged 2048 MiB capacity. This does not qualify the original 1024 MiB configuration. |
| Retained warm-up | Home complete 12.956247 s; first incomplete-shell receipt 5.507020 s. Both five-second targets miss; protocol receipt is not native rendering. |

All-outcome terminal-time percentiles include unsuccessful outcomes and do not
measure time to a complete page for those failures. The first four incomplete
requests end with an activity-stale alert and zero watchers near cycle start.
The next four end with snapshots-unavailable alerts after 17.282–18.581 s,
each with at most one watcher and two rerun registrations. These are terminal
incomplete responses, not thirty-second timeouts or v66-style guard aborts.
Their overlap with the natural cycle does not establish a sole cause.

The separate diagnostic supplement retains 566 rows, 555 timestamped inside
the window, with zero parse/schema failures. It includes activity/snapshot
`source_changed` and queue/rebuild states. Diagnostics are asynchronous,
rate-limited and lack request identity; intermediate events can occur during
successful pages and cannot be counted as page failures or mapped conclusively
to each failure. The separate `operations/residual-analysis/findings.md`
traces three emitted `source_changed` projection failures and their error-cache
echoes. Activity stale and snapshots stale-to-unavailable agree with preserved
cache ages around 21 s / 24 s / 35 s. Current terminal policy has no automatic
page watcher for that reason, while later requests can retry after error TTL.
Exact writer, verification branch and the 17–18 s time allocation remain unknown.
A finite coalesced source-generation retry is proposed with full validation and
all existing limits; it is not implemented or qualified by this observation. No additional production test is part of this closeout.

The initial frozen QA summary records CPU coverage as unavailable at that
checkpoint. Immutable `cpu-window-proof.json` and
`cpu-counter-interpretation.json` subsequently qualify sampled coverage without
rewriting that summary. Each CPU series contains 118 in-window samples at
fifteen-second spacing, `17:54:30Z`–`18:23:45Z`, bracketed by `17:54:15Z` and
`18:24:00Z`; five of 123 captured values are excluded per series. Balance is
932.0077104–4031.0047002 centiseconds, baseline 0.0625 CPU units, and the
throttle cumulative counter remains zero with zero positive deltas. No sampled
reset or changed boundary-crossing interval is observed. This supports no new
throttling in the sampled intervals, not depleted-CPU qualification or absence
of shorter unsampled transients. The CPU result was published at
`18:24:29.552468Z`, 37.054513 s after the window; that publication timestamp is
not the query start time.

Post-run verification captured at `18:24:40.539128Z` again matches all 182
runtime hashes, the same source/image/instance and PIDs 652/653, with both
health endpoints 200/ok. It corroborates service continuity and the completed
cycle; it does not repair the eight failed page requests. The read-only replay
still has no actual emitted proposal/cap rows.

Frozen QA evidence is retained under
`aidlc-docs/construction/dashboard-operator-ui/code/cpu-cost-20261027/operations/qa-ops-v67/`:
`audit-summary.json`, `audit-results.json`, `freeze-manifest.json`,
`diagnostics-supplement.json`, `cpu-supplement.json`,
`cpu-window-proof.json` and `cpu-counter-interpretation.json`. The final runtime
capture and continuity comparison are retained as sibling
`operations/postrun.json` and `operations/postrun-comparison.json`. Temporary
originals remain in the delivery directory and
`/private/tmp/crypto-master-debt087-089-closeout/cpu-cost-final.json`.

## Prior failures and unchanged acceptance

V66 remains **FAIL_SAMPLE**: 356 matched requests, 352 complete and four
`aborted_after_guard_stop`, with a 5.219426 s health timeout and no complete
natural cycle inside the 1,800.914084 s observation. Those four outcomes were
censored after approximately 22–24 s, not measured thirty-second timeouts.
Home warm-up completion 10.777154 s and first incomplete-shell receipt
5.069114 s also miss their five-second targets. Positive CPU throttling overlaps
the failure; function-level causality is not established. Post-window cycle and
health recovery do not retroactively pass the sample. See the
[v66 session](2026-10-27-dashboard-page-progress.md) for its frozen evidence.

The new local optimization cannot waive cold/native/depleted/original
1024 MiB qualification. Complete Home/Trading targets remain cold p95 ≤5 s and
warm p95 ≤2 s, at least twenty samples per required page/scenario, retaining
failures. Incomplete-shell timing is a separate target. Four concurrent
sessions must include a full natural cycle and healthy service; native browser
acceptance is distinct from protocol receipt. Guest ≤768 MiB on the declared
1024 MiB configuration and dashboard growth ≤256 MiB remain separate checks.
Current deployment stays one shared CPU / 2048 MiB with the same dependencies,
configuration, volume, cadence and trading controls. Prior v64/v65 failures and
DEBT-083 Critical / active status are preserved.

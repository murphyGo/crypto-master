# Dashboard proposal refresh CPU cost — 2026-10-27 KST

Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
DEBT-083 remains Critical / active. Baseline main is `2eae9cf`; production
remains source `ce5c4f5` / Fly v66 at this checkpoint. Work is isolated in
`/private/tmp/crypto-master-cpu-cost-20261027`.

**Source qualified; ready for commit/push and same-configuration rollout.**
The implemented correction removes an unused checkpoint eligibility calculation
from unchanged proposal refreshes. The full suite passes 3,021 tests and
independent source QA is GREEN. Deployment and operational observation are
pending; this does not explain every production failure or complete the
original readiness gates.

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
| Commit/push and same-configuration rollout | Pending. No new production source claim at this checkpoint. |
| Bounded production observation | Pending; retain each failed request, health guard, guest/CPU evidence and a complete natural engine cycle inside the observation window. |

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

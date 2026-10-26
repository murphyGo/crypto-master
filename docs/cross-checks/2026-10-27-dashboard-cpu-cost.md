# Cross-check: dashboard proposal refresh CPU cost — 2026-10-27 KST

Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
Baseline main `2eae9cf`; existing deployed source `ce5c4f5` / Fly v66.
DEBT-083 is Critical / active. This source checkpoint is GREEN and ready for
commit/push and same-configuration rollout: 3,021 full tests, independent
source QA and controlled output/CPU comparisons pass. Deployment and
operational acceptance remain pending.

## Scope and traceability

The [construction plan](../../aidlc-docs/construction/plans/dashboard-cpu-cost-plan.md)
maps this work to BDL-NFR-03/04/06/07/08, FR-029/031/032/036/042,
NFR-003/007/008/011/012 and US-012/014/020/023. The
[design](../../aidlc-docs/construction/dashboard-operator-ui/code/cpu-cost-20261027/design.md)
selects only checkpoint average-size eligibility in
`src/dashboard/projections.py`, plus relevant regression tests.

Moving the optional proposal heuristic below unchanged-digest reuse and adding
the `cache_prepared` guard avoids work whose result cannot affect those paths.
It preserves the strict sixteen-KiB average cutoff on paths that use the result.
No new service, dependency, checkpoint format, data source, runtime write,
deployment setting or trading behavior is authorized by this correction.

## Evidence matrix

| Claim / obligation | Evidence and assessment |
|---|---|
| A specific avoidable cost exists | Frozen October 25 Fly fixture, 13,084 proposal files. Five exact-source unchanged refreshes: cProfile cumulative 2.135347 s, optional size sum 1.215076 s, 65,420 reconstructed entries. Separate process CPU totals 2.067764 s. Measured locally with warmed imports/cache; not production attribution. |
| Baseline/output parity | Fixed `2026-10-25T10:50:02Z`; complete proposal payload 38,436 bytes, SHA-256 `3ee8372c6bdf2a7391167929c72657ded3f536658e1bc127940f485ef50a32b0`. All forty before/after output fingerprints match within each of four paired scenarios. |
| Canonical meaning and boundaries | Independent source QA GREEN: 175 tests / 4.60 s, plus exact-24-hour boundary and +1 microsecond expiry proof for both store modes. Source/member mutation rejection, malformed changed data, reversed clock and strict/mixed average thresholds remain protected. |
| Behavioral regression | Corrected baseline three failures / ten passes in 2.23 s; candidate 153 focused passes in 5.21 s, including thirteen new cases. Only heuristic ordering/guard changes in runtime source. |
| Source gates identify exact final code | 3,021 full tests pass in 228.36 s on Python 3.13.0; wrapper 229.657 s. All 262 inputs unchanged. Black/Ruff pass two files; mypy passes 135 source files. |
| CPU improvement is quantified honestly | Twenty alternating uninstrumented pairs per scenario: direct disabled/enabled store median process-CPU reductions 34.38% / 35.16%; Home/Trading query-service replay 30.20% / 29.70%. All twenty candidate values lower in each scenario. Fixture/source unchanged; light audit GREEN for this local comparison only. |
| Engine context does not expand scope | Separate pure snapshot replay: active twelve-account median 0.876439 s CPU, 88,192 rows; excludes actual engine/IO-write/network/PnL work. No engine change or production-cause claim. |
| Deployment preserves operational settings | Commit/push, exact deployed hashes, dependencies/config/volume/capacity and first natural cycle verification pending. |
| Readiness has not been declared | Existing v66 FAIL_SAMPLE remains; no live observation for the selected correction yet. |

The twenty-pair Home/Trading cases are controlled `request_many` replays with
a custom builder and already validated bytes primed twenty seconds old, beyond
the two-second complete freshness limit. They include actual worker
revalidation but not full-page/native rendering. Enabled preparation is
explicitly asserted. Warm imports/hash-warmed filesystem cache, historical
data and concurrent host load prevent production/cold inference; wall timings
are diagnostic only.

The initial service/page baseline wrongly described an enabled store although
its missing root made preparation false. The original raw record remains
unchanged and its correction is retained. Separate actual enabled-store
AppTest baseline/candidate records each contain one bootstrap and two warm
runs per page with matching saved fingerprints; they do not supply twenty-sample page/native
acceptance. The test fixture also preserves its initial six-failure/seven-pass
setup error and the corrected intended three-failure/ten-pass baseline.

The runtime file hash is
`0399e63c3f822ee381e2c6f6fa28ba56bb639521420cee2d5b0e6bc03d68704d`.
The full command is
`/Users/user/Desktop/Projects/crypto-master/.venv/bin/python -m pytest -q`.
The review evidence is retained under
`aidlc-docs/construction/dashboard-operator-ui/code/cpu-cost-20261027/` in
`developer/baseline-profile.json`, `developer/input-manifest.json` and
`developer/developer-verification.json`, `developer/diagnosis-summary.json`,
`developer/paired-cpu-results.json`,
the original/corrected/enabled AppTest records, `qa/source-verdict.json`,
`qa/benchmark-light-audit.json`, `source-qualification.json`,
`source-input-sha256.json` and `full-pytest.txt`. The separate engine replay is
`engine-context/result.json`. Temporary originals remain under
`/private/tmp/crypto-master-cpu-cost-delivery-20261027/`; operational entries
remain pending.

## Original acceptance remains independent

| Requirement / historical result | Current status |
|---|---|
| V66 four-session observation | **FAIL_SAMPLE**: 356 matched / 352 complete / four guard-aborted; health 5.219426 s timeout; full cycle ends outside the 1,800.914084 s window. Failures remain counted. |
| V66 warm-up | Home 10.777154 s complete and 5.069114 s first incomplete-shell receipt exceed five seconds. One warm-up is not a twenty-sample cold qualification. |
| CPU evidence interpretation | Positive throttle overlaps the failed period; neither per-process counters nor this local hotspot prove the exact failing function or sole cause. Successful depleted-CPU qualification remains open. |
| Cold / warm complete-page targets | Cold p95 ≤5 s / warm p95 ≤2 s, at least twenty samples per required page/scenario; failures retained. Cacheless queries, seeded reuse and process-cold starts are separate conditions. Pending. |
| Native rendering | Protocol messages and local execution do not certify native browser/viewport acceptance. Pending. |
| Concurrent sessions / natural cycle | At least four sessions, minimum ten minutes and one full natural cycle inside the observed window; health remains within the guard. Pending for this correction. |
| Memory / original capacity | Dashboard growth ≤256 MiB; guest use ≤768 MiB on declared 1024 MiB. Current 2048 MiB observations do not qualify the original capacity. Pending. |
| Protected runtime behavior | One worker/four admitted jobs, bounded state, four-second foreground wait, two-second complete freshness, thirty-second explicit stale fallback, generation proof and manual terminal retry remain required. |

The [session](../sessions/2026-10-27-dashboard-cpu-cost.md) separates this
diagnosis from historical v64/v65/v66 outcomes. Local evidence qualifies this
bounded source correction; it does not close DEBT-083 or authorize
capacity, cadence, credential, cost or trading-policy changes.

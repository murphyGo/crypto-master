# Cross-check: dashboard proposal refresh CPU cost — 2026-10-27 KST

Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
Baseline main `2eae9cf`, formerly deployed source `ce5c4f5` / Fly v66;
current correction `120b440` / Fly v67. DEBT-083 is Critical / active.
Source qualification and initial deployed identity/health/cycle verification
pass: 3,021 full tests, independent source QA and controlled output/CPU
comparisons are GREEN. The completed concurrent observation is **FAIL_SAMPLE**:
348/356 complete, eight incomplete. Full operational acceptance remains open.

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
| Commit/push/deployed identity | Remote main confirms `120b4408dc0d3eedb241edf26f8f161c062cf126`; Fly v67 capture at `2026-10-26T17:52:51.096640Z` matches all 182 runtime hashes. Public/internal health 200/ok; PIDs 652/653. |
| Deployment settings | `operations/deployment-verification.json` confirms dependencies, configuration, guest and volume unchanged: existing machine, one shared CPU / 2048 MiB, `/data`, paper/Codex and 1,800-second cadence. |
| Initial natural cycle | `17:52:18.752809Z`–`17:52:37.908691Z` on October 26 UTC: 19.155882 s, twelve monitor passes, zero errors and zero proposals. It precedes the new observation and cannot satisfy that observation's full-cycle gate. |
| Trading evidence boundary | No actual proposal/cap-event rows. Separate pure method replay: eighteen score rows / twelve accounts all match; eleven monitorable legacy trade cap rows; twenty-four input hashes unchanged during replay. Fixed confidence, omitted proposal joins and unknown market marks prevent emitted-proposal coverage claims; actual funding remains unknown. |
| Readiness has not been declared | V67 is FAIL_SAMPLE: 348 complete plus eight incomplete among 356 matched requests; health and the full natural cycle pass independently. Existing v66 failure is retained. |

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
`/private/tmp/crypto-master-cpu-cost-delivery-20261027/`. Initial deployed evidence
is retained in `operations/postdeploy.json`; the lead retains the final
operational package separately from source qualification.
Image digest is
`sha256:2aa60d27cf4aed283b9e4596e17cf3403f39b88794b3347f5abeb40462700382`,
machine `6835752b711958`, instance `01M5WNEGCGSRY9CE34VRT7K6X3`.

## Final v67 observation cross-check

Independent QA covers `2026-10-26T17:54:18.225469Z`–`18:23:52.497955Z`,
1,774.272486 s. All 356 starts/outcomes are bijective, with no duplicates,
classification errors or summary differences. The eight unsuccessful outcomes
are preserved; passing successful-response percentiles do not change the verdict.

| Gate | Evidence / verdict |
|---|---|
| Complete pages | **FAIL_SAMPLE**. Home 174/178, Trading 174/178; four incomplete per page. Complete-only p95 0.576250 / 0.487714 s; all-outcome terminal-time p95 0.682332 / 1.026017 s, not latency-to-complete for unsuccessful outcomes. |
| Health | PASS for this window: 352/352 checks, maximum 0.661728 s. |
| Natural engine cycle | PASS for this window: cycle `54425221-0b58-4c65-bbec-573474aa4d00`, `18:22:37.998358Z`–`18:23:12.286517Z`, 34.288159 s, twelve monitors, zero errors and zero proposals. No forced cycle. |
| Warm-up | FAIL: Home complete 12.956247 s; first incomplete-shell receipt 5.507020 s. Native rendering and twenty-sample cold acceptance remain unqualified. |
| Memory | Observed guest peak 663.171875 MiB, dashboard RSS growth 31.578125 MiB, on current 2048 MiB. Original 1024 MiB gate remains unqualified. |
| CPU history supplement | 118 in-window samples per series at fifteen-second spacing, five of 123 values excluded; bracket `17:54:15Z`/`18:24:00Z`. Balance 932.0077104–4031.0047002 centiseconds; baseline 0.0625 CPU units; throttle counter/deltas zero. No sampled depletion, hence no depleted-CPU pass. |
| Final source/service continuity | `18:24:40.539128Z`: all 182 hashes match, same image/instance/PIDs and public/internal 200. This post-window check does not convert incomplete requests into successes. |

The first four failures carry activity-stale alerts and zero watchers. The
next four end with snapshots-unavailable after 17.282–18.581 s, at most one
watcher and two rerun registrations each. They are neither timeouts nor
guard-aborted outcomes. Diagnostic capture has 566 rows / 555 in-window and
zero parse/schema failures; asynchronous, rate-limited delivery without request
identity prevents exact event-to-request attribution. A natural-cycle overlap
is evidence of timing, not proof of an exclusive cause.

The initial immutable summary's CPU-incomplete flag is superseded only for
sampled coverage by separate `cpu-window-proof.json` and
`cpu-counter-interpretation.json`; its FAIL_SAMPLE is unchanged. CPU publication
is `18:24:29.552468Z`, after the window, not a claimed query start. Zero sampled
counter deltas do not exclude shorter unsampled transients. These supplements
add no production load. Frozen evidence is retained under
`aidlc-docs/construction/dashboard-operator-ui/code/cpu-cost-20261027/operations/qa-ops-v67/`,
with final runtime identity and continuity in sibling `operations/postrun.json`
and `operations/postrun-comparison.json`. The separate
`operations/residual-analysis/findings.md` records `source_changed` failures and
terminal-policy behavior consistent with activity stale and snapshot
unavailable outcomes. It preserves cache-age/source-validation limits and does
not identify an exact writer, verification branch or per-job time allocation.
Finite coalesced recovery is a follow-up candidate, not a shipped change.

## Original acceptance remains independent

| Requirement / historical result | Current status |
|---|---|
| V66 four-session observation | **FAIL_SAMPLE**: 356 matched / 352 complete / four guard-aborted; health 5.219426 s timeout; full cycle ends outside the 1,800.914084 s window. Failures remain counted. |
| V66 warm-up | Home 10.777154 s complete and 5.069114 s first incomplete-shell receipt exceed five seconds. One warm-up is not a twenty-sample cold qualification. |
| CPU evidence interpretation | **V66:** observed throttle increase overlaps its failed period. **V67:** the sampled throttle counter and deltas remain zero. Neither this comparison nor the local hotspot proves the exact failing function or sole cause. Successful depleted-CPU qualification remains open. |
| Cold / warm complete-page targets | Cold p95 ≤5 s / warm p95 ≤2 s, at least twenty samples per required page/scenario; failures retained. Cacheless queries, seeded reuse and process-cold starts are separate conditions. Pending. |
| Native rendering | Protocol messages and local execution do not certify native browser/viewport acceptance. Pending. |
| Concurrent sessions / natural cycle | V67 captures four sessions for 1,774.272486 s, one full cycle and healthy service, but eight incomplete pages fail the combined sample. |
| Memory / original capacity | Dashboard growth ≤256 MiB; guest use ≤768 MiB on declared 1024 MiB. Current 2048 MiB observations do not qualify the original capacity. Pending. |
| Protected runtime behavior | One worker/four admitted jobs, bounded state, four-second foreground wait, two-second complete freshness, thirty-second explicit stale fallback, generation proof and manual terminal retry remain required. |

The [session](../sessions/2026-10-27-dashboard-cpu-cost.md) separates this
diagnosis from historical v64/v65/v66 outcomes. Local evidence qualifies this
bounded source correction; it does not close DEBT-083 or authorize
capacity, cadence, credential, cost or trading-policy changes.

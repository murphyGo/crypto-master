# Dashboard page-dependent progress cross-check — 2026-10-27 KST

Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
Baseline main `37b29d7`, previous runtime `382c26b` / Fly v65;
new deployed source `ce5c4f5` / Fly v66.
Requirements: BDL-NFR-03/04/06/07/08; FR-029/031/032/036/042;
NFR-003/007/008/011/012; US-012/014/020/023.

**Bounded correction deployed:** source gate, remote push, v66 source/health
and first-natural-cycle checks pass. Final four-session observation is
`FAIL_SAMPLE`: 352/356 complete, four guard-aborted requests, a failed health
sample and no full cycle captured inside its window. Warm-up Home misses both
5 s targets. Full DEBT-083 acceptance remains open.

| Contract | Design / verification obligation | Current disposition |
|---|---|---|
| Relevant completion wakes this page | A completed dependency must be observable while unrelated work is active; retain one page watcher. | Baseline behavioral failure becomes a pass in `test_page_ready_while_unrelated_job_blocks_reruns_once`; actual two-session Streamlit smoke and independent QA pass. |
| Queue-full recovery | Pure probe notices relevant coalesced work, completed state or valid admission opportunity without admitting work itself. | Free-slot baseline failure becomes a pass; targeted tests cover same-query admission at four occupied slots and fresh-result/root gates without poll mutation. |
| Exact attempt identity | Capture compact signal before waiting; settlement/replacement cannot switch a timeout handle to a later generation. Separate sessions do not consume shared completion. | Original-generation race and shared-generation/latch tests pass; independent source review is GREEN. |
| Shutdown and ownership | Active/queued attempts are notified on close without waiting for a slow builder; retired page handles retain no future/payload/cache. Queue probe holds only a weak service reference and bounded normalized query. | Targeted close, evicted-payload/Future GC and weak-service ownership tests pass. |
| BDL-NFR-06: bounded work/state | One worker/four admissions remain; at most sixteen probes per render, one latch/watcher and bounded legacy fallback. No extra scheduler/thread, poll-side IO/admission or cardinality growth. | Focused bounds/coalescing/side-effect tests pass; logical bounds are not measured RSS acceptance. |
| BDL-NFR-07/08: meaning and failure | Settled attempt is not verified success. Normal request retains generation proof, four-second foreground deadline, two-second complete freshness and thirty-second explicit stale fallback. Terminal retry stays manual. | Focused expiry and retained availability/service/diagnostic tests pass; expired siblings are not pinned complete. Final full regression passes 3,008 tests. |
| Compatibility/privacy | Optional nonserialized probe defaults to None, excluded from repr/equality; missing/excess probes cannot suppress known relevant progress. No path/query identifiers in diagnostics. | Targeted legacy fallback, probe-cap/dedup and mixed-result tests pass. |
| Fragment absence | Existing manual control remains, without duplicate retry buttons. | Existing fragment-absent mixed-terminal test passes in the focused gate; native rendering remains unqualified. |
| BDL-NFR-03/04: page/resource acceptance | Original complete-page, shell, concurrency, engine and memory targets remain. | v66 `FAIL_SAMPLE`: 356 matched requests, 352 complete and four guard-aborted. Home/Trading each 176/178; successful p95 0.726289/0.703791 s cannot hide failures. Previous v65 remains `FAIL_SAMPLE`. |
| Deployment identity | Exact validated source, unchanged capacity/config/dependencies/volume. | Remote main `ce5c4f5`, Fly v66, all 182 runtime hashes match; public/internal health 200/ok. |
| First natural cycle | Existing cadence and monitoring, independent of page-readiness acceptance. | 16:38:08.677457–16:38:35.739136 UTC, twelve monitors, zero recorded errors, three upstream accepted proposals, one later rejection and two opened paper positions. |
| Warm-up | Preserve first-shell and complete timings even if subsequent responses improve. | Home 10.777154 s complete / 5.069114 s first incomplete receipt miss 5 s; Trading 0.975259 s. Single warm-up is not cold p95/native qualification. |
| Measured health/continuity | Every health sample <5 s and one complete natural cycle within the observation window. | Failed: final of 353 health checks reports `TimeoutError` after 5.219426 s; no full cycle completes inside 16:39:23.994031–17:09:24.908115 UTC. |
| Observed memory subset | Keep current-allocation measurements separate from original guest qualification. | RSS growth 67.394531 MiB, HWM increase 67.714844 MiB, guest peak 694.718750 MiB on 2048 MiB only. |

## Preserved evidence and causal scope

The controlled baseline probe demonstrates that a page's complete activity
result can wait through twenty polls for unrelated audit work to drain. This
justifies the bounded page-progress correction, but does not prove it caused
every production timeout or that removing it will meet all readiness targets.

The v65 production result remains **116/120 complete, four timeouts**, two per
page, in 607.100718 s. Its successful-response p95 (Home 1.852226 s, Trading
1.396472 s), healthy endpoints and full natural cycle do not change the failed
sample. Current 2048 MiB resource observations do not qualify original 1024 MiB
requirements. Historical v64's two incomplete Home outcomes are also retained.

Seven v65 `source_changed` diagnostic records were asynchronous delivery events,
not seven failed pages or request-specific causality. The separate valid-append
probe demonstrates correct verification rejection, and the expiry probe shows
why a result older than two seconds cannot stay marked complete while waiting
for another section. Neither rule is relaxed by page-progress notification.

## Source evidence and pending operational gates

Developer evidence records two baseline behavioral failures in 0.35 s, then
both behaviors passing in 0.32 s. The final focused run passes **67 tests in
2.52 s**, including nineteen page-progress cases, on Python 3.13.0. Black/Ruff
pass six initial changed files and mypy the three changed source files. Exact
commands and hashes are retained in `developer-verification.json` under
`aidlc-docs/construction/dashboard-operator-ui/code/page-progress-20261027/`.

`qa-fragment-smoke-result.json` is PASS on actual local Streamlit AppTest:
two sessions independently execute their captured fragment and rerender from
pending to complete after the shared activity event, while an unrelated audit
job remains admitted. Event/PageProgress argument capture works; each old
fragment's second dispatch returns through its latch. Both reads build once,
one worker remains, source hashes are unchanged and no exception is recorded.
This dispatch is explicit, not a browser timer or native viewport measurement.

Final independent QA is **GREEN across 77 distinct cases**, including ten
bounded-page follow-up cases. The first full run had **3 failures and 3,005
passes in 221.80 s** because its watcher mock still accepted only one argument.
Changing that test-only signature to accept optional `progress=None` preserves
all page/one-watcher assertions. The three runtime hashes remain unchanged;
the original failed iteration is retained, and the combined focused follow-up
passes 77 in 3.30 s.

The final exact-source command
`/Users/user/Desktop/Projects/crypto-master/.venv/bin/python -m pytest -q`
passes **3,008 tests in 231.58 s on Python 3.13.0**, with all **261 input hashes
unchanged** during the run. Final Black/Ruff pass seven changed Python files;
`mypy src --cache-dir /private/tmp/crypto-master-page-progress-delivery-20261027/mypy-final-cache`
passes all 135 source files using the same root interpreter. Evidence:
`source-qualification.json`, `source-input-sha256.json`, `full-pytest.txt`,
`mypy-final.json`, `qa-source-verdict.json`, `qa-page-fixture-followup.json`
and the separately preserved initial iteration. Commit/deployment are complete;
the measured production-readiness sample fails.

The authorized rollout retains machine `6835752b711958`, shared CPU 1 / 2048 MiB,
volume, dependencies, paper/Codex settings and cadence. Deployed source
`ce5c4f5eb71a1954ec264c0380eaa7e5c4b0742d` has image
`sha256:d9a234ff67bd9dd6b1fc1ea76cb1f302c049e677019ae8a388db7179e4c91709`,
instance `01M5WH6PXMT865Y5XEDDWETVA0`. The 16:38:36.531715 UTC post-deploy
capture and `operations/deployment-verification.json` retain identity/config
checks. The final observer reconciles every request but fails readiness/health
and the full-cycle-in-window requirement; deployment checks do not replace them.

Actual checks cover three proposals across MA `1.0.0` (one; prior sample 227,
expected value -0.3738099982477091) and Raschke `1.0.0` (two; sample 266,
expected value 0.00931627480353263). All sample/expected-value fields match;
one final symbol-cap rejection and two opens are distinct from upstream
acceptance. The single matching cap row has null account/no proposal ID and
does not prove all-account/proposal cap coverage. Separate pure replay covers
eighteen score rows/twelve accounts and eleven cap trades, with twenty-four
input hashes unchanged only across that read-only replay; do not equate it
with emitted decision coverage.

The independent final audit spans **1,800.914084 s**, with no duplicate/unmatched
request identities or summary differences. Four pages are canceled after
**22.012–23.958 s** following the health sample at **17:09:02.513768 UTC** that
reports `TimeoutError` after **5.219426 s**. These observations are censored by
the guard, not thirty-second request timeouts; eventual completion is unknown.
Their first incomplete receipts arrive in 4.079–4.315 s, with at most one watcher.

The CPU supplement provides full original-window sampled coverage: **120 points
per series / 15 s**, with seven outside points excluded. Positive throttle at
**17:09:00/17:09:15** coincides with low positive balance **1.0000096/0.9868925
raw units**. Do not label this run uniformly buffered/unthrottled or infer exact
causality from overlap. The retrospectively collected history is published at
17:10:34.551347 UTC; successful depleted-load qualification is not established.
`cpu-interpretation-correction.json` expressly qualifies the inherited
buffered-CPU sentence while retaining the original artifact and failed verdict.

The separate **17:10:21.712921 UTC** verifier confirms 182 source hashes,
public/internal 200/ok and stable PIDs **652/653**. The cycle starting
17:08:35.825169 completes only at **17:10:20.751571**, after **104.926402 s**,
with twelve monitors, zero recorded errors and no proposals. Its completion is
outside the observation and cannot retroactively pass that failed cycle/health
gate. No additional production load or resource/config/policy changes follow
from this evidence.

Final supplemental artifacts are separate from the unchanged initial audit.
`diagnostics-functional-supplement.json` validates 560 records, 550 within the
page window, with no parse/schema failure; asynchronous/rate-limited delivery
and absent request identity prevent exact page attribution. Collection has
stopped per `collector-termination-proof.json`; `post-window-recovery.json`
freezes the later continuity proof separately. Artifact completion is not an
operational pass.

`operations/contention-analysis.json` records zero watchers on all 352 complete
requests and at most one watcher per aborted request, with one or two auto-rerun
registrations. No rerender storm is demonstrated. Its pre-cycle dashboard CPU
estimate (6.05% of one core) is during the four-session workload, not idle cost;
process counters and temporal throttle overlap do not identify exact functions
or establish the cause of each failure.

Original qualification still requires >=20 cold and >=20 warm observations per
page/scenario, p95 <=5/2 s complete readiness, separate <=5 s incomplete-shell
timing, four sessions >=10 minutes and a full natural cycle, health <5 s,
dashboard RSS growth <=256 MiB and guest use <=768 MiB on declared 1024 MiB.
Native browser, cacheless/process-cold, depleted CPU and original guest gates
remain open. CPU/cost is deferred. DEBT-083 remains **Critical / active**.

Plan: `aidlc-docs/construction/plans/dashboard-page-progress-plan.md`.
Design: `aidlc-docs/construction/dashboard-operator-ui/code/page-progress-20261027/design.md`.
Prior diagnosis: `aidlc-docs/construction/dashboard-operator-ui/code/home-recovery-20261026/operations/offline-diagnosis.md`.
Session: `docs/sessions/2026-10-27-dashboard-page-progress.md`.

# Dashboard page-dependent progress cross-check — 2026-10-27 KST

Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
Baseline main `37b29d7`, deployed source `382c26b` / Fly v65.
Requirements: BDL-NFR-03/04/06/07/08; FR-029/031/032/036/042;
NFR-003/007/008/011/012; US-012/014/020/023.

**Source qualified:** final regression, source-wide typing, changed-file static
checks, independent QA and actual local Streamlit fragment smoke pass.
Commit/push, rollout and post-change readiness remain next. No production
acceptance is inferred from this source gate.

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
| BDL-NFR-03/04: page/resource acceptance | Original complete-page, shell, concurrency, engine and memory targets remain. | New measured result pending; previous v65 remains `FAIL_SAMPLE`. |

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
and the separately preserved initial iteration. Commit/deployment and
production-readiness evidence remain pending.

After the validated source is committed/pushed, the authorized rollout must
preserve the machine, capacity, volume, dependencies, paper/Codex settings and
engine cadence. Verify the exact deployed hashes and run one fresh protocol
observation across a full natural cycle. Keep warm-up, every request outcome,
health/memory/CPU scope and original failures explicit; do not manufacture a
pass by forcing a cycle or excluding timeout samples.

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

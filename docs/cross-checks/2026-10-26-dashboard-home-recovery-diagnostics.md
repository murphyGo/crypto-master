# Dashboard Home recovery cross-check — 2026-10-26 KST

Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
Scope: approved bounded Home recovery/diagnostic correction on `5fcad54`, with
production application baseline `dca38fb` / Fly v64. Requirements:
BDL-NFR-03/04/06/07/08; FR-029/031/032/036/042;
NFR-003/007/008/011/012; US-012/014/020/023.
Concurrent documentation parent `f1863de` is integrated with runtime source
unchanged.

**Source gate passed:** independent QA, final regression and static checks are
complete. Commit/push, rollout and operational qualification remain next.
This document does not certify deployed recovery or debt closure.

| Contract | Current evidence / disposition |
|---|---|
| Queue-full recovery | `availability.py` treats unavailable/stale `queue_full` as retryable and retains one page watcher. `test_five_home_queries_queue_full_release_and_watcher_coalescing` reproduces five queries, four admissions and one worker, then confirms recovery after release. |
| Explicit terminal retry | One page-level `Refresh data` control invokes captured terminal callbacks. `test_home_cached_source_failure_manual_retry_preserves_healthy_data_and_age` verifies failed activity/snapshot recovery with healthy siblings and ages preserved. Terminal failures do not register an automatic rebuild loop. |
| Retry identity/concurrency | `test_stale_retry_callback_cannot_clear_new_failure_or_other_query` and `test_concurrent_explicit_retries_coalesce_one_new_read` verify generation-specific invalidation and normal single-worker coalescing. Callback is excluded from `ReadResult` representation/equality and is not serialized into encoded payloads. |
| BDL-NFR-06: resource caps | Existing worker/admission/cache/result/state/manifest/identity/account/strategy/root/foreground-wait constants are unchanged. Diagnostic history/rate keys are capped at 64 each; one daemon has 64 queued records plus one active event, drops overflow and does not wait on a stalled sink. |
| Diagnostic privacy and failure isolation | Finite kind/status/reason/stage values, sanitized age/admission only; unknown inputs become `unknown`. No paths, identities, raw payloads, exception strings or runtime files. Tests cover sanitization, rate/cardinality, blocked/raising sinks, shared drain and worker outcomes. |
| BDL-NFR-07/08: meaning and coverage | Verified siblings keep their payload/evaluation age. Retry does not bypass validation, modify trading math or claim incomplete/stale data is complete. Existing source-proof/reader behavior remains; final regression passes 2,989 tests. |
| Observer completeness | Exact expected labels, nonplaceholder metrics, element counts and no incomplete alert are required. Every request outcome and warm-up is retained; fresh output directory prevents appending old evidence. Classification/first-shell timings are sanitized. This does not verify individual table-cell values or native presentation. |
| Observer engine continuity | Full-cycle qualification requires `window start <= cycle start <= cycle completion <= window end`, including the live stop check. First complete natural cycle remains evidence even if errored; any recorded in-window cycle error makes continuity fail. Tests reject pre-window/future/inverted cycles and prevent a later clean cycle from hiding an earlier error. Engine cadence is unchanged. |
| BDL-NFR-03/04: historical failure accounting | Offline replay exactly preserves 347/349 complete and two failed Home requests; zero classification differences, starts/outcomes bijective, aggregate readiness false despite successful-response p95 <2 s. This is a harness regression check, not post-fix operational evidence. |
| BDL-NFR-02/03/04 and broader qualification | Original cold/native/depleted/1024 MiB requirements remain open. No current 2048 MiB result or protocol-only run waives them. |

## Evidence and outstanding gates

The retained red/green record shows three expected failures before source edits
and all three passing afterward with the same test selection. The developer's
focused suite passes **48 tests in 4.69 s** on Python 3.11.13 and four changed
source files pass mypy. Exact commands and results are captured in
`source-red-green.json` / `.txt`.

Independent QA is **green across 106 distinct cases**: initial 101 plus five
observation-window cases. Its final exact observer gate passes **48 tests in
0.18 s**, following the developer's 48-case / 0.23 s gate. CLI `--help` and
changed-two-file Black/Ruff also pass. Import-safety,
privacy, partial/exception/cancellation preservation, pending-to-complete
reruns, identity reconciliation, errored cycles and output reuse rejection are
covered. QA's observation-window finding is corrected with four invalid-time
cases and inclusive-boundary coverage. The production sampler literal is
unchanged from the committed driver.

The final full suite passes **2,989 tests in 224.06 s on Python 3.13.0** with
all 260 `src`/`tests`/`scripts` hashes unchanged during the run. Black/Ruff pass
for nine changed Python files and mypy for 135 source files. An earlier Python
3.11.13 run passed 2,984 tests in 61.06 s before the five observer boundary
tests; it is supplementary, not the final exact-source gate.

Evidence is retained under
`aidlc-docs/construction/dashboard-operator-ui/code/home-recovery-20261026/`:
`source-qualification.json`, `source-input-sha256.json`,
`full-pytest-final.txt`, `independent-qa.json` and `source-red-green.json` / `.txt`.

The replay reads the prior immutable
`qualification-continuation-20261026/concurrency-audit/frozen/raw/` artifacts:
Home completes 172/174 (successful p95 0.760711 s); Trading 175/175
(0.724168 s). All 349 request identities match exactly. No new production
workload or Fly call was made for that replay.

The historical two Home failures remain **cause unknown**. Deterministic
reproduction establishes two code defects, not incident attribution. The new
diagnostics are best effort and may drop delivery under saturation; absence of
a diagnostic alone must not be presented as absence of a read failure.

Before deployment, capture the exact validated remote commit and recheck
concurrent production identity. The same-capacity recipe then requires deployed source hashes,
health/process/configuration checks, a full natural engine cycle and one
enhanced four-session observation. Preserve all failures and the first-shell
measurement; do not force cycles or alter budgets to obtain a pass.

The original acceptance matrix still requires >=20 cold and >=20 warm
observations per page/scenario, complete readiness p95 <=5/2 s, separate
incomplete-shell <=5 s evidence, four sessions for >=10 minutes plus a full
natural cycle, health <5 s, dashboard RSS increase <=256 MiB and guest use
<=768 MiB on a declared 1024 MiB allocation. Cacheless cold and restarted
process/import time remain distinct from seeded reuse. Native/depleted
qualification and the deferred CPU/cost decision are unchanged.

DEBT-083 remains **Critical / active**. No new strategy defect or performance
optimization is introduced in this bounded correction.

Plan: `aidlc-docs/construction/plans/dashboard-home-recovery-diagnostics-plan.md`.
Design: `aidlc-docs/construction/dashboard-operator-ui/code/home-recovery-20261026/design.md`.
Session: `docs/sessions/2026-10-26-dashboard-home-recovery-diagnostics.md`.

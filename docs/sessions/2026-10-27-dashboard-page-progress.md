# Dashboard page-dependent progress — 2026-10-27 KST

Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
DEBT-083 remains Critical / active. Baseline main is `37b29d7`; deployed source
is `382c26b` / Fly v65. Work is isolated in
`/private/tmp/crypto-master-page-progress-20261027`, preserving unrelated root
and worktree changes. The user's `고칠 수 있음?` continues the registered
correction; earlier sequential commit/push and same-capacity rollout authority
persists.

**Source qualified:** three source files and four test files pass final
regression, static checks, independent QA and the actual local Streamlit
two-session fragment check. Commit/push, deployment and operational observation
are next; no production recovery claim follows from this local source gate.

## Evidence motivating the correction

On v65, the page watcher reruns only when the process-wide service has no
admitted jobs. The prior controlled probe completes this page's activity query
while an unrelated audit job remains blocked: twenty watcher polls produce no
rerun, then finishing the unrelated job produces one. This establishes a
specific dependency on unrelated work without assuming CPU pressure or source
mutation.

It does not establish the sole cause of the production failures. The v65
607.100718 s observation retains **120 matched requests, 116 complete and four
timeouts**, two per page. Successful p95 is Home 1.852226 s / Trading 1.396472 s;
failures prevent acceptance. All 120 health checks and the full natural cycle
pass, with observed guest use 701.949219 MiB and dashboard growth 65.648438 MiB
on the current 2048 MiB machine. The next requests recover, so indefinite live
starvation is not proven. Prior v64's two incomplete Home responses also remain
failed historical observations.

The v65 diagnostics identify verification failures but have asynchronous,
rate-limited delivery and no request identity. Correct source-generation
rejection and required two-second freshness revalidation are separate from the
watcher dependency. The exact relationship between those paths and each timeout
remains unresolved.

## Bounded design and ownership

The implementation lets the existing watcher notice this page's relevant
read completion or queue-admission opportunity. A progress signal means an
attempt settled; normal rendering still fetches and classifies its result.
It is not proof that the data is complete or fresh.

- `read_models.py`: optional private progress probe on `ReadResult`, excluded
  from representation/equality and never encoded into payloads or diagnostics;
  existing callers default to no probe. Explicit terminal retry stays separate.
- `data_service.py`: compact per-job completion signals captured before waiting
  preserve the original attempt across timeout/completion and same-query
  replacement races. At most four jobs/signals are service-owned. Retired
  handles must not retain futures, payloads or caches. Queue-full probes use a
  weak service reference and the already normalized query, without IO,
  normalization, admission, error clearing or age mutation during polling.
- `availability.py`: one watcher aggregates at most sixteen deduplicated probes
  per render. A per-render latch avoids repeat notification; different sessions
  observe shared job completion independently. Missing/excess legacy probes
  retain one conservative global-drain fallback without hiding known progress.

Targeted tests cover settlement/close, stale-generation callbacks, queue
opportunity, eviction and garbage collection. The change introduces
no worker, scheduler, runtime-data write, dependency, API cost, resource/config
change or trading interpretation. One worker, four admitted jobs, one watcher,
four-second foreground wait, two-second complete freshness and thirty-second
explicitly stale fallback remain. Terminal failures still require explicit
manual retry; polling cannot trigger rebuilds or bypass verification.

The developer owns only the three runtime files and targeted tests. Independent
QA reviews the implementation and evidence. The lead owns plan/design/state/
debt, integration and operations; this documentation slice owns only the new
session and cross-check.

## Verification checkpoint

| Gate | Status and required evidence |
|---|---|
| Design review | GREEN recorded in the current plan; compact signals, bounded page probes and nonmutating readiness are implementation obligations. |
| Baseline regression | Two behavioral cases fail on baseline in 0.35 s, then the same behaviors pass in 0.32 s: page completion while unrelated work blocks, and queue-full page noticing a free slot before global drain. |
| Targeted tests | 67 passed in 2.52 s on Python 3.13.0, including nineteen progress cases; availability/service/diagnostic regression is included. |
| Independent source QA | GREEN across 77 distinct targeted cases: initial 67 plus ten bounded-page follow-up cases. No remaining source/fixture blocker; actual fragment smoke also passes. |
| Actual Streamlit fragment interaction | PASS: two independent AppTest sessions dispatch their captured fragment after shared activity completes while unrelated audit work remains admitted. Both rerender to complete; old-fragment redispatch returns without another fragment-induced rerun. No exception or extra read build. Explicit closure dispatch does not certify browser timer/native rendering. |
| Final static gate | Black/Ruff pass seven changed Python files; source-wide mypy passes 135 files. Earlier three-source-file typing remains supplementary. |
| Final full regression | 3,008 passed in 231.58 s on Python 3.13.0, using `/Users/user/Desktop/Projects/crypto-master/.venv/bin/python -m pytest -q`. All 261 `src`/`tests`/`scripts` hashes remain unchanged during the final run. |
| Commit/push and rollout | Pending: confirm validated remote SHA, preserve concurrent work, use existing configuration. |
| Operational observation | Pending: deployed hashes/health, one fresh four-session run spanning a full natural cycle, all outcomes retained, independent final audit. No forced cycle or overlapping observers. |

The focused command is the existing root `.venv/bin/python -m pytest
tests/test_dashboard_page_progress.py tests/test_dashboard_availability.py
tests/test_dashboard_data_service.py tests/test_dashboard_read_diagnostics.py -q`.
`developer-verification.json` retains exact commands, the two-case baseline
failure, behavioral retest and initial six-file hashes. Final evidence is
retained under `aidlc-docs/construction/dashboard-operator-ui/code/page-progress-20261027/`:
`source-qualification.json`, `source-input-sha256.json`, `full-pytest.txt`,
`mypy-final.json`, `qa-source-verdict.json` and the fixture follow-up artifacts.

The first full iteration records **3 failed / 3,005 passed in 221.80 s**. Its
old bounded-page watcher mock accepted one argument and rejected the new
optional progress argument. Only that test mock changed to accept
`progress=None`; section messages and one-watcher assertions remain intact.
The three runtime source hashes stayed unchanged throughout. Independent QA
passes the ten bounded-page cases, and the developer's combined follow-up
passes 77 cases in 3.30 s. The initial failed output and qualification manifest
are retained separately; the final 3,008-test result covers the corrected test
fixture and exact frozen source.

`qa-fragment-smoke-result.json` checks real Streamlit fragment registration,
Event/PageProgress argument capture, `st.rerun` and session separation. Each
session starts with one pending fragment and reaches a complete `Ready=7`
display after one dispatched relevant-completion signal. The service still has
one unrelated admitted job and one worker; activity/audit each build once.
Redispatching each old fragment returns normally through its local latch. The
three source hashes are unchanged before/after. This is controlled local
interaction evidence, not timer scheduling, page latency or production proof.

## Acceptance boundaries

The original complete Home/Trading p95 targets remain <=5 s cold and <=2 s warm
with >=20 observations per page/scenario. Every timeout/incomplete result remains
in the denominator; the separate incomplete-shell target is <=5 s. Cacheless
construction and process restart/import time remain distinct from seeded reuse.

Four sessions must run >=10 minutes across a full natural cycle, with every
sampled health response <5 s. Dashboard RSS growth <=256 MiB and guest use
<=768 MiB on a declared 1024 MiB allocation remain required. Current 2048 MiB
measurements do not qualify the original allocation. Cold/native/depleted/
original-guest gates and CPU/cost deferral remain open; this source correction
cannot close them by itself.

Plan: `aidlc-docs/construction/plans/dashboard-page-progress-plan.md`.
Design: `aidlc-docs/construction/dashboard-operator-ui/code/page-progress-20261027/design.md`.
Prior evidence: `aidlc-docs/construction/dashboard-operator-ui/code/home-recovery-20261026/operations/`.
Cross-check: `docs/cross-checks/2026-10-27-dashboard-page-progress.md`.

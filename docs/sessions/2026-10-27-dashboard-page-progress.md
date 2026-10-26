# Dashboard page-dependent progress — 2026-10-27 KST

Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
DEBT-083 remains Critical / active. Baseline main is `37b29d7`, previously
deployed source `382c26b` / Fly v65; the correction is now `ce5c4f5` / Fly v66.
Work is isolated in
`/private/tmp/crypto-master-page-progress-20261027`, preserving unrelated root
and worktree changes. The user's `고칠 수 있음?` continues the registered
correction; earlier sequential commit/push and same-capacity rollout authority
persists.

**Bounded correction deployed:** qualified source `ce5c4f5` is confirmed on
remote main and Fly v66. Source hashes, unchanged configuration and the first
natural cycle pass verification. The four-session observation is `FAIL_SAMPLE`:
352/356 complete, four requests aborted after a health guard, and no full
natural cycle captured within the observation window. Warm-up Home also misses
both 5 s targets. DEBT-083 remains Critical / active.

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
| Commit/push and rollout | `ce5c4f5eb71a1954ec264c0380eaa7e5c4b0742d` confirmed on remote main; deployed as Fly v66, with local main fast-forwarded. |
| Initial deployed verification | All 182 runtime hashes match; dependencies, configuration, guest and volume unchanged; public/internal health 200/ok. First natural cycle completes with twelve monitors and zero recorded errors. |
| Four-session observation | `FAIL_SAMPLE`: 1,800.914084 s, 356 matched starts/outcomes, 352 complete and four `aborted_after_guard_stop`; health guard fires and no full cycle completes inside the window. Warm-up Home 10.777154 s / first shell 5.069114 s remain misses. |

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

## Deployment checkpoint and measured scope

Fly v66 runs source `ce5c4f5eb71a1954ec264c0380eaa7e5c4b0742d`, image
`sha256:d9a234ff67bd9dd6b1fc1ea76cb1f302c049e677019ae8a388db7179e4c91709`,
instance `01M5WH6PXMT865Y5XEDDWETVA0` on existing machine `6835752b711958`.
The existing shared CPU 1 / 2048 MiB, `/data` volume, installed dependencies,
paper/Codex configuration and 1800-second cadence are unchanged. The
16:38:36.531715 UTC capture verifies 182 runtime hashes and 200/ok public/internal
health. Evidence: `operations/postdeploy.json` and `deployment-verification.json`.

The first natural cycle spans **2026-10-26 16:38:08.677457–16:38:35.739136 UTC**
(27.061679 s), with twelve monitor events and zero recorded errors. It generates
three proposals, accepts all three upstream, rejects one at a later gate and
opens two paper positions. Upstream acceptance is not execution count.

Actual proposal checks cover two account/version pairs: one `ma_crossover`
`1.0.0` proposal has sample 227 and expected value -0.3738099982477091, ending
`gate_rejected_symbol_cap`; two `raschke_holy_grail` `1.0.0` proposals each have
sample 266 and expected value 0.00931627480353263, ending `trade_opened`. All
sample-size/expected-value comparisons match prior closes. This does not
certify every score field, other accounts or profitability. One cap-event row
matches `legacy_no_perf_link` / `monitorable=true`, but has null account and no
proposal ID, so it does not establish complete proposal-level cap attribution.

Separate pure replay checks eighteen account/version score rows across twelve
accounts and eleven cap trades. All score comparisons match and twenty-four
input hashes remain unchanged across that read-only replay. Its current-data,
fixed-confidence, omitted-proposal-join and unknown-market-mark basis remains
separate from emitted decisions and runtime-wide data immutability.

The observation retains warm-up separately. Home starts at
16:39:04.177676 UTC and completes in **10.777154 s**; first incomplete protocol
receipt is **5.069114 s**, and the first incomplete script finish is 5.956060 s.
Complete readiness and first-shell receipt both miss their 5 s single-sample
targets. Trading then completes in 0.975259 s. These are warm-up observations,
not twenty-sample cold qualification or native visual timing.

## Final v66 operational observation: failed sample

Independent audit reconciles **356 starts and 356 outcomes**, with no duplicate
or unmatched request identities and no summary differences. The window is
**2026-10-26 16:39:23.994031–17:09:24.908115 UTC**, **1,800.914084 s**.
There are **352 complete responses and four `aborted_after_guard_stop`**:

| Page | Complete / attempts | Guard-aborted requests | Successful complete p95 |
|---|---:|---:|---:|
| Home | 176 / 178 | 2 | 0.726289 s |
| Trading | 176 / 178 | 2 | 0.703791 s |

The last of **353 health samples**, timestamped 17:09:02.513768 UTC, reports
`TimeoutError` after **5.219426 s**, triggering `health_failed_or_deadline_exceeded`.
Four in-flight pages are then canceled after **22.012–23.958 s**. These are
guard-censored observations, not completed responses or thirty-second request
timeouts; their eventual completion times are unknown. Their first incomplete
receipts arrive in 4.079–4.315 s, and each retains at most one watcher. Fast
successful-response p95 does not make this failed set pass.

Observed dashboard RSS growth is **67.394531 MiB**, conservative process HWM
minus warmed RSS **67.714844 MiB**, and guest use **694.718750 MiB** on the
current **2048 MiB** machine. Numeric memory ceilings pass this observed subset;
the original 1024 MiB condition remains unqualified. No full natural cycle
completes inside the observation interval, so its continuity gate also fails.

The separate CPU supplement covers the original window with **120 samples per
series at 15 s spacing**, bounded by 16:39:15 and 17:09:30 UTC, excluding seven
out-of-window points per series. Throttle is positive at **17:09:00 and
17:09:15**, when balance is **1.0000096 and 0.9868925 in raw metric units**.
This is observed throttling with low positive balance, not uniformly buffered,
unthrottled execution. Its overlap with the guard failure is correlation, not
an exact cause assignment. The CPU history is published at 17:10:34.551347 UTC,
after the run; sampled coverage does not establish successful depleted-load
qualification or exclude shorter unsampled behavior. The separate
`cpu-interpretation-correction.json` qualifies inherited buffered-CPU wording
without rewriting the original CPU artifacts or `FAIL_SAMPLE` verdict.

A **post-window** verifier at 17:10:21.712921 UTC confirms all 182 source hashes,
200/ok public/internal health and the same engine/dashboard PIDs **652/653**.
The second natural cycle started at 17:08:35.825169 and completed at
**17:10:20.751571 UTC**, lasting **104.926402 s**, with twelve monitors, zero
recorded errors and no proposals. This later continuity result does not
retroactively satisfy the failed observation's full-cycle or health gate.

Final supplements retain the evidence boundaries explicitly:
`diagnostics-functional-supplement.json` contains 560 diagnostic records, 550
inside the page window, with zero parse/schema failures; delivery remains
asynchronous and rate-limited without request identity, so these are not page
failure counts or precise causal assignments. `collector-termination-proof.json`
confirms collection stopped before the final diagnostic freeze.
`post-window-recovery.json` preserves the later health/cycle result separately.
Completing these audit artifacts does not turn the operational sample into a
pass.

`operations/contention-analysis.json` finds zero watchers for all 352 complete
requests; each guard-aborted request has at most one watcher and one or two
auto-rerun registrations. These records do not show a rerender storm. The
pre-cycle dashboard CPU estimate of 6.05% of one core is measured during the
four-session workload, not idle overhead. Simultaneous engine/dashboard demand
and throttling support further bounded diagnosis, without identifying function
costs or the exact cause of an individual failed request.

The deployment/source checks and controlled page-progress regression are valid,
but complete operational readiness remains unproven. Earlier v65/v64 failed
samples stay separate, and this run does not establish a sole timeout cause.
No additional production load, resource/configuration or trading-policy change
is part of this closeout. Detailed audit and post-window evidence are retained
with the task's operational artifacts.

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

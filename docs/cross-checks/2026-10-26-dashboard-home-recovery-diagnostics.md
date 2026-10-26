# Dashboard Home recovery cross-check — 2026-10-26 KST

Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
Scope: approved bounded Home recovery/diagnostic correction on `5fcad54`, from
application baseline `dca38fb` / Fly v64 to deployed `382c26b` / Fly v65. Requirements:
BDL-NFR-03/04/06/07/08; FR-029/031/032/036/042;
NFR-003/007/008/011/012; US-012/014/020/023.
Concurrent documentation parent `f1863de` is integrated with runtime source
unchanged.

**Bounded correction deployed:** independent QA, final source gate, remote push
and v65 source/health checks pass. Final enhanced observation is `FAIL_SAMPLE`:
116/120 requests complete and four time out. Full debt acceptance remains open.

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
| Actual refresh interaction | Temporary-data Streamlit AppTest clicks within 0.061 s of the cached failure; activity rebuilds once and becomes complete, healthy ledger identity/build count is preserved, subsequent rendering causes no additional build or exception. AppTest stale-button behavior is also reproduced without application code; native DOM/viewport acceptance is not inferred. |
| Exact deployed source/configuration | Remote main `382c26b` is Fly v65, image `sha256:6a621b4d7ee3427c47251a4d833c0754679a0b73bba7b9f388e3c7cdfae42200`. All 182 runtime hashes match at 04:55:19 UTC; existing machine, shared CPU 1 / 2048 MiB, volume, dependencies, paper/Codex and cadence are retained. |
| Post-deployment runtime observation | Later 04:55:19 UTC check reports 200/ok public/internal health, five completed cycles and 60 monitor events with zero recorded errors since 02:28 UTC. Runtime began around 02:29 UTC; this is not an immediate deployment sample. |
| Enhanced four-session protocol | `FAIL_SAMPLE`: 04:56:43.681997–05:06:50.782715 UTC (607.100718 s); 120 matched starts/outcomes, 116 complete and four timeouts, two per page. No duplicate/orphan identities or summary differences. Successful p95 Home/Trading 1.852226/1.396472 s does not erase failures. |
| Observed resource/continuity subset | 120 health checks pass, maximum 4.001187 s. Guest peak 701.949219 MiB; dashboard growth 65.648438 MiB on current 2048 MiB. Natural cycle 05:01:34.008593–05:02:04.252059 UTC lasts 30.243466 s with twelve monitors and zero recorded errors. |
| Warm-up / incomplete shell | Home warm-up completes in 11.414767 s and first incomplete receipt is 5.072113 s: both single-sample 5 s targets missed. The four tracked failures receive shells in 4.307–4.794 s. Protocol receipt is not native rendering; one warm-up is not cold p95 qualification. |
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

Operations artifacts are retained in the evidence directory's `operations/`:
candidate/deployment manifest, source/health/runtime capture and local AppTest
scripts/results. The exact source is pushed and deployed; independent final
protocol audit and its diagnostic supplement preserve every failure and
first-shell measurement without forcing cycles or changing budgets.

The post-deployment capture verifies sample-size/expected-value fields for
thirteen actual proposals: MA `1.0.0` four (226 prior closes), RSI 15m `1.1.0`
five (227), VWAP mean-reversion `1.1.1` four (190). Every comparison matches;
final states are twelve symbol-cap rejections and one opened trade. Thirteen
accepted events are not thirteen executions or universal score-field coverage.
Twelve matching cap-event rows cover six trades; their account values are null
and proposal IDs are absent, limiting event attribution.

Separate pure replay checks eighteen account/version score rows across twelve
accounts and eleven cap trades, with all score comparisons matching and twenty-
four input hashes unchanged across the read-only replay. It uses current inputs,
fixed confidence, omitted proposal joins and unknown market marks; do not call
it emitted decision coverage or runtime-wide data immutability. Actual funding
remains unknown/null; MA's complete 226-trade hypothetical carry inputs and
10,000 USDT rendering assumption are not measured funding or current returns.

In the final protocol window, the distinct actual proposal is
`session_vwap_pullback` / `1.1.0`, ID `882b0872-3c7e-474f-a5e3-43b8927c8c0a`:
prior sample 47 and expected value 1.529362657442265 match, final state
`gate_rejected_trend_filter`. There are no cap-event rows in this later window;
do not merge it with the earlier thirteen-proposal/twelve-cap-event coverage.

Each page completes 58/60 attempts (96.67%). Supplementary all-outcome duration
p95 is Home 2.369965 s / Trading 2.055165 s; the successful-only p95 cannot
certify a failing sample. The four 30.044–30.261 s timeouts overlap the natural
cycle. Their next requests complete in 1.317–3.262 s, so indefinite starvation
is not established. Previous v64 failures remain separate historical evidence.

The framed diagnostic supplement validates 169 records, including seven
`source_changed` (four projection, three error-cache). These are asynchronous
delivery records without request/query identity, rate-limited and potentially
dropped, collected after the page window began. They are not seven failed
pages or precise failure timestamps. The initial empty collector decoded no
multiline Fly objects and cannot prove diagnostic absence.

Offline source-preserving probes confirm a watcher waiting for global job drain
can delay an otherwise ready page behind unrelated work. They also confirm
required two-second freshness revalidation and fail-closed generation checks
under valid appends. Global-drain coupling is a concrete follow-up candidate,
not a demonstrated sole cause of these timeouts. No source-proof bypass,
expired-as-complete shortcut or resource change is authorized by this evidence.
The later CPU supplement is independently audited over the original window:
41 points per series at 15 s spacing, 04:56:45–05:06:45 UTC, bracketed by
04:56:30/05:07:00 with no gaps/duplicates. It excludes 470 earlier/later values
per series. Balance stays positive (raw metric 41,601.002–45,501.002), sampled
throttle is zero and baseline 0.0625. The historical query result was published
locally at 07:03:47.085509 UTC; this is not a contemporaneous capture or query-
start timestamp. Sampled coverage does not rule out shorter transients or
qualify depleted CPU, and does not change `FAIL_SAMPLE` or establish causality.

`operations/closeout-current.json` at 07:04:35.888616 UTC confirms unchanged
182 hashes/image/instance/configuration and 200/ok health, plus four later
cycles/48 monitors/zero errors, one time-stop close and no proposals since
05:06:51 UTC; this later continuity check is outside the failed performance
window and cannot convert it to a pass.

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

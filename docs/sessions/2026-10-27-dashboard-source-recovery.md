# Dashboard source-generation recovery — 2026-10-27 KST

> **Final checkpoint — 2026-10-28 KST:** Source `7b87d9a` is committed/pushed
> and deployed as v68, with182runtime hashes and unchanged configuration verified.
> User requested stop/wrap-up. Observer and collector are stopped; exact remote
> sampler is absent. Partial raw16/16complete is not readiness acceptance: no
> full cycle/minimum duration/final health/CPU proof. Home warmup10.430s remains
> over target. **USER_STOPPED_INCOMPLETE; DEBT-083 Critical/active.**
> Final evidence: `aidlc-docs/construction/dashboard-operator-ui/code/`
> `source-recovery-20261027/operations/`. Earlier pending statements below are
> source-stage checkpoints superseded by this deployment/stop record.


Unit: `dashboard-operator-ui`; related `dashboard-operator-command-center`.
DEBT-083 remains Critical / active. Baseline main is
`7d604ad8dc36acb52e22d16830c841e274657250`, deployed source `120b440` / Fly v67.
Work is isolated in `/private/tmp/crypto-master-source-recovery-20261027`.
The user's `계속 진행` continues the bounded correction and prior sequential
commit/push, same-configuration deployment and operational verification authority.

**Full source gate passes; commit/push and deployment pending.**
The developer suite passes 214 tests, including 27 new recovery cases;
independent QA passes 236 tests and the actual two-session AppTest interaction.
Full regression passes 3,048 tests with all 265 input hashes unchanged;
source-wide mypy passes 135 files. Final read-only QA classified arbitrary
private Future callback injection as outside the public API, with no blocker.
Supported lifecycle guarantees cover service-owned, unmodified Futures. This verifies the finite
`source_changed` policy, not recovery from every production mutation window.

## Evidence and the policy amendment

The previous v67 observation remains **FAIL_SAMPLE**: 356 matched requests,
348 complete and eight terminal incomplete, four per page. Four failures
show activity-stale alerts with zero watchers; the next four show snapshots
unavailable after 17.282–18.581 s. Nearby diagnostic records classify one
activity and two snapshot projection failures as `source_changed`. All 352
health checks and the full 34.288159 s natural cycle pass; sampled throttle
counter increments are zero. This supports investigating changed-generation
recovery without claiming a CPU-throttle cause or a regression in the prior
proposal CPU optimization.

The diagnostics have asynchronous timestamps and no request/file identity.
They cannot identify an exact writer, verification branch or per-page causal
join. Later requests recover, so permanent production starvation is not
established. The retained
[residual analysis](../../aidlc-docs/construction/dashboard-operator-ui/code/cpu-cost-20261027/operations/residual-analysis/findings.md)
separates observed behavior from the supported follow-up candidate.

The earlier Home recovery design says terminal retry is invoked only by
explicit operator interaction; page-progress design preserves that policy.
The current service also expires ordinary error cache entries after two seconds,
so a later normal request can reattempt. Neither statement guarantees recovery
within the original incomplete page. This change creates one explicit exception:
`source_changed` receives a finite shared recovery sequence before becoming a
manual terminal outcome. Corruption, other terminal reasons and exhausted
source recovery keep explicit handling. Previous documents remain historical.

The [plan](../../aidlc-docs/construction/plans/dashboard-source-recovery-plan.md),
[functional rules](../../aidlc-docs/construction/dashboard-operator-ui/functional-design/source-recovery/business-rules.md)
and [NFR design](../../aidlc-docs/construction/dashboard-operator-ui/nfr-design/source-recovery/nfr-design-patterns.md)
record the authorized change. Primary traceability is FR-028–032/036/038,
NFR-003 and US-012, related US-023; operator safety/account/history obligations
also preserve FR-042, NFR-007/008/011/012 and US-020/014. BDL-NFR-03/04/06/07/08
directly govern readiness, continuity, bounded work, meaning and truthful
coverage. No infrastructure, capacity, dependency, credential, cadence or
trading-policy change is selected.

## Recovery contract and source scope

The current runtime scope is `src/dashboard/data_service.py` plus bounded
allowlist additions in `read_diagnostics.py`; related dashboard tests cover
the change. Projection/source verification, page layout, trading math and
runtime writers are outside this source scope.

- One normalized query admits one logical job with the same shared Future and
  compact generation Event through at most **three total attempts**. Four
  sessions coalesce onto that allowance, not four independent retry loops.
- The thirty-second monotonic recovery window begins at original admission.
  Delays are 0.25 and 0.5 s before the second and third attempts. Rerender,
  queue rotation and error-TTL expiry cannot reset the window or attempt count.
- A failed iterator/state is closed and discarded. Each retry recreates its
  builder, rediscovers membership and performs full generation validation.
  Failed partial output cannot become complete or enter the result cache.
- The sole worker chooses eligible siblings while a retry is delayed, using
  condition scheduling rather than sleeping inside the delayed job. One
  worker/four admissions and the four-second page foreground wait remain.
- Active recovery reports existing `rebuild_pending` with the original progress
  signal. The current single page watcher waits for final settlement; progress
  does not mean verified success. Complete age remains <=2 s and last-complete
  stale fallback <=30 s from its original evaluation. Failures renew neither.
- Exhausted `source_changed` is a protected terminal token, surviving normal
  rerenders and ordinary error TTL. The existing metadata pool is bounded by
  64 entries by default, with capacity reserved for admitted jobs. Protected
  tokens are not silently evicted; full capacity rejects new admission with
  explicit `recovery_budget_exhausted`. This can reduce availability under many
  exhausted scopes while keeping work and metadata finite.
- Exact-query manual retry removes only the captured token identity. It cannot
  clear another query, newer failure or active work. Close retires reservations
  and settles progress; cleanup failures remain terminal. No replacement worker,
  durable retry files or uncharged cache is introduced.

The thirty-second window bounds cooperative recovery eligibility, not a hard
wall-clock deadline. The first ordinary slow read remains compatible; a slow
initial read without `source_changed` is not newly cancelled at thirty seconds.
Blocking filesystem IO cannot be preempted safely. The design does not promise
completion during arbitrary sustained source churn or syscall blocking.

A deterministic synthetic writer schedule exposes the operational tradeoff:
three six-second attempts occupy 0–6, 6.25–12.25 and 12.75–18.75 s while writes
continue until 34 s. Recovery exhausts at 18.75 s and remains latched after the
writer becomes quiet; a normal rerender does not passively heal it. This is a
policy test, not a production replay, CPU profile or latency measurement.
Persistent new page unavailability after sufficient retained evidence of source
quiescence is a rollback consideration even with healthy HTTP/processes. A
cycle completion alone does not prove all sources are quiet. Keep the failed
observation and do not expand retry bounds or weaken proof to manufacture a pass.

## Verification checkpoint

| Gate | Evidence / current status |
|---|---|
| Independent source review | GREEN for the approved finite recovery policy; operational suitability remains unqualified. |
| Baseline reproduction | Three failures in 3.43 s: real activity mutation from cached generation, two real snapshot replacements before stable input, and four clients sharing one Future/progress through retry. |
| Developer targeted result | 214 passed in 10.11 s, including 27 new recovery cases. Real activity mutation and atomic snapshot replacement with disabled and explicitly prepared enabled checkpoints match canonical output. |
| Preserved iterations | Initial three failures / 71 passes in 10.73 s; a later 91-pass/one-failure diagnostic fixture iteration and the 213-pass pre-settlement-guard checkpoint remain retained. Old source-change counts now include three attempts; explicit-only manual/diagnostic fixtures use `invalid_record` to preserve their separate purpose. |
| Independent targeted result | 236 passed in 9.44 s. Verified attempt/deadline, same-job coalescing/fairness, sticky TTL-resistant exhaustion, 63+1/64 metadata boundaries, manual/ABA, original stale ages, cleanup/close and worker-exit containment without replacement. |
| Actual Streamlit interaction | PASS on local Streamlit 1.57.0: two sessions explicitly dispatch saved real fragments through three attempts, retaining the same Future/Event, one watcher and no manual terminal button during recovery; each session rerenders once on final success. This is not deployed Streamlit 1.65.0 timer/native-viewport qualification. |
| Static/source freeze | Black/Ruff pass five changed Python files; source-wide mypy passes 135 files, supplementing the earlier two-source check. The full run preserves all 265 source/test/script hashes. |
| Full regression | `uv run --no-sync python -m pytest -q`: 3,048 passed in 68.86 s on Python 3.13.0; wrapper 70.530427 s. Earlier sandbox attempt exited before tests on uv-cache permissions; that failure remains retained separately. |
| Final read-only QA follow-up | GREEN / no blocker. Public callers receive ReadResult and Event progress, never Futures; arbitrary private callback injection is outside supported usage. See `qa/shutdown-callback-scope.json`. |
| Commit/push/deployment | Pending exact source and remote/deployed identity. Existing v67 remains the verified runtime baseline. |
| Bounded live observation | Pending after source qualification and deployment; retain warm-up, every failed outcome, health/memory/CPU and a full natural cycle. |

The three baseline cases are in `tests/test_dashboard_source_recovery.py`.
The developer's exact focused command is retained in
`developer/developer-verification.json`: root `.venv/bin/python -m pytest`
over source-recovery, data-service, page-progress, availability, diagnostics,
projections, segment-checkpoint and bounded-page tests, using `-q
-p no:cacheprovider` and a retained JUnit file. The runtime source hashes are
`64dfd467db127b85410d47225e4e7bcfacdc8c56a8be4574f6694683a32024b4`
for `data_service.py` and
`4012d7e5889a5601a74ce63041f442b0ea0228c87c17666520ee64a3f7ecbc43`
for `read_diagnostics.py`. Availability, ReadResult, projection and source-proof
files match their predesign hashes.

Evidence is retained under
`aidlc-docs/construction/dashboard-operator-ui/code/source-recovery-20261027/`:
developer baseline/intermediate/final reports, `attempt-timings.json`,
`qa/source-verdict.json`, `qa/recovery-fragment-smoke-result.json`,
`qa/operational-risk-note.json` and the sandbox full-run failure record.
The lead's final gate records are `full-gate.json`, `full-pytest.txt`,
`source-input-sha256.json` and `mypy-src.json`; temporary originals are in
`/private/tmp/crypto-master-source-recovery-delivery-20261027/`.
Temporary originals remain in the task delivery directory. The
[context memo](../../aidlc-docs/construction/dashboard-operator-ui/code/source-recovery-20261027/context-acceptance-memo.md)
maps prior accepted rules and current ownership. No source/operational pass is
inferred from the prebuilt v68 audit adapter or its v67 self-check fixture.

## Acceptance and ownership remain separate

Retain historical failures: v64 347/349 with two Home incomplete, v65 116/120
with four timeouts, v66 352/356 with four guard-aborted, and v67 348/356 with
eight terminal incomplete. V67 Home warm-up 12.956247 s complete / 5.507020 s
first incomplete receipt also remains a miss. Later health/cycle recovery does
not turn any failed request into a successful measurement.

Original complete-page targets remain cold p95<=5 s / warm<=2 s, at least
twenty samples per page/scenario, with all failures retained. Incomplete-shell
timing is separate. Four sessions must run at least ten minutes and capture a
full natural engine cycle with all health<5 s. Native browser, cacheless versus
process-cold, successful depleted-CPU and original 1024 MiB qualification remain
open. Current shared CPU / 2048 MiB does not certify guest<=768 MiB on the original
capacity; dashboard growth<=256 MiB and incident/1M boundedness still apply.

Lead owns plan/design/state/debt/maps, integration and operations. Developer
owns source/tests and QA independently verifies. This slice owns only this new
session and the corresponding cross-check; no historical document is rewritten.

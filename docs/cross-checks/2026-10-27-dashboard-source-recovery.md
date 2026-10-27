# Cross-check: bounded source-generation recovery — 2026-10-27 KST

> **Final checkpoint — 2026-10-28 KST:** Source `7b87d9a` is committed/pushed
> and deployed as v68, with182runtime hashes and unchanged configuration verified.
> User requested stop/wrap-up. Observer and collector are stopped; exact remote
> sampler is absent. Partial raw16/16complete is not readiness acceptance: no
> full cycle/minimum duration/final health/CPU proof. Home warmup10.430s remains
> over target. **USER_STOPPED_INCOMPLETE; DEBT-083 Critical/active.**
> Final evidence: `aidlc-docs/construction/dashboard-operator-ui/code/`
> `source-recovery-20261027/operations/`. Earlier pending statements below are
> source-stage checkpoints superseded by this deployment/stop record.


Primary unit `dashboard-operator-ui`; related `dashboard-operator-command-center`.
Baseline main `7d604ad`, deployed source `120b440` / Fly v67. DEBT-083 remains
Critical / active. This is an implementation checkpoint, not final source or
production qualification. Developer 214-test and independent 236-test suites
pass, as do 3,048 full tests with 265 unchanged input hashes, five-file
Black/Ruff and 135-source mypy. Local two-session AppTest is GREEN. Final
private Future-callback QA disposition has no blocker; commit/push/rollout remain pending.
Finite-policy correctness is separate from long-mutation operational recovery.

## Traceability and intentional contract change

The [construction plan](../../aidlc-docs/construction/plans/dashboard-source-recovery-plan.md)
maps FR-028–032/036/038, NFR-003, US-012 and related US-023, with legacy
Phases 7/8.2/19.3. FR-042, NFR-007/008/011/012 and US-020/014 remain protected
safety/history/operations context. BDL-NFR-03/04/06/07/08 govern this finite
recovery; existing resource/scale and cold/native/depleted/original-capacity
requirements remain independent.

Previous Home recovery allowed only explicit terminal retry, while ordinary
service errors expired after two seconds and could be retried by a later
normal request. The approved current continuation intentionally gives only
`source_changed` a finite automatic recovery phase. It does not claim all
terminal semantics remain unchanged. After exhaustion, a protected token
requires exact-generation manual retry; other terminal errors retain their
existing treatment. The prior source and documents remain historical evidence.

## Contract and verification matrix

| Requirement / risk | Current design and evidence |
|---|---|
| Finite shared recovery | Three attempts total, thirty seconds from initial monotonic admission, delays 0.25/0.5 s. Same Future/Event across clients; no reset on rerender/TTL/queue rotation. Independent bounded-policy verification passes. |
| Source integrity | Close/discard failed iterator/state; fresh discovery and full validation each attempt. Real mutation/atomic replacement cases pass with disabled and explicitly prepared enabled checkpoints and exact canonical-output parity. Projection/source-proof files are unchanged. |
| Foreground and fairness | Existing four-second foreground, one worker/four admissions. Independent scheduling/race tests verify ready siblings proceed during retry delay and failed partial state is released before the next builder; no worker multiplication. |
| Freshness and partial state | Original two-second complete / thirty-second stale ages retained; failure cannot renew age or pin old sibling complete. Active recovery uses `rebuild_pending` and existing one-watcher progress. |
| Protected metadata | Existing default 64-entry pool covers terminal tokens plus admitted reservations. Exhausted source-change tokens are sticky; new admission fails visibly with `recovery_budget_exhausted` at capacity. No unbounded token map or silent budget reset by eviction. |
| Manual retry / close | Exact query/token identity protects newer failures, healthy cache and active work. Lifecycle tests pass: close settles delayed/active waits and rejects late publication; cleanup faults terminalize, unexpected worker exit quarantines without replacement. Guarantees cover supported service-owned, unmodified Futures; arbitrary private callbacks are outside the public API. |
| Time bound interpretation | Thirty seconds limits cooperative recovery eligibility; no filesystem preemption or hard completion promise. First ordinary slow reads retain compatibility before any source-change recovery. |
| Source scope | `src/dashboard/data_service.py`, bounded diagnostic allowlist in `read_diagnostics.py`, related dashboard tests. No planned projection/source-proof/page-layout/engine/trading/config change. |
| Baseline / correction | Three baseline failures in 3.43 s become passing behavior. Final developer targeted suite: 214 passed / 10.11 s, including 27 new cases. |
| Preserved iterations | Three failed / 71 passed in 10.73 s; later 91-pass/one-failure diagnostic fixture and 213-pass pre-guard checkpoint retained. Intentional three-attempt counts and `invalid_record` explicit-terminal fixtures preserve their separate purposes. |
| Independent QA / static | Primary source-policy GREEN, 236 passed / 9.44 s; Black/Ruff five files, mypy all 135 source files pass. Final read-only private Future-callback classification: no blocker; see `qa/shutdown-callback-scope.json`. |
| Full regression / exact inputs | `uv run --no-sync python -m pytest -q`: 3,048 passed / 68.86 s, Python 3.13.0, wrapper 70.530427 s; all 265 input hashes unchanged. Earlier sandbox attempt failed before tests on uv-cache permissions, retained separately. |
| Actual Streamlit AppTest | Local 1.57.0, two sessions, three attempts, same Future/Event, one watcher and one final rerender each. Saved fragments explicitly dispatched; deployed 1.65.0 timers/native viewport remain unqualified. |
| Deployment / observation | No new release claim. Commit/push and exact deployed source/settings verification, then one bounded four-session/natural-cycle observation pending. |

Source of the amended contract:
[business rules](../../aidlc-docs/construction/dashboard-operator-ui/functional-design/source-recovery/business-rules.md),
[recovery flow](../../aidlc-docs/construction/dashboard-operator-ui/functional-design/source-recovery/business-logic-model.md),
[NFR requirements](../../aidlc-docs/construction/dashboard-operator-ui/nfr-requirements/source-recovery/nfr-requirements.md)
and [NFR design](../../aidlc-docs/construction/dashboard-operator-ui/nfr-design/source-recovery/nfr-design-patterns.md).
New attempt/phase diagnostics remain allowlisted and bounded; no raw path,
account/query identity or exception body may enter telemetry or the normal UI.

The targeted baseline names in `tests/test_dashboard_source_recovery.py` cover
real activity change from a cached generation, snapshot replacements followed
by a third stable attempt, and four clients retaining one shared Future/progress.
Raw reports are retained under
`aidlc-docs/construction/dashboard-operator-ui/code/source-recovery-20261027/`:
`developer/developer-verification.json`, baseline/intermediate/final reports,
`developer/attempt-timings.json`, `qa/source-verdict.json`,
`qa/recovery-fragment-smoke-result.json` and `qa/operational-risk-note.json`.
The lead's final records are `full-gate.json`, `full-pytest.txt`,
`source-input-sha256.json` and `mypy-src.json`, with temporary originals in
`/private/tmp/crypto-master-source-recovery-delivery-20261027/`. The v68 audit
adapter is preparation/self-check material, not evidence that v68 is deployed
or a new observation has passed.

The synthetic 34 s writer model intentionally exhausts three six-second
attempts by 18.75 s and remains latched after subsequent stability. This proves
boundedness and the loss of prior passive TTL healing; it is not a production
replay or recovery guarantee. Persistent new page unavailability after retained
evidence of sufficient source quiescence is a rollback consideration even when
HTTP/process health is good. Cycle completion alone is not quiescence proof.
Preserve every failed outcome and do not expand limits to manufacture a pass.

## Acceptance boundaries retained

| Evidence / gate | Status |
|---|---|
| Historical v64/v65/v66/v67 | Retain 347/349, 116/120, 352/356 and 348/356 complete respectively, with their incomplete/timeout/guard-abort distinctions. All are failed samples. |
| V67 cause limits | Eight incomplete responses coincide with section-level source-change diagnostics. Async timestamps/no request identity cannot prove exact writer/branch/page joins. Healthy cycle/endpoints and zero sampled throttle increments do not repair the failures. |
| Cold/warm readiness | Cold<=5 s / warm<=2 s p95, >=20 observations per required page/scenario; retain every failure. First incomplete shell<=5 s is separate and not complete acceptance. Open. |
| Four sessions / engine | >=10 min and a full natural cycle within the observed window, all health<5 s, unchanged engine cadence. Source tests cannot satisfy this gate. |
| Memory / original capacity | Dashboard growth<=256 MiB, guest<=768 MiB on original 1024 MiB. Current shared CPU / 2048 MiB observations are separate. Open. |
| Other retained qualification | Native viewport, cacheless/process-cold distinction, incident/1M-event boundedness and successful depleted-CPU acceptance are not waived. |

The [session](../sessions/2026-10-27-dashboard-source-recovery.md) records the
same bounded scope and pending gates. The user-authorized correction changes
no capacity/cost, credentials, canonical runtime data or trading policy.
DEBT-083 cannot be closed from these source-policy results alone.

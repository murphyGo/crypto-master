# Source-change recovery: context and acceptance memo

Read-only context audit, 2026-10-27 KST. Worktree baseline:
`7d604ad8dc36acb52e22d16830c841e274657250`; deployed baseline v67 / `120b440`.
Only this delivery memo is written. No source/test/runtime/production action.

## Ownership and applicable requirements

Primary unit is `dashboard-operator-ui`; secondary is
`dashboard-operator-command-center`. Persistence and runtime-safety are
protected consumers, not permission to change their writers or trading math.
DEBT-083 remains Critical / active. Relevant legacy context is Phase 7 UI,
8.2 engine visibility and 19.3 sub-account selection; no new legacy phase.

| Context | Applicability |
|---|---|
| FR-029/031/032 | Restore verifiable active positions, summaries and Streamlit read availability. |
| FR-036/042 | Preserve account/mode isolation and operator safety meanings; incomplete input cannot become fresh SAFE/zero. |
| NFR-003/007/008 | Preserve Streamlit, trade/asset-history interpretation and mode/account scope; no persistence rewrite. |
| NFR-011/012 | Protected credentials and explicit live intent; no new credential, exchange or trading actions. |
| US-012/023 | Primary operator dashboard and command-center recovery workflow. |
| US-020/014 | Safety/freshness visibility and unchanged secure operational deployment. |
| BDL-NFR-03/04/06/07/08 | Readiness, shared-guest continuity, bounded work, exact semantics and truthful incomplete/freshness states directly govern this change. BDL-NFR-01/02/05 containment and resource/scale requirements remain obligations. |

Traceability: `aidlc-docs/inception/requirements/requirements.md:59–94`,
`user-stories/stories.md:33–54`,
`application-design/unit-of-work-story-map.md:13–17`,
`units/unit-of-work.md:138–169`, `units/debt-unit-map.md:13–19` and
`docs/TECH-DEBT.md:44–53`. Paths above are relative to their inception directory
where abbreviated. The debt's top table retains earlier v64 wording; current
status comes from its chronological follow-ups and `aidlc-state.md:60–79`.

## Previously accepted recovery contract

1. **One shared reader / four total admissions.** Coalesce identical queries;
   never add a worker per session, replacement worker, or uncharged retry queue.
   Queue time counts against the same 4 s monotonic foreground deadline.
2. **Truthful ages and coverage.** Complete age <=2 s; last complete fallback
   <=30 s from its original evaluation, labelled stale. A failed retry cannot
   renew either timestamp, pin an expired sibling as complete, or hide an
   independently valid ledger. Only fully verified new input can be complete.
3. **Full generation proof.** Rediscover membership and revalidate selected
   files/directories on rebuild; atomic replacement, truncation, same-size
   rewrite and append may invalidate the old result. No prefix trust,
   directory-only proof, mixed-generation publication or checkpoint bypass.
4. **Terminal retry is currently explicit.** Home recovery design lines 26–28:
   “Only explicit operator interaction invokes terminal retry.” Its callback
   removes only the captured error generation for that query, never a newer
   error, healthy cache or active job (lines 17–24). Persistent corruption must
   not auto-loop. This is a UI retry rule, not permanent error storage: current
   service error TTL is 2 s and a subsequent ordinary request can reattempt.
5. **Page progress stays bounded and read-only.** At most sixteen probes,
   one watcher and one notification per render; job-generation events survive
   timeout/ABA races and are observed independently by coalesced sessions.
   Probes do not normalize/read/admit/clear errors/change age. Close settles
   handles without waiting indefinitely. Manual fallback remains when fragments
   are unavailable. A completion signal means settlement, not verified success.
6. **Existing resource accounting and privacy remain.** Cache 16 MiB/64 entries,
   active state 16 MiB, manifest 4 MiB, two roots, eight handles, 2 MiB encoded
   result, 1 MiB record, 64 KiB blocks, 512 MiB/4 s quantum and cooperative checks.
   Checkpoint storage already has its own approved bounded optional namespace;
   do not add retry files or create missing canonical roots. Diagnostics use
   bounded allowlisted metadata, no path/account/query identity/raw exception;
   asynchronous diagnostic failure cannot block reading or settlement.

Exact sources:
`code/home-recovery-20261026/design.md:9–41`,
`code/page-progress-20261027/design.md:17–47`,
`nfr-design/bounded-data-loading/nfr-design-patterns.md:16–33,42–60,88–131`,
`nfr-design/verified-segment-checkpoints/nfr-design-patterns.md:27–43,47–95`,
all under `aidlc-docs/construction/dashboard-operator-ui/`.

## Explicit new amendment needed in the current approved continuation

Treating `source_changed` as a transient bounded attempt sequence intentionally
changes item 4 above; do not describe terminal policy as wholly unchanged.
The user's current fix/commit/push/deploy authority permits this bounded task;
the reviewed design should state the exception before implementation. Functional
Design and NFR Design apply (`inception/plans/execution-plan.md:14–19,31–32`).
No new infrastructure/capacity/cost topology is selected.

The new design must choose explicit finite attempt and total-time limits; no
particular new retry count was previously approved. The allowance belongs to
one logical query sequence shared across sessions. It must not reset merely on
rerender, error-TTL expiry or competing callers. A failed generation is discarded
and the next attempt fully rediscovers/verifies. Backoff must release useful
sibling scheduling without sleeping the sole worker or expanding admission.
After exhaustion, retain an actionable generation-scoped manual retry; corrupt,
oversized, budget-limited and other non-source-change terminal failures keep
their existing explicit handling. Recovery must not promise success during
arbitrarily long churn. Define close, eviction, scope churn and old-callback
behavior so bounded metadata cannot revive an exhausted/newer sequence.

Minimum deterministic proofs: one mutation then stable input; two sequential
snapshot replacements then stability within the chosen budget; four coalesced
clients; persistent churn exhausted without polling reset; malformed/resource
failure never auto-loops; each verification boundary still rejects; healthy
siblings retain original ages; retry fairness, ABA/manual/close and AppTest
progress preserve the one-watcher contract. Verify exact full canonical output,
not just absence of exceptions. This list is review criteria, not passed tests.

## Historical and final acceptance boundaries

V64 347/349 (two Home incomplete), v65 116/120 (four timeouts), v66 352/356
(four guard-aborted) and v67 348/356 (eight terminal incomplete) remain failures.
V67's 352 healthy checks, full 34.288 s cycle and zero sampled throttle increments
do not repair page failures. Its diagnostics show `source_changed`, but async
timestamps/no request identity do not prove a writer, verification branch or
exact page causal join. The existing residual analysis is a supported candidate,
not a promise that finite retries solve every source churn window.

Retain complete cold p95<=5 s / warm<=2 s with >=20 samples per page/scenario;
incomplete shell<=5 s independently; all failures in the sample. Four sessions
>=10 min must capture a full natural engine cycle, all health<5 s, no fabricated
cycle/cadence change. Keep dashboard growth<=256 MiB and guest<=768 MiB on the
original 1024 MiB condition; current unchanged shared-CPU/2048 MiB does not
certify it. Native viewport, cacheless versus process-cold, incident/1M scale,
successful depleted-CPU and original-capacity gates remain open.

## Context reviewed / subsequent ownership

Reviewed the `/dev-crypto` entrypoint and required context: AGENTS, state,
canonical requirements/verification questions/stories/story map/components,
unit/legacy/debt maps, execution/construction guides, requirements, debt,
DESIGN and CLAUDE; read relevant dashboard sections and accepted designs above.
Also read v67 `operations/residual-analysis/findings.md` and current service/
availability contracts to distinguish error TTL from page watcher behavior.
No tests or production queries were run for this audit.

Lead owns plan/design/state/debt/maps and operations. Developer owns source/tests;
QA independently verifies. After verified reports arrive, docs-auditor owns only
`docs/sessions/2026-10-27-dashboard-source-recovery.md` and the corresponding
`docs/cross-checks/` file. Neither is created at this checkpoint.

# Runtime Safety Streaming: Functional Design Plan

- **Unit / stage:** `runtime-safety-score` / Functional Design candidate; related `proposal-runtime`, `persistence-data-integrity` and dashboard DEBT-083.
- **Requirements / stories:** FR-014/015/042, NFR-007; US-020. Shared-VM BDL-NFR-02/04 qualification supplies current incident evidence.
- **Evidence:** v62 engine peak RSS 899748 KiB, guest peak 1293.313 MiB; four actual 30s server page timeouts despite large CPU burst balance/zero throttle. `_current_runtime_safety_score` materializes all activity before recency filtering, and its result drives actual pause gating.
- **Authorization boundary:** Remaining UI investigation/qualified source work is authorized. The presented base safety evaluation-time contract is approved for NFR continuation; the new failure-isolation amendment/NFR budgets are not yet approved. Existing runtime code/paper/live controls remain unchanged; no persistence or added cost activated.

1. [x] Trace the actual whole-history allocation and both notification/live-pause consumers.
2. [x] Identify fixed-time invariants, source ordering, extras/cache, error and timing differences.
3. [x] Prepare logic/rules/entities/frontend-consumer artifacts under `functional-design/streaming-activity-inputs/`.
4. [x] Receive explicit functional approval before the next NFR stage.
5. [ ] Define/review read/state/time budgets, clock reversal and guarded failure integration in NFR design.
6. [ ] Only after applicable approvals: implement, independently cross-check safety/pause behavior, qualify the exact source and obtain scoped rollout evidence.

## Questions / concrete candidate choices

These are proposals for review, not recorded operator answers.

- **Logic / domain:** [Answer]: Stream canonical source events into the same exact counters/distinct conditions; preserve formulas and modes.
- **Time rule:** [Answer]: Propose explicit request-time UTC anchoring. This can conservatively retain boundary incidents that completion-time anchoring would expire; approval is required.
- **Data flow:** [Answer]: Add a read-only source iterator; keep canonical data/retention and chronological API intact. No disk cache.
- **Integration:** [Answer]: Both notifications and actual pause gate consume the same snapshot; preserve `None`/extra-list/cache semantics.
- **Errors:** [Answer]: Preserve legacy malformed-row warning/skip behavior, while hard read/budget failure must use a guarded error path rather than a healthy/zero score. Exact NFR behavior needs review.
- **Scenarios:** [Answer]: Fixed-time parity, UTC edges/future, advisory/dedup fallbacks, replay duplication, cache, malformed/error/exhaustion and mode/pause controls must be tested.
- **Frontend:** [Answer]: Existing controls/status/freshness surfaces; no new trading or configuration flow.
- **Approval:** [Answer]: Operator `나머지도 계속 진행해줘` after the explicit approval-pending status approves the presented base streaming/time contract for NFR continuation. This is not approval of unpresented NFR budgets or the newly discovered failure-isolation amendment.

## Approval checkpoint

- Exact continuation: `나머지도 계속 진행해줘`.
- Context: assistant explicitly reported incomplete acceptance and pending follow-up designs.
- Scope: approve the already-presented base Functional Design and continue NFR formalization/design; CPU/cost deferral and existing capacity remain.
- New numeric budgets and any failure-flow amendment are not pre-approved.
- Recorded at: 2026-10-25T11:21:35.006589+00:00 (record time, not message timestamp).

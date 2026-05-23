# Session: cross-account-risk-policy DEDICATED RISK EVENT TYPES (DEBT-068(g))

Date: 2026-05-24
Units: `cross-account-risk-policy`
Stage: Code Generation
Related debt: DEBT-068(g) — dedicated `RISK_CAP_ADVISORY` + `RISK_KILL_SWITCH_TRIPPED` `ActivityEventType` values SHIPPED (event-type migration only); a dashboard "Rejected"-column undercount surfaced and filed as (g-note-dashboard-undercount) tied to (f)
Related requirements: FR-036, FR-037, FR-038, FR-044, NFR-007, NFR-008, NFR-012

> Sixth same-day session log on the `cross-account-risk-policy` unit, distinct
> from its five siblings:
> `docs/sessions/2026-05-24-cross-account-risk-policy-opt-in-global-caps.md`
> (DEBT-068(b), opt-in global exposure caps, commit `a088e17`),
> `docs/sessions/2026-05-24-cross-account-risk-policy-kill-switch-c1.md`
> (DEBT-068(c-1), the STATELESS kill-switch gates),
> `docs/sessions/2026-05-24-cross-account-risk-policy-kill-switch-c2-daily-loss.md`
> (DEBT-068(c-2), the STATEFUL daily-loss kill switch that completed (c)),
> `docs/sessions/2026-05-24-cross-account-risk-policy-operator-freeze.md`
> (DEBT-068(d), the operator manual freeze runtime READ side), and
> `docs/sessions/2026-05-24-cross-account-risk-policy-stale-actions.md`
> (DEBT-068(e), the stale-position `auto_close` / `alert_only` actions). This
> log covers DEBT-068(g) — the dedicated risk-event-type migration. Uncommitted
> on `main` at the time of writing; committed immediately after.

## Scope

DEBT-068(g) migrates the paper-mode risk emissions off the
`PROPOSAL_REJECTED + details.advisory=True` reuse that the kill-switch and
aggregate-cap gates have carried since Slice 2a, onto two dedicated
`ActivityEventType` values. This is an **event-type migration only** — no
`final_state` change, no funnel change, no rejection-bookkeeping change. The
scope was held tight by design: the funnel and the proposal-rejection counts
are keyed on `final_state` terminals and `proposals_rejected`, both of which
are independent of `event_type`, so migrating the event type cannot move a
single funnel number.

Two new values were added to `ActivityEventType` in
`src/runtime/activity_log.py`: `RISK_CAP_ADVISORY` and
`RISK_KILL_SWITCH_TRIPPED`. The migration touched the **event type only** at
four emission sites in `src/runtime/engine.py`:

- `_kill_switch_outcome` paper branch → `RISK_KILL_SWITCH_TRIPPED`.
- `_kill_switch_outcome` live branch → `RISK_KILL_SWITCH_TRIPPED`.
- `_account_aggregate_cap_gate` paper branch → `RISK_CAP_ADVISORY`.
- `_global_aggregate_cap_gate` paper branch → `RISK_CAP_ADVISORY`.

The `details.advisory=True` discriminator on the paper advisories is
preserved — consumers that distinguished advisory from hard-block via that flag
continue to work. Live CAP hard-blocks, the stale-block advisory,
operator-freeze, and every non-risk gate are UNCHANGED. The stale
"deferred to DEBT-068(g)" docstrings (which had described the old
`PROPOSAL_REJECTED + advisory` reuse as a placeholder) were rewritten to
describe the shipped behavior, so the in-code documentation no longer points at
a deferral that has now landed.

Approximately 10 test assertions were updated to expect the new event types at
the four migrated sites. No new behavior was added, so no new tests were
written — the delta is a pure type swap plus the assertion updates that follow
from it.

## Changes — DEBT-068(g) dedicated risk event types

- `src/runtime/activity_log.py`
  - New **`ActivityEventType.RISK_CAP_ADVISORY`**.
  - New **`ActivityEventType.RISK_KILL_SWITCH_TRIPPED`**.
- `src/runtime/engine.py` (EVENT TYPE migrated at four sites; no
  `final_state` / funnel change):
  - **`_kill_switch_outcome` paper branch** → `RISK_KILL_SWITCH_TRIPPED`.
  - **`_kill_switch_outcome` live branch** → `RISK_KILL_SWITCH_TRIPPED`.
  - **`_account_aggregate_cap_gate` paper branch** → `RISK_CAP_ADVISORY`.
  - **`_global_aggregate_cap_gate` paper branch** → `RISK_CAP_ADVISORY`.
  - `details.advisory=True` discriminator preserved on paper advisories.
  - Stale "deferred to DEBT-068(g)" docstrings rewritten to describe the
    shipped behavior.
- `tests/`
  - ~10 assertions updated to expect the new event types at the four migrated
    sites. No new tests (pure type migration).

Live CAP hard-blocks, the stale-block advisory, operator-freeze, and all
non-risk gates are UNCHANGED — verified by the qa reviewer.

## Review

- qa-reviewer: 🟡 **SHIP WITH NOTE**. Full suite **2142 passed (delta 0 —
  migration only)**, 0 failed; `ruff` + `mypy` clean. Funnel / rejection
  bookkeeping verified UNCHANGED — the `final_state` terminals and
  `proposals_rejected` are independent of `event_type`, so the migration moves
  no funnel number. Migration complete and scope-disciplined. The 🟡 note is a
  downstream dashboard-tally observation, filed as
  (g-note-dashboard-undercount) — see TECH-DEBT Items below.
- No quant escalation — no trading-math / `src/trading` touched; this is an
  activity-log event-type migration.

## Verification

- Full suite: 2142 passed, 0 failed (was 2142; net 0 — pure event-type
  migration, no behavior change, no regressions).
- `ruff check src tests`: clean.
- `mypy src`: clean.

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Potential Risks

- **Secondary dashboard "Rejected" column drifts (the qa 🟡 note).**
  `src/dashboard/pages/engine.py` `_count_events` (~line 189) and
  `build_sub_account_metrics_dataframe` (~line 374) tally the "Rejected" column
  by an exact `event_type == PROPOSAL_REJECTED` match. Post-migration this
  shifts two ways: (1) paper cap / kill-switch advisories correctly STOP
  inflating "Rejected" — an improvement, since they were never real rejections;
  (2) LIVE kill-switch hard-blocks — which ARE genuine rejections (their
  `final_state` is a `GATE_REJECTED_*_KILL_SWITCH` terminal) — are now emitted
  as `RISK_KILL_SWITCH_TRIPPED` and therefore EXCLUDED from this
  activity-event-based "Rejected" tally, producing a genuine undercount in that
  secondary dashboard column. **No data is lost**: the proposal funnel keyed on
  `final_state` remains authoritative and fully correct; only the
  activity-event-based dashboard summary column drifts, and live kill-switch
  trips are rare. Filed as (g-note-dashboard-undercount), tied to the (f)
  dashboard slice — recommended fix is to rebase the dashboard "Rejected"
  column on the funnel / `final_state` rather than activity-event scanning, OR
  fold non-advisory `RISK_KILL_SWITCH_TRIPPED` into the tally.

## TECH-DEBT Items

DEBT-068(g) ships the dedicated risk event types. The DEBT-068 umbrella remains
Active. One follow-up filed this cycle:

- **(g-note-dashboard-undercount)** (qa) — the secondary dashboard "Rejected"
  column in `src/dashboard/pages/engine.py` (`_count_events` ~line 189 and
  `build_sub_account_metrics_dataframe` ~line 374) keys on exact
  `event_type == PROPOSAL_REJECTED`; post-(g), LIVE kill-switch hard-blocks
  (genuine rejections) are emitted as `RISK_KILL_SWITCH_TRIPPED` and excluded
  from that tally, a genuine undercount in that one column. No data lost — the
  funnel keyed on `final_state` remains authoritative. Recommended fix:
  rebase the column on the funnel / `final_state`, OR fold non-advisory
  `RISK_KILL_SWITCH_TRIPPED` into the tally. Tied to the (f) dashboard slice.

The DEBT-068(g) sub-item is annotated SHIPPED in the umbrella.

## Remaining Work

DEBT-068 remains Active. Deferred follow-ups, all still open:

- **(c-arb)** `cap_resolution=lowest_priority_loses` arbitration for global
  `(symbol, side)` caps — separate slice. **Candidate next slice** (closes the
  last open-cap v1-arbitration gap left by (b)).
- **(f)** dashboard cross-account risk exposure panel + the operator-freeze
  toggle WRITE side + stale-event surfacing + the (g-note-dashboard-undercount)
  "Rejected"-column rebase.
- **(h)** `runtime-safety-score` kill-switch + stale-event integration.

No ADR needed — this slice implements the already-decided DEBT-068(g) event-type
migration named in the cross-account-risk-policy functional-design spec and the
construction plan. It introduces no new component boundary, chooses between no
competing approaches with long-term implications, and locks in no new constraint
that future work must respect; it merely retires a placeholder reuse
(`PROPOSAL_REJECTED + advisory`) in favor of the dedicated enum values that were
already reserved for it. No architecture decision record is warranted.

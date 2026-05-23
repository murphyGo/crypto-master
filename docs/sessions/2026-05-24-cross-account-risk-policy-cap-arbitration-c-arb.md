# Session: cross-account-risk-policy CAP ARBITRATION — `lowest_priority_loses` (DEBT-068(c-arb))

Date: 2026-05-24
Units: `cross-account-risk-policy`
Stage: Code Generation
Related debt: DEBT-068(c-arb) — `cap_resolution=lowest_priority_loses` arbitration for the global `(symbol, side)`/`symbol` caps SHIPPED. **COMPLETES the last open-cap v1-arbitration gap left by (b).** One MINOR non-blocking follow-up filed as (c-arb-note-overshoot-units), tied to (f)
Related requirements: FR-036, FR-037, FR-038, FR-044, NFR-007, NFR-008, NFR-012

> Seventh same-day session log on the `cross-account-risk-policy` unit, distinct
> from its six siblings:
> `docs/sessions/2026-05-24-cross-account-risk-policy-opt-in-global-caps.md`
> (DEBT-068(b), opt-in global exposure caps, commit `a088e17`),
> `docs/sessions/2026-05-24-cross-account-risk-policy-kill-switch-c1.md`
> (DEBT-068(c-1), the STATELESS kill-switch gates),
> `docs/sessions/2026-05-24-cross-account-risk-policy-kill-switch-c2-daily-loss.md`
> (DEBT-068(c-2), the STATEFUL daily-loss kill switch that completed (c)),
> `docs/sessions/2026-05-24-cross-account-risk-policy-operator-freeze.md`
> (DEBT-068(d), the operator manual freeze runtime READ side),
> `docs/sessions/2026-05-24-cross-account-risk-policy-stale-actions.md`
> (DEBT-068(e), the stale-position `auto_close` / `alert_only` actions), and
> `docs/sessions/2026-05-24-cross-account-risk-policy-risk-event-types.md`
> (DEBT-068(g), the dedicated risk-event-type migration). This log covers
> DEBT-068(c-arb) — the `lowest_priority_loses` cap-arbitration slice, which
> closes the last open-cap v1-arbitration gap left open by (b)'s
> `first_come_first_serve`-only ship. Uncommitted on `main` at the time of
> writing; committed immediately after.

## Scope

DEBT-068(b) shipped `_global_aggregate_cap_gate` with `first_come_first_serve`
(FCFS) v1 arbitration only — when a global `(symbol, side)` or `symbol` cap
would breach, the proposal is always blocked, first-mover-wins. DEBT-068(c-arb)
adds the second `cap_resolution` mode the spec reserved:
`lowest_priority_loses`. **Breach detection is unchanged** — the same
cross-sub-account exposure aggregation decides which caps would breach. What
this slice adds is an **arbitration step** that decides `block_overall` after
breach detection has run.

The arbitration is a **SOFT ceiling**, per the quant design: when a cap would
breach under `lowest_priority_loses`, the proposal is ADMITTED iff, for EVERY
breached cap, the proposing account **strictly outranks at least one OTHER
(self-excluded) holder** on that cap's key. Account priority is read from
`account_priority` (earlier in the list = higher priority; unlisted = lowest
priority). Composition across multiple simultaneously-breached caps is
**AND-conservative**: any single cap that arbitrates to block blocks the whole
proposal. A more-permissive broad cap can therefore never override a stricter
narrow-cap block.

The change is purely additive on the runtime data model — the gate's `details`
payload gained `cap_resolution`, `arbitration_outcome`, `proposer_account`,
`proposer_rank`, `proposer_listed`, `existing_holders`, `arbitration_by_cap`,
and `cap_overshoot` fields, none of which alter any decision-bearing
`final_state` or funnel count. FCFS is preserved **bit-for-bit** — when
`cap_resolution` is FCFS (the v1 default), the gate behaves exactly as it did
post-(b), and all 7 pre-existing global-cap tests pass unchanged. A set of
fallbacks all behave FCFS-equivalent (block on breach): empty
`account_priority`, an unlisted proposer, `sub_account` None / a single-account
deployment, and no existing holders on the breaching key.

One additional safety surface: an ADMITTED **LIVE** overshoot (the case where
arbitration lets a proposal through that nonetheless pushes a cap past its
ceiling) emits an informational `RISK_CAP_ADVISORY` (with `advisory=False`,
distinguishing it from the paper would-block advisories) carrying
`cap_overshoot`, so the soft-ceiling admission is **never silent** on the
operator dashboard.

## Changes — DEBT-068(c-arb) `lowest_priority_loses` arbitration

- `src/runtime/engine.py`
  - `_global_aggregate_cap_gate` — breach detection UNCHANGED; new arbitration
    step decides `block_overall`. Under `cap_resolution=lowest_priority_loses`,
    a breaching proposal is ADMITTED iff for EVERY breached cap the proposing
    account strictly outranks at least one OTHER (self-excluded) holder on that
    cap's key (`account_priority`: earlier = higher, unlisted = lowest).
    AND-conservative across multiple breached caps — any cap that arbitrates to
    block blocks the proposal.
  - FCFS preserved bit-for-bit — FCFS-default path behaves exactly as post-(b).
  - FCFS-equivalent fallbacks: empty `account_priority`, unlisted proposer,
    `sub_account` None / single-account, no existing holders on the key.
  - Admitted LIVE overshoot emits an informational `RISK_CAP_ADVISORY`
    (`advisory=False`) carrying `cap_overshoot` — soft-ceiling admission is not
    silent.
  - Additive `details` fields: `cap_resolution`, `arbitration_outcome`,
    `proposer_account`, `proposer_rank`, `proposer_listed`, `existing_holders`,
    `arbitration_by_cap`, `cap_overshoot`. None alter `final_state` / funnel.
- `tests/`
  - +14 tests covering the arbitration matrix: strict-outrank admit;
    lowest-priority/unlisted block; AND-conservative multi-cap composition (a
    permissive broad cap cannot override a stricter narrow-cap block);
    self-exclusion; the FCFS-equivalent fallbacks; the LIVE-overshoot
    `RISK_CAP_ADVISORY` emission; and the 7 pre-existing global-cap tests
    passing unchanged.

Breach detection, FCFS behavior, funnel counts, and `final_state` terminals are
all UNCHANGED — verified by the qa reviewer (FCFS bit-for-bit; funnel /
`final_state` unchanged).

## Review

- quant-trader-expert: 🟢 **"sound — ship"**. Design conformance confirmed
  (SOFT-ceiling semantics: admit iff strictly outranks ≥1 other holder on every
  breached cap; AND-conservative composition). Additionally confirmed that the
  **superset relationship** between the per-`(symbol, side)` key and the
  per-`symbol` key is **strictly safe** under AND-conservative composition — a
  more-permissive broad cap can never override a stricter narrow-cap block, and
  the per-cap audit trail (`arbitration_by_cap`) disambiguates which cap drove
  the outcome.
- qa-reviewer: 🟢. Full suite **2156 passed (+14)**, 0 failed; `ruff` + `mypy`
  clean. **FCFS preserved bit-for-bit**; all **7 pre-existing global-cap tests
  pass unchanged**; funnel / `final_state` unchanged.

## Verification

- Full suite: 2156 passed (+14), 0 failed.
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

- **`cap_overshoot` mixes units across cap kinds (the c-arb-note).** When a
  COUNT cap (`open_positions_per_symbol_side`) and a NOTIONAL cap breach
  together, `cap_overshoot`'s `total` / `max` aggregate would sum positions and
  dollars into a single number. This is **harmless** — `cap_overshoot` is an
  advisory DISPLAY-only field, never read by any decision path (the arbitration
  decision is per-cap and unit-aware via `arbitration_by_cap`) — but a future
  reader could misread the mixed-unit aggregate. Recommended remedy: a one-line
  code comment at the aggregation site, or a per-cap-unit split of
  `cap_overshoot`. Filed as (c-arb-note-overshoot-units), tied to the (f)
  dashboard slice (which surfaces these fields).

## TECH-DEBT Items

DEBT-068(c-arb) ships the `lowest_priority_loses` arbitration and is annotated
SHIPPED in the umbrella. **This COMPLETES (c-arb) — the last open-cap
arbitration gap.** One MINOR non-blocking follow-up filed this cycle:

- **(c-arb-note-overshoot-units)** (qa/dev) — `cap_overshoot` mixes units when a
  COUNT cap (`open_positions_per_symbol_side`) and a NOTIONAL cap breach
  together: its `total` / `max` would sum positions and dollars. Harmless
  (advisory DISPLAY only, never used in any decision — the arbitration is
  per-cap and unit-aware), but worth a one-line code comment or a per-cap-unit
  split if a future reader might misread it. Tied to (f) dashboard surfacing.

## Remaining Work

DEBT-068 remains Active. With (c-arb) shipped, the umbrella's open follow-ups
are now:

- **(f)** dashboard cross-account risk exposure panel — now accumulates the
  operator-freeze toggle WRITE side from (d), the stale-event surfacing from
  (e), the (g-note-dashboard-undercount) "Rejected"-column rebase, and the new
  `RISK_*` event charting (incl. the (c-arb) `RISK_CAP_ADVISORY` overshoot
  advisories and the (c-arb-note-overshoot-units) display fields).
- **(h)** `runtime-safety-score` kill-switch + stale-event integration.

No ADR needed — this slice implements the `lowest_priority_loses` arbitration
mode already named and specified in the `cross-account-risk-policy`
functional-design spec (§"Symbol/Side Caps") and reserved by the DEBT-068(b)
construction-plan step. It introduces no new component boundary, chooses between
no competing approaches with long-term implications (the SOFT-ceiling /
AND-conservative semantics were fixed by the quant design), and locks in no new
constraint future work must respect that the spec did not already establish; it
merely retires the FCFS-only v1 deferral. No architecture decision record is
warranted.

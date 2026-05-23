# Session: cross-account-risk-policy STALE-POSITION auto_close / alert_only ACTIONS (DEBT-068(e))

Date: 2026-05-24
Units: `cross-account-risk-policy`
Stage: Code Generation
Related debt: DEBT-068(e) — stale `auto_close` / `alert_only` runtime actions SHIPPED; dashboard surface + runtime-safety-score inputs remain (f)/(h)
Related requirements: FR-036, FR-037, FR-038, FR-044, NFR-007, NFR-008, NFR-012

> Fifth same-day session log on the `cross-account-risk-policy` unit, distinct
> from its four siblings:
> `docs/sessions/2026-05-24-cross-account-risk-policy-opt-in-global-caps.md`
> (DEBT-068(b), opt-in global exposure caps, commit `a088e17`),
> `docs/sessions/2026-05-24-cross-account-risk-policy-kill-switch-c1.md`
> (DEBT-068(c-1), the STATELESS kill-switch gates),
> `docs/sessions/2026-05-24-cross-account-risk-policy-kill-switch-c2-daily-loss.md`
> (DEBT-068(c-2), the STATEFUL daily-loss kill switch that completed (c)), and
> `docs/sessions/2026-05-24-cross-account-risk-policy-operator-freeze.md`
> (DEBT-068(d), the operator manual freeze runtime READ side). This log covers
> DEBT-068(e) — the stale-position `auto_close` and `alert_only` actions.
> Uncommitted on `main` at the time of writing; committed immediately after.

## Scope

DEBT-068(e) ships the two stale-position actions that Slice 1 deferred:
`auto_close` and `alert_only`. Slice 1 shipped only `block_new_entries` via the
(unchanged) `_stale_position_block_gate`. This slice adds the missing runtime
behavior driven by the per-sub-account `stale_position_action` config: a
position aging past `max_time_in_position_hours` is now handled per the
configured action, with the resolution constrained by the position's
`runtime-reconciliation` state so that auto-close can never act on a position
that may be subject to exchange/ledger drift.

The work lives entirely in the monitor loop (`_monitor` in
`src/runtime/engine.py`), slotted as a **fallback AFTER the SL/TP check and the
per-strategy time-stop**, so a position that would already exit via SL/TP or
the time-stop never reaches the stale-age handler — no double-close. Two new
methods carry the behavior: `_classify_trade_reconciliation` resolves the
position's reconciliation state, and `_maybe_stale_age_action` dispatches the
configured action under the resolution table below.

The defining design constraint, ratified by the quant review, is that **no path
auto-closes a `degraded` or `unrecoverable` position**. The spec's
exchange/ledger-drift protection is the whole reason stale-age actions
coordinate with `runtime-reconciliation`: a position that is stale AND degraded
must not be flattened at market, because the local ledger and the exchange may
disagree about whether the position even exists. The resolution table enforces
this: only `MONITORABLE` and `LEGACY_NO_PERF_LINK` positions are eligible to
close; `DEGRADED` downgrades to a block + event; `UNRECOVERABLE` raises a
high-priority operator-only alert and never closes.

The staleness math reuses the same age computation as the block gate, and the
quant review confirmed the two agree (a position the block gate would treat as
stale is the same position the stale-age handler acts on). The close path
inherits the existing close machinery and introduces no new price-safety gap.

## Changes — DEBT-068(e) stale-position auto_close / alert_only actions

- `src/runtime/engine.py`
  - **`_classify_trade_reconciliation`** (new) — resolves the open trade's
    `runtime-reconciliation` state for the stale-age decision.
  - **`_maybe_stale_age_action`** (new) — slotted into `_monitor` as a
    **fallback AFTER SL/TP and the per-strategy time-stop** (so no
    double-close). Dispatches per `stale_position_action`:
    - **`auto_close`** — closes the position at market, writing a
      `POSITION_CLOSED` event with `reason="stale_age_cap"` plus a new
      `STALE_POSITION_AUTO_CLOSED` event, in **both paper and live**.
    - **`alert_only`** — emits `STALE_POSITION_DETECTED` only; no enforcement.
    - **`block_new_entries`** — emits a visibility `STALE_POSITION_DETECTED`;
      enforcement stays in the **unchanged** `_stale_position_block_gate`.
  - **Reconciliation resolution table** (enforced inside the close decision):
    - `MONITORABLE` / `LEGACY_NO_PERF_LINK` ⇒ close.
    - `DEGRADED` ⇒ no-close + downgrade-to-block event
      (`resolution=degraded_block_new_entries`, priority `high`).
    - `UNRECOVERABLE` ⇒ no-close + high-priority alert
      (`resolution=unrecoverable_operator_only`).
- `src/runtime/activity_log.py`
  - New **`ActivityEventType.STALE_POSITION_DETECTED`**.
  - New **`ActivityEventType.STALE_POSITION_AUTO_CLOSED`**.
- `tests/`
  - +8 tests covering all 8 scenarios (auto_close paper, auto_close live,
    alert_only, block_new_entries visibility event, degraded downgrade,
    unrecoverable operator-only, no-double-close after SL/TP and time-stop,
    block-gate-unchanged).

`_stale_position_block_gate` is genuinely unchanged — verified by the qa
reviewer.

## Review

- quant-trader-expert: 🟢 "sound — ship". Verified **NO path auto-closes a
  degraded/unrecoverable position** (the spec's exchange/ledger-drift
  protection holds); the **staleness math matches the block gate**; **no
  double-close** (the handler sits after SL/TP and the time-stop); and the
  close path **inherits no new price-safety gap**.
- qa-reviewer: 🟢. Full suite **2142 passed (+8)**, 0 failed; `ruff` + `mypy`
  clean. All 8 scenarios covered; confirmed `_stale_position_block_gate` is
  genuinely unchanged.

## Verification

- Full suite: 2142 passed, 0 failed (was 2134; net +8, zero regressions).
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

- **Close path does not consult `reject_if_stale_quote`.** The close path for
  ALL triggers (SL/TP, time-stop, and now stale-age) does not consult the
  `reject_if_stale_quote` guard, which today protects only entry/proposal
  execution. This is a **pre-existing project-wide property, not a regression**
  introduced by stale-age — the new handler closes through the same close
  machinery as the other triggers. If close-side stale-quote protection is
  wanted, it belongs in the shared close path rather than bolted onto stale-age
  alone, and is a design question for a separate ticket (filed as a DEBT-068(e)
  follow-up note below). Flagged by quant-trader-expert.
- **Stale events are not yet surfaced on the dashboard or fed to the safety
  score.** `STALE_POSITION_DETECTED` / `STALE_POSITION_AUTO_CLOSED` are emitted
  to the activity log but are not yet rendered on the command center nor wired
  into runtime-safety-score inputs. Until that lands (aligned with the deferred
  (g)/(h) surfaces), the stale-action signal is activity-log-only.

## TECH-DEBT Items

DEBT-068(e) ships the **runtime stale-position actions** (`auto_close`,
`alert_only`, plus the `block_new_entries` visibility event). The DEBT-068
umbrella remains Active. Two follow-ups filed this cycle:

- **(e-note-close-stale-quote)** (quant, optional, project-wide) — the close
  path for ALL triggers does not consult `reject_if_stale_quote`; if close-side
  stale-quote protection is wanted it belongs in the shared close path, not on
  stale-age alone. Not a regression — pre-existing project-wide property.
  Separate ticket / design question.
- **(e-followup-dashboard)** (dev) — surface `STALE_POSITION_DETECTED` /
  `STALE_POSITION_AUTO_CLOSED` on the dashboard command center and feed
  runtime-safety-score inputs (aligns with deferred (g)/(h)).

The DEBT-068(e) sub-item is annotated SHIPPED (runtime actions) in the umbrella.

## Remaining Work

DEBT-068 remains Active. Deferred follow-ups, all still open:

- **(c-arb)** `cap_resolution=lowest_priority_loses` arbitration for global
  `(symbol, side)` caps — separate slice. **Candidate next slice** (closes the
  last open-cap v1-arbitration gap left by (b)).
- **(f)** dashboard cross-account risk exposure panel + the operator-freeze
  toggle WRITE side.
- **(g)** dedicated `RISK_KILL_SWITCH_TRIPPED` / `RISK_CAP_ADVISORY`
  `ActivityEventType` (and surfacing of the new stale event types).
- **(h)** `runtime-safety-score` kill-switch + stale-event integration.

No ADR needed — this slice implements the already-decided stale-position-action
contract from the cross-account-risk-policy functional-design spec
(`stale_position_action`: `auto_close` / `block_new_entries` / `alert_only`,
plus the "Coordination with runtime-reconciliation" resolution rules). The
no-auto-close-on-degraded/unrecoverable constraint and the after-SL/TP-and-
time-stop slotting follow directly from the spec; they introduce no new
component boundary and no new long-term constraint, so no architecture decision
record is warranted.

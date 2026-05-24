# Session: cross-account-risk-policy CROSS-ACCOUNT RISK DASHBOARD PANEL (DEBT-068(f-1) read-only panel)

Date: 2026-05-24
Units: `cross-account-risk-policy` / `dashboard-operator-ui`
Stage: Code Generation
Related debt: DEBT-068(f) — the dashboard slice now SPLIT into (f-1) read-only
panel [SHIPPED, this log] and (f-2) operator-freeze toggle WRITE side [OPEN].
Also resolves the (g-note-dashboard-undercount) "Rejected"-column undercount.
Related requirements: FR-036, FR-037, FR-038, FR-044, NFR-007, NFR-008, NFR-012

> Same-unit dashboard sibling to the eight runtime/policy `cross-account-risk-policy`
> logs that precede it (DEBT-068(b) opt-in caps, (c-1)/(c-2) kill switches,
> (c-arb) cap arbitration, (d) operator-freeze runtime read side, (e) stale
> actions, (g) risk event types). Those all shipped the runtime / policy halves;
> this log covers the FIRST dashboard slice — the read-only Cross-Account Risk
> panel that surfaces the accumulated risk machinery to the operator. Uncommitted
> on `main` at the time of writing; committed immediately after.

## Scope

DEBT-068(f) was always the dashboard slice. It is now SPLIT so the read side and
the write side ship separately and unambiguously:

- **(f-1) — read-only Cross-Account Risk panel. SHIPPED this cycle.** Per-account
  risk table, portfolio cap-utilization bands, symbol/side exposure, risk-gate
  event feed, and a READ-ONLY operator-freeze STATE indicator. Plus the
  (g-note-dashboard-undercount) "Rejected"-column fix.
- **(f-2) — operator-freeze toggle WRITE side. STILL OPEN.** The interactive
  widget that WRITES `trading_freeze` back to `config/runtime_flags.yaml` with a
  confirmation step. Correctly DEFERRED — (f-1) ships only the read-only
  freeze-STATE indicator, never a writer.

All new code is in `src/dashboard/pages/engine.py`, event-driven, and follows the
established **reconciliation-banner pattern**: pure `build_*` functions that take
parsed activity events and return dataframes / state objects, with thin `render_*`
wrappers that only call Streamlit. The panel never invents fields, never crashes
on empty or partial data, and reads details defensively.

## Changes — DEBT-068(f-1) Cross-Account Risk dashboard panel (read-only)

All in `src/dashboard/pages/engine.py`:

- **`build_cross_account_risk_dataframe`** — per-account equity / realized-today /
  unrealized / stop-risk / notional + kill-switch state, assembled from risk-gate
  event details.
- **`kill_switch_state_for_account`** — resolves the per-account kill-switch state
  shown in the table.
- **`build_portfolio_cap_utilization`** — GREEN / AMBER / RED / BREACH bands at
  70 / 90 / 100% thresholds, **lower-inclusive** (a value AT a threshold takes the
  higher band), **breach is strictly > 100%**.
- **`build_symbol_side_exposure_dataframe`** — distinct-account count + total
  notional + closest cap per `(symbol, side)`.
- **`build_risk_gate_events_dataframe`** — the risk-gate event feed.
- **`build_operator_freeze_state`** — READ-ONLY freeze-STATE indicator (reflects
  the runtime read-side flag; does NOT write).
- **`render_cross_account_risk`** — thin render wrapper, wired into `render()`.
- **(g-note) Rejected-column fix** — a shared `_genuine_rejection_events` helper
  now counts hard blocks ONCE: live kill-switch trips de-duplicated by
  `proposal_id`, operator-freeze events self-counted, paper advisories excluded.
  This resolves the (g-note-dashboard-undercount) drift the (g) event-type
  migration introduced.

## Review

- qa-reviewer: 🟢. Full suite **2169 passed (+14)**, 0 failed; `ruff` + `mypy`
  clean. Verified the **Rejected-column rule against the engine emission paths**
  (no double-count: live kill-switch counted once via `proposal_id` dedup; paper
  advisories excluded; operator-freeze counted once). Confirmed **`build_*`
  purity**, **empty-data safety**, and **defensive details access** throughout.
- No quant escalation — no trading-math and no `src/trading` code was touched
  (dashboard read-only assembly over already-emitted activity events).

## Verification

- Full suite: 2169 passed, 0 failed (was 2156; net +14, zero regressions).
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

- **No steady-state on quiet cycles (KEY LIMITATION — dev + qa both flagged).**
  The engine has NO dedicated portfolio-snapshot `ActivityEvent` —
  `_record_portfolio_snapshot` writes to `PortfolioTracker` (`data/performance`),
  not the activity log. So the panel's per-account metrics + cap-utilization
  populate ONLY from risk-gate event details that fired on a breach. An account or
  cap that never tripped shows "n/a" / empty — there is no steady-state equity /
  PnL / 0%-utilization row on a quiet cycle. Fields are never invented and never
  crash. A dedicated per-cycle portfolio-snapshot (or "caps configured / current
  totals") `ActivityEvent` would let the panel show steady-state equity / PnL and
  0%-utilization rows. Filed as DEBT-068(f-1-note-snapshot-event).

- **Read-only freeze indicator only.** The panel surfaces the freeze STATE but
  cannot engage it — the operator still edits `config/runtime_flags.yaml` on disk
  (runtime read side shipped under (d)). The interactive toggle that writes the
  flag back is DEBT-068(f-2) and is not built.

## TECH-DEBT Items

DEBT-068(f) is now split into **(f-1) read-only panel [SHIPPED this cycle]** and
**(f-2) operator-freeze toggle write-side [OPEN]** in the umbrella. The
(g-note-dashboard-undercount) "Rejected"-column undercount is marked **RESOLVED**
by this cycle's shared `_genuine_rejection_events` helper. One new follow-up filed:
(f-1-note-snapshot-event) — a dedicated per-cycle portfolio-snapshot `ActivityEvent`
so the panel can show steady-state metrics on quiet cycles. DEBT-068 umbrella
remains Active for (f-2) and (h).

## Remaining Work

DEBT-068 remains Active. Remaining after (f-1):

- **(f-2)** operator-freeze toggle WRITE side — interactive widget that writes
  `config/runtime_flags.yaml` + confirmation. **Candidate next slice.**
- **(h)** `runtime-safety-score` kill-switch + stale-event integration — smaller,
  bundles after (f-2).

No ADR needed — this slice surfaces already-decided risk machinery onto the
dashboard using the established reconciliation-banner pure-`build_*` / thin-`render_*`
pattern. It introduces no new component boundary and no new long-term constraint;
the band thresholds (70/90/100, lower-inclusive, breach > 100) and the
read-only-vs-write split follow directly from the (f) umbrella description, so no
architecture decision record is warranted.

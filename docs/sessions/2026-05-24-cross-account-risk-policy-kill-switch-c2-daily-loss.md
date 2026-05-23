# Session: cross-account-risk-policy STATEFUL daily-loss kill switch (DEBT-068(c-2))

Date: 2026-05-24
Units: `cross-account-risk-policy`
Stage: Code Generation
Related debt: DEBT-068(c-2) — COMPLETES DEBT-068(c)
Related requirements: FR-036, FR-037, FR-038, FR-044, NFR-007, NFR-008, NFR-012

> Third same-day session log on the `cross-account-risk-policy` unit, distinct
> from both siblings:
> `docs/sessions/2026-05-24-cross-account-risk-policy-opt-in-global-caps.md`
> (DEBT-068(b), opt-in global exposure caps, commit `a088e17`) and
> `docs/sessions/2026-05-24-cross-account-risk-policy-kill-switch-c1.md`
> (DEBT-068(c-1), the STATELESS kill-switch gates). This log covers the
> STATEFUL half — DEBT-068(c-2), the realized daily-loss kill switch — which
> **completes the full DEBT-068(c) kill-switch slice**. Uncommitted on `main`
> at the time of writing; committed immediately after.

## Scope

DEBT-068(c-2) ships the **stateful** half of the DEBT-068(c) kill-switch slice:
the per-account and portfolio realized daily-loss kill switches. These trip on
realized PnL accumulated since UTC midnight — the half that c-1 explicitly
deferred because it depends on reading closed-trade history rather than the
current cycle's reconstruction of open positions and equity.

The defining design choice is **equity reconstruction with no state file**.
Rather than snapshotting start-of-day equity to disk, the gate reconstructs it
each cycle from persisted closed-trade history:
`starting_equity_today = current_quote_balance - realized_pnl_today`. The
realized-PnL term is recovered by summing `TradeHistory.pnl` for closed trades
whose `exit_time >= UTC midnight today`. This identity recovers true
start-of-day equity exactly (the current balance already reflects today's
realized PnL, so subtracting it backs out to the morning baseline), which means
the gate **survives a process restart with zero persisted kill-switch state** —
it re-derives everything from the trade ledger on disk. This continues the
reconstruction baseline locked in for c-1 (and DEBT-068(b) before it) rather
than introducing a daily-loss state file.

The trip condition is
`realized_pnl_today < -(daily_loss_limit_pct * starting_equity_today)`. Both
gates run **ahead of** their c-1 stateless siblings: `_account_daily_loss_check`
is the first check inside `_account_kill_switch_gate` (before c-1's open
drawdown / stop-risk), and `_portfolio_daily_loss_check` is the first check
inside `_global_kill_switch_gate`. This daily-loss-before-drawdown ordering is
deliberate — a realized loss already booked to the ledger is a stronger,
already-crystallized signal than open unrealized drawdown, so it should surface
first when both would trip.

## Changes — DEBT-068(c-2) stateful daily-loss kill switch

- `src/runtime/engine.py`
  - **`_utc_midnight_today`** — returns UTC midnight of the current day, the
    lower bound for the realized-PnL window.
  - **`_realized_pnl_today`** — sums persisted `TradeHistory.pnl` for closed
    trades with `exit_time >= UTC midnight`. Applies `ensure_utc()` coercion to
    each `exit_time` before comparison (legacy-naive read tolerance, consistent
    with the Phase 21 UTC contract), and **excludes None/open rows** so an open
    position or a malformed closed row cannot perturb the realized sum.
  - **`_account_daily_loss_check`** — per-account realized daily-loss check, run
    **at the top of `_account_kill_switch_gate`**, ahead of the c-1 stateless
    open-drawdown / stop-risk checks. Trips when
    `realized_pnl_today < -(daily_loss_limit_pct * starting_equity_today)` with
    `starting_equity_today = current_quote_balance - realized_pnl_today`
    (reconstruction — no state file, survives restart). Inert when
    `daily_loss_limit_pct` is `None`.
  - **`_portfolio_daily_loss_check`** — portfolio realized daily-loss check, run
    **at the top of `_global_kill_switch_gate`**, ahead of the c-1 portfolio
    open-drawdown check. Sums realized PnL across enabled sub-accounts under the
    v1 single-quote-currency assumption (see below). Inert unless
    `GlobalRiskPolicy.enabled`.
  - A code comment was added documenting the **cross-midnight fee-attribution
    approximation** (see Potential Risks).
- `src/proposal/interaction.py`
  - Two new `ProposalFinalState` terminals:
    `GATE_REJECTED_DAILY_LOSS_KILL_SWITCH`,
    `GATE_REJECTED_PORTFOLIO_DAILY_LOSS_KILL_SWITCH`.
- `src/proposal/funnel.py`
  - Funnel count buckets + label/count wiring for the two new terminals.
- `tests/`
  - 10 new tests.

The lead decisions applied this slice: **equity reconstruction (no state
file)** — daily start-of-day equity is recomputed each cycle from the trade
ledger rather than snapshotted, so the gate survives restart; **paper mode is
advisory-only** — daily-loss kill switches emit an event but do NOT halt paper
labs, preserving per-account paper-lab measurement (inherits the c-1
asymmetry); **config-driven inert-when-None** — per-account gate is inert when
`daily_loss_limit_pct` is `None`; **global inert unless
`GlobalRiskPolicy.enabled`**; and the **v1 single-quote-currency assumption** —
sub-accounts whose quote currency does not match are skipped from the portfolio
sum with a warning rather than being naively summed in a foreign denomination.

## Review

- quant-trader-expert: verdict "🟢 ship". **Verified the reconstruction identity
  recovers true start-of-day equity** — `starting_equity_today =
  current_quote_balance - realized_pnl_today` correctly backs today's realized
  PnL out of the current balance, with **no PnL double-count**. Residual is a
  **sub-1-USDT fee-timing approximation per cross-midnight trade in the safe
  (trip-earlier) direction** — see Potential Risks; documented in code.
- qa-reviewer: 🟢 ship. Full suite **2117 passed (+10)**, 0 failed; `ruff` +
  `mypy` clean. **All 9 required behaviors covered**, including the UTC-midnight
  boundary, restart-survival-from-disk, fail-open, and the
  daily-loss-before-drawdown ordering.

## Verification

- Full suite: 2117 passed, 0 failed (was 2107; net +10, zero regressions).
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

- **Cross-midnight fee-attribution approximation.** The realized-PnL window
  selects closed trades by `exit_time >= UTC midnight`, and `TradeHistory.pnl`
  is net of fees including the entry fee paid on the prior side of midnight.
  For a trade opened before midnight and closed after, today's realized sum
  therefore absorbs a fee that economically belonged to yesterday. The
  quant-trader-expert quantified this as a sub-1-USDT effect per cross-midnight
  trade, and crucially it biases the gate in the **safe (trip-earlier)**
  direction — the daily-loss figure is marginally more negative than a strict
  same-day-fee attribution would produce, so the kill switch can only fire
  slightly sooner, never later. Documented in a code comment at the
  attribution site. Recorded as a DEBT-068 follow-up note.
- **v1 single-quote-currency assumption.** `_portfolio_daily_loss_check` sums
  realized PnL across enabled sub-accounts assuming a common quote currency.
  Sub-accounts whose quote currency does not match are **skipped from the
  portfolio sum with a warning** rather than summed in a foreign denomination —
  a deliberate v1 narrowing that avoids fabricating a cross-currency total. The
  consequence is that a mixed-quote-currency portfolio's daily-loss gate only
  covers the matching-currency subset. Recorded as a DEBT-068 follow-up note.

## TECH-DEBT Items

DEBT-068(c-2) **completes DEBT-068(c)** — both the c-1 stateless half (shipped
earlier 2026-05-24) and the c-2 stateful daily-loss half are now shipped. The
DEBT-068 umbrella remains Active for (c-arb), (d)–(h). Two new follow-up notes
filed under the DEBT-068 umbrella this cycle:

- **(c-2-note-fee-timing)** cross-midnight fee-attribution approximation —
  `TradeHistory.pnl` for a trade spanning UTC midnight absorbs the
  prior-day entry fee into today's realized sum; sub-1-USDT per cross-midnight
  trade, biased in the safe trip-earlier direction; documented in a code
  comment (quant-trader-expert review note).
- **(c-2-note-quote-currency)** v1 single-quote-currency assumption —
  `_portfolio_daily_loss_check` skips mismatched-quote-currency sub-accounts
  from the portfolio sum with a warning; mixed-currency portfolios only have
  their matching-currency subset covered.

No DEBT item is fully resolved this cycle (DEBT-068(c-2) is a sub-item closing
out the (c) slice; the DEBT-068 umbrella itself remains Active).

## Remaining Work

DEBT-068 remains Active. Deferred follow-ups, all still open:

- **(c-arb)** `cap_resolution=lowest_priority_loses` arbitration for global
  `(symbol, side)` caps — separate slice, not bundled into (c). **Candidate
  next slice.**
- **(d)** operator freeze toggle (reload-per-cycle infrastructure). **Candidate
  next slice.**
- (e) stale `auto_close` / `alert_only` actions.
- (f) dashboard cross-account risk exposure panel.
- (g) dedicated `RISK_CAP_ADVISORY` / `RISK_KILL_SWITCH_TRIPPED`
  `ActivityEventType`.
- (h) `runtime-safety-score` kill-switch integration.

No ADR needed — this slice implements the already-decided kill-switch contract
(the reconstruction equity baseline and the paper-advisory / live-hard-block
asymmetry were both decided at planning, consistent with the DEBT-068(b) and
(c-1) precedents). It does not introduce a new component boundary or a new
long-term constraint; the equity-reconstruction approach is a continuation of
the existing decision, not a new one.

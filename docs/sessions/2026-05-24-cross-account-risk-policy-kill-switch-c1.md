# Session: cross-account-risk-policy STATELESS kill-switch gates (DEBT-068(c-1))

Date: 2026-05-24
Units: `cross-account-risk-policy`
Stage: Code Generation
Related debt: DEBT-068(c-1)
Related requirements: FR-036, FR-037, FR-038, FR-044, NFR-007, NFR-008, NFR-012

> Distinct from the earlier same-day session log
> `docs/sessions/2026-05-24-cross-account-risk-policy-opt-in-global-caps.md`
> (DEBT-068(b), opt-in global exposure caps, commit `a088e17`). This log
> covers the next slice — DEBT-068(c-1), the STATELESS kill-switch gates.
> Uncommitted on `main` at the time of writing; committed immediately after.

## Scope

DEBT-068(c-1) ships the **stateless** half of the DEBT-068(c) kill-switch slice:
the per-account open-position drawdown / stop-risk kill switches and the
portfolio open-drawdown kill switch. These are the gates that can be evaluated
from the current cycle's reconstruction of account equity and open positions
with no persisted state. The **stateful** half — the daily-loss kill switch
(realized-PnL-since-UTC-midnight, restart-survives) — is explicitly deferred to
DEBT-068(c-2) and is the next slice.

The slice continues the `cross-account-risk-policy` unit after the 2026-05-24
DEBT-068(b) opt-in global exposure cap gate.

## Changes — DEBT-068(c-1) stateless kill-switch gates

- `src/runtime/engine.py`
  - **`_account_kill_switch_gate`** — per-account gate evaluating
    open-unrealized-drawdown first, then open-stop-risk, **first breach wins**.
    Inert per-account when the relevant `_pct` threshold is `None`.
  - **`_global_kill_switch_gate`** — portfolio open-drawdown summed across all
    enabled sub-accounts. Inert unless `GlobalRiskPolicy.enabled`.
  - **`_open_stop_risk_sum`** — helper now **shared** with
    `_account_aggregate_cap_gate` (behavior-preserving refactor — the existing
    aggregate-cap stop-risk summation was lifted into this shared helper, no
    semantic change to the cap gate).
  - **`_account_equity`** — quote balance, falling back to
    `CapitalPolicy.sizing_balance`, **fail-open** on missing equity (the gate is
    skipped rather than blocking when equity is unavailable).
  - **`_open_unrealized_pnl`** — reuses `pnl_for_trade` over the synchronous mark
    cache; **excludes stale-mark positions** so a stale mark cannot fabricate a
    drawdown breach.
  - **`_kill_switch_outcome`** — shared outcome helper: paper mode is
    **advisory** (event-only, never halts paper labs), live mode is a
    **hard-block**.
  - Both gates wired into `_handle_proposal` **after the regime gate and before
    sizing/caps**.
- `src/proposal/interaction.py`
  - Three new `ProposalFinalState` terminals:
    `GATE_REJECTED_OPEN_DRAWDOWN_KILL_SWITCH`,
    `GATE_REJECTED_OPEN_STOP_RISK_KILL_SWITCH`,
    `GATE_REJECTED_PORTFOLIO_KILL_SWITCH`.
- `src/proposal/funnel.py`
  - Funnel count buckets + label/count wiring for the three new terminals.
- `tests/`
  - 13 new tests.

The two lead decisions applied this slice were locked in at the planning stage:
**paper mode is advisory-only** — per-account kill switches do NOT halt paper
labs (event-only), preserving the per-account strategy/account performance
measurement that the paper labs exist to provide; and the **equity baseline uses
the reconstruction approach** (no state file) — equity is recomputed from
current balances each cycle rather than snapshotted to disk. The slice is
config-driven with no hardcoded thresholds: per-account gates are inert when the
relevant `_pct` is `None`, and the global gate is inert unless
`GlobalRiskPolicy.enabled`.

## Review

- quant-trader-expert: verdict "sound — ship". Risk math correct. Flagged one
  **non-blocking note**: zero/negative exchange equity hard-blocks in live mode
  (a consequence of fail-open on *missing* equity but treating a present
  zero/negative equity as a real reading) — worth one spec line. Recorded below
  as a TECH-DEBT follow-up.
- qa-reviewer: 🟢 ship. Full suite 2107 passed (+13), 0 failed; `ruff` + `mypy`
  clean. One **non-blocking 🟡 note**: the `_account_equity` exception branch is
  `# pragma: no cover` — the fail-soft behavior is proven elsewhere, but the
  branch itself is not directly exercised. Recorded below as a TECH-DEBT
  follow-up.

## Verification

- Full suite: 2107 passed, 0 failed (was 2097; net +13, zero regressions).
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

- The stateless kill switches reconstruct account equity and open positions each
  time a proposal reaches the gate. As with the DEBT-068(b) global cap, the
  aggregation cost scales with open-position count and sub-account count; the
  global kill switch in particular sums open unrealized PnL across every enabled
  sub-account per proposal. v1 keeps this on the proposal path only (not the
  monitor loop), so the blast radius is bounded, but a future cycle should
  confirm the combined cap + kill-switch cross-account reads do not become a
  hot-path cost once DEBT-068(c-2) adds the stateful daily-loss reads.
- Stale-mark exclusion in `_open_unrealized_pnl` means that when many open
  positions carry stale marks the computed drawdown understates true exposure —
  the gate fails *open* (does not block) in that case. This is the deliberate
  conservative-throughput choice for paper labs, but in live mode it means a
  drawdown breach can go unobserved while marks are stale. The mark cache
  freshness window (DEBT-066) bounds how stale a mark can be before exclusion.

## TECH-DEBT Items

DEBT-068 remains Active — DEBT-068(c-1) is the stateless half of the (c) slice;
the umbrella stays Active for (c-2), (c-arb), (d)–(h). Two new follow-up
sub-bullets filed under the DEBT-068 umbrella this cycle from the reviewer
non-blocking notes:

- **(c-1-note-equity)** zero/negative exchange equity hard-blocks in live mode —
  worth one spec line (quant-trader-expert non-blocking note).
- **(c-1-note-cover)** `_account_equity` exception branch is `# pragma: no
  cover`; fail-soft proven elsewhere but the branch is not directly exercised
  (qa-reviewer 🟡 note).

No DEBT item is fully resolved this cycle.

## Remaining Work

DEBT-068 remains Active. Deferred follow-ups, all still open:

- **(c-2) daily-loss kill switch** — realized-PnL-since-UTC-midnight,
  restart-survives. **NEXT slice.** This is the stateful half of (c); slots were
  reserved this cycle.
- **(c-arb)** `cap_resolution=lowest_priority_loses` arbitration for global
  `(symbol, side)` caps — separate slice, not to be bundled into (c).
- **(d)** operator freeze toggle (reload-per-cycle infrastructure).
- (e) stale `auto_close` / `alert_only` actions.
- (f) dashboard cross-account risk exposure panel.
- (g) dedicated `RISK_CAP_ADVISORY` `ActivityEventType`.
- (h) `runtime-safety-score` kill-switch integration.

No ADR needed — this slice implements the already-decided kill-switch contract
(paper-advisory / live-hard-block asymmetry and the reconstruction equity
baseline were decided at planning, consistent with the DEBT-068(b) precedent);
it does not introduce a new component boundary or a new long-term constraint.

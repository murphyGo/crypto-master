# Session: cross-account-risk-policy opt-in global exposure cap gate (DEBT-068(b)) + robustness-gate strategy coverage

Date: 2026-05-24
Units: `cross-account-risk-policy`, `backtesting-validation`
Stage: Code Generation
Related debt: DEBT-068(b)
Related requirements: FR-036, FR-037, FR-038, FR-044, NFR-007, NFR-008, NFR-012

## Scope

Two pieces of work shipped on `main` this cycle:

1. **Commit `50a7080`** — added `raschke_holy_grail` and `ma_crossover` to the
   robustness gate's `StrategySpec` catalog in `scripts/run_robustness_gate.py`
   and bumped the count assertion in `tests/test_run_robustness_gate.py` from
   7 to 9. Both strategies were verified end-to-end via `--live` against
   BTC/USDT.
2. **Commit `a088e17`** — implemented DEBT-068(b): the opt-in global exposure
   cap gate, the next slice of the `cross-account-risk-policy` unit after the
   2026-05-15 DEBT-068(a) risk-budget sizing wire-in.

## Changes — robustness gate (`50a7080`)

- `scripts/run_robustness_gate.py`
  - Added two `StrategySpec` entries (`raschke_holy_grail`, `ma_crossover`).
- `tests/test_run_robustness_gate.py`
  - Count assertion updated 7 → 9.

Both new strategies FAIL all edge gates, consistent with the standing
no-OHLCV-only-edge finding (strategies are ~breakeven on price data alone).
`raschke_holy_grail` correctly SKIPs the sensitivity gate — it carries
module-level constant knobs and exposes no `param_grid`, so there is nothing for
the sensitivity sweep to perturb. `ma_crossover` does exercise the sensitivity
gate via a short/long moving-average period grid.

## Changes — DEBT-068(b) opt-in global cap gate (`a088e17`)

- `src/trading/sub_account.py`
  - `GlobalRiskPolicy` gained opt-in `enabled` / `paper_mode` / `live_mode`
    fields. `enabled` defaults false; unset caps are inert.
- `src/proposal/interaction.py`
  - New `ProposalFinalState.GATE_REJECTED_GLOBAL_CAP` terminal.
- `src/proposal/funnel.py`
  - New `FunnelCounts.gate_rejected_global_cap` bucket + label/count wiring.
- `src/runtime/engine.py`
  - New `_global_aggregate_cap_gate`, wired into `_handle_proposal` after the
    per-account `_account_aggregate_cap_gate` and `_stale_position_block_gate`
    gates (and after `_correlation_gate`), per the functional-design spec
    ordering. It aggregates open positions across all sub-accounts and enforces
    `max_open_positions_per_symbol_side`, `max_gross_notional_per_symbol_side`,
    and `max_gross_notional_per_symbol`. Opt-in (default disabled / inert):
    paper mode is advisory-with-event and never blocks; live mode hard-blocks
    only when explicitly enabled. v1 arbitration is `first_come_first_serve`.
- `tests/`
  - 7 engine gate tests + 3 config-parsing tests (10 total).

The gate is the cross-sub-account counterpart to the per-account aggregate cap.
The paper/live asymmetry is deliberate and was locked in at the 2026-05-24
planning session (`docs/sessions/2026-05-24-cross-account-risk-policy-opt-in-global-caps-plan.md`):
paper accounts are used to measure per-account strategy/account performance
independently, so a global cap must never silently suppress paper-lab
throughput — it emits would-block evidence and continues. Live mode is the only
path that hard-blocks, and only when the operator has explicitly enabled the
global policy.

## Review

- quant-trader-expert: verdict "sound — ship". Risk math correct; no
  double-counting and no off-by-one in the cross-account aggregation.
- qa-reviewer: 🟢 ship. Full suite 2097 passed, 0 failed; `ruff` + `mypy`
  clean.

## Verification

- `uv run pytest tests/test_trading_sub_account.py tests/test_trading_sub_account_registry.py tests/test_runtime_engine.py -q`
  - Result: 189 passed (DEBT-068(b) opt-in global cap behavior).
- Full suite: 2097 passed, 0 failed.
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

- The global cap aggregates open positions across all sub-accounts each time a
  proposal reaches the gate. As the traded-symbol universe and sub-account count
  grow, the aggregation cost scales with open-position count. v1 keeps this on
  the proposal path only (not the monitor loop), so the blast radius is bounded,
  but a future cycle should confirm the aggregation does not become a hot-path
  cost once kill switches ((c)) introduce additional cross-account state reads.
- v1 arbitration is `first_come_first_serve`: when two sub-accounts race toward
  the same symbol/side cap, the first proposal through the gate wins and later
  ones are rejected/advised. The `cap_resolution=lowest_priority_loses`
  arbitration that would make this deterministic by account priority is
  deferred and is the one item below flagged as not-yet-ticketed.

## TECH-DEBT Items

None new. DEBT-068(b) is a sub-slice close-out of the still-open DEBT-068
umbrella — the umbrella stays Active for (c)–(h). No DEBT item is fully resolved
this cycle (the umbrella tracks the whole Slice 2).

## Remaining Work

DEBT-068 remains Active. Deferred follow-ups, all still open:

- (c) per-account + portfolio kill switches (`daily_loss_limit_pct`,
  `open_drawdown_limit_pct`, portfolio variants) — also the documented home for
  the `cap_resolution=lowest_priority_loses` arbitration upgrade.
- (d) operator freeze toggle (reload-per-cycle infrastructure).
- (e) stale `auto_close` / `alert_only` actions.
- (f) dashboard cross-account risk exposure panel.
- (g) dedicated `RISK_CAP_ADVISORY` `ActivityEventType` (paper-mode advisories
  currently reuse `PROPOSAL_REJECTED + details.advisory=True`).
- (h) `runtime-safety-score` kill-switch integration.

Flagged for the lead: `cap_resolution=lowest_priority_loses` arbitration is
deferred but not explicitly ticketed in the DEBT-068 umbrella description (the
construction plan attributes it to DEBT-068(c); the TECH-DEBT entry's (c) bullet
does not yet name it). Recommend the planner add an explicit sub-bullet so it is
not lost.

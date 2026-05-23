# Code Generation Plan: cross-account-risk-policy

## Task

Implement the existing `cross-account-risk-policy` functional design:
risk-based sizing, per-account exposure caps, opt-in global exposure caps,
stale-position age caps, account/global kill switches, an operator manual
freeze, and the dashboard exposure panel.

## Related Context

- Unit: `cross-account-risk-policy`
- Stage: Code Generation
- Requirements: FR-036, FR-037, FR-038, FR-044, NFR-007, NFR-008, NFR-012
- Functional design:
  `aidlc-docs/construction/cross-account-risk-policy/functional-design/spec.md`
- Source evidence: 2026-05-13 Fly snapshot showed 49,000 USDT gross open
  notional, concentrated ETH longs / BNB shorts / AVAX shorts across many
  paper accounts, fixed 1,000 USDT sizing, and stop-risk dispersion across
  strategies.
- Related units: `sub-account-capital-segmentation`,
  `strategy-correlation-governor`, `runtime-safety-score`,
  `runtime-reconciliation`, `proposal-runtime`, `dashboard-operator-ui`,
  `dashboard-operator-command-center`

## Steps

- [x] Extend `RiskPolicy` with sizing, cap, kill-switch, and stale-position
      fields; add `GlobalRiskPolicy` and operator freeze flag.
      (Slice 1 — 2026-05-13: all new RiskPolicy fields, GlobalRiskPolicy
      block + registry parsing.)
- [ ] Add `RuntimeRiskPolicy` resolver and a pure sizing helper.
      (Slice 1 partial — `src/trading/risk_sizing.py` pure
      `compute_risk_budget_size` helper landed with 5 structured
      `RiskSizingRejection` modes and full unit-test coverage. Slice 2a
      — 2026-05-15: `TradingEngine._risk_budget_sizing_gate` now calls
      the helper for `sizing_mode='risk_budget'`, rewrites
      `proposal.quantity` before downstream gates, rejects structured
      sizing failures with `gate_rejected_risk_sizing`, and removed the
      temporary config-time `_reject_risk_budget_mode_until_wired_in`
      validator. The `RuntimeRiskPolicy` resolver is still deferred
      with the global-cap / kill-switch gate wiring it backs; current
      gates read off the frozen `SubAccount.risk_policy` directly.)
- [ ] Wire the new gates into `_handle_proposal` in the order documented in
      the spec. (Slice 1 partial — 2 of 5 planned gates shipped:
      `_account_aggregate_cap_gate` (notional + stop-risk) and
      `_stale_position_block_gate`, both wired after the symbol-cap
      gate with paper-advisory-with-event / live-hard-block semantics;
      3 new `ProposalFinalState` terminals
      (`gate_rejected_account_aggregate_cap`,
      `gate_rejected_stale_position_block`,
      `gate_rejected_risk_sizing`); R2 wrapped `trade.entry_time` in
      `ensure_utc()` at the stale-block gate per Q5 UTC defense.
      Opt-in global symbol/side caps, per-account + portfolio kill switches,
      and operator freeze toggle deferred under DEBT-068(b)/(c)/(d).
      Risk-sizing gate shipped 2026-05-15 under DEBT-068(a).)
- [ ] Implement DEBT-068(b) as an opt-in global exposure cap gate.
      `GlobalRiskPolicy.enabled` defaults false; unset caps are inert. In paper
      mode, enabled global caps emit advisory / would-block evidence only and
      never block execution, preserving per-account strategy lab measurements.
      In live mode, explicitly enabled global caps hard-block proposals that
      breach `max_open_positions_per_symbol_side`,
      `max_gross_notional_per_symbol_side`, or
      `max_gross_notional_per_symbol`.
- [ ] Add new `ActivityEventType` values and surface them on the dashboard
      command center and through runtime-safety-score inputs.
      (Deferred to Slice 2. Paper-mode advisories currently reuse
      `PROPOSAL_REJECTED + details.advisory=True` per Q2 docstring-honesty
      fix; dedicated `RISK_CAP_ADVISORY` event type tracked under
      DEBT-068(g). `runtime-safety-score` kill-switch integration
      tracked under DEBT-068(h).)
- [ ] Add the Cross-Account Risk dashboard panel and the operator freeze
      toggle. (Deferred to Slice 2 under DEBT-068(f); operator freeze
      toggle reload-per-cycle infrastructure deferred under
      DEBT-068(d).)
- [ ] Add tests for sizing math, config parsing, gate ordering, kill-switch
      lifecycle, stale-position actions, and dashboard rendering.
      (Slice 1 partial — sizing-math, config-parsing, per-account
      aggregate cap gate (live + paper advisory + over-stop-risk +
      no-caps no-op + under-caps pass), stale-position block gate
      (live + paper advisory + alert-only no-op + fresh-trade pass),
      `_reject_risk_budget_mode_until_wired_in` validator regression,
      and naive-tz stale-block defense shipped (+29 tests, 1978 →
      2007). Kill-switch lifecycle, global-cap gating, and dashboard
      rendering deferred to Slice 2. DEBT-068(b) must add regressions for
      default-disabled behavior, paper advisory/pass-through behavior, and live
      hard-block behavior.)

## Verification

- [x] `uv run pytest tests/test_trading_risk_sizing.py tests/test_trading_sub_account.py tests/test_runtime_engine.py -q`
- [x] `uv run pytest tests/test_trading_sub_account_registry.py -q`
- [ ] `uv run pytest tests/test_trading_sub_account.py tests/test_trading_sub_account_registry.py tests/test_runtime_engine.py -q`
      for DEBT-068(b) opt-in global cap behavior.
- [ ] Targeted dashboard tests for the cross-account risk panel and operator
      freeze toggle.
- [ ] Targeted runtime-safety-score tests for kill-switch event propagation.

## Completion Checklist

- [ ] Code implemented.
- [ ] Tests pass.
- [ ] Session log and cross-check added.
- [ ] `aidlc-docs/aidlc-state.md` updated.

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
- [ ] **DEBT-068(c) — per-account + global kill switches.** Wire the kill-switch
      gates documented in the spec §"Kill Switches" into `_handle_proposal`,
      reading off the frozen `SubAccount.risk_policy` / `GlobalRiskPolicy`
      (model fields already shipped Slice 1). Established paper-advisory /
      live-hard-block convention. Realized-PnL-since-UTC-midnight state survives
      restart (recomputed from persisted trade history at startup); drawdown /
      stop-risk gates are stateless per cycle. Operator manual freeze is
      explicitly OUT of scope here — tracked under DEBT-068(d). Items:
  - [x] Per-account daily-loss kill switch — block new entries when realized
        PnL since UTC midnight on the sub-account is worse than
        `-daily_loss_limit_pct * starting_equity_today`. State recomputed from
        persisted trade history at startup so a restart cannot escape the
        limit; auto-releases at next UTC-midnight rollover. New gate in
        `src/runtime/engine.py::_handle_proposal` between operator-freeze (d)
        and the per-account open-risk gates, per spec Runtime-Behavior order.
        (DEBT-068(c-2) — 2026-05-24: `_account_daily_loss_check` runs at the
        TOP of the existing combined `_account_kill_switch_gate` (ahead of the
        c-1 drawdown / stop-risk checks), so the `_handle_proposal` wiring is
        untouched. `starting_equity_today` reconstructed as
        `current_quote_balance - realized_pnl_today` — NO state file (lead
        decision); equity via the c-1 `_account_equity` (unavailable ⇒
        fail-open). `realized_pnl_today` from `_realized_pnl_today` summing
        signed net `TradeHistory.pnl` over closed trades with
        `exit_time >= utc_midnight_today` (coerced via `ensure_utc`). Live
        hard-block / paper advisory via shared `_kill_switch_outcome`.)
  - [x] Per-account open-drawdown / open-stop-risk kill switches — stateless
        per cycle: block when open unrealized PnL is worse than
        `-open_unrealized_drawdown_limit_pct * equity`, or when summed
        `abs(entry - stop) * qty` over open positions exceeds
        `open_stop_risk_limit_pct * equity`. Auto-release when the metric
        recovers. (DEBT-068(c-1) — 2026-05-24: combined
        `TradingEngine._account_kill_switch_gate` (drawdown then
        stop-risk, first breach wins) wired into `_handle_proposal`
        AFTER the regime gate and BEFORE `_risk_budget_sizing_gate`.
        Equity from `trader.get_balances()` → quote currency, fallback
        `CapitalPolicy.sizing_balance`; unavailable ⇒ skip (fail-open).
        Unrealized PnL reuses `pnl_for_trade` over the synchronous
        mark-price cache (stale-symbol positions excluded). Stop-risk
        numerator factored into shared `_open_stop_risk_sum` (also used
        by `_account_aggregate_cap_gate`). Paper = advisory-with-event;
        live = hard-block.)
  - [x] Global (portfolio) daily-loss / open-drawdown kill switches —
        `portfolio_daily_loss_limit_pct` / `portfolio_unrealized_drawdown_limit_pct`
        computed over the sum of all enabled sub-account equity + PnL in the
        common quote currency; a trip blocks new entries on all sub-accounts.
        (DEBT-068(c-1) — 2026-05-24: open-drawdown portion shipped as
        `_global_kill_switch_gate` (inert unless
        `GlobalRiskPolicy.enabled` AND
        `portfolio_unrealized_drawdown_limit_pct` set; equity summed via
        `_account_equity` per enabled sub, no usable equity ⇒ fail-open;
        unrealized via `_open_unrealized_pnl` over
        `_open_trades_for_correlation`).
        DEBT-068(c-2) — 2026-05-24: `portfolio_daily_loss_limit_pct` half
        shipped as `_portfolio_daily_loss_check`, run at the TOP of
        `_global_kill_switch_gate` (ahead of the portfolio drawdown check).
        `portfolio_realized_pnl_today` = Σ `_realized_pnl_today` and
        `portfolio_starting_equity_today` = Σ
        `(current_quote_balance - realized_pnl_today)`, accumulated in the
        single existing `list_active()` pass. v1 single-quote-currency: a
        sub-account whose quote currency differs from the first active
        account's is skipped with a one-line warning.)
  - [ ] New `ProposalFinalState` terminals for each kill-switch reject
        (mirroring the Slice 1 `gate_rejected_account_aggregate_cap` /
        `gate_rejected_stale_position_block` pattern) + funnel label/count
        wiring. Paper-mode advisories reused `PROPOSAL_REJECTED +
        details.advisory=True` per the Slice 2a convention; the dedicated
        `RISK_CAP_ADVISORY` / `RISK_KILL_SWITCH_TRIPPED` event types SHIPPED
        2026-05-24 under DEBT-068(g) (event-type migration only — the four risk
        paper/live emission sites now use the dedicated values; the
        `details.advisory=True` discriminator is preserved and `final_state` /
        funnel are unchanged).
        (DEBT-068(c-1) — 2026-05-24: three stateless terminals added —
        `GATE_REJECTED_OPEN_DRAWDOWN_KILL_SWITCH`,
        `GATE_REJECTED_OPEN_STOP_RISK_KILL_SWITCH`,
        `GATE_REJECTED_PORTFOLIO_KILL_SWITCH` — with matching
        `FunnelCounts` fields, `_STATE_TO_FIELD` entries, and inclusion
        in the `gate_rejected_total` sum. Daily-loss terminal pending
        under DEBT-068(c-2).
        DEBT-068(c-2) — 2026-05-24: two daily-loss terminals added —
        `GATE_REJECTED_DAILY_LOSS_KILL_SWITCH` (gate_reason
        `daily_loss_kill_switch`) and
        `GATE_REJECTED_PORTFOLIO_DAILY_LOSS_KILL_SWITCH` (gate_reason
        `portfolio_daily_loss_kill_switch`) — with matching `FunnelCounts`
        fields, `_STATE_TO_FIELD` entries, and inclusion in
        `gate_rejected_total`.)
  - [x] Add the daily-loss restart-recompute helper (realized PnL aggregated
        since UTC midnight from persisted trade history) under `src/trading/`
        and wire it into engine startup.
        (DEBT-068(c-2) — 2026-05-24: DEVIATION from the "`src/trading/` helper
        + engine-startup wiring" wording. Per the lead's reconstruction
        decision there is NO startup step and NO separate helper module:
        `TradingEngine._realized_pnl_today` recomputes the figure from the
        per-account on-disk trade tracker EVERY cycle inside the gate, so the
        limit is enforced continuously and survives restart with no state
        file. Adding a startup pre-warm would be redundant and is intentionally
        omitted.)
  - [x] Write unit tests — daily-loss trip + UTC-rollover auto-release +
        restart-preservation; open-drawdown and open-stop-risk trip /
        auto-release; global daily-loss + open-drawdown trip blocking all
        accounts; gate-evaluation order relative to existing gates;
        paper-advisory-vs-live-hard-block for each. (`tests/test_runtime_engine.py`,
        `tests/test_trading_sub_account.py`.)
        (DEBT-068(c-2) — 2026-05-24: +10 daily-loss tests in
        `tests/test_runtime_engine.py` — per-account not-tripped / tripped-live
        / paper-advisory / UTC-midnight window boundary (before-excluded vs
        after-trips) / restart-survival (real on-disk tracker rebuilt) /
        equity-unavailable fail-open / daily-loss-before-open-drawdown ordering
        / inert-when-pct-None; portfolio daily-loss summed-across-accounts live
        block + inert-when-disabled.)
        (DEBT-068(c-1) — 2026-05-24: +13 tests in
        `tests/test_runtime_engine.py` — open-drawdown not-tripped /
        tripped-live / paper-advisory / stale-mark-excluded;
        open-stop-risk tripped-live with gate_reason distinct from
        `account_aggregate_cap` and short-circuiting before it; inert
        when both `_pct` None; equity-unavailable fail-open no-event;
        global portfolio-drawdown live block + cross-account equity sum
        + inert-when-disabled. Daily-loss trip / UTC-rollover /
        restart-preservation tests deferred to DEBT-068(c-2).)
- [x] **DEBT-068(c-arb) — `cap_resolution=lowest_priority_loses` arbitration
      for global `(symbol, side)` caps. SHIPPED 2026-05-24 (uncommitted on
      `main` at plan-update time; committed immediately after). COMPLETES the
      last open-cap v1-arbitration gap left by (b).** DEBT-068(b) shipped
      `_global_aggregate_cap_gate` with `first_come_first_serve` (FCFS) v1 only
      (spec §"Symbol/Side Caps", gate step 7); this slice adds the reserved
      `lowest_priority_loses` mode. Breach detection (the cross-sub-account
      exposure aggregation) is UNCHANGED — an arbitration step now decides
      `block_overall`. SOFT-ceiling semantics (per quant design): a breaching
      proposal is ADMITTED iff, for EVERY breached cap, the proposing account
      strictly outranks at least one OTHER (self-excluded) holder on that cap's
      key (`account_priority`: earlier = higher priority, unlisted = lowest);
      AND-conservative across multiple breached caps (any cap that arbitrates to
      block ⇒ block — a more-permissive broad cap can never override a stricter
      narrow-cap block). FCFS preserved bit-for-bit. FCFS-equivalent fallbacks:
      empty `account_priority`, unlisted proposer, `sub_account` None /
      single-account, no existing holders on the key. Admitted LIVE overshoot
      emits an informational `RISK_CAP_ADVISORY` (`advisory=False`) with
      `cap_overshoot` — soft-ceiling admission is not silent. Additive `details`
      fields only (`cap_resolution`, `arbitration_outcome`, `proposer_account`,
      `proposer_rank`, `proposer_listed`, `existing_holders`,
      `arbitration_by_cap`, `cap_overshoot`); no `final_state` / funnel change.
      +14 tests; full suite 2156 passed (+14), 0 failed; ruff + mypy clean;
      quant-trader-expert 🟢 "sound — ship" (design conformance confirmed; the
      superset relationship between the per-`(symbol, side)` and per-`symbol`
      keys verified strictly safe under AND-conservative composition), qa-reviewer
      🟢 (FCFS bit-for-bit preserved, all 7 pre-existing global-cap tests pass
      unchanged, funnel / `final_state` unchanged). One MINOR non-blocking
      follow-up filed as (c-arb-note-overshoot-units) — `cap_overshoot`
      mixes units when a COUNT cap and a NOTIONAL cap breach together; harmless
      (advisory DISPLAY-only, never read by any decision path), tied to (f).
      Session log
      `docs/sessions/2026-05-24-cross-account-risk-policy-cap-arbitration-c-arb.md`.
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
- [x] Implement DEBT-068(b) as an opt-in global exposure cap gate.
      (2026-05-24: `GlobalRiskPolicy.enabled`/`paper_mode`/`live_mode`
      fields added; new `_global_aggregate_cap_gate` wired into
      `_handle_proposal` after `_stale_position_block_gate` — i.e. after
      per-account caps and after `_correlation_gate` (line ~1160), per
      spec ordering. first_come_first_serve v1; `lowest_priority_loses`
      arbitration deferred to DEBT-068(c). New
      `ProposalFinalState.GATE_REJECTED_GLOBAL_CAP` terminal + funnel
      label/count wiring. +9 tests.)
      `GlobalRiskPolicy.enabled` defaults false; unset caps are inert. In paper
      mode, enabled global caps emit advisory / would-block evidence only and
      never block execution, preserving per-account strategy lab measurements.
      In live mode, explicitly enabled global caps hard-block proposals that
      breach `max_open_positions_per_symbol_side`,
      `max_gross_notional_per_symbol_side`, or
      `max_gross_notional_per_symbol`.
- [x] **DEBT-068(e) — stale-position `auto_close` / `alert_only` actions.
      SHIPPED 2026-05-24.** (Split out so the runtime stale-action
      implementation is unambiguously marked shipped — the dashboard-surfacing
      and safety-score halves stay open under the two checkboxes below and
      under (f)/(h).) Two new methods in `src/runtime/engine.py`:
      `_classify_trade_reconciliation` (resolves the open trade's
      `runtime-reconciliation` state) and `_maybe_stale_age_action` (dispatches
      per `stale_position_action`), slotted into `_monitor` as a fallback AFTER
      the SL/TP check and the per-strategy time-stop — no double-close.
      `auto_close` closes at market with a `POSITION_CLOSED` event
      (`reason="stale_age_cap"`) plus a new `STALE_POSITION_AUTO_CLOSED` event,
      in BOTH paper and live; `alert_only` emits `STALE_POSITION_DETECTED`
      only; `block_new_entries` emits a visibility `STALE_POSITION_DETECTED`
      while enforcement stays in the unchanged `_stale_position_block_gate`.
      Reconciliation resolution table: `MONITORABLE` / `LEGACY_NO_PERF_LINK` ⇒
      close; `DEGRADED` ⇒ no-close + downgrade-to-block event
      (`resolution=degraded_block_new_entries`, priority high); `UNRECOVERABLE`
      ⇒ no-close + high-priority alert (`resolution=unrecoverable_operator_only`)
      — NO path auto-closes a degraded/unrecoverable position. Two new
      `ActivityEventType` values (`STALE_POSITION_DETECTED`,
      `STALE_POSITION_AUTO_CLOSED` in `src/runtime/activity_log.py`). +8 tests;
      full suite 2142 passed (+8); ruff + mypy clean; quant-trader-expert
      "sound — ship", qa-reviewer 🟢. Session log
      `docs/sessions/2026-05-24-cross-account-risk-policy-stale-actions.md`.
- [ ] Surface the new `ActivityEventType` values on the dashboard command
      center and through runtime-safety-score inputs.
      (Deferred to Slice 2. The DEBT-068(e) stale event types
      `STALE_POSITION_DETECTED` / `STALE_POSITION_AUTO_CLOSED` are EMITTED to
      the activity log as of 2026-05-24, but their dashboard surfacing +
      safety-score feed are NOT built — tracked here and under (f)/(h). Paper-
      mode cap advisories now emit the dedicated `RISK_CAP_ADVISORY` event type
      (DEBT-068(g) SHIPPED 2026-05-24 — paper cap advisories migrated off the
      `PROPOSAL_REJECTED + details.advisory=True` reuse, with the kill-switch
      paper + live emissions moved to `RISK_KILL_SWITCH_TRIPPED`; event-type
      migration only, `final_state` / funnel unchanged, `details.advisory=True`
      preserved). One follow-up surfaced: the secondary dashboard "Rejected"
      column in `src/dashboard/pages/engine.py` keys on exact
      `event_type == PROPOSAL_REJECTED`, so LIVE kill-switch hard-blocks (now
      emitted as `RISK_KILL_SWITCH_TRIPPED`) are excluded from that tally — a
      genuine undercount in that one column (no data lost; funnel keyed on
      `final_state` remains authoritative) — filed (g-note-dashboard-undercount)
      tied to (f).
      `runtime-safety-score` kill-switch + stale-event integration tracked
      under DEBT-068(h).)
- [x] **DEBT-068(d) — operator-freeze RUNTIME READ side. SHIPPED 2026-05-24.**
      (Split out from the originally-bundled dashboard-panel checkbox below so
      the runtime-shipped half and the dashboard-pending half are unambiguous.)
      A file-based `config/runtime_flags.yaml` reader (`read_trading_freeze` in
      `src/runtime/runtime_flags.py`), re-read ONCE at the top of `run_cycle`
      into `self._operator_freeze_active` (freezes a RUNNING engine without
      restart; fail-safe to NOT frozen on missing/malformed/non-bool file — a
      typo can neither freeze nor crash the cycle). New
      `EngineConfig.runtime_flags_path` (default `config/runtime_flags.yaml`).
      Gate at the VERY TOP of `_handle_proposal` — the earliest reject, ahead of
      correlation / regime / kill-switch / sizing / caps — hard-blocking in BOTH
      paper and live (manual kill; NO paper-advisory carve-out, unlike the
      kill-switch gates). New `ProposalFinalState.GATE_REJECTED_OPERATOR_FREEZE`
      terminal + `FunnelCounts` field + `_STATE_TO_FIELD` entry +
      `gate_rejected_total` inclusion; new
      `ActivityEventType.OPERATOR_FREEZE_ENGAGED` event with
      `reason="operator_freeze"`. `config/runtime_flags.yaml.example` added.
      Freeze blocks NEW-ENTRY proposals only; open positions wind down via the
      separate (non-freeze-gated) SL/TP polling path, per spec. +17 tests (11
      loader + 6 engine); full suite 2134 passed (+17); ruff + mypy clean;
      qa-reviewer 🟢. Session log
      `docs/sessions/2026-05-24-cross-account-risk-policy-operator-freeze.md`.
- [ ] **DEBT-068(f) — Cross-Account Risk dashboard panel + operator-freeze
      toggle WRITE side.** (Originally bundled with the (d) runtime read side
      above; split 2026-05-24. The runtime READ side shipped under (d); what
      remains here is the dashboard panel — per-account + global aggregate
      views, kill-switch state indicator, freeze-state indicator — plus the
      operator-freeze toggle UI that WRITES `trading_freeze` back to
      `config/runtime_flags.yaml`. NOT built; stays open.)
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
      hard-block behavior. 2026-05-24 DEBT-068(e) shipped the stale-position
      ACTION tests — all 8 scenarios for `_maybe_stale_age_action` (auto_close
      paper, auto_close live, alert_only, block_new_entries visibility event,
      degraded downgrade, unrecoverable operator-only, no-double-close after
      SL/TP and time-stop, block-gate-unchanged), +8 tests (2134 → 2142).
      Dashboard RENDERING tests remain deferred to (f).)

## Verification

- [x] `uv run pytest tests/test_trading_risk_sizing.py tests/test_trading_sub_account.py tests/test_runtime_engine.py -q`
- [x] `uv run pytest tests/test_trading_sub_account_registry.py -q`
- [x] `uv run pytest tests/test_trading_sub_account.py tests/test_trading_sub_account_registry.py tests/test_runtime_engine.py -q`
      for DEBT-068(b) opt-in global cap behavior. (2026-05-24: 189 passed.)
- [ ] Targeted dashboard tests for the cross-account risk panel and operator
      freeze toggle.
- [ ] Targeted runtime-safety-score tests for kill-switch event propagation.

## Completion Checklist

- [ ] Code implemented.
- [ ] Tests pass.
- [ ] Session log and cross-check added.
- [ ] `aidlc-docs/aidlc-state.md` updated.

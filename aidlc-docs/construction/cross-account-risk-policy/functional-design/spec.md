# Cross-Account Risk Policy Functional Specification

## Purpose

`cross-account-risk-policy` defines portfolio-level risk controls that operate
across strategy-isolated sub-accounts. Existing sub-account policy is per-account
only: each lab has its own per-trade risk percent, per-symbol cap, leverage cap,
and proposal threshold. There is no policy layer that reasons about exposure
across sub-accounts, no risk-adjusted sizing, and no drawdown- or age-based
kill switch.

The 2026-05-13 Fly runtime snapshot exposed the consequences:

- Roughly 49,000 USDT gross open notional across paper sub-accounts.
- Concentrated same-side exposure (ETH longs, BNB shorts, AVAX shorts) across
  many strategy-isolated accounts, with no account individually breaching its
  per-account cap.
- Fixed 1,000 USDT position sizing regardless of stop distance, producing a
  ~10x dispersion in actual per-trade risk between strategies.
- Open trades aging into days-old paper positions with no auto-close or
  stale-position pause.

This unit is intentionally additive. The existing `RiskPolicy`,
`CapitalPolicy`, and `ExecutionPolicy` blocks on `SubAccount` keep their
current semantics. New per-account fields and a new global policy section
extend them. The proposal runtime's gate stack gains new entries; existing
gates (composite threshold, correlation governor, safety-score pause,
cross-cycle position cap, stale-quote, past-SL, slippage) keep their current
ordering and rejection semantics.

## Policy Surfaces

The unit introduces three policy surfaces:

1. **Risk-based sizing** on each sub-account: replaces the fixed-notional
   sizing default with `risk_budget / stop_distance` math, with explicit
   floors and ceilings.
2. **Per-account and global exposure caps**: extend the existing per-account
   open-position / notional caps with cross-sub-account `(symbol, side)` and
   `symbol` aggregate caps.
3. **Stale-position age caps and kill switches**: add time-in-position limits,
   account-level drawdown / open-stop-risk pauses, a portfolio-level
   daily-loss kill switch, and an operator manual freeze toggle.

Each surface emits operator-visible activity events. Each surface is advisory
by default in paper mode (rejections only) and enforced in live mode.

## Risk-Based Sizing

### Formula

For a sub-account with equity `E` (in the account's quote currency) and a
proposal with entry price `P_entry` and stop-loss `P_sl`:

- Long: `risk_per_unit = P_entry - P_sl`
- Short: `risk_per_unit = P_sl - P_entry`
- `account_risk_budget = E * risk_budget_pct`
- Raw position size `Q = account_risk_budget / risk_per_unit`

`risk_budget_pct` is a per-sub-account configuration field (e.g. `0.005` for
0.5% of equity per trade). It replaces the legacy fixed-notional default for
sub-accounts that opt in. Accounts that do not opt in keep the existing
sizing path unchanged.

### Bounds and Fallbacks

The raw `Q` is clamped against three bounds before sizing the order:

- `max_notional_per_trade`: hard ceiling on `Q * P_entry`. When `risk_per_unit`
  is tiny (very tight stop), the formula can produce an oversized notional;
  the ceiling caps it.
- `min_notional_per_trade`: floor on `Q * P_entry`. When `risk_per_unit` is
  large (very wide stop), the formula can produce a sub-exchange-minimum size;
  proposals below the floor are rejected, not silently rounded up.
- `min_stop_distance_bps`: floor on `risk_per_unit / P_entry` expressed in
  basis points. Proposals with stops tighter than this floor are rejected as
  "stop too tight" rather than allowed to consume the full notional ceiling.

Fallback behavior:

- If account equity is unavailable (e.g. balance snapshot stale), use the
  last-known sizing balance from `CapitalPolicy.sizing_balance`. If neither is
  available, reject the proposal with a structured "sizing-equity-unknown"
  reason — silent fallback to a hardcoded default is not allowed.
- If `P_sl` is missing or on the wrong side of `P_entry`, the proposal is
  rejected before sizing math runs (proposal-runtime validation, not this
  unit's responsibility, but the sizing path must not assume valid input).

### Proposed Policy Shape

```yaml
sub_accounts:
  rsi_universal:
    risk_policy:
      sizing_mode: risk_budget   # or "fixed_notional" (legacy)
      risk_budget_pct: 0.005
      min_notional_per_trade: 50
      max_notional_per_trade: 2000
      min_stop_distance_bps: 25
```

Policy semantics:

- `sizing_mode: fixed_notional` preserves current behavior. The other fields
  in the block are ignored when fixed mode is selected.
- `sizing_mode: risk_budget` requires `risk_budget_pct`; the others have
  documented defaults.
- The block is per-sub-account so each lab can pick its own risk unit.

## Exposure Caps

### Per-Account Caps

`RiskPolicy` already carries `max_open_positions_total` and
`max_open_positions_per_symbol`. The unit adds:

- `max_gross_notional`: cap on the sum of open-position notional in the
  account's quote currency.
- `max_open_stop_risk`: cap on the sum across open positions of
  `abs(entry_price - stop_loss) * quantity`, i.e. total worst-case loss if
  every open stop fires simultaneously.

A proposal whose addition would push either total over its account cap is
rejected before order placement. Both caps are aggregate-only; a single trade
that fits the per-trade ceilings can still be rejected here when the account
is already loaded.

### Global Symbol/Side Caps

A new top-level `global_risk_policy` block governs aggregate exposure across
all enabled sub-accounts:

```yaml
global_risk_policy:
  max_open_positions_per_symbol_side: 3
  max_gross_notional_per_symbol_side: 5000
  max_gross_notional_per_symbol: 8000
  cap_resolution: lowest_priority_loses   # or "first_come_first_serve"
  account_priority:
    - rsi_universal
    - bollinger_band_reversion
    - vcp_breakout
```

Policy semantics:

- `max_open_positions_per_symbol_side`: total open positions across all
  sub-accounts on a given `(symbol, side)` tuple. Reached when, for example,
  three accounts each hold one ETH long.
- `max_gross_notional_per_symbol_side`: aggregate notional cap on a given
  `(symbol, side)` tuple.
- `max_gross_notional_per_symbol`: aggregate cap on long-plus-short notional
  on a symbol. Catches the case where the portfolio is delta-balanced but
  still highly concentrated on one asset.
- `cap_resolution` controls which sub-account loses the proposal when a
  global cap is at the boundary:
  - `first_come_first_serve`: cycle order wins. Simpler, matches existing
    cross-cycle cap behavior.
  - `lowest_priority_loses`: the proposal is allowed only if the proposing
    sub-account is not the lowest priority among accounts already holding
    exposure on that key. `account_priority` is an explicit ordered list.
- The global caps are checked **after** per-account caps and **after** the
  correlation governor in the gate stack, so an already-correlated portfolio
  does not become a global-cap problem.

### Relationship to Existing Surfaces

- `strategy-correlation-governor` already caps `max_sub_accounts_per_symbol_side`
  and `max_sub_accounts_per_strategy_symbol_side`. The new
  `max_open_positions_per_symbol_side` is the **count-of-open-trades** view
  whereas correlation governance is the **count-of-distinct-accounts** view.
  Both gates are kept; correlation runs first.
- `runtime-safety-score` continues to drive pause-recommended decisions. The
  new caps do not change safety-score inputs.

## Stale-Position Age Caps

### Policy Shape

```yaml
sub_accounts:
  rsi_universal:
    risk_policy:
      max_time_in_position_hours: 48
      stale_position_action: block_new_entries   # or "auto_close", "alert_only"
```

Policy semantics:

- `max_time_in_position_hours` is per-sub-account and operator-configurable.
  Strategies with intentionally long horizons (e.g. trend-following) use a
  larger value than scalpers.
- `stale_position_action` controls what happens when an open trade exceeds
  the cap:
  - `auto_close`: the runtime closes the position at market on the next
    cycle and writes a `POSITION_CLOSED` event with `reason="stale_age_cap"`.
  - `block_new_entries`: the position stays open but the sub-account is
    blocked from opening new trades until the stale position closes.
    Operator-visible activity event makes the block actionable.
  - `alert_only`: an activity event is emitted; no enforcement.

### Coordination with `runtime-reconciliation`

A position aging past the cap may also be in a `degraded` or `unrecoverable`
reconciliation state. The combination matters for operator playbooks:

- Stale + reconciliation OK: routine — auto-close or block is correct.
- Stale + `degraded`: do not auto-close (exchange/ledger drift risk);
  downgrade to `block_new_entries` and emit an operator-action event.
- Stale + `unrecoverable`: never auto-close; emit a high-priority alert and
  leave operator-only resolution.

This is encoded as a resolution table inside the runtime, not as separate
policy fields, so operators do not have to enumerate combinations in YAML.

## Kill Switches

### Per-Account Kill Switches

```yaml
sub_accounts:
  rsi_universal:
    risk_policy:
      daily_loss_limit_pct: 0.03
      open_unrealized_drawdown_limit_pct: 0.05
      open_stop_risk_limit_pct: 0.10
```

Policy semantics:

- `daily_loss_limit_pct`: when realized PnL since UTC midnight on this
  sub-account is worse than `-pct * starting_equity_today`, block all new
  entries for the rest of the UTC day.
- `open_unrealized_drawdown_limit_pct`: when current open unrealized PnL is
  worse than `-pct * equity`, block all new entries until the unrealized
  drawdown recovers above the threshold.
- `open_stop_risk_limit_pct`: when the sum of `abs(entry - stop) * qty` on
  open positions exceeds `pct * equity`, block new entries until existing
  positions close or move their stops in.

Per-account kill switches do not auto-close open positions; they only block
new entries. The closing decision remains with the strategy's own exit logic
or with the operator.

### Global Kill Switches

```yaml
global_risk_policy:
  portfolio_daily_loss_limit_pct: 0.02
  portfolio_unrealized_drawdown_limit_pct: 0.04
```

Computed over the sum of all enabled sub-account equity and PnL in the
common quote currency. Triggered global kill switches block new entries on
all sub-accounts.

### Operator Manual Freeze

A single operator-controlled flag — surfaced in the dashboard and in
`config/runtime_flags.yaml` (or equivalent) — overrides everything:

```yaml
runtime_flags:
  trading_freeze: false
```

When `true`, the engine rejects all proposals with `reason="operator_freeze"`
regardless of any other gate decision. This is the manual analogue of
runtime-safety-score's `pause_recommended` state.

### Hysteresis and Reset Semantics

- **Daily loss limits** auto-release at the next UTC midnight rollover.
- **Open unrealized drawdown limits** auto-release when the underlying metric
  recovers; the gate is stateless across cycles.
- **Open stop-risk limits** auto-release the same way.
- **Operator freeze** never auto-releases; an explicit operator action is
  required.
- **Engine restart** does **not** clear daily-loss state. The daily-loss
  metric is recomputed from persisted trade history at startup, so a restart
  cannot be used to escape a daily limit.

## Runtime Behavior

The proposal runtime adds the following gates to `_handle_proposal`, in this
order, after the existing composite acceptance and before order execution:

1. **Operator manual freeze** — earliest reject if active.
2. **Per-account daily loss limit** — checked against the account's realized
   PnL today.
3. **Per-account open-drawdown / open-stop-risk limits**.
4. **Global daily-loss / open-drawdown limits**.
5. **Risk-based sizing math** with bound clamps; rejection on stop-too-tight
   or sub-floor notional.
6. **Per-account `max_gross_notional` / `max_open_stop_risk` cap**.
7. **Global `(symbol, side)` and per-symbol caps** with `cap_resolution`.
8. **Stale-position age check** on the *opening account* (block-new-entries
   action; does not affect this proposal directly but is evaluated here so
   the stale state is logged on the same cycle).

Each gate that rejects emits an event. Persistent portfolio-condition gates
(daily loss state, stale-position state, freeze state) earn dedicated
`ActivityEventType` values so dashboards can chart them over time. Transient
per-proposal rejections reuse `PROPOSAL_REJECTED` with structured
`details.reason`.

## Dashboard Behavior

The dashboard adds a Cross-Account Risk panel with:

- Per-sub-account current equity, realized-PnL-today, open unrealized PnL,
  open stop-risk total, and gross open notional.
- Per-sub-account kill-switch state (none / daily-loss-tripped /
  drawdown-tripped / stop-risk-tripped / stale-block).
- Portfolio totals against the global caps, with a colored band at 70% / 90%
  / 100% of cap.
- Cross-sub-account `(symbol, side)` exposure summary: rows for every active
  tuple, with a count of accounts, total notional, and which global cap (if
  any) it is closest to breaching.
- Operator manual freeze toggle with confirmation.
- Recent risk-gate-blocked proposal events.

## Test Scope

Future implementation should include:

- Pure sizing-formula tests: long/short, tight stop ceiling, wide stop floor,
  unknown equity fallback.
- Sub-account policy parsing / validation tests for the new fields.
- Global policy parsing tests (presence/absence, cap resolution choice,
  account priority order).
- Runtime proposal-gating tests for each new gate, including order of gate
  evaluation relative to existing gates.
- Kill-switch state tests, including UTC-rollover auto-release for the daily
  loss limit and restart preservation.
- Stale-position action tests for `auto_close`, `block_new_entries`, and
  `alert_only`, including the reconciliation-state interaction matrix.
- Dashboard tests for the cross-account risk panel and the operator freeze
  toggle.

## Cross-Unit Dependencies

- `sub-account-capital-segmentation`: this unit extends `RiskPolicy` and
  introduces `global_risk_policy`. Schema and migration belong with the
  sub-account model owner.
- `strategy-correlation-governor`: already enforces `max_sub_accounts_per_*`
  caps. Cap-resolution policy and event ordering must remain consistent;
  correlation runs before global symbol/side caps.
- `runtime-safety-score`: kill switches emit safety-relevant activity events
  that flow into the runtime safety score. Tripping a portfolio kill switch
  should at minimum bump the safety band to `degraded`.
- `runtime-reconciliation`: stale-position auto-close interacts with
  `degraded` / `unrecoverable` states (see Stale-Position Age Caps).
- `proposal-runtime`: gate-stack ordering and activity event schema.
- `dashboard-operator-command-center`: surfaces the new panel and the
  operator freeze toggle.

## Inception Sync

The unit is registered in the AI-DLC inception requirement index,
user-story map, unit-of-work story map, unit breakdown, and AI-DLC state
tracker. Related Requirements: FR-036, FR-037, FR-038, FR-044, NFR-007,
NFR-008, NFR-012.

## Open Decisions

- Risk budget unit: percentage of account equity per trade (proposed
  default) versus a fixed USDT-per-trade budget per sub-account. The spec
  assumes percent-of-equity; confirm before code generation.
- Symbol/side cap unit: open-position count, gross notional, or both. The
  spec proposes both, but operators may want to ship only one to start.
- Default stale-position cap: a single 48h default versus per-strategy
  defaults baked into baseline strategy frontmatter. The spec leaves it
  per-sub-account-config; strategy-family defaults can come later.
- Live-mode hardening: which caps are advisory (event-only) in paper mode
  and hard-blocking in live mode. The spec assumes all caps hard-block in
  live mode; confirm.
- Account-tier risk presets ("conservative" / "standard" / "aggressive"):
  ship as named profiles operators select per sub-account, or defer to a
  later iteration once individual fields have field-tested defaults. The
  spec defers presets.
- Cap-resolution default: `first_come_first_serve` versus
  `lowest_priority_loses`. The spec exposes both but does not pick a
  shipped default.
- Whether the operator manual freeze should also auto-cancel open SL/TP
  orders in live mode, or strictly block new entries. The spec assumes the
  latter.

## Code-Generation Plan

Implementation should land in the following sequence; one bounded slice
each so cross-checks stay small.

1. **Config schema additions**.
   - Extend `RiskPolicy` (`src/trading/sub_account.py`) with the new sizing,
     cap, kill-switch, and stale-position fields. Existing fields keep
     their semantics; the new fields default to `None` so existing configs
     parse unchanged.
   - Add a top-level `GlobalRiskPolicy` model loaded from
     `config/sub_accounts.yaml` (or a parallel `config/risk_policy.yaml` if
     the registry owner prefers separation).
   - Add an operator `trading_freeze` flag — file-based, picked up at the
     start of each cycle.

2. **Policy resolution at runtime**.
   - Add `RuntimeRiskPolicy` (analogous to `RuntimePolicy` for the
     correlation/cap fields) that merges per-account `RiskPolicy` with
     `GlobalRiskPolicy` and returns the effective bounds for sizing and
     gating.
   - Add a sizing helper that takes `(entry, stop, equity, policy)` and
     returns the clamped position size or a structured rejection reason.

3. **Gate wiring**.
   - Insert the new gates into `_handle_proposal` in the order documented
     under Runtime Behavior.
   - Preserve existing gate semantics; do not change the gate signatures of
     stale-quote, past-SL, slippage, or the cross-cycle position cap.

4. **Activity events**.
   - New `ActivityEventType` values: `RISK_KILL_SWITCH_TRIPPED`,
     `OPERATOR_FREEZE_ENGAGED`, `STALE_POSITION_DETECTED`,
     `STALE_POSITION_AUTO_CLOSED`. Per-proposal rejections continue to use
     `PROPOSAL_REJECTED` with `details.reason`.
   - Update the JSONL rotator schema if new event types add new persistent
     fields.

5. **Dashboard exposure views**.
   - Add the Cross-Account Risk panel described under Dashboard Behavior.
   - Wire the operator freeze toggle with confirmation, persisting to the
     same file the runtime reads.
   - Update the existing exposure summary so global caps are colored at
     70% / 90% / 100%.

6. **Tests**.
   - `tests/test_trading_sub_account.py`: new field parsing and validation.
   - `tests/test_trading_sub_account_registry.py`: global policy block
     parsing, account priority ordering.
   - `tests/test_runtime_engine.py`: each new gate, gate ordering, kill
     switch lifecycle, stale-position actions including reconciliation
     interaction.
   - `tests/test_dashboard_trading.py` / `tests/test_dashboard_engine.py`:
     cross-account risk panel, operator freeze toggle.
   - `tests/test_runtime_safety_score.py`: kill-switch events affect
     runtime safety band.

Cross-checks should land per slice rather than as one merged review, so the
risk-gate ordering can be audited independently of the sizing math.

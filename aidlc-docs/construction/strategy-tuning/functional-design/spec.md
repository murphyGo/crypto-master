# Strategy Tuning Functional Specification

## Purpose

`strategy-tuning` converts observed paper-lab evidence into explicit, auditable
actions for each strategy running in a sub-account: keep, shadow, scout,
pause, promote, or retune. Today the operator does this by eye against the
Strategies and Trading dashboard pages, with no codified thresholds, no audit
trail, and no policy for moving a strategy between paper-lab tiers.

The unit is intentionally separate from individual strategy logic. Strategies
keep owning their own entry/exit rules. `strategy-tuning` owns the
above-strategy *action state* per (sub-account, strategy) pair, the evidence
thresholds that recommend an action, the runtime gates that enforce the
applied action, and the dashboard surface that lets an operator see and apply
recommendations.

This unit is downstream of `strategy-promotion-lab` (which already scores
candidate strategies and persists promotion recommendations) and upstream of
the runtime proposal pipeline (`proposal-runtime`) which must respect the
applied action when deciding whether to emit or open a trade for a given
strategy.

## Action States

Each (sub-account, strategy) pair carries one *applied* action state and one
*recommended* action state. The applied state is what the runtime enforces.
The recommended state is what the current evidence suggests; the two are
allowed to diverge until an operator (or, later, an automated policy)
applies the recommendation.

The initial action set is:

- `keep`: strategy is performing within thresholds; runtime emits and opens
  proposals normally.
- `shadow`: runtime records proposal evidence for evaluation but blocks any
  open. Equivalent to "paper-paper" — we keep generating signals so we can
  measure them, but no capital is committed.
- `scout`: runtime allows opens but at a reduced risk budget (default `0.25x`
  the account's normal per-trade risk). Used to keep a positive-edge but
  under-sampled strategy alive without giving it full size.
- `pause`: runtime fully blocks opens. Strategy config is preserved so a
  later `keep` resumes the prior behavior without re-registration. `pause`
  is sticky: it stays until an operator explicitly changes it.
- `promote`: signal that the strategy should graduate to a higher-tier
  sub-account (for example, from `paper_alt` to `paper_btc_main`). The
  applied state itself does not move the strategy; it makes the
  recommendation visible and provides the operator-action wiring.
- `retune`: opens are still allowed but the strategy is flagged for
  parameter retuning. Operators see a Retune badge on the dashboard.
  No runtime gating; this is an attention signal, not a block.

### Transitions

Allowed transitions:

- `keep <-> scout`: operator-initiated either direction; system may
  recommend the move from evidence.
- `keep -> shadow`: system or operator. Recovery requires
  `shadow -> keep` and is operator-only.
- `keep -> pause`, `scout -> pause`, `shadow -> pause`: any state can be
  paused.
- `pause -> keep`: operator-only. The system never auto-unpauses.
- `keep -> retune`, `scout -> retune`: system or operator. Recovery is
  operator-only (acknowledge the retune work landed).
- `keep -> promote` or `scout -> promote`: system recommendation only; the
  applied state changes only after operator action moves the strategy to a
  new sub-account.

`scout -> keep` requires at least `keep_promotion_sample_size` successful
closed trades inside the scout window (default 10) with profit-factor at or
above the `keep` threshold; otherwise the recommendation stays `scout`.

## Evidence Thresholds

The recommender consumes the metrics already tracked by `PerformanceTracker`
(`src/strategy/performance.py`), the per-strategy fail-closed counters from
`fail_closed_metrics.py` (DEBT-061), and current open exposure from the
sub-account registry. Defaults are deliberately conservative starting points
and intended to be tuned in operator config.

Metrics referenced:

- `closed_pnl_pct`: rolling closed PnL over the last N closed trades, as a
  percentage of account starting balance.
- `win_rate`: closed-trade win rate over the same window.
- `profit_factor`: gross-win / gross-loss over the window.
- `max_drawdown_pct`: max closed-trade drawdown over the window.
- `sample_size`: count of closed trades inside the window.
- `open_notional_pct`: current open exposure as a fraction of account
  allocation.
- `proposal_emission_rate`: emitted proposals per evaluation cycle.
- `fail_closed_rate`: fraction of emitted proposals rejected by post-gen
  gates (DEBT-061 surface).

Proposed default thresholds (per (sub-account, strategy) pair):

```yaml
strategy_tuning:
  window:
    closed_trades: 30          # rolling sample window
  pause:
    closed_pnl_pct_max: -5.0   # cumulative closed PnL <= -5%
    sample_size_min: 15        # only act after enough evidence
    OR_fail_closed_rate_min: 0.80  # >= 80% post-gen rejection rate
  shadow:
    profit_factor_max: 0.6     # systematically losing
    sample_size_min: 20
    closed_pnl_pct_max: -2.0
  scout:
    profit_factor_min: 1.0
    profit_factor_max: 1.5     # positive but not strong
    sample_size_max: 15        # under-sampled; aligned with keep.sample_size_min
  keep:
    profit_factor_min: 1.3
    win_rate_min: 0.40
    sample_size_min: 15
  promote:
    profit_factor_min: 1.8
    win_rate_min: 0.50
    sample_size_min: 30
    fail_closed_rate_max: 0.30
  retune:
    profit_factor_min: 0.8
    profit_factor_max: 1.2
    sample_size_min: 20        # enough evidence to know it is mediocre
    max_drawdown_pct_max: 8.0
  scout_size_factor: 0.25      # 0.25x normal risk budget under scout
```

The recommender evaluates thresholds in priority order
`pause -> shadow -> scout -> retune -> keep -> promote`, returning the first
match. A `null` recommendation means "insufficient evidence; leave applied
state untouched".

## Initial Actions for Named Strategy Families

These are the *initial recommendations based on the Fly 2026-05-13 snapshot
evidence* — not durable trading convictions. They populate the recommendation
column on day one so the operator has a starting point. Applied state
remains `keep` until the operator (or a later automated policy) applies the
recommendation.

| Strategy family | Initial recommendation | Source signal |
|---|---|---|
| `rsi_universal`, `rsi_4h`, `rsi_15m` | `scout` | DEBT-060 just landed an R/R fix that was rejecting ~50% of RSI proposals; RSI is the documented degraded-mode safety net (`docs/baselines.md`) so we keep it alive but at reduced size while the fix accumulates closed-trade evidence. |
| `momentum_pinball_orb` | `pause` | Under-performing on closed-PnL and win-rate in the 2026-05-13 snapshot. |
| `vwap_mean_reversion` and other mean-reversion accounts | `pause` | Negative closed-PnL and weak profit-factor across the family. |
| `default` / simple-trend / LLM-generated | `retune` | Mediocre profit-factor band; needs parameter or prompt work before pausing. |
| `raschke_holy_grail` | `scout` | Promising early indicators but under-sampled. |
| `ma_crossover` | `scout` | Promising early indicators but under-sampled. |
| `vcp_breakout` | `keep` if profit-factor meets `keep` threshold, else `retune` | No-signal diagnostics expected before any pause. |
| `session_vwap_pullback` | `keep` if profit-factor meets `keep` threshold, else `retune` | Same logic as `vcp_breakout`. |

The recommender re-evaluates every cycle; the table above is the seed, not
a static policy.

## Runtime Behavior

The proposal runtime should, for each (sub-account, strategy) pair:

1. Load the applied action state for the pair from sub-account config.
2. Compute and persist the current recommended action from evidence.
3. Enforce the applied state at proposal time:
   - `keep`: no change to current behavior.
   - `retune`: no change to runtime behavior; surface the flag on the
     dashboard.
   - `scout`: scale the per-proposal risk budget by `scout_size_factor`
     before sizing.
   - `shadow`: persist the proposal record with decision
     `shadow_recorded` and do not open a trade.
   - `pause`: reject the proposal with structured reason
     `strategy_action_pause` and emit `PROPOSAL_REJECTED`.
   - `promote`: behave like the underlying recommended state (`keep` or
     `scout`); the promote signal is a recommendation only — applying it
     requires moving the strategy to a different sub-account.
4. Every applied-state change is an activity event with operator/system
   attribution, prior state, new state, evidence snapshot, and timestamp.
5. The runtime should preserve enough context for dashboards and
   post-mortems: sub-account id, strategy id, applied state, recommended
   state, evidence snapshot, and decision.

A dedicated `ActivityEventType` is *not* warranted for shadow/scout/pause
rejections — they ride on `PROPOSAL_REJECTED` with `details.reason`
distinguishing the action. Applied-state *changes* themselves are operator
actions and use the existing operator-action activity event surface where
appropriate (see `dashboard-operator-command-center`).

## Dashboard Behavior

The Strategies page should show, per (sub-account, strategy) row:

- **Applied** state badge.
- **Recommended** state badge (with diff indicator if it differs from
  applied).
- Closed-PnL, win-rate, profit-factor, sample size, drawdown — the same
  columns the operator already reads.
- Fail-closed rate (DEBT-061 surface) so the operator can see proposal
  quality alongside trade quality.
- Most recent applied-state change with timestamp and attribution.

An "Apply recommendation" affordance appears when applied and recommended
differ. For v1 the affordance can be either an in-dashboard button (if the
sub-account config layer supports hot-reload) or a copy-to-clipboard YAML
snippet plus a documented restart workflow — see `## Open Decisions`.

A separate "Strategy Tuning" tab (or section on the Strategies page)
should show:

- Per-strategy recent action history.
- Current evidence thresholds in effect.
- Recommendations grouped by sub-account.

## Account Policy

Each sub-account must be able to opt in to strategy-tuning and override
defaults. Proposed shape:

```yaml
sub_accounts:
  paper_alt:
    strategy_tuning:
      enabled: true
      scout_size_factor: 0.25
      strategy_overrides:
        rsi_universal:
          applied: scout
        momentum_pinball_orb:
          applied: pause
  paper_btc_main:
    strategy_tuning:
      enabled: true
      scout_size_factor: 0.5   # main book uses larger scout
```

Semantics:

- `enabled: false` preserves current behavior for that account; no gating,
  no recommendation persistence.
- `enabled: true` activates evidence collection, recommendation, and
  runtime gating.
- `strategy_overrides.<strategy>.applied` is the operator-set applied
  state. Missing entries default to `keep`.
- `scout_size_factor` is account-scoped; per-strategy override is a
  potential v2 addition (see `## Open Decisions`).

## Test Scope

Future implementation should include:

- Recommender unit tests for each action (each threshold path).
- Sub-account policy parsing and validation tests.
- Runtime proposal-gating tests for `pause`, `shadow`, `scout`, `retune`,
  `keep`.
- `scout` sizing math tests against `scout_size_factor`.
- Activity-event tests for applied-state changes (operator and system
  attribution).
- Dashboard tests for applied/recommended badge rendering, "Apply
  recommendation" affordance, and per-strategy evidence rows.
- Regression test that DEBT-061 fail-closed-rate is read by the
  recommender (so the two units do not drift).

## Inception Sync

The unit is registered in the inception requirement index, user-story map,
unit-of-work story map, unit breakdown, and AI-DLC state tracker.

## Open Decisions

- Whether action state is per (sub-account, strategy) — the current
  proposal — or globally per strategy. Per-pair is more flexible but more
  config surface.
  - **Resolved 2026-05-13**: per (sub-account, strategy). Rationale: matches existing per-account isolation; same strategy can be `keep` in one lab and `pause` in another.
- Whether action-change workflow is an in-dashboard button (requires
  hot-reload of sub-account config) or YAML-edit + restart for v1. The
  v1 default proposed here is YAML-edit + restart, with a clipboard helper
  in the dashboard.
  - **Resolved 2026-05-13**: YAML-edit + restart for v1, with dashboard clipboard helper showing the diff. Rationale: avoids new write-from-dashboard surface; config remains the single source of truth.
- Whether `shadow` should persist proposal records to the same JSONL stream
  as live proposals (subsuming DEBT-061 fail-closed semantics) or to a
  separate `shadow_proposals.jsonl`.
  - **Resolved 2026-05-13**: same JSONL with `shadow=true` field on the record. Rationale: single stream stays simpler; downstream tools filter on the field.
- Whether `scout_size_factor` should be account-scoped only or also
  per-strategy.
  - **Resolved 2026-05-13**: per-strategy in YAML, default 0.25. Rationale: per-strategy gives flexibility; default mirrors the spec's example.
- Promotion target resolution: for a `promote` recommendation, who
  decides the destination sub-account — operator-only, or does the
  marketplace template embed a default promotion target?
  - **Resolved 2026-05-13**: operator-only for v1. Rationale: marketplace template integration is `sub-account-experiment-marketplace`'s territory — defer cross-unit coupling.
- Whether `pause` should also stop the evidence window from rolling
  forward (so an unpaused strategy resumes against the same dataset) or
  reset the window on unpause.
  - **Resolved 2026-05-13**: reset on unpause. Rationale: cleaner trigger semantics — unpause means "fresh start under current config"; preserves operator agency.

All decisions above resolved 2026-05-13; code-generation cycle unblocked.

## Code-Generation Plan

A full plan is tracked in
`aidlc-docs/construction/plans/strategy-tuning-code-generation-plan.md`. At a
glance:

- Strategy file changes: none required. Action state is runtime-only and
  lives in sub-account config plus per-pair runtime store; strategies keep
  their existing contract.
- Sub-account config schema: extend the YAML schema with the
  `strategy_tuning` block above; validate on load; default to disabled.
- Runtime gate: in `src/proposal/` or `src/runtime/`, evaluate the applied
  action before emit/open and produce the structured rejection/record
  described in `## Runtime Behavior`.
- Recommender: pure function over `PerformanceTracker` aggregates and
  DEBT-061 fail-closed metrics; no I/O; persists recommendations through
  an observation store analogous to `PromotionObservationStore`.
- Dashboard: new columns and tab on the Strategies page; "Apply
  recommendation" affordance.
- Tests: as in `## Test Scope`.

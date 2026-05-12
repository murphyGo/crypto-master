# Market Regime Functional Specification

## Purpose

`market-regime` provides a shared runtime view of the current market condition
so Crypto Master can distinguish bullish, bearish, and sideways environments
before deciding which strategy proposals should be allowed.

The unit is intentionally separate from individual strategy logic. Strategies
may still contain their own trend or range filters, but the engine should have a
single operator-visible regime classification that can be reused by proposal
generation, dashboard summaries, and future risk policy.

## Regime Labels

The initial label set is:

- `bull`: price is materially above the long moving-average baseline.
- `bear`: price is materially below the long moving-average baseline.
- `sideways`: price is inside the neutral band around the baseline.
- `unknown`: insufficient or stale data.

The first implementation should align with the existing robustness-gate
convention unless a later design decision changes it:

- `close > SMA(200) * 1.02` -> `bull`
- `close < SMA(200) * 0.98` -> `bear`
- otherwise -> `sideways`

## Account Policy

Each sub-account must be able to decide whether market-regime gating applies.

Proposed policy shape:

```yaml
sub_accounts:
  default:
    market_regime:
      enabled: false
      reference_symbol: BTC/USDT
      timeframe: 4h
      allowed_regimes: [bull, bear, sideways]
  trend_following:
    market_regime:
      enabled: true
      reference_symbol: BTC/USDT
      timeframe: 4h
      allowed_regimes: [bull, bear]
  mean_reversion:
    market_regime:
      enabled: true
      reference_symbol: BTC/USDT
      timeframe: 4h
      allowed_regimes: [sideways]
```

Policy semantics:

- `enabled: false` preserves current behavior for that account.
- `enabled: true` makes the proposal runtime check the current regime before
  opening a proposal for that account.
- `allowed_regimes` controls whether proposals are allowed. An empty list should
  be invalid.
- `unknown` should block by default when gating is enabled unless the account
  explicitly allows it.
- Account policy is advisory for paper experimentation but must be enforced
  before live execution once wired.

## Runtime Behavior

The proposal runtime should:

1. Load or compute the current regime for the account's `reference_symbol` and
   `timeframe`.
2. If account regime gating is disabled, continue unchanged.
3. If enabled and the regime is not allowed, skip proposal execution for that
   account and emit an operator-visible activity event.
4. Persist enough context for dashboards and post-mortems: symbol, timeframe,
   regime, baseline, close, policy decision, and sub-account id.

A gate earns its own dedicated `ActivityEventType` iff it represents a
persistent market or portfolio condition the dashboard will chart over time
(regime, correlation, runtime-safety). Otherwise emit `PROPOSAL_REJECTED` with
`details.reason` (score threshold, sibling family, transient validation
failure).

## Dashboard Behavior

The dashboard should show:

- Current market regime and freshness.
- Per-sub-account regime policy state.
- Recent regime-blocked proposal/account events.
- Whether the current regime is allowing or blocking each account.

## Test Scope

Future implementation should include:

- Pure classifier tests for bull, bear, sideways, and unknown.
- Sub-account config parsing and validation tests.
- Runtime proposal-gating tests for enabled/disabled accounts.
- Activity event tests for regime-blocked decisions.
- Dashboard tests for regime status and account policy rendering.

## Inception Sync

The unit is registered in the inception requirement index, user-story map,
unit-of-work story map, unit breakdown, and AI-DLC state tracker.

## Open Decisions

- Whether BTC/USDT should be the only default reference symbol or account-level
  strategy groups can choose their own reference market.
- Whether account policy should only gate proposal execution or also rank/select
  strategies by regime fit.
- Whether live mode should require `unknown` to block regardless of account
  override.

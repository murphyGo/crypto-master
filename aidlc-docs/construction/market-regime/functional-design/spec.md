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

---

## Funding+OI Crowding Filter

### Purpose and hypothesis

The first consumer of the sealed derivatives context is a proposal-layer
crowding filter. At a settled Funding extreme with rising open interest, the
Funding-paying side is treated as crowded. Entering with that crowd may carry
asymmetric squeeze risk. The filter must first measure this claim in shadow
mode; it may veto entries only after both proposal-history replay and pinned
Snapshot-v2 backtest evidence qualify it.

The hypothesis is falsified when with-crowd-at-extreme entries do not
underperform comparable entries, or when removing them produces a negative
expectancy delta. In that case veto remains unavailable.

### Classification labels

- `crowded_long`: latest settled Funding is positive and at or above the
  nearest-rank 95th percentile of the trailing 30-day settled Funding window,
  and latest OI is strictly greater than the 24-hour reference OI.
- `crowded_short`: latest settled Funding is negative and at or below the
  nearest-rank 5th percentile, with the same rising-OI confirmation.
- `neutral`: sufficient fresh data exists but the conjunction is false.
- `unavailable`: Funding/OI is missing, stale, structurally invalid, or lacks
  the full comparison window.

The percentile sample includes only settled Funding records at or before the
decision `as_of`; predicted Funding is never used. A 30-day 8h grid requires at
least 90 observations. The OI comparison uses the latest point at or before
`as_of` and the latest point at or before `as_of - 24h`; the reference must be
within one OI interval of that target. Equality is not rising.

### Proposal decision

The filter is evaluated after score acceptance, correlation, and the existing
OHLCV market-regime gate, but before sizing and risk-cap gates. It references
`proposal.symbol` and is side-aware:

- `crowded_long` + new `long` proposal -> `would_block=true`.
- `crowded_short` + new `short` proposal -> `would_block=true`.
- Opposite-side and neutral proposals pass.
- `unavailable` always passes and emits
  `gate_skipped_missing_market_context` telemetry.

Per-sub-account policy is disabled by default. The initial rollout supports
`shadow`, which records the decision without mutating the proposal record or
opening behavior. `veto` is a reserved later action and cannot become active
until a validated evidence artifact proves the predeclared gate.

### Evidence gate

Veto eligibility requires all of the following from one declared evaluation:

1. Proposal-history replay and pinned Snapshot-v2 backtest both complete.
2. Both reports identify their input bounds; snapshot evidence pins generation
   id, configuration digest, and seed.
3. Filtered-minus-unfiltered net expectancy is non-negative in both reports.
4. Sample counts are labeled; neither report may claim qualification with zero
   with-crowd observations.
5. At least two non-`unknown` OHLCV market-regime buckets are represented.
6. Missing, mixed-generation, live-fetched, or structurally incomplete data
   yields `insufficient_evidence`, never pass.

### Telemetry and dashboard

Shadow evaluation records only normalized derived values: proposal/record id,
sub-account, symbol, signal, decision time, crowding label, latest settled
Funding, low/high thresholds, latest/reference OI, OI delta, policy action,
`would_block`, and stable reason. Raw exchange payloads, credentials, request
URLs, exception text, and predicted Funding are excluded.

The dashboard shows the newest classification per symbol, per-account policy
mode, evaluated/would-block/skip counts, and recent shadow rows. It labels all
pre-evidence results `SHADOW — NOT ENFORCING` and never presents would-block
counts as executed vetoes.

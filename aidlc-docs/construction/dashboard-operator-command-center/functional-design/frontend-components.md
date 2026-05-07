# Frontend Components: dashboard-operator-command-center

## Component Hierarchy

```text
Dashboard App
  Home / Command Center
    StatusHeader
    AccountContextBand
    SafetyBreakdown
    ExposureSummary
    InvestigationLinks
  Existing Pages
    Trading
    Engine
    Strategies
    Feedback Loop
```

The first slice should implement the Home / Command Center pieces with pure
read-model helpers in `src/dashboard/app.py` or a small local helper module if
the app chassis becomes too large.

## StatusHeader

- Inputs: `CommandCenterStatus`.
- Shows: safety band, safety score, last cycle status/time, open positions,
  latest snapshot freshness, actionable event count.
- Interaction: no mutation; page links or captions point to Engine/Trading.
- Empty state: if no activity/trading data exists, render missing state without
  exceptions.

## AccountContextBand

- Inputs: `AccountContext`.
- Shows: selected mode/scope, sub-account count, latest equity, quote currency,
  data availability.
- Interaction: first slice may use default `paper` + aggregate scope; later
  slices can add mode/scope controls shared with Trading.
- Validation: live mode must be labeled clearly when introduced.

## SafetyBreakdown

- Inputs: `RuntimeSafetyScore` and `SafetyEventSummary` rows.
- Shows: factor rows and recent notification failure, stale/no-live-data,
  liquidation, cold-start, and correlation-warning counts.
- Interaction: expandable raw event details for long JSON payloads in later
  slices.

## ExposureSummary

- Inputs: `ExposureRow` rows.
- Shows: symbol, side, sub-accounts, open count, estimated notional,
  max leverage, duplicate-account flag, correlation status.
- Empty state: no open persisted trades.
- Constraint: no current-price or exchange-derived PnL until an explicit future
  design wires fresh market data.

## InvestigationLinks

- Inputs: summary status from other components.
- Shows: compact links or labels to investigate in Trading, Engine, Strategies,
  and Feedback.
- First slice: text links/labels only; do not add new Streamlit pages yet.

## Test Expectations

- `tests/test_dashboard_app.py`: Home renders command-center status with empty
  and synthetic data fixtures.
- `tests/test_dashboard_trading.py`: pure exposure/freshness helpers return
  stable DataFrames.
- `tests/test_dashboard_engine.py`: safety-event summaries classify runtime
  events into actionable buckets.

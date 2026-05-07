# Business Logic Model: dashboard-operator-command-center

## Goal

The command center answers the operator's first runtime question:

> Is the bot safe to keep running, and where should I investigate next?

It is a read-only dashboard workflow. It summarizes existing persisted runtime,
trading, feedback, and strategy evidence without calling exchanges, mutating
runtime data, or bypassing operator approval gates.

## Information Architecture

| Layer | Purpose | Drilldown |
|-------|---------|-----------|
| Status header | One-screen safety answer: safety band, score, last cycle, open exposure, stale data, recent critical events | Engine, Trading |
| Account context | Shows paper/live mode and selected aggregate/default/sub-account scope before metrics | Trading |
| Exposure summary | Groups open positions by symbol/side/sub-account with notional and leverage | Trading, Engine |
| Safety events | Separates notification failures, stale/no-live-data, liquidation, cold-start, and correlation warnings | Engine |
| Strategy evidence | Links strategy state, candidate status, robustness, promotion score, replay, audit, proposal, and trade outcomes | Strategies, Feedback |

## First Code Slice

The first implementation slice should be deliberately narrow:

1. Add a command-center status section to the Home page.
2. Reuse existing readers:
   - `ActivityLog` for last cycle and safety events.
   - `compute_runtime_safety_score` for safety band and factors.
   - `TradeHistoryTracker` and `PortfolioTracker` for open position and
     snapshot freshness summaries.
3. Add pure helper functions before rendering so tests can validate the read
   model without a live Streamlit runtime.
4. Keep all existing pages intact.

## Data Flow

```text
data/runtime/activity.jsonl
  -> ActivityLog.read_all()
  -> cycle summary, safety score, recent actionable events

data/trades/{mode}/{sub_account_id}/
  -> TradeHistoryTracker.load_trades()
  -> open position count and exposure rows

data/portfolio/{mode}/{sub_account_id}/
  -> PortfolioTracker.load_snapshots()
  -> latest equity, latest snapshot timestamp, freshness state

data/feedback/ + data/audit/
  -> future strategy evidence slice
```

## Out Of Scope For First Slice

- Direct exchange price refresh.
- Live trading controls.
- Candidate promotion or proposal replay mutation.
- Replacing existing `Trading`, `Engine`, `Strategies`, or `Feedback` pages.

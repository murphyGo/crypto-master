# User Review Synthesis: dashboard-operator-command-center

## Purpose

Three user-perspective reviews converged on the same dashboard gap: the current
Streamlit UI exposes domain pages, but it does not start from the operator's
first decision: whether the bot is safe to keep running and where to investigate
next.

## Review Perspectives

| Perspective | Main Finding | Primary Existing Surface |
|-------------|--------------|--------------------------|
| Day-to-day operator | Home is section guidance, not an operational status board | `src/dashboard/app.py` |
| Strategy maintainer | Strategy, candidate, robustness, promotion, replay, and audit evidence are fragmented | `src/dashboard/pages/strategies.py`, `src/dashboard/pages/feedback.py` |
| Risk reviewer | Sub-account, aggregate exposure, correlation, notification, liquidation, and data-freshness signals are not actionable enough | `src/dashboard/pages/trading.py`, `src/dashboard/pages/engine.py` |

## Functional Design Direction

The command center should be an operator-first dashboard layer, not just a
visual refresh. It should:

- Put runtime safety band, last cycle, open exposure, data freshness, and recent
  actionable events on the first screen.
- Keep paper/live and selected/aggregate/sub-account context visible before
  showing trading or engine details.
- Surface cross-account exposure by symbol, side, sub-account count, notional,
  leverage, and correlation-warning status.
- Split safety-score factors into readable cards and recent event tables for
  notification failures, stale/no-live-data, liquidation, cold-start, and
  correlation warnings.
- Link strategy status to candidate evidence: source file, backtest run,
  robustness gates, promotion score, blockers, replay scenarios, audit events,
  proposal history, and trade outcomes.

## Non-Goals For First Slice

- No live trading action buttons.
- No direct exchange calls from the dashboard.
- No mutation of runtime/operator `data/` during render.
- No replacement of the existing Strategies, Trading, Feedback, or Engine pages;
  the command center should summarize and drill down into them.

## Suggested First Implementation Slice

Start with Home/Status and risk-read models:

1. Add a command-center status section to `src/dashboard/app.py`.
2. Reuse `ActivityLog`, `TradeHistoryTracker`, `PortfolioTracker`, and
   `RuntimeSafetyScore` rather than introducing a new runtime dependency.
3. Add pure helper functions for snapshot freshness and cross-account open
   exposure so AppTest and DataFrame tests can pin behavior.
4. Add targeted tests before visual polish:
   `tests/test_dashboard_app.py`, `tests/test_dashboard_trading.py`, and
   `tests/test_dashboard_engine.py`.

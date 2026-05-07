# Session: dashboard-operator-ui open-position PnL

## Unit

`dashboard-operator-ui`

## Related Requirements

- FR-029: Show active trading state
- FR-031: Show asset and performance summaries
- NFR-003: Implement the dashboard with Streamlit
- NFR-007: Persist trade history with prices, quantity, leverage, fees, PnL,
  and timestamps
- NFR-008: Persist asset and PnL history separately by mode

## Files Changed

- `src/trading/portfolio.py`
- `src/dashboard/pages/trading.py`
- `tests/test_dashboard_trading.py`
- `tests/test_portfolio.py`
- `aidlc-docs/construction/plans/dashboard-operator-ui-open-position-pnl-code-generation-plan.md`
- `aidlc-docs/construction/dashboard-operator-ui/code/open-position-pnl.md`
- `docs/sessions/2026-05-08-dashboard-operator-ui-open-position-pnl.md`
- `docs/cross-checks/2026-05-08-dashboard-operator-ui-open-position-pnl.md`

## Checks

- `uv run pytest tests/test_dashboard_trading.py tests/test_portfolio.py -q`

## Decisions

- The dashboard does not call exchanges directly. It uses the latest persisted
  snapshot's mark prices, which are already collected by the runtime snapshot
  path.
- Row-level PnL is blank when a symbol has no mark price in the latest snapshot.
  This preserves partial snapshot semantics instead of turning missing prices
  into zero PnL.

## Risks

- Older snapshots do not include `current_prices`, so open-position PnL appears
  after the runtime records a fresh snapshot.

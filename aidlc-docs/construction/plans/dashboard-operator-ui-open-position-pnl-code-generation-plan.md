# Code Generation Plan: dashboard-operator-ui open-position PnL

## Task

Show current open-position PnL in the Trading dashboard from the latest
portfolio snapshot's mark prices.

## Related Context

- Unit: `dashboard-operator-ui`
- Stage: Code Generation
- Requirements: FR-029, FR-031, NFR-003, NFR-007, NFR-008
- Stories: US-012
- Related units: `trading-core`, `persistence-data-integrity`

## Steps

- [x] Persist snapshot mark prices so the dashboard can calculate per-position
      PnL without calling an exchange.
- [x] Add current price, PnL, and PnL percent columns to the open positions
      table when snapshot prices are available.
- [x] Cover the new snapshot and dashboard helpers with targeted tests.
- [x] Record the implementation summary and session evidence.

## Verification

- [x] `uv run pytest tests/test_dashboard_trading.py tests/test_portfolio.py -q`

## Completion Checklist

- [x] Application code updated.
- [x] Tests updated and passing.
- [x] Session log created.
- [x] AI-DLC plan marked complete.

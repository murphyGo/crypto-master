# Dashboard Operator UI: Open-Position PnL

## Summary

The Trading dashboard now shows current open-position PnL when the latest
portfolio snapshot includes mark prices for the position symbols.

## Implementation

- `AssetSnapshot.current_prices` persists the symbol -> mark price map used when
  `PortfolioTracker.record_snapshot` calculates unrealized PnL.
- `build_open_positions_dataframe` accepts those latest snapshot prices and adds
  `Current Price`, `Current P&L`, and `Current P&L %` columns for open trades.
- Missing mark prices stay blank at the row level so stale or partial price
  collection does not imply zero PnL.

## Verification

- `uv run pytest tests/test_dashboard_trading.py tests/test_portfolio.py -q`

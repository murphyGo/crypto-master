# Cross-Check: dashboard-operator-ui open-position PnL

## Scope

Verify that the Trading dashboard can show current PnL for open positions
without adding direct exchange calls to Streamlit.

## Requirements

- FR-029: Show active trading state
- FR-031: Show asset and performance summaries
- NFR-003: Implement the dashboard with Streamlit
- NFR-007: Persist trade history with prices, quantity, leverage, fees, PnL,
  and timestamps
- NFR-008: Persist asset and PnL history separately by mode

## Evidence

- `PortfolioTracker.record_snapshot` persists the mark-price map already used
  for snapshot unrealized PnL as `AssetSnapshot.current_prices`.
- `build_open_positions_dataframe` computes per-row `Current Price`,
  `Current P&L`, and `Current P&L %` from the latest snapshot prices.
- Missing per-symbol prices remain blank, preserving partial snapshot behavior.

## Checks

- `uv run pytest tests/test_dashboard_trading.py tests/test_portfolio.py -q`

## Result

PASS

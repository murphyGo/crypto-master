# Cross-Check: consistency-hardening CH-07 Live Position Rehydration

## Scope

Verify that live open positions can be monitored after process restart when the
trade record contains persisted SL/TP state, while legacy open trades without
that state remain visible but require operator reconciliation.

## Requirements

- FR-009 Live Trading Mode
- FR-010 Paper/Live Mode Switching
- NFR-007 Trading History Storage
- NFR-008 Asset/PnL History
- NFR-012 Live Trading Confirmation

## Evidence

- `TradeHistory` now stores optional `stop_loss` and `take_profit`.
- `TradeHistoryTracker.open_trade` accepts persisted entry fees and risk
  bounds.
- `LiveTrader.open_position` writes SL/TP and entry fee state into the live
  trade record.
- `LiveTrader._rehydrate_open_positions()` rebuilds monitorable `Position`
  state from persisted live open trades with SL/TP.
- `LiveTrader.get_open_position()` lets the runtime orphan guard detect legacy
  open trades that lack monitor state.

## Verification

- `uv run pytest tests/test_live_trading.py tests/test_strategy_performance.py -q`
  - 126 passed.
- `uv run black --check src/trading/live.py src/strategy/performance.py tests/test_live_trading.py tests/test_strategy_performance.py`
  - passed.
- `uv run ruff check src/trading/live.py src/strategy/performance.py tests/test_live_trading.py tests/test_strategy_performance.py`
  - passed.

## Result

PASS. CH-07 closes the forward runtime-restart gap for live trades opened after
the schema extension. Historical open trades without persisted SL/TP remain a
deliberate reconciliation case.

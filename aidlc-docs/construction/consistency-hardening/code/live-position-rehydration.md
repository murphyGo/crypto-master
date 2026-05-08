# CH-07 Live Position Rehydration

## Summary

`LiveTrader` now persists runtime monitor bounds (`stop_loss`, `take_profit`)
and entry-side fees in `TradeHistory` when a live position is opened. On
construction, it scans persisted open live trades and rebuilds monitorable
`Position` objects for records that include SL/TP state.

Legacy open live trades without persisted SL/TP remain visible through
`get_open_trades()` but are intentionally not rehydrated into
`_open_positions`. `get_open_position()` exposes this state to the runtime
orphan guard so the engine can require operator reconciliation instead of
silently skipping SL/TP enforcement.

## Verification

- `uv run pytest tests/test_live_trading.py tests/test_strategy_performance.py -q`
  - 126 passed.
- `uv run black --check src/trading/live.py src/strategy/performance.py tests/test_live_trading.py tests/test_strategy_performance.py`
  - passed.
- `uv run ruff check src/trading/live.py src/strategy/performance.py tests/test_live_trading.py tests/test_strategy_performance.py`
  - passed.

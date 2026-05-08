# Session: consistency-hardening CH-07 Live Position Rehydration

## Unit

- `consistency-hardening`
- Primary owner units: `trading-core`, `persistence-data-integrity`

## Related Requirements

- FR-009 Live Trading Mode
- FR-010 Paper/Live Mode Switching
- NFR-007 Trading History Storage
- NFR-008 Asset/PnL History
- NFR-012 Live Trading Confirmation

## Changes

- Added optional `stop_loss` and `take_profit` fields to `TradeHistory`.
- Extended `TradeHistoryTracker.open_trade` to persist initial fees and risk
  bounds.
- Updated `LiveTrader.open_position` to persist SL/TP and entry-side fees.
- Added `LiveTrader._rehydrate_open_positions()` so restarted live traders
  rebuild monitorable `Position` state from persisted open live trades.
- Added `LiveTrader.get_open_position()` for the runtime orphan-state guard.
- Kept legacy open live trades without SL/TP visible but non-monitorable so the
  operator reconciliation path remains conservative.

## Tests

- `uv run pytest tests/test_live_trading.py tests/test_strategy_performance.py -q`
  - 126 passed.
- `uv run black --check src/trading/live.py src/strategy/performance.py tests/test_live_trading.py tests/test_strategy_performance.py`
  - passed.
- `uv run ruff check src/trading/live.py src/strategy/performance.py tests/test_live_trading.py tests/test_strategy_performance.py`
  - passed.

## Decisions

- Rehydration only treats trades with persisted SL/TP bounds as monitorable.
  Older live open trades without those bounds remain orphaned until an operator
  reconciles them.
- Entry fees are now persisted at open time. Close handling adds only the exit
  fee when a persisted fee is already present, preserving CH-06 fee attribution
  while allowing restart-safe accounting.

## Risks

- Historical open live trades created before CH-07 do not gain SL/TP state
  automatically. This is intentional because reconstructing risk bounds without
  the original proposal would be unsafe.

# Code Generation Plan: consistency-hardening - CH-07 Live position rehydration

## Task

Persist enough live open-trade state for `LiveTrader` to rehydrate its
in-memory SL/TP monitor state after a process restart. Legacy open trades that
do not include SL/TP bounds must remain visible as open trades but should not be
silently treated as monitorable.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-07
- Primary owner units: `trading-core`, `persistence-data-integrity`
- Related debt: `DEBT-053`

## Related Requirements

- FR-009 Live Trading Mode
- FR-010 Paper/Live Mode Switching
- NFR-007 Trading History Storage
- NFR-008 Asset/PnL History
- NFR-012 Live Trading Confirmation

## Steps

- [x] Extend `TradeHistory` / `TradeHistoryTracker.open_trade` with optional
      `stop_loss` and `take_profit` fields.
- [x] Persist live entry fees at open time so restarted live closes keep fee
      accounting without relying only on memory.
- [x] Rehydrate `LiveTrader._open_positions` from persisted open live trades
      when SL/TP bounds are present.
- [x] Expose `LiveTrader.get_open_position` for the runtime orphan-state guard.
- [x] Tests: live open persists SL/TP + entry fee, restart rehydrates
      monitorable positions, legacy open trades without SL/TP remain orphaned.
- [x] Targeted pytest: `uv run pytest tests/test_live_trading.py
      tests/test_strategy_performance.py -q`.

## Verification

- [x] Targeted tests pass.
- [x] Formatting/lint run for changed source/test files where practical.

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Tests added.
- [x] Plan steps closed.
- [x] State row/spec status updated.
- [x] Session log written.
- [x] `DEBT-053` resolved or narrowed with explicit remaining caveat.

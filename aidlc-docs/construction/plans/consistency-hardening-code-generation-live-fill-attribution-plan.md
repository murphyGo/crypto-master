# Code Generation Plan: consistency-hardening — CH-06 Live fill attribution

## Task

Live trades on disk previously recorded the caller's expected exit
price (or, in the open-side path, ``position.entry_price``) and never
threaded ``order.fee``, so realised P&L diverged from what actually
executed and live vs paper P&L could not be compared.

Add `average_price` and `fee` (with `fee_currency`) fields to the
shared `Order` model. Have `BinanceExchange._map_order` and
`BybitExchange._map_order` populate them from ccxt's response via two
shared helpers in `src/exchange/base.py`. Update
`LiveTrader.open_position` to record the exchange's average fill
price and capture the entry fee. Update `LiveTrader._execute_close` to
use the close-side average fill price (with caller fallback) and to
sum entry+exit fees through `TradeHistoryTracker.close_trade(fees=)`.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-06
- Primary owner units: `trading-core`, `exchange-integration`

## Related Requirements

- FR-009 Live Trading Mode
- FR-016 Binance Integration
- FR-017 Bybit Integration
- FR-019 Exchange Abstraction
- NFR-008 Atomic Persistence (P&L truthfulness)

## Steps

- [x] Add `average_price`, `fee`, `fee_currency` fields to `Order`.
- [x] Add `_decimal_or_none` and `_extract_ccxt_fee` helpers in
      `src/exchange/base.py`.
- [x] Wire helpers into `BinanceExchange._map_order` and
      `BybitExchange._map_order`.
- [x] `LiveTrader.open_position` records `order.average_price` and
      stashes `order.fee` in `_entry_fees`.
- [x] `LiveTrader._execute_close` uses `order.average_price` (caller
      fallback) and threads `entry_fee + exit_fee` to
      `close_trade(fees=)`.
- [x] Tests: live close records actual fill + sum of fees; legacy
      adapters fall back; both `_map_order` adapters extract average
      and per-fill fee lists.
- [x] Targeted pytest: 240/240 across live trading, models,
      exchange base/binance/bybit, and main dispatch.
- [x] Lint/format/types clean for changed files (pre-existing harness
      error unaffected).
- [x] State row + spec.md status updated, session log written.

## Verification

- 240 / 240 targeted tests pass.
- ruff/black clean. mypy clean for the five changed source files.

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Tests added.
- [x] Plan steps closed.
- [x] State row updated.
- [x] Session log written.

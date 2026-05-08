# Session: consistency-hardening — CH-06 Live fill attribution

## Unit

- `consistency-hardening` (primary owner units: `trading-core`,
  `exchange-integration`)
- Stage: Code Generation
- Slice ID: CH-06

## Related Requirements

- FR-009 Live Trading Mode
- FR-016 Binance Integration
- FR-017 Bybit Integration
- FR-019 Exchange Abstraction
- NFR-008 Atomic Persistence (P&L truthfulness)

## Problem

`LiveTrader._execute_close` recorded
``actual_exit_price = exit_price or position.entry_price`` — the
caller's expected exit price (or the entry price as a last-ditch
fallback). The exchange's actual fill price (``order.average``) was
never read, so realised P&L on disk could drift arbitrarily from what
really executed. `LiveTrader.open_position` had the same gap on the
entry side: it recorded ``position.entry_price`` rather than the
average reported by the exchange.

Worse, the live tracker never captured ``order.fee`` for either side,
so live trade ``fees`` were always zero on disk. Paper and live P&L
were no longer comparable: PaperTrader debits both entry and exit
fees, LiveTrader debited none.

## Fix

- `Order` gains `average_price`, `fee`, and `fee_currency`. All three
  are optional so adapters that haven't been updated still build
  valid `Order` objects.
- `src/exchange/base.py` exposes two helpers:
  - `_decimal_or_none(value)` — coerce a ccxt scalar to `Decimal`,
    returning `None` for null/0/empty so the optional `Order` fields
    are absent rather than zero-decimal.
  - `_extract_ccxt_fee(raw_order)` — sum `fees[*].cost` when the
    venue returns per-fill fee objects, otherwise read the unified
    `fee` block; returns `(amount, currency)`.
- `BinanceExchange._map_order` and `BybitExchange._map_order` now
  populate the three new fields via the helpers.
- `LiveTrader._open_position` prefers `order.average_price` for the
  recorded entry price and stashes `order.fee` in a new
  `_entry_fees: dict[trade_id, Decimal]`. It also propagates the
  exchange-reported entry price into the in-memory `Position` (used
  by `monitor_positions` for SL/TP checks) so SL/TP comparisons run
  against the price the caller actually paid.
- `LiveTrader._execute_close` prefers `order.average_price` for the
  recorded exit price (caller-passed `exit_price` falls through as a
  fallback for legacy adapters), pops the entry fee, sums it with
  `order.fee`, and threads `total_fees` into
  `TradeHistoryTracker.close_trade(fees=)`.

## Files Changed

- `src/models.py`
- `src/exchange/base.py`
- `src/exchange/binance.py`
- `src/exchange/bybit.py`
- `src/trading/live.py`
- `tests/test_live_trading.py`
- `tests/test_exchange_binance.py`
- `tests/test_exchange_bybit.py`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/consistency-hardening/functional-design/spec.md`
- `aidlc-docs/construction/plans/consistency-hardening-code-generation-live-fill-attribution-plan.md`

## Tests / Checks Run

- `uv run pytest tests/test_live_trading.py tests/test_models.py
  tests/test_exchange_binance.py tests/test_exchange_bybit.py
  tests/test_exchange_base.py tests/test_main_dispatch.py` — 240/240
  passed (5 new tests).
- `uv run ruff check` clean for the eight changed files.
- `uv run black` applied (auto-format on `src/exchange/base.py` and
  `src/trading/live.py`).
- `uv run mypy` clean for the five changed source files. The
  unrelated `src/backtest/harness.py:113` error remains (CH-09 scope).

## Decisions

- Helpers prefixed with `_` to mark them as adapter-internal even
  though they live in the public `src/exchange/base.py` module. Two
  callers today (Binance + Bybit); they're explicitly not part of the
  abstract `BaseExchange` API, so leaving them module-level avoids
  growing the abstract contract.
- `_extract_ccxt_fee` prefers the per-fill `fees` list over the
  unified `fee` block when both are present — ccxt sometimes
  duplicates the totals and we want to avoid double-counting.
- Caller-passed `exit_price` is still honoured as a fallback so the
  manual-close path doesn't break if a venue ever returns a market
  order without an `average`. Long-term this can be removed once
  every adapter is known-good; for now it preserves safe legacy
  behaviour while the exchange-reported value wins.
- Entry price recorded into the in-memory `Position` is
  exchange-authoritative so the SL/TP gate inside `monitor_positions`
  evaluates against the price actually paid. Otherwise a paper-mode
  cleanup that adjusted `position.entry_price` to a fill could leave
  live in disagreement with its own SL/TP math.

## Risks

- Low. The new fields default to `None`, so adapters and tests that
  don't supply them still build valid `Order` objects. The fee
  capture path opts in via `order.fee or Decimal("0")` so an adapter
  returning no fee data falls back to the prior behaviour (zero fees,
  same as before).

## Debt Added / Resolved

- No new tech-debt entries. Pre-existing
  `src/backtest/harness.py:113` mypy error remains queued under CH-09.

## Follow-up

- CH-07: live position rehydration — on `LiveTrader.__init__`,
  rebuild `_open_positions` from the persisted `TradeHistory.get_open_trades`
  set so SL/TP enforcement survives a process restart.

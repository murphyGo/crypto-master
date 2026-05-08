# Session: consistency-hardening CH-27 Backtest Fill/Close Helpers

## Unit

- `consistency-hardening`
- Primary owner unit: `backtesting-validation`

## Related Requirements

- FR-025 Execute backtests against historical data
- NFR-006 Store backtest results in structured artifacts

## Changes

- Added `Backtester._open_trade_from_position()`.
- Added `Backtester._close_open_trade_at_end_of_data()`.
- Routed both single-timeframe and multi-timeframe loops through the helpers.

## Tests

- `uv run pytest tests/test_backtest_engine.py tests/test_backtest_multi_timeframe.py -q`
  - 54 passed.
- `uv run ruff check src/backtest/engine.py`
  - passed.
- `uv run black --check src/backtest/engine.py`
  - passed.
- `uv run mypy src/backtest/engine.py`
  - passed.

## Decisions

- Continue reducing duplicated loop mechanics in small verified steps rather
  than extracting the full analysis/breaker branch in one high-risk change.

## Risks

- CH-27 remains incomplete; analysis invocation and breaker counter handling are
  still duplicated between single-TF and multi-TF loops.

# Session: consistency-hardening CH-27 Backtest Exit Helper

## Unit

- `consistency-hardening`
- Primary owner unit: `backtesting-validation`

## Related Requirements

- FR-025 Execute backtests against historical data
- NFR-006 Store backtest results in structured artifacts

## Changes

- Added `Backtester._close_open_trade_if_exit_hit()`.
- Routed both single-timeframe and multi-timeframe loops through the helper.
- Preserved liquidation marking and balance update semantics.

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

- Ship the exit-helper extraction as a narrow behavior-preserving step before
  attempting full `_execute_bar` extraction.

## Risks

- CH-27 remains incomplete; analysis invocation and entry-fill branches are
  still duplicated between single-TF and multi-TF loops.

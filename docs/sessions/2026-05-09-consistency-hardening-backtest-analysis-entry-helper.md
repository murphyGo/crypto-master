# Session: consistency-hardening CH-27 Backtest Analysis Entry Helper

## Unit

- `consistency-hardening`
- Primary owner unit: `backtesting-validation`

## Related Requirements

- FR-025 Execute backtests against historical data
- NFR-006 Store backtest results in structured artifacts

## Changes

- Added `Backtester._open_trade_from_analysis()`.
- Routed both single-timeframe and multi-timeframe loops through the helper.
- Preserved neutral-signal filtering, trading-profile acceptance, validation
  rejection, and existing simulated fill behavior.

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

- Kept analysis invocation and circuit-breaker counters unchanged in this slice
  because single-TF and multi-TF calls still have different argument shapes.

## Risks

- CH-27 remains open for the final analysis invocation / breaker counter
  deduplication pass.

# CH-27 Backtest Exit Helper

## Summary

`Backtester.run()` and `Backtester.run_multi_timeframe()` now share
`_close_open_trade_if_exit_hit()` for intra-candle SL/TP close handling. The
helper preserves the existing close, balance update, liquidation marker, and
trade append behavior.

This is a foundation slice for the larger CH-27 simulation-loop deduplication.
Full `_execute_bar` extraction remains open.

## Verification

- `uv run pytest tests/test_backtest_engine.py tests/test_backtest_multi_timeframe.py -q`
  - 54 passed.
- `uv run ruff check src/backtest/engine.py`
  - passed.
- `uv run black --check src/backtest/engine.py`
  - passed.
- `uv run mypy src/backtest/engine.py`
  - passed.

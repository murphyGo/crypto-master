# CH-27 Backtest Fill/Close Helpers

## Summary

`Backtester.run()` and `Backtester.run_multi_timeframe()` now share helper
logic for:

- simulated entry slippage, fee affordability, and `_OpenTrade` creation,
- end-of-data forced close, balance update, liquidation marker, and trade
  append behavior.

This follows the prior intra-candle exit helper and further reduces duplicated
simulation-loop mechanics. Full analysis/breaker branch extraction remains
open.

## Verification

- `uv run pytest tests/test_backtest_engine.py tests/test_backtest_multi_timeframe.py -q`
  - 54 passed.
- `uv run ruff check src/backtest/engine.py`
  - passed.
- `uv run black --check src/backtest/engine.py`
  - passed.
- `uv run mypy src/backtest/engine.py`
  - passed.

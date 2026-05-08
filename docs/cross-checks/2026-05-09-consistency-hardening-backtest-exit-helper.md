# Cross-Check: consistency-hardening CH-27 Backtest Exit Helper

## Scope

Verify that extracting intra-candle exit handling into a shared helper preserves
single-timeframe and multi-timeframe backtest behavior.

## Requirements

- FR-025 Execute backtests against historical data
- NFR-006 Store backtest results in structured artifacts

## Evidence

- Both `Backtester.run()` and `Backtester.run_multi_timeframe()` call
  `_close_open_trade_if_exit_hit()`.
- The helper uses the same `_check_intra_candle_exit()`, `_close_trade()`, and
  `_mark_if_liquidated()` path as the previous duplicated code.

## Verification

- `uv run pytest tests/test_backtest_engine.py tests/test_backtest_multi_timeframe.py -q`
  - 54 passed.
- `uv run ruff check src/backtest/engine.py`
  - passed.
- `uv run black --check src/backtest/engine.py`
  - passed.
- `uv run mypy src/backtest/engine.py`
  - passed.

## Result

PASS. The exit-helper extraction is behavior-preserving. CH-27 remains open for
full simulation-step deduplication.

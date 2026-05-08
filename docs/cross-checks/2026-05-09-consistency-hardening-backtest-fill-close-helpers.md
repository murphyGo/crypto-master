# Cross-Check: consistency-hardening CH-27 Backtest Fill/Close Helpers

## Scope

Verify that entry-fill and end-of-data close helper extraction preserves
single-timeframe and multi-timeframe backtest behavior.

## Requirements

- FR-025 Execute backtests against historical data
- NFR-006 Store backtest results in structured artifacts

## Evidence

- Both simulation loops call `_open_trade_from_position()`.
- Both simulation loops call `_close_open_trade_at_end_of_data()`.
- Existing slippage, fee, end-of-data, and liquidation tests remain green.

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

PASS. The fill/close helper extraction is behavior-preserving. CH-27 remains
open for analysis/breaker deduplication.

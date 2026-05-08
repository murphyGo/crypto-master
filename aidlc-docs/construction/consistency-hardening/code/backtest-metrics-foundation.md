# CH-26 Backtest Metrics Foundation

## Summary

Added `src/backtest/metrics.py` as the shared home for low-risk metric helpers:

- `count_trade_outcomes`
- `return_percent`
- `sharpe_from_returns`
- `sharpe_from_trade_pnls`

`Backtester`, `PerformanceAnalyzer`, `RobustnessGate`, and `BacktestHarness`
now share these helpers for outcome counts, return percentage, and Sharpe
calculation. This keeps behavior unchanged while reducing duplicate formulas
before moving the larger max-drawdown surfaces.

## Verification

- `uv run pytest tests/test_backtest_metrics.py tests/test_backtest_analyzer.py tests/test_backtest_validator.py tests/test_backtest_engine.py tests/test_backtest_harness.py -q`
  - 102 passed.
- `uv run ruff check src/backtest/metrics.py src/backtest/analyzer.py src/backtest/validator.py src/backtest/engine.py src/backtest/harness.py tests/test_backtest_metrics.py`
  - passed.
- `uv run black --check src/backtest/metrics.py src/backtest/analyzer.py src/backtest/validator.py src/backtest/engine.py src/backtest/harness.py tests/test_backtest_metrics.py`
  - passed.
- `uv run mypy src/backtest/metrics.py src/backtest/analyzer.py src/backtest/validator.py src/backtest/engine.py src/backtest/harness.py`
  - passed.

## Remaining CH-26 Scope

Max drawdown consolidation remains open so liquidation-truncated equity-curve
semantics can be moved without changing reported values.

# CH-26 Backtest Metrics Foundation

## Summary

Added `src/backtest/metrics.py` as the shared home for low-risk metric helpers:

- `count_trade_outcomes`
- `return_percent`
- `sharpe_from_returns`
- `sharpe_from_trade_pnls`
- `max_drawdown_from_equity_values`

`Backtester`, `PerformanceAnalyzer`, `RobustnessGate`, and `BacktestHarness`
now share these helpers for outcome counts, return percentage, Sharpe
calculation, and analyzer max drawdown calculation. This keeps behavior
unchanged while reducing duplicate formulas.

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

CH-26 is complete. Liquidation-truncated equity-curve semantics remain owned by
`Backtester._build_result()` and are covered by existing engine/analyzer tests.

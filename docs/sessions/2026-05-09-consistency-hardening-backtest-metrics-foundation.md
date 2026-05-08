# Session: consistency-hardening CH-26 Backtest Metrics Foundation

## Unit

- `consistency-hardening`
- Primary owner units: `backtesting-validation`, `quality-governance`

## Related Requirements

- FR-021 Analyze strategy performance and generate reports
- FR-025 Execute backtests against historical data
- FR-034 Gate strategy promotion through robustness validation
- NFR-006 Store backtest results in structured artifacts

## Changes

- Added `src/backtest/metrics.py`.
- Moved shared trade outcome counts, return percentage, and Sharpe tail
  calculations into the metrics module.
- Moved analyzer max-drawdown peak-to-trough calculation into the metrics
  module.
- Routed `Backtester`, `PerformanceAnalyzer`, `RobustnessGate`, and
  `BacktestHarness` through the shared helpers.
- Added direct tests for shared metric helpers.

## Tests

- `uv run pytest tests/test_backtest_metrics.py tests/test_backtest_analyzer.py tests/test_backtest_validator.py tests/test_backtest_engine.py tests/test_backtest_harness.py -q`
  - 102 passed.
- `uv run ruff check src/backtest/metrics.py src/backtest/analyzer.py src/backtest/validator.py src/backtest/engine.py src/backtest/harness.py tests/test_backtest_metrics.py`
  - passed.
- `uv run black --check src/backtest/metrics.py src/backtest/analyzer.py src/backtest/validator.py src/backtest/engine.py src/backtest/harness.py tests/test_backtest_metrics.py`
  - passed.
- `uv run mypy src/backtest/metrics.py src/backtest/analyzer.py src/backtest/validator.py src/backtest/engine.py src/backtest/harness.py`
  - passed.
- `uv run pytest tests/test_backtest_metrics.py tests/test_backtest_analyzer.py tests/test_backtest_engine.py -q`
  - 78 passed after the MDD completion slice.
- `uv run mypy src/backtest/metrics.py src/backtest/analyzer.py`
  - passed after the MDD completion slice.

## Decisions

- Keep liquidation truncation in `Backtester._build_result()` and consolidate
  the pure peak-to-trough calculation in `src/backtest/metrics.py`.

## Risks

- None observed in targeted backtest suites. Reported values should be unchanged.

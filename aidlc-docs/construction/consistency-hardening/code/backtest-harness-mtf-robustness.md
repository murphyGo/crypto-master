# CH-09 Backtest Harness Multi-TF + Robustness Reporting

## Summary

`BacktestHarness` now carries same-symbol multi-timeframe OHLCV windows through
sub-account combination runs and calls `Backtester.run_for_strategy()` so
strategies declaring `requires_multi_timeframe=True` route to
`run_multi_timeframe()`.

Robustness evaluation now runs for every selected strategy. The existing
account-level `robustness_passed` field remains for compatibility, while
`MultiAccountReport.robustness_by_strategy` preserves per-strategy evidence.

## Verification

- `uv run pytest tests/test_backtest_harness.py -q`
  - 3 passed.
- `uv run black --check src/backtest/harness.py src/backtest/multi_account_report.py tests/test_backtest_harness.py`
  - passed.
- `uv run ruff check src/backtest/harness.py src/backtest/multi_account_report.py tests/test_backtest_harness.py`
  - passed.
- `uv run mypy src/backtest/harness.py src/backtest/multi_account_report.py`
  - passed.

# Session: consistency-hardening CH-09 Backtest Harness MTF + Robustness

## Unit

- `consistency-hardening`
- Primary owner units: `backtesting-validation`, `strategy-framework`

## Related Requirements

- FR-025 Execute backtests against historical data
- FR-034 Gate strategy promotion through robustness validation
- FR-038 Run strategy-combination A/B backtests by sub-account
- NFR-006 Store backtest results in structured artifacts

## Changes

- Built same-symbol `ohlcv_by_timeframe` context inside `BacktestHarness`.
- Replaced direct `Backtester.run()` calls with `run_for_strategy()` so
  multi-timeframe strategies use `run_multi_timeframe()`.
- Passed multi-timeframe context to robustness gate evaluation.
- Evaluated robustness for every selected strategy per sub-account.
- Added `MultiAccountReport.robustness_by_strategy` while preserving existing
  account-level `robustness_passed`.

## Tests

- `uv run pytest tests/test_backtest_harness.py -q`
  - 3 passed.
- `uv run black --check src/backtest/harness.py src/backtest/multi_account_report.py tests/test_backtest_harness.py`
  - passed.
- `uv run ruff check src/backtest/harness.py src/backtest/multi_account_report.py tests/test_backtest_harness.py`
  - passed.
- `uv run mypy src/backtest/harness.py src/backtest/multi_account_report.py`
  - passed.

## Decisions

- Keep `robustness_passed` as an aggregate compatibility field and add the new
  per-strategy field for detailed operator evidence.
- Scope multi-timeframe grouping to the selected report symbol, matching the
  existing single-symbol report model.

## Risks

- Multi-symbol combination reporting still needs a future report-model
  expansion before one harness run can represent multiple symbols explicitly.

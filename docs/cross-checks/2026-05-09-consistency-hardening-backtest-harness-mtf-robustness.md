# Cross-Check: consistency-hardening CH-09 Backtest Harness MTF + Robustness

## Scope

Verify that `BacktestHarness` routes multi-timeframe strategies through the
multi-TF backtester path and records robustness evidence per strategy.

## Requirements

- FR-025 Execute backtests against historical data
- FR-034 Gate strategy promotion through robustness validation
- FR-038 Run strategy-combination A/B backtests by sub-account
- NFR-006 Store backtest results in structured artifacts

## Evidence

- `BacktestHarness._run_one()` now calls `Backtester.run_for_strategy()` with
  same-symbol `ohlcv_by_timeframe`.
- Multi-timeframe strategy tests assert the strategy receives both `1h` and
  `4h` context.
- Robustness gate tests assert the gate receives `ohlcv_by_timeframe`.
- `MultiAccountReport` now includes `robustness_by_strategy` while preserving
  `robustness_passed`.

## Verification

- `uv run pytest tests/test_backtest_harness.py -q`
  - 3 passed.
- `uv run black --check src/backtest/harness.py src/backtest/multi_account_report.py tests/test_backtest_harness.py`
  - passed.
- `uv run ruff check src/backtest/harness.py src/backtest/multi_account_report.py tests/test_backtest_harness.py`
  - passed.
- `uv run mypy src/backtest/harness.py src/backtest/multi_account_report.py`
  - passed.

## Result

PASS. CH-09 closes the harness-level multi-timeframe routing gap and preserves
strategy-level robustness evidence in the report model.

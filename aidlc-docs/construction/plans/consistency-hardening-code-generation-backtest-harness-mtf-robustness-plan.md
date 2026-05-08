# Code Generation Plan: consistency-hardening - CH-09 Backtest harness MTF + robustness reporting

## Task

Route multi-timeframe strategies through the backtester multi-TF dispatcher in
`BacktestHarness` and preserve robustness results per strategy instead of only
storing a single account-level boolean.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-09
- Primary owner units: `backtesting-validation`, `strategy-framework`

## Related Requirements

- FR-025 Execute backtests against historical data
- FR-034 Gate strategy promotion through robustness validation
- FR-038 Run strategy-combination A/B backtests by sub-account
- NFR-006 Store backtest results in structured artifacts

## Steps

- [x] Pass same-symbol multi-timeframe OHLCV windows through the harness.
- [x] Use `Backtester.run_for_strategy()` so MTF strategies route to
      `run_multi_timeframe()`.
- [x] Evaluate robustness for every selected strategy and preserve
      per-strategy results in `MultiAccountReport`.
- [x] Tests: harness passes multi-TF context into MTF strategy and robustness
      gate receives `ohlcv_by_timeframe`.
- [x] Targeted pytest: `uv run pytest tests/test_backtest_harness.py -q`.

## Verification

- [x] Targeted tests pass.
- [x] Formatting/lint run for changed source/test files where practical.

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Tests added.
- [x] Plan steps closed.
- [x] State/spec updated.
- [x] Session log and cross-check written.

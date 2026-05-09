# Session: consistency-hardening CH-27 Execute Bar Dedup

## Unit

- `consistency-hardening`
- Primary owner unit: `backtesting-validation`

## Summary

Completed the CH-27 follow-up by extracting shared per-bar execution into
`Backtester._execute_bar`. Both `Backtester.run` and
`Backtester.run_multi_timeframe` now route through the same helper for:

- intra-candle SL/TP checks
- warmup and concurrent-position gates
- per-bar timeout and parse/strategy circuit breakers
- cumulative parse-failure checks
- position creation, slippage, fee, and balance updates

The single-TF and multi-TF loops now only prepare their strategy context
(`ohlcv` slice vs multi-timeframe slice) and delegate execution.

## Tests

- `uv run pytest tests/test_backtest_engine.py tests/test_backtest_multi_timeframe.py -q`
- `uv run black --check src/backtest/engine.py tests/test_backtest_multi_timeframe.py`
- `uv run ruff check src/backtest/engine.py tests/test_backtest_multi_timeframe.py`
- `uv run mypy src/backtest/engine.py`

## Regression

Added a deterministic single-TF vs one-timeframe multi-TF parity test that
compares the closed-trade ledger excluding random trade IDs.

## Risks

- No runtime data was touched.
- Remaining consistency-hardening work starts at CH-28.

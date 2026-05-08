# Code Generation Plan: consistency-hardening - CH-27 Fill/close helpers

## Task

Continue CH-27 simulation-loop deduplication by extracting duplicated entry-fill
and end-of-data close handling from the single-TF and multi-TF backtest loops.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-27 fill/close helpers
- Primary owner unit: `backtesting-validation`

## Related Requirements

- FR-025 Execute backtests against historical data
- NFR-006 Store backtest results in structured artifacts

## Steps

- [x] Add shared helper for simulated entry fill.
- [x] Add shared helper for end-of-data forced close.
- [x] Route `Backtester.run()` through both helpers.
- [x] Route `Backtester.run_multi_timeframe()` through both helpers.
- [x] Targeted pytest: `uv run pytest tests/test_backtest_engine.py
      tests/test_backtest_multi_timeframe.py -q`.

## Verification

- [x] Targeted tests pass.
- [x] Ruff/black/mypy pass for changed file.

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Plan steps closed.
- [x] State/spec updated.
- [x] Session log and cross-check written.

# Code Generation Plan: consistency-hardening - CH-27 Exit helper

## Task

Start CH-27 simulation-loop deduplication by extracting the identical
single-TF and multi-TF intra-candle exit handling block into a shared helper.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-27 exit helper
- Primary owner unit: `backtesting-validation`

## Related Requirements

- FR-025 Execute backtests against historical data
- NFR-006 Store backtest results in structured artifacts

## Steps

- [x] Add a shared helper for intra-candle close/liquidation append behavior.
- [x] Route `Backtester.run()` through the helper.
- [x] Route `Backtester.run_multi_timeframe()` through the helper.
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

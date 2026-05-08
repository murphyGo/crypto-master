# Code Generation Plan: consistency-hardening - CH-26 Backtest metrics foundation

## Task

Introduce a shared backtest metrics module and route low-risk duplicated
calculations through it before continuing the broader CH-26 drawdown
consolidation.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-26 foundation
- Primary owner units: `backtesting-validation`, `quality-governance`

## Related Requirements

- FR-021 Analyze strategy performance and generate reports
- FR-025 Execute backtests against historical data
- FR-034 Gate strategy promotion through robustness validation
- NFR-006 Store backtest results in structured artifacts

## Steps

- [x] Add `src/backtest/metrics.py` with shared outcome, return, and Sharpe
      helpers.
- [x] Route `Backtester`, `PerformanceAnalyzer`, `RobustnessGate`, and
      `BacktestHarness` through the shared helpers where behavior is identical.
- [x] Add direct unit tests for the shared metrics helpers.
- [x] Targeted pytest: `uv run pytest tests/test_backtest_metrics.py
      tests/test_backtest_analyzer.py tests/test_backtest_validator.py
      tests/test_backtest_engine.py tests/test_backtest_harness.py -q`.
- [x] Run ruff, black, and mypy for changed backtest files.

## Verification

- [x] 102 targeted tests passed.
- [x] Ruff passed.
- [x] Black check passed.
- [x] Mypy passed for changed backtest source files.

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Tests added.
- [x] Plan steps closed.
- [x] State/spec updated.
- [x] Session log and cross-check written.

## Remaining CH-26 Work

- Consolidate max drawdown helper behavior across analyzer and any remaining
  callers.
- Keep liquidation-truncated equity-curve semantics pinned while moving MDD
  into the shared metrics module.

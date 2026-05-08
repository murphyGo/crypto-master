# Code Generation Plan: consistency-hardening - CH-26 MDD consolidation

## Task

Move max-drawdown peak-to-trough calculation into `src/backtest/metrics.py`
while preserving analyzer behavior and liquidation-truncated equity curve
semantics from the backtest engine.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-26 MDD completion
- Primary owner units: `backtesting-validation`, `quality-governance`

## Related Requirements

- FR-021 Analyze strategy performance and generate reports
- FR-025 Execute backtests against historical data
- NFR-006 Store backtest results in structured artifacts

## Steps

- [x] Add shared `max_drawdown_from_equity_values` helper.
- [x] Route analyzer closed-trade fallback MDD through the shared helper.
- [x] Route analyzer equity-curve MDD through the shared helper.
- [x] Add direct helper test for peak-to-trough MDD percent.
- [x] Targeted pytest: `uv run pytest tests/test_backtest_metrics.py
      tests/test_backtest_analyzer.py tests/test_backtest_engine.py -q`.
- [x] Run ruff, black, and mypy for changed files.

## Verification

- [x] 78 targeted tests passed.
- [x] Ruff passed.
- [x] Black check passed.
- [x] Mypy passed for changed files.

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Tests added.
- [x] Plan steps closed.
- [x] State/spec updated.
- [x] Session log and cross-check updated.

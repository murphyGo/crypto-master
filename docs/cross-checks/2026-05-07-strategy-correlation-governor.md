# Cross-Check: Strategy Correlation Governor

## Scope

Verify that Strategy Correlation Governor provides normalized exposure inputs,
duplicate-exposure warnings, and an optional runtime rejection gate.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Backtest exposures normalize into common inputs | Complete | `CorrelationInputSet.from_backtest_results` converts `BacktestTrade` ledgers into `CorrelationExposure`. |
| Runtime trade history normalizes into common inputs | Complete | `CorrelationInputSet.from_trade_history` converts `TradeHistory` records and optional strategy lookup data. |
| Duplicate exposure warnings exist | Complete | `compute_duplicate_exposure_warnings` emits symbol/side and strategy/symbol/side warnings across distinct sub-accounts. |
| Warning thresholds are configurable | Complete | `CorrelationWarningPolicy` controls tolerated sub-account counts for each warning type. |
| Runtime rejection gate is optional | Complete | `evaluate_correlation_gate` allows advisory mode by default and rejects only when `CorrelationGateConfig.enabled` is true. |

## Implementation Evidence

- `src/runtime/correlation_governor.py`
- `src/runtime/__init__.py`
- `tests/test_runtime_correlation_governor.py`

## Test Evidence

- `uv run pytest tests/test_runtime_correlation_governor.py -q`
- `uv run ruff check src/runtime/correlation_governor.py src/runtime/__init__.py tests/test_runtime_correlation_governor.py`
- `uv run black --check src/runtime/correlation_governor.py src/runtime/__init__.py tests/test_runtime_correlation_governor.py`
- `uv run mypy src`
- `uv run pytest -q`

## Gaps and Risks

- The gate is implemented as a pure decision helper and is not yet wired into
  `TradingEngine`; this preserves the unit's optional/advisory posture until an
  operator policy is chosen.

## Unit Mapping

- **Primary Unit**: `strategy-correlation-governor`
- **Related Units**: `proposal-runtime`, `sub-account-capital-segmentation`, `dashboard-operator-ui`

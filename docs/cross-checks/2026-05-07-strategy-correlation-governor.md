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
| Runtime advisory/rejection wiring exists | Complete | `TradingEngine` collects open trades across active sub-account traders, emits `correlation_warning` in advisory mode, and rejects when the opt-in gate is enabled. |
| Runtime strategy matching uses proposal history | Complete | Open trade ids are mapped back to proposal technique names so strategy/symbol/side policy works even when `TradeHistory.performance_record_id` is absent. |
| Empty/open-only runtime states are safe | Complete | `CorrelationInputSet` supports empty existing exposure sets and `open_only()` filters closed historical trades. |

## Implementation Evidence

- `src/runtime/correlation_governor.py`
- `src/runtime/engine.py`
- `src/runtime/__init__.py`
- `tests/test_runtime_correlation_governor.py`
- `tests/test_runtime_engine.py`

## Test Evidence

- `uv run pytest tests/test_runtime_correlation_governor.py -q`
- `uv run ruff check src/runtime/correlation_governor.py src/runtime/__init__.py tests/test_runtime_correlation_governor.py`
- `uv run black --check src/runtime/correlation_governor.py src/runtime/__init__.py tests/test_runtime_correlation_governor.py`
- `uv run pytest tests/test_runtime_engine.py::test_correlation_warning_is_advisory_by_default tests/test_runtime_engine.py::test_correlation_gate_rejects_when_enabled tests/test_runtime_engine.py::test_correlation_gate_uses_proposal_history_strategy_lookup -q`
- `uv run mypy src`
- `uv run pytest -q`

## Gaps and Risks

- The gate is wired at the engine level but policy tuning is still code/env
  driven; there is no dashboard control for changing correlation thresholds.

## Unit Mapping

- **Primary Unit**: `strategy-correlation-governor`
- **Related Units**: `proposal-runtime`, `sub-account-capital-segmentation`, `dashboard-operator-ui`

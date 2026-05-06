# Cross-Check: DEBT-022 Cumulative Parse-Failure Breaker

## Scope

Verify that the backtester now aborts intermittent parse-failure patterns that
avoid the existing consecutive-failure breaker.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Consecutive breaker remains unchanged | Complete | Existing `test_consecutive_parse_failures_trip_breaker` still asserts `reason="consecutive_parse_failures"`. |
| Single-timeframe cumulative breaker exists | Complete | `test_cumulative_parse_failure_rate_trips_breaker` alternates parse failures and neutral successes, then asserts `reason="cumulative_parse_failure_rate"`. |
| Multi-timeframe cumulative breaker exists | Complete | `test_cumulative_parse_failure_rate_trips_multi_tf_breaker` covers `run_multi_timeframe`. |
| Thresholds are configurable | Complete | `BacktestConfig.min_cumulative_parse_failures` and `max_cumulative_parse_failure_rate` are mirrored by `Settings.engine_backtest_*` fields. |
| Operator env docs are updated | Complete | `.env.example` documents the cumulative threshold variables. |
| Debt and AI-DLC maps are updated | Complete | `docs/TECH-DEBT.md` resolves DEBT-022 and `aidlc-docs/inception/units/debt-unit-map.md` shows no active debt. |

## Implementation Evidence

- `src/backtest/engine.py`
- `src/config.py`
- `tests/test_backtest_engine.py`
- `tests/test_backtest_multi_timeframe.py`
- `tests/test_config.py`
- `.env.example`

## Test Evidence

- `uv run pytest tests/test_backtest_engine.py::TestPerBarCircuitBreaker tests/test_backtest_multi_timeframe.py::TestRunMultiTimeframeSemantics::test_cumulative_parse_failure_rate_trips_multi_tf_breaker tests/test_config.py::TestBacktestEngineSettings -q`
- `uv run ruff check src/backtest/engine.py src/config.py tests/test_backtest_engine.py tests/test_backtest_multi_timeframe.py tests/test_config.py`
- `uv run mypy src`

## Gaps and Risks

- The breaker counts `ClaudeParseError` and `StrategyError` failures, matching
  the existing consecutive breaker. `StrategyValidationError` remains a warmup
  skip and does not count toward either breaker.

## Unit and Debt Mapping

- **Primary Unit**: `backtesting-validation`
- **Related Debt**: DEBT-022 resolved
- **Legacy Phase Context**: Phase 17.2 circuit breaker hardening

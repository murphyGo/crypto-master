# Session Log: 2026-05-07 - backtesting-validation - DEBT-022 Cumulative Breaker

## Overview

- **Date**: 2026-05-07
- **Primary Unit**: `backtesting-validation`
- **Stage**: Code Generation
- **Task**: Close DEBT-022 by adding a cumulative parse-failure-rate breaker to the backtester.

## Work Summary

The existing per-bar breaker handled timeouts and consecutive
parse/strategy failures. It did not catch alternating fail/success patterns
that avoid the consecutive counter while still wasting a large fraction of
LLM-backed analysis calls.

This cycle adds cumulative failure counters to both `Backtester.run` and
`Backtester.run_multi_timeframe`. When cumulative parse/strategy failures
exceed the configured minimum sample and the failure ratio is above the
configured threshold, the backtester aborts with
`BacktestAbortedError(reason="cumulative_parse_failure_rate")`.

## Files Changed

- Modified: `src/backtest/engine.py`
- Modified: `src/config.py`
- Modified: `tests/test_backtest_engine.py`
- Modified: `tests/test_backtest_multi_timeframe.py`
- Modified: `tests/test_config.py`
- Modified: `.env.example`
- Modified: `docs/TECH-DEBT.md`
- Modified: `aidlc-docs/inception/units/debt-unit-map.md`
- Modified: `aidlc-docs/construction/plans/backtesting-validation-code-generation-plan.md`
- Created: `docs/cross-checks/2026-05-07-debt-022-cumulative-parse-failure-breaker.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Keep the consecutive breaker unchanged | All-fail structural failures should still abort quickly at the existing threshold. |
| Add the cumulative breaker after the consecutive check | The more specific fast-fail reason remains stable for fully broken strategies. |
| Mirror thresholds into `Settings` | Operators can tune noisy LLM-backed backtests without code changes. |

## Verification

- `uv run pytest tests/test_backtest_engine.py::TestPerBarCircuitBreaker tests/test_backtest_multi_timeframe.py::TestRunMultiTimeframeSemantics::test_cumulative_parse_failure_rate_trips_multi_tf_breaker tests/test_config.py::TestBacktestEngineSettings -q`
- `uv run ruff check src/backtest/engine.py src/config.py tests/test_backtest_engine.py tests/test_backtest_multi_timeframe.py tests/test_config.py`
- `uv run mypy src`

## Code Review Results

| Category | Status |
|----------|--------|
| Breaker Semantics | ✅ |
| Backward Compatibility | ✅ |
| Configuration | ✅ |
| Tests | ✅ |

## TECH-DEBT Items

- Resolved: DEBT-022.

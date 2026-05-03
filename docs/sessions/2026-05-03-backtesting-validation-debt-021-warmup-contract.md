# Session Log: 2026-05-03 - backtesting-validation - DEBT-021 Warmup Contract

## Overview

- **Date**: 2026-05-03
- **Unit**: `backtesting-validation`
- **Secondary Unit**: `strategy-framework`
- **Task**: Resolve DEBT-021 by making strategy-specific minimum warmup part of
  the backtester contract.

## Work Summary

Added a declared strategy warmup contract and changed backtester warmup gates to
use the maximum of engine configuration and strategy minimum. This removes the
contract mismatch where `BacktestConfig.warmup_candles` could be lower than a
strategy's real internal floor.

## Files Changed

- Modified: `src/strategy/base.py`
- Modified: `strategies/rsi.py`
- Modified: `src/backtest/engine.py`
- Modified: `src/backtest/validator.py`
- Modified: `tests/test_backtest_engine.py`
- Modified: `tests/test_backtest_multi_timeframe.py`
- Modified: `tests/test_rsi_variants.py`
- Modified: `docs/TECH-DEBT.md`
- Modified: `aidlc-docs/inception/units/debt-unit-map.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Add `TechniqueInfo.min_warmup_candles` | Prompt/code strategies can declare static warmup through metadata. |
| Add `BaseStrategy.minimum_candles` | Strategies with dynamic constructor tunables can override the property. |
| Add `Backtester.effective_warmup_candles(strategy)` | Centralizes the `max(config, strategy)` policy for run loops and robustness pre-checks. |
| Keep `StrategyValidationError` skip handling | It remains a defensive guard for unexpected or dynamic validation failures. |

## Verification

```bash
uv run pytest tests/test_backtest_engine.py::TestBacktesterGuards::test_strategy_minimum_candles_raises_effective_warmup tests/test_backtest_multi_timeframe.py::TestRunMultiTimeframeSemantics::test_strategy_minimum_candles_raises_multi_tf_warmup tests/test_rsi_variants.py::test_rsi_declares_dynamic_minimum_candles -q
uv run black src/strategy/base.py strategies/rsi.py src/backtest/engine.py src/backtest/validator.py tests/test_backtest_engine.py tests/test_backtest_multi_timeframe.py tests/test_rsi_variants.py
uv run pytest tests/test_backtest_engine.py tests/test_backtest_multi_timeframe.py tests/test_backtest_validator.py tests/test_rsi_variants.py -q
uv run ruff check src/strategy/base.py strategies/rsi.py src/backtest/engine.py src/backtest/validator.py tests/test_backtest_engine.py tests/test_backtest_multi_timeframe.py tests/test_rsi_variants.py
uv run mypy src/strategy/base.py src/backtest/engine.py src/backtest/validator.py
```

Result: targeted 3 passed; broader related suite 79 passed; ruff passed; mypy
passed on touched source files.

## Risks

- Existing strategies that do not declare `minimum_candles` retain previous
  behavior through the `0` metadata default.
- RSI now starts analysis at 42 candles by default in backtests, matching its own
  validation floor. This can reduce analyzed bars compared with the previous
  workaround, but removes misleading operator expectations.

## TECH-DEBT Items

- Resolved: DEBT-021.

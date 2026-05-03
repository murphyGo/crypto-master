# Cross-Check: DEBT-021 Warmup Contract

## Scope

- **Primary Unit**: `backtesting-validation`
- **Secondary Unit**: `strategy-framework`
- **Related Debt**: DEBT-021
- **Legacy Phase Context**: Phase 17.2

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| FR-025 Backtesting Execution | Complete | `Backtester.run`, `run_multi_timeframe`, and robustness pre-checks use effective strategy-aware warmup. |
| FR-003 Chart Analysis Technique Definition | Complete | `TechniqueInfo.min_warmup_candles` exposes static warmup metadata. |
| NFR-010 Analysis Technique Extensibility | Complete | Strategies can use metadata defaults or override `BaseStrategy.minimum_candles` for dynamic tunables. |

## Implementation Evidence

- `src/strategy/base.py`: adds `TechniqueInfo.min_warmup_candles` and
  `BaseStrategy.minimum_candles`.
- `strategies/rsi.py`: declares dynamic RSI warmup as `period * 3`.
- `src/backtest/engine.py`: adds `effective_warmup_candles(strategy)` and uses
  it in single-TF and multi-TF warmup gates.
- `src/backtest/validator.py`: robustness OOS and walk-forward pre-checks use
  effective strategy-aware warmup.

## Test Evidence

```bash
uv run pytest tests/test_backtest_engine.py::TestBacktesterGuards::test_strategy_minimum_candles_raises_effective_warmup tests/test_backtest_multi_timeframe.py::TestRunMultiTimeframeSemantics::test_strategy_minimum_candles_raises_multi_tf_warmup tests/test_rsi_variants.py::test_rsi_declares_dynamic_minimum_candles -q
uv run pytest tests/test_backtest_engine.py tests/test_backtest_multi_timeframe.py tests/test_backtest_validator.py tests/test_rsi_variants.py -q
uv run ruff check src/strategy/base.py strategies/rsi.py src/backtest/engine.py src/backtest/validator.py tests/test_backtest_engine.py tests/test_backtest_multi_timeframe.py tests/test_rsi_variants.py
uv run mypy src/strategy/base.py src/backtest/engine.py src/backtest/validator.py
```

Result: targeted 3 passed; broader related suite 79 passed; ruff passed; mypy
passed on touched source files.

## Gaps and Risks

- Full repository test suite was not run in this pass.
- Prompt strategies with static warmup needs can now declare
  `min_warmup_candles`, but no prompt strategy was changed in this task.

## Recommendations

- Use `BaseStrategy.minimum_candles` for dynamic strategy tunables.
- Use `TechniqueInfo.min_warmup_candles` for generated or prompt strategies with
  static warmup needs.

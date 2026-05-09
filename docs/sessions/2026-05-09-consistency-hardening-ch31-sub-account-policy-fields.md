# Session: consistency-hardening CH-31 sub-account policy fields

Date: 2026-05-09

## Scope

- Completed CH-31 follow-up for sub-account policy-field cleanup.
- Added conflict validation so configs cannot write both root `initial_balance` and `capital_policy.initial_balance`, or both root `strategy_filter` and `strategy_policy.strategy_filter`.
- Migrated runtime-facing tests and marketplace templates to policy blocks.
- Made `RiskPolicy` the canonical runtime risk schema for effective risk/cap/leverage reads.
- Converted `TradingProfile.risk_percent` to `Decimal` and adapted profile/backtest boundaries that still consume float risk percentages.

## Verification

- `uv run pytest tests/test_trading_sub_account.py tests/test_trading_sub_account_registry.py tests/test_trading_profiles.py tests/test_trading_experiment_marketplace.py tests/test_backtest_harness.py tests/test_runtime_engine.py -q`
- `uv run black --check src/trading/sub_account.py src/trading/sub_account_registry.py src/trading/profiles.py src/trading/experiment_marketplace.py src/backtest/engine.py tests/test_trading_sub_account.py tests/test_trading_sub_account_registry.py tests/test_trading_profiles.py tests/test_trading_experiment_marketplace.py tests/test_backtest_harness.py tests/test_runtime_engine.py`
- `uv run ruff check src/trading/sub_account.py src/trading/sub_account_registry.py src/trading/profiles.py src/trading/experiment_marketplace.py src/backtest/engine.py tests/test_trading_sub_account.py tests/test_trading_sub_account_registry.py tests/test_trading_profiles.py tests/test_trading_experiment_marketplace.py tests/test_backtest_harness.py tests/test_runtime_engine.py`
- `uv run mypy src/trading/sub_account.py src/trading/sub_account_registry.py src/trading/profiles.py src/trading/experiment_marketplace.py src/runtime/engine.py src/backtest/harness.py src/backtest/engine.py`

## Notes

- Legacy root fields remain loadable as deprecated reads, but dual-source YAML now fails fast with a clear conflict message.
- Runtime risk reads no longer fall back through `RiskOverrides`; new writes use `RiskPolicy` / `ProposalPolicy`.

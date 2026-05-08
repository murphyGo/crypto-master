# Cross-Check: consistency-hardening CH-31 Default Sub-Account Policy Fields

## Scope

Verify that synthesized default sub-accounts now use policy fields without
changing effective runtime behavior.

## Requirements

- FR-036 Sub-account capital isolation
- FR-037 Sub-account strategy isolation

## Evidence

- `_materialise_default()` now sets `capital_policy=CapitalPolicy(...)`.
- `_materialise_default()` now sets `strategy_policy=StrategyPolicy(...)`.
- `effective_initial_balance()` and `effective_strategy_filter()` preserve the
  previous values for the default account.

## Verification

- `uv run pytest tests/test_trading_sub_account.py tests/test_trading_sub_account_registry.py tests/test_trading_experiment_marketplace.py -q`
  - 33 passed.
- `uv run ruff check src/trading/sub_account_registry.py tests/test_trading_sub_account_registry.py`
  - passed.
- `uv run black --check src/trading/sub_account_registry.py tests/test_trading_sub_account_registry.py`
  - passed.
- `uv run mypy src/trading/sub_account_registry.py`
  - passed.

## Result

PASS. Synthesized default sub-accounts now use `capital_policy` and
`strategy_policy` as their source of truth while preserving effective values.
CH-31 remains open for broader compatibility cleanup.

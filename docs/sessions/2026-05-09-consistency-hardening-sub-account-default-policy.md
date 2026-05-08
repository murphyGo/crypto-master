# Session: consistency-hardening CH-31 Default Sub-Account Policy Fields

## Unit

- `consistency-hardening`
- Primary owner unit: `sub-account-capital-segmentation`

## Related Requirements

- FR-036 Sub-account capital isolation
- FR-037 Sub-account strategy isolation

## Changes

- Updated synthesized default sub-account creation to write
  `capital_policy.initial_balance`.
- Updated synthesized default sub-account creation to write
  `strategy_policy.strategy_filter`.
- Updated registry tests to assert the root compatibility fields stay empty on
  synthesized defaults while effective accessors return the same values.

## Tests

- `uv run pytest tests/test_trading_sub_account.py tests/test_trading_sub_account_registry.py tests/test_trading_experiment_marketplace.py -q`
  - 33 passed.
- `uv run ruff check src/trading/sub_account_registry.py tests/test_trading_sub_account_registry.py`
  - passed.
- `uv run black --check src/trading/sub_account_registry.py tests/test_trading_sub_account_registry.py`
  - passed.
- `uv run mypy src/trading/sub_account_registry.py`
  - passed.
- `uv run mypy src/trading/sub_account_registry.py tests/test_trading_sub_account_registry.py`
  - failed on existing test type issues around `_StubStrategy` and mocked
    exchange config access.

## Decisions

- Kept legacy root-field parsing for YAML compatibility. This slice only
  changes newly synthesized defaults so the runtime stops creating dual-source
  accounts itself.

## Risks

- CH-31 remains open for broader root-field deprecation and `RiskOverrides` /
  `RiskPolicy` reconciliation.

# Code Generation Plan: consistency-hardening - CH-31 Default sub-account policy fields

## Task

Start CH-31 dual-source field removal by materialising the synthesized default
sub-account with `capital_policy` and `strategy_policy` instead of root
`initial_balance` and `strategy_filter`.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-31 default policy materialization
- Primary owner unit: `sub-account-capital-segmentation`

## Related Requirements

- FR-036 Sub-account capital isolation
- FR-037 Sub-account strategy isolation

## Steps

- [x] Update `SubAccountRegistry._materialise_default()` to populate
      `CapitalPolicy.initial_balance`.
- [x] Update default materialization to populate `StrategyPolicy`.
- [x] Keep legacy YAML root-field parsing untouched for backward
      compatibility.
- [x] Update registry tests for the new synthesized default shape.

## Verification

- [x] `uv run pytest tests/test_trading_sub_account.py
      tests/test_trading_sub_account_registry.py
      tests/test_trading_experiment_marketplace.py -q`
- [x] `uv run ruff check src/trading/sub_account_registry.py
      tests/test_trading_sub_account_registry.py`
- [x] `uv run black --check src/trading/sub_account_registry.py
      tests/test_trading_sub_account_registry.py`
- [x] `uv run mypy src/trading/sub_account_registry.py`
- [ ] `uv run mypy src/trading/sub_account_registry.py
      tests/test_trading_sub_account_registry.py` - blocked by existing test
      type-stub issues in `_StubStrategy` and mocked exchange config access.

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Tests updated.
- [x] State/spec updated.
- [x] Session log and cross-check written.

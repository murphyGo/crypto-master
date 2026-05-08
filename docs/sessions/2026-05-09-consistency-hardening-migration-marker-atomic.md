# Session: consistency-hardening CH-32 Migration Marker Atomic Writes

## Unit

- `consistency-hardening`
- Primary owner unit: `persistence-data-integrity`

## Related Requirements

- NFR-006 Backtest / runtime artifact durability
- NFR-007 Trading history / proposal persistence

## Changes

- Changed sub-account migration completion markers to use
  `atomic_write_text()`.
- Covered both `.subaccounts_migrated_v19_1` and
  `.performance_migrated_v19_2`.
- Added a regression test that monkeypatches the helper and asserts both marker
  writes route through it.

## Tests

- `uv run pytest tests/test_trading_sub_account_migration.py tests/test_utils_atomic_write.py -q`
  - 22 passed.
- `uv run ruff check src/trading/sub_account_migration.py tests/test_trading_sub_account_migration.py`
  - passed.
- `uv run black --check src/trading/sub_account_migration.py tests/test_trading_sub_account_migration.py`
  - passed.
- `uv run mypy src/trading/sub_account_migration.py tests/test_trading_sub_account_migration.py`
  - passed.

## Decisions

- Limited this CH-32 slice to marker durability. Feedback promotion rollback and
  strategy loader frontmatter atomicity remain separate changes.

## Risks

- CH-32 remains open for the remaining atomic-write coverage items.

# Cross-Check: consistency-hardening CH-32 Migration Marker Atomic Writes

## Scope

Verify that migration completion markers no longer use direct `Path.write_text`.

## Requirements

- NFR-006 Backtest / runtime artifact durability
- NFR-007 Trading history / proposal persistence

## Evidence

- `migrate_legacy_paths()` writes both migration markers through
  `atomic_write_text()`.
- Regression test confirms both marker paths invoke the shared helper.
- Atomic write helper tests remain green.

## Verification

- `uv run pytest tests/test_trading_sub_account_migration.py tests/test_utils_atomic_write.py -q`
  - 22 passed.
- `uv run ruff check src/trading/sub_account_migration.py tests/test_trading_sub_account_migration.py`
  - passed.
- `uv run black --check src/trading/sub_account_migration.py tests/test_trading_sub_account_migration.py`
  - passed.
- `uv run mypy src/trading/sub_account_migration.py tests/test_trading_sub_account_migration.py`
  - passed.

## Result

PASS. Sub-account migration marker writes now use the shared atomic write helper.
CH-32 remains open for feedback promotion rollback and strategy loader coverage.

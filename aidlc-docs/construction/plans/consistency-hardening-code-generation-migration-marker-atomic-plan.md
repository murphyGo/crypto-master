# Code Generation Plan: consistency-hardening - CH-32 Migration marker atomic writes

## Task

Start CH-32 atomic write coverage by routing sub-account migration marker writes
through the shared atomic write helper.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-32 migration marker atomic writes
- Primary owner unit: `persistence-data-integrity`

## Related Requirements

- NFR-006 Backtest / runtime artifact durability
- NFR-007 Trading history / proposal persistence

## Steps

- [x] Route the v19.1 sub-account migration marker through
      `atomic_write_text()`.
- [x] Route the v19.2 performance migration marker through
      `atomic_write_text()`.
- [x] Add a regression test pinning marker writes to the shared helper.

## Verification

- [x] `uv run pytest tests/test_trading_sub_account_migration.py
      tests/test_utils_atomic_write.py -q`
- [x] `uv run ruff check src/trading/sub_account_migration.py
      tests/test_trading_sub_account_migration.py`
- [x] `uv run black --check src/trading/sub_account_migration.py
      tests/test_trading_sub_account_migration.py`
- [x] `uv run mypy src/trading/sub_account_migration.py
      tests/test_trading_sub_account_migration.py`

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Tests updated.
- [x] State/spec updated.
- [x] Session log and cross-check written.

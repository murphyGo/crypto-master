# Session: consistency-hardening CH-32 atomic promotion

Date: 2026-05-09

## Scope

- Completed CH-32 follow-up for feedback promotion atomicity.
- Wrapped `_promote_file()` source unlink after `atomic_write_text()` so an unlink failure removes the just-written active target and raises a clear partial-promotion error.
- Re-parsed rewritten YAML frontmatter before returning promoted markdown content.
- Confirmed the current strategy loader has no `.md` frontmatter rewrite path; loader coverage remains read/parse validation only.

## Verification

- `uv run pytest tests/test_trading_sub_account_migration.py tests/test_feedback_loop.py tests/test_strategy_loader.py -q`
- `uv run black --check src/feedback/loop.py src/strategy/loader.py tests/test_trading_sub_account_migration.py tests/test_feedback_loop.py tests/test_strategy_loader.py`
- `uv run ruff check src/feedback/loop.py src/strategy/loader.py tests/test_trading_sub_account_migration.py tests/test_feedback_loop.py tests/test_strategy_loader.py`
- `uv run mypy src/feedback/loop.py src/strategy/loader.py`

## Notes

- Added a regression test that simulates source `unlink()` failure and asserts the active target is rolled back, preventing double-promotion state.

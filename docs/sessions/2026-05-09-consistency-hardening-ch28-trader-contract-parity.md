# Session: consistency-hardening CH-28 trader contract parity

Date: 2026-05-09

## Scope

- Completed CH-28 follow-up for Paper/Live trader contract parity.
- Moved shared stop-loss / take-profit exit-reason semantics into `src/trading/base.py`.
- Routed both `PaperTrader.check_exit_conditions()` and `LiveTrader.check_exit_conditions()` through the shared helper.
- Added cleanup around live open-position in-memory state so a late post-persist failure cannot leave stale `_entry_fees` or tracked positions.

## Verification

- `uv run pytest tests/test_paper_trading.py tests/test_live_trading.py -q`
- `uv run black --check src/trading/base.py src/trading/paper.py src/trading/live.py tests/test_paper_trading.py tests/test_live_trading.py`
- `uv run ruff check src/trading/base.py src/trading/paper.py src/trading/live.py tests/test_paper_trading.py tests/test_live_trading.py`
- `uv run mypy src/trading/base.py src/trading/paper.py src/trading/live.py`

## Notes

- Added explicit paper/live boundary coverage for inclusive SL/TP checks and stop-loss priority.
- Added a live regression test for a failure after entry-fee stash registration.

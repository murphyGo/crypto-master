# Cross-Check: consistency-hardening CH-35 Trading Side Aliases

## Scope

Verify that shared trading side aliases are available without changing PnL
behavior.

## Requirements

- FR-006 Risk/reward calculation
- FR-008 Entry, stop-loss, and take-profit setting

## Evidence

- `src/utils/trading_types.py` exports `TradeSide` and `PositionSide`.
- `pnl_for_trade()` imports `TradeSide` from the shared utility module.
- Existing trading math tests remain green.

## Verification

- `uv run pytest tests/test_utils_trading_math.py -q`
  - 12 passed.
- `uv run ruff check src/utils/trading_types.py src/utils/trading_math.py tests/test_utils_trading_math.py`
  - passed.
- `uv run black --check src/utils/trading_types.py src/utils/trading_math.py tests/test_utils_trading_math.py`
  - passed.
- `uv run mypy src/utils/trading_types.py src/utils/trading_math.py tests/test_utils_trading_math.py`
  - passed.

## Result

PASS. Trading side vocabulary now has a shared utility source and PnL behavior
is unchanged.

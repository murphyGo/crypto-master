# Code Generation Plan: consistency-hardening - CH-35 Trading side aliases

## Task

Start CH-35 trading vocabulary unification by moving the shared
`"long"` / `"short"` side literal aliases into `src/utils/`.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-35 trading side aliases
- Primary owner unit: `trading-core`

## Related Requirements

- FR-006 Risk/reward calculation
- FR-008 Entry, stop-loss, and take-profit setting

## Steps

- [x] Add `src/utils/trading_types.py`.
- [x] Export `TradeSide` and `PositionSide`.
- [x] Route `src/utils/trading_math.py` through the shared alias.
- [x] Add a focused importability test.

## Verification

- [x] `uv run pytest tests/test_utils_trading_math.py -q`
- [x] `uv run ruff check src/utils/trading_types.py src/utils/trading_math.py
      tests/test_utils_trading_math.py`
- [x] `uv run black --check src/utils/trading_types.py src/utils/trading_math.py
      tests/test_utils_trading_math.py`
- [x] `uv run mypy src/utils/trading_types.py src/utils/trading_math.py
      tests/test_utils_trading_math.py`

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Tests updated.
- [x] State/spec updated.
- [x] Session log and cross-check written.

# Session: consistency-hardening CH-35 error envelope

Date: 2026-05-09

## Scope

- Completed CH-35 follow-up for trading vocabulary and runtime error envelopes.
- Added shared `OrderSide` / `SignalSide` alongside `TradeSide` / `PositionSide` and migrated core models plus paper/live/proposal/runtime/trading side annotations to shared aliases.
- Replaced `CycleResult.errors` string entries with structured `EngineError` records categorized by `ErrorCategory`.
- Updated runtime tests to assert homogeneous `EngineError` entries and category-specific failures.

## Verification

- `uv run pytest tests/test_models.py tests/test_runtime_engine.py -q`
- `uv run black --check src/models.py src/utils/trading_types.py src/trading/live.py src/trading/paper.py src/trading/strategy.py src/runtime/engine.py src/runtime/correlation_governor.py src/proposal/engine.py src/proposal/replay.py tests/test_models.py tests/test_runtime_engine.py`
- `uv run ruff check src/models.py src/utils/trading_types.py src/trading/live.py src/trading/paper.py src/trading/strategy.py src/runtime/engine.py src/runtime/correlation_governor.py src/proposal/engine.py src/proposal/replay.py tests/test_models.py tests/test_runtime_engine.py`
- `uv run mypy src/models.py src/utils/trading_types.py src/trading/live.py src/trading/paper.py src/trading/strategy.py src/runtime/engine.py src/runtime/correlation_governor.py src/proposal/engine.py src/proposal/replay.py`

## Notes

- Runtime result errors now preserve category, symbol, detail, and original exception without mixing raw strings into cycle summaries.

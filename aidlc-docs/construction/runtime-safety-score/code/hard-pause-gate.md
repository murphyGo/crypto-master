# Code Summary: Hard Pause Gate

## Slice

Added an opt-in runtime safety hard-pause gate before accepted proposals can
open positions.

## Behavior

- `EngineConfig.runtime_safety_pause_min_score` defaults to `None`, preserving
  existing runtime behavior.
- `Settings.engine_runtime_safety_pause_min_score` exposes the env-driven
  setting as `ENGINE_RUNTIME_SAFETY_PAUSE_MIN_SCORE`.
- When configured, accepted proposals are rejected before execution if the
  recent runtime safety score is below the configured minimum.
- The rejection is persisted to proposal history and recorded in the activity
  log with the safety score, safety band, and configured minimum.

## Verification

```bash
uv run pytest tests/test_runtime_engine.py tests/test_config.py tests/test_main_dispatch.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

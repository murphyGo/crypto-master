# CH-10 Post-Incident Safety Score

## Summary

The runtime hard-pause gate now uses a safety score recomputed after
same-proposal notification failures and advisory correlation warnings are
written to the activity log. Notification payloads still receive the
pre-notification safety score, preserving the existing notification contract.

## Verification

- `uv run pytest tests/test_runtime_engine.py -q`
  - 56 passed.
- `uv run black --check src/runtime/engine.py tests/test_runtime_engine.py`
  - passed.
- `uv run ruff check src/runtime/engine.py tests/test_runtime_engine.py`
  - passed.

## Remaining Type-Check Context

`uv run mypy src/runtime/engine.py` still reports existing nullable-type errors
in `src/proposal/engine.py` and runtime policy construction.

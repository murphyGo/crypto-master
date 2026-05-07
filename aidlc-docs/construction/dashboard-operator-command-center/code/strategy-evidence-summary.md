# Code Summary: Strategy Evidence Summary

## Slice

Added a Home command-center strategy-evidence summary.

## Behavior

- Home reads persisted feedback candidate records through the existing Feedback
  dashboard loader.
- Home displays total candidates, awaiting approval, promoted, and errored
  counts.
- The section is read-only and does not add promotion/rejection controls.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_feedback.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

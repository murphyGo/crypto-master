# Code Summary: Ops Runtime Diagnostics

## Slice

Added an operator runtime-diagnostics table to the Home command center.

## Behavior

- Home now derives diagnostic rows from existing command-center inputs:
  runtime safety, last-cycle status, snapshot freshness, and recent incidents.
- Diagnostics use simple `pass`, `watch`, and `stop` statuses with concrete
  detail and next-step labels.
- The table appears before exposure details so operators can scan runtime
  health before drilling into trading and strategy evidence.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

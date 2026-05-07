# Code Summary: Runtime Diagnostics Dashboard

## Slice

Added an Ops Diagnostics dashboard page.

## Behavior

- New `Ops Diagnostics` page is registered in the sidebar.
- The page checks whether the configured data directory exists.
- The page checks the newest runtime activity log file, including rotated
  `activity*.jsonl` files, and marks stale activity as `watch`.
- Operators can provide a health URL, such as a deployed Streamlit health
  endpoint, and the page reports HTTP status or request failure.
- The diagnostic output is read-only and does not invoke Fly or mutate runtime
  state.

## Verification

```bash
uv run pytest tests/test_dashboard_ops.py tests/test_dashboard_app.py tests/test_dashboard_engine.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_autopsy.py tests/test_dashboard_ops.py tests/test_dashboard_replay.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

# Code Summary: Incident Action Panel

## Slice

Added a Home command-center incident/action panel.

## Behavior

- `Actionable events` now uses the same recent 24-hour window as runtime safety
  scoring.
- Home now renders a `Recent Incidents` table for recent actionable runtime
  events.
- Incident rows include severity, event type, timestamp, sub-account, symbol,
  message, and a next-step hint.
- Empty recent incident windows render a positive empty state.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

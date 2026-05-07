# Code Summary: Open Exposure Summary

## Slice

Added a Home command-center open-exposure drilldown table.

## Behavior

- Persisted open trades are grouped by symbol and side.
- Each row preserves the source sub-account ids.
- The table shows open count, estimated notional, max leverage, and whether
  the same exposure spans multiple sub-accounts.
- Empty selected scopes render a clear no-open-exposure message.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

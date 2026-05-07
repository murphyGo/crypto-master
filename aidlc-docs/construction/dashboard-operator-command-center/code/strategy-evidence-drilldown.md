# Code Summary: Strategy Evidence Drilldown

## Slice

Added recent strategy-candidate evidence rows to the Home command center.

## Behavior

- Home now builds recent candidate rows from persisted Feedback Loop candidate
  records.
- The Strategy Evidence section renders a read-only table with candidate ID,
  technique, version, status, robustness result, backtest run, sub-account,
  update time, and next-step hint.
- Candidate rows are sorted newest first and capped to the command-center
  display limit.
- Approval and rejection actions remain owned by the Feedback Loop page.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_feedback.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

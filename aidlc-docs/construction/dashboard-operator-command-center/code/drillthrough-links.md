# Code Summary: Drillthrough Links

## Slice

Converted Home command-center next-step hints into page-level drill-through
links.

## Behavior

- Diagnostic, incident, and candidate rows now carry a target page, filter hint,
  and query params.
- Home renders `st.page_link` controls for actionable diagnostic rows, recent
  incidents, and strategy candidates.
- Engine honors `event_type` query params by defaulting the activity-timeline
  multiselect to the requested event type(s).
- Trading honors `mode`, `sub_account`, and `symbol` query params for default
  controls and table filtering.
- Feedback honors `candidate_id` and `status` query params when selecting the
  candidate detail record.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

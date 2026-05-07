# Code Generation Plan: dashboard-operator-command-center Drillthrough

## Unit

- **Unit**: `dashboard-operator-command-center`
- **Stage**: Code Generation
- **Task**: Convert Home next-step hints into page-level drill-through links
  with query-param context.
- **Related Requirements**: FR-029, FR-030, FR-031, FR-032, FR-036, FR-042,
  FR-044, NFR-003, NFR-007, NFR-008.
- **Related Stories**: US-012, US-017, US-020, US-022, US-023.
- **Related Debt**: none active.

## Implementation Steps

- [x] Add target page, filter hint, and query params to incident, candidate,
  and diagnostic Home read models.
- [x] Render Streamlit page links for actionable diagnostic, incident, and
  candidate rows.
- [x] Teach Engine, Trading, and Feedback pages to honor Home query-param
  context where practical.
- [x] Add targeted tests for row-level drill-through metadata and table
  columns.
- [x] Run targeted dashboard tests and formatting checks.
- [x] Write implementation notes/session log.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

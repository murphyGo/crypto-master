# Session: dashboard-operator-command-center Drillthrough

## Unit

- `dashboard-operator-command-center`

## Related Requirements

- FR-029, FR-030, FR-031, FR-032, FR-036, FR-042, FR-044
- NFR-003, NFR-007, NFR-008

## Files Changed

- `src/dashboard/app.py`
- `src/dashboard/pages/engine.py`
- `src/dashboard/pages/feedback.py`
- `src/dashboard/pages/trading.py`
- `tests/test_dashboard_app.py`
- `aidlc-docs/construction/plans/dashboard-operator-command-center-drillthrough-code-generation-plan.md`
- `aidlc-docs/construction/dashboard-operator-command-center/code/drillthrough-links.md`
- `docs/sessions/2026-05-07-dashboard-operator-command-center-drillthrough.md`

## Checks Run

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

## Decisions

- Used Streamlit `st.page_link` with query params rather than inventing a
  custom router.
- Kept query-param handling page-local and optional so direct page visits keep
  their existing defaults.
- Preserved read-only Home behavior; operational decisions still belong to the
  target pages and existing APIs.

## Risks

- Query params set default context only. They do not persist a shared global
  dashboard state after operators change page controls manually.

## Debt

- No new TECH-DEBT item added.

# Code Generation Plan: dashboard-operator-command-center Incident Action Panel

## Unit

- **Unit**: `dashboard-operator-command-center`
- **Stage**: Code Generation
- **Task**: Add a Home command-center incident/action panel for recent
  actionable runtime events.
- **Related Requirements**: FR-029, FR-031, FR-032, FR-036, FR-042, FR-044,
  NFR-003, NFR-007, NFR-008.
- **Related Stories**: US-012, US-020, US-022, US-023.
- **Related Debt**: none active.

## Implementation Steps

- [x] Align Home actionable-event count with the same recent 24-hour window as
  runtime safety scoring.
- [x] Add a recent incidents read model with severity, event type, timestamp,
  sub-account, symbol, message, and next-step hint.
- [x] Render a `Recent Incidents` Home table with a clear empty state.
- [x] Add targeted tests for recent-window filtering and incident field
  extraction.
- [x] Run targeted dashboard tests and formatting checks.
- [x] Write implementation notes/session log.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

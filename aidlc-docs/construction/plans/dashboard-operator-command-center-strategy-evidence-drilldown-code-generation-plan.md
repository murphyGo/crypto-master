# Code Generation Plan: dashboard-operator-command-center Strategy Evidence Drilldown

## Unit

- **Unit**: `dashboard-operator-command-center`
- **Stage**: Code Generation
- **Task**: Add a recent strategy-candidate evidence table to the Home command
  center.
- **Related Requirements**: FR-028, FR-030, FR-039, NFR-003.
- **Related Stories**: US-012, US-017, US-023.
- **Related Debt**: none active.

## Implementation Steps

- [x] Reuse persisted Feedback Loop candidate records already loaded for Home
  evidence metrics.
- [x] Add a recent-candidate read model with candidate ID, technique, version,
  status, robustness, backtest run, sub-account, update time, and next step.
- [x] Render the recent candidates below the Strategy Evidence metric cards.
- [x] Keep the Home drilldown read-only and route decisions to the Feedback
  Loop page.
- [x] Add targeted tests for candidate sorting, next-step mapping, and empty
  table columns.
- [x] Run targeted dashboard tests and formatting checks.
- [x] Write implementation notes/session log.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_feedback.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

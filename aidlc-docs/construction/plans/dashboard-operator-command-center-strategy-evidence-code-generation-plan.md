# Code Generation Plan: dashboard-operator-command-center Strategy Evidence

## Unit

- **Unit**: `dashboard-operator-command-center`
- **Stage**: Code Generation
- **Task**: Add a Home command-center strategy-evidence summary from persisted
  feedback candidates.
- **Related Requirements**: FR-028, FR-030, FR-039, NFR-003.
- **Related Stories**: US-012, US-017, US-023.
- **Related Debt**: none active.

## Implementation Steps

- [x] Extend the command-center read model with candidate total, awaiting
  approval, promoted, and errored counts.
- [x] Render a compact `Strategy Evidence` section on Home without adding
  promotion actions.
- [x] Add targeted tests for strategy evidence summary fields.
- [x] Run targeted dashboard tests and formatting checks.
- [x] Write implementation notes/session log.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_feedback.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

# Code Generation Plan: dashboard-operator-command-center Ops Runtime Diagnostics

## Unit

- **Unit**: `dashboard-operator-command-center`
- **Stage**: Code Generation
- **Task**: Add Home command-center runtime diagnostics from existing
  operator signals.
- **Related Requirements**: FR-029, FR-031, FR-032, FR-036, FR-042, FR-044,
  NFR-003, NFR-007, NFR-008.
- **Related Stories**: US-012, US-020, US-022, US-023.
- **Related Debt**: none active.

## Implementation Steps

- [x] Reuse runtime safety, last-cycle status, portfolio snapshot freshness,
  and recent incident rows as diagnostic inputs.
- [x] Add a Home runtime-diagnostic read model with check, status, detail, and
  next-step fields.
- [x] Render a `Runtime Diagnostics` table above exposure details.
- [x] Add targeted tests for stop/watch/pass mapping and empty-table columns.
- [x] Run targeted dashboard tests and formatting checks.
- [x] Write implementation notes/session log.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

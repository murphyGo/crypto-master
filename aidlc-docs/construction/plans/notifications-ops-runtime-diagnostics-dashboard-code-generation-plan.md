# Code Generation Plan: notifications-ops Runtime Diagnostics Dashboard

## Unit

- **Unit**: `notifications-ops`
- **Stage**: Code Generation
- **Task**: Add dashboard operations diagnostics for runtime data freshness and
  optional deployed health checks.
- **Related Requirements**: FR-032, NFR-003, NFR-007.
- **Related Stories**: US-020, US-022, US-023.
- **Related Debt**: none active.

## Implementation Steps

- [x] Add an Ops Diagnostics dashboard page.
- [x] Check configured data directory existence.
- [x] Check runtime activity-log freshness, including rotated activity files.
- [x] Support an optional health URL probe.
- [x] Add targeted tests for diagnostics rows, health checker injection, table
  schema, and dashboard registration.
- [x] Run dashboard tests and formatting checks.
- [x] Write implementation notes/session log.

## Verification

```bash
uv run pytest tests/test_dashboard_ops.py tests/test_dashboard_app.py tests/test_dashboard_engine.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_autopsy.py tests/test_dashboard_ops.py tests/test_dashboard_replay.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

# Code Generation Plan: dashboard-operator-command-center Account Context

## Unit

- **Unit**: `dashboard-operator-command-center`
- **Stage**: Code Generation
- **Task**: Add Home command-center account-context controls for mode and
  aggregate/sub-account scope.
- **Related Requirements**: FR-029, FR-031, FR-032, FR-036, NFR-003,
  NFR-007, NFR-008.
- **Related Stories**: US-012, US-020, US-023.
- **Related Debt**: none active.

## Implementation Steps

- [x] Extend the command-center read model with selected scope and discovered
  sub-account ids.
- [x] Add Home controls for `paper` / `live` and `Aggregate` / sub-account
  scope without changing the Trading page.
- [x] Add targeted tests for aggregate vs single sub-account loading semantics.
- [x] Run targeted dashboard tests and formatting checks.
- [x] Write implementation notes/session log.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

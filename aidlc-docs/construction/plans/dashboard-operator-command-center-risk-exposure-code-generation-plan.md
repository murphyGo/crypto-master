# Code Generation Plan: dashboard-operator-command-center Risk Exposure Detail

## Unit

- **Unit**: `dashboard-operator-command-center`
- **Stage**: Code Generation
- **Task**: Add margin and equity-relative risk context to Home command-center
  exposure rows.
- **Related Requirements**: FR-029, FR-031, FR-032, FR-036, FR-042, FR-044,
  NFR-003, NFR-007, NFR-008.
- **Related Stories**: US-012, US-020, US-022, US-023.
- **Related Debt**: none active.

## Implementation Steps

- [x] Read latest portfolio equity from persisted snapshots.
- [x] Carry latest equity through the Home command-center status read model.
- [x] Calculate estimated margin per symbol/side exposure row using recorded
  leverage.
- [x] Calculate notional exposure as a percentage of latest portfolio equity
  when equity is available.
- [x] Render the new exposure fields in the Home exposure table.
- [x] Add targeted tests for latest-equity selection and exposure math.
- [x] Run targeted dashboard tests and formatting checks.
- [x] Write implementation notes/session log.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

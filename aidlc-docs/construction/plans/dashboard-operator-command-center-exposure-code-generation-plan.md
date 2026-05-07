# Code Generation Plan: dashboard-operator-command-center Exposure Summary

## Unit

- **Unit**: `dashboard-operator-command-center`
- **Stage**: Code Generation
- **Task**: Add a Home command-center open-exposure drilldown table grouped by
  symbol and side.
- **Related Requirements**: FR-029, FR-031, FR-036, FR-044, NFR-003, NFR-007.
- **Related Stories**: US-012, US-020, US-022, US-023.
- **Related Debt**: none active.

## Implementation Steps

- [x] Add an exposure row read model that preserves sub-account source while
  loading persisted trades.
- [x] Render a compact `Open Exposure` table on Home with symbol, side,
  sub-accounts, count, notional, max leverage, and duplicate-account flag.
- [x] Add targeted helper tests for duplicate cross-account exposure.
- [x] Run targeted dashboard tests and formatting checks.
- [x] Write implementation notes/session log.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

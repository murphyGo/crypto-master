# Code Generation Plan: dashboard-operator-command-center

## Unit

- **Unit**: `dashboard-operator-command-center`
- **Stage**: Code Generation
- **Task**: Add the first Home command-center slice with safety, freshness, and
  open-exposure summaries.
- **Related Requirements**: FR-028, FR-029, FR-031, FR-032, FR-036, FR-042,
  FR-044, NFR-003, NFR-007, NFR-008.
- **Related Stories**: US-012, US-020, US-022, US-023.
- **Related Legacy Phases**: Phase 7, Phase 8.2, Phase 19.3, Phase 24,
  Phase 26.4.
- **Related Debt**: none active.

## Implementation Steps

- [x] Add pure command-center read-model helpers for empty/missing data,
  snapshot freshness, actionable runtime events, and open exposure.
- [x] Render the Home command-center status section without replacing existing
  dashboard pages.
- [x] Add targeted AppTest/DataFrame tests for empty state and synthetic
  activity/trading fixtures.
- [x] Run targeted dashboard tests and formatting checks.
- [x] Write implementation notes/session log and mark the first slice complete.

## Target Files

- `src/dashboard/app.py`
- `tests/test_dashboard_app.py`
- Optional if helper ownership becomes clearer:
  `src/dashboard/pages/trading.py`, `src/dashboard/pages/engine.py`,
  `tests/test_dashboard_trading.py`, `tests/test_dashboard_engine.py`
- `aidlc-docs/construction/dashboard-operator-command-center/code/`
- `docs/sessions/`

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_runtime_safety_score.py -q
uv run black src tests
uv run ruff check src tests
```

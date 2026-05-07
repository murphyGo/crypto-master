# Session: dashboard-operator-command-center Account Context

## Unit

- `dashboard-operator-command-center`

## Related Requirements

- FR-029, FR-031, FR-032, FR-036
- NFR-003, NFR-007, NFR-008

## Files Changed

- `src/dashboard/app.py`
- `tests/test_dashboard_app.py`
- `aidlc-docs/construction/plans/dashboard-operator-command-center-account-context-code-generation-plan.md`
- `aidlc-docs/construction/dashboard-operator-command-center/code/account-context-controls.md`
- `docs/sessions/2026-05-07-dashboard-operator-command-center-account-context.md`

## Checks Run

```bash
uv run pytest tests/test_dashboard_app.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
uv run black src tests
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

## Decisions

- Kept scope controls on Home so the operator sees account context before
  entering domain-specific dashboard pages.
- Reused existing sub-account discovery from the Trading page.
- Scope-specific reads use the selected sub-account only; Aggregate reads all
  discovered ids.

## Risks

- The first account-context control is local to Home. Shared page-level context
  can be added in a future slice.

## Debt

- No new TECH-DEBT item added.

# Session: dashboard-operator-command-center Home Summary

## Unit

- `dashboard-operator-command-center`

## Related Requirements

- FR-028, FR-029, FR-031, FR-032, FR-036, FR-042, FR-044
- NFR-003, NFR-007, NFR-008

## Files Changed

- `src/dashboard/app.py`
- `tests/test_dashboard_app.py`
- `aidlc-docs/construction/plans/dashboard-operator-command-center-code-generation-plan.md`
- `aidlc-docs/construction/dashboard-operator-command-center/code/home-command-center-summary.md`
- `docs/sessions/2026-05-07-dashboard-operator-command-center-home.md`

## Checks Run

```bash
uv run pytest tests/test_dashboard_app.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_runtime_safety_score.py -q
uv run black src tests
uv run ruff check src tests --fix
uv run black src tests --check
uv run ruff check src tests
```

## Decisions

- Kept the first UI slice on Home instead of adding a new page so the operator
  gets safety context before choosing a domain page.
- Reused persisted `ActivityLog`, `TradeHistoryTracker`, `PortfolioTracker`,
  and existing runtime safety scoring.
- Kept the command center read-only and avoided exchange calls during render.

## Risks

- Estimated open notional uses persisted entry price and quantity, not fresh
  market price.
- First slice defaults to paper aggregate scope; live/shared scope controls can
  be added in a later slice.

## Debt

- No new TECH-DEBT item added.

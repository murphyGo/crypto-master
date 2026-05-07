# Session: dashboard-operator-command-center Exposure Summary

## Unit

- `dashboard-operator-command-center`

## Related Requirements

- FR-029, FR-031, FR-036, FR-044
- NFR-003, NFR-007

## Files Changed

- `src/dashboard/app.py`
- `tests/test_dashboard_app.py`
- `aidlc-docs/construction/plans/dashboard-operator-command-center-exposure-code-generation-plan.md`
- `aidlc-docs/construction/dashboard-operator-command-center/code/open-exposure-summary.md`
- `docs/sessions/2026-05-07-dashboard-operator-command-center-exposure.md`

## Checks Run

```bash
uv run pytest tests/test_dashboard_app.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_runtime_safety_score.py -q
uv run ruff check src tests --fix
uv run black src tests
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

## Decisions

- Kept exposure grouping on persisted entry price and quantity to avoid live
  exchange calls during dashboard render.
- Added duplicate-account detection for same symbol/side exposure across
  sub-accounts.

## Risks

- Estimated notional is not mark-to-market. Current-price exposure requires a
  future explicit market-data design.

## Debt

- No new TECH-DEBT item added.

# Session: dashboard-operator-command-center Risk Exposure Detail

## Unit

- `dashboard-operator-command-center`

## Related Requirements

- FR-029, FR-031, FR-032, FR-036, FR-042, FR-044
- NFR-003, NFR-007, NFR-008

## Files Changed

- `src/dashboard/app.py`
- `tests/test_dashboard_app.py`
- `aidlc-docs/construction/plans/dashboard-operator-command-center-risk-exposure-code-generation-plan.md`
- `aidlc-docs/construction/dashboard-operator-command-center/code/risk-exposure-detail.md`
- `docs/sessions/2026-05-07-dashboard-operator-command-center-risk-exposure.md`

## Checks Run

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

## Decisions

- Used the newest persisted portfolio snapshot as the equity source for Home
  exposure percentages.
- Kept exposure percentages nullable when no positive equity is available
  instead of inventing a fallback denominator.
- Computed estimated margin directly from recorded entry notional and leverage
  to match the persisted trade model.

## Risks

- Equity-relative exposure uses the latest portfolio snapshot, which can lag
  live market movement if snapshot refresh stalls.

## Debt

- No new TECH-DEBT item added.

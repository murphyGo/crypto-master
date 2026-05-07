# Cross-Check: dashboard-operator-command-center Home Summary

## Scope

First command-center implementation slice for the Streamlit Home page.

## Requirements

| Requirement | Result | Evidence |
|-------------|--------|----------|
| FR-028 | PASS | Home preserves navigation to strategy status and existing Strategies page. |
| FR-029 | PASS | Home now summarizes open persisted paper positions. |
| FR-031 | PASS | Home now surfaces estimated open notional and latest snapshot freshness. |
| FR-032 / NFR-003 | PASS | Streamlit Home AppTest covers command-center render. |
| FR-036 | PASS | Home discovers persisted sub-account ids for paper mode and reports count. |
| FR-042 | PASS | Home reuses runtime safety score band, score, and factors. |
| FR-044 | PASS | Home counts correlation warnings as actionable runtime events. |
| NFR-007 / NFR-008 | PASS | Home reads persisted trade and portfolio snapshot state without mutation. |

## Files Checked

- `src/dashboard/app.py`
- `tests/test_dashboard_app.py`
- `aidlc-docs/construction/dashboard-operator-command-center/code/home-command-center-summary.md`
- `docs/sessions/2026-05-07-dashboard-operator-command-center-home.md`

## Verification

```bash
uv run pytest tests/test_dashboard_app.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

## Findings

- No blocking gaps found for the first Home command-center slice.
- The first slice intentionally estimates open notional from persisted entry
  price and quantity; it does not imply a fresh exchange mark price.
- The first slice defaults to paper aggregate scope. Future slices should add
  shared account-context controls and exposure drilldown.

## Result

PASS.

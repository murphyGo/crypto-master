# Session: dashboard-operator-command-center Strategy Evidence Drilldown

## Unit

- `dashboard-operator-command-center`

## Related Requirements

- FR-028, FR-030, FR-039
- NFR-003

## Files Changed

- `src/dashboard/app.py`
- `tests/test_dashboard_app.py`
- `aidlc-docs/construction/plans/dashboard-operator-command-center-strategy-evidence-drilldown-code-generation-plan.md`
- `aidlc-docs/construction/dashboard-operator-command-center/code/strategy-evidence-drilldown.md`
- `docs/sessions/2026-05-07-dashboard-operator-command-center-strategy-evidence-drilldown.md`

## Checks Run

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_feedback.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

## Decisions

- Reused Feedback Loop candidate records rather than adding another persistence
  path.
- Kept the Home table read-only; operator decisions still run through Feedback
  Loop controls.
- Used explicit next-step labels instead of links because the Streamlit
  navigation contract is still page-level.

## Risks

- The table shows the latest candidate snapshots only. Full audit timeline
  still requires opening the Feedback Loop page.

## Debt

- No new TECH-DEBT item added.

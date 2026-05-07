# Session: proposal-replay-simulator Dashboard Tooling

## Unit

- `proposal-replay-simulator`

## Related Requirements

- FR-032, FR-043
- NFR-003

## Files Changed

- `src/dashboard/app.py`
- `src/dashboard/pages/replay.py`
- `tests/test_dashboard_replay.py`
- `aidlc-docs/construction/plans/proposal-replay-simulator-dashboard-code-generation-plan.md`
- `aidlc-docs/construction/proposal-replay-simulator/code/dashboard-tooling.md`
- `docs/sessions/2026-05-07-proposal-replay-dashboard-tooling.md`

## Checks Run

```bash
uv run pytest tests/test_dashboard_replay.py tests/test_proposal_replay.py tests/test_tools_proposal_replay.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_replay.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

## Decisions

- Reused the file-based replay JSON contract rather than inventing a second
  dashboard-only input model.
- Kept the page read-only; it renders reports but does not fetch market data or
  mutate proposal history.
- Exposed threshold entry as comma-separated text so operators can compare a
  small scenario grid without needing repeated form controls.

## Risks

- Operators still need to prepare the deterministic replay input JSON outside
  the dashboard.

## Debt

- No new TECH-DEBT item added.

# Code Generation Plan: proposal-replay-simulator Dashboard Tooling

## Unit

- **Unit**: `proposal-replay-simulator`
- **Stage**: Code Generation
- **Task**: Add Streamlit dashboard tooling for replay report rendering.
- **Related Requirements**: FR-032, FR-043, NFR-003.
- **Related Stories**: US-012, US-023.
- **Related Debt**: none active.

## Implementation Steps

- [x] Add a Proposal Replay dashboard page that accepts a replay input JSON
  path.
- [x] Reuse the existing proposal replay CLI/input/scenario/report contract.
- [x] Add threshold and same-candle exit-assumption controls.
- [x] Render Markdown replay reports in-app and expose a Markdown download.
- [x] Add targeted tests for threshold parsing, report rendering, and dashboard
  navigation.
- [x] Run replay/dashboard tests and formatting checks.
- [x] Write implementation notes/session log.

## Verification

```bash
uv run pytest tests/test_dashboard_replay.py tests/test_proposal_replay.py tests/test_tools_proposal_replay.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_replay.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

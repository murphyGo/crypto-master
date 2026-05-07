# Code Summary: Dashboard Tooling

## Slice

Added Streamlit dashboard tooling for proposal replay reports.

## Behavior

- New `Proposal Replay` dashboard page is registered in the sidebar.
- Operators can enter a `ProposalReplayInput` JSON path, approval thresholds,
  and same-candle exit assumptions.
- The page reuses `load_replay_input`, `build_scenarios`,
  `compare_replay_scenarios`, and `render_replay_report`.
- Reports render as Markdown in the app and can be downloaded as
  `proposal-replay-report.md`.
- Query params can prefill input path, threshold, and exit-assumption context.

## Verification

```bash
uv run pytest tests/test_dashboard_replay.py tests/test_proposal_replay.py tests/test_tools_proposal_replay.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_replay.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

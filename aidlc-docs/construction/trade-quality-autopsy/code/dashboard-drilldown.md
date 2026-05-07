# Code Summary: Dashboard Drilldown

## Slice

Added a Streamlit Trade Autopsy page for closed-trade evidence review.

## Behavior

- New `Trade Autopsy` dashboard page is registered in the sidebar.
- Operators can review paper/live closed trades by aggregate or sub-account
  scope.
- Closed trades are converted through `TradeAutopsy.from_trade_history`; open
  or incomplete trades are ignored.
- The summary table exposes outcome, PnL, holding time, close reason,
  sub-account, and MFE/MAE columns.
- A selected-trade detail block shows outcome, close reason, and evidence.
- Query params can preselect mode, sub-account, and symbol context.

## Verification

```bash
uv run pytest tests/test_dashboard_autopsy.py tests/test_strategy_trade_autopsy.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_autopsy.py tests/test_dashboard_replay.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py tests/test_strategy_trade_autopsy.py -q
uv run black src tests --check
uv run ruff check src tests
```

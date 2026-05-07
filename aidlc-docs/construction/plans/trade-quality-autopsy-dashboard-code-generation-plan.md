# Code Generation Plan: trade-quality-autopsy Dashboard Drilldown

## Unit

- **Unit**: `trade-quality-autopsy`
- **Stage**: Code Generation
- **Task**: Add Streamlit dashboard drilldown for closed-trade autopsy evidence.
- **Related Requirements**: FR-032, FR-041, NFR-003, NFR-007.
- **Related Stories**: US-012, US-018, US-023.
- **Related Debt**: none active.

## Implementation Steps

- [x] Add a Trade Autopsy dashboard page for paper/live closed trades.
- [x] Reuse `TradeAutopsy.from_trade_history` for normalized evidence.
- [x] Support aggregate and per-sub-account scopes plus optional symbol query
  context.
- [x] Render summary and selected-trade detail evidence.
- [x] Add targeted tests for autopsy filtering, table schema, and dashboard
  registration.
- [x] Run autopsy/dashboard tests and formatting checks.
- [x] Write implementation notes/session log.

## Verification

```bash
uv run pytest tests/test_dashboard_autopsy.py tests/test_strategy_trade_autopsy.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_autopsy.py tests/test_dashboard_replay.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py tests/test_strategy_trade_autopsy.py -q
uv run black src tests --check
uv run ruff check src tests
```

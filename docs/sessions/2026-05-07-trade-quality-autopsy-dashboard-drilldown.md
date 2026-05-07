# Session: trade-quality-autopsy Dashboard Drilldown

## Unit

- `trade-quality-autopsy`

## Related Requirements

- FR-032, FR-041
- NFR-003, NFR-007

## Files Changed

- `src/dashboard/app.py`
- `src/dashboard/pages/autopsy.py`
- `tests/test_dashboard_autopsy.py`
- `aidlc-docs/construction/plans/trade-quality-autopsy-dashboard-code-generation-plan.md`
- `aidlc-docs/construction/trade-quality-autopsy/code/dashboard-drilldown.md`
- `docs/sessions/2026-05-07-trade-quality-autopsy-dashboard-drilldown.md`

## Checks Run

```bash
uv run pytest tests/test_dashboard_autopsy.py tests/test_strategy_trade_autopsy.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_autopsy.py tests/test_dashboard_replay.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py tests/test_strategy_trade_autopsy.py -q
uv run black src tests --check
uv run ruff check src tests
```

## Decisions

- Reused the existing `TradeAutopsy` model instead of adding dashboard-specific
  trade-quality calculations.
- Kept candle-window enrichment out of this slice because persisted trade
  history does not carry the required candle window.
- Ignored incomplete closed-trade evidence rather than showing partial rows.

## Risks

- MFE/MAE remain blank until a future slice supplies candle-window enrichment
  for runtime trades.

## Debt

- No new TECH-DEBT item added.

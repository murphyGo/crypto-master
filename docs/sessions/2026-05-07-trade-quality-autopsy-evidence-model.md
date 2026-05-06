# Session Log: 2026-05-07 - trade-quality-autopsy - Evidence Model

## Overview

- **Date**: 2026-05-07
- **Primary Unit**: `trade-quality-autopsy`
- **Stage**: Code Generation
- **Task**: Define the closed-trade autopsy evidence model.

## Work Summary

This cycle starts Trade Quality Autopsy with a normalized evidence model.
`TradeAutopsy` converts closed `TradeHistory` records and `BacktestTrade`
records into one diagnostic shape with holding time, PnL, fees, close reason,
mode, sub-account, and win/loss/breakeven outcome.

The follow-up step adds candle-window enrichment. `with_candle_window` computes
MFE, MAE, drawdown-before-exit, and appends evidence describing the candle
sample used.

The final code-generation step feeds autopsy summaries into
`StrategyImprover.suggest_improvement`. Existing calls remain compatible, while
callers with autopsies can pass them into the improvement prompt.

## Files Changed

- Created: `src/strategy/trade_autopsy.py`
- Created: `tests/test_strategy_trade_autopsy.py`
- Modified: `src/strategy/__init__.py`
- Modified: `aidlc-docs/construction/plans/trade-quality-autopsy-code-generation-plan.md`
- Modified: `aidlc-docs/construction/trade-quality-autopsy/code/implementation-summary.md`
- Created: `docs/cross-checks/2026-05-07-trade-quality-autopsy-evidence-model.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Normalize runtime and backtest trades into one model | Later MFE/MAE and improvement-context steps can consume one evidence shape. |
| Reject open runtime trades | Autopsy is a closed-trade diagnostic; open trades lack exit and realized PnL evidence. |
| Use type-check-only backtest import | Avoids circular imports through `src.strategy.__init__` and `src.backtest.engine`. |
| Store excursions as positive percentages | MFE/MAE are easier to compare across long and short trades when both are positive magnitudes. |
| Keep autopsies optional in the improver | Existing improvement flows should not need to collect autopsies before generating candidates. |

## Verification

- `uv run pytest tests/test_strategy_trade_autopsy.py -q`
- `uv run pytest tests/test_ai_improver.py tests/test_strategy_trade_autopsy.py -q`
- `uv run ruff check src/strategy/trade_autopsy.py src/strategy/__init__.py tests/test_strategy_trade_autopsy.py`
- `uv run ruff check src/ai/improver.py tests/test_ai_improver.py`
- `uv run black --check src/strategy/trade_autopsy.py src/strategy/__init__.py tests/test_strategy_trade_autopsy.py`
- `uv run black --check src/ai/improver.py tests/test_ai_improver.py`

## Follow-Up

- Add dashboard drill-downs for autopsy records.

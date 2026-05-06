# Cross-Check: Trade Quality Autopsy Evidence Model

## Scope

Verify that closed runtime and backtest trades can be normalized into a shared
autopsy evidence model.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Autopsy model exists | Complete | `TradeAutopsy` in `src/strategy/trade_autopsy.py`. |
| Runtime closed trades convert | Complete | Test converts a closed `TradeHistory` with paper mode and sub-account id. |
| Open runtime trades are rejected | Complete | Test asserts `TradeAutopsyError` for `status="open"`. |
| Backtest trades convert | Complete | Test converts `BacktestTrade` and computes normalized fees/PnL percentage. |
| Outcome bucket is explicit | Complete | Tests cover win and breakeven outcomes. |
| Candle-window MFE/MAE are computed | Complete | Tests cover long and short trades with side-aware favorable/adverse excursion. |
| Missing candle overlap is rejected | Complete | Test asserts `TradeAutopsyError` when no candle falls inside the trade window. |

## Implementation Evidence

- `src/strategy/trade_autopsy.py`
- `src/strategy/__init__.py`
- `tests/test_strategy_trade_autopsy.py`

## Test Evidence

- `uv run pytest tests/test_strategy_trade_autopsy.py -q`
- `uv run ruff check src/strategy/trade_autopsy.py src/strategy/__init__.py tests/test_strategy_trade_autopsy.py`
- `uv run black --check src/strategy/trade_autopsy.py src/strategy/__init__.py tests/test_strategy_trade_autopsy.py`

## Gaps and Risks

- Strategy improvement prompts do not consume autopsy summaries yet.

## Unit Mapping

- **Primary Unit**: `trade-quality-autopsy`
- **Related Units**: `strategy-framework`, `backtesting-validation`, `ai-feedback-loop`

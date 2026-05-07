# Market Strategy Expansion Implementation Summary

## Scope

Added four deterministic, OHLCV-only strategy candidates in the strategy
framework unit:

- `strategies/vcp_breakout.py`: Minervini-style VCP breakout with trend-template,
  contraction, pivot-breakout, and volume-expansion checks.
- `strategies/session_vwap_pullback.py`: intraday/session VWAP continuation
  after a pullback into VWAP and momentum reclaim.
- `strategies/vwap_mean_reversion.py`: rolling VWAP band mean reversion with a
  muted-slope regime guard.
- `strategies/weinstein_stage2_filter.py`: Weinstein-style Stage 2 breakout and
  Stage 4 breakdown regime candidate.

## Decisions

- Kept the first pass as file-based Python strategies so the existing loader,
  proposal, and backtest paths can discover them without core loader changes.
- Kept all candidates `experimental`; promotion remains gated by backtest,
  robustness, and operator approval.
- Deferred funding, basis, pairs, and tick/volume-profile strategies because
  they need data surfaces beyond the current single-symbol OHLCV strategy
  contract.

## Verification

```bash
uv run pytest tests/test_baseline_strategies.py tests/test_strategy_loader.py tests/test_strategy_integration.py -q
uv run ruff check strategies/vcp_breakout.py strategies/session_vwap_pullback.py strategies/vwap_mean_reversion.py strategies/weinstein_stage2_filter.py tests/test_baseline_strategies.py
uv run black strategies/vcp_breakout.py strategies/session_vwap_pullback.py strategies/vwap_mean_reversion.py strategies/weinstein_stage2_filter.py tests/test_baseline_strategies.py
```

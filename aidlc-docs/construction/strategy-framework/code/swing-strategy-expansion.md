# Swing Strategy Expansion Implementation Summary

## Scope

Added three deterministic, OHLCV-only strategy candidates in the strategy
framework unit:

- `strategies/momentum_pinball_orb.py`: daily Momentum Pinball precursor plus
  next-session opening-range breakout.
- `strategies/turtle_soup_reclaim.py`: failed 20-bar high/low breakout fade
  after a wick sweep and close back inside the range.
- `strategies/raschke_holy_grail.py`: ADX-confirmed trend pullback into EMA20
  followed by continuation through the prior candle.

## Decisions

- Kept all candidates file-based Python strategies so the existing loader and
  backtest paths can discover them without runtime contract changes.
- Kept all candidates `experimental`; promotion remains gated by backtest,
  robustness, and operator approval.
- Used fixed OHLCV-derived filters only. Funding, OI, news, and session-specific
  exchange microstructure inputs remain out of scope.

## Verification

```bash
uv run pytest tests/test_baseline_strategies.py tests/test_strategy_loader.py tests/test_strategy_integration.py -q
uv run ruff check strategies/momentum_pinball_orb.py strategies/turtle_soup_reclaim.py strategies/raschke_holy_grail.py tests/test_baseline_strategies.py
uv run black strategies/momentum_pinball_orb.py strategies/turtle_soup_reclaim.py strategies/raschke_holy_grail.py tests/test_baseline_strategies.py
```

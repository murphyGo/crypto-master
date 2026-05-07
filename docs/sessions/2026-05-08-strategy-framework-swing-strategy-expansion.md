# Strategy Framework Swing Strategy Expansion

## Unit

`strategy-framework`

## Related Requirements

FR-001, FR-002, FR-003, FR-004, FR-005, NFR-005, NFR-010

## Files Changed

- `strategies/momentum_pinball_orb.py`
- `strategies/turtle_soup_reclaim.py`
- `strategies/raschke_holy_grail.py`
- `tests/test_baseline_strategies.py`
- `aidlc-docs/construction/plans/strategy-framework-code-generation-swing-strategy-expansion-plan.md`
- `aidlc-docs/construction/strategy-framework/code/swing-strategy-expansion.md`
- `aidlc-docs/aidlc-state.md`
- `docs/sessions/2026-05-08-strategy-framework-swing-strategy-expansion.md`

## Summary

Added the next three researched strategy candidates after VCP/VWAP/Weinstein:
Momentum Pinball ORB, Turtle Soup Reclaim, and Raschke Holy Grail Pullback.

The strategies are deterministic and OHLCV-only so they remain compatible with
the existing strategy loader and backtest/proposal paths without adding external
data dependencies.

## Tests and Checks

- `uv run pytest tests/test_baseline_strategies.py tests/test_strategy_loader.py tests/test_strategy_integration.py -q` - 80 passed
- `uv run ruff check strategies/momentum_pinball_orb.py strategies/turtle_soup_reclaim.py strategies/raschke_holy_grail.py tests/test_baseline_strategies.py` - passed
- `uv run black strategies/momentum_pinball_orb.py strategies/turtle_soup_reclaim.py strategies/raschke_holy_grail.py tests/test_baseline_strategies.py` - passed

## Decisions

- Momentum Pinball groups completed daily closes before the latest session, then
  uses the current session's opening range for execution.
- Turtle Soup requires stale prior range extremes and volume expansion to avoid
  fading every marginal high/low touch.
- Holy Grail uses ADX plus DI direction and EMA20 pullback/reclaim rules instead
  of discretionary trend labels.

## Risks

- Session anchoring for Momentum Pinball is UTC-date based in the supplied OHLCV
  timestamps. Backtest sensitivity should compare 15m and 1h cadences before
  promotion.
- Turtle Soup is explicitly counter-trend after sweeps; strong trend regimes may
  need additional ADX or higher-timeframe filters if backtests show repeated
  stop-outs.

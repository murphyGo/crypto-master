# Strategy Framework Market Strategy Expansion

## Unit

`strategy-framework`

## Related Requirements

FR-001, FR-002, FR-003, FR-004, FR-005, NFR-005, NFR-010

## Files Changed

- `strategies/vcp_breakout.py`
- `strategies/session_vwap_pullback.py`
- `strategies/vwap_mean_reversion.py`
- `strategies/weinstein_stage2_filter.py`
- `tests/test_baseline_strategies.py`
- `aidlc-docs/construction/plans/strategy-framework-code-generation-market-strategy-expansion-plan.md`
- `aidlc-docs/construction/strategy-framework/code/market-strategy-expansion.md`
- `aidlc-docs/aidlc-state.md`
- `docs/sessions/2026-05-08-strategy-framework-market-strategy-expansion.md`

## Summary

Added four deterministic experimental strategy candidates in the requested
sequence: VCP Breakout, Session VWAP Pullback, VWAP Mean Reversion, and
Weinstein Stage 2/Stage 4 regime strategy.

The strategies are intentionally OHLCV-only and file-based so they can be
discovered through the existing Python strategy loader without changing runtime
data contracts or live-trading behavior.

## Tests and Checks

- `uv run pytest tests/test_baseline_strategies.py tests/test_strategy_loader.py tests/test_strategy_integration.py -q` - 77 passed
- `uv run ruff check strategies/vcp_breakout.py strategies/session_vwap_pullback.py strategies/vwap_mean_reversion.py strategies/weinstein_stage2_filter.py tests/test_baseline_strategies.py` - passed
- `uv run black strategies/vcp_breakout.py strategies/session_vwap_pullback.py strategies/vwap_mean_reversion.py strategies/weinstein_stage2_filter.py tests/test_baseline_strategies.py` - passed

## Decisions

- VCP contraction is evaluated before the breakout bar so breakout expansion
  does not invalidate the setup.
- VWAP strategies use the supplied OHLCV only; exact market/volume profile and
  derivative-data strategies are deferred until the data layer supports them.
- Weinstein is represented as an experimental strategy candidate, not a global
  runtime gate, to avoid changing existing strategy behavior.

## Risks

- These are candidate strategies, not promoted live strategies. They still need
  backtest, out-of-sample, walk-forward, and robustness gate evidence before any
  promotion.
- Session VWAP behavior depends on timestamp/session boundaries; sensitivity
  checks should compare 15m and 1h cadences before operator adoption.

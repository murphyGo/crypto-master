# Code Generation Plan: trade-quality-autopsy

## Migration Status

New product-intelligence unit for post-trade diagnostics.

## Planned Code Generation Steps

- [x] Register the trade quality autopsy unit and construction plan.
- [x] Define closed-trade autopsy metrics and evidence model.
- [ ] Compute MFE/MAE and drawdown-before-exit from candle windows.
- [ ] Feed autopsy summaries into strategy improvement context.

## Evidence

- Requirements: FR-005, FR-021, FR-041.
- Primary paths: `src/strategy/performance.py`, `src/backtest/`, `src/trading/`.

## Future Work

Add dashboard drill-downs after the metric contract is pinned.

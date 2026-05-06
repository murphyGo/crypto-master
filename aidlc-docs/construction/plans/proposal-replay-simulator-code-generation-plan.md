# Code Generation Plan: proposal-replay-simulator

## Migration Status

New product-intelligence unit for replaying historical proposal decisions.

## Planned Code Generation Steps

- [x] Register the proposal replay simulator unit and construction plan.
- [x] Define replay input model over proposal history and candle windows.
- [x] Compare alternate approval thresholds and exit assumptions.
- [ ] Emit replay reports for operator threshold tuning.

## Evidence

- Requirements: FR-013, FR-014, FR-025, FR-043.
- Primary paths: `src/proposal/`, `src/backtest/`, `scripts/`.

## Future Work

Add CLI entrypoint once replay semantics are test-pinned.

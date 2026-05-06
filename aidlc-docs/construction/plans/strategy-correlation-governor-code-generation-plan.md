# Code Generation Plan: strategy-correlation-governor

## Migration Status

New product-intelligence unit for correlation-aware exposure control.

## Planned Code Generation Steps

- [x] Register the strategy correlation governor unit and construction plan.
- [x] Define strategy and asset correlation inputs from backtest and runtime data.
- [ ] Compute duplicate-exposure warnings across sub-accounts.
- [ ] Add optional runtime rejection gate for excessive correlated exposure.

## Evidence

- Requirements: FR-036, FR-038, FR-044.
- Primary paths: `src/backtest/`, `src/runtime/`, `src/trading/`.

## Future Work

Start advisory-only before making correlation checks execution-blocking.

# Session: consistency-hardening CH-08 Account-Scoped Exchange Routing

## Unit

- `consistency-hardening`
- Primary owner units: `sub-account-capital-segmentation`, `trading-core`

## Related Requirements

- FR-009 Live Trading Mode
- FR-036 Isolate capital, positions, history, and equity by sub-account
- FR-037 Bind live sub-accounts to explicit credential sets
- NFR-011 Protect exchange API keys from source code
- NFR-012 Require explicit live trading confirmation

## Changes

- Removed the runtime hard rejection for active non-default `exchange_ref`
  values.
- Added account-scoped exchange resolution from the active trader.
- Routed proposal scan, stale-quote checks, monitor ticker fetches, and
  portfolio mark prices through the account exchange when present.
- Restored the proposal engine's default exchange after each account scan.
- Built paper sub-account traders with named-credential exchanges when
  configured.
- Added regression coverage for non-default exchange refs and named paper
  exchange binding.

## Tests

- `uv run pytest tests/test_runtime_engine.py tests/test_trading_sub_account_registry.py -q`
  - 70 passed.
- `uv run black --check src/runtime/engine.py src/trading/sub_account_registry.py tests/test_runtime_engine.py tests/test_trading_sub_account_registry.py`
  - passed.
- `uv run ruff check src/runtime/engine.py src/trading/sub_account_registry.py tests/test_runtime_engine.py tests/test_trading_sub_account_registry.py`
  - passed.

## Type Check

- `uv run mypy src/runtime/engine.py src/trading/sub_account_registry.py`
  - failed on existing nullable-type errors in `src/proposal/engine.py`,
    `src/backtest/harness.py`, and runtime policy construction.

## Decisions

- Reuse the exchange already attached to `PaperTrader` / `LiveTrader` instead
  of introducing a separate router registry in this slice.
- Swap `ProposalEngine.exchange` only during a sub-account scan and restore it
  immediately afterward to keep the existing proposal engine API stable.

## Risks

- Multi-exchange connection lifecycle still depends on
  `SubAccountRegistry.connect_owned_exchanges()` for registry-created exchange
  instances.

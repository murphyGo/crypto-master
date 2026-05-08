# CH-08 Account-Scoped Exchange Routing

## Summary

The runtime no longer rejects active non-default `exchange_ref` values at
startup. For each active sub-account cycle, `TradingEngine` resolves an
account-scoped exchange from the selected trader when one is present and uses
that exchange for:

- proposal scan market data,
- stale-quote execution gates,
- monitor ticker fetches,
- portfolio mark prices.

The proposal engine's `exchange` is swapped only for the duration of the
sub-account scan and then restored, preserving legacy default behavior for
single-account deployments and tests.

`SubAccountRegistry` also builds paper traders with a named-credential exchange
when a paper sub-account declares a non-default `exchange_ref` that resolves to
configured credentials.

## Verification

- `uv run pytest tests/test_runtime_engine.py tests/test_trading_sub_account_registry.py -q`
  - 70 passed.
- `uv run black --check src/runtime/engine.py src/trading/sub_account_registry.py tests/test_runtime_engine.py tests/test_trading_sub_account_registry.py`
  - passed.
- `uv run ruff check src/runtime/engine.py src/trading/sub_account_registry.py tests/test_runtime_engine.py tests/test_trading_sub_account_registry.py`
  - passed.

## Remaining Type-Check Context

`uv run mypy src/runtime/engine.py src/trading/sub_account_registry.py` still
reports existing unrelated nullable-type errors in `src/proposal/engine.py`,
`src/backtest/harness.py`, and existing runtime policy construction paths.

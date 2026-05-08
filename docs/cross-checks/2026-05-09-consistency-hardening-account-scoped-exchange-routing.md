# Cross-Check: consistency-hardening CH-08 Account-Scoped Exchange Routing

## Scope

Verify that sub-accounts with non-default exchange refs are no longer blocked
at runtime and that market-data reads use the account-scoped exchange when a
trader exposes one.

## Requirements

- FR-009 Live Trading Mode
- FR-036 Isolate capital, positions, history, and equity by sub-account
- FR-037 Bind live sub-accounts to explicit credential sets
- NFR-011 Protect exchange API keys from source code
- NFR-012 Require explicit live trading confirmation

## Evidence

- `TradingEngine` resolves an exchange from each active trader and uses it for
  scan, stale-quote, monitor, and snapshot ticker reads.
- The previous startup rejection for active non-default `exchange_ref` values
  was removed.
- `ProposalEngine.exchange` is restored after account-scoped scan execution.
- `SubAccountRegistry` binds named-credential paper sub-accounts to their
  configured exchange.

## Verification

- `uv run pytest tests/test_runtime_engine.py tests/test_trading_sub_account_registry.py -q`
  - 70 passed.
- `uv run black --check src/runtime/engine.py src/trading/sub_account_registry.py tests/test_runtime_engine.py tests/test_trading_sub_account_registry.py`
  - passed.
- `uv run ruff check src/runtime/engine.py src/trading/sub_account_registry.py tests/test_runtime_engine.py tests/test_trading_sub_account_registry.py`
  - passed.

## Result

PASS. CH-08 removes the runtime block and routes account-specific market data
through the active trader's exchange while preserving default single-account
behavior.

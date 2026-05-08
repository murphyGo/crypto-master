# Code Generation Plan: consistency-hardening - CH-08 Account-scoped exchange routing

## Task

Remove the runtime hard block on active non-default `exchange_ref` values by
routing account-scoped market-data reads through the exchange attached to each
sub-account trader. Preserve legacy default behavior when a trader has no
account-specific exchange.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-08
- Primary owner units: `sub-account-capital-segmentation`, `trading-core`
- Related debt: `DEBT-054`

## Related Requirements

- FR-009 Live Trading Mode
- FR-036 Isolate capital, positions, history, and equity by sub-account
- FR-037 Bind live sub-accounts to explicit credential sets
- NFR-011 Protect exchange API keys from source code
- NFR-012 Require explicit live trading confirmation

## Steps

- [x] Remove the runtime startup rejection for active non-default
      `exchange_ref` values.
- [x] Resolve an account-scoped exchange from the active trader when present.
- [x] Use the account exchange for proposal scan, stale-quote checks,
      monitor ticker fetches, and portfolio mark prices.
- [x] Build named-credential paper traders with their account exchange when
      available.
- [x] Tests: non-default exchange refs are accepted and ticker reads route to
      the account exchange.
- [x] Targeted pytest: `uv run pytest tests/test_runtime_engine.py
      tests/test_trading_sub_account_registry.py -q`.

## Verification

- [x] Targeted tests pass.
- [x] Formatting/lint run for changed source/test files where practical.

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Tests added.
- [x] Plan steps closed.
- [x] State/spec/debt updated.
- [x] Session log and cross-check written.

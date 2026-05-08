# Refactor / Consistency Review Follow-ups

## Scope

Implemented follow-ups from the 5-subagent refactoring and code-consistency
review. The work was split into small runtime, generated-strategy, sub-account,
persistence, and replay units.

## Changes

- Fixed multi-account monitoring to evaluate SL/TP exits against the
  per-sub-account trader passed into `_monitor`.
- Added monitor visibility for persisted open trades whose in-memory position
  state is missing after restart.
- Added generated Python strategy AST validation before save/load, rejecting
  banned I/O/process imports, banned dynamic execution calls, and unsafe
  top-level statements.
- Enforced falsifiable hypothesis metadata for generated techniques.
- Added runtime Output Contract enforcement for generated prompt techniques,
  including the user-idea path.
- Threaded sub-account leverage caps into runtime proposal sizing.
- Passed shared exchange, activity log, and liquidation auto-deposit policy into
  YAML-created paper sub-account traders.
- Allowed `build_exchange` to use named credentials when legacy live keys are
  absent.
- Blocked active non-default sub-account `exchange_ref` values at runtime until
  an account-scoped exchange router exists.
- Saved closed-trade performance records under the trade's sub-account path.
- Kept migration markers unwritten when legacy/new-layout conflicts remain.
- Ignored proposal-candle high/low extremes in proposal replay exits.
- Added regression coverage for strategy filters and committed paper-lab config.
- Tightened live mode credential validation so named testnet credentials cannot
  satisfy `TRADING_MODE=live` or be selected for mainnet exchange construction.
- Required live market orders to return fully filled quantities before open or
  close trade history is mutated.
- Wired `ENGINE_MAX_TICKER_AGE_SECONDS` through `Settings` into
  `EngineConfig`.
- Treated `symbols: []` as the universal strategy metadata contract in factory
  symbol filtering.

## Follow-up Debt

- `DEBT-053`: Persisted open-position hydration after runtime restart.
- `DEBT-054`: Account-scoped exchange router for sub-account runtime.

## 2026-05-08 Verification Addendum

- `uv run pytest tests/test_live_trading.py tests/test_main_dispatch.py tests/test_config.py tests/test_strategy_factory.py -q`
- `uv run black src/config.py src/main.py src/trading/live.py src/strategy/factory.py tests/test_config.py tests/test_main_dispatch.py tests/test_live_trading.py tests/test_strategy_factory.py --check`

# Cross-Check: Live Safety, Runtime Config, and Strategy Factory Contracts

## Scope

Verify follow-ups from the refactor/code-consistency review for live credential
safety, live market-order fill handling, runtime ticker-age configuration, and
strategy symbol filtering.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Live mode must require live credentials | Complete | `Settings.validate_for_live_trading` now requires legacy live keys or named credentials with `testnet=False`. |
| Live named credentials must not select testnet refs for mainnet execution | Complete | `build_exchange` filters named credentials to live refs before constructing a mainnet exchange. |
| Live orders must not persist zero, open, or partial fills as usable positions | Complete | `LiveTrader._submit_order` rejects non-`FILLED`, zero-fill, and partial-fill market orders before open/close trade history mutation. |
| Stale quote max age must be operator configurable | Complete | `ENGINE_MAX_TICKER_AGE_SECONDS` maps through `Settings` to `EngineConfig.max_ticker_age_seconds`. |
| Empty strategy `symbols` metadata means universal | Complete | `get_strategies_by_symbol` treats `symbols: []` the same as a universal strategy contract. |

## Implementation Evidence

- `src/config.py`
- `src/main.py`
- `src/trading/live.py`
- `src/strategy/factory.py`
- `tests/test_config.py`
- `tests/test_main_dispatch.py`
- `tests/test_live_trading.py`
- `tests/test_strategy_factory.py`

## Test Evidence

- `uv run pytest tests/test_live_trading.py tests/test_main_dispatch.py tests/test_config.py tests/test_strategy_factory.py -q`
- `uv run black src/config.py src/main.py src/trading/live.py src/strategy/factory.py tests/test_config.py tests/test_main_dispatch.py tests/test_live_trading.py tests/test_strategy_factory.py --check`

## Gaps and Risks

- Live PnL still uses caller-provided prices instead of exchange average fill
  prices and fees. That remains a separate live correctness follow-up.
- Partial live fills are rejected conservatively. Supporting partial-fill
  reconciliation would require explicit position sizing and close-order
  accounting design.

## Unit Mapping

- **Primary Units**: `exchange-integration`, `trading-core`,
  `strategy-framework`
- **Related Units**: `proposal-runtime`, `persistence-data-integrity`,
  `quality-governance`

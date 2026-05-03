# Code Generation Plan: exchange-integration

## Migration Status

Legacy Phase work is migrated as brownfield-complete. This plan is not a queue
of unfinished historical tasks.

## Source Legacy Components

| Component | Phase | Secondary Unit |
|-----------|-------|----------------|
| Configuration Management | 1 | `notifications-ops` |
| Exchange Abstraction | 2 | |
| Binance Integration | 2 | |
| Bybit Integration | 2 | |
| Exchange Testnet Support | 4 | `trading-core` |
| Live Trading | 4 | `trading-core` |
| Live Trading Wiring | 10 | `trading-core` |
| OHLCV Cache for Multi-Technique Scan | 11 | `proposal-runtime` |
| BaseExchange.get_ohlcv `since` Parameter | 13 | `backtesting-validation` |
| Multi-Credential Live Mode | 19 | `sub-account-capital-segmentation` |
| UTC-Aware Timestamp Helper + Adapter Migration | 21 | `persistence-data-integrity` |

## Completed Code Generation Steps

- [x] Implement exchange abstraction and shared market/order models.
- [x] Implement Binance and Bybit adapters with OHLCV, ticker, balance, and order interfaces.
- [x] Add testnet-aware exchange configuration and tests.
- [x] Wire exchange behavior into live trading and runtime paths.
- [x] Add OHLCV cache and `since` parameter support for scan/backtest flows.
- [x] Preserve multi-credential live-mode and timestamp adapter behavior.

## Evidence

- Requirements: FR-016, FR-017, FR-018, FR-019, FR-020, NFR-009, NFR-011.
- Primary paths: `src/exchange/`, `src/config.py`, `tests/test_exchange_*`.
- Cross-checks: `docs/cross-checks/phase2-exchange-integration.md`, phase 10, phase 13, phase 19 reports.
- Session logs: related Phase 2, 4, 10, 11, 13, 19, and 21 entries under `docs/sessions/`.

## Future Work

Add new unchecked steps here only for future exchange integration changes.

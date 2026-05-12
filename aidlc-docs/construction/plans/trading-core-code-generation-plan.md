# Code Generation Plan: trading-core

## Migration Status

Legacy Phase work is migrated as brownfield-complete. This plan is not a queue
of unfinished historical tasks.

## Source Legacy Components

| Component | Phase | Secondary Unit |
|-----------|-------|----------------|
| Trading Strategy | 4 | |
| Exchange Testnet Support | 4 | `exchange-integration` |
| Paper Trading (Local) | 4 | |
| Paper Trading (Testnet) | 4 | `exchange-integration` |
| Paper Trading (Fees) | 4 | |
| Live Trading | 4 | `exchange-integration` |
| Portfolio / Asset Management | 4 | |
| Trading Strategy Profiles | 4 | |
| Trading Engine Runtime | 8 | `proposal-runtime` |
| Live Trading Wiring | 10 | `exchange-integration` |
| EngineConfig Env Override | 10 | `notifications-ops` |
| Cross-Cycle Position Cap | 12 | `proposal-runtime` |
| EngineConfig Remaining-Fields Env Override | 13 | `notifications-ops` |
| Portfolio Snapshot Recording in Runtime Cycle | 17 | `proposal-runtime` |
| Closed-Trade Performance Records | 17 | `strategy-framework` |
| Stale-Quote Sanity Gate at Proposal Fill | 18 | `proposal-runtime` |
| Sub-Account Foundation | 19 | `sub-account-capital-segmentation` |
| PnL Convention Single Source | 20 | `backtesting-validation` |
| Backtest / Portfolio Leverage Math Alignment | 20 | `backtesting-validation` |
| Paper Trader Liquidation Visibility | 22 | |
| Backtester Liquidation Parity | 26 | `backtesting-validation` |

## Completed Code Generation Steps

- [x] Implement trading calculations, entry/TP/SL logic, leverage, and position sizing.
- [x] Implement local/testnet paper trading, live trading, fees, profiles, and portfolio tracking.
- [x] Wire trading engine runtime, environment overrides, and position cap behavior.
- [x] Add portfolio snapshots, closed-trade performance records, and stale-quote safety interactions.
- [x] Align leverage/PnL math across backtest, portfolio, and liquidation visibility paths.
- [x] Resolve paper persistence follow-ups DEBT-059, DEBT-058, and DEBT-057: restart-safe paper balance snapshots, legacy SL/TP backfill tooling confirmation, and entry-fee persistence.

## Evidence

- Requirements: FR-006, FR-007, FR-008, FR-009, FR-010, FR-036, FR-037, NFR-007, NFR-008, NFR-012.
- Primary paths: `src/trading/`, `src/utils/trading_math.py`, `trading_profiles/`, `tests/test_trading_*`, `tests/test_portfolio.py`.
- Cross-checks: phase 4, phase 8, phase 10, phase 12, phase 17, phase 18, phase 19, phase 20, phase 22, and phase 26 reports.
- Session logs: related Phase 4, 8, 10, 12, 13, 17, 18, 19, 20, 22, and 26 entries under `docs/sessions/`.
- Follow-up evidence: `docs/sessions/2026-05-12-trading-core-paper-persistence-followups.md`, `docs/cross-checks/2026-05-12-trading-core-paper-persistence.md`.

## Future Work

Add future trading, risk, profile, portfolio, or PnL behavior changes as new
unchecked steps here.

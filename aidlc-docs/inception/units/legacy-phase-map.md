# Legacy Phase to Unit Map

## Purpose

`docs/legacy/development-plan.md` is the archived chronological history of the
project. `unit-of-work.md` is the unit-oriented AI-DLC view. This map connects
the two so future work can preserve audit history while planning by bounded
functional area.

## Mapping Rules

- A legacy component can map to more than one unit when it changed shared
  behavior.
- The first listed unit is the primary owner for future changes.
- Historical phase numbers are not renumbered here.
- Deferred/operator-only items remain mapped to their owning unit, even when
  implementation is not fully autonomous.

## Current Status Table Crosswalk

| Legacy Component | Phase | Primary Unit | Secondary Unit |
|------------------|-------|--------------|----------------|
| Project Setup | 1 | `quality-governance` | `persistence-data-integrity` |
| Configuration Management | 1 | `notifications-ops` | `exchange-integration` |
| Exchange Abstraction | 2 | `exchange-integration` | |
| Binance Integration | 2 | `exchange-integration` | |
| Bybit Integration | 2 | `exchange-integration` | |
| Analysis Technique Framework | 3 | `strategy-framework` | |
| Claude Integration | 3 | `ai-feedback-loop` | |
| Trading Strategy | 4 | `trading-core` | |
| Exchange Testnet Support | 4 | `exchange-integration` | `trading-core` |
| Paper Trading (Local) | 4 | `trading-core` | |
| Paper Trading (Testnet) | 4 | `trading-core` | `exchange-integration` |
| Paper Trading (Fees) | 4 | `trading-core` | |
| Live Trading | 4 | `trading-core` | `exchange-integration` |
| Portfolio / Asset Management | 4 | `trading-core` | |
| Trading Strategy Profiles | 4 | `trading-core` | |
| Backtesting | 5 | `backtesting-validation` | |
| Performance Analyzer | 5 | `backtesting-validation` | `strategy-framework` |
| Strategy Improver (Hypothesis-Driven) | 5 | `ai-feedback-loop` | `strategy-framework` |
| Robustness Validation Gate | 5 | `backtesting-validation` | `strategy-framework` |
| Feedback Loop | 5 | `ai-feedback-loop` | `backtesting-validation` |
| Trading Proposal | 6 | `proposal-runtime` | |
| UI Dashboard | 7 | `dashboard-operator-ui` | |
| Trading Engine Runtime | 8 | `proposal-runtime` | `trading-core` |
| Engine Status Dashboard Page | 8 | `dashboard-operator-ui` | `proposal-runtime` |
| Fly.io Deployment | 8 | `notifications-ops` | |
| Multi-Timeframe Strategy Support | 9 | `strategy-framework` | `backtesting-validation` |
| Baseline Indicator Strategies | 9 | `strategy-framework` | |
| Multi-Timeframe Backtester | 9 | `backtesting-validation` | `strategy-framework` |
| Per-Timeframe RSI Baselines | 9 | `strategy-framework` | |
| Live Trading Wiring | 10 | `trading-core` | `exchange-integration` |
| EngineConfig Env Override | 10 | `notifications-ops` | `trading-core` |
| Baseline Reference Numbers | 10 | `backtesting-validation` | |
| Log Retention Policy | 10 | `notifications-ops` | `persistence-data-integrity` |
| Volume-Aware Default Paths | 10 | `persistence-data-integrity` | `backtesting-validation` |
| Multi-Technique Per-Symbol Scan | 10 | `proposal-runtime` | `strategy-framework` |
| Pre-Existing Lint/Type Sweep | 11 | `quality-governance` | |
| OHLCV Cache for Multi-Technique Scan | 11 | `proposal-runtime` | `exchange-integration` |
| Notification Push Backend | 11 | `notifications-ops` | `proposal-runtime` |
| ProposalHistory.purge_old Wiring | 11 | `proposal-runtime` | `persistence-data-integrity` |
| Cross-Cycle Position Cap | 12 | `proposal-runtime` | `trading-core` |
| Residual mypy Sweep | 12 | `quality-governance` | |
| LLM Strategy Timeout Handling | 12 | `ai-feedback-loop` | |
| Telegram Notification Backend | 12 | `notifications-ops` | |
| Cleanup Batch (DEBT-009/010/011) | 13 | `quality-governance` | |
| EngineConfig Remaining-Fields Env Override | 13 | `notifications-ops` | `trading-core` |
| BaseExchange.get_ohlcv `since` Parameter | 13 | `exchange-integration` | `backtesting-validation` |
| Email Notification Backend | 13 | `notifications-ops` | |
| Chasulang Timeout Mitigation | 14 | `ai-feedback-loop` | `strategy-framework` |
| SMTP_SSL Alternative | 14 | `notifications-ops` | |
| Diagnostic Clarity | 15 | `proposal-runtime` | `notifications-ops` |
| chasulang Parse + Wedge Mitigation | 16 | `strategy-framework` | `ai-feedback-loop` |
| Auto-Research Operator Workflow + Catalog-Aware Improver | 17 | `ai-feedback-loop` | `backtesting-validation` |
| Portfolio Snapshot Recording in Runtime Cycle | 17 | `proposal-runtime` | `trading-core` |
| Closed-Trade Performance Records | 17 | `trading-core` | `strategy-framework` |
| Auto-Research Workflow Unblock - Runtime Contract + Backtest Circuit Breaker | 17 | `ai-feedback-loop` | `backtesting-validation` |
| Code-Type Steering for Deterministic Catalog Picks | 17 | `ai-feedback-loop` | `strategy-framework` |
| Stale-Quote Sanity Gate at Proposal Fill | 18 | `proposal-runtime` | `trading-core` |
| Trade-Quality Diagnostic | 18 | `proposal-runtime` | `dashboard-operator-ui` |
| Sub-Account Foundation (entity + registry + default migration) | 19 | `sub-account-capital-segmentation` | `trading-core` |
| Sub-Account Engine Integration | 19 | `sub-account-capital-segmentation` | `proposal-runtime` |
| Multi-Paper-Account Support + YAML Config + Dashboard | 19 | `sub-account-capital-segmentation` | `dashboard-operator-ui` |
| Multi-Credential Live Mode | 19 | `sub-account-capital-segmentation` | `exchange-integration` |
| Strategy-Combination A/B Backtest Harness | 19 | `sub-account-capital-segmentation` | `backtesting-validation` |
| PnL Convention Single Source - Leverage No Double-Apply | 20 | `trading-core` | `backtesting-validation` |
| Backtest / Portfolio Leverage Math Alignment | 20 | `backtesting-validation` | `trading-core` |
| Phase 5.4+ Baseline Re-computation | 20/25 | `backtesting-validation` | |
| UTC-Aware Timestamp Helper + Adapter Migration | 21 | `persistence-data-integrity` | `exchange-integration` |
| `JsonlRotator` UTC Month Boundary | 21 | `persistence-data-integrity` | |
| Stale-Quote Payload Timestamp Coherence | 21 | `proposal-runtime` | `persistence-data-integrity` |
| Atomic JSON Persistence Helper | 22 | `persistence-data-integrity` | |
| Paper Trader Liquidation Visibility | 22 | `trading-core` | |
| AIDLC Hygiene Backfill (sessions / cross-checks / drift) | 23 | `quality-governance` | |
| Phase 17.2 / 17.3 / 17.4 / 17.5 Numbering Reconciliation | 23 | `quality-governance` | |
| Strategy Robustness Polish (intra-trade MDD / MA-SL / OOS guard / cold-start) | 24 | `backtesting-validation` | `strategy-framework` |
| Snapshot Dataset + Format | 25 | `backtesting-validation` | `persistence-data-integrity` |
| `--snapshot` CLI Flag + Script Changes | 25 | `backtesting-validation` | |
| First Run + Populate `docs/baselines.md` | 25 | `backtesting-validation` | |
| Atomic-Write Completion (DEBT-044, 045) | 26 | `persistence-data-integrity` | |
| Code Hygiene Sweep (DEBT-035, 036, 040, 041, 048) | 26 | `quality-governance` | |
| Observability + Logger Test-Friendliness (DEBT-038, 039) | 26 | `quality-governance` | `notifications-ops` |
| Backtester Liquidation Parity (DEBT-047) | 26 | `backtesting-validation` | `trading-core` |
| Black Sweep (DEBT-042) | 26 | `quality-governance` | |

## Unit Ownership by Phase Range

| Phase Range | Dominant Units |
|-------------|----------------|
| 1-4 | `exchange-integration`, `strategy-framework`, `trading-core`, `quality-governance` |
| 5-9 | `backtesting-validation`, `ai-feedback-loop`, `proposal-runtime`, `dashboard-operator-ui` |
| 10-14 | `notifications-ops`, `proposal-runtime`, `exchange-integration`, `ai-feedback-loop` |
| 15-18 | `proposal-runtime`, `ai-feedback-loop`, `strategy-framework`, `trading-core` |
| 19 | `sub-account-capital-segmentation` plus touched integration units |
| 20-22 | `trading-core`, `backtesting-validation`, `persistence-data-integrity` |
| 23-26 | `quality-governance`, `backtesting-validation`, `persistence-data-integrity` |

## How To Use This Map

When starting a new task:

1. Find the relevant legacy component or phase here.
2. Open the primary unit in `unit-of-work.md`.
3. Read the suggested tests and related requirements.
4. Preserve the old phase history in session logs, but plan and cross-check the
   new change by unit.

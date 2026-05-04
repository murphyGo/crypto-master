# Code Generation Plan: strategy-framework

## Migration Status

Legacy Phase work is migrated as brownfield-complete. This plan is not a queue
of unfinished historical tasks.

## Source Legacy Components

| Component | Phase | Secondary Unit |
|-----------|-------|----------------|
| Analysis Technique Framework | 3 | |
| Performance Analyzer | 5 | `backtesting-validation` |
| Strategy Improver (Hypothesis-Driven) | 5 | `ai-feedback-loop` |
| Robustness Validation Gate | 5 | `backtesting-validation` |
| Multi-Timeframe Strategy Support | 9 | `backtesting-validation` |
| Baseline Indicator Strategies | 9 | |
| Multi-Timeframe Backtester | 9 | `backtesting-validation` |
| Per-Timeframe RSI Baselines | 9 | |
| Multi-Technique Per-Symbol Scan | 10 | `proposal-runtime` |
| Chasulang Timeout Mitigation | 14 | `ai-feedback-loop` |
| chasulang Parse + Wedge Mitigation | 16 | `ai-feedback-loop` |
| Closed-Trade Performance Records | 17 | `trading-core` |
| Code-Type Steering for Deterministic Catalog Picks | 17 | `ai-feedback-loop` |
| Strategy Robustness Polish | 24 | `backtesting-validation` |

## Completed Code Generation Steps

- [x] Implement base strategy contracts, loader behavior, and strategy metadata.
- [x] Add prompt/code strategy examples and performance tracking.
- [x] Implement multi-timeframe support and baseline indicator strategies.
- [x] Support multi-technique scans and Chasulang parsing/timeout mitigations.
- [x] Preserve generated-code catalog steering and robustness polish behavior.
- [x] Archive the truncated Donchian experimental artefact outside runtime strategy discovery.

## Evidence

- Requirements: FR-001, FR-002, FR-003, FR-004, FR-005, FR-033, FR-034, FR-035, NFR-005, NFR-010.
- Primary paths: `src/strategy/`, `strategies/`, `tests/test_strategy_*`, `tests/test_rsi_*`.
- Cross-checks: phase 3, phase 9, phase 16, phase 17, and phase 24 reports.
- Session logs: related Phase 3, 5, 9, 14, 16, 17, and 24 entries under `docs/sessions/`.

## Future Work

Add future loader, indicator, generated-strategy, or experimental-artefact work
as new unchecked steps here.

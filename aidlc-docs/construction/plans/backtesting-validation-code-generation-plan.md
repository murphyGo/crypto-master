# Code Generation Plan: backtesting-validation

## Migration Status

Legacy Phase work is migrated as brownfield-complete. This plan is not a queue
of unfinished historical tasks.

## Source Legacy Components

| Component | Phase | Secondary Unit |
|-----------|-------|----------------|
| Backtesting | 5 | |
| Performance Analyzer | 5 | `strategy-framework` |
| Robustness Validation Gate | 5 | `strategy-framework` |
| Feedback Loop | 5 | `ai-feedback-loop` |
| Multi-Timeframe Strategy Support | 9 | `strategy-framework` |
| Multi-Timeframe Backtester | 9 | `strategy-framework` |
| Baseline Reference Numbers | 10 | |
| Volume-Aware Default Paths | 10 | `persistence-data-integrity` |
| BaseExchange.get_ohlcv `since` Parameter | 13 | `exchange-integration` |
| Auto-Research Operator Workflow + Catalog-Aware Improver | 17 | `ai-feedback-loop` |
| Auto-Research Workflow Unblock | 17 | `ai-feedback-loop` |
| Strategy-Combination A/B Backtest Harness | 19 | `sub-account-capital-segmentation` |
| PnL Convention Single Source | 20 | `trading-core` |
| Backtest / Portfolio Leverage Math Alignment | 20 | `trading-core` |
| Phase 5.4+ Baseline Re-computation | 20/25 | |
| Strategy Robustness Polish | 24 | `strategy-framework` |
| Snapshot Dataset + Format | 25 | `persistence-data-integrity` |
| `--snapshot` CLI Flag + Script Changes | 25 | |
| First Run + Populate `docs/baselines.md` | 25 | |
| Backtester Liquidation Parity | 26 | `trading-core` |

## Completed Code Generation Steps

- [x] Implement backtest engine, analyzer, robustness validator, and baseline reporting.
- [x] Add multi-timeframe and per-strategy backtest support.
- [x] Add deterministic snapshot dataset format and `--snapshot` CLI support.
- [x] Align backtest leverage/liquidation behavior with trading and portfolio math.
- [x] Add strategy-combination A/B harness and operator baseline runbook behavior.
- [x] Enable auto-research catalog picks to exercise the robustness sensitivity gate.
- [x] Verify code-type auto-research strategies can emit signals that produce backtest trades.
- [x] Add cumulative parse-failure-rate breaker for intermittent LLM parse failures.

## Evidence

- Requirements: FR-005, FR-025, FR-026, FR-034, FR-038, NFR-006.
- Primary paths: `src/backtest/`, `scripts/backtest_*`, `data/backtest/`, `docs/baselines.md`, `tests/test_backtest_*`.
- Cross-checks: phase 5, phase 9, phase 10, phase 17, phase 19, phase 20, phase 24, phase 25, and phase 26 reports.
- Session logs: related Phase 5, 9, 10, 13, 17, 19, 20, 24, 25, and 26 entries under `docs/sessions/`.

## Future Work

Add future backtest, reproducibility, baseline, robustness, or validation work
as new unchecked steps here.

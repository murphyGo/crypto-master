# Unit of Work Story Map

This map connects standard AI-DLC user stories to the brownfield unit breakdown.

| Unit | Stories | Requirements | Primary Verification |
|------|---------|--------------|----------------------|
| `exchange-integration` | US-008, US-014 | FR-016 - FR-020, NFR-009, NFR-011, CON-002 | `tests/test_exchange_base.py`, `tests/test_exchange_binance.py`, `tests/test_exchange_bybit.py`, config tests |
| `strategy-framework` | US-001, US-003, US-004 | FR-001 - FR-005, FR-027, FR-033 - FR-035, NFR-005, NFR-010 | `tests/test_strategy_loader.py`, `tests/test_strategy_factory.py`, strategy/indicator tests |
| `trading-core` | US-007, US-008, US-009 | FR-006 - FR-010, FR-036, FR-037, NFR-007, NFR-008, NFR-012 | `tests/test_trading_strategy.py`, `tests/test_paper_trading.py`, `tests/test_live_trading.py`, `tests/test_portfolio.py` |
| `backtesting-validation` | US-002, US-003, US-011 | FR-005, FR-025, FR-026, FR-034, FR-038, NFR-006 | `tests/test_backtest_*`, `tests/test_scripts_backtest_*` |
| `ai-feedback-loop` | US-004 | FR-021 - FR-027, FR-033, FR-035, NFR-002, CON-001 | `tests/test_ai_*`, `tests/test_feedback_*`, auto-research script tests |
| `proposal-runtime` | US-005, US-006, US-013 | FR-011 - FR-015, FR-026, CON-003 | `tests/test_proposal_*`, `tests/test_runtime_*`, main dispatch tests |
| `dashboard-operator-ui` | US-012 | FR-028 - FR-032, FR-036, FR-038, NFR-003 | `tests/test_dashboard_*` |
| `dashboard-operator-command-center` | US-012, US-017, US-020, US-022, US-023 | FR-028 - FR-032, FR-036, FR-039, FR-042 - FR-044, NFR-003, NFR-007, NFR-008 | `tests/test_dashboard_app.py`, `tests/test_dashboard_trading.py`, `tests/test_dashboard_engine.py`, `tests/test_dashboard_feedback.py`, `tests/test_dashboard_strategies.py` |
| `notifications-ops` | US-013, US-014 | FR-015, NFR-004, NFR-011, NFR-012 | notification tests, deployment/runbook review |
| `sub-account-capital-segmentation` | US-009, US-010, US-011 | FR-036 - FR-038 | `tests/test_trading_sub_account*`, backtest harness tests |
| `persistence-data-integrity` | US-006, US-007, US-015 | FR-014, NFR-006 - NFR-008 | `tests/test_utils_atomic_write.py`, `tests/test_utils_time.py`, `tests/test_jsonl_rotator.py` |
| `quality-governance` | US-015, US-016 | All | session logs, cross-checks, TECH-DEBT updates, AI-DLC state updates |
| `strategy-promotion-lab` | US-017 | FR-027, FR-034, FR-039 | `tests/test_feedback_promotion_lab.py`, feedback/dashboard tests |
| `sub-account-experiment-marketplace` | US-018 | FR-036, FR-038, FR-040 | sub-account registry tests, backtest harness tests |
| `trade-quality-autopsy` | US-019 | FR-005, FR-021, FR-041 | strategy performance tests, backtest/trading tests |
| `runtime-safety-score` | US-020 | FR-014, FR-015, FR-042, NFR-007 | runtime activity tests, dashboard engine tests |
| `proposal-replay-simulator` | US-021 | FR-013, FR-014, FR-025, FR-043 | proposal/runtime tests, replay script tests |
| `strategy-correlation-governor` | US-022 | FR-036, FR-038, FR-044 | backtest harness tests, runtime exposure tests |
| `market-regime` | US-024 | FR-045, FR-036, FR-029, FR-031, NFR-003, NFR-007, NFR-008 | regime classifier tests, sub-account policy tests, runtime proposal-gating tests, dashboard tests |

## Planning Use

For new work:

1. Identify the story or requirement first.
2. Select the owning unit from this map.
3. Open `aidlc-docs/inception/units/unit-of-work.md` for paths and suggested
   tests.
4. Create or resume the appropriate construction plan under
   `aidlc-docs/construction/plans/`.

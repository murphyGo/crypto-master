# Unit of Work: Crypto Master Brownfield Breakdown

## Overview

The original Crypto Master plan is chronological. This document remaps the
existing implementation into AI-DLC units so future development can be planned,
reviewed, tested, and cross-checked by bounded functional area.

For a row-by-row mapping from `docs/development-plan.md` components to these
units, see `aidlc-docs/inception/units/legacy-phase-map.md`.

For active technical debt grouped by these units, see
`aidlc-docs/inception/units/debt-unit-map.md`.

## Unit Summary

| Unit | Purpose | Primary Paths |
|------|---------|---------------|
| `exchange-integration` | Exchange adapters and market/order API abstraction | `src/exchange/`, `src/config.py`, `tests/test_exchange_*` |
| `strategy-framework` | Strategy definition, loading, indicators, multi-timeframe support | `src/strategy/`, `strategies/`, `tests/test_strategy_*`, `tests/test_rsi_*` |
| `trading-core` | Paper/live trading, portfolio, risk math, profiles, PnL conventions | `src/trading/`, `src/utils/trading_math.py`, `trading_profiles/`, `tests/test_trading_*`, `tests/test_portfolio.py` |
| `backtesting-validation` | Backtest engine, snapshots, robustness gates, baseline reports | `src/backtest/`, `scripts/backtest_*`, `data/backtest/`, `docs/baselines.md`, `tests/test_backtest_*` |
| `ai-feedback-loop` | Claude CLI integration, strategy improver, feedback loop, audit | `src/ai/`, `src/feedback/`, `scripts/auto_research_candidates.py`, `tests/test_ai_*`, `tests/test_feedback_*` |
| `proposal-runtime` | Proposal lifecycle, runtime cycles, activity logs, stale-quote and cap gates | `src/proposal/`, `src/runtime/`, `src/main.py`, `tests/test_proposal_*`, `tests/test_runtime_*` |
| `dashboard-operator-ui` | Streamlit dashboard and operator-facing monitoring/control pages | `src/dashboard/`, `tests/test_dashboard_*` |
| `notifications-ops` | Notification backends, deployment, runtime operations, log retention | `src/proposal/notification.py`, `Dockerfile`, `fly.toml`, `start.sh`, `docs/deployment.md` |
| `sub-account-capital-segmentation` | Independent capital pools, credential bindings, A/B harness | `src/trading/sub_account*.py`, `config/sub_accounts.yaml.example`, `src/backtest/harness.py`, `tests/test_trading_sub_account*` |
| `persistence-data-integrity` | Atomic writes, JSON/JSONL rotation, UTC timestamp contracts | `src/utils/io.py`, `src/utils/time.py`, `src/runtime/jsonl_rotator.py`, `tests/test_utils_*`, `tests/test_jsonl_rotator.py` |
| `quality-governance` | Session logs, cross-checks, technical debt, generated skills, AI-DLC overlay | `docs/`, `.agents/`, `.claude/`, `aidlc-docs/`, `aidlc-workflows/` |

## Detailed Units

### `exchange-integration`

- **Responsibilities**: Exchange abstraction, Binance/Bybit implementations,
  OHLCV/ticker/balance/order methods, testnet/live credentials, rate-limit-safe
  API behavior.
- **Related Requirements**: FR-016, FR-017, FR-018, FR-019, FR-020, NFR-009,
  NFR-011.
- **Legacy Phases**: 2, 10.1, 13.3.
- **Existing Status**: Complete.
- **Future Change Triggers**: New exchange, credential model change, OHLCV
  contract change, live order behavior change.
- **Suggested Tests**: `tests/test_exchange_base.py`,
  `tests/test_exchange_binance.py`, `tests/test_exchange_bybit.py`,
  credential/config tests.

### `strategy-framework`

- **Responsibilities**: Prompt/code strategy loading, strategy factory,
  indicators, multi-timeframe support, baseline strategies, active vs
  experimental strategy boundaries.
- **Related Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-033,
  FR-034, FR-035, NFR-005, NFR-010.
- **Legacy Phases**: 3, 9, 16, 24.
- **Existing Status**: Complete.
- **Future Change Triggers**: New strategy type, metadata contract changes,
  indicator behavior changes, robustness admission changes.
- **Suggested Tests**: `tests/test_strategy_loader.py`,
  `tests/test_strategy_factory.py`, `tests/test_strategy_indicators.py`,
  `tests/test_baseline_strategies.py`, `tests/test_multi_timeframe_smoke.py`.

### `trading-core`

- **Responsibilities**: Trade calculation, live/paper execution, portfolio
  snapshots, profile loading, PnL/leverage conventions, liquidation visibility.
- **Related Requirements**: FR-006, FR-007, FR-008, FR-009, FR-010, FR-036,
  FR-037, NFR-007, NFR-008, NFR-012.
- **Legacy Phases**: 4, 10, 20, 22.
- **Existing Status**: Complete.
- **Future Change Triggers**: Position sizing, leverage math, live execution,
  portfolio accounting, profile schema.
- **Suggested Tests**: `tests/test_trading_strategy.py`,
  `tests/test_paper_trading.py`, `tests/test_live_trading.py`,
  `tests/test_portfolio.py`, `tests/test_leverage_pnl_no_double_apply.py`.

### `backtesting-validation`

- **Responsibilities**: Backtest engine, analysis, multi-account harness,
  snapshot-pinned reproducibility, robustness validation gates, baseline report
  generation.
- **Related Requirements**: FR-005, FR-025, FR-026, FR-034, FR-038, NFR-006.
- **Legacy Phases**: 5, 17, 24, 25.
- **Existing Status**: Complete.
- **Future Change Triggers**: New robustness gate, snapshot schema, baseline
  script changes, A/B harness behavior.
- **Suggested Tests**: `tests/test_backtest_engine.py`,
  `tests/test_backtest_harness.py`, `tests/test_backtest_snapshot.py`,
  `tests/test_backtest_validator.py`, `tests/test_scripts_backtest_*`.

### `ai-feedback-loop`

- **Responsibilities**: Claude CLI wrapper, strategy improver, generated idea
  workflow, performance analysis feedback, audit trail.
- **Related Requirements**: FR-021, FR-022, FR-023, FR-024, FR-026, FR-027,
  FR-033, FR-035, NFR-002.
- **Legacy Phases**: 5, 12.3, 17.
- **Existing Status**: Complete.
- **Future Change Triggers**: Prompt contract changes, timeout/retry behavior,
  generated strategy schema, feedback audit changes.
- **Suggested Tests**: `tests/test_ai_claude.py`,
  `tests/test_ai_improver.py`, `tests/test_feedback_loop.py`,
  `tests/test_feedback_audit.py`,
  `tests/test_scripts_auto_research_candidates.py`.

### `proposal-runtime`

- **Responsibilities**: Proposal generation, accept/reject flow, notification
  dispatch hook, runtime cycle orchestration, activity logs, stale-quote checks,
  cross-cycle position cap.
- **Related Requirements**: FR-011, FR-012, FR-013, FR-014, FR-015, FR-026,
  NFR-012.
- **Legacy Phases**: 6, 8, 12, 18, 21.
- **Existing Status**: Complete.
- **Future Change Triggers**: Proposal scoring, acceptance gates, runtime
  counters, activity event schema, main entrypoint behavior.
- **Suggested Tests**: `tests/test_proposal_engine.py`,
  `tests/test_proposal_interaction.py`,
  `tests/test_proposal_notification.py`, `tests/test_runtime_engine.py`,
  `tests/test_runtime_activity_log.py`, `tests/test_main_dispatch.py`.

### `dashboard-operator-ui`

- **Responsibilities**: Streamlit application shell, dashboard data loading,
  strategy/trading/feedback/runtime/sub-account pages, operator visibility.
- **Related Requirements**: FR-028, FR-029, FR-030, FR-031, FR-032, FR-036,
  FR-038, NFR-003.
- **Legacy Phases**: 7, 8.2, 19.3.
- **Existing Status**: Complete.
- **Future Change Triggers**: New operator workflow, new runtime metric,
  sub-account UI changes, visualization changes.
- **Suggested Tests**: `tests/test_dashboard_app.py`,
  `tests/test_dashboard_engine.py`, `tests/test_dashboard_feedback.py`,
  `tests/test_dashboard_strategies.py`,
  `tests/test_dashboard_trading.py`.

### `notifications-ops`

- **Responsibilities**: Slack/Telegram/email backends, deployment packaging,
  Fly.io runtime, start script, log retention, operator runbooks.
- **Related Requirements**: FR-015, NFR-004, NFR-011, NFR-012.
- **Legacy Phases**: 8.3, 10.4, 11.3, 12.4, 13.4, 14.
- **Existing Status**: Complete.
- **Future Change Triggers**: New notification channel, delivery semantics,
  deployment target, credential handling, production diagnostics.
- **Suggested Tests**: `tests/test_proposal_notification.py`,
  deployment/runbook review, targeted notification backend tests.

### `sub-account-capital-segmentation`

- **Responsibilities**: Capital pool isolation, default migration, YAML
  sub-account config, live credential binding, multi-account backtest reports.
- **Related Requirements**: FR-036, FR-037, FR-038.
- **Legacy Phases**: 19.
- **Existing Status**: Complete.
- **Future Change Triggers**: Account allocation semantics, credential binding,
  dashboard presentation, A/B harness output.
- **Suggested Tests**: `tests/test_trading_sub_account.py`,
  `tests/test_trading_sub_account_migration.py`,
  `tests/test_trading_sub_account_registry.py`,
  `tests/test_backtest_harness.py`.

### `persistence-data-integrity`

- **Responsibilities**: Atomic JSON writes, UTC-aware timestamp helpers,
  JSONL rotation, stale-quote timestamp coherence, file persistence contracts.
- **Related Requirements**: NFR-006, NFR-007, NFR-008.
- **Legacy Phases**: 21, 22, 26.
- **Existing Status**: Complete.
- **Future Change Triggers**: Persistence path changes, timestamp format
  changes, activity/event schema changes, atomicity requirements.
- **Suggested Tests**: `tests/test_utils_atomic_write.py`,
  `tests/test_utils_time.py`, `tests/test_jsonl_rotator.py`,
  runtime/proposal persistence tests.

### `quality-governance`

- **Responsibilities**: AI-DLC overlay, session logs, cross-checks, tech debt,
  lint/type sweeps, generated agent/team skills, documentation hygiene.
- **Related Requirements**: Cross-cutting traceability and process controls.
- **Legacy Phases**: 11, 12.2, 23, 26.
- **Existing Status**: Complete.
- **Future Change Triggers**: New development workflow, new quality gate,
  documentation structure migration, agent/team update.
- **Suggested Tests**: Documentation validation, targeted skill dry-run,
  `uv run pytest` for code-affecting changes.

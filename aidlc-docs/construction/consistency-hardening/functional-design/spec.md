# Functional Design: consistency-hardening

## Purpose

`consistency-hardening` owns cross-cutting refactor and code-consistency work
that is too broad for a single existing functional unit but too concrete to
leave as unstructured review notes. It exists to preserve operational
correctness while the brownfield system expands across sub-accounts, live
trading, generated strategies, dashboard command-center workflows, and
backtest-driven promotion gates.

The unit does not replace the underlying owner units. Each implementation slice
must still name its primary functional owner and targeted tests.

## Source Findings

The unit starts from the 2026-05-08 five-subagent review after commit
`1a01866 Harden live safety contracts`. Findings already fixed in that commit
are out of scope unless a regression reappears:

- named testnet credentials satisfying live mode,
- partial/zero/non-filled live market orders being persisted,
- missing `ENGINE_MAX_TICKER_AGE_SECONDS` settings wiring,
- `symbols: []` not being treated as universal strategy metadata.

## Scope

### Live and Exchange Safety

- Align exchange instance mode with credential selection for legacy
  Binance/Bybit configs.
- Preserve actual live fill price, quantity, and fee information in
  trade history.
- Complete account-scoped exchange routing for proposal validation,
  SL/TP monitoring, and portfolio snapshots.
- Track persisted open-position hydration after restart.

### Runtime and Notification Consistency

- Isolate runtime cycle failures by sub-account so one account cannot block
  scan, monitor, or snapshot work for later accounts.
- Surface backend-specific notification failures as activity events that feed
  runtime safety scoring.
- Recompute or otherwise update runtime safety hard-pause inputs after
  same-proposal notification/correlation incidents.
- Normalize proposal lifecycle timestamps and avoid sub-account-ambiguous
  proposal history updates.

### Generated Strategy and Feedback Contracts

- Keep `.py` candidate promotion from injecting markdown frontmatter.
- Use atomic writes for generated strategy and operator artifact files.
- Ensure markdown prompt outputs cannot bypass Output Contract checks with
  `technique_type: code`.
- Keep prompt Output Contract validation aligned with runtime parser fields.

### Backtest and Promotion Validity

- Distinguish warmup/data insufficiency from structural strategy contract
  errors in `StrategyValidationError` handling.
- Route multi-timeframe strategies correctly through the backtest harness.
- Represent skipped robustness gates as conditional operator evidence rather
  than indistinguishable pass/fail state.
- Reduce serializer/report drift across backtest engine, baseline scripts, and
  combination reports.

### Dashboard and Quality Governance

- Make command-center sub-account discovery include configured-only accounts.
- Compute aggregate equity from latest snapshot per sub-account rather than a
  single latest snapshot.
- Apply command-center scope consistently to incidents, safety factors, and
  candidate evidence.
- Align active queue references away from legacy `docs/development-plan.md`
  where team routing still drifts.

## Non-Goals

- Do not batch all findings into one large implementation PR.
- Do not use this unit to bypass the owning unit's tests or requirements.
- Do not migrate or delete runtime `data/`.
- Do not change live trading defaults without explicit safety tests and
  operator-facing documentation.

## Prioritized Backlog

Slice IDs are stable across sessions so plan files, session logs, and
cross-checks can reference them directly. Existing fixed slices keep their ID
even after the work ships. New findings from the 2026-05-09 five-subagent
review are captured below with file:line anchors so each slice can be picked
up without rerunning the review.

| Slice ID | Priority | Slice | Anchors | Primary Owner Units | Suggested Tests | Status |
|----------|----------|-------|---------|---------------------|-----------------|--------|
| CH-01 | P1 | Legacy exchange config mode/credential alignment | `src/config.py`, `src/exchange/binance.py:159`, `src/exchange/bybit.py:90` | `exchange-integration`, `trading-core` | `tests/test_main_dispatch.py`, `tests/test_exchange_*` | Shipped 2026-05-09 (commit `97e6d4f`) |
| CH-02 | P1 | `.py` strategy promotion integrity + atomic artifact writes | `src/feedback/loop.py:691`, `src/ai/improver.py:533` | `ai-feedback-loop`, `strategy-framework`, `persistence-data-integrity` | `tests/test_feedback_loop.py`, `tests/test_ai_improver.py`, `tests/test_strategy_loader.py` | Open |
| CH-03 | P1 | Sub-account cycle failure isolation + notifier failure visibility | `src/runtime/engine.py:417`, `src/proposal/notification.py:754` | `proposal-runtime`, `sub-account-capital-segmentation`, `notifications-ops`, `runtime-safety-score` | `tests/test_runtime_engine.py`, `tests/test_proposal_notification.py` | Open |
| CH-04 | P1 | Split `StrategyValidationError` (warmup vs structural contract) | `src/strategy/base.py:339`, `src/backtest/engine.py:518`, `src/strategy/loader.py:171` | `strategy-framework`, `backtesting-validation` | `tests/test_backtest_engine.py`, `tests/test_strategy_loader.py` | Open |
| CH-05 | P1 | Dashboard command-center scope + aggregate equity consistency | `src/dashboard/app.py:246`, `src/dashboard/app.py:317`, `src/dashboard/app.py:259` | `dashboard-operator-command-center` | `tests/test_dashboard_app.py` | Open |
| CH-06 | P1 | Live fill attribution: actual exit price + fees on `LiveTrader` | `src/trading/live.py:236`, `src/trading/live.py:429` | `trading-core`, `exchange-integration` | `tests/test_live_trading.py`, `tests/test_exchange_*` | Open |
| CH-07 | P1 | Live position rehydration on restart (SL/TP enforcement) | `src/trading/live.py:189`, `src/trading/live.py:334` | `trading-core`, `persistence-data-integrity` | `tests/test_live_trading.py` | Open |
| CH-08 | P1 | Account-scoped exchange routing for multi-account live | `src/main.py:418`, `src/trading/sub_account_registry.py:218` | `sub-account-capital-segmentation`, `trading-core` | `tests/test_main_dispatch.py`, `tests/test_trading_sub_account*.py` | Open |
| CH-09 | P1 | Multi-timeframe + robustness reporting in `BacktestHarness` | `src/backtest/harness.py:43`, `src/backtest/multi_account_report.py:26` | `backtesting-validation`, `strategy-framework` | `tests/test_backtest_harness.py`, `tests/test_backtest_multi_timeframe.py` | Open |
| CH-10 | P1 | Hard-pause gate uses post-incident safety score | `src/runtime/engine.py:572`, `src/runtime/engine.py:625` | `runtime-safety-score`, `proposal-runtime` | `tests/test_runtime_engine.py` | Open |
| CH-11 | P2 | `technique_type: code` Output-Contract bypass on markdown generations | `src/ai/improver.py:398` | `ai-feedback-loop` | `tests/test_ai_improver.py` | Open |
| CH-12 | P2 | `ProposalHistory.load` sub-account ambiguity | `src/proposal/interaction.py:248` | `proposal-runtime`, `persistence-data-integrity` | `tests/test_proposal_interaction.py` | Open |
| CH-13 | P2 | JSONL append rotation race + lost-line counter | `src/runtime/jsonl_rotator.py:172` | `persistence-data-integrity` | `tests/test_jsonl_rotator.py` | Open |
| CH-14 | P2 | `ActivityEvent`/`AuditEvent` schema versioning | `src/runtime/activity_log.py:151`, `src/feedback/audit.py` | `persistence-data-integrity`, `quality-governance` | `tests/test_logger.py`, `tests/test_feedback_audit.py` | Open |
| CH-15 | P2 | Baseline scripts: serializer reuse + atomic writes | `scripts/backtest_baselines.py:279`, `src/backtest/analyzer.py:550` | `backtesting-validation`, `persistence-data-integrity` | `tests/test_baseline_strategies.py`, `tests/test_backtest_analyzer.py` | Open |
| CH-16 | P2 | Regime gate requires ≥2 evaluable regimes | `src/backtest/validator.py:660` | `backtesting-validation` | `tests/test_backtest_validator.py` | Open |
| CH-17 | P2 | BinanceExchange/BybitExchange contract parity (CCXT helpers) | `src/exchange/binance.py`, `src/exchange/bybit.py` | `exchange-integration` | `tests/test_exchange_binance.py`, `tests/test_exchange_bybit.py` | Open |
| CH-18 | P2 | Drillthrough query params carry mode/scope | `src/dashboard/app.py:520`, `src/dashboard/app.py:656` | `dashboard-operator-command-center`, `dashboard-operator-ui` | `tests/test_dashboard_app.py` | Open |
| CH-19 | P2 | Active-queue caption points at unit-of-work, not legacy plan | `src/dashboard/app.py:239` | `dashboard-operator-ui`, `quality-governance` | `tests/test_dashboard_app.py` | Open |
| CH-20 | P3 | Shared dashboard `query_param_first/values` helper | `src/dashboard/pages/*.py` | `dashboard-operator-ui` | `tests/test_dashboard_*` | Open |
| CH-21 | P3 | Cycle-scoped lookup cache for correlation gate | `src/runtime/engine.py:825` | `proposal-runtime` | `tests/test_runtime_engine.py` | Open |
| CH-22 | P3 | Indicator helpers consolidated under `src/strategy/indicators.py` | `strategies/raschke_holy_grail.py:119`, `strategies/vcp_breakout.py:139` | `strategy-framework` | `tests/test_strategy_*` | Open |
| CH-23 | P3 | `ClaudeCLI` env allowlist (no API-key leakage) | `src/ai/claude.py:283` | `ai-feedback-loop` | `tests/test_ai_claude.py` | Open |
| CH-24 | P3 | Equity-curve entry-bar slippage phantom mark removal | `src/backtest/engine.py:1188` | `backtesting-validation` | `tests/test_backtest_engine.py` | Open |
| CH-25 | P3 | Dead-code cleanup: live `model_copy(filled_quantity)`, paper testnet fee/margin, duplicated auto-confirm callbacks | `src/trading/live.py:237`, `src/trading/paper.py:910`, `src/main.py:184`, `src/trading/sub_account_registry.py:381` | `trading-core` | `tests/test_live_trading.py`, `tests/test_paper_trading.py` | Open |

## Acceptance Criteria

- Each slice has a focused implementation summary and cross-check evidence.
- Each slice adds or updates regression tests for the exact consistency issue.
- Cross-unit behavior changes cite both this unit and the primary owner unit.
- Deferred findings are linked to `docs/TECH-DEBT.md` rather than left as
  free-text TODOs.

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
`1a01866 Harden live safety contracts`, was extended on 2026-05-09 with the
five-subagent review (CH-07..CH-25), and is extended again on 2026-05-09 with
a ten-subagent refactor / code-consistency review covering every `src/`
package (CH-26..CH-36). Findings already fixed in that commit
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
| CH-02 | P1 | `.py` strategy promotion integrity + atomic artifact writes | `src/feedback/loop.py:691`, `src/ai/improver.py:533` | `ai-feedback-loop`, `strategy-framework`, `persistence-data-integrity` | `tests/test_feedback_loop.py`, `tests/test_ai_improver.py`, `tests/test_strategy_loader.py` | Shipped 2026-05-09 (`d19b308`) |
| CH-03 | P1 | Sub-account cycle failure isolation + notifier failure visibility | `src/runtime/engine.py:417`, `src/proposal/notification.py:754` | `proposal-runtime`, `sub-account-capital-segmentation`, `notifications-ops`, `runtime-safety-score` | `tests/test_runtime_engine.py`, `tests/test_proposal_notification.py` | Shipped 2026-05-09 (`c7c30b7`) |
| CH-04 | P1 | Split `StrategyValidationError` (warmup vs structural contract) | `src/strategy/base.py:339`, `src/backtest/engine.py:518`, `src/strategy/loader.py:171` | `strategy-framework`, `backtesting-validation` | `tests/test_backtest_engine.py`, `tests/test_strategy_loader.py` | Shipped 2026-05-09 (`c108c3c`) |
| CH-05 | P1 | Dashboard command-center scope + aggregate equity consistency | `src/dashboard/app.py:246`, `src/dashboard/app.py:317`, `src/dashboard/app.py:259` | `dashboard-operator-command-center` | `tests/test_dashboard_app.py` | Shipped 2026-05-09 |
| CH-06 | P1 | Live fill attribution: actual exit price + fees on `LiveTrader` | `src/trading/live.py:236`, `src/trading/live.py:429` | `trading-core`, `exchange-integration` | `tests/test_live_trading.py`, `tests/test_exchange_*` | Shipped 2026-05-09 |
| CH-07 | P1 | Live position rehydration on restart (SL/TP enforcement) | `src/trading/live.py:189`, `src/trading/live.py:334` | `trading-core`, `persistence-data-integrity` | `tests/test_live_trading.py` | Shipped 2026-05-09 |
| CH-08 | P1 | Account-scoped exchange routing for multi-account live | `src/main.py:418`, `src/trading/sub_account_registry.py:218` | `sub-account-capital-segmentation`, `trading-core` | `tests/test_main_dispatch.py`, `tests/test_trading_sub_account*.py` | Shipped 2026-05-09 |
| CH-09 | P1 | Multi-timeframe + robustness reporting in `BacktestHarness` | `src/backtest/harness.py:43`, `src/backtest/multi_account_report.py:26` | `backtesting-validation`, `strategy-framework` | `tests/test_backtest_harness.py`, `tests/test_backtest_multi_timeframe.py` | Shipped 2026-05-09 |
| CH-10 | P1 | Hard-pause gate uses post-incident safety score | `src/runtime/engine.py:572`, `src/runtime/engine.py:625` | `runtime-safety-score`, `proposal-runtime` | `tests/test_runtime_engine.py` | Shipped 2026-05-09 |
| CH-11 | P2 | `technique_type: code` Output-Contract bypass on markdown generations | `src/ai/improver.py:398` | `ai-feedback-loop` | `tests/test_ai_improver.py` | Shipped 2026-05-09 |
| CH-12 | P2 | `ProposalHistory.load` sub-account ambiguity | `src/proposal/interaction.py:248` | `proposal-runtime`, `persistence-data-integrity` | `tests/test_proposal_interaction.py` | Shipped 2026-05-09 |
| CH-13 | P2 | JSONL append rotation race + lost-line counter | `src/runtime/jsonl_rotator.py:172` | `persistence-data-integrity` | `tests/test_jsonl_rotator.py` | Shipped 2026-05-09 |
| CH-14 | P2 | `ActivityEvent`/`AuditEvent` schema versioning | `src/runtime/activity_log.py:151`, `src/feedback/audit.py` | `persistence-data-integrity`, `quality-governance` | `tests/test_logger.py`, `tests/test_feedback_audit.py` | Shipped 2026-05-09 |
| CH-15 | P2 | Baseline scripts: serializer reuse + atomic writes | `scripts/backtest_baselines.py:279`, `src/backtest/analyzer.py:550` | `backtesting-validation`, `persistence-data-integrity` | `tests/test_baseline_strategies.py`, `tests/test_backtest_analyzer.py` | Shipped 2026-05-09 |
| CH-16 | P2 | Regime gate requires ≥2 evaluable regimes | `src/backtest/validator.py:660` | `backtesting-validation` | `tests/test_backtest_validator.py` | Shipped 2026-05-09 |
| CH-17 | P2 | BinanceExchange/BybitExchange contract parity (CCXT helpers) | `src/exchange/binance.py`, `src/exchange/bybit.py` | `exchange-integration` | `tests/test_exchange_binance.py`, `tests/test_exchange_bybit.py` | Shipped 2026-05-09 |
| CH-18 | P2 | Drillthrough query params carry mode/scope | `src/dashboard/app.py:520`, `src/dashboard/app.py:656` | `dashboard-operator-command-center`, `dashboard-operator-ui` | `tests/test_dashboard_app.py` | Shipped 2026-05-09 |
| CH-19 | P2 | Active-queue caption points at unit-of-work, not legacy plan | `src/dashboard/app.py:239` | `dashboard-operator-ui`, `quality-governance` | `tests/test_dashboard_app.py` | Shipped 2026-05-09 (folded into CH-05) |
| CH-20 | P3 | Shared dashboard `query_param_first/values` helper | `src/dashboard/pages/*.py` | `dashboard-operator-ui` | `tests/test_dashboard_*` | Shipped 2026-05-09 |
| CH-21 | P3 | Cycle-scoped lookup cache for correlation gate | `src/runtime/engine.py:825` | `proposal-runtime` | `tests/test_runtime_engine.py` | Shipped 2026-05-09 |
| CH-22 | P3 | Indicator helpers consolidated under `src/strategy/indicators.py` | `strategies/raschke_holy_grail.py:119`, `strategies/vcp_breakout.py:139` | `strategy-framework` | `tests/test_strategy_*` | Shipped 2026-05-09 |
| CH-23 | P3 | `ClaudeCLI` env allowlist (no API-key leakage) | `src/ai/claude.py:283` | `ai-feedback-loop` | `tests/test_ai_claude.py` | Shipped 2026-05-09 |
| CH-24 | P3 | Equity-curve entry-bar slippage phantom mark removal | `src/backtest/engine.py:1188` | `backtesting-validation` | `tests/test_backtest_engine.py` | Shipped 2026-05-09 |
| CH-25 | P3 | Dead-code cleanup: live `model_copy(filled_quantity)`, paper testnet fee/margin, duplicated auto-confirm callbacks | `src/trading/live.py:237`, `src/trading/paper.py:910`, `src/main.py:184`, `src/trading/sub_account_registry.py:381` | `trading-core` | `tests/test_live_trading.py`, `tests/test_paper_trading.py` | Verified superseded 2026-05-09: anchors are active fill/confirmation contracts |
| CH-26 | P1 | Backtest metrics consolidation (`src/backtest/metrics.py`): unified Sharpe/MDD/win-loss across validator+analyzer+engine+harness, drawdown truncation at first liquidation | `src/backtest/validator.py:902`, `src/backtest/analyzer.py:247`, `src/backtest/analyzer.py:310`, `src/backtest/engine.py:1227`, `src/backtest/harness.py:136` | `backtesting-validation`, `quality-governance` | `tests/test_backtest_validator.py`, `tests/test_backtest_analyzer.py`, `tests/test_backtest_engine.py` | Shipped 2026-05-09 |
| CH-27 | P1 | Backtest simulation-loop dedup: extract `_execute_bar` helper from `Backtester.run` and `run_multi_timeframe` (~170 lines duplicated) | `src/backtest/engine.py:471`, `src/backtest/engine.py:717` | `backtesting-validation` | `tests/test_backtest_engine.py`, `tests/test_backtest_multi_timeframe.py` | Shipped 2026-05-09 (`382d3b9`) |
| CH-28 | P1 | Paper/Live trader contract parity: testnet `close_position`/`open_position_on_testnet` fee + actual fill price capture, SL/TP signature unification, `_entry_fees` orphan cleanup | `src/trading/paper.py:962`, `src/trading/paper.py:1061`, `src/trading/live.py:191`, `src/trading/live.py:264`, `src/trading/base.py` | `trading-core`, `exchange-integration` | `tests/test_paper_trading.py`, `tests/test_live_trading.py` | Shipped 2026-05-09 (`48e461c`) |
| CH-29 | P1 | Proposal gate decision envelope + atomic record write: chain notify→decision→correlation→safety→cap into a `GateOutcome`, save+log once, eliminate `_correlation_gate` reload-modify-save race | `src/runtime/engine.py:655`, `src/runtime/engine.py:744`, `src/runtime/engine.py:980`, `src/runtime/engine.py:1030` | `proposal-runtime`, `runtime-safety-score`, `persistence-data-integrity` | `tests/test_runtime_engine.py`, `tests/test_proposal_*` | Shipped 2026-05-09 (`0cf51a3`) |
| CH-30 | P1 | Engine bootstrap + policy resolver decomposition: split `build_engine` (260 lines) and `_runtime_policy_for` (105-line conditional chain) into phase functions / `PolicyResolver` class | `src/main.py:245`, `src/runtime/engine.py:1615` | `proposal-runtime`, `sub-account-capital-segmentation`, `quality-governance` | `tests/test_main_dispatch.py`, `tests/test_runtime_engine.py` | Shipped 2026-05-09 (`5d3f4d9`) |
| CH-31 | P1 | SubAccount dual-source field removal: deprecate root `initial_balance`/`strategy_filter` in favor of `capital_policy`/`strategy_policy`, reconcile `RiskOverrides` vs `RiskPolicy` (incl. `risk_percent` `float` vs `Decimal`) | `src/trading/sub_account.py:224`, `src/trading/sub_account.py:225`, `src/trading/sub_account.py:289`, `src/trading/profiles.py`, `src/trading/experiment_marketplace.py:105` | `sub-account-capital-segmentation`, `sub-account-experiment-marketplace`, `trading-core` | `tests/test_trading_sub_account*.py`, `tests/test_trading_profiles.py` | Shipped 2026-05-09 (`73181b0`) |
| CH-32 | P1 | Atomic write coverage: sub-account migration marker, feedback promotion `_promote_file` rollback path on `unlink` failure, `.md` frontmatter rewrites in strategy loader | `src/trading/sub_account_migration.py:95`, `src/feedback/loop.py:705`, `src/feedback/loop.py:816`, `src/strategy/loader.py:375` | `persistence-data-integrity`, `ai-feedback-loop`, `strategy-framework` | `tests/test_trading_sub_account_migration.py`, `tests/test_feedback_loop.py`, `tests/test_strategy_loader.py` | Shipped 2026-05-09 (`29b58c5`) |
| CH-33 | P2 | Long-function decomposition (`_build_proposal_for_strategy` 162 lines multi-TF/single-TF dedup, `StrategyImprover._build_*_prompt` 78/111-line sections, notifier payload triplication) | `src/proposal/engine.py:543`, `src/ai/improver.py:654`, `src/ai/improver.py:783`, `src/proposal/notification.py:259`, `src/proposal/notification.py:385`, `src/proposal/notification.py:525` | `proposal-runtime`, `ai-feedback-loop`, `notifications-ops` | `tests/test_proposal_engine.py`, `tests/test_ai_improver.py`, `tests/test_proposal_notification.py` | Shipped 2026-05-09 (`47a723e`) |
| CH-34 | P2 | Per-cycle cache extension (extends CH-21): cache `_runtime_policy_for_id`, runtime safety score, and `_strategy_lookup_for_open_trades` once per cycle to remove N+1 reloads | `src/runtime/engine.py:672`, `src/runtime/engine.py:925`, `src/runtime/engine.py:1021` | `proposal-runtime`, `runtime-safety-score` | `tests/test_runtime_engine.py` | Shipped 2026-05-09 (`ddd55a9`) |
| CH-35 | P2 | Trading vocabulary + error envelope unification: `Side`/`TradeSide` type aliases in `src/utils/`, structured `EngineError` dataclass replacing string vs dict mix in `result.errors` | `src/models.py`, `src/utils/trading_math.py:48`, `src/runtime/engine.py:605`, `src/runtime/engine.py:1355` | `trading-core`, `proposal-runtime`, `quality-governance` | `tests/test_models.py`, `tests/test_runtime_engine.py` | In progress: shared `TradeSide`/`PositionSide` aliases shipped 2026-05-09 |
| CH-36 | P2 | Shared validator mixins + parse-error semantics: `DecimalFieldsMixin` (Performance/TradeHistory), `UtcTimestampMixin` (feedback/proposal), unify `audit.read_all` (warn-skip) vs `loop.load_state` (raise) on corrupt records | `src/strategy/performance.py:109`, `src/strategy/performance.py:921`, `src/feedback/loop.py:110`, `src/feedback/promotion_lab.py:49`, `src/feedback/audit.py:180`, `src/feedback/loop.py:492` | `quality-governance`, `ai-feedback-loop`, `persistence-data-integrity` | `tests/test_strategy_performance.py`, `tests/test_feedback_loop.py`, `tests/test_feedback_audit.py`, `tests/test_feedback_promotion_lab.py` | In progress: `UtcTimestampMixin` shipped 2026-05-09 |

## Acceptance Criteria

- Each slice has a focused implementation summary and cross-check evidence.
- Each slice adds or updates regression tests for the exact consistency issue.
- Cross-unit behavior changes cite both this unit and the primary owner unit.
- Deferred findings are linked to `docs/TECH-DEBT.md` rather than left as
  free-text TODOs.

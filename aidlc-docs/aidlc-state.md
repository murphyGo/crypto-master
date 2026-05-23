# AI-DLC State Tracking

## Project Information

- **Project Name**: Crypto Master
- **Project Type**: Brownfield
- **Overlay Created**: 2026-05-03
- **Current Stage**: CONSTRUCTION - Brownfield Ready
- **Workspace Root**: `/Users/user/Desktop/Projects/crypto-master`

## Workspace State

- **Existing Code**: Yes
- **Primary Language**: Python 3.10+
- **Build System**: `pyproject.toml`, `uv.lock`, `requirements.txt`
- **Application Shape**: Modular monolith with Streamlit dashboard, runtime
  engine, exchange adapters, strategy framework, backtest engine, proposal
  workflow, and local JSON/JSONL persistence.
- **Reverse Engineering Needed**: No for baseline overlay; rerun when major
  module boundaries change.

## Code Location Rules

- **Application Code**: Workspace root (`src/`, `strategies/`, `scripts/`,
  `tests/`)
- **AI-DLC Documentation**: `aidlc-docs/`
- **Legacy Documentation**: `docs/`, `DESIGN.md`, `CLAUDE.md`
- **Runtime Data**: `data/` is operator/runtime data and must not be migrated
  or deleted by AI-DLC overlay tasks.

## Inception Artifacts

| Artifact | Status | Path |
|----------|--------|------|
| Workspace Detection | Complete | `aidlc-docs/aidlc-state.md` |
| Requirements | Complete | `aidlc-docs/inception/requirements/requirements.md` |
| Requirement Verification Questions | Complete | `aidlc-docs/inception/requirements/requirement-verification-questions.md` |
| User Stories | Complete | `aidlc-docs/inception/user-stories/stories.md` |
| Personas | Complete | `aidlc-docs/inception/user-stories/personas.md` |
| Application Design | Complete | `aidlc-docs/inception/application-design/` |
| Reverse Engineering | Complete | `aidlc-docs/inception/reverse-engineering/` |
| Unit Breakdown | Complete | `aidlc-docs/inception/units/unit-of-work.md` |
| Legacy Phase Crosswalk | Complete | `aidlc-docs/inception/units/legacy-phase-map.md` |
| Debt Unit Map | Complete | `aidlc-docs/inception/units/debt-unit-map.md` |
| Execution Plan | Complete | `aidlc-docs/inception/plans/execution-plan.md` |

## Construction Artifacts

| Artifact | Status | Path |
|----------|--------|------|
| Construction Workspace | Ready | `aidlc-docs/construction/` |
| Construction Plan Queue | Ready | `aidlc-docs/construction/plans/` |
| Build and Test Workspace | Ready on demand | `aidlc-docs/construction/build-and-test/` |

Construction artifacts are created just in time for new work. Existing Phase
1-26 implementation is not replayed through construction plans.

## Unit Progress

| Unit | Existing Implementation | AI-DLC State | Next Action |
|------|-------------------------|--------------|-------------|
| `exchange-integration` | Complete | Brownfield-complete; construction-ready | Track future exchange changes in construction plans |
| `strategy-framework` | Complete | Brownfield-complete; construction-ready; 2026-05-08 deterministic market/swing strategy expansions logged; 2026-05-13 DEBT-060 closed (RSI baseline family TP raised 0.04 → 0.05 across `strategies/rsi.py` / `strategies/rsi_4h.py` / `strategies/rsi_15m.py` in `14ca04c`; quant-ratified post-widen R/R floor = 2.22 on binding 4h-alt case; regression coverage added via per-strategy TP-constant pin and parametrized 3-row positive R/R floor mirror; dashboard fail-closed-rate observability scope-split to DEBT-061) | Track future strategy loader/indicator changes in construction plans |
| `trading-core` | Complete | Brownfield-complete; construction-ready; 2026-05-12 paper persistence follow-ups shipped for DEBT-059/058/057 (restart-safe balance snapshots, legacy SL/TP backfill tooling confirmation, entry-fee persistence) | Track future paper/live/risk math changes in construction plans |
| `backtesting-validation` | Complete | Brownfield-complete; construction-ready; 2026-05-24 (`50a7080`) added `raschke_holy_grail` + `ma_crossover` `StrategySpec` entries to `scripts/run_robustness_gate.py` (count assertion 7 → 9 in `tests/test_run_robustness_gate.py`); both verified end-to-end via `--live` against BTC/USDT, both FAIL all edge gates (consistent with no-OHLCV-only-edge finding); `raschke_holy_grail` SKIPs the sensitivity gate (module-level constant knobs, no `param_grid`), `ma_crossover` exercises it via a short/long period grid | Track future robustness/baseline changes in construction plans |
| `ai-feedback-loop` | Complete | Brownfield-complete; construction-ready; 2026-05-13 DEBT-056 closed (fixture-vs-validator drift in `tests/test_scripts_auto_research_candidates.py` aligned with `85a33b0` runtime-validator hardening; `## Output Contract` block + `"hypothesis"` keys added; 2 lint sites cleared via `ruff --fix`; pytest 1808 passed) | Track future Claude/improver loop changes in construction plans |
| `proposal-runtime` | Complete | Brownfield-complete; construction-ready; 2026-05-13 DEBT-061 closed (per-strategy fail-closed counter instrumentation in `ProposalEngine._build_proposal_for_strategy` at emit / `StrategyError` catch / `TradingValidationError` catch; new `src/proposal/fail_closed_metrics.py` with `StrategyFailClosedCounts` Pydantic model `model_validate`-enforced on every increment + `FailClosedMetricsTracker` writing `data/performance/<sub_account_id>/<technique_name>/fail_closed.json` via `atomic_write_text`; `sub_account_id` plumbed as per-call argument after second-round 🔴 fix; quant Q1/Q2/Q4 ratified-as-shipped, Q4 per-reason breakdown deferred as non-breaking extension; pytest 1843 passed, net +31); 2026-05-13 DEBT-070 closed (ranking-side `total_trades` → `real_trade_count` sweep: 4 reads in `ProposalEngine._select_best_technique` at `src/proposal/engine.py:996, 1010, 1014` and `_select_all_techniques` at `:1132` switched with inline `# DEBT-070:` comments; display sites at `src/dashboard/pages/strategies.py:118` and `src/ai/improver.py:667` intentionally untouched; pinned by `test_select_best_technique_tiebreaks_on_real_trade_count` + `test_select_best_technique_any_history_ignores_synthetic_only` in `tests/test_proposal_engine.py`; pytest 2061 passed, net +2) | Track future proposal/runtime cycle changes in construction plans |
| `dashboard-operator-ui` | Complete | Brownfield-complete; construction-ready; 2026-05-13 per-strategy `Emitted` / `Fail-Closed` / `Fail-Closed %` columns shipped on the Strategies page (`src/dashboard/pages/strategies.py`) as part of DEBT-061 closeout | Track future Streamlit/operator UI changes in construction plans |
| `dashboard-operator-command-center` | Complete | Home command center shipped with safety/freshness, account context, exposure detail, strategy evidence drilldown, incident actions, runtime diagnostics, and page-level drillthrough links | Track future shared state or cross-page workflow refinements in construction plans |
| `notifications-ops` | Complete | Runtime notification operations plus Ops Diagnostics dashboard for data-directory, activity-log freshness, and optional health URL checks shipped | Track future notification, deployment, credential, runtime process, or operations changes in construction plans |
| `sub-account-capital-segmentation` | Complete | Brownfield-complete; construction-ready | Track future capital isolation changes in construction plans |
| `persistence-data-integrity` | Complete | Brownfield-complete; construction-ready | Track future timestamp/atomic persistence changes in construction plans |
| `quality-governance` | Complete | Brownfield-complete; construction-ready; 2026-05-13 `mypy src` repo-wide clean milestone — `Success: no issues found in 88 source files` for the first time this session, achieved by bundled DEBT-067 + DEBT-070 close-out (DEBT-067 cleared the 3 pre-existing `src/dashboard/app.py` errors that had been QA-noise across the past 4 unit cycles); candidate future-work item: optional CI gate to lock the repo-wide-clean baseline (queued, NOT filed as DEBT pending explicit user approval) | Track future AI-DLC hygiene, debt, and review changes in construction plans |
| `consistency-hardening` | Complete | CH-01 `97e6d4f`, CH-02 `d19b308`, CH-03 `c7c30b7`, CH-04 `c108c3c`, CH-05 `809638f`, CH-06 (live fill attribution: actual exit price + entry/exit fees on `LiveTrader`) shipped 2026-05-09, CH-07 (live position rehydration from persisted SL/TP + fee state) shipped 2026-05-09, CH-08 (account-scoped exchange routing for scan/stale-quote/monitor/snapshot) shipped 2026-05-09, CH-09 (BacktestHarness multi-TF routing + per-strategy robustness reporting) shipped 2026-05-09, CH-10 (post-notification/correlation incident safety-score recompute before hard pause) shipped 2026-05-09, CH-11..CH-18 and CH-20..CH-24 shipped 2026-05-09, CH-25 verified superseded by active fill/confirmation contracts 2026-05-09, CH-26 (`src/backtest/metrics.py` shared outcome/return/Sharpe/MDD helpers) shipped 2026-05-09, CH-27 `_execute_bar` loop dedup + parity regression shipped 2026-05-09 (`955897f`), CH-28 paper/live SL/TP parity + live entry-fee cleanup shipped 2026-05-09 (`48e461c`), CH-29 proposal gate envelope + single final save shipped 2026-05-09 (`0cf51a3`), CH-30 build_engine phase split + PolicyResolver shipped 2026-05-09 (`5d3f4d9`), CH-31 policy-field-only sub-account runtime + Decimal profile risk shipped 2026-05-09 (`73181b0`), CH-32 feedback promotion rollback + YAML reparse shipped 2026-05-09 (`29b58c5`), CH-33 proposal/improver/notification helper decomposition shipped 2026-05-09 (`47a723e`), CH-34 runtime policy/safety per-cycle cache shipped 2026-05-09 (`c99573c`), CH-35 structured engine errors + shared trading side aliases shipped 2026-05-09 (`072bb73`), CH-36 shared validator mixins + parse-error semantics shipped 2026-05-09 (`eccbade`); spec.md backlog extended with CH-26..CH-36 from the 2026-05-09 ten-subagent refactor review (36 anchored slices total); 2026-05-13 DEBT-055 CH-27 multi-TF parity test gaps resolved (4 parity variants + true non-degenerate divergence test in `TestRunMultiTimeframeParity`; superseded test deleted) | Track future cross-cutting consistency work in construction plans |
| `strategy-promotion-lab` | Complete | First-pass scoring, observation persistence, dashboard recommendations, and operator action helper shipped | Track future lab workflow refinements in construction plans |
| `sub-account-experiment-marketplace` | Complete | Template schema, YAML rendering, publish-time validation, policy-block sub-account config, runtime strategy-per-account paper lab config, and dashboard config discovery shipped | Track future marketplace dashboard/operator tooling in construction plans |
| `trade-quality-autopsy` | Complete | Evidence model, candle-window excursions, improvement-context summaries, and Trade Autopsy dashboard drilldown shipped | Track future candle-window enrichment for runtime dashboard autopsies in construction plans |
| `runtime-safety-score` | Complete | Safety score contract, activity aggregation, dashboard section, notification summary hooks, and opt-in runtime hard-pause gate shipped | Track future threshold calibration and default-policy changes in construction plans |
| `proposal-replay-simulator` | Complete | Replay input model, threshold/exit comparison, operator Markdown report, file-based CLI, and Proposal Replay dashboard page shipped | Track future in-dashboard replay input generation in construction plans |
| `strategy-correlation-governor` | Complete | Backtest/runtime exposure inputs, duplicate-exposure warnings, and optional rejection gate shipped | Track future engine/dashboard wiring in construction plans |
| `runtime-reconciliation` | Complete | Shipped 2026-05-13. State taxonomy (`src/runtime/reconciliation.py`), async startup health check, persistent dashboard banner with cash-only suppression rule, `close_unrecoverable_paper_trades` CLI with synthetic-perf-record markers (`synthetic`/`reconciliation_close` fields on `PerformanceRecord`), hybrid locked-consistency tolerance, `RECONCILIATION_HEALTH_CHECK_FAILED` meta-event for silent-disable visibility. 1942 passed (+60). 2026-05-13 DEBT-065 closed (option (b): new `TechniquePerformance.real_trade_count` property = `total_trades - synthetic_count`; `ProposalEngine._cold_start_blocks_live` + `_score.sample_size` switched to read it; `total_trades` semantics preserved for operator-facing display; canonical 9+2 defect at threshold 10 now correctly blocks; pytest 2054 passed, net +7; QA-surfaced ranking-side follow-up filed as DEBT-070). 2026-05-13 DEBT-064 + DEBT-066 bundled close-out: DEBT-064 added `is_stale` auxiliary signal to `OpenTradeClassification` (state-independent, 7-day default via `DEFAULT_STALE_THRESHOLD_SECONDS`, configurable per-call via new `now` + `stale_threshold_seconds` kwargs on `classify_open_trade`, `entry_time` as conservative `last_seen_at` proxy since `TradeHistory` has no `last_seen_at` field today) + new `compute_closed_but_malformed_count(data_dir, sub_account_id)` sweep over `status="closed"` rows with `exit_price IS NULL` or `exit_time IS NULL`; `compute_health_report` surfaces both `stale_count` + `closed_but_malformed_count` per-sub-account and at totals; `_load_open_trade_rows` open-row filter intentionally untouched; 10 new tests in `tests/test_runtime_reconciliation.py`. DEBT-066 added `_mark_price_cache: dict[str, MarkPriceEntry]` to `TradingEngine` populated at 3 existing ticker-fetch sites (`_monitor` SL/TP, orphan force-close, `_record_portfolio_snapshot`) — zero new exchange calls; `_get_cached_mark_price(symbol, *, max_age_seconds=300.0)` w/ freshness gate; `_build_cap_blocker_payload` consumes the cache (long `(mark-entry)/entry × 100`, short `(entry-mark)/entry × 100`, matching `pnl_for_trade` sign convention); cache-miss `None` fallback preserved as regression-safe; 6 new tests in `tests/test_runtime_engine.py`. pytest 2078 passed (was 2061; net +17 zero regressions); ruff clean; **`mypy src` repo-wide clean milestone preserved (88 source files, zero issues)**. | No remaining runtime-reconciliation follow-ups (DEBT-064 + DEBT-065 + DEBT-066 all resolved). |
| `proposal-funnel-audit` | Complete | Shipped 2026-05-13. `ProposalFinalState` enum (15 states + `gate_rejected_unknown` legacy fallback) on `ProposalRecord`, `record_id` threaded into all 10 post-acceptance gate emission sites, `_handle_proposal` rewrites `final_state` on every transition, cap-blocker diagnostic payload consuming `runtime-reconciliation.classify_open_trade` for `monitorable` flag, `src/proposal/funnel.py` aggregator (derived-on-read), new Proposals dashboard page + command-center single-line summary. 1978 passed (+36). | Track DEBT-066 (in-memory mark-price cache for cap-blocker `unrealized_pnl_percent`) and DEBT-067 (pre-existing `src/dashboard/app.py` mypy errors at lines 285, 869, 882). |
| `cross-account-risk-policy` | Slice 2(c-1) Complete | Slice 1 shipped 2026-05-13. `RiskPolicy` schema extensions + `GlobalRiskPolicy` + `compute_risk_budget_size` helper, `_account_aggregate_cap_gate` (notional + stop-risk) + `_stale_position_block_gate` wired after symbol-cap with paper-advisory / live-hard-block semantics. 3 new `ProposalFinalState` terminals. 2007 passed (+29). 2026-05-15 DEBT-068(a) shipped: `TradingEngine._risk_budget_sizing_gate` now wires `sizing_mode='risk_budget'`, rewrites `proposal.quantity` before downstream gates, rejects helper failures with `gate_rejected_risk_sizing`, uses account balances with explicit `CapitalPolicy.sizing_balance` fallback, and removes the temporary config-time fail-closed validator. Targeted pytest 174 passed. 2026-05-24 planning update narrowed DEBT-068(b) to opt-in global exposure caps: default disabled; paper advisory / would-block only; live hard-block only when explicitly enabled, preserving paper-lab strategy measurement. 2026-05-24 DEBT-068(b) shipped (`a088e17`): `GlobalRiskPolicy.enabled`/`paper_mode`/`live_mode` opt-in fields (`src/trading/sub_account.py`, `enabled` defaults false / unset caps inert); new `TradingEngine._global_aggregate_cap_gate` wired into `_handle_proposal` after `_account_aggregate_cap_gate` + `_stale_position_block_gate` (and after `_correlation_gate`) per spec ordering — aggregates open positions across all sub-accounts and enforces `max_open_positions_per_symbol_side` / `max_gross_notional_per_symbol_side` / `max_gross_notional_per_symbol`; paper mode advisory-with-event (never blocks), live mode hard-blocks only when explicitly enabled; v1 arbitration `first_come_first_serve` (`cap_resolution=lowest_priority_loses` deferred to DEBT-068(c)). New `ProposalFinalState.GATE_REJECTED_GLOBAL_CAP` terminal + `FunnelCounts.gate_rejected_global_cap` label/count wiring. 7 engine gate tests + 3 config-parsing tests; targeted pytest 189 passed; full suite 2097 passed, 0 failed; ruff + mypy clean; quant-trader-expert "sound — ship", qa-reviewer 🟢. 2026-05-24 DEBT-068(c-1) shipped (uncommitted on `main` at log time; committed immediately after): STATELESS kill-switch gates. `TradingEngine._account_kill_switch_gate` (per-account open-unrealized-drawdown then open-stop-risk, first breach wins) + `_global_kill_switch_gate` (portfolio open-drawdown summed across enabled sub-accounts), both in `src/runtime/engine.py`, wired into `_handle_proposal` after the regime gate and before sizing/caps. Helpers: `_open_stop_risk_sum` (now shared with `_account_aggregate_cap_gate` — behavior-preserving refactor), `_account_equity` (quote balance → `CapitalPolicy.sizing_balance` fallback → fail-open on missing equity), `_open_unrealized_pnl` (reuses `pnl_for_trade` over the synchronous mark cache, excludes stale-mark positions), `_kill_switch_outcome` (paper advisory / live hard-block). Three new `ProposalFinalState` terminals (`GATE_REJECTED_OPEN_DRAWDOWN_KILL_SWITCH` / `GATE_REJECTED_OPEN_STOP_RISK_KILL_SWITCH` / `GATE_REJECTED_PORTFOLIO_KILL_SWITCH` in `src/proposal/interaction.py`) + `src/proposal/funnel.py` count/label wiring. Lead decisions: paper mode advisory-only (per-account kill switches do NOT halt paper labs, event-only); equity baseline uses the reconstruction approach (no state file). Config-driven, no hardcoded thresholds — per-account inert when `_pct` is `None`, global inert unless `GlobalRiskPolicy.enabled`. 13 new tests; full suite 2107 passed (+13), 0 failed; ruff + mypy clean; quant-trader-expert "sound — ship" (non-blocking note: zero/negative exchange equity hard-blocks in live — filed DEBT-068(c-1-note-equity)), qa-reviewer 🟢 (one 🟡: `_account_equity` exception branch `# pragma: no cover` — filed DEBT-068(c-1-note-cover)). Session log `docs/sessions/2026-05-24-cross-account-risk-policy-kill-switch-c1.md`. **Remaining DEBT-068 umbrella**: (c-2) STATEFUL daily-loss kill switch (realized-PnL-since-UTC-midnight, restart-survives — NEXT slice), (c-arb) `cap_resolution=lowest_priority_loses` arbitration, (d) operator freeze, (e) stale auto-close / alert-only, (f) dashboard exposure panel, (g) `RISK_CAP_ADVISORY` event type, (h) runtime-safety-score integration. | Track DEBT-068(c-2) next, then (c-arb)/(d)–(h). DEBT-069 if QA's `interaction.py:108-111` comment nit is filed. |
| `market-regime` | Complete | Classifier (`src/runtime/market_regime.py`), `MarketRegimePolicy` on `SubAccount`, `_market_regime_gate` wired into `_handle_proposal`, per-cycle classification cache, `MARKET_REGIME_BLOCKED` + `MARKET_REGIME_DEGRADED` activity events, dashboard section, 39 new tests (1843→1882). Shipped 2026-05-13. 2026-05-13 DEBT-062 + DEBT-063 closed (gate-sequencing relocation: `_market_regime_gate` moved after `_correlation_gate` so the actionable correlation-block signal wins on the operator dashboard when both gates would block; classifier hysteresis: `classify_regime_detailed` now requires 2-bar confirmation before flipping out of `sideways`, ±2% threshold unchanged for `RobustnessGate._classify_regimes` parity; pytest 2054 → 2059, ruff + mypy clean). | No remaining market-regime follow-ups. |
| `strategy-tuning` | Slice 1 Complete | Slice 1 shipped 2026-05-13. `StrategyAction` enum + `StrategyTuningPolicy` (frozen, per-account + per-strategy override), pure `recommend_action` recommender with priority `pause → shadow → scout → retune → keep → promote`, `_strategy_action_gate` wired after correlation gate. 6 action behaviors implemented (keep/promote pass-through; retune+advisory; scout scales quantity; shadow persists `shadow=True` record; pause rejects). 2 new `ProposalFinalState` terminals + funnel plumbing. 2047 passed (+39). **Slice 2 deferred (DEBT-069 umbrella)**: dashboard view, initial-action seeding, observation store, `STRATEGY_ACTION_APPLIED` emission, PF computation upgrade, pause-reason split, funnel test gaps. | Track DEBT-069 (Slice 2 umbrella). |

## Construction Stage Policy

Existing Phase 1-26 work is not replayed through construction stages. It is
registered as brownfield-complete and mapped into units. New work should be
planned against one or more units using this stage order:

1. Functional Design, if behavior or contracts change.
2. NFR Requirements / NFR Design, if reliability, security, operations,
   latency, persistence, or trading safety changes.
3. Infrastructure Design, if deployment, credentials, runtime process, or
   external service topology changes.
4. Code Generation.
5. Build and Test.
6. Unit cross-check and session log.

New work is tracked in `aidlc-docs/construction/plans/` and unit-specific
subdirectories under `aidlc-docs/construction/`.
`docs/legacy/development-plan.md` is legacy chronology, not the active queue.

## Canonical Inception Paths

The brownfield overlay keeps reverse-engineering and legacy maps as evidence,
but AI-DLC planning should now start from the standard inception tree:

1. Requirements: `aidlc-docs/inception/requirements/requirements.md`
2. Verification questions:
   `aidlc-docs/inception/requirements/requirement-verification-questions.md`
3. Personas and stories: `aidlc-docs/inception/user-stories/`
4. Application design: `aidlc-docs/inception/application-design/`
5. Unit ownership and legacy/debt crosswalks: `aidlc-docs/inception/units/`

`docs/requirements.md` remains the historical detailed requirements document and
change log. The AI-DLC requirements index points back to it for full text.

## Legacy References

- Chronological plan archive: `docs/legacy/development-plan.md`
- Development plan pointer: `docs/development-plan.md`
- Canonical AI-DLC requirements:
  `aidlc-docs/inception/requirements/requirements.md`
- Canonical AI-DLC stories: `aidlc-docs/inception/user-stories/stories.md`
- Canonical AI-DLC application design:
  `aidlc-docs/inception/application-design/`
- Legacy phase to unit map: `aidlc-docs/inception/units/legacy-phase-map.md`
- Debt to unit map: `aidlc-docs/inception/units/debt-unit-map.md`
- Requirements: `docs/requirements.md`
- Architecture: `DESIGN.md`
- Project guide: `CLAUDE.md`
- Debt registry: `docs/TECH-DEBT.md`
- Session logs: `docs/sessions/`
- Cross-checks: `docs/cross-checks/`

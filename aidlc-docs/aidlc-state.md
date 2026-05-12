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
| `backtesting-validation` | Complete | Brownfield-complete; construction-ready | Track future robustness/baseline changes in construction plans |
| `ai-feedback-loop` | Complete | Brownfield-complete; construction-ready; 2026-05-13 DEBT-056 closed (fixture-vs-validator drift in `tests/test_scripts_auto_research_candidates.py` aligned with `85a33b0` runtime-validator hardening; `## Output Contract` block + `"hypothesis"` keys added; 2 lint sites cleared via `ruff --fix`; pytest 1808 passed) | Track future Claude/improver loop changes in construction plans |
| `proposal-runtime` | Complete | Brownfield-complete; construction-ready; 2026-05-13 DEBT-061 closed (per-strategy fail-closed counter instrumentation in `ProposalEngine._build_proposal_for_strategy` at emit / `StrategyError` catch / `TradingValidationError` catch; new `src/proposal/fail_closed_metrics.py` with `StrategyFailClosedCounts` Pydantic model `model_validate`-enforced on every increment + `FailClosedMetricsTracker` writing `data/performance/<sub_account_id>/<technique_name>/fail_closed.json` via `atomic_write_text`; `sub_account_id` plumbed as per-call argument after second-round 🔴 fix; quant Q1/Q2/Q4 ratified-as-shipped, Q4 per-reason breakdown deferred as non-breaking extension; pytest 1843 passed, net +31) | Track future proposal/runtime cycle changes in construction plans |
| `dashboard-operator-ui` | Complete | Brownfield-complete; construction-ready; 2026-05-13 per-strategy `Emitted` / `Fail-Closed` / `Fail-Closed %` columns shipped on the Strategies page (`src/dashboard/pages/strategies.py`) as part of DEBT-061 closeout | Track future Streamlit/operator UI changes in construction plans |
| `dashboard-operator-command-center` | Complete | Home command center shipped with safety/freshness, account context, exposure detail, strategy evidence drilldown, incident actions, runtime diagnostics, and page-level drillthrough links | Track future shared state or cross-page workflow refinements in construction plans |
| `notifications-ops` | Complete | Runtime notification operations plus Ops Diagnostics dashboard for data-directory, activity-log freshness, and optional health URL checks shipped | Track future notification, deployment, credential, runtime process, or operations changes in construction plans |
| `sub-account-capital-segmentation` | Complete | Brownfield-complete; construction-ready | Track future capital isolation changes in construction plans |
| `persistence-data-integrity` | Complete | Brownfield-complete; construction-ready | Track future timestamp/atomic persistence changes in construction plans |
| `quality-governance` | Complete | Brownfield-complete; construction-ready | Track future AI-DLC hygiene, debt, and review changes in construction plans |
| `consistency-hardening` | Complete | CH-01 `97e6d4f`, CH-02 `d19b308`, CH-03 `c7c30b7`, CH-04 `c108c3c`, CH-05 `809638f`, CH-06 (live fill attribution: actual exit price + entry/exit fees on `LiveTrader`) shipped 2026-05-09, CH-07 (live position rehydration from persisted SL/TP + fee state) shipped 2026-05-09, CH-08 (account-scoped exchange routing for scan/stale-quote/monitor/snapshot) shipped 2026-05-09, CH-09 (BacktestHarness multi-TF routing + per-strategy robustness reporting) shipped 2026-05-09, CH-10 (post-notification/correlation incident safety-score recompute before hard pause) shipped 2026-05-09, CH-11..CH-18 and CH-20..CH-24 shipped 2026-05-09, CH-25 verified superseded by active fill/confirmation contracts 2026-05-09, CH-26 (`src/backtest/metrics.py` shared outcome/return/Sharpe/MDD helpers) shipped 2026-05-09, CH-27 `_execute_bar` loop dedup + parity regression shipped 2026-05-09 (`955897f`), CH-28 paper/live SL/TP parity + live entry-fee cleanup shipped 2026-05-09 (`48e461c`), CH-29 proposal gate envelope + single final save shipped 2026-05-09 (`0cf51a3`), CH-30 build_engine phase split + PolicyResolver shipped 2026-05-09 (`5d3f4d9`), CH-31 policy-field-only sub-account runtime + Decimal profile risk shipped 2026-05-09 (`73181b0`), CH-32 feedback promotion rollback + YAML reparse shipped 2026-05-09 (`29b58c5`), CH-33 proposal/improver/notification helper decomposition shipped 2026-05-09 (`47a723e`), CH-34 runtime policy/safety per-cycle cache shipped 2026-05-09 (`c99573c`), CH-35 structured engine errors + shared trading side aliases shipped 2026-05-09 (`072bb73`), CH-36 shared validator mixins + parse-error semantics shipped 2026-05-09 (`eccbade`); spec.md backlog extended with CH-26..CH-36 from the 2026-05-09 ten-subagent refactor review (36 anchored slices total); 2026-05-13 DEBT-055 CH-27 multi-TF parity test gaps resolved (4 parity variants + true non-degenerate divergence test in `TestRunMultiTimeframeParity`; superseded test deleted) | Track future cross-cutting consistency work in construction plans |
| `strategy-promotion-lab` | Complete | First-pass scoring, observation persistence, dashboard recommendations, and operator action helper shipped | Track future lab workflow refinements in construction plans |
| `sub-account-experiment-marketplace` | Complete | Template schema, YAML rendering, publish-time validation, policy-block sub-account config, runtime strategy-per-account paper lab config, and dashboard config discovery shipped | Track future marketplace dashboard/operator tooling in construction plans |
| `trade-quality-autopsy` | Complete | Evidence model, candle-window excursions, improvement-context summaries, and Trade Autopsy dashboard drilldown shipped | Track future candle-window enrichment for runtime dashboard autopsies in construction plans |
| `runtime-safety-score` | Complete | Safety score contract, activity aggregation, dashboard section, notification summary hooks, and opt-in runtime hard-pause gate shipped | Track future threshold calibration and default-policy changes in construction plans |
| `proposal-replay-simulator` | Complete | Replay input model, threshold/exit comparison, operator Markdown report, file-based CLI, and Proposal Replay dashboard page shipped | Track future in-dashboard replay input generation in construction plans |
| `strategy-correlation-governor` | Complete | Backtest/runtime exposure inputs, duplicate-exposure warnings, and optional rejection gate shipped | Track future engine/dashboard wiring in construction plans |
| `runtime-reconciliation` | Complete | Shipped 2026-05-13. State taxonomy (`src/runtime/reconciliation.py`), async startup health check, persistent dashboard banner with cash-only suppression rule, `close_unrecoverable_paper_trades` CLI with synthetic-perf-record markers (`synthetic`/`reconciliation_close` fields on `PerformanceRecord`), hybrid locked-consistency tolerance, `RECONCILIATION_HEALTH_CHECK_FAILED` meta-event for silent-disable visibility. 1942 passed (+60). | Track DEBT-064 (taxonomy gaps) and DEBT-065 (synthetic-row leak into live-promotion gating). |
| `proposal-funnel-audit` | Complete | Shipped 2026-05-13. `ProposalFinalState` enum (15 states + `gate_rejected_unknown` legacy fallback) on `ProposalRecord`, `record_id` threaded into all 10 post-acceptance gate emission sites, `_handle_proposal` rewrites `final_state` on every transition, cap-blocker diagnostic payload consuming `runtime-reconciliation.classify_open_trade` for `monitorable` flag, `src/proposal/funnel.py` aggregator (derived-on-read), new Proposals dashboard page + command-center single-line summary. 1978 passed (+36). | Track DEBT-066 (in-memory mark-price cache for cap-blocker `unrealized_pnl_percent`) and DEBT-067 (pre-existing `src/dashboard/app.py` mypy errors at lines 285, 869, 882). |
| `cross-account-risk-policy` | Slice 1 Complete | Slice 1 shipped 2026-05-13. `RiskPolicy` schema extensions + `GlobalRiskPolicy` + `compute_risk_budget_size` helper (unit-tested, NOT yet wired into ProposalEngine — DEBT-068), `_account_aggregate_cap_gate` (notional + stop-risk) + `_stale_position_block_gate` wired after symbol-cap with paper-advisory / live-hard-block semantics. 3 new `ProposalFinalState` terminals. 2007 passed (+29). **Slice 2 deferred (DEBT-068 umbrella)**: global symbol/side caps, kill switches, operator freeze, stale auto-close, dashboard panel, risk-sizing wire-in, `RISK_CAP_ADVISORY` event type. | Track DEBT-068 (Slice 2 umbrella). DEBT-069 if QA's `interaction.py:108-111` comment nit is filed. |
| `market-regime` | Complete | Classifier (`src/runtime/market_regime.py`), `MarketRegimePolicy` on `SubAccount`, `_market_regime_gate` wired into `_handle_proposal`, per-cycle classification cache, `MARKET_REGIME_BLOCKED` + `MARKET_REGIME_DEGRADED` activity events, dashboard section, 39 new tests (1843→1882). Shipped 2026-05-13. | Track DEBT-062 (gate sequencing) and DEBT-063 (classifier hysteresis) follow-ups. |
| `strategy-tuning` | Not started | Design complete; code-generation queued. Functional-design spec landed 2026-05-13 at `aidlc-docs/construction/strategy-tuning/functional-design/spec.md`; defines a per-(sub-account, strategy) action state machine (keep/shadow/scout/pause/promote/retune) with evidence thresholds and per-strategy initial recommendations. Code-generation blocked on 6 open decisions. | Resolve open decisions, then run code-generation cycle against the staged plan |

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

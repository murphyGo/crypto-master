# Crypto Master - Development Plan

## Reference Documents

- `docs/requirements.md` - Requirements Specification
- `docs/inception.md` - Project Concept Document

---

## Current Status

| Component | Status | Phase |
|-----------|--------|-------|
| Project Setup | ✅ Complete | 1 |
| Configuration Management | ✅ Complete | 1 |
| Exchange Abstraction | ✅ Complete | 2 |
| Binance Integration | ✅ Complete | 2 |
| Bybit Integration | ✅ Complete | 2 |
| Analysis Technique Framework | ✅ Complete | 3 |
| Claude Integration | ✅ Complete | 3 |
| Trading Strategy | ✅ Complete | 4 |
| Exchange Testnet Support | ✅ Complete | 4 |
| Paper Trading (Local) | ✅ Complete | 4 |
| Paper Trading (Testnet) | ✅ Complete | 4 |
| Paper Trading (Fees) | ✅ Complete | 4 |
| Live Trading | ✅ Complete | 4 |
| Portfolio / Asset Management | ✅ Complete | 4 |
| Trading Strategy Profiles | ✅ Complete | 4 |
| Backtesting | ✅ Complete | 5 |
| Performance Analyzer | ✅ Complete | 5 |
| Strategy Improver (Hypothesis-Driven) | ✅ Complete | 5 |
| Robustness Validation Gate | ✅ Complete | 5 |
| Feedback Loop | ✅ Complete | 5 |
| Trading Proposal | ✅ Complete | 6 |
| UI Dashboard | ✅ Complete | 7 |
| Trading Engine Runtime | ✅ Complete | 8 |
| Engine Status Dashboard Page | ✅ Complete | 8 |
| Fly.io Deployment | ✅ Complete | 8 |
| Multi-Timeframe Strategy Support | ✅ Complete | 9 |
| Baseline Indicator Strategies | ✅ Complete | 9 |
| Multi-Timeframe Backtester | ✅ Complete | 9 |
| Per-Timeframe RSI Baselines | ✅ Complete | 9 |
| Live Trading Wiring | ✅ Complete | 10 |
| EngineConfig Env Override | ✅ Complete | 10 |
| Baseline Reference Numbers | ✅ Complete | 10 |
| Log Retention Policy | ✅ Complete | 10 |
| Volume-Aware Default Paths | ✅ Complete | 10 |
| Multi-Technique Per-Symbol Scan | ✅ Complete | 10 |
| Pre-Existing Lint/Type Sweep | ✅ Complete | 11 |
| OHLCV Cache for Multi-Technique Scan | ✅ Complete | 11 |
| Notification Push Backend | ✅ Complete | 11 |
| ProposalHistory.purge_old Wiring | ✅ Complete | 11 |
| Cross-Cycle Position Cap | ✅ Complete | 12 |
| Residual mypy Sweep | ✅ Complete | 12 |
| LLM Strategy Timeout Handling | ✅ Complete | 12 |
| Telegram Notification Backend | ✅ Complete | 12 |
| Cleanup Batch (DEBT-009/010/011) | ✅ Complete | 13 |
| EngineConfig Remaining-Fields Env Override | ✅ Complete | 13 |
| BaseExchange.get_ohlcv `since` Parameter | ✅ Complete | 13 |
| Email Notification Backend | ✅ Complete | 13 |
| Chasulang Timeout Mitigation | ✅ Complete | 14 |
| SMTP_SSL Alternative | ✅ Complete | 14 |
| Diagnostic Clarity | ✅ Complete | 15 |
| chasulang Parse + Wedge Mitigation | ✅ Complete | 16 |
| Auto-Research Operator Workflow + Catalog-Aware Improver | ✅ Complete | 17 |
| Portfolio Snapshot Recording in Runtime Cycle | ✅ Complete | 17 |
| Closed-Trade Performance Records | ✅ Complete | 17 |
| Auto-Research Workflow Unblock — Runtime Contract + Backtest Circuit Breaker | ✅ Complete | 17 |
| Code-Type Steering for Deterministic Catalog Picks | ❌ Missing | 17 |
| Stale-Quote Sanity Gate at Proposal Fill | ✅ Complete | 18 |
| Trade-Quality Diagnostic | ❌ Missing | 18 |
| Sub-Account Foundation (entity + registry + default migration) | ❌ Missing | 19 |
| Sub-Account Engine Integration | ❌ Missing | 19 |
| Multi-Paper-Account Support + YAML Config + Dashboard | ❌ Missing | 19 |
| Multi-Credential Live Mode | ❌ Missing | 19 |
| Strategy-Combination A/B Backtest Harness | ❌ Missing | 19 |
| PnL Convention Single Source — Leverage No Double-Apply | ✅ Complete | 20 |
| Backtest / Portfolio Leverage Math Alignment | ✅ Complete | 20 |
| Phase 5.4+ Baseline Re-computation | ⏸ Deferred (Phase 25) | 20 [^p20-3] |
| UTC-Aware Timestamp Helper + Adapter Migration | ✅ Complete | 21 |
| `JsonlRotator` UTC Month Boundary | ✅ Complete | 21 |
| Stale-Quote Payload Timestamp Coherence | ✅ Complete | 21 |
| Atomic JSON Persistence Helper | ✅ Complete | 22 |
| Paper Trader Liquidation Visibility | ✅ Complete | 22 |
| AIDLC Hygiene Backfill (sessions / cross-checks / drift) | ✅ Complete | 23 |
| Phase 17.2 / 17.3 / 17.4 / 17.5 Numbering Reconciliation | ✅ Complete | 23 |
| Strategy Robustness Polish (intra-trade MDD / MA-SL / OOS guard / cold-start) | ✅ Complete | 24 |
| Snapshot Dataset + Format | ✅ Complete | 25 |
| `--snapshot` CLI Flag + Script Changes | ✅ Complete | 25 |
| First Run + Populate `docs/baselines.md` (Part A: runbook ✅; Part B: operator) | ✅ Complete[^p25-3] | 25 |

**Status Legend**: ✅ Complete | 🔄 In Progress | ❌ Missing | ⏸ Deferred

[^p20-3]: Phase 20.3 reframed 2026-05-01 — `scripts/backtest_baselines.py` calls live Binance with no snapshot mode (non-deterministic, operator-only), `data/backtest/baselines/` directory absent, `docs/baselines.md` operator table all `_TBD_`. The "operator-artefact regeneration" framing (DEBT-029) was vacuous — no inflated artefacts had ever been persisted; the math fix (DEBT-024) closed at the code level by 20.1 + 20.2. Snapshot-pinned reproducibility re-scoped to Phase 25 (closes new DEBT-043). DEBT-029 closed as **Reframed**.

[^p25-3]: Phase 25.3 split 2026-05-01 — Part A (autonomous, this sub-task) restructured `docs/baselines.md` with operator runbook + freshness policy + reproducibility note + all 5 baselines enumerated. Part B (operator action, post-seal) is the one-time live Binance read-only fetch + first-time number population per the runbook; not blocking any further phase. Phase 25 partial seal at Part A is sufficient because the reproducibility *infrastructure* (25.1 format + 25.2 CLI/SnapshotExchange + 25.3 runbook) is autonomous-complete; only the first-numbers population requires operator credentials. Two minor spec deviations (table widening 6→9 columns, placeholder rename) deferred as DEBT-048 (Low) due to autonomous-shipping rewriter conflict.

---

## Phase 1: Project Setup & Basic Infrastructure

**Related Requirements**: NFR-001, NFR-004, NFR-005

### 1.1 Project Structure Setup

- [x] Create `src/` package structure (`src/__init__.py`)
- [x] Configure `pyproject.toml` (dependencies, metadata)
- [x] Create `requirements.txt` (pip compatible)
- [x] Create `.env.example` template
- [x] Update `.gitignore` (.env, __pycache__, .venv, etc.)

### 1.2 Configuration Management Module

- [x] `src/config.py` - Environment variable loading (python-dotenv)
- [x] Required configuration validation logic
- [x] API key configuration structure per exchange

### 1.3 Common Utilities

- [x] `src/logger.py` - Logging setup (file + console)
- [x] `src/models.py` - Common type definitions (dataclass/Pydantic)
- [x] Unit test setup (`tests/__init__.py`, `pytest.ini`)

---

## Phase 2: Exchange Integration Base

**Related Requirements**: FR-016, FR-017, FR-018, FR-019, FR-020, NFR-009

### 2.1 Exchange Abstraction Layer

- [x] `src/exchange/base.py` - BaseExchange abstract class definition
- [x] Common data model definitions (OHLCV, Order, Position, Balance)
- [x] Exchange factory function implementation
- [x] Write unit tests

### 2.2 Binance Integration

- [x] `src/exchange/binance.py` - BinanceExchange class implementation
- [x] Historical OHLCV data query (klines API)
- [x] Current price query
- [x] Balance query
- [x] Order create/cancel/query interface
- [x] Rate limit handling
- [x] Write unit tests (API mocking)

### 2.3 Bybit Integration

- [x] `src/exchange/bybit.py` - BybitExchange class implementation
- [x] Historical OHLCV data query
- [x] Current price query
- [x] Balance query
- [x] Order interface
- [x] Write unit tests

### 2.4 Tapbit Integration — *deferred to later*

---

## Phase 3: Chart Analysis System

**Related Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-005, NFR-007, NFR-008, NFR-010

### 3.1 Analysis Technique Framework

- [x] `src/strategy/base.py` - BaseStrategy abstract class
- [x] `src/strategy/loader.py` - Technique loader (from md/py files)
- [x] Create `strategies/` directory structure
- [x] Define technique metadata schema (name, version, description)
- [x] Write unit tests

### 3.2 Basic Analysis Technique Implementation

- [x] `strategies/sample_prompt.md` - Sample md prompt technique
- [x] `strategies/sample_code.py` - Sample Python code technique
- [x] Technique execution and result return logic
- [x] Write unit tests

### 3.3 Claude Integration

- [x] `src/ai/claude.py` - Claude CLI wrapper (`claude -p "..."`)
- [x] Chart analysis prompt template
- [x] Response parsing logic (trading point extraction)
- [x] Error handling (CLI failure, parsing failure)
- [x] Write unit tests

### 3.4 Analysis Technique Performance Tracking

- [x] `src/strategy/performance.py` - Performance data model
- [x] Performance record storage (`data/performance/`)
- [x] Performance query and aggregation functions
- [x] Write unit tests

### 3.5 Trade History Enhancement

- [x] Enhance `PerformanceRecord` with trade execution fields (quantity, leverage, fees, mode)
- [x] Create `TradeHistory` model for complete trade lifecycle
- [x] Create `TradeHistoryTracker` class with CRUD operations
- [x] Separate storage by mode (`data/trades/{backtest,paper,live}/`)
- [x] Link between `PerformanceRecord` and `TradeHistory`
- [x] Write unit tests

---

## Phase 4: Trading Strategy & Execution

**Related Requirements**: FR-006, FR-007, FR-008, FR-009, FR-010, NFR-007, NFR-008, NFR-012

### 4.1 Trading Strategy Module

- [x] `src/trading/strategy.py` - Trading strategy calculator
- [x] Risk/Reward (R/R) calculation function
- [x] Entry/take-profit/stop-loss calculation function
- [x] Leverage setting logic
- [x] Position size calculation
- [x] Write unit tests

### 4.2 Exchange Testnet Support

- [x] Add `testnet: bool` parameter to `BaseExchange` abstract class
- [x] Add testnet URL configuration to `BinanceExchange` (testnet.binance.vision)
- [x] Add testnet URL configuration to `BybitExchange` (testnet.bybit.com)
- [x] Add testnet API key configuration to Settings (separate from live keys)
- [x] Write unit tests for testnet mode

### 4.3 Paper Trading Engine

**Local Simulation (Complete):**
- [x] `src/trading/paper.py` - PaperTrader class
- [x] Virtual asset (balance) management
- [x] Order simulation (entry, take-profit, stop-loss)
- [x] Trade history recording (`data/trades/paper/`)
- [x] Write unit tests

**Exchange Testnet Integration (Primary):**
- [x] Update PaperTrader to accept exchange instance in testnet mode
- [x] Use exchange testnet for order execution when available
- [x] Fetch real testnet balances from exchange
- [x] Write integration tests with testnet

**Fee Simulation (Fallback):**
- [x] Add fee configuration to PaperTrader (maker/taker fees per exchange)
- [x] Calculate and deduct fees on order execution
- [x] Include fees in P&L calculation
- [x] Write unit tests for fee calculation

### 4.4 Live Trading Engine

- [x] `src/trading/live.py` - LiveTrader class
- [x] Exchange-connected order execution
- [x] User confirmation flow (approval before execution)
- [x] Position monitoring
- [x] Trade history recording (`data/trades/live/`)
- [x] Write unit tests

### 4.5 Asset/PnL Management

- [x] `src/trading/portfolio.py` - Portfolio management
- [x] Asset history storage (`data/portfolio/`)
- [x] PnL calculation (realized/unrealized)
- [x] Separate storage by paper/live mode
- [x] Write unit tests

### 4.6 Trading Strategy Profiles

- [x] `src/trading/profiles.py` - TradingProfile model (risk params, entry/exit rules)
- [x] `src/trading/profile_loader.py` - Load profiles from YAML/JSON files
- [x] Create `trading_profiles/` directory for profile storage
- [x] Sample profiles (conservative, moderate, aggressive, scalping)
- [x] Combine Analysis Technique + Trading Profile for execution
- [x] Update PerformanceTracker to track by technique+profile combination
- [x] Write unit tests

---

## Phase 5: Feedback Loop System

**Related Requirements**: FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, FR-027, NFR-006

### 5.1 Backtesting Engine

- [x] `src/backtest/engine.py` - Backtester class
- [x] Strategy simulation with historical data
- [x] Trade simulation (considering slippage, fees)
- [x] Result storage (JSON/CSV - `data/backtest/`)
- [x] Write unit tests

### 5.2 Performance Analyzer

- [x] `src/backtest/analyzer.py` - PerformanceAnalyzer class
- [x] Win rate calculation
- [x] Total return / annualized return
- [x] Maximum drawdown (MDD) calculation
- [x] Sharpe ratio calculation
- [x] Report generation (md format)
- [x] Write unit tests

### 5.3 Claude-Based Technique Improvement

- [x] `src/ai/improver.py` - StrategyImprover class
- [x] Improvement prompt generation based on performance data
- [x] New technique idea generation prompt
- [x] User idea input → technique generation
- [x] Generated technique storage (`strategies/experimental/`)
- [x] Write unit tests
- [x] **Hypothesis-driven prompt redesign** (FR-033, FR-035): mandatory
  `hypothesis` frontmatter field; new-idea prompt rejects generic
  indicator mashups and steers toward market-structure hypotheses
  (funding/liquidation/OI/basis/stablecoin flow); improvement prompt
  enforces a structural Failure Analysis section and caps added
  conditions to ≤ 2 per revision.

### 5.4 Robustness Validation Gate

**Related Requirements**: FR-034, FR-027, NFR-006

- [x] `src/backtest/validator.py` - `RobustnessGate`, `RobustnessReport`,
  `RobustnessConfig`, `GateResult`, `GateStatus`
- [x] **Out-of-sample (OOS) gate** — chronological 70/30 split; OOS
  Sharpe must retain ≥ 70% of in-sample Sharpe; SKIPPED if either
  split has too few trades.
- [x] **Walk-forward gate** — N consecutive non-overlapping windows;
  ≥ 60% of evaluable windows must be profitable.
- [x] **Regime gate** — classify each entry candle by SMA-relative
  regime (bull/bear/sideways); require non-negative expectancy in
  every regime that has enough trades.
- [x] **Parameter sensitivity gate** — sweep caller-supplied
  `param_grid` via `strategy_factory`; require mean Sharpe across
  grid ≥ 50% of baseline AND ≥ 60% of grid points profitable;
  hard cap on combo count to prevent grid explosion.
- [x] Aggregate `RobustnessReport` with overall verdict (PASSED if no
  FAILED gates), per-gate diagnostics, and human-readable summary.
- [x] Write unit tests (18 tests covering each gate's PASS / FAIL /
  SKIP paths plus aggregate report).

### 5.5 Automated Feedback Loop

**Related Requirements**: FR-026, FR-027, FR-034, CON-003

- [x] `src/feedback/loop.py` - `FeedbackLoop` orchestrator with
  `CandidateRecord`, `LoopStatus`, `FeedbackLoopError`
- [x] Loop execution: improvement → backtesting → **robustness gate** → decision
  via `improve_existing` / `propose_new` / `from_user_idea` / `reevaluate`
- [x] Automatic decision based on `RobustnessReport.overall_passed`
  (FAILED → `DISCARDED`; PASSED → `AWAITING_APPROVAL`)
- [x] Technique adoption flow — `approve(candidate_id, approver)` moves
  the file from `strategies/experimental/` to `strategies/` and
  rewrites frontmatter `status: active`; `reject(...)` keeps the file
  in experimental for further iteration. CON-003 enforced.
- [x] Loop state persistence at `data/feedback/state/<candidate_id>.json`
  with `save_state` / `load_state` / `list_pending` for manual resumption.
- [x] Append-only JSONL audit log at `data/audit/feedback.jsonl`
  (`src/feedback/audit.py`) recording every
  GENERATED / BACKTESTED / GATE_PASSED / GATE_FAILED / APPROVED /
  REJECTED / PROMOTED / DISCARDED / ERRORED event.
- [x] Write unit tests (23 tests across audit and loop covering
  happy paths, gate failure, approve/reject, state persistence,
  error propagation, frontmatter rewrite).

---

## Phase 6: Trading Proposal System

**Related Requirements**: FR-011, FR-012, FR-013, FR-014, FR-015

### 6.1 Proposal Engine

- [x] `src/proposal/engine.py` - `ProposalEngine` class with
  `Proposal`, `ProposalScore`, `ProposalEngineConfig`,
  `ProposalEngineError`.
- [x] Bitcoin trading proposal logic (FR-011) — `propose_bitcoin`
  selects the best technique by historical edge × sample size and
  produces a fully-priced `Proposal` (entry / SL / TP / quantity /
  leverage) via `TradingStrategy.create_position`.
- [x] Altcoin scan and proposal logic (FR-012) — `propose_altcoins`
  scans a list of symbols, ranks by composite score, returns the
  top-K. Per-symbol exchange and strategy errors are logged and
  skipped so one bad pair doesn't kill the scan.
- [x] Proposal score calculation — `composite = confidence × edge ×
  sample_factor` with a confidence-only fallback when the technique
  has no history. All factors surfaced in `ProposalScore` so callers
  can explain the ranking.
- [x] Write unit tests (19 tests covering happy paths, neutral
  signals, missing strategies, exchange errors, ranking,
  best-technique selection, score formula).

### 6.2 User Interaction

- [x] `src/proposal/interaction.py` - User interaction handling
- [x] Proposal display format (CLI)
- [x] Accept/reject input handling
- [x] Proposal history storage (`data/proposals/`)
- [x] Write unit tests

### 6.3 Notification System

- [x] `src/proposal/notification.py` - Notification module
- [x] Console notification
- [x] File-based notification log
- [x] Write unit tests

---

## Phase 7: UI Dashboard

**Related Requirements**: FR-028, FR-029, FR-030, FR-031, FR-032, NFR-003

### 7.1 Streamlit App Basic Structure

- [x] `src/dashboard/app.py` - Main Streamlit app
- [x] App layout setup (sidebar, main area)
- [x] Page navigation configuration
- [x] Common style/theme settings

### 7.2 Analysis Technique Status Page

- [x] `src/dashboard/pages/strategies.py` - Technique status page
- [x] Display registered technique list
- [x] Display technique-specific performance metrics
- [x] Performance trend charts

### 7.3 Trading Status Page

- [x] `src/dashboard/pages/trading.py` - Trading status page
- [x] Display active positions (paper/live)
- [x] Recent trade history
- [x] Asset status and PnL summary
- [x] Equity curve chart

### 7.4 Feedback Loop Status Page

- [x] `src/dashboard/pages/feedback.py` - Feedback loop page
- [x] Experimental technique list
- [x] Backtesting result display
- [x] Loop progress status

### 7.5 Tapbit Integration (Deferred)

- [ ] `src/exchange/tapbit.py` - TapbitExchange class implementation

---

## Phase 8: Production Runtime & Deployment

**Goal**: Wrap the existing components into a long-running headless
service and deploy to Fly.io. Auto-approves proposals based on a
configurable composite-score threshold; surfaces every cycle event
to the dashboard via an append-only activity log.

### 8.1 Trading Engine Runtime

- [x] `src/runtime/activity_log.py` - Append-only JSONL event stream
- [x] `src/runtime/engine.py` - `TradingEngine` orchestrator (scan → auto-decide → execute → monitor loop)
- [x] `src/runtime/engine.py` - `EngineConfig` (cycle interval, auto-approve threshold, symbol list, balance)
- [x] `src/main.py` - Production entrypoint with signal-based graceful shutdown
- [x] `ProposalHistory.attach_trade` - Link a proposal to its executed `TradeHistory.id` at open time
- [x] Write unit tests

### 8.2 Engine Status Dashboard Page

- [x] `src/dashboard/pages/engine.py` - Engine activity page
- [x] Current cycle status + summary cards (last cycle, recent activity)
- [x] Activity log timeline with event-type filter
- [x] Cycle-time histogram
- [x] Write unit tests

### 8.3 Fly.io Deployment

- [x] `Dockerfile` (Claude CLI + Python deps)
- [x] `fly.toml` (multi-process: trader + dashboard, single volume)
- [x] `.dockerignore`
- [x] `docs/deployment.md` (Cloudflare Access setup, secrets list, region pick, rollout flow)

---

## Phase 9: Framework Extensions

**Goal**: Extend the strategy framework to support methodologies
that need richer input than the current single-timeframe contract.
The first driver is multi-timeframe top-down analysis (ICT/SMC and
similar) where one decision needs candles across 4h / 1h / 15m / 5m
plus the current spot price.

### 9.1 Multi-Timeframe Strategy Support

**Background**: Phase 8.1's production rollout exposed that
`chasulang_ict_smc` (and any other multi-TF technique) cannot run
on the current framework. `PromptStrategy.format_prompt` only
substitutes `{symbol}`, `{timeframe}`, `{ohlcv_data}`; templates
asking for `{ohlcv_4h}` / `{ohlcv_1h}` / `{ohlcv_15m}` / `{ohlcv_5m}`
/ `{current_price}` correctly fail-fast (introduced post-deploy)
but the strategy is dormant. This sub-task lifts the
single-timeframe restriction.

**Related Requirements**: FR-001, FR-002, FR-003 (chart analysis
methodology — generalising the existing contract; no new FR
introduced)

- [x] Extend `PromptStrategy.format_prompt` to accept
  `ohlcv_by_timeframe: dict[str, list[OHLCV]]` and
  `current_price: Decimal`; fill `{ohlcv_<timeframe>}` and
  `{current_price}` placeholders alongside the existing three
- [x] Adjust `BaseStrategy.analyze` (or add an opt-in companion
  method) so multi-TF data threads through without breaking
  single-TF strategies — extended the abstract signature with
  keyword-only `ohlcv_by_timeframe` / `current_price` defaulting to
  `None`; added explicit `requires_multi_timeframe: bool = False`
  to `TechniqueInfo` so the engine has an unambiguous opt-in flag
  (existing strategies use `timeframes` as "compatible TFs", so
  list length isn't a safe multi-TF signal)
- [x] Extend `ProposalEngine._propose_for_symbol` to read
  `strategy.info.requires_multi_timeframe` (with `timeframes` as the
  list of required TFs), fetch each via `exchange.get_ohlcv`, and
  pass the dict + derived `current_price` to `strategy.analyze` —
  falls back to the current single-TF path otherwise
- [x] Update `Backtester` to feed multi-TF candles per simulated
  step — delivered by Phase 9.3 (`Backtester.run_multi_timeframe`
  with bisect-based per-TF slicing + per-TF warmup gating, plus
  `Backtester.run_for_strategy` dispatcher and full
  `RobustnessGate` / `FeedbackLoop` integration).
- [x] Verify `chasulang_ict_smc` runs end-to-end on the new
  contract — `tests/test_multi_timeframe_smoke.py` loads the real
  template through `load_strategy` and confirms `format_prompt`
  fills every placeholder with no fail-fast. Live Claude call is
  out of scope for unit tests; manual REPL verification documented
  in the session log
- [x] Write unit tests covering the multi-TF `format_prompt` path,
  the engine's multi-TF fetch flow, and a chasulang-style smoke
  test (7 new tests across loader / engine / smoke)

### 9.2 Baseline Indicator Strategies ✅

**Background**: The LLM-driven techniques (`chasulang_ict_smc`,
`simple_trend_analysis`) need a reference point. Without
deterministic indicator strategies running side-by-side, we can't
tell whether the LLM is contributing real edge or just
confidently agreeing with simple TA. These baselines are also a
useful safety net — even if every Claude call fails (rate limit,
auth, parse), the engine still produces proposals from the
indicator strategies.

**Related Requirements**: FR-001, FR-002, FR-003, FR-004
(extending the strategy library; reusing the existing
``BaseStrategy`` interface — no framework changes here)

- [x] `src/strategy/indicators.py` — shared `rsi`, `sma`,
  `bollinger_bands` math so the strategies don't duplicate the
  arithmetic
- [x] `strategies/rsi.py` — RSI mean-reversion. Long when RSI < 30
  on the close; short when RSI > 70. Operates on whatever
  timeframe the engine passes; a per-timeframe split into
  `rsi_4h.py` / `rsi_15m.py` is deferred to a follow-up sub-task
  once Phase 9.1 (multi-TF) lands
- [x] `strategies/bollinger_bands.py` — Bollinger Band mean
  reversion. Long when close pierces the lower band; short on
  the upper band
- [x] `strategies/ma_crossover.py` — Rename the existing
  `sample_code.py` (already implements SMA crossover) into a
  proper baseline; its `sample_*` framing stops mattering as soon
  as it's a real registered strategy
- [x] Mark all three with `status: experimental` and `symbols: []`
  (universal) so they run on every symbol the engine scans
- [x] Update tests that referenced `sample_code.py` by path to use
  the new filename
- [x] Add `docs/baselines.md` describing each baseline's signal
  logic + the exact `Backtester` invocation an operator runs to
  populate win-rate / Sharpe / MDD numbers (running the actual
  backtest needs historical OHLCV fetching that this sub-task
  does not bundle)
- [x] Write unit tests for the indicators (`rsi`, `sma`,
  `bollinger_bands`) and each strategy's signal logic (clear
  triggers above/below threshold, edge cases at exactly the
  threshold, neutral when no setup)

### 9.3 Multi-Timeframe Backtester

**Background**: Phase 9.1 wired multi-TF through the live
``ProposalEngine`` but the offline path (backtester → robustness gate
→ feedback loop) still operated on a single candle stream. A
multi-TF strategy declaring ``requires_multi_timeframe=True`` reached
``format_prompt`` with ``ohlcv_by_timeframe=None`` → unfilled
placeholders → ``StrategyValidationError``. So ``chasulang_ict_smc``
could not pass through the four robustness gates, blocking promotion
through the feedback loop.

**Related Requirements**: FR-025 (Backtesting Execution), FR-027 /
FR-034 (Robustness Validation Gate) — extending existing backtester +
gate; no new FR introduced.

- [x] ``Backtester.run_multi_timeframe(strategy, ohlcv_by_timeframe,
  symbol, primary_timeframe, profile=None)`` — walks the primary TF,
  slices higher TFs by timestamp at each step using ``bisect`` for
  O(N log M) total work, calls ``strategy.analyze`` with the full
  per-TF dict + ``current_price`` derived from the primary candle's
  close. Reuses every existing helper (``_check_intra_candle_exit`` /
  ``_close_trade`` / ``_apply_slippage`` / ``_build_result``). All
  strategy-irrelevant logic — fees, slippage, sizing, end-of-data
  force-close — driven by the primary TF.
- [x] Module-level ``slice_multi_tf_by_index(primary, by_tf, start,
  end)`` helper used by the run loop and the gate splits. Single-TF
  callers pass ``by_tf=None`` and get a clean passthrough.
- [x] ``Backtester.run_for_strategy`` dispatcher — picks
  ``run`` / ``run_multi_timeframe`` from
  ``strategy.info.requires_multi_timeframe``. Raises
  ``BacktestError`` early when a multi-TF strategy has no dict.
- [x] ``RobustnessGate`` — ``evaluate``, ``_gate_oos``,
  ``_gate_walk_forward``, ``_gate_sensitivity``, and ``_run_subset``
  thread an opt-in ``ohlcv_by_timeframe`` keyword through. The OOS
  and walk-forward splits use ``slice_multi_tf_by_index`` to derive
  aligned per-TF subsets — no future leakage. ``_gate_regime``
  unchanged (operates on baseline trades + primary SMA only).
- [x] ``FeedbackLoop`` — every entry point
  (``improve_existing`` / ``propose_new`` / ``from_user_idea`` /
  ``reevaluate``) accepts ``ohlcv_by_timeframe``; ``_run_cycle``
  calls ``backtester.run_for_strategy`` and forwards the dict to
  ``gate.evaluate``. ``chasulang_ict_smc`` (and any future multi-TF
  technique) can now reach ``AWAITING_APPROVAL`` end-to-end.
- [x] Validation: empty dict / missing primary key / empty primary
  series each raise ``BacktestError`` with a useful message.
- [x] Warmup gates every TF, not just the primary — multi-TF
  top-down strategies are useless without a full higher-TF context
  window.
- [x] Write unit tests — 13 in
  ``tests/test_backtest_multi_timeframe.py`` (slicer, validation,
  no-future-leakage, warmup gating, dispatcher); 1 in
  ``tests/test_backtest_validator.py`` (multi-TF gate routing
  preserves no-leakage); 1 in ``tests/test_feedback_loop.py``
  (``ohlcv_by_timeframe`` reaches both backtester and gate).

### 9.4 Per-Timeframe RSI Baselines

**Background**: Phase 9.2 shipped a single universal-cadence
``rsi_mean_reversion`` baseline that ran on whichever timeframe the
engine passed. The user's original ask included both a 4h RSI
(swing) and a 15m RSI (scalp) baseline as distinct strategies — but
in a single-TF engine cycle a universal entry only covers *one*
cadence at a time, so the swing and scalp behaviours can't fire side
by side. This sub-task adds the explicit-cadence siblings and
renames the universal entry for symmetry.

**Related Requirements**: FR-001 / FR-002 / FR-003 / FR-004 —
extending the strategy library only; reuses Phase 9.2's
``RSIMeanReversionStrategy`` class verbatim.

- [x] ``strategies/rsi_4h.py`` — declares ``timeframes: ["4h"]``,
  imports ``RSIMeanReversionStrategy`` so signal logic equivalence
  is automatic.
- [x] ``strategies/rsi_15m.py`` — same logic, ``timeframes: ["15m"]``.
- [x] Renamed universal ``rsi.py``'s ``TECHNIQUE_INFO["name"]``
  from ``rsi_mean_reversion`` → ``rsi_universal`` for symmetry with
  the new siblings. Module file path / class names unchanged so
  every existing import keeps working.
- [x] Updated ``docs/baselines.md`` to list all five baselines and
  describe what each cadence is good for.
- [x] Wrote unit tests (``tests/test_rsi_variants.py``, 6 tests)
  covering loader pickup, metadata, signal-equivalence on identical
  input, and ``TECHNIQUE_INFO`` dict isolation between variants.

---

## Phase 10: Operational Maturation

**Goal**: Take the system from "feature-complete + deployable" to
"operable in production". Each sub-task closes a specific
operational gap surfaced in prior-phase session logs and risk
lists. No new framework abstractions — production wiring of
existing components plus operator tooling.

### 10.1 Live Trading Wiring

**Background**: Phase 8.3 deployed paper-only — `src/main.py::build_exchange`
always returns a testnet exchange even when `Settings.trading_mode == "live"`.
The Phase 8 cross-check explicitly carried this as a deliberate deferral.

**Related Requirements**: FR-009, FR-010, NFR-012.

- [x] `src/main.py::build_exchange` switches on `Settings.trading_mode`
  — testnet for paper (with either live or testnet keys accepted),
  mainnet for live (requires live keys; raises a friendly error
  otherwise).
- [x] `src/main.py::build_trader` factory dispatches on
  `Settings.trading_mode`: returns `PaperTrader` for paper,
  `LiveTrader` for live. Engine code path is now mode-agnostic
  (consumes the new `Trader` protocol).
- [x] Introduced `src/trading/base.py::Trader` Protocol —
  `open_position` / `close_position` async, `get_open_trades` /
  `check_exit_conditions` sync. Both `PaperTrader` and `LiveTrader`
  satisfy it; `TradingEngine` now takes `trader: Trader` instead of
  `paper_trader: PaperTrader`.
- [x] `LiveTrader.close_position` signature aligned with PaperTrader's
  (`(trade_id, exit_price, reason="manual")`); auto-exit reasons
  (`stop_loss` / `take_profit`) skip the confirmation callback —
  the user pre-authorized those bounds at open time.
- [x] Wired live confirmation callback to a `_engine_auto_confirmation`
  shim that auto-approves (the engine's threshold gate has already
  authorized the proposal). Interactive sessions can still swap in
  `default_confirmation` for stdin prompts per NFR-012.
- [x] Updated `docs/deployment.md` with a 9-step live-mode checklist
  covering key rotation, threshold tuning, sizing, notifications,
  start-small advice, confirmation policy, exit policy, monitoring,
  and rollback.
- [x] Tests: 11 new dispatch tests in `tests/test_main_dispatch.py`;
  refactored `tests/test_runtime_engine.py` to mock the new `Trader`
  protocol; converted PaperTrader tests to async (open/close
  methods are now async). Existing live-trader tests adjusted to
  the new signature.

### 10.2 EngineConfig Env Override

**Background**: `EngineConfig` (cycle interval, auto-approve threshold,
symbol list, balance) is built from literals in `src/main.py`. Changing
any value requires a code edit + redeploy — bad operability. Phase 8
cross-check tracked this as a documented small follow-up.

**Related Requirements**: NFR-004 (env-driven config); operational concern.

- [x] Add `engine_*` fields to `Settings` (`engine_cycle_interval`,
  `engine_auto_approve_threshold`, `engine_symbols`,
  `engine_balance`).
- [x] `src/main.py` builds `EngineConfig` from `Settings`, not from
  literals.
- [x] `.env.example` documents each new env var with sensible
  defaults that match today's hardcoded values (so existing
  deployments don't change behaviour without an explicit env
  setting).
- [x] `docs/deployment.md` lists the new env vars in the Fly secrets
  / config section.
- [x] Tests: settings-load tests for the new fields; smoke that env
  override propagates through to `EngineConfig`.

### 10.3 Baseline Reference Numbers

**Background**: `docs/baselines.md` shows TBD for win-rate / Sharpe / MDD
on every baseline. Without numbers, "is the LLM beating the baselines?"
isn't answerable. Phase 9.3's multi-TF backtester is in place; this
sub-task is purely operational glue: fetch historical OHLCV, run the
existing `Backtester`, write the table.

**Related Requirements**: FR-025 (consumed); operator tooling.

- [x] `scripts/backtest_baselines.py` — operator script (not a service):
  fetch Binance historical OHLCV (3 months × 1h for swing baselines;
  1 month × 15m for `rsi_15m`), run `Backtester.run` per baseline,
  run `PerformanceAnalyzer`, persist results under
  `data/backtest/baselines/<strategy>/`. Idempotent — re-runnable
  to refresh the numbers.
- [x] Update `docs/baselines.md` reference-numbers table from the
  latest run.
- [x] No automated tests required (one-off operator script); a smoke
  test that mocks the exchange and verifies the script writes the
  expected output files is sufficient.

### 10.4 Log Retention Policy

**Background**: `data/audit/feedback.jsonl`, `data/runtime/activity.jsonl`,
and `data/proposals/` all grow unbounded. Phase 5 / 7 / 8 risk lists
all flagged this. Today's volumes are tiny but post-deployment the
files balloon — a few MB/day at current scan cadence.

**Related Requirements**: NFR-008 (mode-separated storage extends to
retention); operational concern.

- [x] Add a small `JsonlRotator` utility that wraps an append-only
  JSONL file with **time-based monthly rotation**: writes go to
  `<base>.YYYY-MM.jsonl`; reads merge across the active month +
  the most recent N archives in timestamp order.
- [x] `AuditLog` and `ActivityLog` use the rotator. ProposalHistory
  (which uses one file per proposal) gets its own age-based purge:
  records older than the retention window move to
  `data/proposals/archive/<YYYY-MM>/`.
- [x] Retention default: 12 months active + archives. Configurable
  via `Settings.log_retention_months`.
- [x] Tests: rotation triggers at month boundary; reads see merged
  history; archives don't affect new writes; corrupt archive lines
  don't kill the read.

### 10.5 Volume-Aware Default Paths

**Background**: Cycle 1's runtime verification (see
`docs/sessions/2026-04-28-priorities-fly-zero-trades-diagnosis.md`,
Runtime Verification Addendum) confirmed that `fly.toml` mounts the
persistent volume at `/data` but the Dockerfile sets `WORKDIR=/app`.
`src/runtime/activity_log.py:34` defaults `DEFAULT_ACTIVITY_PATH` to
`Path("data/runtime/activity.jsonl")` — a relative path that resolves
to `/app/data/runtime/activity.jsonl` (ephemeral container root), not
`/data/runtime/activity.jsonl` (persistent volume). Same defect in
`src/feedback/audit.py`, `src/feedback/loop.py`,
`src/proposal/interaction.py`, `src/proposal/notification.py`, and
`src/trading/portfolio.py`. `PerformanceTracker` and
`TradeHistoryTracker` already thread `Settings.data_dir` correctly
and are the pattern to copy. Impact: every Fly machine recycle
(auto-deploy, OOM, host migration) wipes the activity log, audit
log, proposal history, and portfolio history — producing dashboard
timeline holes and breaking the audit trail Phase 5.5 was designed
to provide.

**Related Requirements**: NFR-008 (mode-separated storage extends to
retention); operational concern — no new FR introduced.

- [x] Route `src/runtime/activity_log.py`'s default activity path
  through `Settings.data_dir` (replicate the
  `PerformanceTracker.__init__` pattern: read `data_dir` from
  settings, build the JSONL path under it).
- [x] Same fix in `src/feedback/audit.py` (`data/audit/feedback.jsonl`).
- [x] Same fix in `src/feedback/loop.py` (loop state directory
  `data/feedback/state/`).
- [x] Same fix in `src/proposal/interaction.py` (`data/proposals/`
  history directory).
- [x] Same fix in `src/proposal/notification.py` (file-notifier
  JSONL path).
- [x] Same fix in `src/trading/portfolio.py` (`data/portfolio/`
  history directory).
- [x] Tests: each component's existing test file gains a "respects
  `data_dir` override" case using `tmp_path` — assert the default
  path is rooted under the configured `data_dir`, not the literal
  string `data/...`.

### 10.6 Multi-Technique Per-Symbol Scan

**Background**: Cycle 1's runtime verification (see
`docs/sessions/2026-04-28-priorities-fly-zero-trades-diagnosis.md`,
Runtime Verification Addendum) showed that
`ProposalEngine._select_best_technique` (`src/proposal/engine.py:391`)
returns exactly one strategy per symbol per cycle, with an
alphabetic-by-name tiebreaker in cold-start. On the live Fly
deployment this means only `bollinger_band_reversion` ever runs —
every other strategy (`rsi`, `ma_crossover`, `chasulang_ict_smc`,
`simple_trend_analysis`, `sample_prompt`) is loaded but never
analyses a candle. Bollinger reversion has a low-base-rate signal
(price piercing the bands), so most cycles produce zero proposals
and the threshold gate never fires. The Phase 9.2 stated goal of
"side-by-side LLM-vs-deterministic comparison + degraded-mode safety
net" is structurally broken by this single-selection design. Note
that Phase 9.4's `rsi_4h` / `rsi_15m` strategies are not on the
deployed Fly image today; once 10.6 ships, the user will manually
redeploy so those siblings actually fire alongside the existing
baselines (out of scope for this sub-task).

**Related Requirements**: FR-005 (Analysis Technique Performance
Tracking — multi-strategy diversification feeds the tracker), FR-012
(Altcoin Trading Proposal — ranking semantics extend to multiple
proposals per symbol).

- [x] Change `ProposalEngine._propose_for_symbol` (or add a sibling)
  so it iterates over **every** applicable technique for the symbol,
  generating one candidate `Proposal` per `(symbol, technique)` pair.
  Neutral signals are still filtered out as today.
- [x] **Per-symbol dedup (trading-correctness — required)**: each
  public entry point (`propose_bitcoin` / `propose_altcoins`) must
  guarantee **at most one proposal per symbol** in its return value.
  When multiple non-neutral techniques produce candidates on the same
  symbol — including the long-vs-short conflict case — the
  highest-composite candidate wins; the others are dropped. Group key
  is the symbol alone, never `(symbol, side)`. Without this guard the
  runtime engine would call `trader.open_position` once per
  technique per symbol per cycle, opening N positions on the same
  pair at N× the intended `risk_percent` — a real-money defect.
- [x] `propose_altcoins` aggregation order: **dedup-by-symbol first,
  then top-K**. With ≤ 1 candidate per symbol and `top_k=3`, the
  result is the 3 best symbols (preserves FR-012's diversification
  semantic). Sorting first then deduping would change the K-th
  selection — don't.
- [x] `propose_bitcoin` returns the single highest-scoring candidate
  from the BTC set. Existing single-proposal contract preserved.
- [x] Add a `ProposalEngineConfig` flag (e.g.
  `multi_technique_per_symbol: bool = True`) for backwards-compatible
  opt-out. Default behaviour is multi-technique. When `False`, the
  legacy `_select_best_technique` path is used unchanged. Decide
  whether to keep `_select_best_technique` as live code (gated by the
  flag) or retire it; document the choice in the session log.
- [x] Tests: new `tests/test_proposal_engine_multi_technique.py`
  covering —
  - multiple non-neutral techniques each produce one proposal on the
    same symbol → only the highest-composite one is returned (long+long
    case);
  - one long candidate and one short candidate on the same symbol with
    different composites → only the highest-composite one is returned
    (long+short conflict case — explicit, not implicit);
  - neutral techniques are filtered out before the dedup;
  - cold-start techniques (no history, composite = `confidence × 0.5`)
    don't crowd out proven techniques (existing scoring semantic
    preserved);
  - top-K across the combined cross-symbol set after per-symbol dedup;
  - single-applicable-technique still works (back-compat smoke);
  - `multi_technique_per_symbol=False` produces identical output to
    the pre-10.6 behaviour (legacy-path smoke).

---

## Phase 11: Operational Hardening + Observability

**Goal**: Take the system from "operationally complete" to
"observable and clean". Phase 10 wired live mode and closed the
audit-trail / multi-technique / config gaps; Phase 11 hardens the
codebase (lint/type sweep), reduces operational drift (OHLCV cache,
`purge_old` wiring), and adds a paging backend for unattended live
operation. No new framework abstractions — production hygiene + one
new notifier.

### 11.1 Pre-Existing Lint/Type Sweep

**Background**: Phase 10's cycles surfaced 18 pre-existing ruff
errors and 24 mypy errors across `src/ai/claude.py`,
`src/strategy/loader.py`, `src/feedback/loop.py`, `src/trading/live.py`,
`src/ai/improver.py`, `src/exchange/binance.py`, `src/trading/paper.py`,
`src/trading/profile_loader.py`, `src/backtest/analyzer.py`, plus the
`pyproject.toml` ruff-deprecation warning and missing `types-PyYAML`.
None new since the project's start; they accumulate friction on every
cycle that touches those modules. Tracked as DEBT-001 (Medium).

**Related Requirements**: NFR-001 (code quality); operational concern
— no new FR introduced.

- [x] Fix ruff errors in `src/ai/claude.py`, `src/strategy/loader.py`,
  `src/feedback/loop.py` (B904 raise-from), test files (F841 / F401
  unused), and any UP035 typing imports.
- [x] Fix mypy errors in `src/trading/live.py` (untyped `Order`
  returns at lines 235 / 244 / 252 / 438 / 445), `src/ai/improver.py:280`
  (arg-type mismatch), `src/trading/paper.py`,
  `src/trading/profile_loader.py`, `src/backtest/analyzer.py`.
- [x] Move `pyproject.toml` ruff config from deprecated top-level
  `select` / `ignore` / `isort` keys to `[tool.ruff.lint]` section.
- [x] Add `types-PyYAML` to dev extras in `pyproject.toml`.
- [x] Document the clean-baseline contract: `ruff check src tests &&
  mypy src` should pass clean. Add a small `scripts/lint.sh` (or
  CONTRIBUTING note) so future cycles can gate on it.
- [x] Tests: existing test suite must remain green; this is a
  refactor, not a feature — no new tests.

### 11.2 OHLCV Cache for Multi-Technique Scan

**Background**: Phase 10.6's `_propose_all_for_symbol` re-fetches
OHLCV per technique → N×M `get_ohlcv` calls per symbol per cycle
(vs 1×M previously). Quant flagged temporal-drift risk (techniques
seeing different candle T's mid-cycle) and rate-limit pressure at
scale. Tracked as DEBT-002 (Low).

**Related Requirements**: FR-005 (consumed); operational concern —
no new FR introduced.

- [x] Add a per-call OHLCV cache keyed by `(symbol, timeframe)`
  threaded through `_propose_all_for_symbol` and
  `_build_proposal_for_strategy`. The simplest shape is a
  `dict[(str, str), list[OHLCV]]` instantiated at the public entry
  point.
- [x] Cache MUST be per-call, not per-engine — strategy decisions
  need fresh data each cycle. Lifetime is exactly one
  `propose_bitcoin` / `propose_altcoins` invocation.
- [x] Multi-TF strategies: keying by `(symbol, tf)` means each
  timeframe is fetched at most once per call regardless of how many
  strategies request it.
- [x] Tests: extend `tests/test_proposal_engine_multi_technique.py`
  with a "fetch is called once per (symbol, tf) even when N
  techniques request it" test (mock `exchange.get_ohlcv`, assert
  call count).

### 11.3 Notification Push Backend

**Background**: Phase 10.1 carried this forward in its session log.
Live mode runs unattended; current notifier backends are Console +
File which page nobody. A push-style backend (Slack via webhook —
simplest setup, no OAuth, easy operator-side mute/redirect) lets the
operator know when a real-money trade fires. Telegram / email left
as future sub-tasks.

**Related Requirements**: FR-015 (Notification System — extending
existing); NFR-012 (live trading awareness).

- [x] `src/proposal/notification.py` — add `SlackNotifier` class
  implementing the existing `Notifier` protocol. Reads
  `SLACK_WEBHOOK_URL` from `Settings` (add field; optional —
  notifier is silent / disabled when not set).
- [x] Notification text: 1-line summary
  (`{symbol} {side} score={composite:.2f} entry={price}`) + a
  thread-style detail block (rationale / SL / TP) in Slack
  code-fence formatting.
- [x] `src/main.py::build_engine` adds `SlackNotifier()` to the
  dispatcher's notifier list when `Settings.slack_webhook_url` is
  set.
- [x] `.env.example` and `docs/deployment.md` document
  `SLACK_WEBHOOK_URL` (operator setup: incoming-webhook creation
  steps).
- [x] Tests: mock the webhook POST; verify (a) notifier is created
  and dispatches when env set, (b) notifier is silent / not
  registered when env unset, (c) message format matches spec, (d)
  HTTP failure does not crash the dispatch path (existing
  per-channel failure isolation contract from Phase 6.3 preserved).

### 11.4 ProposalHistory.purge_old Wiring

**Background**: Phase 10.4 implemented
`ProposalHistory.purge_old(now, retention_months)` but left it
unwired — the method ships and is tested, but no runtime path
invokes it. Long-running Fly deploys will accumulate proposal
records indefinitely until something calls it. The 10.4 session log
explicitly deferred the wiring to a separate sub-task.

**Related Requirements**: NFR-008 (mode-separated storage extends
to retention); operational concern — no new FR introduced.

- [x] `src/main.py::run` (or equivalent startup hook) calls
  `ProposalHistory(...).purge_old(retention_months=settings.log_retention_months)`
  once after `build_engine` returns and before `engine.run_forever()`
  is awaited. Log the count of records purged at INFO level.
- [x] New `src/tools/__init__.py` + `src/tools/purge_proposals.py`
  operator CLI: constructs `ProposalHistory()` from `Settings`,
  calls `purge_old(...)`, prints a summary line. Invocable as
  `python -m src.tools.purge_proposals`.
- [x] `docs/deployment.md` documents the CLI (operator manual
  lever) and notes that the startup hook handles always-on cases.
- [x] Tests: smoke test for the startup hook (`build_engine`
  followed by purge call doesn't crash; mock `ProposalHistory`); CLI
  test (mock `ProposalHistory.purge_old`, assert it was called with
  the retention value from `Settings`).

---

## Phase 12: Risk Hardening + Reliability

**Goal**: Phase 11 closed the operational hardening agenda (lint,
cache, push notifier, purge wiring). Phase 12 closes two real-money
risks surfaced by live Fly monitoring (cross-cycle position
accumulation; LLM-strategy timeouts that silently drop proposals),
batches the residual lint/type debt that Phase 11.1 deferred to
other modules, and adds a second push backend so live mode isn't
single-channel.

### 12.1 Cross-Cycle Position Cap

**Background**: The Fly redeploy on 2026-04-28 produced two BNB short
positions in 14 minutes (05:40:51 and 05:54:30) — the second cycle's
proposal opened a second BNB position because Phase 10.6's per-cycle
dedup only operates *within* a cycle, not *across* cycles. The
`Trader` protocol has no `if symbol in self._open_positions` guard.
Quant flagged this risk during Phase 10.6 design ("Option (b) cap at
TradingEngine — defensible belt-and-braces, follow-up sub-task") but
it was deferred. With the runtime now actively trading, deferring it
any further is a real-money concern: 4× cycle = 4× position
concentration on a single pair, 4× the intended `risk_percent`. This
is independent of Phase 10.6's per-cycle dedup which stays in place.

**Related Requirements**: FR-006, FR-007, FR-008 (Trading Strategy —
risk/leverage/sizing — extending the existing contract; no new FR
introduced).

- [x] Add `max_open_positions_per_symbol: int = 1` field to
  `EngineConfig` — env-overridable as
  `ENGINE_MAX_OPEN_POSITIONS_PER_SYMBOL` via `Settings.engine_*` (10.2
  pattern).
- [x] In `TradingEngine._handle_proposal` (or earlier in `_scan`
  filtering), check `trader.get_open_trades()` for any open position
  on the proposal's symbol; if count ≥ cap, log `proposal_rejected`
  with reason "symbol cap N reached" and skip execution.
- [x] Hard cap at the engine layer, NOT at the proposal-engine layer
  — proposal generation continues unchanged; cap operates at the
  execution gate. Rationale: the proposal still gets recorded for
  audit; only execution is blocked.
- [x] Activity log records the cap rejection so the dashboard
  timeline surfaces it (re-uses the existing `proposal_rejected`
  event shape).
- [x] Tests: extend `tests/test_runtime_engine.py` — proposal
  accepted but symbol already has cap-reached open positions →
  execution is skipped, activity log records the cap rejection, no
  `trader.open_position` call.

### 12.2 Residual mypy Sweep

**Background**: Phase 11.1 fixed the in-scope mypy errors (12 → 0)
but logged 4 follow-up clusters as DEBT-005..008. With the type-clean
baseline established, these can be tackled as a single mini-sweep
cycle. DEBT-006 in particular needs quant review before fix lands —
the factory shape drift looks like genuine API mismatch, not typing
hygiene.

**Related Requirements**: NFR-001 (code quality); operational concern
— no new FR introduced.

- [x] DEBT-005: ccxt typing in `src/exchange/binance.py` (11
  errors). Hand-rolled Protocol covering the 8+ ccxt methods used,
  or runtime `cast(Any, ...)` if Protocol is too noisy — pick the
  lower-friction path.
- [x] DEBT-006: `src/exchange/factory.py` shape drift (3 errors).
  Genuine API mismatch — quant review before fix lands.
- [x] DEBT-007: Dashboard Streamlit type errors (~13 errors across
  `src/dashboard/{theme,app,pages/trading,pages/engine}.py`). Local
  annotations / casts.
- [x] DEBT-008: `src/main.py:271` lambda annotation (1 error).
  One-line fix.
- [x] After: `mypy src` should be fully clean. Add a CI/local check
  (pairs naturally with the DEBT-009 `scripts/lint.sh --fix` safety
  fix if the operator wants both in one PR).
- [x] Tests: existing test suite must remain green; no new tests
  (refactor, not a feature).

### 12.3 LLM Strategy Timeout Handling

**Background**: Live Fly monitoring on 2026-04-28 showed
`chasulang_ict_smc` failing twice within 12 minutes with `Claude CLI
timed out after 120.0 seconds`. The error is logged but the strategy
silently drops out of that cycle's multi-technique scan — no
fallback, no retry, no operational visibility beyond the log line.
As LLM strategies multiply this becomes a reliability concern.

**Related Requirements**: FR-022 (Technique Improvement Suggestion —
extending existing Claude CLI integration); operational concern.

- [x] Add `claude_cli_timeout_seconds: int = Field(default=120)` to
  `Settings` so operators can tune without redeploy.
- [x] Add `claude_cli_max_retries: int = Field(default=1)` — on
  timeout, retry once with a longer timeout (e.g. 1.5×). After max
  retries, fall back to a neutral signal cleanly so the strategy
  doesn't kill the cycle.
- [x] `src/ai/claude.py` — wrap the existing `subprocess.run(...,
  timeout=...)` call with the new retry logic. Log each attempt
  explicitly.
- [x] Add an `ActivityEventType.LLM_TIMEOUT` event so the dashboard
  can show LLM reliability over time.
- [x] Tests: mock subprocess to time out N times; verify retry
  count, eventual neutral fallback, activity event recorded.

### 12.4 Telegram Notification Backend

**Background**: Phase 11.3 shipped Slack-via-webhook. Phase 10.1's
"notification redundancy for live mode" follow-up listed Slack OR
Telegram OR email as candidates — Slack was the first ship, Telegram
is the second logical addition (also webhook-style, also no OAuth
dance, easier setup than email infrastructure).

**Related Requirements**: FR-015 (Proposal Notification — extending
existing); NFR-012 (live trading awareness redundancy).

- [x] `src/proposal/notification.py` — `TelegramNotifier` class
  implementing the existing `Notifier` protocol. Reads
  `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` from `Settings` (both
  required for activation; if either missing, notifier is silent /
  not registered).
- [x] Telegram Bot API URL:
  `https://api.telegram.org/bot<TOKEN>/sendMessage` with
  form-encoded `chat_id` + `text` (Markdown). Use stdlib
  `urllib.request.urlopen` + `asyncio.to_thread` (matches Slack's
  stdlib pattern from Phase 11.3 — zero new dep).
- [x] Message format: same proposal summary line + code-fenced
  detail block as Slack — easier to maintain a single payload spec.
- [x] `src/main.py::build_engine` adds `TelegramNotifier(...)` to
  the dispatcher's notifier list when both env vars set; logs
  presence not values.
- [x] `.env.example` and `docs/deployment.md` document
  `TELEGRAM_BOT_TOKEN` (secret) + `TELEGRAM_CHAT_ID`.
- [x] Tests: mock the HTTP POST; verify (a) created when both env
  set, (b) silent when either missing, (c) message format matches
  spec, (d) HTTP 5xx doesn't crash dispatch (existing per-channel
  failure-isolation contract from Phase 6.3 preserved).

---

## Phase 13: Cleanup + Operational Polish

**Goal**: Phase 13 closes the carry-forward TECH-DEBT items
(DEBT-003, 004, 009, 010, 011), extends the engine env-override
surface to the remaining `EngineConfig` fields, generalises the
exchange OHLCV fetch with a `since` parameter (unblocking 10.3's
pagination reach-around), and adds an email notification backend for
redundancy. Pure cleanup + small ops improvements — no new
architectural directions.

### 13.1 Cleanup Batch (DEBT-009/010/011)

**Background**: Three small cleanup items accumulated across Phases
11 and 12. DEBT-009 (Low): `scripts/lint.sh` uses `ruff check src
tests --fix` which silently rewrites source on lintable regressions
— unsafe for CI gates. DEBT-010 (Low): Phase 12.1's cross-cycle
position cap correctly blocks the long+short same-symbol case (cap
counts trades regardless of side, preventing synthetic hedge), but
the test suite doesn't explicitly cover that path. DEBT-011 (Low):
Phase 12.2 left `dict[str, object]` returns in `build_summary_metrics`
(`src/dashboard/pages/{trading,engine}.py`) forcing
`cast(int|float|str, ...)` at consumer sites — a `TypedDict` rewrite
drops the casts cleanly.

**Related Requirements**: NFR-001 (code quality + test coverage);
operational concern — no new FR introduced.

- [x] DEBT-009: split `scripts/lint.sh` into `scripts/lint.sh`
  (`ruff check src tests && mypy src` — no `--fix`; for CI /
  pre-commit) and `scripts/lint-fix.sh` (`ruff check src tests --fix
  && mypy src` — for dev convenience). Both executable. Update any
  docs that reference `scripts/lint.sh` to clarify which to use.
- [x] DEBT-010: add `test_cap_blocks_opposite_side_same_symbol` to
  `tests/test_runtime_engine.py` — existing trade is long, new
  proposal is short same-symbol, cap=1; verify execution skipped +
  cap-rejection event recorded.
- [x] DEBT-011: define a `SummaryMetrics` `TypedDict` (in
  `src/dashboard/pages/{trading,engine}.py` or a shared
  `src/dashboard/_types.py`); update `build_summary_metrics` returns
  + consumer call sites; drop the `cast()` calls.
- [x] Tests: 13.1 only NEEDS the DEBT-010 test added; existing tests
  must remain green for the lint-script split + dashboard TypedDict
  refactor (refactor only, no behavioural change).

### 13.2 EngineConfig Remaining-Fields Env Override

**Background**: Phase 10.2 wired 4 `EngineConfig` fields
(`cycle_interval`, `auto_approve_threshold`, `symbols`, `balance`)
through `Settings`. The remaining 4 fields are still hardcoded in
`EngineConfig` defaults: `monitor_interval_seconds`,
`bitcoin_symbol`, `altcoin_top_k`, `actor`. Tracked as DEBT-003
(Low). Now that real operators run the system on Fly, the
rare-but-real cases for tuning these without a redeploy justify the
small extension.

**Related Requirements**: NFR-004 (env-driven config); operational
concern — no new FR introduced.

- [x] Add 4 fields to `Settings` in `src/config.py`:
  `engine_monitor_interval: int = Field(default=60, ge=10)` (env
  `ENGINE_MONITOR_INTERVAL`), `engine_bitcoin_symbol: str =
  Field(default="BTC/USDT")` (env `ENGINE_BITCOIN_SYMBOL`),
  `engine_altcoin_top_k: int = Field(default=3, ge=1)` (env
  `ENGINE_ALTCOIN_TOP_K`), `engine_actor: str =
  Field(default="auto-engine")` (env `ENGINE_ACTOR`).
- [x] `src/main.py::build_engine` passes all 4 through to
  `EngineConfig(...)` (10.2 explicit-config-wins back-compat
  preserved).
- [x] Defaults bytewise-equal to the pre-13.2 hardcoded values so
  existing deployments are unchanged without an env setting.
- [x] `.env.example` and `docs/deployment.md` document the 4 new env
  vars.
- [x] Tests: extend `tests/test_config.py::TestEngineSettings` with
  default-value + env-override tests for each (4 new tests); extend
  `tests/test_main_dispatch.py` with one smoke test verifying env
  propagates to `EngineConfig`.

### 13.3 BaseExchange.get_ohlcv with `since` Parameter

**Background**: `scripts/backtest_baselines.py` (Phase 10.3) needs
`since` to paginate past the 1500-candle ccxt cap, but
`BaseExchange.get_ohlcv` doesn't expose it — the script reaches into
`BinanceExchange._client` to access ccxt's `since` arg directly.
Tracked as DEBT-004 (Low). Now that there's a real consumer, the
abstraction should grow the parameter so the reach-around can go
away.

**Related Requirements**: FR-020 (Historical Chart Data Query —
extending the existing contract; no new FR introduced).

- [x] Extend `BaseExchange.get_ohlcv` abstract signature to include
  `since: int | None = None` (timestamp in ms). Update docstring.
- [x] Update `BinanceExchange.get_ohlcv` and `BybitExchange.get_ohlcv`
  to forward `since` to ccxt. Default behaviour (no `since`)
  unchanged.
- [x] Update `scripts/backtest_baselines.py` to use the public API
  instead of the `_client` reach-around. Drop the inline comment
  about the reach-around.
- [x] Tests: add `since`-parameter tests for both Binance and Bybit
  (mock ccxt, verify `since` is forwarded); existing OHLCV tests
  must remain green.

### 13.4 Email Notification Backend

**Background**: Phase 11.3 shipped Slack and Phase 12.4 shipped
Telegram. Phase 10.1's "notification redundancy for live mode"
follow-up listed Slack/Telegram/email as candidates — email is the
third logical addition with a different failure mode (SMTP can fail
when chat APIs are up, and vice versa).

**Related Requirements**: FR-015 (Proposal Notification — extending
existing); NFR-012 (live trading awareness redundancy).

- [x] `src/proposal/notification.py` — `EmailNotifier` class
  implementing the existing `Notifier` protocol. Reads SMTP config
  from `Settings`: `email_smtp_host`, `email_smtp_port`,
  `email_smtp_user`, `email_smtp_password`, `email_from`,
  `email_to`. All 6 required for activation; partial config silent
  (matches Slack/Telegram pattern).
- [x] Use stdlib `smtplib.SMTP` + `email.message.EmailMessage` wrapped
  in `asyncio.to_thread` (zero new dep — matches Slack/Telegram). Subject:
  `"Crypto Master: {symbol} {side} score={c:.2f}"`; body: same
  Markdown content as Telegram (works in any client; plain-text
  fallback included).
- [x] STARTTLS by default; SMTP_SSL as alternative (config option).
  Set socket timeout to 10s. `__repr__` masks password — never log
  credentials.
- [x] `src/main.py::build_engine` appends `EmailNotifier(...)` to the
  dispatcher's notifier list when ALL 6 fields set; logs presence
  not values.
- [x] `.env.example` and `docs/deployment.md` document the 6 SMTP
  env vars.
- [x] Tests: mock `smtplib.SMTP`; verify (a) created when all 6 env
  set, (b) silent when any missing, (c) message format (subject +
  body) matches spec, (d) STARTTLS handshake called, (e) SMTP error
  doesn't crash dispatch (existing per-channel failure-isolation
  contract from Phase 6.3 preserved).

---

## Phase 14: Production Reliability

**Goal**: Phase 14 closes two prod-observed and tracked items: the
persistent chasulang Claude CLI timeouts that Phase 12.3's retry
didn't eliminate, and the SMTP_SSL alternative DEBT-012 that emerged
in 13.4. Compact two-sub-task phase — production reliability polish,
no new framework abstractions.

### 14.1 Chasulang Timeout Mitigation

**Background**: Phase 12.3 added Claude CLI retry-with-1.5×-backoff
(default `max_retries=1`, base timeout 120s → 180s on retry). Live
Fly logs after the Phase 12 redeploy still show `chasulang_ict_smc`
timing out after 120s on every BTC scan cycle (~once per 5 minutes).
Two probable causes worth investigating: (a) the chasulang prompt
template is too long for 120s on the Fly machine's shared CPU /
1 GB RAM, and (b) the retry is firing but both attempts time out —
meaning even 180s isn't enough. Operator tuning of
`CLAUDE_CLI_TIMEOUT_SECONDS` / `CLAUDE_CLI_MAX_RETRIES` only delays
the actual problem if the prompt is the issue; the right fix
combines a per-strategy timeout override (so chasulang can run on a
longer leash without slowing baselines like `rsi_4h.analyze` that
don't need 120s) with observability on the retry path.

**Related Requirements**: FR-022 (Claude AI Integration — extending
the existing contract; no new FR introduced); NFR-001 (operational
reliability).

- [x] Read recent Fly logs (`fly logs -a crypto-master`) and grep
  for `chasulang_ict_smc` + `LLM_TIMEOUT` to confirm actual
  frequency and whether the retry path is being hit (look for the
  Phase 12.3 `retrying with timeout=180s` warning).
- [x] Add per-strategy timeout override to `BaseStrategy.info`
  (e.g. `claude_timeout_seconds: int | None = None` on
  `TechniqueInfo`). When set, `PromptStrategy` passes that to
  `ClaudeCLI` instead of the `Settings.claude_cli_timeout_seconds`
  default; `None` (existing strategies unaffected) falls back to
  Settings.
- [x] Update `strategies/chasulang_ict_smc.md` frontmatter with
  `claude_timeout_seconds: 240` (240s × 1.5 = 360s total with one
  retry).
- [x] Extend `LLM_TIMEOUT` activity event details with
  `attempt_number` (1, 2, ...) + `final_timeout_seconds` so the
  dashboard / operator can verify retry path execution.
- [x] Tests: `BaseStrategy.info` gains a new optional field —
  default `None` keeps existing strategies unaffected; per-strategy
  override path tested with mocked subprocess; `LLM_TIMEOUT` event
  payload tests verify `attempt_number` + `final_timeout_seconds`
  fields.

### 14.2 SMTP_SSL Alternative (DEBT-012)

**Background**: Phase 13.4's `EmailNotifier` ships STARTTLS-only
(`smtplib.SMTP` + `starttls()`). Some SMTP providers (Yahoo Mail,
AT&T, ProtonMail) only offer SMTP-over-SSL on port 465 with no
STARTTLS option. Tracked as DEBT-012 (Low). Now that Phase 13's
notifier shipped, the gap can close cleanly.

**Related Requirements**: FR-015 (Proposal Notification — extending
existing); operational concern.

- [x] Add `email_use_ssl: bool = Field(default=False)` to
  `Settings` in `src/config.py`. Env `EMAIL_USE_SSL=true` activates
  SMTP_SSL on port 465 instead of SMTP+STARTTLS on port 587.
- [x] `src/proposal/notification.py::EmailNotifier` constructor
  accepts a `use_ssl: bool` flag. When True: `smtplib.SMTP_SSL(host,
  port, timeout=...)` with NO `starttls()` call (already encrypted).
  When False (default): existing `smtplib.SMTP` + `starttls()`
  path.
- [x] `src/main.py::build_engine` reads `settings.email_use_ssl`
  and forwards to `EmailNotifier(...)`.
- [x] `.env.example` documents the new env var with provider-specific
  guidance ("Set `EMAIL_USE_SSL=true` and `EMAIL_SMTP_PORT=465` for
  Yahoo / AT&T / ProtonMail").
- [x] `docs/deployment.md` extends the Email subsection with an
  SMTP_SSL note.
- [x] Tests: extend `tests/test_proposal_notification.py` with two
  tests — `test_email_notifier_uses_smtp_ssl_when_flag_set`
  (verifies `smtplib.SMTP_SSL` constructor called, `starttls` NOT
  called) and `test_email_notifier_uses_starttls_when_flag_unset`
  (existing default path stays correct).

---

## Phase 15: Diagnostic Clarity

**Goal**: Surface diagnostic signals that would have prevented the
2026-04-28 misdiagnosis where 139 rejected proposals showed as "0
trades on the dashboard, must be a bug" instead of "threshold gate
working as designed". Two concrete fixes — log message rename for
the proposal sizing path, and a dashboard rejection-reason summary
so operators can see *why* the trade table is empty. No new
framework abstractions.

### 15.1 Diagnostic Clarity (Log + Dashboard)

**Background**: While monitoring the 2026-04-28 Phase 12 redeploy,
the `crypto_master.trading.strategy` logger emitted lines like
`Created position: short BTC/USDT @ 76750.0` — which read like a
trade was opened, but is actually emitted from
`TradingStrategy.create_position` during proposal sizing
(`src/trading/strategy.py:473`), called from
`ProposalEngine._propose_for_symbol` (`src/proposal/engine.py:548`),
**before** the threshold gate runs. The actual trade-open log lives
in `PaperTrader.open_position` at `src/trading/paper.py:546`
(`Opened paper position: ...`) and never fired because every
proposal was rejected at `auto_approve_threshold = 1.0` while
composite scores topped out around 0.35. Result: an hour of
mistaken "trades are happening" reads on logs that turned into
"why does the dashboard show 0?" — both assumptions wrong.
The fix is two safe, mechanical changes plus the operator action
(setting `ENGINE_AUTO_APPROVE_THRESHOLD=0.30` via Fly secrets) that
unblocks actual execution. The operator action is out-of-scope for
this sub-task; only the code clarity follow-up is in scope.

**Related Requirements**: NFR-001 (operability / observability);
operational concern.

- [x] `src/trading/strategy.py` — rename the
  `Created position: ...` log emit at line ~473 to
  `Sized position candidate: ...` so it can't be misread as a
  trade-execution event. Same fields and verbosity; only the verb
  changes. The existing `PaperTrader` "Opened paper position" log
  stays unchanged so the two events are clearly distinct in `fly
  logs` greps.
- [x] `src/dashboard/pages/trading.py` — extend
  `build_summary_metrics` (and the `TradingSummaryMetrics` TypedDict
  from Phase 13.1) with a `proposals_rejected_threshold_count`
  field. Read from `ProposalHistory.list_all()` and count records
  with `decision == "rejected"` whose rejection reason matches the
  threshold-gate pattern (`"composite … below threshold …"`) — the
  cap-rejected pattern (Phase 12.1) is a different cause. Render as
  a compact metric card next to "Active Positions" so an operator
  seeing 0 active positions immediately sees how many proposals
  were rejected and why.
- [x] Tests: extend `tests/test_dashboard_trading.py` with a fixture
  that seeds `ProposalHistory` with one threshold-rejected, one
  cap-rejected (Phase 12.1 pattern), one accepted, and one neutral;
  assert the count surfaces only the threshold-rejected one. Also a
  smoke test that the existing trade renderer still works when the
  new field is `0`.

---

## Phase 16: Chasulang Stability

**Goal**: Address two prod-observed chasulang failures from the
Phase 15.1 redeploy on 2026-04-28: (a) every successful Claude
return parses with `KeyError: 'signal'` because the response is
nested under `trade.*` rather than flat, and (b) the engine
wedged at `15:02:15` for 12+ hours on a 360s chasulang retry —
the subprocess never released, so the wrapper's declared
timeout was a lie. Both render chasulang effectively disabled in
prod and pose a wedge risk for the engine. No new framework
abstractions.

### 16.1 chasulang Parse + Wedge Mitigation

**Background**: After 2026-04-28's Phase 15.1 redeploy, fly logs
showed every chasulang Claude response failing with
`Invalid Claude response format: 'signal'` (a `KeyError` on
`response["signal"]`). The actual response from
`strategies/chasulang_ict_smc.md` returns trade fields nested
under `trade`: `{"external_structure": ..., "liquidity_map":
..., "order_blocks": [...], "trade": {"signal": "neutral", ...},
"wait_conditions": ...}`. Intentional per the chasulang SMC
methodology — top-level keys are the analysis frame; the
actionable trade is the synthesis. Parser needs to look in
`trade.*` first, fall back to top-level for back-compat.

Separately, the engine wedged at `2026-04-28T15:02:15Z` on a
chasulang retry attempt with `timeout=360.0s` and stayed silent
for 12+ hours until the operator manually restarted. Likely
cause: `subprocess.run(..., timeout=...)` under `asyncio.to_thread`
fires the timeout but the child process doesn't get killed
cleanly — stdout buffer fills, child blocks on write, parent
blocks on the timeout exit path. Need explicit kill.

**Related Requirements**: FR-022 (Claude AI Integration —
extending), NFR-001 (operational reliability).

- [x] `src/ai/claude.py::_parse_response` — accept the nested
  `trade.*` form. When the response has a `trade` sub-dict,
  prefer its keys (`signal`, `entry_price`, `stop_loss`,
  `take_profit`, `confidence`, `reasoning`) over top-level. Keep
  top-level fallback for back-compat (`sample_prompt.md`,
  `simple_trend_analysis.md`). When neither form has `signal`,
  raise a clearer error mentioning both candidate paths.
- [x] When the nested form carries `take_profit_1` + `take_profit_2`,
  pick `take_profit_1` (closest target, conservative). Document
  the choice in a parser comment.
- [x] Subprocess wedge: harden `_execute_cli_once` so a timeout
  actually terminates the child. Replace `subprocess.run(...,
  timeout=...)` with explicit `Popen` + `proc.kill()` +
  `proc.wait(timeout=5)` on timeout. Drain stdout/stderr via
  `communicate(timeout=...)` so the process can complete writes.
- [x] Tests:
  - `test_parse_response_handles_nested_trade_form` — chasulang
    shape; `signal` resolved from `trade.signal`.
  - `test_parse_response_handles_top_level_form` — legacy flat
    shape still works.
  - `test_parse_response_picks_take_profit_1_when_tp2_present`.
  - `test_parse_response_raises_clear_error_when_neither_has_signal` —
    error mentions both candidate paths.
  - `test_subprocess_kill_on_timeout` — mock `Popen` to never
    complete; assert `proc.kill()` was called and
    `ClaudeTimeoutError` is raised within bounded wall-clock time.

---

## Phase 17: Strategy-Evolution Operator Workflow

**Goal**: Phase 5.5 shipped `FeedbackLoop` (orchestrator) +
`StrategyImprover` (Claude-driven idea generation) + `RobustnessGate`
(OOS / walk-forward / regime / sensitivity), and Phase 9.3 threaded
multi-timeframe data through the loop end-to-end. The components are
unit-tested but never invoked at runtime — `src/main.py` only has a
FR-026 placeholder comment, and `/app/data/feedback/state/` +
`/app/data/audit/` are empty on Fly. Phase 17 closes the
**operator-driven** path first: a manual `python -m
scripts.auto_research_candidates` invocation that turns Top-N
OHLCV-only picks from `docs/research/strategies/00-priority-matrix.md`
into `AWAITING_APPROVAL` candidate records, leaving promotion to the
operator per CON-003. Nightly auto-execution wiring is deferred to a
later phase.

### 17.1 Auto-Research Operator Workflow + Catalog-Aware Improver

**Background**: The strategy-evolution stack
(`StrategyImprover` → `Backtester` → `PerformanceAnalyzer` →
`RobustnessGate` → `FeedbackLoop._run_cycle` → `CandidateRecord`) has
shipped and is tested in isolation, but no caller has ever exercised
the full chain on Fly — `data/feedback/state/` and `data/audit/` are
empty in production, and `src/main.py` only carries a FR-026 comment.
At the same time the operator built a research catalog under
`docs/research/strategies/` (priority matrix + 9 technique briefs)
that the current `StrategyImprover._build_new_idea_prompt` doesn't
see, so Claude regenerates from-scratch ideas every time instead of
picking from the curated OHLCV-only first-wave list. Two surgical
changes close both gaps without introducing scheduling or
auto-promotion: (a) inject the catalog (priority matrix + per-strategy
docs) into the `generate_idea` / `generate_from_user_idea` prompts so
Claude has the full taxonomy in context, and (b) ship
`scripts/auto_research_candidates.py` — an operator entry point that
reads the priority matrix, picks Top-N OHLCV-only entries, and runs
each through `improver.generate_idea` → `FeedbackLoop._run_cycle()`,
landing every robustness-gate-passing result in `AWAITING_APPROVAL`
for explicit operator approval (CON-003). Nightly scheduling and
`main.py` wiring are deferred to a follow-up sub-task — operator
control comes first.

**Related Requirements**: FR-023 (New Technique Idea Generation),
FR-026 (Automated Feedback Loop), FR-034 (Robustness Validation Gate),
CON-003 (User Approval Required — no auto-promotion); operator
tooling on top of existing components, no new FR/NFR introduced.

**In Scope**:
- `scripts/auto_research_candidates.py` operator entry point
  (`python -m scripts.auto_research_candidates`).
- Catalog-aware `StrategyImprover`: new-idea + user-idea prompts read
  `docs/research/strategies/00-priority-matrix.md` and the per-strategy
  briefs and inject them into the prompt; improvement prompts
  (`generate_improvement`) deliberately do NOT receive the catalog
  (failure-mode analysis stays focused on the existing strategy's
  trace, not the wider taxonomy).
- Fail-soft when the catalog file is missing — improver logs a warning
  and continues with the pre-17.1 prompt, so the path stays usable in
  environments that don't ship the catalog.
- Robustness-gate-passing candidates land in `AWAITING_APPROVAL`;
  failing ones land in `DISCARDED`; errored picks land in `ERRORED`.
  An error on one pick does NOT abort the batch — every pick gets its
  own try/except.
- `--picks N` (default 5; matrix's first-wave OHLCV picks) and
  `--dry-run` flags. Dry-run generates the experimental strategy file
  but skips backtest + robustness gate.
- Run snapshot persisted to `data/research_runs/run_{ts}.json` with
  per-pick status, candidate id, and final state.
- State + audit files (`data/feedback/state/*.json`,
  `data/audit/*.jsonl`) are written end-to-end through the existing
  `FeedbackLoop` machinery — no new persistence code in 17.1.
- Operator-facing summary printed to stdout after the batch (counts +
  per-pick status line).
- README / module-level docstring telling the operator how to invoke,
  what the flags do, and where the output files land.

**Out of Scope**:
- Nightly scheduling / cron / `main.py` wiring (deferred to a later
  sub-task — explicitly out so this stays a single `/dev-crypto`
  cycle).
- Auto-promotion: every passing candidate stops at
  `AWAITING_APPROVAL`; the operator runs `FeedbackLoop.approve()`
  separately. No new approval-flow logic in 17.1.
- Dashboard changes (the existing Phase 7.4 feedback page already
  renders `AWAITING_APPROVAL` records).
- Funding-rate / open-interest / on-chain data wiring — the matrix's
  first-wave picks are OHLCV-only by design; non-OHLCV data sources
  belong to a later phase.

- [x] `scripts/auto_research_candidates.py` — argparse entry point
  with `--picks N` (default 5) and `--dry-run` flags. Reads
  `docs/research/strategies/00-priority-matrix.md`, parses the
  first-wave OHLCV-only picks, and dispatches each through the
  improver + feedback loop. Module docstring documents invocation,
  flags, output locations, and the FR mapping (FR-023 / FR-026 /
  FR-034 / CON-003).
- [x] `src/ai/improver.py::StrategyImprover.__init__` accepts
  `catalog_path: Path | None = None` (defaults to
  `docs/research/strategies/`); add a private `_load_catalog` helper
  that reads the priority matrix + per-strategy briefs, caches the
  joined string on the instance, and fail-softs (logs WARNING +
  returns empty string) when the path is missing.
- [x] `_build_new_idea_prompt` injects the cached catalog content
  under a clearly-labelled section (`## Reference Catalog`).
  `_build_user_idea_prompt` deliberately omits the catalog (the user
  has already described their idea — injecting the catalog would
  redirect Claude away from the user's intent). `_build_improvement_prompt`
  is left untouched — improvement is a focused failure-mode analysis,
  not a fresh-idea exercise. (Deviation from spec wording per
  quant-trader-expert review Issue 4.)
- [x] Dispatch loop in the script: for each pick, call
  `improver.generate_idea(context=<pick description>)` to land the
  new template in `strategies/experimental/`, then
  `FeedbackLoop._run_cycle(strategy_path, ohlcv, ...)` to run
  backtest → robustness gate → state persistence. One pick failing
  raises an exception caught at the per-pick boundary and recorded as
  `ERRORED` in the run snapshot — the batch continues.
- [x] After the batch, persist a JSON run snapshot to
  `data/research_runs/run_{YYYYMMDD-HHMMSS}.json` containing the
  picks list, per-pick `{slug, status, candidate_id, error?}`
  records, and a totals summary. `data/research_runs/` is created on
  first invocation.
- [x] Print an operator-facing summary to stdout: total picks,
  counts by status (`AWAITING_APPROVAL` / `DISCARDED` / `ERRORED`),
  and a per-pick line showing the slug + final state, so the operator
  can immediately spot which candidates need review without opening
  the JSON. Each row is followed by an indented continuation line
  carrying ``decision_reason`` + ``robustness_summary`` so a
  DISCARDED pick's *why* is visible without opening the JSON.
- [x] `--dry-run` short-circuits before the feedback-loop call:
  generates the experimental strategy file under
  ``strategies/experimental/dry_runs/`` (so it never mixes with real
  gated candidates), prints the planned-pick list, but does NOT run
  the backtest / robustness gate / state persistence. Useful for
  validating catalog parsing + prompt output against `claude -p`
  without paying the backtest cost.
- [x] Tests:
  - `tests/test_ai_improver.py` — extend with three catalog-injection
    cases: (a) catalog content appears in `_build_new_idea_prompt`
    output, (b) catalog content does NOT appear in
    `_build_user_idea_prompt` output (regression guard — user-idea is
    anchored on the user's described idea; injecting the catalog
    would redirect Claude away from the user's intent — deviation
    from the original spec wording per quant-trader-expert review
    Issue 4), (c) catalog content does NOT appear in
    `_build_improvement_prompt` output (regression guard that
    improvement stays focused). One additional case for the fail-soft
    branch: missing `catalog_path` produces an INFO log
    (operator-friendly, fail-soft) + empty string, prompts still
    build successfully.
  - `tests/test_scripts_auto_research_candidates.py` — full mocked
    Binance + Claude CLI coverage. Cases: (a) end-to-end happy path
    with N=2 picks, both reaching `AWAITING_APPROVAL`, run snapshot
    written + stdout summary correct; (b) `--dry-run` generates
    strategy files but skips `_run_cycle`; (c) one pick raises,
    other completes — batch does NOT abort, errored pick recorded
    in snapshot. State-file / audit-log persistence under
    `data/feedback/state/` and `data/audit/` is owned by
    `src/feedback/loop.py` + `src/feedback/audit.py` and pinned by
    those modules' own test suites; pinning it again at the script
    level is duplication, so 17.1 inherits the existing coverage
    rather than re-asserting at the script boundary. The
    "matrix-missing" branch and end-to-end persistence behaviour are
    instead exercised by the operator's Fly verification run.

**Verification Criteria**:
- All 4 currently-uncommitted files (`scripts/auto_research_candidates.py`,
  `tests/test_scripts_auto_research_candidates.py`, `src/ai/improver.py`,
  `tests/test_ai_improver.py`) are committed alongside any new files
  this sub-task adds.
- Test count delta: ~+5 to +8 net new tests (1170 → ~1175–1178).
- `scripts/lint.sh` passes (ruff + mypy clean across 53 source files,
  unchanged file count expected — `scripts/` is not in the mypy scope
  so the new script's typing is best-effort).
- One operator-driven Fly run produces ≥1 `CandidateRecord` under
  `/data/feedback/state/` and ≥1 audit entry under `/data/audit/`.
  **This is an operator action, not a code task** — flagged here as a
  follow-up to be checked off after the sub-task ships, not a
  blocker for `/dev-crypto` completion.
- No ADR — see `src/ai/improver.py` and `src/feedback/loop.py` for
  the canonical loop semantics. 17.1 wires existing components into
  an operator script and extends one prompt; no new architectural
  seam.

### 17.2 Portfolio Snapshot Recording in Runtime Cycle

**Background**: Trading dashboard previously only showed PnL because
`PortfolioTracker.record_snapshot` had no caller — `data/portfolio/`
was empty on Fly even after weeks of paper trading, so the equity
curve metric card rendered as a flat line. The runtime engine now
records an `AssetSnapshot` at the end of every cycle (balances +
open-position marks); fetch errors are swallowed so a flaky exchange
query never breaks the loop. The `Trader` Protocol grows an async
`get_balances()` so paper and live both feed the recorder through the
same surface. Dashboard Summary promotes Current Equity to the
leading metric card with unrealized P&L as the delta; the prior
caption-only treatment buried the number. **Shipped 2026-04-30 in
commit `094a79d`**; this entry is the back-fill of the spec text
that was missed during the original planning cycle.

**Related Requirements**: NFR-008 (Asset/PnL History — wires
`PortfolioTracker.record_snapshot` end-to-end so the volume layout
actually receives data), FR-031 (Asset and Performance Summary —
dashboard Current Equity card consumes the snapshots).

- [x] `src/runtime/engine.py` — at the end of each cycle, gather
  balances via `trader.get_balances()` and open-position marks via
  `trader.get_open_trades()`, build an `AssetSnapshot`, and call
  `PortfolioTracker.record_snapshot(...)`. Wrap in `try/except` so a
  ticker / balance fetch failure logs WARN but does not abort the
  cycle.
- [x] `src/trading/base.py::Trader` — Protocol gains async
  `get_balances() -> dict[str, Balance]`. `PaperTrader` and
  `LiveTrader` both implement.
- [x] `src/main.py::build_engine` — wire the `PortfolioTracker`
  instance into `TradingEngine` (new constructor parameter; default
  preserves single-engine wiring).
- [x] `src/dashboard/pages/trading.py` — promote Current Equity to
  the leading metric card; unrealized P&L becomes the delta.
- [x] Tests in `tests/test_runtime_engine.py` — happy-path
  `record_snapshot` invocation per cycle, error path swallows
  exception, balance shape forwarded correctly.
- [x] Write unit tests.

### 17.3 Closed-Trade Performance Records

**Background**: Analysis Techniques dashboard read every aggregate
as 0 because `PerformanceTracker.save_record` had no caller in
production — the proposal engine queried it for ranking but nothing
wrote to it, so per-technique win rate / average PnL / total PnL
were all dead values on the page. The runtime engine now snapshots a
complete `PerformanceRecord` at trade close (technique fields from
the originating proposal, fill prices / fees / pnl / outcome from
`TradeHistory`) so the dashboard moves as trades land. Failures are
logged and swallowed so a missed performance row never breaks the
cycle. **Shipped 2026-04-30 in commit `ab9dc32`**; this entry is the
back-fill of the spec text that was missed during the original
planning cycle.

**Related Requirements**: FR-005 (Analysis Technique Performance
Tracking — wires `PerformanceTracker.save_record` end-to-end so
per-technique aggregates actually accumulate), FR-021 (Technique
Performance Analysis — dashboard reads the persisted records).

- [x] `src/runtime/engine.py` — on trade close, build a
  `PerformanceRecord` from the originating `Proposal` (technique
  name / version / hypothesis fields) and the `TradeHistory` (fill
  prices, fees, realized PnL, win/loss outcome); call
  `PerformanceTracker.save_record(...)`. Wrap in `try/except` so a
  malformed record logs WARN but does not abort the cycle.
- [x] `src/runtime/engine.py` — track the originating proposal id on
  each open position so the trade-close site can recover the
  technique fields without re-querying `ProposalHistory`.
- [x] `src/main.py::build_engine` — wire the `PerformanceTracker`
  instance into `TradingEngine` alongside the
  `PortfolioTracker` from 17.2.
- [x] Tests in `tests/test_runtime_engine.py` — happy-path
  `save_record` on trade close (technique fields populated from
  proposal, pnl from trade); error path swallows exception; missing
  proposal-id falls through with WARN.
- [x] Write unit tests.

### 17.4 Auto-Research Workflow Unblock — Runtime Contract + Backtest Circuit Breaker

**Background**: First real run of `python -m
scripts.auto_research_candidates --picks 5` on 2026-04-30 hung for ~9
hours after producing exactly one candidate
(`strategies/experimental/donchian_turtle_system_2_20260430_002157.md`).
DEBT-019 (High, 2026-04-30) traces it to a three-way contract gap:
(a) `_build_new_idea_prompt` injects the catalog and asks for a
falsifiable hypothesis but does NOT mandate the runtime JSON schema
in the technique body, so Claude defaults to a human-readable rule
list; (b) the generated technique frontmatter lands on
`technique_type: prompt`, so `Backtester` invokes Claude per-bar
expecting strict JSON; (c) `Backtester` has no per-bar timeout and no
"N consecutive parse failures → abort" rule, so the engine logs
"Claude response did not contain parseable JSON" and continues bar
after bar, producing 1.5 MB of warnings and unbounded API spend
without ever erroring out. Production-shipped `chasulang_ict_smc.md`
is unaffected — its body has the JSON schema baked in and Phase 16.1
hardened the parser. Phase 17.4 closes this with the **A + C** combo
from DEBT-019: hardening the new-idea prompt to embed the runtime
JSON contract (so the next generated `prompt`-type candidate is
actually runnable) plus a backtest circuit breaker (so any future
contract drift fails fast in minutes instead of hours and surfaces a
clean `ERRORED` candidate). Option B (code-type steering for
deterministic catalog picks) is the cleaner long-term fix and lands
separately as Phase 17.5.

**Related Requirements**: FR-022 (Technique Improvement Suggestion —
prompt-format hardening of generated artefacts), FR-023 (New Technique
Idea Generation — the prompt path that produced the broken candidate),
FR-025 (Backtesting Execution — the per-bar invocation site where the
hang occurred), NFR-001 (operational maturity — circuit breaker / fast-
fail). Extends existing requirements; no new FR/NFR introduced.

- [x] `src/ai/improver.py::_build_new_idea_prompt` gains an explicit
  "Output Contract" section in its instructions, requiring the
  generated `prompt`-type technique body to include a `## Output
  Contract` block carrying the chasulang JSON schema verbatim
  (`signal: long|short|neutral`, `entry_price`, `stop_loss`,
  `take_profit` keys; one JSON object per bar; no prose around the
  fenced JSON block). Reference `strategies/chasulang_ict_smc.md` as
  the canonical template Claude must replicate. Do NOT inject this
  into `_build_user_idea_prompt` — Phase 17.1's Issue-4 deviation
  explicitly anchors user-idea on the user's text, pinned by
  `tests/test_ai_improver.py::TestCatalogInjection::test_catalog_not_in_user_idea_prompt`;
  `_build_improvement_prompt` is also untouched (improvement is
  failure-mode analysis, not a fresh body).
- [x] `src/backtest/engine.py::Backtester.run` (single-TF, line ~334)
  and `Backtester._run_multi_timeframe` (line ~532) — both per-bar
  `strategy.analyze(...)` invocation sites — gain a per-bar timeout
  wrapping the call (`asyncio.wait_for(...)`) and a counter that
  increments on `ClaudeParseError` / `StrategyError`. When the
  consecutive-failure counter reaches the threshold, abort the run
  and raise a new `BacktestAbortedError` with `reason` ∈
  `{"per_bar_timeout", "consecutive_parse_failures"}` and the offending
  candle index. A single non-error bar resets the counter (so a
  flaky one-off doesn't trip the breaker). The existing `try/except
  StrategyError` at `engine.py:337` is the surface to extend; do not
  introduce a second per-bar try/except. **Refinement at
  implementation:** ``StrategyValidationError`` (a ``StrategyError``
  subclass that semantically means "data not ready yet") is caught
  separately and skipped without incrementing the breaker counter —
  otherwise any strategy whose internal warmup exceeds
  ``BacktestConfig.warmup_candles`` (e.g. ``rsi_universal``'s
  ``period * 3`` floor against the default 20-bar engine warmup)
  would trip the breaker immediately, which is a footgun, not a
  circuit breaker. Genuine contract failures
  (``ClaudeParseError``, ``StrategyExecutionError``,
  ``StrategyLoadError``, ``asyncio.TimeoutError``) still count.
- [x] `BacktestAbortedError` propagates through
  `Backtester.run_for_strategy` and `RobustnessGate` to
  `FeedbackLoop._run_cycle`'s existing exception handler, where it
  lands as `LoopStatus.ERRORED` (`src/feedback/loop.py:529`) with
  `decision_reason` carrying the abort reason and offending-candle
  index. The candidate record is recorded `ERRORED`, never silently
  passing or hanging. No new path through the loop — reuse the
  current ERRORED handler shape.
- [x] `Settings` gains two env-overridable fields in `src/config.py`
  following the Phase 10.2 / 13.2 pattern:
  `engine_backtest_per_bar_timeout: float = Field(default=60.0, ge=1.0)`
  (env `ENGINE_BACKTEST_PER_BAR_TIMEOUT`) and
  `engine_backtest_max_parse_failures: int = Field(default=5, ge=1)`
  (env `ENGINE_BACKTEST_MAX_PARSE_FAILURES`). Defaults are
  conservative — 60s per bar (chasulang's per-call ceiling under the
  Phase 14.1 240s strategy override is multi-bar amortised; 60s per
  bar still gates a runaway), 5 consecutive failures (one transient
  blip won't trip; a structurally broken contract trips inside the
  first warmup window). `BacktestConfig` reads these from `Settings`
  in `Backtester.__init__` (or equivalent — match whichever existing
  pattern threads `Settings` into `BacktestConfig` today; if none, add
  fields to `BacktestConfig` and have `build_engine` /
  `FeedbackLoop` callers wire the `Settings.engine_*` values
  through). Parity assertion alongside the existing
  `test_settings_defaults_match_engine_config` style. **Implementation
  decision:** added the fields directly to `BacktestConfig` with
  defaults matching `Settings.engine_backtest_*`. Since no caller
  currently threads `Settings` into `BacktestConfig`, this is the
  one-line minimum-diff seam — `BacktestConfig()` and
  `Backtester()` continue to inherit the breaker behaviour without
  caller changes; the parity test
  (`TestBacktestEngineSettings::test_backtest_defaults_match_backtest_config`)
  pins the two sides together.
- [x] `.env.example` documents both new env vars with operator-facing
  prose: when to raise the per-bar timeout (long-running multi-TF
  Claude calls), when to raise the max-parse-failures threshold (a
  noisy LLM in development), and the warning that lowering
  `engine_backtest_per_bar_timeout` below the strategy's
  `claude_timeout_seconds` will trip the breaker on every bar.
- [x] Tests:
  - `tests/test_ai_improver.py` — three new cases under
    `TestNewIdeaOutputContract`: (a) `_build_new_idea_prompt` output
    contains the literal "Output Contract" instruction and the
    canonical JSON-schema keys (`signal`, `entry_price`, `stop_loss`,
    `take_profit`); (b) the same instruction does NOT appear in
    `_build_user_idea_prompt` output (regression guard, parallel to
    `TestCatalogInjection::test_catalog_not_in_user_idea_prompt`);
    (c) the same instruction does NOT appear in
    `_build_improvement_prompt` output. Existing
    `TestCatalogInjection` cases are untouched and must continue to
    pass.
  - `tests/test_backtest_engine.py` — three new cases: (a) a
    `MockStrategy` whose `analyze` raises `ClaudeParseError` on every
    bar trips the breaker after `engine_backtest_max_parse_failures`
    consecutive failures and aborts with `BacktestAbortedError(
    reason="consecutive_parse_failures")`; (b) a slow `MockStrategy`
    whose `analyze` blocks past `engine_backtest_per_bar_timeout`
    aborts with `BacktestAbortedError(reason="per_bar_timeout")`;
    (c) a `MockStrategy` that fails 4 times then succeeds does NOT
    trip the breaker (counter resets) — pins the consecutive-only
    contract.
- [ ] Acceptance — operator action, not a `/dev-crypto` blocker: re-run
  (Pending — this is operator action against a real Claude CLI session
  and is intentionally out of scope for the implementation cycle.)
  `python -m scripts.auto_research_candidates --picks 1` against the
  surviving artefact `strategies/experimental/donchian_turtle_system_2_20260430_002157.md`
  (DEBT-019 flags this file as the canonical test case). Must either
  (i) complete the backtest within minutes because the hardened prompt
  from item 1 produces a parseable response, or (ii) abort cleanly to
  `LoopStatus.ERRORED` with `decision_reason` naming the abort reason.
  9-hour hangs are a hard regression.
- [x] Write unit tests.

**Parent Debt**: DEBT-019 (Auto-research script hangs indefinitely on
prompt-type technique backtest, High, 2026-04-30). DEBT-019's Option B
(code-type steering) is deferred to Phase 17.5.

### 17.5 Code-Type Steering for Deterministic Catalog Picks (DEBT-019 Option B)

**Background**: Phase 17.4 unblocks the auto-research workflow with a
runtime contract + circuit breaker, but the deeper fix for
deterministic catalog picks (Donchian, Supertrend, Z-score, Larry
Williams, NR7, Connors RSI(2), BB %B+RSI, Golden Cross) is to generate
them as Python `BaseStrategy` subclasses instead of Claude-driven
markdown prompts. A code-type technique runs locally per bar, with no
LLM in the hot path — orders of magnitude faster, deterministic, and
immune to JSON-contract drift entirely. DEBT-019 lists this as the
cleaner long-term fix; this sub-task ships it as a separate
`/dev-crypto` cycle so the unblock (17.4) and the cleanup (17.5) can
land independently.

**Related Requirements**: FR-023 (New Technique Idea Generation — adds
a code-generation branch to the existing prompt path), FR-025
(Backtesting Execution — code-type techniques bypass the per-bar
Claude call entirely), NFR-001 (operational maturity — eliminates the
LLM-in-hot-path failure surface for deterministic strategies). No new
FR/NFR introduced.

- [ ] Decide steering signal: explicit boolean flag on `Pick` (the
  cleanest test, no fragile heuristic) versus context-keyword
  detection (e.g. "close > N-bar high") versus always-code for catalog
  picks. Recommended: explicit flag on `Pick`, defaulting to `False`
  so non-flagged picks retain the 17.4-hardened prompt path.
- [ ] `src/ai/improver.py` — branch `_build_new_idea_prompt` (or add a
  sibling `_build_new_idea_code_prompt`) on the steering signal. The
  code branch instructs Claude to produce a Python file containing a
  `BaseStrategy` subclass with a synchronous `signal()` method,
  mirroring `strategies/rsi.py`, `strategies/bollinger_bands.py`, and
  `strategies/ma_crossover.py` as canonical templates (frontmatter
  block + class + parameter constants). The catalog injection from
  Phase 17.1 is retained on this branch (Claude still benefits from
  the taxonomy when picking implementation choices).
- [ ] `scripts/auto_research_candidates.py::TOP_PICKS` — flag the
  deterministic picks for code-type generation. Likely all 9 default
  picks qualify (Donchian, Supertrend, Z-score, Larry Williams, NR7,
  Connors RSI(2), BB %B+RSI, Golden Cross, plus whichever ninth the
  matrix ranks); confirm against
  `docs/research/strategies/00-priority-matrix.md` at implementation
  time.
- [ ] Tests:
  - `tests/test_ai_improver.py` — new cases asserting the code-type
    prompt path emits the `BaseStrategy` / `signal()` instruction
    string and references the canonical example files; the prompt
    branch is selected when the steering flag is `True` and skipped
    when `False`.
  - Integration test: a `BaseStrategy` subclass produced via the
    code-type path is loadable by `src/strategy/loader.py::load_strategy`
    and runs through `Backtester.run_for_strategy` end-to-end without
    invoking the Claude CLI per-bar (mock `ClaudeCLI` should record
    zero `analyze` calls during the simulated backtest).
- [ ] Acceptance: `python -m scripts.auto_research_candidates --picks 5`
  produces 5 Python strategy files under `strategies/experimental/`
  that load cleanly via `load_strategy` and run through `Backtester` +
  `RobustnessGate` with no per-bar Claude calls. Wallclock for the
  whole batch is dominated by OHLCV fetches, not LLM round-trips.
- [ ] Write unit tests.

**Parent Debt**: DEBT-019 Option B (Auto-research script hangs
indefinitely on prompt-type technique backtest, High, 2026-04-30). 17.4
ships the unblock; 17.5 ships the cleaner long-term path.

---

## Phase 18: Live Trading Quality

**Goal**: Close trading-correctness gaps surfaced by the 2026-04-30
production review of `/data/trades/paper/trades.json` (1W/8L,
-78.50 USDT, EV -8.73/trade). The first defect is a stale-quote class
of bug at proposal fill: the runtime engine copies
`proposal.entry_price` into the opened `Position` with no live-price
sanity check, so when chasulang/Claude CLI takes minutes to return
the auto-approved fill happens at a price the live ticker has already
crossed past the proposal's stop-loss. Phase 18 starts with the fill
boundary; later sub-tasks will address the next-largest contributors
the production review surfaces.

### 18.1 Stale-Quote Sanity Gate at Proposal Fill

**Background**: Production paper-trading data on Fly volume
`/data/trades/paper/trades.json` shows trade
`5d51cba3-900f-4415-a401-096df391860a` (ETH long, proposal
`6ef8c07e...`) as a smoking-gun for the stale-quote class of bug:
proposal created at `14:43:21` with `entry=2323`, `SL=2305`;
chasulang/Claude CLI took 3 min 13 sec to return; auto-approval +
fill at `14:46:34` recorded the position at the stale `entry=2323`;
the position closed `0.48s` later at `2300` because the live ticker
had already crossed past the SL by the time of fill. The runtime
engine (`src/runtime/engine.py::_execute` →
`_proposal_to_position`) copies `proposal.entry_price` into the
`Position` with no live-price sanity check, so any LLM latency
spike turns into a guaranteed-loss fill at a price the market has
already moved through. The fix is a sanity gate between
auto-approval and `trader.open_position`: fetch a fresh ticker,
reject the fill if live has crossed the SL or drifted beyond a
configurable slippage tolerance, otherwise fill at
`proposal.entry_price` exactly as today (no silent switch to live
price — that would defeat the proposal's R/R math). Ticker fetch
failure falls back to fill so a transient exchange hiccup doesn't
silently disable trading; the WARN log is the operator's signal.

**Related Requirements**: FR-008 (Entry/Take-Profit/Stop-Loss
Setting — extending the fill boundary so SL is enforced at fill,
not just at exit), FR-013 (User Accept/Reject — auto-approval is
the system's stand-in; the gate is the system's reject path),
NFR-012 (Live Trading Confirmation — paper-trading correctness
boundary; same code path runs live).

- [x] `src/runtime/engine.py::_execute` — between auto-approval and
  `trader.open_position`, call `exchange.get_ticker(symbol).price`
  to fetch a fresh live price. On `Exception`, log WARN
  (`stale_quote_check_failed`) and fall through to fill (preserve
  current behaviour — transient exchange errors must not silently
  disable trading).
- [x] When `EngineConfig.reject_if_past_stop_loss` is `True` and
  live has crossed the SL (live ≤ `proposal.stop_loss` for longs,
  live ≥ `proposal.stop_loss` for shorts), record the proposal as
  `rejected` with `decision_reason="stale_quote_past_sl"` and emit
  the existing rejection activity event with structured fields
  (`live_price`, `proposal_entry`, `proposal_stop_loss`, `side`).
  Skip `trader.open_position`; do not increment `positions_opened`.
- [x] When the absolute drift `abs(live - proposal.entry_price) /
  proposal.entry_price` exceeds
  `EngineConfig.fill_slippage_tolerance`, record the proposal as
  `rejected` with `decision_reason="slippage_exceeds_tolerance"`
  and emit the same rejection activity event shape. Order matters:
  the past-SL check runs first (more specific signal); only if it
  passes does the slippage check run.
- [x] Otherwise fill at `proposal.entry_price` as today — no
  silent switch to the live price. The proposal's R/R math is
  predicated on `entry_price`; mutating it at fill would corrupt
  every downstream metric.
- [x] `EngineConfig.fill_slippage_tolerance: Decimal = Decimal("0.005")`
  (50 bps default; `Field(ge=0)`) and
  `EngineConfig.reject_if_past_stop_loss: bool = True` defaults in
  `src/runtime/engine.py`. Defaults are deliberately conservative —
  reject_if_past_sl on by default closes the smoking-gun bug
  without an env flip.
- [x] `Settings.engine_fill_slippage_tolerance: Decimal` and
  `Settings.engine_reject_if_past_stop_loss: bool` env overrides
  in `src/config.py` (`ENGINE_FILL_SLIPPAGE_TOLERANCE` and
  `ENGINE_REJECT_IF_PAST_STOP_LOSS`); follow the Phase 10.2 /
  13.2 pattern (`Field(default=...)`, parity assertion via the
  existing `test_settings_defaults_match_engine_config` style).
- [x] `src/main.py::build_engine` — wire the two new
  `Settings.engine_*` fields into the `EngineConfig(...)`
  constructor call alongside the existing eight fields; explicit-
  config-wins back-compat preserved. `.env.example` documents both
  new env vars with operator-facing prose.
- [x] Tests in `tests/test_runtime_engine.py` — four cases:
  (a) live past SL → proposal recorded `rejected` with
  `decision_reason="stale_quote_past_sl"`, rejection activity
  event emitted, no `trader.open_position` call,
  `positions_opened == 0`; (b) live within tolerance → fill at
  `proposal.entry_price` (regression guard — pin the no-silent-
  switch contract); (c) live drift beyond tolerance → proposal
  recorded `rejected` with
  `decision_reason="slippage_exceeds_tolerance"`, rejection event
  emitted; (d) `exchange.get_ticker` raises → fill proceeds as
  before, WARN logged with `stale_quote_check_failed`.

### 18.2 Trade-Quality Diagnostic

**Background**: The same 2026-04-30 production review of
`/data/trades/paper/trades.json` that surfaced Phase 18.1 also
surfaced the broader trade-quality picture: 1W/8L, -78.50 USDT,
EV -8.73/trade, 11% win rate across `simple_trend_analysis` and
`bollinger_band_reversion`. Phase 18.1 closed the smoking-gun
stale-quote fill class but does not explain why the surviving
fills are still net-negative. Before any code change to SL
distance, R:R, composite-gate threshold, or strategy-specific
gating, the team needs a measurement pass on the closed-trade
ledger to attribute losses to specific causes — slippage
calibration, SL/RR appropriateness, accepted-vs-rejected EV
gap, per-strategy concentration. Editing engine knobs without
this attribution risks chasing the wrong defect; the
methodology is locked in `docs/research/trade-quality-design-
2026-05-01.md` (this cycle's design pass) so the analysis
itself can run next cycle as a pure read-only research task.

**Related Requirements**: FR-005 (Analysis Technique Performance
Tracking — extending the per-strategy live-EV view from the
performance store into a cross-strategy diagnostic), FR-021
(Technique Performance Analysis — extending the existing report
generation contract into a one-off forensic), FR-025
(Backtesting Execution — §4.5 hypothetical EV walk for rejected
proposals reuses the backtest fill semantics), NFR-001 (Python
3.10+ tooling for the analysis script — extending the existing
contract; no new FR/NFR introduced).

- [ ] Pull `/data/trades/paper/trades.json` and `/data/proposals/
  *.json` from the Fly volume per `docs/research/trade-quality-
  design-2026-05-01.md` §2.1 and §2.2; cross-link every closed
  trade to its `ProposalRecord` via `proposal_id` and surface
  any orphans.
- [ ] Compute the §3 per-trade table for all 9 closed trades
  (columns: `trade_id`, `symbol`, `strategy`, `side`,
  `latency_seconds`, `realised_drift_bps`, `sl_distance_bps`,
  `tp_distance_bps`, `rr_ratio`, `exit_reason`, `pnl_realised`,
  `r_multiple`, `regime_tag`) using the formulae in §5 verbatim.
- [ ] Emit the §4.1 per-strategy EV table with `live_ev_usdt` vs
  `baseline_ev_usdt` delta against `data/backtest/baselines/
  <strategy>/summary.json` (Phase 10.3 numbers); annotate every
  aggregate with `(n=N)` and the §9 sample-size caveats.
- [ ] Emit §4.2 per-regime, §4.3 per-exit-reason, §4.4 latency-
  vs-adverse-drift scatter (PNG to `docs/research/figures/
  2026-05-01-latency-drift.png` linked inline, or ASCII), §4.5
  rejected-vs-accepted EV gap with hypothetical-outcome walk,
  and §4.6 50-bps recalibration empirical drift CDF
  (augmenting the truncated post-18.1 tail with rejected-by-
  slippage drift values per §4.6 caveat).
- [ ] Land the analysis as `docs/research/trade-quality-2026-05-
  01.md` following the §6 output skeleton; include the §6.1
  ETH `5d51cba3` worked example as the first row of §1 per-
  trade table.
- [ ] Apply the §7 decision rules and write a single explicit
  recommendation in §9 of the output doc — one of: §7.1
  (tighten tolerance → Phase 18.3 trigger), §7.2 (composite-
  gate inversion → top-priority escalation), §7.3 (strategy-
  specific gate / removal), §7.4 (no clear signal — return to
  dev plan); cite the numerical trigger threshold met.
- [ ] Update `docs/baselines.md` with a cross-reference pointer
  to the new analysis doc for each strategy touched (per the
  design's §10 cross-check item); if the regime-tertile
  convention from §3.1 is novel, document it in `docs/baselines.
  md` and add a one-line `docs/TECH-DEBT.md` entry for any
  newly-surfaced gap surfaced during the analysis.
- [ ] Write unit tests — N/A for a research-only sub-task; no
  `src/` or `tests/` changes are produced. The §10 cross-check
  list in the design doc is the verification gate in lieu of
  unit tests; the analyst ticks every box before publishing.

---

## Phase 19: Sub-Account / Capital Segmentation

**Goal**: Decompose the single-`Trader` / single-seed runtime into N
independent capital pools ("sub-accounts"). Today every strategy
shares one USDT balance — `src/main.py::build_trader` constructs one
`PaperTrader(initial_balance={"USDT": Decimal(paper_initial_balance)})`
and `TradingEngine` holds one `self.trader`, so a drawdown in
`bollinger_band_reversion` directly starves `chasulang_ict_smc` of
capital. The same constraint blocks four operationally important
scenarios: (a) per-strategy seed isolation, (b) running multiple
exchange-credential sets in parallel (e.g. `binance_main` for futures
and `binance_alt` for spot altcoins), (c) controlled-capital A/B
testing of strategy combinations against the same OHLCV stream, and
(d) per-bucket risk overrides ("1% risk on the experimental bucket,
0.3% on main"). Phase 19 is split into five sub-tasks staged from
foundation outward — every step preserves a working `default`
sub-account materialised from existing `Settings.paper_initial_balance`
so legacy single-seed deployments operate unchanged at every commit
on the way through. See `DESIGN.md` §9 for the full architecture.

### 19.1 Sub-Account Foundation (Entity + Registry + Default Migration)

**Background**: The architectural seam this phase introduces only
becomes valuable once engine, persistence, and dashboard wire through
it (19.2 / 19.3). Landing it as a free-standing first sub-task
without consumers keeps the diff reviewable and lets a single test
suite pin the legacy-single-seed compatibility invariant before any
behaviour-touching code follows. The foundation is: a `SubAccount`
Pydantic model, a `SubAccountRegistry` that today holds exactly one
synthesised `default` entry derived from `Settings`, and a one-shot
on-disk migration that renames `data/{trades,portfolio,performance,
proposals}/{mode}/...` into `.../default/...` guarded by a marker file
so the rename is idempotent across restarts. No `Trader`, no engine,
no dashboard touched in 19.1 — the registry hands out the same
`PaperTrader` instance `build_trader` already builds today, just
addressed by `id="default"`.

**Related Requirements**: FR-036 (Sub-Account Capital Isolation —
introducing the entity that will eventually own a balance pool;
single-account materialisation is the back-compat floor).

- [ ] `src/trading/sub_account.py` — new module. `SubAccount` Pydantic
  model with fields per `DESIGN.md §9.2` (`id` / `name` / `mode` /
  `exchange_ref` / `initial_balance` / `strategy_filter` /
  `risk_overrides` / `enabled`); `RiskOverrides` sub-model with
  optional `risk_percent` / `max_open_positions_total` /
  `max_open_positions_per_symbol` / `leverage_cap`. Validators:
  `id` matches `^[a-z][a-z0-9_]*$` (filesystem-safe), `enabled and
  mode == "live"` requires non-null `exchange_ref`,
  `initial_balance` keys are upper-case currency codes. Frozen model
  (`model_config = ConfigDict(frozen=True)`) so registry consumers
  can't mutate behind the registry's back.
- [ ] `src/trading/sub_account_registry.py` — `SubAccountRegistry`
  class. `__init__` accepts `settings: Settings`, `trader: Trader`,
  `config_path: Path | None = None` (default
  `Path("config/sub_accounts.yaml")`). When config file is absent
  (the 19.1 default — YAML support is 19.3 territory), materialises
  one `SubAccount(id="default", name="Default Account",
  mode=settings.trading_mode, exchange_ref="default", initial_balance=
  {"USDT": Decimal(str(settings.paper_initial_balance))},
  strategy_filter=None, risk_overrides=RiskOverrides(),
  enabled=True)`. Methods: `list_active()`, `get(id)` (raises
  `SubAccountNotFoundError`), `get_trader(id)` (returns the single
  shared `Trader` in 19.1 — registry stores the wiring seam now,
  19.2 lights it up), `filter_strategies(id, available)` (returns
  `available` unchanged when `strategy_filter is None`).
- [ ] `src/trading/sub_account_migration.py` — `migrate_legacy_paths(
  data_dir: Path) -> dict[str, int]` helper. Idempotent rename of
  `data/trades/{mode}/trades.json` → `data/trades/{mode}/default/
  trades.json` across `mode in {paper, live, backtest}`; same shape
  for `portfolio/{mode}/snapshots.json` and `proposals/{date}_{
  symbol}.json` (proposals top-level → `proposals/default/...`).
  Performance subtree (`performance/{technique}/...`) deferred to
  19.2 because the new layout adds a sub-account level above the
  technique. Marker file `data_dir/.subaccounts_migrated_v19_1`
  written on first success; presence short-circuits subsequent
  invocations. Returns count-per-component dict for operator log.
- [ ] `src/main.py::run` — call `migrate_legacy_paths(settings.data_dir)`
  before `build_engine` (mirrors Phase 11.4's
  `_purge_old_proposals` placement). Log INFO with the rename count
  only when non-zero (silent on already-migrated to avoid restart
  noise). Build the registry after `build_trader` returns; pass to
  `build_engine` (registry currently unused inside the engine — the
  parameter is added now so 19.2 doesn't churn `build_engine`'s
  signature).
- [ ] `tests/test_trading_sub_account.py` — model field validation
  (id regex / live-requires-exchange-ref / currency-code casing /
  frozen behaviour); 6 tests.
- [ ] `tests/test_trading_sub_account_registry.py` — default
  materialisation reads `Settings.paper_initial_balance` /
  `Settings.trading_mode`; `list_active`, `get`, `get_trader`,
  `filter_strategies(None)` and `filter_strategies(["rsi_4h"])`
  paths; missing-id raises `SubAccountNotFoundError`; 7 tests.
- [ ] `tests/test_trading_sub_account_migration.py` — rename-and-
  marker on fresh dir; idempotent re-run (marker present, no work);
  no source files (empty mode dir, no marker written but no error);
  partial pre-existing (one mode already migrated, others not) —
  marker absent → finishes the rest. 5 tests.
- [ ] `tests/test_main_dispatch.py` — extend with a smoke test
  asserting `run` calls `migrate_legacy_paths` once and constructs
  a registry. 2 tests.

### 19.2 Sub-Account Engine Integration

**Background**: 19.1 lands the seam; 19.2 is where the runtime starts
flowing through it. Every proposal, trade, performance record, and
portfolio snapshot grows a `sub_account_id` field; `TradingEngine`
fans out per active sub-account; persistence paths take the
sub-account in their key. The cross-cycle position cap (Phase 12.1)
becomes per-sub-account by virtue of each sub-account having its own
`Trader`; the symbol-cap text reads "symbol X cap N reached on
sub-account default (M open)". The 19.1 registry still holds one
`default` sub-account in 19.2 — the multi-sub-account parsing arrives
in 19.3. So the entire 19.2 diff is observable as "one sub-account in
flight, all paths now namespace-scoped, behaviour bytewise unchanged
for the operator".

**Related Requirements**: FR-036 (Capital Isolation — engine plumbing
that enforces it), FR-005 (Performance Tracking — extends the
per-technique record to per-(sub-account, technique)), NFR-007 /
NFR-008 (Trade History / Asset-PnL History — storage layout
extension).

**Prerequisites**: **DEBT-046 (Medium — atomic write does not protect
against concurrent-mutation loss)** must be addressed before 19.2
ships. Phase 22.1's `atomic_write_text` helper resolves crash-mid-write
durability but is silently last-writer-wins under concurrent
load → mutate → save against the same file. 19.2's sub-account fan-out
introduces parallel workers writing to shared persistence files
(`data/performance/...`, `data/trades/...`, `data/portfolio/...`,
`data/proposals/...`); without per-file locking (e.g. `fcntl.flock` on
POSIX) or per-account file partitioning, sub-account A's mutation can
silently overwrite sub-account B's. Planner picks the resolution shape
(per-file lock helper layered over `atomic_write_text`, OR per-account
file partitioning aligned with the 19.2 path layout); see DEBT-046 in
`docs/TECH-DEBT.md` for the suggested resolution surface.

- [ ] `src/proposal/proposal.py` — `Proposal.sub_account_id: str`
  field (default `"default"` for back-compat through serialised
  histories). `ProposalRecord` mirrors.
- [ ] `src/strategy/performance.py` — `PerformanceRecord.sub_account_id:
  str` field; `TechniquePerformance` keyed by `(sub_account_id,
  technique_name)`; `PerformanceTracker` constructor accepts
  `sub_account_id` and writes under
  `data/performance/{sub_account_id}/{technique_name}/`.
- [ ] `src/strategy/performance.py::TradeHistory` — `sub_account_id:
  str` field; `TradeHistoryTracker` writes under
  `data/trades/{mode}/{sub_account_id}/trades.json`.
- [ ] `src/trading/portfolio.py` — `PortfolioTracker` writes under
  `data/portfolio/{mode}/{sub_account_id}/snapshots.json`; existing
  `record_snapshot` / `get_equity_curve` accept `sub_account_id`.
- [ ] `src/runtime/engine.py::TradingEngine` — `__init__` takes
  `registry: SubAccountRegistry` (replaces `trader`). `cycle()`
  iterates `registry.list_active()`; for each sub-account, calls
  `proposal_engine.propose_*` with the registry-filtered strategies
  and the sub-account's balance; routes results through
  `registry.get_trader(sub.id)`. Every proposal is stamped with
  `sub_account_id` before persistence. `_handle_proposal`'s symbol
  cap check uses the sub-account's trader's `get_open_trades()`
  (naturally scoped) and the sub-account's
  `risk_overrides.max_open_positions_per_symbol or
  config.max_open_positions_per_symbol`. Log lines + activity
  events gain `sub_account_id` in their structured payload.
- [ ] `src/proposal/engine.py::ProposalEngine` — accepts
  `strategies` and `risk_percent` overrides per call (already the
  shape, but verify `propose_bitcoin` / `propose_altcoins` thread
  the new strategy list correctly through `_propose_all_for_symbol`
  / `_select_all_techniques`). No structural change expected; pin
  with new tests.
- [ ] `src/main.py::build_engine` — wires `registry` instead of
  `trader` directly; back-compat-preserving overload with `trader`
  removed (single-sub-account default does what the old wiring did,
  via the registry).
- [ ] `src/dashboard/pages/trading.py` / `pages/engine.py` — read
  performance + portfolio from the new
  `{sub_account_id}` paths; default sub-account selector filter set
  to `default` so today's view is preserved. Multi-account selector
  shipped in 19.3.
- [ ] One-shot performance-tree migration: extend
  `migrate_legacy_paths` (19.1) with the `performance/{technique}`
  → `performance/default/{technique}` rename now that the new
  layout is live. Same marker-file pattern, but a separate marker
  (`.performance_migrated_v19_2`) so a 19.1-completed deployment
  picks up the 19.2 rename on the next boot.
- [ ] Tests: `tests/test_runtime_engine.py` — sub-account fan-out
  (one default sub-account: behaviour bytewise unchanged); cap
  rejection log includes `sub_account_id=default`; per-sub-account
  trader isolation (fake registry with two stub sub-accounts to
  pin the routing seam even though 19.3 hasn't lit it up yet).
  `tests/test_strategy_performance.py` — record routing under
  `{sub_account_id}/{technique_name}`. `tests/test_trading_portfolio.py`
  — snapshot routing. ~20 net new tests.

### 19.3 Multi-Paper-Account Support + YAML Config + Dashboard

**Background**: 19.2 leaves the registry capable of holding N
sub-accounts, but the only producer is the single-default
materialiser. 19.3 turns on the multi-account producer: a YAML
config file at `config/sub_accounts.yaml` parsed into N
`SubAccount` entries; the dashboard surfaces per-sub-account equity
curves and a selector. Strategy whitelisting is now end-to-end
operative — a sub-account with `strategy_filter: [chasulang_ict_smc,
rsi_4h]` will see only those two strategies' proposals, while a
sibling sub-account with `null` keeps the all-strategies behaviour.
Live mode is deliberately NOT enabled for multi-account in 19.3 —
the multi-credentials machinery comes in 19.4 and gates live
expansion. Multiple paper sub-accounts become operative immediately;
multiple live sub-accounts are explicitly rejected at registry-load
time.

**Related Requirements**: FR-036 (Capital Isolation — multi-paper
becomes the first observable manifestation), FR-038 (Strategy-
Combination — paper-mode runtime support; backtest harness in 19.5),
FR-013 (User Accept/Reject — auto-approval threshold can now be
overridden per sub-account), NFR-003 (Streamlit UI — dashboard
surface).

- [ ] `config/sub_accounts.yaml.example` — operator-facing template
  with three commented examples (1) `default` paper-mode all-
  strategies, (2) `btc_only` paper-mode `strategy_filter` =
  [chasulang_ict_smc, rsi_4h], (3) `experimental` paper-mode with
  tighter `risk_overrides.risk_percent: 0.5` and
  `max_open_positions_total: 1`.
- [ ] `src/trading/sub_account_registry.py` — when YAML present,
  parse + validate every entry through the Pydantic model; on parse
  failure raise `SubAccountConfigError` at startup (silent fallback
  would leak risk). Reject `mode: live` for any sub-account whose
  `id != "default"` with a `Phase 19.4 not landed` error message
  pointing at the planned migration. Reject duplicate `id`s,
  reject conflicting `exchange_ref` references that don't resolve
  to a credential set.
- [ ] `src/dashboard/pages/trading.py` — sub-account selector at
  top (`st.selectbox` with `default` first; "Aggregate" option
  sums across all active). Equity-curve panel switches data source
  by selection. Active-positions and recent-trades tables filter
  by selection. Aggregate path renders side-by-side comparative
  view of equity curves (one trace per sub-account).
- [ ] `src/dashboard/pages/engine.py` — per-sub-account cycle
  metrics card; aggregate row sums the totals.
- [ ] `src/proposal/notification.py` — every notifier's payload
  gets `sub_account_id` in the headline + structured detail
  (Slack `text`, Telegram body, email subject suffix `[<id>]`).
  Per-sub-account routing override (e.g. `experimental` →
  `slack_webhook_url_experimental`) deferred as a 19.x follow-up
  (capture as DEBT-XXX in seal).
- [ ] `scripts/auto_research_candidates.py` — `--sub-account` flag
  defaults to `default`; resulting `CandidateRecord` carries the
  sub-account into `loop.propose_new`.
- [ ] Tests: parser happy path (3 sub-accounts), live-on-non-
  default rejected, duplicate-id rejected, exchange-ref-unresolved
  rejected, dashboard selector smoke (AppTest), notifier payload
  carries `sub_account_id`. ~15 net new tests.

### 19.4 Multi-Credential Live Mode

**Background**: 19.3 explicitly walls off multi-account live. 19.4
opens it. The blocker is credentials: each sub-account's `LiveTrader`
has to operate against its own API key set, and the current
`Settings.binance` / `Settings.bybit` shape only carries one of each.
The fix is a flat enumerated dict — `Settings.exchange_credentials:
dict[str, ExchangeConfig]` keyed by `exchange_ref` (e.g.
`binance_main`, `binance_alt`) — populated from env vars following
`EXCHANGE_<REF>_API_KEY` / `EXCHANGE_<REF>_API_SECRET` /
`EXCHANGE_<REF>_TESTNET`. Existing single-creds env vars
(`BINANCE_API_KEY`, `BYBIT_API_KEY`) are honoured as
`exchange_credentials["binance_main"]` / `["bybit_main"]` aliases so
existing deployments work unchanged. A live sub-account whose
`exchange_ref` doesn't resolve is a startup failure, not a silent
degrade — the cost of a wrong-credential live trade is not
recoverable.

**Related Requirements**: FR-037 (Multi-Exchange-Account Support —
the central deliverable), FR-009 (Live Trading Mode — extending the
fill boundary to multi-cred), NFR-011 (API Key Protection — every
ref's secrets stay in env), NFR-012 (Live Trading Confirmation — the
auto-approval threshold gate is now per-sub-account).

- [ ] `src/config.py::Settings` — new `exchange_credentials:
  dict[str, ExchangeConfig]` field. Pydantic `model_validator(mode=
  "after")` parses env vars matching `EXCHANGE_<REF>_*` and merges
  with legacy `binance` / `bybit` aliases under canonical keys
  `binance_main` / `bybit_main`. Conflict (legacy + explicit
  `EXCHANGE_BINANCE_MAIN_*`) is a validation error.
- [ ] `src/trading/sub_account_registry.py` — `get_trader(id)` for
  live sub-accounts constructs / caches a `LiveTrader` per
  `exchange_ref` lazily. Missing credentials at registry-load time
  for any `enabled and mode == "live"` sub-account raises
  `MissingExchangeCredentialsError` (does NOT silently demote to
  paper; does NOT defer to first-use error — fail loud at boot).
- [ ] `src/main.py::build_trader` — split into `build_traders(
  registry, settings) -> dict[str, Trader]` returning per-sub-account
  traders; the registry owns the dict.
- [ ] `src/runtime/engine.py` — auto-approval threshold gate
  (`EngineConfig.auto_approve_threshold`) gains an optional
  per-sub-account override sourced from the sub-account's risk
  profile. Phase 18.1 stale-quote sanity gate is per-sub-account
  (each `LiveTrader` fetches the ticker via its own exchange
  client; hands back to engine through the same path).
- [ ] `.env.example` — document the `EXCHANGE_<REF>_*` schema with
  a worked two-account example. `docs/deployment.md` gains a
  "Multi-Account Live" section with the operator checklist
  (separate API keys, separate IP whitelisting, separate
  margin-mode configuration on the exchange dashboard).
- [ ] Tests: env-parsing happy path (2 credential sets), legacy
  `BINANCE_API_KEY` aliasing, conflict rejection, missing-creds-
  for-live-sub-account rejected at load time, per-sub-account
  `LiveTrader` isolation (fake exchange creds, assert each trader
  uses its own). Phase 18.1 sanity-gate routing per sub-account.
  ~18 net new tests.

### 19.5 Strategy-Combination A/B Backtest Harness

**Background**: With per-sub-account everything in flight (19.1–
19.4), strategy-combination A/B testing is the natural payoff. A
single backtest run can drive N sub-accounts in lockstep over the
same OHLCV stream and emit a comparative report. Today's backtester
(`src/backtest/`) is single-strategy; 19.5 adds a thin orchestration
layer that pre-loads the OHLCV window once, then per-tick fans out
to each sub-account's whitelisted strategies, each consuming its
own risk overrides and balance, and accumulates per-sub-account
trade ledgers. Output is `MultiAccountReport` with per-sub-account
equity curve + `PerformanceAnalyzer` summary + pairwise correlation
of returns. The robustness gate (Phase 5.4) is reused per
sub-account; the gate's pass/fail bubbles up to the report.

**Related Requirements**: FR-038 (Strategy-Combination A/B
Backtesting — the central deliverable), FR-025 (Backtesting
Execution — extends the engine to multi-account), FR-027
(Technique Adoption — improver/feedback can now operate on the
report), FR-034 (Robustness Validation Gate — reused per sub-
account).

- [ ] `src/backtest/harness.py` — `BacktestHarness.run_sub_accounts(
  sub_accounts: list[SubAccount], ohlcv_by_symbol_tf: dict[...],
  strategies: dict[str, BaseStrategy]) ->
  MultiAccountReport`. Pre-loads the OHLCV window once;
  per-bar dispatch fans out per sub-account; each sub-account's
  trade ledger accumulates independently. Risk overrides and
  initial-balance per sub-account are honoured.
- [ ] `src/backtest/multi_account_report.py` — `MultiAccountReport`
  Pydantic model: `per_sub_account: dict[str, PerformanceSummary]`,
  `equity_curves: dict[str, list[tuple[datetime, Decimal]]]`,
  `pairwise_correlation: dict[tuple[str, str], float]`,
  `merged_trade_ledger: list[TradeHistory]` (each carrying its
  `sub_account_id`).
- [ ] `scripts/backtest_combinations.py` — operator entry point
  `python -m scripts.backtest_combinations
  --config config/combinations/<name>.yaml --window 90d`. YAML
  schema is a list of sub-accounts (same shape as Phase 19.3's
  `config/sub_accounts.yaml`). Output: `data/backtest/
  combinations/<run_id>/{report.json, equity_curves.png,
  trades.csv}`.
- [ ] `src/dashboard/pages/strategies.py` — link to the latest
  combinations run (if `data/backtest/combinations/` non-empty);
  side-by-side equity-curve viewer.
- [ ] Robustness-gate routing: extend `RobustnessGate` to accept
  a list of sub-accounts when called via the harness; report
  per-sub-account verdicts in the multi-account summary.
- [ ] Tests: 2-sub-account lockstep harness over a 90-day synthetic
  window — sub-A whitelists `[rsi_4h]`, sub-B whitelists
  `[chasulang_ict_smc]`, equal initial balance, assert per-sub-
  account ledger + equity curve are independent and the merged
  ledger preserves sub-account attribution. Pairwise-correlation
  computation. Robustness-gate-per-sub-account routing.
  Operator-script smoke (YAML parse → harness call → report
  serialisation). ~22 net new tests.

---

## Phase 20: Trading-Math Correctness Sweep

**Goal**: Close the leverage double-application that the 2026-04-30
3-agent comprehensive audit surfaced (DEBT-024, High). The
backtester's `calculate_position_size` already returns a leverage-
neutral notional, then the per-trade PnL writer multiplies the trade
PnL by `leverage` again — every Phase 5.4+ baseline figure
(absolute PnL, drawdown in USDT, MDD-in-USDT) is inflated by the
leverage multiplier (typically 5×–10×). `Portfolio.calculate_unreali
zed_pnl` follows the same shape; `PaperTrader` records realized PnL
without the second multiplication, so backtest and paper-trader
ledgers carry divergent conventions and are not directly comparable.
Sharpe / hit-rate are scale-invariant and therefore robustness-gate
verdicts are preserved, but operator-facing absolute-magnitude
numbers mislead by the multiplier. Phase 20 picks one canonical
convention (recommended: leverage already baked into position size,
backtester / portfolio drop the second multiplication, paper-trader
shape is the reference), extracts a single helper, fixes both
ledgers, and re-runs every persisted baseline.

### 20.1 PnL Convention Single Source — Leverage No Double-Apply

**Background**: DEBT-024 (High) traced the leverage double-
application across two ledgers. Phase 20.1 picks the canonical shape
(leverage already in position size; PnL = `(exit - entry) * qty`
with sign-by-side; no second multiplication) and lifts the helper
into a single module so backtester, portfolio, and paper-trader all
go through it. The mathematical change is one removal in two files;
the discipline change is "every PnL site goes through the helper".

**Related Requirements**: FR-006 (Risk/Reward Calculation —
correctness boundary on the per-trade PnL math), FR-025 (Backtesting
Execution — backtester PnL must match operator expectations),
NFR-001 (operational maturity — single source of truth for a
trading-math primitive). Extending existing requirements; no new
FR/NFR introduced.

- [x] `src/utils/trading_math.py` — new module. `pnl_for_trade(entry:
  Decimal, exit: Decimal, qty: Decimal, side: TradeSide) -> Decimal`
  helper. Computes `(exit - entry) * qty` for longs, `(entry - exit)
  * qty` for shorts. Leverage is NOT a parameter — the qty already
  reflects the levered notional from `calculate_position_size`.
  Module-level unit tests pin both signs.
- [x] `src/backtest/engine.py:783-794` — drop the `pnl *= leverage`
  line in the per-trade PnL writer; route through
  `pnl_for_trade(...)` from the helper module.
- [x] `src/trading/portfolio.py:245-247` — replace the `* leverage`
  in `calculate_unrealized_pnl` with `pnl_for_trade(...)` against
  the current mark price.
- [x] `src/trading/paper.py` — already correct shape; route the
  realized-PnL site through `pnl_for_trade(...)` for symmetry (no
  behaviour change).
- [x] Regression test — `tests/test_utils_trading_math.py` pins the
  helper; `tests/test_backtest_engine.py` adds a fixture asserting
  backtester and paper-trader produce identical PnL on a (entry,
  exit, qty, leverage) fixture (today they diverge by `× leverage`).
- [x] Write unit tests.

### 20.2 Backtest / Portfolio Leverage Math Alignment

**Background**: 20.1 lands the helper and the math fix. 20.2 sweeps
every PnL surface in the codebase to confirm no other call site
applies leverage at PnL time. `BacktestTrade.pnl` field semantics,
`Portfolio.unrealized_pnl` field semantics, and dashboard cards
that consume them all need a docstring update naming the new
convention so future contributors don't reintroduce the bug.

**Related Requirements**: FR-006, FR-025, NFR-001 (extending
existing requirements; no new FR/NFR introduced).

- [x] `grep -rn "leverage" src/backtest/ src/trading/` — audit
  every `* leverage` / `/ leverage` / `leverage *` occurrence;
  classify as (a) position-sizing math (correct, keep) or
  (b) PnL math (must go through `pnl_for_trade`). Document each
  in the sub-task PR description.
- [x] `src/backtest/engine.py::BacktestTrade.pnl` field —
  docstring naming the convention ("PnL is computed against
  leveraged notional via `pnl_for_trade`; do not re-multiply by
  `leverage` downstream").
- [x] `src/trading/portfolio.py::Portfolio.unrealized_pnl` field
  — same docstring convention.
- [x] Dashboard `src/dashboard/pages/trading.py` Current-Equity
  card prose — verify the unrealized-PnL delta reads cleanly
  post-fix (no caption rewording expected; mostly a smoke check).
- [x] Write unit tests.

### 20.3 Phase 5.4+ Baseline Re-computation — DEFERRED (mis-framed; see DEBT-043)

**Status**: ⏸ Deferred 2026-05-01. Senior-developer surfaced three
hard blockers that invalidate the "mechanical re-run" framing:

1. **`scripts/backtest_baselines.py` calls live Binance mainnet**
   (no snapshot mode; module docstring lines 26-30 explicitly says
   so). A re-run today produces non-deterministic output that drifts
   day-to-day with whatever the live OHLCV looks like. Not suitable
   for an autonomous cycle and not idempotent across operators.
2. **No pre-DEBT-024 baseline JSONs exist on disk.**
   `data/backtest/baselines/` is gitignored and absent on this
   checkout; `docs/baselines.md` operator table is `_TBD_` for every
   metric (lines 124-136). There is no inflated-figure artefact to
   restate, so DEBT-029's "operator-facing artefact regeneration"
   has zero current operator impact — the bug existed in the math,
   not in any persisted operator surface.
3. **Spec lists 4 baselines; script ships 5** (`rsi_universal` is
   in `BASELINES` at lines 108-149 but absent from the original
   sub-task brief).

**Reframing**: the work that *does* need to happen is not a
"re-compute" but a first-time, snapshot-pinned, reproducible
baseline run. That is real design work (snapshot dataset format,
gitignore exception, freshness policy, `--snapshot` flag, cross-
operator determinism), not a mechanical re-run, and is split out
into **Phase 25: Snapshot-Pinned Reproducible Baselines** (see
DEBT-043 for the underlying reproducibility debt).

DEBT-029 is closed by reframing — the "post-leverage-fix figures
need restating" assumption was wrong because the figures were
never persisted in the first place. The math fix landed in 20.1 +
20.2 and is verified by the alignment + regression-guard tests.

**Related Requirements**: FR-025. No FR/NFR change.

---

## Phase 21: Time / Timezone Hardening

**Goal**: Close the UTC-naive `datetime` surface that the audit
surfaced (DEBT-025, High). Exchange adapters
(`src/exchange/binance.py`, `src/exchange/bybit.py`) construct
OHLCV / ticker / order timestamps via `datetime.fromtimestamp(ms /
1000)` with no `tz=` argument — host-local tz interpretation.
`JsonlRotator` (`src/runtime/jsonl_rotator.py`) uses
`datetime.now()` (also tz-naive local) to derive the active month
token, so a record written near UTC midnight on a non-UTC host
lands in the wrong month file. Phase 18.1's stale-quote payload
mixes both tz-naive sources. Production on Fly (UTC host) hides
the bug; local development on KST hosts surfaces it as silent
9-hour shifts. A future region change (e.g. `fly regions add nrt`)
silently activates the bug in production.

### 21.1 UTC-Aware Timestamp Helper + Adapter Migration

**Background**: A single helper plus four adapter call-site swaps
closes the largest surface. DEBT-025 names the four
`datetime.fromtimestamp(ms / 1000)` sites in the two adapters;
each gets one-line replacement after the helper is in place.

**Related Requirements**: FR-020 (Historical Chart Data Query —
correctness boundary on the OHLCV timestamp), NFR-007 (Trading
History Storage — timestamps in the trade ledger must be UTC).
Extending existing requirements; no new FR/NFR introduced.

- [x] `src/utils/time.py` — new module. `from_unix_ms(ms: int) ->
  datetime` returning `datetime.fromtimestamp(ms / 1000, tz=UTC)`;
  `now_utc() -> datetime` wrapping `datetime.now(tz=UTC)`. Module-
  level test pins UTC tzinfo on both functions.
- [x] `src/exchange/binance.py` — replace `datetime.fromtimestamp(
  ms / 1000)` at lines 235, 272, 503-505 with
  `from_unix_ms(ms)`. Verify any `timestamp.replace(tzinfo=...)`
  calls downstream stay correct.
- [x] `src/exchange/bybit.py` — same swap at lines 165, 202,
  433-435.
- [x] `_coerce_timestamp` (or equivalent helper that converts
  incoming ms / s timestamps to `datetime`) — normalise to UTC-
  aware return.
- [x] Regression tests — `tests/test_exchange_binance.py` and
  `tests/test_exchange_bybit.py` add a `freeze_time` test running
  under a non-UTC TZ via `time_machine.travel(..., tz_offset=9)`
  and asserting the returned `datetime` carries `tzinfo=UTC` and
  the wall-clock UTC value matches the input ms.
- [x] Write unit tests.

### 21.2 `JsonlRotator` UTC Month Boundary

**Background**: `JsonlRotator` at lines 105 / 180 / 253 uses
`datetime.now()` (tz-naive local) to derive the active-month
token. Records written near UTC midnight on a non-UTC host land
in the wrong month file; readers expecting UTC alignment miss
records or double-count them on month-boundary days. The fix is
mechanical once 21.1's `now_utc()` is in place.

**Related Requirements**: NFR-008 (Asset/PnL History — log
retention rotation must be UTC-stable), NFR-007 (Trading History
Storage — same). Extending existing requirements; no new FR/NFR
introduced.

- [x] `src/runtime/jsonl_rotator.py:105,180,253` — replace
  `datetime.now()` with `now_utc()` from 21.1.
- [x] `JsonlRotator.read_with_retention` (and related readers) —
  audit any timestamp comparison; ensure UTC-aware on both sides
  of the comparison (no naive-vs-aware `TypeError`).
- [x] Regression test — `tests/test_runtime_jsonl_rotator.py`
  freezes time at `2026-04-30T23:30:00+09:00` (Asia/Tokyo) and
  asserts the active-month token is `2026-04` (UTC-month) not
  `2026-05` (local-month).
- [x] Write unit tests.

### 21.3 Stale-Quote Payload Timestamp Coherence

**Background**: Phase 18.1's `_record_stale_quote_rejection`
(`src/runtime/engine.py:653-659`) builds the payload from a mix
of engine-side `datetime.now()` (today: tz-naive) and adapter-
returned candle timestamps (today: tz-naive local). After 21.1 +
21.2 land, both sources become UTC-aware; the rejection payload
needs to consume them coherently. The work is verification +
type-tightening, not new behaviour.

**Related Requirements**: FR-008 (Entry/Take-Profit/Stop-Loss
Setting — stale-quote rejection is a fill-boundary correctness
surface), NFR-012 (Live Trading Confirmation — same). Extending
existing requirements; no new FR/NFR introduced.

- [x] `src/runtime/engine.py::_record_stale_quote_rejection` —
  replace any `datetime.now()` with `now_utc()`; assert the
  candle timestamp pulled from the ticker is UTC-aware before
  passing to the payload.
- [x] Regression test — extends one of the four Phase 18.1
  rejection tests (`test_runtime_engine.py`) with a `freeze_time`
  under non-UTC TZ; assert the rejection event's
  `proposal_entry_timestamp` and `live_price_timestamp` both
  carry UTC tzinfo.
- [x] Write unit tests.

---

## Phase 22: Persistence Atomicity & Liquidation Visibility

**Goal**: Close DEBT-028 (Medium — non-atomic JSON persistence
across `TradeHistoryTracker` / `PortfolioTracker` /
`ProposalHistory` / Phase 18.1 stale-quote rewrite) and DEBT-027
(Medium — paper trader silently zeroes balance instead of
recording liquidation). The atomicity fix matters before Phase
19.2 lands because the sub-account fan-out introduces N
concurrent writers per cycle against the same persistence files.
The liquidation fix closes the paper-vs-live divergence: paper
mode currently absorbs leveraged drawdowns silently, so an
operator using paper to forecast live behaviour sees a softer
risk profile than reality.

### 22.1 Atomic JSON Persistence Helper

**Background**: DEBT-028 names four call sites
(`TradeHistoryTracker`, `PortfolioTracker`, `ProposalHistory`,
`_record_stale_quote_rejection`) all using a load → mutate →
`Path.write_text(json.dumps(...))` shape. Concurrent writers
race; mid-write crashes truncate. A single helper plus one-line
replacements at each site closes the surface.

**Related Requirements**: NFR-006 (Backtesting Result Storage),
NFR-007 (Trading History Storage), NFR-008 (Asset/PnL History)
— atomicity is a storage-correctness boundary across all three.
Extending existing requirements; no new FR/NFR introduced.

- [x] `src/utils/io.py` — new module. `atomic_write_text(path:
  Path, text: str) -> None` writes to `path.with_suffix(path.
  suffix + ".tmp")` then `os.replace(...)` into the destination.
  Atomic on POSIX + Windows. Module-level test pins both happy
  path and the "tmp file present after crash" rollback scenario.
- [x] `src/strategy/performance.py:984-1000` — route
  `TradeHistoryTracker` save through the helper.
- [x] `src/trading/portfolio.py` — route `PortfolioTracker.
  record_snapshot` save through the helper.
- [x] `src/proposal/interaction.py` — route `ProposalHistory.record`
  / `update` saves through the helper. (Plan originally wrote
  `src/proposal/history.py`; `ProposalHistory` actually lives in
  `src/proposal/interaction.py`. Corrected 2026-05-01 by Phase 22.1
  docs-auditor.)
- [x] `src/runtime/engine.py:653-659` —
  `_record_stale_quote_rejection`'s `model_copy` + save sequence
  routes through the helper.
- [x] Regression test — fault-injection test that crashes
  mid-write (mocks the `write_text` to raise after the tmp file
  is written but before `os.replace`); asserts the destination
  is either fully old or fully new (never partial).
- [x] Write unit tests.

### 22.2 Paper Trader Liquidation Visibility

**Background**: DEBT-027 (Medium) — `PaperTrader.close_position`
(`src/trading/paper.py:619` and `:626`) clamps `balance.free =
Decimal("0")` when an exit-fee + loss combo would push free
balance negative. The position closes "successfully" with the
recorded loss capped, no liquidation event emitted, no activity-
log row, no negative-equity record. Operators using paper-mode
to forecast live-mode behaviour see a softer drawdown profile
than they will see live (where the exchange liquidates).

**Related Requirements**: FR-010 (Paper Trading Mode — paper
must reflect live-mode risk events for forecasting parity),
NFR-007 (Trading History Storage — liquidation must persist as
a structured event).

- [x] `src/runtime/activity_log.py::ActivityEventType` — new
  member `LIQUIDATED` with structured-fields contract
  documented in the docstring (`symbol`, `side`, `entry`,
  `exit`, `qty`, `realized_pnl`, `balance_before`,
  `balance_after`).
- [x] `src/trading/paper.py::PaperTrader.close_position` —
  branch on the under-water case: emit the `LIQUIDATED`
  activity event, record the close with the true (negative)
  equity in `TradeHistory`, set the balance to the post-
  liquidation value (negative when leverage > 1; pin the
  convention with the test). `PaperBalance.free` relaxed to
  drop the `ge=0` constraint so the negative equity round-
  trips through pydantic's `validate_assignment`. The
  `PaperTrader.__init__` signature gains optional
  `activity_log` and `auto_deposit_on_liquidation` kwargs;
  `build_trader` in `src/main.py` plumbs both through.
- [x] `EngineConfig.paper_auto_deposit_on_liquidation: bool =
  Field(default=False)` — opt-out flag for the legacy
  balance-clamp behaviour, intended only for testing scenarios
  that need a continuing run after liquidation. Default off
  closes the paper-vs-live divergence. Mirrored as
  `Settings.paper_auto_deposit_on_liquidation` (env-overridable
  via `PAPER_AUTO_DEPOSIT_ON_LIQUIDATION`) and documented in
  `.env.example`.
- [x] Regression test — `tests/test_paper_trading.py` adds
  `test_under_water_close_emits_liquidated_event` and
  `test_under_water_close_records_negative_equity`; the
  legacy clamp behaviour stays available behind the new flag,
  pinned by `test_under_water_close_with_auto_deposit_clamps`.
  Also pins `test_exit_fee_only_shortfall_emits_liquidated_event`
  for the historical line-626 fee-shortfall branch and
  `test_normal_close_does_not_emit_liquidated_event` for the
  happy path.
- [x] Write unit tests.

---

## Phase 23: AIDLC Hygiene Backfill

**Goal**: Close the documentation drift the audit surfaced
(DEBT-037 Low) plus the meta-issue around the duplicate
`Phase 17.2` / `Phase 17.3` numbering. None of this is a code
change; all of it is documentation that operators / new
contributors trip over. The phase batches the items because
each individually is too small for a `/dev-crypto` cycle and the
cumulative drift is real.

### 23.1 AIDLC Hygiene Backfill (sessions / cross-checks / drift)

**Background**: The 3-agent audit surfaced four documentation
gaps: (1) `docs/sessions/` is missing
`2026-04-30-phase-17.2-portfolio-snapshot-recording.md` and
`2026-04-30-phase-17.3-closed-trade-performance-records.md` for
the two shipped commits (`094a79d`, `ab9dc32`); (2)
`docs/cross-checks/` is missing the Phase 15 cross-check (Phase
15 sealed in change-history but no cross-check file written);
(3) `CLAUDE.md`'s project-structure tree omits `src/runtime/`
and `src/tools/`; (4) `DESIGN.md §2.3` references a
`ClaudeClient` class but the actual code is `ClaudeCLI`.
DEBT-037 carries the full surface; this sub-task lands the fixes
in one pass.

**Related Requirements**: NFR-001 (operational maturity —
docs reflect code). Extending existing requirements; no new
FR/NFR introduced.

- [x] `docs/sessions/2026-04-30-phase-17.2-portfolio-snapshot-
  recording.md` — back-fill from commit `094a79d` body. Match
  existing session-log format (Cycle / Phase header /
  files-changed / test-count delta / qa verdict).
- [x] `docs/sessions/2026-04-30-phase-17.3-closed-trade-
  performance-records.md` — back-fill from commit `ab9dc32`
  body. Same format.
- [x] `docs/cross-checks/2026-04-28-phase-15-diagnostic-
  clarity.md` — back-fill the Phase 15 cross-check (single
  sub-task only; light document). Cross-reference the change-
  history row.
- [x] `CLAUDE.md` — add `src/runtime/` (engine, activity_log,
  audit_log, jsonl_rotator) and `src/tools/` (operator scripts)
  to the project-structure tree.
- [x] `DESIGN.md §2.3` — rename `ClaudeClient` → `ClaudeCLI`
  end to end; verify the ADR list also matches.
- [x] No tests — documentation-only sub-task. (Lint pass on
  Markdown if the project has one; otherwise visual review.)

### 23.2 Phase 17.2 / 17.3 Numbering Reconciliation

**Background**: `git log` shows two commits using each of the
labels `Phase 17.2` (`094a79d` portfolio snapshot, then later
`41f9212` auto-research workflow unblock) and `Phase 17.3`
(`ab9dc32` closed-trade performance, then later the auto-
research code-type steering planned spec). The dev-plan status
table and sub-task headers were updated in this cycle to:
shipped portfolio-snapshot → 17.2; shipped performance-record
→ 17.3; auto-research unblock spec → 17.4 (already shipped per
change-history, marked complete); code-type steering spec →
17.5 (still missing). Phase 23.2 is the audit pass that locks
this in: change-history rows reconciled, the conflicting
`Phase 17.2 added` / `Phase 17.2 complete` rows reconciled
with the new numbering, and a single back-fill change-history
row added explaining the rebrand.

**Related Requirements**: NFR-001 (operational maturity —
change-history accuracy). Extending existing requirements; no
new FR/NFR introduced.

- [x] Audit `docs/development-plan.md` change-history table for
  rows referencing `Phase 17.2` / `Phase 17.3`; tag each row
  with its post-rebrand number (17.2 portfolio, 17.3
  performance, 17.4 auto-research unblock, 17.5 code-type
  steering). Multiple rows may need an erratum-style
  parenthetical noting the original number.
- [x] Add a single change-history row dated 2026-05-01
  documenting the rebrand: "Phase 17.2 / 17.3 renumbered:
  shipped portfolio-snapshot recording (commit `094a79d`) is
  formal Phase 17.2; shipped closed-trade performance records
  (commit `ab9dc32`) is formal Phase 17.3; previously-spec'd
  Auto-Research Unblock and Code-Type Steering renumbered to
  17.4 / 17.5".
- [x] Verify the `Requirements Mapping` row for Phase 17 lists
  every FR/NFR consumed across 17.1–17.5.
- [x] No tests — documentation-only sub-task.

---

## Phase 24: Strategy Robustness Polish

**Goal**: Batch the Low-priority correctness items the audit
surfaced where each individually is too small for a phase but
the cumulative effect on per-strategy metrics is real. The
batch closes DEBT-030 (intra-trade MDD), DEBT-031 (MA-crossover
SL window), DEBT-032 (OOS gate IS-sample-size guard), DEBT-033
(stale-quote ticker freshness threshold), and DEBT-034 (cold-
start technique selection). All five are isolated to a single
file each; the cumulative test surface is small.

### 24.1 Strategy Robustness Polish

**Background**: Five Low-priority debts share the "isolated
correctness improvement" shape. Each has a one-or-two-line code
change and a regression test. Bundling avoids five separate
`/dev-crypto` cycles. Sequencing within the sub-task is
arbitrary; recommended order is dependency-order
(MDD analyzer first, since later items don't read from it).

**Related Requirements**: FR-005 (Performance Tracking —
intra-trade MDD), FR-008 (Stop-Loss Setting — MA-crossover SL
correctness), FR-025 (Backtesting Execution — OOS gate
sample-size guard), FR-013 (User Accept/Reject — stale-quote
ticker freshness for accept/reject decisions). Extending
existing requirements; no new FR/NFR introduced.

- [x] DEBT-030: `src/backtest/analyzer.py:251-315` — replace
  the closed-trade equity curve with a per-bar equity curve
  (mark open positions to market each bar). Regression test on
  a long-hold scenario pins the new MDD floor below the
  closed-trade-only value.
- [x] DEBT-031: `strategies/ma_crossover.py:85,94` — roll the
  SL window back by one bar (`df.iloc[i-period:i]` rather than
  `df.iloc[i-period+1:i+1]`); regression test fixture fires on
  the silent-drop case and asserts the trade is emitted.
- [x] DEBT-032: `src/backtest/validator.py:409-420` — add
  `minimum_is_trades: int = 5` config field; when IS trade
  count is below floor, mark OOS gate `SKIPPED` (consistent
  with sensitivity-gate-skip pattern from DEBT-014); surface
  the SKIP in the gate verdict.
- [x] DEBT-033: `src/runtime/engine.py:557-571` — add
  `EngineConfig.max_ticker_age_seconds: float = 10.0`; check
  the ticker `timestamp` against `now_utc()` (post-Phase 21);
  fall through with the same WARN as the exception path when
  the ticker is older than the threshold.
- [x] DEBT-034: `src/proposal/engine.py:655-659` — minimum-
  sample guard: if no technique has ≥ N samples, skip the
  proposal entirely in live mode (return no proposal); paper
  mode falls through to the alphabetical default (cold-start-
  tolerant). Pin both branches with tests.
- [x] Write unit tests.

---

## Phase 25: Snapshot-Pinned Reproducible Baselines

**Goal**: Replace the live-Binance dependence in
`scripts/backtest_baselines.py` with a snapshot-pinned dataset
so baselines are reproducible across operators / days. Closes
DEBT-043 (the reproducibility debt re-scoped out of DEBT-029
when Phase 20.3 was deferred — see Phase 20.3's footnote).
Once the snapshot-pinned regenerator ships, run the baselines
for the first time post-DEBT-024 fix (the 20.1 + 20.2 math
cleanup) and populate `docs/baselines.md`'s operator table,
which has stayed `_TBD_` since the file was created.

The script today calls live Binance mainnet with no snapshot
mode (module docstring lines 26-30; live-exchange construction
lines 511-518), so a re-run produces non-deterministic output
that drifts day-to-day with whatever the live OHLCV looks
like. That's not suitable for reproducible operator artefacts
or autonomous cycles. The fix is a snapshot-pinned dataset
(CSV check-in or fixture format), a `--snapshot <path>` CLI
flag, a freshness policy for refreshing the snapshot, and a
gitignore exception for the snapshot files.

### 25.1 Snapshot Dataset + Format

**Background**: Pick the snapshot format (CSV, parquet, JSONL),
decide what gets persisted (per-symbol per-timeframe OHLCV +
fetch metadata: source URL, fetch timestamp, candle count),
gitignore exception path, freshness policy (e.g. "snapshot is
valid for 90 days; refresh requires operator opt-in"). Land
the empty-directory + format spec + format-validation tests
before the script changes touch any production code.

**Related Requirements**: FR-025 (extending; no new FR/NFR).

- [x] Snapshot directory layout under `data/backtest/snapshots/`
  with per-(symbol, timeframe) subdirectories.
- [x] Snapshot file format spec (header schema, OHLCV row
  schema, fetch-metadata sidecar).
- [x] `.gitignore` exception so snapshot files are committed
  (the whole point is reproducibility — they must travel with
  the repo).
- [x] Freshness policy documented (refresh cadence + opt-in
  refresh command).
- [x] Format-validation test on a synthetic snapshot fixture.
- [x] Write unit tests.

### 25.2 CLI `--snapshot` Flag + Script Changes

**Background**: Add the `--snapshot <path>` flag to
`scripts/backtest_baselines.py`; route the OHLCV fetch through
the snapshot loader instead of `BinanceExchange.get_ohlcv`
when the flag is set; keep the live-fetch path as the
explicit "refresh snapshot" mode behind a separate
`--refresh-snapshot` flag that writes to the snapshot
directory and is operator-gated.

**Related Requirements**: FR-025 (extending; no new FR/NFR).

- [x] `scripts/backtest_baselines.py` — `--snapshot` flag
  parses snapshot path; default snapshot path under
  `data/backtest/snapshots/baselines/`.
- [x] Snapshot loader replaces the live OHLCV fetch when
  `--snapshot` is set; freshness check fails loud if the
  snapshot's fetch timestamp is older than the policy's
  ceiling.
- [x] `--refresh-snapshot` flag writes a fresh snapshot from
  live (operator-gated; the only path that touches mainnet).
- [x] Cross-operator determinism test: same snapshot → same
  baseline numbers byte-for-byte.
- [x] Reconcile the spec-vs-script baseline-list drift (spec
  said 4, script ships 5 — `rsi_universal` extra). Either
  fold `rsi_universal` into the documented set or drop it
  from `BASELINES`; document the decision.
- [x] Write unit tests.

### 25.3 First Run + Populate `docs/baselines.md`

**Background**: With the snapshot-pinned regenerator in place,
run the baselines for the first time post-DEBT-024 fix
(20.1 + 20.2 math cleanup) and populate `docs/baselines.md`'s
operator table, which has stayed `_TBD_` since the file was
created. This is the operator-facing closure of the
reproducibility story.

**Two-part split** (lead, 2026-04-30): the original spec assumed
a single autonomous cycle, but the first-run step requires
fetching live Binance OHLCV which is an operator-only action.
25.3 split into:

- **Part A (autonomous)**: prepare `docs/baselines.md` operator
  table structure + freshness-window guidance + per-baseline row
  template + operator runbook for the first fetch. No live data
  needed. Phase 25 seals **partially** at 25.3 Part A — the
  snapshot infrastructure (25.1 + 25.2) and operator runbook
  (25.3 Part A) are autonomous-complete; the actual numbers
  require a one-time operator action to land.
- **Part B (operator action, follow-up)**: operator runs
  `--refresh-snapshot` then `--snapshot ...` to fetch live data
  and rewrite the table cells. Tracked as a post-seal operator
  to-do, not a future phase.

**Related Requirements**: FR-025 (extending; no new FR/NFR).

Part A — autonomous (this sub-task):

- [x] Restructure `docs/baselines.md` operator table with all 5
  baselines (`rsi_universal`, `rsi_4h`, `rsi_15m`,
  `bollinger_band_reversion`, `ma_crossover`). Placeholder token
  remains the legacy marker — semantically "awaiting operator
  first run" — because the rewriter and its tests assert that
  literal string pre-rewrite; renaming is deferred as Low-priority
  TECH-DEBT (see senior-developer report). Column shape kept at
  the legacy 6-column shape for the same reason (rewriter is
  hard-wired); widening to the 9-column spec'd shape is also
  Low-priority TECH-DEBT.
- [x] Document the 30-day active-use window vs the 90-day
  absolute stale ceiling so operators understand the freshness
  gate (carry-over from 25.2).
- [x] Add operator runbook section: env-vars → refresh-snapshot
  → verify directories → snapshot run → commit.
- [x] Add reproducibility note explaining cross-operator byte
  equality (modulo `run_id` / `trade_id` UUIDs).
- [x] Change-history row noting Part A complete / Part B awaiting
  operator.

Part B — operator action (post-seal, not blocking the seal):

- [ ] **Operator**: Run `python -m scripts.backtest_baselines
  --refresh-snapshot --snapshot-root data/backtest/snapshots/`
  to fetch live Binance OHLCV and persist the snapshot dataset.
- [ ] **Operator**: Run `python -m scripts.backtest_baselines
  --snapshot data/backtest/snapshots/` for each baseline against
  the committed snapshot.
- [ ] **Operator**: Persist `result.json` / `analysis.md` /
  `summary.json` per baseline under `data/backtest/baselines/`.
- [ ] **Operator**: Populate `docs/baselines.md`'s operator
  table (replace every `_AWAITING_OPERATOR_FIRST_RUN_` with the
  snapshot-pinned figure; the script does this in place).
- [ ] **Operator**: Commit the snapshot directory + the
  resulting `data/backtest/baselines/` artefacts + the rewritten
  `docs/baselines.md`.

No code changes for Part A — this is a docs-only sub-task. No
new tests required (Part A surfaces only documentation changes;
the snapshot infrastructure tests landed with 25.1 + 25.2).

---

## Requirements Mapping

| Phase | Related Requirements |
|-------|---------------------|
| Phase 1 | NFR-001, NFR-004, NFR-005 |
| Phase 2 | FR-016, FR-017, FR-018, FR-019, FR-020, NFR-009 |
| Phase 3 | FR-001, FR-002, FR-003, FR-004, FR-005, NFR-002, NFR-005, NFR-007, NFR-008, NFR-010 |
| Phase 4 | FR-006, FR-007, FR-008, FR-009, FR-010, NFR-012 |
| Phase 5 | FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, FR-027, FR-033, FR-034, FR-035, NFR-006 |
| Phase 6 | FR-011, FR-012, FR-013, FR-014, FR-015 |
| Phase 7 | FR-028, FR-029, FR-030, FR-031, FR-032, NFR-003 |
| Phase 8 | FR-009, FR-010, FR-013, FR-014, FR-015, FR-026 (production wiring of existing requirements; no new FR/NFR introduced) |
| Phase 9 | FR-001, FR-002, FR-003 (extending the strategy framework's input contract; no new FR introduced) |
| Phase 10 | FR-005, FR-009, FR-010, FR-012, FR-025, NFR-004, NFR-008, NFR-012 (production wiring + operator tooling for previously-shipped requirements; no new FR/NFR introduced) |
| Phase 11 | FR-005, FR-015, NFR-001, NFR-008, NFR-012 (operational hardening + observability — lint/type sweep, OHLCV cache, Slack notifier, `purge_old` wiring; no new FR/NFR introduced) |
| Phase 12 | FR-006, FR-007, FR-008, FR-015, FR-022, NFR-001, NFR-012 (risk hardening + reliability — cross-cycle position cap, residual mypy sweep, LLM timeout retry/fallback, Telegram notifier; no new FR/NFR introduced) |
| Phase 13 | FR-015, FR-020, NFR-001, NFR-004, NFR-012 (cleanup + operational polish — DEBT-009/010/011 batch, EngineConfig remaining-fields env override, `BaseExchange.get_ohlcv` `since` param, email notifier; no new FR/NFR introduced) |
| Phase 14 | FR-015, FR-022, NFR-001 (production reliability — chasulang per-strategy Claude CLI timeout override + retry observability, SMTP_SSL alternative for `EmailNotifier`; no new FR/NFR introduced) |
| Phase 15 | NFR-001 (diagnostic clarity — proposal-sizing log rename, dashboard threshold-rejection count; no new FR/NFR introduced) |
| Phase 16 | FR-022, NFR-001 (chasulang stability — JSON parse path now accepts nested `trade.signal`, subprocess wedge mitigation; no new FR/NFR introduced) |
| Phase 17 | FR-022, FR-023, FR-025, FR-026, FR-034, NFR-001, NFR-008, FR-005, FR-021, FR-031, CON-003 (operator-driven strategy-evolution workflow — catalog-aware idea generation + auto-research script landing candidates in `AWAITING_APPROVAL` (17.1); portfolio snapshot recording in runtime cycle wiring `PortfolioTracker.record_snapshot` end-to-end + dashboard Current Equity card (17.2; FR-031, NFR-008); closed-trade `PerformanceRecord` persistence wiring `PerformanceTracker.save_record` end-to-end + dashboard per-technique aggregates (17.3; FR-005, FR-021); runtime JSON contract + backtest circuit breaker resolving DEBT-019's 9-hour hang on prompt-type generations (17.4; FR-022, FR-023, FR-025, NFR-001); code-type steering for deterministic catalog picks (17.5; FR-023, FR-025, NFR-001 — still missing); no new FR/NFR introduced) |
| Phase 18 | FR-005, FR-008, FR-013, FR-021, FR-025, NFR-001, NFR-012 (live-trading quality — 18.1 stale-quote sanity gate at proposal fill enforces SL + slippage tolerance against a fresh ticker; 18.2 trade-quality diagnostic measurement pass over the closed-trade ledger to attribute losses before any further engine-knob edit; extending the fill boundary + performance-tracking + analysis-report contracts, no new FR/NFR introduced) |
| Phase 19 | FR-036, FR-037, FR-038, FR-005, FR-009, FR-013, FR-025, FR-027, FR-034, NFR-003, NFR-007, NFR-008, NFR-011, NFR-012 (sub-account / capital segmentation — N independent capital pools per mode, multi-credential live, strategy-combination A/B backtests; introduces FR-036 / FR-037 / FR-038) |
| Phase 20 | FR-006, FR-025, NFR-001 (trading-math correctness sweep — leverage no-double-apply across backtester / portfolio / paper-trader, single `pnl_for_trade` helper, Phase 5.4+ baseline re-computation post-DEBT-024; no new FR/NFR introduced) |
| Phase 21 | FR-020, NFR-007, NFR-008, NFR-012 (time / timezone hardening — UTC-aware `from_unix_ms` helper across exchange adapters, `JsonlRotator` UTC-month boundary, stale-quote payload tz coherence; resolves DEBT-025; no new FR/NFR introduced) |
| Phase 22 | FR-010, NFR-006, NFR-007, NFR-008 (persistence atomicity — `atomic_write_text` helper across `TradeHistoryTracker` / `PortfolioTracker` / `ProposalHistory` / Phase 18.1 stale-quote rewrite (resolves DEBT-028); paper-trader liquidation visibility — `LIQUIDATED` activity event + negative-equity record (resolves DEBT-027); no new FR/NFR introduced) |
| Phase 23 | NFR-001 (AIDLC hygiene backfill — sessions for shipped 17.2 / 17.3 (23.1), Phase 15 cross-check (23.1), `CLAUDE.md` tree (23.1), `DESIGN.md` ClaudeClient → ClaudeCLI rename (23.1), Phase 17.2 / 17.3 / 17.4 / 17.5 numbering reconciliation (23.2, including renaming the existing 17.2 auto-research-unblock session log to 17.4); resolves DEBT-037; no new FR/NFR introduced) |
| Phase 24 | FR-005, FR-008, FR-013, FR-025, NFR-001 (strategy robustness polish — intra-trade MDD (DEBT-030), MA-crossover SL window (DEBT-031), OOS gate IS-sample-size guard (DEBT-032), stale-quote ticker freshness threshold (DEBT-033), cold-start minimum-sample guard (DEBT-034); no new FR/NFR introduced) |
| Phase 25 | FR-025 (snapshot-pinned reproducible baselines — replace live-Binance dependence in `scripts/backtest_baselines.py` with a snapshot-pinned dataset so baselines are reproducible across operators / days; closes DEBT-043; first run post-DEBT-024 fix populates `docs/baselines.md` operator table; extends FR-025, no new FR/NFR introduced) |

---

## Change History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-04-05 | Initial creation | Claude |
| 1.1 | 2026-04-05 | Phase 1.1 complete | Claude |
| 1.2 | 2026-04-05 | Phase 1.2 complete | Claude |
| 1.3 | 2026-04-05 | Phase 1.3 complete, Phase 1 complete | Claude |
| 2.1 | 2026-04-05 | Phase 2.1 complete - Exchange Abstraction Layer | Claude |
| 2.2 | 2026-04-05 | Phase 2.2 complete - Binance Integration | Claude |
| 2.3 | 2026-04-05 | Phase 2.3 complete - Bybit Integration | Claude |
| 3.1 | 2026-04-05 | Phase 3.1 complete - Analysis Technique Framework | Claude |
| 3.2 | 2026-04-05 | Phase 3.2 complete - Basic Analysis Technique Implementation | Claude |
| 3.3 | 2026-04-05 | Phase 3.3 complete - Claude Integration | Claude |
| 3.4 | 2026-04-05 | Phase 3.4 complete - Performance Tracking, Phase 3 complete | Claude |
| 3.5 | 2026-04-05 | Phase 3.5 complete - Trade History Enhancement (NFR-007, NFR-008) | Claude |
| 4.1 | 2026-04-05 | Phase 4.1 complete - Trading Strategy Module (FR-006, FR-007, FR-008) | Claude |
| 4.5 | 2026-04-06 | Added Phase 4.5 - Trading Strategy Profiles (technique+profile combinations) | Claude |
| 4.2 | 2026-04-06 | Phase 4.2 complete - Paper Trading Engine (FR-010, NFR-007, NFR-008) | Claude |
| 4.x | 2026-04-06 | Restructured Phase 4: Added 4.2 Exchange Testnet Support, split 4.3 Paper Trading into Local/Testnet/Fees, renumbered Live→4.4, Asset→4.5, Profiles→4.6 | Claude |
| 4.2 | 2026-04-06 | Phase 4.2 complete - Exchange Testnet Support (FR-010, NFR-009, NFR-011) | Claude |
| 4.3 | 2026-04-06 | Phase 4.3 complete - Paper Trading Testnet Integration (FR-010, NFR-007, NFR-008) | Claude |
| 4.3 | 2026-04-10 | Phase 4.3 complete - Paper Trading Fee Simulation (FR-010, NFR-008) | Claude |
| 4.4 | 2026-04-10 | Phase 4.4 complete - Live Trading Engine (FR-009, NFR-007, NFR-008, NFR-012) | Claude |
| 4.5 | 2026-04-10 | Phase 4.5 complete - Asset/PnL Management (NFR-007, NFR-008) | Claude |
| 4.6 | 2026-04-10 | Phase 4.6 complete - Trading Strategy Profiles (FR-005, FR-006, FR-007, FR-008) | Claude |
| 4.0 | 2026-04-10 | Phase 4 complete - all sub-tasks checked | Claude |
| 5.1 | 2026-04-11 | Phase 5.1 complete - Backtesting Engine (FR-025, NFR-006) | Claude |
| 5.2 | 2026-04-13 | Phase 5.2 complete - Performance Analyzer (FR-021, NFR-006) | Claude |
| 5.3 | 2026-04-13 | Phase 5.3 complete - Claude-Based Technique Improvement (FR-022, FR-023, FR-024, NFR-002) | Claude |
| 5.3a | 2026-04-14 | Phase 5.3 prompt redesign - hypothesis-driven generation (FR-033, FR-035); rejects generic indicator mashups; mandatory `hypothesis` frontmatter; Failure Analysis required for improvements | Claude |
| 5.4 | 2026-04-14 | Phase 5.4 complete - Robustness Validation Gate (FR-034); 4 gates: OOS / walk-forward / regime / parameter sensitivity; 18 tests | Claude |
| 5.x | 2026-04-14 | Renumbered prior 5.4 (Automated Feedback Loop) → 5.5 to slot the Robustness Gate before the loop orchestrator | Claude |
| 5.5 | 2026-04-25 | Phase 5.5 complete - Automated Feedback Loop (FR-026, FR-027, FR-034, CON-003); FeedbackLoop orchestrator + JSONL audit log + state persistence; 23 tests | Claude |
| 5.0 | 2026-04-25 | Phase 5 complete - all sub-tasks (5.1–5.5) checked | Claude |
| 6.1 | 2026-04-25 | Phase 6.1 complete - Proposal Engine (FR-011, FR-012); ProposalEngine + Proposal/ProposalScore + composite score formula; 19 tests | Claude |
| 6.2 | 2026-04-26 | Phase 6.2 complete - User Interaction (FR-013, FR-014); format_proposal + default_decision_prompt + ProposalHistory + ProposalInteraction; 22 tests | Claude |
| 6.3 | 2026-04-26 | Phase 6.3 complete - Notification System (FR-015); ConsoleNotifier + FileNotifier (JSONL) + NotificationDispatcher with min_score gate and per-channel failure isolation; 20 tests | Claude |
| 6.0 | 2026-04-26 | Phase 6 complete - all sub-tasks (6.1–6.3) checked | Claude |
| 7.1 | 2026-04-27 | Phase 7.1 complete - Streamlit App Basic Structure (FR-032, NFR-003); src/dashboard/{app,theme}.py + st.navigation chassis + AppTest smoke; 7 tests | Claude |
| 7.2 | 2026-04-27 | Phase 7.2 complete - Analysis Technique Status Page (FR-028, FR-005); src/dashboard/pages/strategies.py with summary table + per-technique cumulative-P&L trend chart; 14 tests | Claude |
| 7.3 | 2026-04-27 | Phase 7.3 complete - Trading Status Page (FR-029, FR-031); src/dashboard/pages/trading.py with paper/live mode toggle, summary metrics, active positions, recent trades, equity curve; 18 tests | Claude |
| 7.4 | 2026-04-27 | Phase 7.4 complete - Feedback Loop Status Page (FR-030); src/dashboard/pages/feedback.py with status summary cards, candidates table, per-candidate detail + audit timeline; 15 tests | Claude |
| 7.0 | 2026-04-27 | Phase 7 complete - all sub-tasks (7.1–7.4) checked; 7.5 Tapbit deferred | Claude |
| 8.0 | 2026-04-27 | Phase 8 added to plan - production runtime + Fly.io deployment (8.1 engine, 8.2 dashboard page, 8.3 Fly packaging) | Claude |
| 8.1 | 2026-04-27 | Phase 8.1 complete - Trading Engine Runtime; src/runtime/{engine,activity_log}.py + src/main.py + ProposalHistory.attach_trade; auto-decide + interruptible loop + JSONL activity log; 26 tests | Claude |
| 8.2 | 2026-04-27 | Phase 8.2 complete - Engine Status Dashboard Page; src/dashboard/pages/engine.py with cycle aggregation + summary cards + recent-cycles table + duration bar chart + filterable timeline; 21 tests | Claude |
| 8.3 | 2026-04-27 | Phase 8.3 complete - Fly.io Deployment; Dockerfile (Python 3.13 + Node 18 + Claude CLI + tini) + start.sh (signal-forwarding two-process supervisor) + fly.toml (single machine, single volume, Streamlit healthcheck) + .dockerignore + docs/deployment.md | Claude |
| 8.0 | 2026-04-27 | Phase 8 complete - all sub-tasks (8.1–8.3) checked | Claude |
| 9.0 | 2026-04-27 | Phase 9 added to plan - framework extensions; 9.1 multi-timeframe strategy support (driven by chasulang_ict_smc dormancy under single-TF contract) | Claude |
| 9.2 | 2026-04-27 | Phase 9.2 added to plan - baseline indicator strategies (RSI 4h, RSI 15m, Bollinger Bands, MA crossover) for LLM-vs-deterministic comparison + degraded-mode safety net | Claude |
| 9.2 | 2026-04-27 | Phase 9.2 complete - Baseline Indicator Strategies (FR-001/002/003/004); src/strategy/indicators.py + strategies/{rsi,bollinger_bands,ma_crossover}.py + docs/baselines.md; 30 tests. Per-timeframe RSI split (rsi_4h/rsi_15m) deferred until Phase 9.1 multi-TF lands | Claude |
| 9.1 | 2026-04-27 | Phase 9.1 complete - Multi-Timeframe Strategy Support (FR-001/002/003); `requires_multi_timeframe` flag on `TechniqueInfo`, `BaseStrategy.analyze` extended with keyword-only `ohlcv_by_timeframe` / `current_price`, `PromptStrategy.format_prompt` fills `{ohlcv_<tf>}` + `{current_price}`, `ProposalEngine` dispatches per-TF fetches; `chasulang_ict_smc` template wakes up. 7 new tests + chasulang smoke. Backtester multi-TF iteration deferred to a follow-up. | Claude |
| 9.3 | 2026-04-27 | Phase 9.3 complete - Multi-Timeframe Backtester (FR-025, FR-027, FR-034); `Backtester.run_multi_timeframe` with bisect-based per-TF slicing + warmup gating across every TF; `Backtester.run_for_strategy` dispatcher; `RobustnessGate` threads `ohlcv_by_timeframe` through OOS / walk-forward / sensitivity gates with no future leakage; `FeedbackLoop` accepts `ohlcv_by_timeframe` end-to-end. 15 new tests across backtester / validator / loop suites. Multi-TF strategies (chasulang) can now reach AWAITING_APPROVAL. | Claude |
| 9.4 | 2026-04-27 | Phase 9.4 complete - Per-Timeframe RSI Baselines (FR-001/002/003/004); strategies/rsi_4h.py + rsi_15m.py reuse RSIMeanReversionStrategy with locked timeframes; rsi.py renamed `rsi_mean_reversion` → `rsi_universal` for symmetry; 6 new tests + docs/baselines.md updated. Closes the user's original "4시간봉 RSI / 15분봉 RSI" request. | Claude |
| 10.0 | 2026-04-27 | Phase 10 added to plan - Operational Maturation; 10.1 Live Trading Wiring, 10.2 EngineConfig Env Override, 10.3 Baseline Reference Numbers, 10.4 Log Retention Policy. Closes accumulated operational gaps from prior-phase session logs. | Claude |
| 10.1 | 2026-04-28 | Phase 10.1 complete - Live Trading Wiring (FR-009, FR-010, NFR-012); introduced `src/trading/base.py::Trader` Protocol; `PaperTrader` open/close converted to async; `LiveTrader` aligned to the protocol (close signature, get_open_trades, check_exit_conditions, SL/TP-skips-confirm); `TradingEngine.trader: Trader` (replaces `paper_trader`); `src/main.py::build_exchange` + `build_trader` dispatch on `Settings.trading_mode`; engine auto-confirmation shim for headless live; `docs/deployment.md` 9-step live checklist. 11 new tests + extensive test churn (~50 PaperTrader call sites converted to async). 1027 total passing. | Claude |
| 10.5 | 2026-04-28 | Phase 10.5 complete - Volume-Aware Default Paths (NFR-008); replicated `PerformanceTracker` / `TradeHistoryTracker` `data_dir` pattern across `ActivityLog`, `AuditLog`, `FeedbackLoop`, `ProposalHistory`, `FileNotifier`, and `Portfolio` (latter already correct, comment added); each `__init__` now accepts a keyword-only `data_dir: Path \| None = None` and derives default storage from `Settings.data_dir` at construction time. Closes the Fly persistence-loss defect Cycle 1 diagnosed: relative `Path("data/...")` defaults resolved to ephemeral `/app/data/...` instead of the `/data` volume mount. 6 new "respects `Settings.data_dir`" tests (1027 → 1033). | Claude |
| 10.6 | 2026-04-28 | Phase 10.6 complete - Multi-Technique Per-Symbol Scan (FR-005, FR-012); `ProposalEngine` now iterates every applicable technique per symbol via sibling `_select_all_techniques` / `_propose_all_for_symbol`; `_dedup_by_symbol` keeps the highest-composite winner per symbol (long+long and long+short conflicts both resolved by symbol-only key); `propose_altcoins` aggregation order is dedup-first-then-top-K to preserve FR-012 diversification; new `multi_technique_per_symbol: bool = True` flag on `ProposalEngineConfig` for backwards-compatible opt-out (legacy `_select_best_technique` kept as live code for op-emergency rollback). Closes the single-strategy lockout Cycle 1 diagnosed: only `bollinger_band_reversion` ever ran on Fly. 7 new tests (1033 → 1040). Quant design-phase review caught 2 🔴 blockers before code was written. | Claude |
| 10.2 | 2026-04-28 | Phase 10.2 complete - EngineConfig Env Override (NFR-004); `Settings.engine_*` fields (`engine_cycle_interval`, `engine_auto_approve_threshold`, `engine_symbols`, `engine_balance`) drive `EngineConfig` in `build_engine`. Defaults bytewise-equal to the pre-10.2 hardcoded values so existing deployments are unchanged without an env setting. `engine_symbols` uses `Annotated[list[str], NoDecode]` + `field_validator(mode="before")` for comma-separated env parsing (operationally natural over JSON literals). `build_engine` explicit-config-wins back-compat preserved. `.env.example` and `docs/deployment.md` updated. 12 new tests (1040 → 1052). 4 remaining `EngineConfig` fields (`monitor_interval_seconds`, `bitcoin_symbol`, `altcoin_top_k`, `actor`) deferred as DEBT-003 (Low). | Claude |
| 10.3 | 2026-04-28 | Phase 10.3 complete - Baseline Reference Numbers (FR-025 consumed; operator tooling); `scripts/backtest_baselines.py` (620 lines) operator script fetches Binance public OHLCV with pagination (>1500 candles needs reaching past `BaseExchange.get_ohlcv` contract via `BinanceExchange._client`), runs `Backtester.run_for_strategy` + `PerformanceAnalyzer` per baseline, persists `result.json` + `analysis.md` + `summary.json` under `data/backtest/baselines/<strategy>/`. Idempotent overwrite. `--no-update-doc` flag. Updates `docs/baselines.md` operator-instructions section + period labels; metric cells stay `_TBD_` until operator runs the script (no synthesised numbers). 6 new smoke tests (1052 → 1058). 1 mypy nit at lines 241/248 + `_client` reach-around recorded as DEBT-004 (Low). | Claude |
| 10.4 | 2026-04-28 | Phase 10.4 complete - Log Retention Policy (NFR-008); new `src/runtime/jsonl_rotator.py` (`JsonlRotator`) wraps append-only JSONL with time-based monthly rotation (`<base>.YYYY-MM.jsonl`) + retention-bounded timestamp-ordered merged reads + corrupt-line tolerance + legacy un-rotated file read-as-oldest-archive (never written). `AuditLog` and `ActivityLog` compose the rotator (`self.path` preserved as `.jsonl`-form for back-compat; trailing-suffix stripped to derive rotator base). `ProposalHistory.purge_old(now, retention_months)` ships as operator-callable age-based archive into `<data_dir>/proposals/archive/<YYYY-MM>/` keyed on the proposal's own creation month — idempotent, no startup hook (deferred). `Settings.log_retention_months: int = 12` (`Field(ge=1)`) + `LOG_RETENTION_MONTHS` env var documented in `.env.example`. 25 new tests (1058 → 1083). No new debt. | Claude |
| 11.1 | 2026-04-28 | Phase 11.1 complete - Pre-Existing Lint/Type Sweep (NFR-001; resolves DEBT-001); cleared all in-scope ruff + mypy errors (18 ruff → 0; 12 in-scope mypy → 0; total mypy 39 → 29 with remainder out-of-scope per spec). In-scope fixes: `src/ai/claude.py` (2 B904 with `from e`), `src/strategy/loader.py` (5 B904), `src/strategy/factory.py` (UP035 `Callable` from `collections.abc`), `src/ai/improver.py` (str-coerce `fm.get(...) or fallback` at parse-time), `src/trading/live.py` (`Order` import + return-type widening + `Literal["buy","sell"]` for closing_side), `src/trading/paper.py` (same Literal fix), `src/backtest/analyzer.py` (`float(...)` cast for no-any-return), 6 test files (F401/F841/I001 cleanup via `ruff --fix`). `pyproject.toml` ruff config migrated from deprecated top-level `select`/`ignore` to `[tool.ruff.lint]`. `types-PyYAML>=6.0` added to dev extras. New `scripts/lint.sh` (uses `--fix` — flagged by qa as unsafe for CI; recorded as DEBT-009). 1083 tests pass (no behaviour change, no new tests). Zero `# noqa` / `# type: ignore` added. Remaining 29 mypy errors clustered in 4 modules (binance / factory / dashboard / main lambda) recorded as DEBT-005 / 006 / 007 / 008. | Claude |
| 11.2 | 2026-04-28 | Phase 11.2 complete - OHLCV Cache for Multi-Technique Scan (FR-005 consumed; resolves DEBT-002); per-call OHLCV cache keyed by `(symbol, tf)` threaded through `propose_bitcoin` / `propose_altcoins` → `_propose_for_symbol` / `_propose_all_for_symbol` → `_build_proposal_for_strategy` (Option A). Local dict per call, no module/class state. Both single-TF and multi-TF branches use it; legacy `_select_best_technique` path also threads cache for consistency (no per-path divergence). Fetch counts verified: 3 sym × 4 tech 12 → 3, multi-TF (2 strategies sharing 3 TFs) 6 → 3, sequential 2× `propose_bitcoin` 2 (no leak), legacy 3 sym × 1 tech 3 (no regression). 4 new tests in `tests/test_proposal_engine_multi_technique.py` (1083 → 1087). ruff clean; mypy zero new errors on `engine.py`. 23 existing `test_proposal_engine.py` tests pass unchanged. PEP 604 union syntax for type hints. No new debt. | Claude |
| 10.0 | 2026-04-28 | Phase 10 complete - all sub-tasks (10.1, 10.2, 10.3, 10.4, 10.5, 10.6) checked. Phase 10 cross-check: `docs/cross-checks/2026-04-28-phase-10-operational-maturation.md`. | Claude |
| 11.3 | 2026-04-28 | Phase 11.3 complete - Notification Push Backend (FR-015, NFR-012); `SlackNotifier` in `src/proposal/notification.py` posts to incoming webhook via `urllib.request.urlopen` + `asyncio.to_thread` (no new dep) implementing the existing `Notifier` protocol. `Settings.slack_webhook_url: Optional[str] = None` (non-breaking; notifier silent / not registered when unset). `src/main.py::build_engine` appends `SlackNotifier()` to the dispatcher's notifier list when URL set; logs presence not URL. Payload: `text` line summary `{symbol} {side} score={c:.2f} entry={p}` + 2 mrkdwn blocks (bolded summary + code-fenced detail w/ proposal_id, technique, SL, TP, qty, leverage, rr). `__repr__` redacts URL. `send` deliberately does NOT swallow `HTTPError` — dispatcher's existing try/except handles failure isolation per Phase 6.3 contract. `.env.example` + `docs/deployment.md` document `SLACK_WEBHOOK_URL` + incoming-webhook setup. 9 new tests across 2 test files (1087 → 1096) — incl. exact-string spec match, failure-isolation, build_engine both-branches, `__repr__` redaction. ruff clean; mypy zero new errors (14 mypy errors all pre-existing in untouched modules per 11.1 carry). No new debt. | Claude |
| 11.4 | 2026-04-28 | Phase 11.4 complete - ProposalHistory.purge_old Wiring (NFR-008); `src/main.py::_purge_old_proposals` helper (extracted for testability) called from `run()` between `build_engine` and signal-handler installation; logs INFO only when records were archived (silent on empty so daily restarts don't generate noise). New `src/tools/purge_proposals.py` operator CLI with `argparse --retention-months` override; reads `Settings`; prints informative summary on both "purged N" and "nothing to purge" branches; exit 0 in both. New `src/tools/__init__.py` package marker (operator tooling that imports only project code lives under `src/tools/`; `scripts/` reserved for tools that talk to external services). `docs/deployment.md` got a new "Operator Tools" section. 8 new tests (1096 → 1104) — `TestPurgeOldProposalsHook` (4: forwarding / count / silent-on-empty `caplog` / build-engine→hook smoke against real `ProposalHistory`) + `tests/test_tools_purge_proposals.py` (4: Settings-default / flag override / end-to-end Jan-2024-archives-fresh-stays / empty-print). ruff clean; mypy zero new errors (DEBT-008 lambda error shifted line 232 → 271, same code). No new debt. | Claude |
| 11.0 | 2026-04-28 | Phase 11 complete - all sub-tasks (11.1, 11.2, 11.3, 11.4) checked. Phase 11 cross-check: `docs/cross-checks/2026-04-28-phase-11-operational-hardening.md`. | Claude |
| 12.1 | 2026-04-28 | Phase 12.1 complete - Cross-Cycle Position Cap (FR-006, FR-007, FR-008; REAL-MONEY risk closure); `EngineConfig.max_open_positions_per_symbol: int = Field(default=1, ge=1)` env-overridable as `ENGINE_MAX_OPEN_POSITIONS_PER_SYMBOL` via `Settings.engine_max_open_positions_per_symbol` (Phase 10.2 pattern). `TradingEngine._handle_proposal` checks `trader.get_open_trades()` filtered by symbol *after* the composite-accept gate; on count ≥ cap increments `proposals_rejected`, logs `PROPOSAL_REJECTED` with reason `"symbol X cap N reached (M open)"` + structured `cap` / `open_count` event details, skips `_execute`. Phase 10.6 within-cycle dedup untouched (orthogonal: within-cycle vs across-cycle). Backward-compatible: cap=1 = pre-12.1 effective behaviour. Closes the 2026-04-28 Fly redeploy real-money concern (two BNB shorts in 14 min — 4× cycle = 4× position concentration). 5 new tests in `tests/test_runtime_engine.py` (default value / env wiring / cap-hit rejection / cap-not-reached execution / other-symbol-doesn't-block). 1104 → 1109 tests. ruff clean; mypy zero new errors (14 pre-existing in entry-point chain land in 12.2). One test gap recorded as DEBT-010 (Low): long+short same-symbol — implementation correct (counts both sides, prevents synthetic hedge) but suite doesn't explicitly cover. | Claude |
| 12.2 | 2026-04-28 | Phase 12.2 complete - Residual mypy Sweep (NFR-001; resolves DEBT-005 / 006 / 007 / 008); `mypy src` 29 errors → 0 across 53 source files. DEBT-005 (binance.py, 11 errors): hand-rolled `CCXTClient` Protocol covering the 10 ccxt methods used (`load_markets`, `close`, `fetch_ohlcv`, `fetch_ticker`, `fetch_balance`, `create_market_order`, `create_limit_order`, `cancel_order`, `fetch_order`, `fetch_open_orders`); `_client` typed `CCXTClient \| None`. DEBT-006 (factory.py, 3 errors): investigated — NOT a behavioural mismatch; registry's `type[BaseExchange]` widens away subclass `__init__` params; resolved with tightly-scoped `cast(Any, exchange_class)(...)` + comment explaining the typing gap (runtime preserves exact call shape). DEBT-007 (dashboard cluster, 13 errors across `theme.py`, `app.py`, `pages/trading.py`, `pages/engine.py`): `Literal` types for theme constants (verified against streamlit `commands/page_config.py`), `StreamlitPage` import for navigation, `cast(...)` on `st.metric` numeric values. DEBT-008 (main.py lambda, 1 error): targeted `# type: ignore[misc]` (canonical case for asyncio signal-handler callback shape mismatch). 1109 tests pass (no behaviour change, no new tests — refactor not a feature). 8 files modified. Public API preserved. QA-flagged follow-up (TypedDict for `build_summary_metrics` to drop consumer-side casts) recorded as DEBT-011 (Low). | Claude |
| 12.3 | 2026-04-28 | Phase 12.3 complete - LLM Strategy Timeout Handling (FR-022; operational reliability — closes the 2026-04-28 Fly `chasulang_ict_smc` 120s-timeout silent-drop-out concern); retry-on-timeout with 1.5× backoff for the Claude CLI in `src/ai/claude.py` (120 → 180 → 270 escalation; retry only on `asyncio.TimeoutError` — verified via `test_non_timeout_errors_do_not_trigger_retry`, `mock_exec.call_count == 1`; per-attempt process cleanup, no zombie risk). `ClaudeTimeoutError` now multiply-inherits `ClaudeError + StrategyError` (MRO `[ClaudeTimeoutError, ClaudeError, StrategyError, Exception, ...]`) so the engine's existing `StrategyError` catch handles it without a new except block at every call site. `PromptStrategy.analyze` re-raises `ClaudeTimeoutError` UNWRAPPED (other `ClaudeError` subtypes still wrap into `StrategyError(...)` per pre-existing contract) so the engine emits `LLM_TIMEOUT` with original `timeout_seconds` payload intact — locked by `test_unwrap_propagation`. `Settings.claude_cli_timeout_seconds: int = Field(default=120, ge=10)` + `claude_cli_max_retries: int = Field(default=1, ge=0)` (0 = single shot). `ActivityEventType.LLM_TIMEOUT` added; `ProposalEngine` accepts optional `activity_log` (None default — backward-compat preserved) and emits `LLM_TIMEOUT` with `strategy_name`/`version`/`symbol`/`timeout_seconds` on final exhaustion. `build_engine` creates one `ActivityLog` and shares it between `ProposalEngine` and `TradingEngine`. 12 files modified (src/ai/claude.py, src/ai/exceptions.py, src/strategy/loader.py, src/proposal/engine.py, src/runtime/activity_log.py, src/config.py, src/main.py, .env.example, docs/development-plan.md, plus 3 test files). 1109 → 1119 tests (+10 — 6 retry tests + 3 LLM_TIMEOUT event tests + 1 unwrap-propagation test). ruff/mypy clean. No new debt. | Claude |
| 12.4 | 2026-04-28 | Phase 12.4 complete - Telegram Notification Backend (FR-015, NFR-012; second push backend so live mode isn't single-channel — closes Phase 11 cross-check carry-forward); `TelegramNotifier` in `src/proposal/notification.py` POSTs form-encoded `chat_id` + `text` + `parse_mode=Markdown` to `https://api.telegram.org/bot<TOKEN>/sendMessage` via stdlib `urllib.request.urlopen` + `asyncio.to_thread` (zero new dep — mirrors Slack's Phase 11.3 pattern exactly). `Settings.telegram_bot_token: str \| None = Field(default=None)` + `telegram_chat_id: str \| None = Field(default=None)` (non-breaking; both required for activation). `src/main.py::build_engine` appends `TelegramNotifier(...)` to the dispatcher's notifier list when both env vars set; logs presence only. Activation gate `bool(token and chat_id)` — partial config (token-only, chat-id-only, neither) silent in all three (locked by `test_telegram_notifier_silent_when_either_missing`). Message format collapses Slack's two-block payload into one Markdown string (bolded headline + code-fenced detail) so on-the-wire content of Slack and Telegram alerts stays in sync. `__repr__` masks BOTH token AND chat id (chat id treated as a secret since it identifies the operator's destination channel — tighter contract than Slack's URL-only redaction). `send` does not catch `HTTPError` — dispatcher's existing per-channel failure-isolation contract (Phase 6.3) handles it. `.env.example` + `docs/deployment.md` document `TELEGRAM_BOT_TOKEN` (secret) + `TELEGRAM_CHAT_ID`. 8 files modified (src/proposal/notification.py, src/config.py, src/main.py, .env.example, docs/deployment.md, docs/development-plan.md, plus 2 test files). 1119 → 1127 tests (+8 — 6 in test_proposal_notification.py + 2 in test_main_dispatch.py). ruff/mypy clean. No new debt. | Claude |
| 12.0 | 2026-04-28 | Phase 12 complete - all sub-tasks (12.1, 12.2, 12.3, 12.4) checked. Phase 12 cross-check: `docs/cross-checks/2026-04-28-phase-12-risk-hardening.md`. | Claude |
| 13.1 | 2026-04-28 | Phase 13.1 complete - Cleanup Batch (NFR-001; resolves DEBT-009 / DEBT-010 / DEBT-011); DEBT-009 split `scripts/lint.sh` (no `--fix` — CI / pre-commit safe) + new `scripts/lint-fix.sh` (with `--fix` — dev convenience), both executable. DEBT-010 added `test_cap_blocks_opposite_side_same_symbol` to `tests/test_runtime_engine.py` (1 BNB long open + BNB short proposal at composite=2.0; cap=1 → positions_opened=0, no open_position call, PROPOSAL_REJECTED with BNB + "cap 1 reached") — pins the synthetic-hedge prevention invariant against future regression. DEBT-011 replaced `dict[str, object]` returns with per-page TypedDicts (`TradingSummaryMetrics` in `src/dashboard/pages/trading.py`, `EngineSummaryMetrics` in `src/dashboard/pages/engine.py`) since shapes differ; consumer-side `cast(...)` calls dropped at every access site; no leftover `from typing import cast` in either file. Refactor only — no behavioural change for DEBT-009 / DEBT-011; DEBT-010 adds the single new test. 5 files modified (scripts/lint.sh, scripts/lint-fix.sh, tests/test_runtime_engine.py, src/dashboard/pages/trading.py, src/dashboard/pages/engine.py) plus dev plan. 1127 → 1128 tests (+1 cap test). ruff/mypy clean (53 files). No new debt. | Claude |
| 13.2 | 2026-04-28 | Phase 13.2 complete - EngineConfig Remaining-Fields Env Override (NFR-004; resolves DEBT-003); third application of the Phase 10.2 pattern (10.2 first, 12.1 second). 4 new `Settings.engine_*` fields in `src/config.py` — `engine_monitor_interval: int = Field(default=60, ge=10)` (env `ENGINE_MONITOR_INTERVAL`), `engine_bitcoin_symbol: str = Field(default="BTC/USDT")` (env `ENGINE_BITCOIN_SYMBOL`), `engine_altcoin_top_k: int = Field(default=3, ge=1)` (env `ENGINE_ALTCOIN_TOP_K`), `engine_actor: str = Field(default="auto-engine")` (env `ENGINE_ACTOR`). `ge=` validators mirror `EngineConfig`'s own floors so env input gets the same validation as direct construction. `src/main.py::build_engine` constructs `EngineConfig(...)` with the 4 new fields alongside the existing 4 (10.2 explicit-config-wins back-compat preserved); docstring rewritten to drop the "not yet env-overridable" note. Defaults bytewise-match `EngineConfig` so existing deployments are unchanged without an env setting; parity locked by `test_settings_defaults_match_engine_config`. `.env.example` + `docs/deployment.md` document every new env var with operator-facing prose. Tests: 4 new methods in `tests/test_config.py::TestEngineSettings` (default + env override + `ge=` validators where applicable), 4 new parity assertions in the existing default-match test, 1 new end-to-end smoke test in `tests/test_main_dispatch.py` (`test_build_engine_propagates_all_engine_env_overrides`). 7 files modified (src/config.py, src/main.py, .env.example, docs/deployment.md, tests/test_config.py, tests/test_main_dispatch.py, plus dev plan). 1128 → 1134 tests (+6). ruff/mypy clean (53 files). No new debt. | Claude |
| 13.3 | 2026-04-28 | Phase 13.3 complete - BaseExchange.get_ohlcv `since` Parameter (FR-020 extended; resolves DEBT-004); `BaseExchange.get_ohlcv` ABC now declares `since: int | None = None` (timestamp ms, inclusive on start; None = pre-13.3 most-recent-page semantics). `BinanceExchange.get_ohlcv` and `BybitExchange.get_ohlcv` forward `since` to `ccxt.fetch_ohlcv(since=...)`; both adapters preserve default behaviour bytewise — locked by `test_get_ohlcv_defaults_since_to_none` for each. `scripts/backtest_baselines.py::fetch_ohlcv_window` switched from `exchange._client.fetch_ohlcv(...)` to `exchange.get_ohlcv(..., since=...)` end-to-end; the `_client` reach-around block + the `RuntimeError` it gated + the local `Decimal` import + the bottom-of-function raw-row → `OHLCV` reconstructor are all deleted (real adapter already returns `OHLCV`). The "deliberately reach past the BaseExchange contract" comment removed. `MockExchange` (`tests/test_exchange_base.py`) and `_FakeBinanceExchange` (`tests/test_scripts_backtest_baselines.py`) grew the new `since` parameter for ABC parity; the latter absorbs the pagination-cursor logic that previously lived in the deleted `_FakeCCXTClient`. 9 files modified (src/exchange/base.py, src/exchange/binance.py, src/exchange/bybit.py, scripts/backtest_baselines.py, tests/test_exchange_base.py, tests/test_exchange_binance.py, tests/test_exchange_bybit.py, tests/test_scripts_backtest_baselines.py, plus dev plan). 1134 → 1138 tests (+4 — 2 per adapter: default-None forwarding + explicit-since forwarding). ruff/mypy clean (53 files). No new debt. | Claude |
| 13.4 | 2026-04-28 | Phase 13.4 complete - Email Notification Backend (FR-015, NFR-012; third push backend so live-mode notification redundancy spans webhook + chat + SMTP failure modes). `EmailNotifier` in `src/proposal/notification.py` uses stdlib `smtplib.SMTP` + `email.message.EmailMessage` wrapped in `asyncio.to_thread` (zero new dep — mirrors Slack/Telegram pattern); STARTTLS-only handshake (port 587 default), SMTP_SSL deferred as DEBT-012 (Low). Subject format: `"Crypto Master: {symbol} {side} score={c:.2f}"`. Body reuses `_build_telegram_text` via thin `_build_email_body` helper so all three push backends carry identical content (locked by `test_build_email_body_matches_telegram_text`). 6 SMTP `Settings` fields in `src/config.py`: `email_smtp_host` / `email_smtp_user` / `email_smtp_password` / `email_from` / `email_to` (all `str \| None`, default None) + `email_smtp_port: int = Field(default=587, ge=1, le=65535)`; activation gate is the 5 string fields (port has default so it can't fail `all([...])` — note dev-plan-text "all 6" is loose vs the 5-string code gate; code is correct). `EmailNotifier.__repr__` masks password unconditionally; host/user/from/to remain visible (operationally useful for log triage, not secrets in the same sense). `send` does NOT swallow `smtplib` errors — Phase 6.3 dispatcher's per-channel failure-isolation contract is the single owner. `src/main.py::build_engine` appends `EmailNotifier(...)` when 5 string fields set; logs presence only. `.env.example` + `docs/deployment.md` document the SMTP quintet. Configurable `timeout: float = 10.0` so a slow server can't stall the cycle. 8 files modified (src/proposal/notification.py, src/config.py, src/main.py, .env.example, docs/deployment.md, docs/development-plan.md, plus 2 test files). 1138 → 1149 tests (+11 — 9 in test_proposal_notification.py: subject format / body parity / end-to-end via `_FakeSMTP` / repr masks password / STARTTLS called / login called / SMTP error doesn't crash dispatch / password not in logs / configured timeout reaches `smtplib.SMTP`; 2 in test_main_dispatch.py: created when env set + silent across 6 partial scenarios). ruff/mypy clean (53 files). One new debt: DEBT-012 SMTP_SSL alternative (Low). | Claude |
| 13.0 | 2026-04-28 | Phase 13 complete - all sub-tasks (13.1, 13.2, 13.3, 13.4) checked. Phase 13 cross-check: `docs/cross-checks/2026-04-28-phase-13-cleanup-polish.md`. | Claude |
| 14.1 | 2026-04-28 | Phase 14.1 complete - Chasulang Timeout Mitigation (FR-022 extended, NFR-001; closes prod-observed `chasulang_ict_smc` 120s timeouts that Phase 12.3's retry didn't eliminate — Fly logs confirmed retry path was firing but 180s still timing out, so per-strategy 240s override is the right fix). `TechniqueInfo` gains `claude_timeout_seconds: int \| None = Field(default=None, ge=1)` in `src/strategy/base.py` — `None` keeps existing strategies on `Settings.claude_cli_timeout_seconds`, integer overrides go straight to `ClaudeCLI`; `ge=1` rejects zero at load time as a config bug. `PromptStrategy.analyze` (`src/strategy/loader.py`) reads `self.info.claude_timeout_seconds`; when set constructs `ClaudeCLI(timeout=float(override))`, when `None` constructs `ClaudeCLI()` so the wrapper resolves Settings lazily. `strategies/chasulang_ict_smc.md` frontmatter gains `claude_timeout_seconds: 240` (240 × 1.5 = 360s worst case with one retry, comfortably above the observed timeout floor on Fly's shared-CPU/1GB machine). `ClaudeTimeoutError` (`src/ai/exceptions.py`) grows `attempt_number: int = 1` on `__init__` (default preserves Phase 12.3 single-shot semantics for unmigrated callers); `_execute_cli_once` (`src/ai/claude.py`) accepts the kwarg and stamps it onto raised errors, while the retry loop forwards `attempt + 1` so the surfacing error carries the final attempt's index. `_log_llm_timeout` (`src/proposal/engine.py`) extends the `LLM_TIMEOUT` event payload with `attempt_number` (from `error.attempt_number`) and `final_timeout_seconds` (alias of `error.timeout_seconds`, intent-revealing for the dashboard) so operators can distinguish "first attempt fails, retry didn't fire" (wiring bug) from "every attempt timed out" (leash too short); legacy `timeout_seconds` key preserved for back-compat. 11 files modified (src/ai/exceptions.py, src/ai/claude.py, src/strategy/base.py, src/strategy/loader.py, src/proposal/engine.py, strategies/chasulang_ict_smc.md, plus 5 test files and dev plan). 1153 → 1158 tests (+5 net new — 2 in test_ai_claude.py covering attempt_number through retry loop, 2 in test_ai_exceptions.py for the new field, 2 in test_strategy_base.py for the schema field + ge=1 rejection, 2 in test_strategy_loader.py pinning `ClaudeCLI(timeout=240.0)` vs `ClaudeCLI()`, 1 in test_proposal_engine.py for the `LLM_TIMEOUT` payload). ruff/mypy clean (53 files). No new debt. No ADR — extends existing per-strategy frontmatter pattern. | Claude |
| 14.2 | 2026-04-28 | Phase 14.2 complete - SMTP_SSL Alternative (FR-015 extended, NFR-001; resolves DEBT-012 — Phase 13.4 carry). `Settings.email_use_ssl: bool = Field(default=False)` in `src/config.py` (env `EMAIL_USE_SSL=true` activates the SMTP_SSL path; default `False` keeps the Phase 13.4 STARTTLS path bytewise unchanged for every existing deployment — strict back-compat). `EmailNotifier.__init__` (`src/proposal/notification.py`) accepts keyword-only `use_ssl: bool = False` stored as `self._use_ssl`; class docstring expanded to describe both transports (STARTTLS default for Gmail / Mailgun / SendGrid / corporate; SMTP_SSL for Yahoo Mail / AT&T / ProtonMail). Inner `_send` closure branches at send-time: `use_ssl=True` → `smtplib.SMTP_SSL(host, port, timeout=...)` with NO `starttls()` call (channel already encrypted on connect); `use_ssl=False` → existing `smtplib.SMTP(host, port, timeout=...)` + `starttls()`. `with smtp:` socket cleanup, `login`, `send_message` shared by both paths. `src/main.py::build_engine` reads `settings.email_use_ssl` and forwards to `EmailNotifier(use_ssl=...)`. `.env.example` + `docs/deployment.md` document `EMAIL_USE_SSL` with the Yahoo / AT&T / ProtonMail pairing guidance (`EMAIL_USE_SSL=true` + `EMAIL_SMTP_PORT=465`); deployment doc adds a `fly secrets set` example for Yahoo. 7 files modified (src/config.py, src/proposal/notification.py, src/main.py, .env.example, docs/deployment.md, tests/test_proposal_notification.py, plus dev plan). 1158 → 1160 tests (+2 net new — `test_email_notifier_uses_smtp_ssl_when_flag_set` and `test_email_notifier_uses_starttls_when_flag_unset`, each with cross-protection: patches BOTH constructors, raises on the wrong one so a regression where both branches accidentally call the same constructor fails loudly rather than silently passing). ruff/mypy clean (53 files). No new debt. No ADR — extends Phase 13.4's `EmailNotifier` with one config branch; `Notifier` protocol and dispatcher failure-isolation contract unchanged. | Claude |
| 14.0 | 2026-04-28 | Phase 14 complete - all sub-tasks (14.1, 14.2) checked. Phase 14 cross-check: `docs/cross-checks/2026-04-28-phase-14-production-reliability.md`. | Claude |
| 15.1 | 2026-04-28 | Phase 15.1 complete - Diagnostic Clarity (NFR-001; closes the 2026-04-28 misdiagnosis where 139 rejected proposals read as "0 trades, must be a bug" instead of "threshold gate working as designed"). Two surgical changes. (1) `src/trading/strategy.py:474` log verb rename: `"Created position: ..."` → `"Sized position candidate: ..."` so the proposal-sizing emit can't be misread as a trade-execution event in `fly logs` greps; same fields and verbosity, only the verb changes. The `PaperTrader.open_position` "Opened paper position" log (`src/trading/paper.py:546`) stays unchanged so the two events are clearly distinct. (2) `src/dashboard/pages/trading.py` extends `TradingSummaryMetrics` (Phase 13.1 TypedDict) with `proposals_rejected_threshold_count: int`; `build_summary_metrics` accepts an optional `proposal_history: ProposalHistory \| None = None` (defaults to `ProposalHistory()` so existing callers don't need to wire it up — backward-compat) and counts records where `decision == "rejected"` and `rejection_reason` matches `^composite \d+\.\d+ below threshold \d+\.\d+$` (the exact format from `RuntimeEngine._auto_decide` at `src/runtime/engine.py:586`); cap-rejected records (Phase 12.1, reason starts with `"symbol "`) are excluded so the metric stays interpretable. New helper `_count_threshold_rejections` wraps `history.list_all()` in `try/except` so a malformed proposals dir warns + returns 0 rather than crashing the page render. Render layout: `st.columns([3, 1])` next to "Active Positions" so an operator seeing 0 active positions immediately sees how many proposals were rejected and why. `render(...)` accepts `proposal_history=` for test injection; defaults to `ProposalHistory()`. 4 files modified (src/trading/strategy.py, src/dashboard/pages/trading.py, tests/test_dashboard_trading.py, plus dev plan). 1160 → 1162 tests (+2 net new — `test_summary_metrics_counts_threshold_rejections` seeds 4 records (accepted / threshold-rejected / cap-rejected / no-reason) and asserts the count surfaces only the threshold-rejected one; `test_summary_metrics_handles_empty_proposal_history` pins backward-compat for an absent proposals dir). Existing `test_summary_metrics_empty_inputs` extended with a `tmp_path: Path` fixture and the new field assertion. AppTest smoke tests updated to inject `ProposalHistory(data_dir=...)` and assert the metric card renders with value `"0"`. ruff/mypy clean. No new debt. No ADR — log-string rename + one new dashboard field is mechanical clarity, not a component-shape decision. | Claude |
| 16.1 | 2026-04-29 | Phase 16.1 complete - chasulang Parse + Wedge Mitigation (FR-022 extended, NFR-001; closes two prod-observed defects from the 2026-04-28 redeploy: (a) every chasulang Claude response failed with `KeyError: 'signal'` because chasulang_ict_smc.md returns the trade nested under `trade.*` rather than flat top-level, and (b) at `2026-04-28T15:02:15Z` a chasulang retry timed out at 360s and the engine wedged silent for 12+ hours, the prior `asyncio.create_subprocess_exec` + `asyncio.wait_for` path failing to actually kill the child). `src/ai/claude.py::_parse_response` now calls a new `_normalize_trade_fields` helper after JSON extraction; helper promotes nested `trade.*` keys (`signal`, `entry_price`, `stop_loss`, `take_profit`, `confidence`, `reasoning`) to top level when present (non-destructive — original `trade` sub-dict preserved in returned result for callers wanting full nested view, e.g. `take_profit_2`). Take-profit precedence: explicit `trade.take_profit` > `trade.take_profit_1` > nothing — TP1 is the conservative target, deliberately picked over TP2 stretch. When neither top-level nor `trade.signal` carries a signal, raises `ClaudeParseError` with a message naming both candidate paths so operators can spot the failing template fast. `src/ai/claude.py::_execute_cli_once` rebuilt on `subprocess.Popen` run via `asyncio.to_thread` (decades-stable blocking subprocess semantics, event loop unblocked); `proc.communicate(timeout=...)` drives the timeout, `proc.kill()` (SIGKILL — not soft-terminate) + `proc.wait(timeout=5)` on `subprocess.TimeoutExpired` guarantees the child is reaped or surfaces as a distinct error. SIGKILL-itself-fails branch raises a distinct `ClaudeTimeoutError` ("did not respond to SIGKILL within 5s") so operators can spot zombie / kernel-stuck children in logs; same exception type so the proposal engine's `except StrategyError` path still treats it as a clean per-strategy skip. `ClaudeTimeoutError` continues to carry `attempt_number` per Phase 14.1 contract on both branches. `FileNotFoundError` re-raised unchanged. Test mock surface fully migrated from `asyncio.create_subprocess_exec` / `AsyncMock` to `subprocess.Popen` / `MagicMock(spec=Popen)` — `_make_popen_success` / `_make_popen_timeout` helpers factor the new pattern; `TestClaudeCLIRetryOnTimeout` rewired (timeout-escalation test now captures `proc.communicate(timeout=...)` kwarg instead of patching `asyncio.wait_for`). 3 files modified (src/ai/claude.py, tests/test_ai_claude.py, plus dev plan). 1162 → 1170 tests (+8 net new — 6 `TestParseResponseNestedTradeForm`: chasulang nested-form / top-level back-compat / TP1-over-TP2 / explicit-tp-beats-TP1 / clear-error-names-both-paths / top-level-signal-wins-when-trade-lacks-one; 2 `TestSubprocessKillOnTimeout`: kill-called-once + wait(timeout=5) with attempt_number/timeout_seconds preserved on normal timeout, distinct ClaudeTimeoutError when SIGKILL itself hangs). ruff/mypy clean (53 files). No new debt. No ADR — bug fix to existing component, `ClaudeCLI` public contract unchanged (same `analyze` signature, same exception types, same retry semantics, same `attempt_number` propagation from Phase 14.1). | Claude |
| 16.0 | 2026-04-29 | Phase 16 complete - all sub-tasks (16.1) checked. Phase 16 cross-check: `docs/cross-checks/2026-04-29-phase-16-chasulang-stability.md`. | Claude |
| 17.1 | 2026-04-29 | Phase 17.1 complete - Auto-Research Operator Workflow + Catalog-Aware Improver (FR-023, FR-026, FR-034, CON-003; first end-to-end exercise of the strategy-evolution stack — `StrategyImprover` → `Backtester` → `PerformanceAnalyzer` → `RobustnessGate` → `FeedbackLoop._run_cycle` → `CandidateRecord` — landing every robustness-gate-passing pick in `AWAITING_APPROVAL` for explicit operator approval per CON-003; promotion stays manual). New `scripts/auto_research_candidates.py` operator entry point (`python -m scripts.auto_research_candidates [--picks N] [--dry-run]`) parses the priority matrix's first-wave OHLCV-only Top-N picks from `docs/research/strategies/00-priority-matrix.md`, dispatches each through `improver.generate_idea(context=<pick description>)` → `loop.propose_new(...)`, persists run snapshot to `data/research_runs/run_{ts}.json`, and prints an operator-facing summary with `decision_reason` + `robustness_summary` continuation lines so DISCARDED reasons are visible without opening the JSON. `--dry-run` short-circuits before the loop call and routes generated experimental files under `strategies/experimental/dry_runs/` so they never mix with real gated candidates. `src/ai/improver.py::StrategyImprover.__init__` accepts `catalog_path: Path | None = None` (default `docs/research/strategies/00-priority-matrix.md`); new private `_load_catalog` helper reads the file at most once per improver lifetime, fail-softs on missing path with INFO log + empty string. `_build_new_idea_prompt` injects the cached catalog under a `## Reference Catalog` section. `_build_user_idea_prompt` deliberately omits the catalog (the user has already described their idea — injecting the catalog would redirect Claude away from the user's intent; deviation from original spec wording per quant-trader-expert review Issue 4). `_build_improvement_prompt` also untouched (improvement is failure-mode analysis on an existing strategy, not a fresh-idea exercise). Quant review surfaced 4 in-scope fixes shipped in the dev's commit: per-timeframe candle defaults bumped (1h: 4380, 15m: 8760) so the regime gate sees both bull and bear; summary surfaces `decision_reason` + `robustness_summary` so DISCARDED reasons are terminal-visible; dry-run output routes under `strategies/experimental/dry_runs/`; the user-idea catalog-injection deletion above (Issue 4). 14 files in commit `10bbd7f` (`scripts/auto_research_candidates.py`, `src/ai/improver.py`, `tests/test_ai_improver.py`, `tests/test_scripts_auto_research_candidates.py`, plus the operator-curated catalog under `docs/research/strategies/{00-priority-matrix,01-ict-smc,02-chart-patterns,03-breakout-range,04-mean-reversion,05-trend-indicators,06-crypto-specific,README}.md`, `.gitignore` for `data/research_runs/`, and dev plan). 1170 → 1189 tests (+19 net new — improver gains catalog-injection / catalog-not-in-user-idea / catalog-not-in-improvement / fail-soft-when-absent cases plus existing-test churn for the new `catalog_path` constructor kwarg; new `tests/test_scripts_auto_research_candidates.py` covers happy-path / dry-run / one-pick-raises). ruff/mypy clean (53 source files; `scripts/` not in mypy scope per spec). Two new debt items: DEBT-013 `auto_research_candidates.run_async` constructs its own `FeedbackLoop` / `BinanceExchange` (Low — fine until a second caller materialises; quant Issue 3) and DEBT-014 `loop.propose_new` called without `param_grid` so the sensitivity gate is `SKIPPED` for every Phase 17.1 candidate (Medium — fix needs `Pick`-level parameter-grid declaration or strategy-introspection helper; quant Issue 5; partial-robustness-verdict consequence). One operator action deferred and standing: `flyctl ssh console --app crypto-master -C "python -m scripts.auto_research_candidates --picks 2"` to populate `/data/feedback/state/` + `/data/audit/` end-to-end. No ADR — wires existing components into an operator script + extends one prompt; no new architectural seam. | Claude |
| 17.0 | 2026-04-29 | Phase 17 complete - all sub-tasks (17.1) checked. Phase 17 cross-check: `docs/cross-checks/2026-04-29-phase-17-strategy-evolution-operator.md`. | Claude |
| 18.1 | 2026-04-30 | Phase 18.1 added - Stale-Quote Sanity Gate at Proposal Fill (FR-008, FR-013, NFR-012); driven by 2026-04-30 production review of `/data/trades/paper/trades.json` (1W/8L, EV -8.73/trade) — proposal `6ef8c07e...` filled 3 min 13 sec stale at `entry=2323` then closed `0.48s` later at `2300` because live had already crossed `SL=2305`. | product-planner |
| 18.1 | 2026-04-30 | Phase 18.1 sealed — stale-quote sanity gate shipped, full suite 1198 pass. Sanity gate inserted between auto-approval and `trader.open_position` in `src/runtime/engine.py::_execute` via new `_stale_quote_gate` helper; past-SL check (side-dispatched off `proposal.signal`) + symmetric slippage check (`abs(live - entry)/entry > tolerance`); rejection rewrites `ProposalRecord` to `REJECTED` (load + `model_copy` + save) + emits activity event with `proposal_entry` / `proposal_stop_loss` / `live_price` / `drift_bps`; ticker fetch failure → fall through to fill, log WARN `stale_quote_check_failed`. New `EngineConfig.fill_slippage_tolerance: Decimal = Decimal("0.005")` (50 bps, `Field(ge=0)`) and `EngineConfig.reject_if_past_stop_loss: bool = True`; env overrides `ENGINE_FILL_SLIPPAGE_TOLERANCE` + `ENGINE_REJECT_IF_PAST_STOP_LOSS` via `Settings.engine_*` (Phase 10.2 / 13.2 pattern); `build_engine` wires alongside existing eight fields. Two pre-existing tests (`test_proposal_executes_when_cap_not_reached`, `test_cap_counts_only_matching_symbol`) had inverted-SL fixtures for short proposals that the new gate exposed; dev fixed both fixtures in same diff. 7 files in working-tree diff (not yet committed): src/runtime/engine.py, src/config.py, src/main.py, .env.example, tests/test_runtime_engine.py, tests/test_config.py, docs/development-plan.md. 1193 → 1198 tests (+5 net new in `test_runtime_engine.py`, total 23 → 28). ruff/mypy clean. Quant validated 50-bps default against 1H BTC/ETH expected drift over a 4-min latency window (~26 bps ≈ 2σ at 50 bps); confirmed smoking-gun ETH case caught with 49 bps headroom; flagged `bollinger_band_reversion` will see visible rejection-rate uptick (intended behaviour, not regression). QA verdict: 🟡 Ship with note — four observations recorded as DEBT-015 (Medium — rejection-path semantic divergence vs Phase 12.1) / DEBT-016 (Low — simultaneous-counters contract undocumented) / DEBT-017 (Low / cosmetic — `entry_price` + `proposal_entry` redundancy in event payload) / DEBT-018 (Low — rejection tests don't assert `proposals_accepted == 1`). One operator action standing: Fly redeploy + 24h log monitoring for first `stale_quote_past_sl` / `slippage_exceeds_tolerance` rejection. No ADR — guard inserted into existing seam, `Trader` Protocol unchanged. | docs-auditor |
| 19.x | 2026-04-30 | Phase 19 added — Sub-Account / Capital Segmentation (FR-036, FR-037, FR-038 introduced). Five sub-tasks: 19.1 Foundation (entity + registry + default-account migration, single-default registry preserves single-seed back-compat); 19.2 Engine Integration (every proposal / trade / performance record / portfolio snapshot scoped by `sub_account_id`, persistence paths gain a sub-account level, cap rejection logs include the id, single-default still in flight); 19.3 Multi-Paper-Account + YAML + Dashboard (`config/sub_accounts.yaml` parsed into N entries, dashboard surfaces per-sub-account equity curves + selector, multi-paper operative, multi-live walled off until 19.4); 19.4 Multi-Credential Live Mode (`Settings.exchange_credentials: dict[str, ExchangeConfig]` with `EXCHANGE_<REF>_*` env schema + legacy `BINANCE_API_KEY` / `BYBIT_API_KEY` aliasing, missing creds for live sub-account fail loud at boot, per-sub-account `LiveTrader` cached, Phase 18.1 stale-quote gate routes per sub-account); 19.5 Strategy-Combination A/B Backtest Harness (`BacktestHarness.run_sub_accounts`, `MultiAccountReport` with per-sub-account equity / PerformanceSummary / pairwise correlation / merged trade ledger, `scripts/backtest_combinations.py` operator entry, robustness gate routes per sub-account). Driven by user request 2026-04-30: "전략별로 시드를 분리하거나, 여러 조합의 전략을 테스트하기 위해서는 서브 계정 개념이 필요할듯". Architecture documented in `DESIGN.md §9`. | Claude |
| 17.4 | 2026-04-30 | Phase 17.4 added — Auto-Research Workflow Unblock — Runtime Contract + Backtest Circuit Breaker (FR-022, FR-023, FR-025, NFR-001; resolves DEBT-019 Options A + C). Driven by 2026-04-30 first real run of `auto_research_candidates --picks 5` hanging ~9 hours after generating one candidate (`donchian_turtle_system_2_20260430_002157.md`): generated `prompt`-type body lacked the runtime JSON contract → Claude returned conversational text per bar → `Backtester` swallowed the parse error and looped forever. A: `_build_new_idea_prompt` mandates a `## Output Contract` block in the generated body matching chasulang's JSON schema (`signal` / `entry_price` / `stop_loss` / `take_profit`); user-idea + improvement prompts deliberately untouched per Phase 17.1 Issue-4 deviation. C: `Backtester` gains per-bar timeout + N-consecutive-parse-failures circuit breaker raising new `BacktestAbortedError` that propagates to `LoopStatus.ERRORED`; new `Settings.engine_backtest_per_bar_timeout` (default 60s) + `engine_backtest_max_parse_failures` (default 5) env overrides. Option B (code-type steering) deferred to Phase 17.5 as the cleaner long-term path. *(Originally written under "Phase 17.2" / Option-B-deferred-to-"17.3"; renumbered 2026-05-01 by Phase 23.2 — see reconciliation row below.)* | product-planner |
| 17.5 | 2026-04-30 | Phase 17.5 added — Code-Type Steering for Deterministic Catalog Picks (FR-023, FR-025, NFR-001; resolves DEBT-019 Option B as the long-term cleanup behind 17.4's unblock). Adds an explicit steering flag on `Pick` (recommended over fragile keyword heuristics) so deterministic catalog picks (Donchian, Supertrend, Z-score, Larry Williams, NR7, Connors RSI(2), BB %B+RSI, Golden Cross) generate as Python `BaseStrategy` subclasses mirroring `strategies/{rsi,bollinger_bands,ma_crossover}.py`, eliminating the per-bar Claude call from the hot path entirely. Phase 17.1 catalog injection retained on the new branch so Claude still sees the taxonomy when picking implementation choices. Acceptance: `--picks 5` produces 5 loadable Python strategy files that run end-to-end through `Backtester` + `RobustnessGate` with zero per-bar Claude calls. *(Originally written under "Phase 17.3"; renumbered 2026-05-01 by Phase 23.2 — see reconciliation row below.)* | product-planner |
| 17.4 | 2026-04-30 | Phase 17.4 complete - Auto-Research Workflow Unblock — Runtime Contract + Backtest Circuit Breaker (FR-022, FR-023, FR-025, NFR-001; DEBT-019 Resolved, DEBT-020 Resolved same-cycle, DEBT-021/022/023 Added). *(Originally written under "Phase 17.2"; renumbered 2026-05-01 by Phase 23.2.)* Items 1–6 + 8 of the 8-item spec ticked; item 7 (operator acceptance run against the surviving `donchian_turtle_system_2_20260430_002157.md` artefact) deliberately left `[ ]` as the post-cycle operator action. **Implementation (senior-developer):** `src/ai/improver.py::_new_idea_output_contract()` injection in `_build_new_idea_prompt` only (user-idea + improvement prompts deliberately untouched per Phase 17.1 Issue-4 deviation, pinned by 2 regression-guard tests); `src/backtest/engine.py` gains `BacktestAbortedError(reason, candle_index)` + per-bar `asyncio.wait_for` + consecutive-failure counter on both `Backtester.run` (single-TF) and `_run_multi_timeframe`; `BacktestAbortedError` exported from `src/backtest/__init__.py` and propagates to `LoopStatus.ERRORED` via the existing `FeedbackLoop._run_cycle` exception handler. `BacktestConfig` gains `per_bar_timeout: float = 600.0` (post-DEBT-020 bump from initial 60.0 — see below) and `max_parse_failures: int = 5`; `Settings.engine_backtest_per_bar_timeout` + `engine_backtest_max_parse_failures` mirror the defaults with env overrides. **Implementation refinement:** `StrategyValidationError` (a `StrategyError` subclass meaning "data not ready") caught separately and skipped without incrementing the breaker counter, so `rsi_universal`'s `period * 3 = 42` warmup floor against the engine's default `warmup_candles = 20` doesn't trip the breaker — surfaced as DEBT-021 (Medium) for the long-term `BaseStrategy.minimum_candles` contract fix. Genuine contract failures (`ClaudeParseError`, `StrategyExecutionError`, `StrategyLoadError`, `asyncio.TimeoutError`) still count. **Same-cycle DEBT-020 fix:** `BacktestConfig.per_bar_timeout` default raised `60.0 → 600.0` (chasulang's actual 480s `claude_timeout_seconds` per-`analyze()` ceiling + 120s headroom) — caught by quant-trader-expert review before any chasulang backtest ran; `Settings.engine_backtest_per_bar_timeout` + `.env.example` operator prose + `TestBacktestEngineSettings::test_per_bar_timeout_default_and_env` parity test all updated to match. **While-in-there:** `scripts/auto_research_candidates.py` gains `connect()` / `disconnect()` lifecycle around `BinanceExchange` with `owns_exchange` ownership flag and `try/finally`; this fix landed during the original DEBT-019 hung-Phase-B debugging session when the script first errored "Not connected. Call connect() first." — behaviorally correct, well-tested (12/12 in `tests/test_scripts_auto_research_candidates.py` still pass), recorded in the session log without spawning a separate DEBT entry. **Tests:** `tests/test_ai_improver.py` gains 3 new `TestNewIdeaOutputContract` cases; `tests/test_backtest_engine.py` gains 3 new `TestPerBarCircuitBreaker` cases; `tests/test_config.py` gains 5 new `TestBacktestEngineSettings` cases. 1198 → 1209 (+11 net new — same after DEBT-020 fix). ruff/mypy clean. **QA verdict:** 🟡 Ship with note (qa-reviewer). **Quant verdict:** Ship with follow-ups (3 deferred TECH-DEBT items: DEBT-021 Medium / DEBT-022 Low / DEBT-023 Low — none blocking, all surfaced for future-cycle pickup). No ADR — extends an existing prompt method + adds a circuit-breaker block inside an existing seam (`Backtester.run`); no new architectural component. Phase 17.5 (post-renumber: code-type steering, originally written as "17.3") stays `❌ Missing`; Phase 17 is NOT sealed (cross-check deferred until 17.5 lands). | docs-auditor |
| erratum | 2026-04-30 | Phase 17.4 spec (originally written as "17.2"; renumbered 2026-05-01 by Phase 23.2) — the rationale paragraph that originally lived around `docs/development-plan.md:1750–1754` ("`240s` under Phase 14.1's strategy override is multi-bar amortised") is **stale** and was the source of the DEBT-020 regression vector. Actual values: `strategies/chasulang_ict_smc.md:10` sets `claude_timeout_seconds: 480` (not 240); `src/strategy/loader.py:226–232` applies the override **per `analyze()` call**, NOT amortised across bars (every per-bar invocation gets the full 480s ceiling). The 60s default that flowed from this rationale was 8× smaller than chasulang's actual per-bar leash. Resolved at the code level by DEBT-020's same-cycle 60→600 bump; the spec text remains as written because senior-developer's scope rule is "planner owns spec text". Planner correction needed: rewrite lines 1750–1754 to reference 480s + per-call (not amortised) + the 600s post-fix default. | docs-auditor |
| 20.1 | 2026-05-01 | Phase 20.1 sealed — PnL Convention Single Source — Leverage No Double-Apply (FR-006, FR-025, NFR-001; DEBT-024 Resolved). New `src/utils/__init__.py` + `src/utils/trading_math.py` with `pnl_for_trade(entry, exit, qty, side) -> Decimal` helper (leverage NOT a parameter — qty already reflects the levered notional from `calculate_position_size`; making leverage a parameter would invite a future caller to reintroduce the bug). Routed every PnL site through the helper: `src/backtest/engine.py::_close_trade` (~lines 948-960) dropped `* leverage`, `src/trading/portfolio.py::calculate_unrealized_pnl` dropped `* leverage`, `src/trading/paper.py::close_position` (already correct shape) routed for symmetry. **Scope extension absorbed during quant-trader-expert review** (originally scheduled for Phase 20.2's territory): `src/strategy/performance.py::TradeHistory.calculate_pnl` (lines ~797-839) — both branches dropped `* self.leverage` from `pnl`, and `pnl_pct` reformulated as leverage-neutral (`(exit - entry) / entry` for longs, sign-inverted for shorts) since the persistence-layer was the highest-risk surface 20.2 was going to touch. `BacktestTrade.pnl` field docstring tightened by lead at handoff (lines ~174-176) to name the new convention. New tests: `tests/test_utils_trading_math.py` (11 module-level cases pinning both signs + edges); `tests/test_backtest_engine.py::TestPnLConventionAlignment` (4 cases — long/short numeric equality between backtester and paper-trader on fixed (entry, exit, qty, leverage) fixture + 2 originals); `tests/test_strategy_performance.py::TestTradeHistoryTracker::test_close_trade_persisted_pnl_routes_through_helper{,_short}` (2 persistence-layer parity cases). Cascaded test assertion updates: `tests/test_paper_trading.py` (8 across 7 methods), `tests/test_portfolio.py` (5 methods), `tests/test_strategy_performance.py` (3 `calculate_pnl` methods) — purely mechanical fixture corrections to the new correct numbers. 1226 total passing; ruff/mypy clean. **Note on DEBT-024 line-number staleness**: the original DEBT-024 description pointed at `src/backtest/engine.py:783-794` for the leverage site, but by the time the fix shipped the actual site had moved to `_close_trade` ~lines 948-960; recorded in the Resolved entry's note for future audit-trail readers. QA verdict: 🟢 Ship. Quant verdict: 🟢 Ship. No new debt. No ADR — extracts a math helper into a single-source-of-truth module; public contracts of `Backtester` / `Portfolio` / `PaperTrader` / `TradeHistory` unchanged (same signatures, same return types, same persistence shapes — only the numeric output shifts to the correct convention). 6/6 sub-task checkboxes verified ticked in dev's working-tree diff. Session log: `docs/sessions/2026-05-01-phase-20.1-pnl-helper-unification.md`. | docs-auditor |
| 20.2 | 2026-05-01 | Phase 20.2 scope reconciliation — Phase 20.1's scope extension into `src/strategy/performance.py::TradeHistory.calculate_pnl` (both branches + `pnl_pct` leverage-neutral reformulation) absorbed the highest-risk persistence-layer surface originally scoped for 20.2. Phase 20.2 is **NOT redundant**; remaining work (still `[ ]`): (a) `grep -rn "leverage" src/backtest/ src/trading/ src/strategy/` audit — confirm no other `* leverage` site exists outside the four already-routed callers (likely zero hits, but verification is the point); (b) field-docstring sweep beyond 20.1's tightening — `Portfolio.unrealized_pnl` field + `TradeHistory` `pnl` / `pnl_pct` field docstrings naming the leverage-neutral convention so future contributors don't reintroduce the bug; (c) `src/dashboard/pages/trading.py` Current-Equity card prose verification (no caption rewording expected; smoke check). Phase 20.3 baseline re-computation remains `[ ]` and is the closure for DEBT-029 (Medium, downstream of DEBT-024). **Planner action surfaced**: a linter cycle removed the Phase 19 / 20 / 21 / 22 / 23 / 24 sub-task definition blocks from this file (Phase 20.1 / 20.2 / 20.3 sub-task bullets, Phase 21 timezone hardening, Phase 22 atomic-JSON, Phase 23 AIDLC backfill, Phase 24 robustness polish — all the "what does each sub-task ship" prose). The Current Status table rows for these phases survived the prune and the change-history rows (including the original Phase 20 / 21 / 22 / 23 / 24 plan-add rows) remain as the historical record, but the spec text is gone. Reinstating the spec text is planner territory; flagged here as the next planner cycle's hygiene item before the next implementation cycle picks up Phase 20.2 / 20.3 or Phase 19. | docs-auditor |
| 18.2 | 2026-05-01 | Phase 18.2 spec added — Trade-Quality Diagnostic (FR-005, FR-021, FR-025, NFR-001; no new FR/NFR). Measurement-before-code-change pass over the 2026-04-30 closed-trade ledger (1W/8L, EV -8.73/trade, 11% WR) to attribute losses across slippage calibration, SL/RR appropriateness, accepted-vs-rejected EV gap, and per-strategy concentration before any further engine-knob edit; methodology locked in `docs/research/trade-quality-design-2026-05-01.md`, output lands next cycle as `docs/research/trade-quality-2026-05-01.md`. | product-planner |
| 20.3 | 2026-05-01 | Phase 20.3 deferred / DEBT-029 reframed → DEBT-043 registered + Phase 25 split-out (FR-025; no FR/NFR change). Senior-developer surfaced three blockers that invalidated 20.3's "mechanical re-run" framing: (1) `scripts/backtest_baselines.py` calls live Binance mainnet with no snapshot mode (module docstring lines 26-30, live-exchange construction lines 511-518) — non-deterministic, operator-only, not idempotent across operators / days; (2) `data/backtest/baselines/` directory absent on this checkout (gitignored), `docs/baselines.md` operator table all `_TBD_` (lines 124-136) — no inflated artefact had ever been persisted, so DEBT-029's "operator-facing artefact regeneration" was vacuous (operator impact = 0); (3) spec listed 4 baselines but script ships 5 (`rsi_universal` extra in `BASELINES` lines 108-149). The math fix (DEBT-024) closed at the code level by 20.1 (math) + 20.2 (discipline lock); what remained was reproducible-baseline design work, not "re-compute". DEBT-029 closed as **Reframed** (the "post-leverage-fix figures need restating" assumption was wrong — figures were never persisted in the first place). New DEBT-043 (Medium) registered for the underlying reproducibility debt: live-Binance regenerator with no snapshot mode, owned by Phase 25. Phase 20.3 status flipped `❌ Missing → ⏸ Deferred (Phase 25)` with footnote pointing at Phase 25 / DEBT-043. Phase 25 (Snapshot-Pinned Reproducible Baselines) registered with three sub-tasks: 25.1 snapshot dataset + format (CSV / parquet / JSONL pick + gitignore exception + freshness policy + format-validation test), 25.2 CLI `--snapshot` flag + script changes (snapshot loader path + `--refresh-snapshot` operator-gated mainnet path + cross-operator determinism test + spec-vs-script baseline-list reconciliation for the `rsi_universal` drift), 25.3 first run + populate `docs/baselines.md` (operator table replaces every `_TBD_` with snapshot-pinned figure + change-history row noting first-time-post-DEBT-024-fix). Requirements Mapping table row added for Phase 25 (FR-025 extending; no new FR/NFR). No code change this cycle. Session log: `docs/sessions/2026-05-01-phase-20.3-deferred-and-phase-25-registered.md`. | docs-auditor |
| 20.0 | 2026-05-01 | Phase 20 sealed (20.1 ✅, 20.2 ✅, 20.3 deferred to Phase 25) — DEBT-024 fully closed at the code level (math by 20.1, discipline by 20.2); reproducibility re-scoped to Phase 25 / DEBT-043. Trading-math correctness sweep complete; 1231 tests passing. | docs-auditor |
| 21.1 | 2026-05-01 | Phase 21.1 sealed 2026-05-01 — UTC-aware `from_unix_ms` / `now_utc` helpers (FR-020, NFR-007); 8 adapter sites + JsonlRotator read-side normalized; 16 new tests; pytest 1247. New `src/utils/time.py` (`from_unix_ms`, `now_utc`); `src/exchange/binance.py` 4 site swaps (~lines 233, 273, 504, 506) + import; `src/exchange/bybit.py` 4 site swaps (~lines 165, 202, 433-435) + import; `src/runtime/jsonl_rotator.py::_coerce_timestamp` UTC-normalized (read-side only — write-side `datetime.now()` swap is Phase 21.2). New `tests/test_utils_time.py` (10 cases pinning UTC tzinfo + non-UTC host invariance via `time_machine.travel(..., tz_offset=9)`); `tests/test_exchange_binance.py` and `tests/test_exchange_bybit.py` gain 3 cases each. Both reviewers (qa-reviewer + quant-trader-expert) returned 🟢. DEBT-025 stays Active — 21.1 closes the adapter read-side + JsonlRotator read-side only; full closure requires 21.2 (write-side `datetime.now()` sweep) + 21.3 (stale-quote payload coherence). **Quant follow-up surfaced**: dev's compatibility sweep flagged 12+ remaining naive `datetime.now()` write-sites that go beyond the original 21.2 spec scope (which only mentioned `JsonlRotator` write-side) — `src/runtime/engine.py:649`, `src/feedback/loop.py` (~6 sites), `src/proposal/interaction.py` (~3 sites), `src/strategy/performance.py:247/380/966/1002`, `src/ai/improver.py:334`. Spec text not edited (planner territory); flagged in session log Follow-up section so next planner cycle / senior-dev knows 21.2 needs broader sweep than the spec literally says. No ADR — adds a single helper module + mechanical call-site swaps; public contracts of `BinanceExchange` / `BybitExchange` / `JsonlRotator` unchanged (same return types — only the `tzinfo` attribute flips from `None` to `UTC`). Phase 21 stays open (21.2 + 21.3 still `[ ]`); cross-check deferred until phase seals. Session log: `docs/sessions/2026-05-01-phase-21.1-utc-timestamp-helper.md`. | docs-auditor |
| 21.3 | 2026-05-01 | Phase 21.3 sealed 2026-05-01 — stale-quote payload UTC-aware contract pinned + 3 regression tests; pytest 1265. (FR-008, NFR-012; DEBT-025 final-surface closure on top of 21.1's read-side fix and 21.2's write-side sweep). Verification + type-tightening, no behaviour change. `src/runtime/engine.py::_record_stale_quote_rejection` extended with formal "Timestamp coherence contract (DEBT-025 / Phase 21.3)" section in the docstring naming the five timestamp sources flowing into the rejection payload (engine wall-clock via `now_utc()`, ticker candle via `from_unix_ms(...)`, proposal entry via `now_utc()`, live price via `from_unix_ms(...)`, persisted record via `ensure_utc(...)` shim) — function body byte-identical below the new docstring section. 3 new regression tests in `tests/test_runtime_engine.py`: `test_stale_quote_rejection_payload_timestamps_are_utc_aware` (line 992 — coherence: every timestamp field on the event carries `tzinfo=UTC` under non-UTC host); `test_stale_quote_rejection_decision_at_minus_candle_ts_is_aware_math` (line 1033 — cross-source aware math: `decision_at - candle_ts` succeeds without `TypeError` and the resulting `timedelta` is correct); `test_stale_quote_rejection_tolerates_legacy_naive_record_on_disk` (line 1082 — legacy tolerance: pre-21.2 naive on-disk record flowing back through the read-side shim is silently UTC-coerced). 1262 → 1265 (+3). pytest / ruff / mypy / black clean. Quant verdict: 🟢 Ship — explicitly confirmed DEBT-025 is now fully closeable across the 21.1 / 21.2 / 21.3 chain. QA verdict: 🟡 Ship-with-note — qa-reviewer flagged `src/runtime/engine.py:436-440` as out-of-scope: a cap-rejection f-string was reformatted by the project's linter from a multi-line tuple to a single-line adjacent-literal form (`f"... " f"(...)"`); lead has explicit guidance from the system that this linter change was intentional and must NOT be reverted; recorded in session log for audit-trail completeness, not actioned. **DEBT-025 fully Resolved** (was the highest-priority Active High-class item; Active count drops 27 → 26, High drops 1 → 0, Resolved rises 16 → 17). No new debt. No ADR — mechanical TZ migration; no architectural seam shift. 3/3 sub-task checkboxes verified ticked. Session log: `docs/sessions/2026-05-01-phase-21.3-and-phase-21-seal.md`. | docs-auditor |
| 21.0 | 2026-05-01 | Phase 21 sealed (21.1 ✅, 21.2 ✅, 21.3 ✅) — DEBT-025 fully closed across helper module (`src/utils/time.py` with `from_unix_ms` / `now_utc` / `ensure_utc`), write-side sweep (12+ sites across runtime / feedback / proposal / strategy / ai / models / portfolio), Pydantic `field_validator(mode="after")` UTC-coerce on 7 models (9 fields), reader-boundary `ensure_utc(...)` shims at 5 sites, and stale-quote payload coherence contract docstring + 3 regression tests. Trading-engine timestamp surface UTC-aware end-to-end; every UTC-naive surface flagged in the 2026-04-30 3-agent audit is now closed. 1265 tests passing; ruff / mypy / black all clean. Phase 21 cross-check `docs/cross-checks/2026-05-01-phase-21-time-tz-hardening.md` PASS with 5 requirements complete (FR-008, FR-020, NFR-007, NFR-008, NFR-012), 0 gaps, 0 new debt. Recommended Phase 22 ordering: atomic JSON persistence helper (DEBT-028) before Phase 19 sub-account fan-out introduces N concurrent writers per cycle against the same persistence files. | docs-auditor |
| 21.2 | 2026-05-01 | Phase 21.2 sealed 2026-05-01 — UTC write-side sweep (12+ sites, 7 Pydantic models, 5 reader boundaries); pytest 1262. (FR-020, NFR-007, NFR-008; DEBT-025 follow-up — write-side closure on top of 21.1's read-side fix). Scope expanded from spec wording (rotator-only) to full sweep per team-lead's decision after 21.1's compatibility-sweep findings: splitting into a narrow 21.2 + new 21.4 would have left engine timestamps in a hybrid UTC-aware / tz-naive state across two cycles with cross-comparison `TypeError` risk live for the intervening commits. New `src/utils/time.py::ensure_utc(value)` helper added alongside the existing `from_unix_ms` / `now_utc` (3-function helper module now). Write-side `datetime.now()` swaps at 12+ sites: `src/runtime/jsonl_rotator.py:103` (the original 21.2 spec target), `src/runtime/engine.py` (multiple), `src/runtime/activity_log.py`, `src/feedback/loop.py` (~6 sites), `src/feedback/audit.py`, `src/proposal/interaction.py` (~3 sites), `src/proposal/engine.py`, `src/proposal/notification.py`, `src/strategy/performance.py` (~6 sites incl. field defaults), `src/strategy/base.py`, `src/ai/improver.py:334`, `src/models.py`, `src/trading/portfolio.py`. Pydantic `field_validator(mode="after")` UTC-coerce hooks added on 7 models (9 timestamp fields): `ActivityEvent`, `AuditEvent`, `Proposal`, `CandidateRecord`, `AssetSnapshot`, `PerformanceRecord` (`analysis_timestamp` + `exit_timestamp`), `TradeHistory` (`entry_time` + `exit_time`); `mode="after"` chosen because it always sees a `datetime` (no parsing duplication vs `mode="before"`). Reader-boundary naive-tolerance shims at 5 sites (`PortfolioTracker.load_snapshots`, `TradeHistoryTracker.get_trades_by_date_range`, `PerformanceTracker.get_records_by_date_range`, `ProposalHistory.purge_old`, `ProposalHistory.list_all` sort key) — one-way (read-only) shim that routes legacy on-disk naive values through `ensure_utc(...)` before compare; new writes are UTC-aware end-to-end via the write-side swap, on-disk format self-heals as records cycle. 13 pre-existing tests updated for new UTC-aware return shape; 12 new regression tests added (KST-host invariance on fresh writes + legacy-naive read tolerance). 1247 → 1262 (+12). pytest / ruff / mypy / black clean. Both reviewers (qa-reviewer + quant-trader-expert) returned 🟢; qa-reviewer flagged one cosmetic redundant `f` prefix at `engine.py:438` introduced during the sweep, fixed by lead before hand-off (non-blocking). DEBT-025 stays Active — full closure requires Phase 21.3 (stale-quote payload coherence — the only remaining surface). 21.3's existing spec text already frames it as "verification + type-tightening, not new behaviour" (lines 2704-2706); 21.2's full sweep makes every engine-side / adapter-side timestamp UTC-aware, so 21.3 is now well-positioned and no planner question is needed. No ADR — mechanical write-site swaps + Pydantic boundary validators + read-side compatibility shims; no new architectural component. Phase 21 still open (21.3 still `[ ]`); cross-check deferred until phase seals. 4/4 sub-task checkboxes verified ticked. Session log: `docs/sessions/2026-05-01-phase-21.2-utc-write-side-sweep.md`. | docs-auditor |
| 22.1 | 2026-05-01 | Phase 22.1 sealed 2026-05-01 — `atomic_write_text` helper + 5 site migrations + 19 new tests; pytest 1284 (+19). (FR-010, NFR-006, NFR-007, NFR-008; DEBT-028 closure). New `src/utils/io.py::atomic_write_text(path: Path, text: str) -> None` — writes to a uuid-suffixed `.tmp` (concurrent-writer-tolerant on the tmp side), then `os.replace(...)`s into the destination, with cleanup-on-exception so a raise mid-write leaves no orphan tmp file. Migrated 5 named load → mutate → save sites: `PerformanceTracker._save_records` (`src/strategy/performance.py:439`), `PerformanceTracker._update_summary` (`src/strategy/performance.py:494`), `TradeHistoryTracker._save_trades` (`src/strategy/performance.py:1077`), `PortfolioTracker._save_snapshots` (`src/trading/portfolio.py:407`), `ProposalHistory.save` (`src/proposal/interaction.py:245`). `src/runtime/engine.py::_record_stale_quote_rejection` covered transitively via `ProposalHistory.save`; doc comment added at the call-site naming the transitive coverage (rather than re-routing through the helper directly, which would duplicate the persistence path). 15 module-level helper unit tests + 4 site regression tests (one per migrated tracker — crash-mid-write preserves prior record, threaded last-writer-wins). 1265 → 1284 (+19). pytest / ruff / mypy / black clean. Both reviewers ship-class (qa 🟢, quant 🟢); senior-developer surfaced two adjacent-scope follow-ups (DEBT-044 `FeedbackLoop.save_state`, DEBT-045 `Backtester._save_result`) and quant emphasised the durability-vs-concurrency caveat as a hard prereq for Phase 19.2 fan-out (DEBT-046). Plan-text correction applied in-place: the DEBT-028 description and the Phase 22.1 sub-task spec line both pointed at `src/proposal/history.py`, but `ProposalHistory` actually lives in `src/proposal/interaction.py` (file does not exist under `history.py` — `src/proposal/` ships `engine.py`, `interaction.py`, `notification.py`); corrected at `docs/development-plan.md` Phase 22.1 sub-task block. Phase 19.2 Prerequisites line added citing DEBT-046 (concurrent-mutation lock or per-account file partitioning required before sub-account fan-out). No ADR — single helper module + mechanical call-site swaps; public contracts unchanged. Phase 22 still open (22.2 paper-trader liquidation visibility still `[ ]`); cross-check deferred until phase seals. 7/7 sub-task checkboxes verified ticked. Session log: `docs/sessions/2026-05-01-phase-22.1-atomic-write-helper.md`. | docs-auditor |
| 22.1d | 2026-05-01 | DEBT-028 Resolved (Phase 22.1); DEBT-044 / DEBT-045 / DEBT-046 registered. DEBT-046 named as **hard prereq for Phase 19.2** in `docs/development-plan.md` Phase 19.2 Prerequisites line (concurrent-mutation loss is silent under parallel sub-account workers; resolution shapes per-file lock helper via `fcntl.flock` OR per-account file partitioning, planner picks). TECH-DEBT statistics: Active 26 → 28 (DEBT-028 -1 Medium; DEBT-044 +1 Low, DEBT-045 +1 Low, DEBT-046 +1 Medium); Resolved 17 → 18; Medium stays at 7; Low 19 → 21. | docs-auditor |
| 22.2 | 2026-05-01 | Phase 22.2 sealed 2026-05-01 — paper trader liquidation visibility, `LIQUIDATED` ActivityEvent, opt-out flag; 6 regression tests; pytest 1290 (+6). (FR-010, NFR-007, NFR-008; DEBT-027 closure). New `ActivityEventType.LIQUIDATED` enum member (`src/runtime/activity_log.py:109`) with documented structured payload contract (`symbol`, `side`, `entry`, `exit`, `qty`, `realized_pnl`, `balance_before`, `balance_after`). `PaperTrader.close_position` rewritten under-water branch: detection via projected-free predicate `projected_free = balance.free + (pnl - exit_fee) < 0` evaluated *before* the mutation lands (split detection from remediation). Default behaviour records true negative equity AND emits `LIQUIDATED`; opt-out flag `auto_deposit_on_liquidation=True` reverts to legacy clamp-to-zero (still emits the event — flag controls balance treatment, not event semantics). `PaperBalance.free` Pydantic constraint relaxed (dropped `ge=0`) so the negative-equity round-trip survives `validate_assignment`; lock / deduct / reserve paths still enforce overdraw protection at their own boundaries (relaxation is permission to *report* negative equity, not to silently underflow during normal operations). `PaperTrader.__init__` got 2 backward-compatible kwargs: `activity_log` (default `None`, legacy callers without an activity log still work) and `auto_deposit_on_liquidation` (default `False`, correctness-first). `EngineConfig.paper_auto_deposit_on_liquidation: bool = Field(default=False)`; `Settings.paper_auto_deposit_on_liquidation` env-overridable via `PAPER_AUTO_DEPOSIT_ON_LIQUIDATION`; `.env.example` documented; `src/main.py::build_engine` plumbs `ActivityLog` and the flag into `build_trader`. 6 regression tests in `tests/test_paper_trading.py` pin the contract: under-water default emits LIQUIDATED, under-water default round-trips negative equity, auto-deposit opt-out clamps but still emits, exit-fee-only shortfall (historical line-626 branch) takes liquidation path, normal close stays silent, flag-on payload parity with default. 1284 → 1290 (+6). pytest / ruff / mypy / black clean. Both reviewers ship-class (qa 🟢, quant 🟢); quant surfaced backtester asymmetry (no margin / liquidation modeling — `balance += pnl_delta` runs arbitrarily negative without LIQUIDATED analogue) as DEBT-047 (Medium). Plan-text drift noted: DEBT-027 cited `paper.py:619,626` as under-water clamp sites; actual liquidation branch lives ~656-720 — same pattern as DEBT-024 stale line refs and DEBT-028 / 22.1 path drift. No ADR — visibility addition + opt-out flag + constraint relaxation; public contracts (kwarg defaults backward-compatible). 5/5 sub-task checkboxes verified ticked. Session log: `docs/sessions/2026-05-01-phase-22.2-and-phase-22-seal.md`. | docs-auditor |
| 22.0 | 2026-05-01 | Phase 22 sealed (22.1 ✅, 22.2 ✅) — DEBT-028 + DEBT-027 Resolved; DEBT-046 reserved as Phase 19.2 hard prereq; DEBT-047 registered for backtester liquidation parity follow-up. Persistence layer now crash-safe across 5 named load → mutate → save sites + 1 transitive (`atomic_write_text` helper, uuid-suffixed tmp + `os.replace` + cleanup-on-exception); paper trader's liquidation surface matches live-exchange semantics (structured `LIQUIDATED` ActivityEvent + true-negative-equity round-trip + opt-out flag for legacy testing). 1265 → 1290 tests (+25 net new across the phase: 15 atomic-helper unit + 4 site regression + 6 liquidation contract). ruff / mypy / black clean throughout. Phase 22 cross-check `docs/cross-checks/2026-05-01-phase-22-persistence-atomicity-liquidation.md` PASS — 4 requirements complete (FR-010, NFR-006, NFR-007, NFR-008), 0 gaps blocking phase seal. DEBT residue carrying forward: DEBT-044 / DEBT-045 (Low atomic follow-ups, mechanical), DEBT-046 (Medium, **hard prereq for Phase 19.2** — concurrent-mutation loss; resolution shapes per-file `fcntl.flock` OR per-account file partitioning), DEBT-047 (Medium, backtester liquidation parity follow-up; consider folding into Phase 24). TECH-DEBT statistics post-phase: Active 28 → 28 (DEBT-027 -1 Medium; DEBT-047 +1 Medium); Medium stays at 7; Low unchanged at 21; Resolved (All Time) 18 → 19. Recommended next phase: Phase 19 — Sub-Account / Capital Segmentation, **conditional on DEBT-046 resolution before 19.2 lands**. | docs-auditor |
| 23.1 | 2026-05-01 | Phase 23.1 sealed 2026-05-01 — docs drift backfill (NFR-001; DEBT-037 closure). Documentation-only cycle, no source code or test changes. (a) Backfilled 2 missing session logs surfaced by the 2026-04-30 audit: `docs/sessions/2026-04-30-phase-17.2-portfolio-snapshot-recording.md` (commit `094a79d`, portfolio snapshot recording in runtime cycle) and `docs/sessions/2026-04-30-phase-17.3-closed-trade-performance-records.md` (commit `ab9dc32`, closed-trade `PerformanceRecord` persistence) — both reconstructed from the verbatim commit body and `git show` diff; both carry an explicit "Backfill notice" prologue naming the reconstruction source so future audits can distinguish backfilled logs from real-time ones. (b) Backfilled the missing Phase 15 cross-check: `docs/cross-checks/2026-04-28-phase-15-diagnostic-clarity.md` reconstructed from the Phase 15 spec block + the `2026-04-28-phase-15.1-diagnostic-clarity.md` session log + the change-history row; same backfill-notice prologue. (c) `CLAUDE.md` project-structure tree extended to include `src/runtime/` (engine, activity_log, jsonl_rotator), `src/tools/` (operator scripts), `src/utils/` (`trading_math.py` from Phase 20.1, `time.py` from Phase 21.1, `io.py` from Phase 22.1), and `src/main.py` entry point — four surfaces that had shipped but were never listed. (d) `DESIGN.md §2.3` rewritten end to end: stale `class ClaudeClient` (which never existed in code) replaced with the actual `class ClaudeCLI` from `src/ai/claude.py:46` carrying real method signatures (`__init__(timeout, claude_path, max_retries)`, `is_available()`, `async analyze(prompt) -> dict[str, Any]`, `async complete(prompt) -> str`); parallel `class StrategyImprover` block from `src/ai/improver.py:98` added (`generate_idea`, `generate_user_idea`, `improve`); constraint line clarified to name the `analyze` / `complete` split. (e) `docs/TECH-DEBT.md` ordering: DEBT-018 reordered above DEBT-021 (was below DEBT-019..23 separated by an internal `---` separator); the stray `---` separator removed; Statistics table recomputed by counting `### DEBT-` headings in Active vs Resolved sections (Active 28 → 27 after DEBT-037 closes; Resolved 19 → 20; Medium unchanged at 7; Low 21 → 20). (f) DEBT-037 moved Active → Resolved with full resolution prose. 6/6 sub-task checkboxes verified ticked. No tests, no source code changes, no ADR (documentation-only cycle by spec). Session log: `docs/sessions/2026-05-01-phase-23.1-docs-drift-backfill.md`. Phase 23 still open (23.2 Phase 17.2 / 17.3 numbering reconciliation still `[ ]`); cross-check deferred until phase seals. | docs-auditor |
| 23.2 | 2026-05-01 | Phase 23.2 sealed 2026-05-01 — Phase 17.2 / 17.3 / 17.4 / 17.5 number reconciliation (NFR-001; documentation-only, no code or tests). Locks in the renumbering the planner applied to the dev-plan headers + status table earlier this cycle so the labels in change-history rows, Requirements-Mapping, and the 17.4 session log match the post-rebrand spec body. (a) Per-row change-history relabel: the three pre-existing rows `| 17.2 | Phase 17.2 added — Auto-Research Workflow Unblock`, `| 17.3 | Phase 17.3 added — Code-Type Steering`, and `| 17.2 | Phase 17.2 complete - Auto-Research Workflow Unblock` retagged to `| 17.4 | Phase 17.4 added`, `| 17.5 | Phase 17.5 added`, and `| 17.4 | Phase 17.4 complete` respectively, each with an inline erratum parenthetical "(Originally written under 'Phase 17.2' / '17.3'; renumbered 2026-05-01 by Phase 23.2)" so audit-trail readers can trace the historical names. The "Phase 17.3 stays ❌ Missing" trailing clause inside the 17.4-complete row repointed to "Phase 17.5 (post-renumber: code-type steering, originally written as '17.3') stays ❌ Missing" to match the new header. The DEBT-020 erratum row leading with "Phase 17.2 spec at lines 1750–1754" repointed to reference "Phase 17.4 spec (originally written as '17.2'; renumbered 2026-05-01 by Phase 23.2) — the rationale paragraph that originally lived around lines 1750–1754" since the line numbers have drifted post-renumber but the erratum's substance still applies. (b) Spec-body internal references: 5 in-prose mentions of "Phase 17.2" / "Phase 17.3" inside the 17.4 / 17.5 spec bodies (referencing themselves under their pre-renumber names — `1781:Phase 17.2 closes this with the **A + C** combo`, `1788:separately as Phase 17.3`, `1907:deferred to Phase 17.3`, `1911:Phase 17.2 unblocks`, `1920:so the unblock (17.2) and the cleanup (17.3) can land independently`, `1934:so non-flagged picks retain the 17.2-hardened prompt path`, `1971:17.2 ships the unblock; 17.3 ships the cleaner long-term path`) all repointed to "Phase 17.4" / "Phase 17.5". (c) Requirements-Mapping table row for Phase 17 expanded from "(17.1) ... (17.2) ... (17.3)" three-tuple to the full 17.1–17.5 enumeration with FR-031 / NFR-008 / FR-005 / FR-021 added (consumed by 17.2 portfolio-snapshot + 17.3 closed-trade-performance, the two backfilled-via-23.1 spec bodies whose FRs the 23.1 backfill landed in the spec but the Requirements-Mapping row hadn't yet been updated to absorb). (d) Phase 23 Requirements-Mapping row updated to enumerate 23.1-vs-23.2 ownership of the items + name the 17.4 session-log rename. (e) Session log `docs/sessions/2026-04-30-phase-17.2-auto-research-unblock.md` renamed via `git mv` to `2026-04-30-phase-17.4-auto-research-unblock.md`; new "Renumber notice" prologue added at the top of the log naming the rename + the date + the linkage to Phase 23.2 (body byte-identical below the prologue, original "Phase 17.2" prose preserved verbatim per audit-trail discipline — the prologue tells the reader "in-prose `Phase 17.2` references should be read as `Phase 17.4`"). (f) Audit confirmed commit `41f9212` already had a real-time session log (it was the renamed file in (e)); no new backfill needed for that commit. 4/4 sub-task checkboxes ticked. No tests, no source code changes, no ADR (documentation-only cycle by spec). Status table row "Phase 17.2 / 17.3 Numbering Reconciliation" flipped to ✅ Complete and renamed to "Phase 17.2 / 17.3 / 17.4 / 17.5 Numbering Reconciliation" to reflect the actual scope. Session log: `docs/sessions/2026-05-01-phase-23.2-and-phase-23-seal.md`. | docs-auditor |
| 23.0 | 2026-05-01 | Phase 23 sealed (23.1 ✅, 23.2 ✅) — DEBT-037 Resolved (closed by 23.1); full audit-trail backfill complete. 23.1 closed the 4 docs-drift items the 2026-04-30 3-agent comprehensive audit named (2 missing session logs for shipped Phase 17.2 / 17.3 commits, 1 missing Phase 15 cross-check, `CLAUDE.md` tree + `DESIGN.md` ClaudeClient → ClaudeCLI rename, `TECH-DEBT.md` ordering / Statistics drift). 23.2 closed the duplicate-numbering meta-issue: shipped portfolio-snapshot recording (`094a79d`) → formal Phase 17.2; shipped closed-trade performance records (`ab9dc32`) → formal Phase 17.3; shipped auto-research workflow unblock (`41f9212`) → formal Phase 17.4 (session log renamed via `git mv` from the original "phase-17.2-auto-research-unblock.md" filename); previously-spec'd code-type steering renumbered to formal Phase 17.5 (still ❌ Missing — the only remaining sub-task before Phase 17 can seal). Phase 23 cross-check `docs/cross-checks/2026-05-01-phase-23-aidlc-hygiene.md` PASS — 1 requirement complete (NFR-001), 0 gaps blocking phase seal, 0 new debt. No source code edits, no tests, no ADR (documentation-only phase by spec). Recommended next phase: Phase 17.5 (Code-Type Steering — DEBT-019 Option B, the long-term cleanup behind 17.4's unblock) to seal Phase 17, OR Phase 19.1 (Sub-Account Foundation) if the operator prefers to lean into the multi-account-segmentation track first. Phase 24 (strategy robustness polish — 5 Low-priority debt items batched) remains scoped but uncommitted. | docs-auditor |
| 20.2 | 2026-05-01 | Phase 20.2 sealed 2026-05-01 — leverage math sweep + docstring convention pinned + regression guard test added; pytest 1231; DEBT-024 fully closed. (FR-006, FR-025, NFR-001; DEBT-024 follow-up — discipline lock on top of 20.1's math fix). Grep audit across `src/backtest/`, `src/trading/`, `src/strategy/`: 8-row classification (4 margin / position-sizing sites kept where `* leverage` is the correct shape; 4 PnL sites confirmed already routed through `pnl_for_trade(...)` per 20.1) — no missed `* leverage` anywhere on the PnL surface. Convention docstrings added on `src/trading/portfolio.py::AssetSnapshot.unrealized_pnl` + `Portfolio.unrealized_pnl` field listings, `src/strategy/performance.py::TradeHistory.pnl` + `pnl_percent` field listings, and `src/models.py::Position.calculate_pnl` method — each names the leverage-neutral convention and points at `pnl_for_trade` ("PnL is computed against leveraged notional via `pnl_for_trade`; do not re-multiply by `leverage` downstream"). New regression-guard test `tests/test_leverage_pnl_no_double_apply.py` (5 tests: 4 file scans flagging any `pnl.*\* *leverage` or `\* *self\.leverage` reintroduction outside the allow-listed margin sites, plus 1 self-test of the guard regex). Module docstring acknowledges the indirect-aliasing limitation (regex catches direct `* leverage` reintroduction, not arbitrary aliasing — defence-in-depth alongside Phase 20.1's `TestPnLConventionAlignment` numeric parity, not a sole gate) per quant-trader-expert ship-with-note. Two cosmetic single-line collapses in `src/trading/portfolio.py` (lines 366, 381) crept in via black during the docstring edit pass — harmless reformats, no behaviour change, flagged in session log per QA-reviewer ship-with-note. 1226 → 1231 tests (+5). pytest / ruff / mypy / black clean. No new debt; no ADR (discipline lock + docstring sweep + regex test, no new contracts). 5/5 sub-task checkboxes verified ticked. QA verdict: 🟡 Ship-with-note (cosmetic reformats; addressed). Quant verdict: 🟡 Ship-with-note (regression-guard alias gap; addressed via module docstring). Both notes resolved. Phase 20 still open (2/3 — 20.3 baseline re-computation pending; closes DEBT-029 and seals Phase 20). DEBT-024 fully closed (math by 20.1, discipline by 20.2). Session log: `docs/sessions/2026-05-01-phase-20.2-leverage-math-alignment.md`. | docs-auditor |
| 24.1 | 2026-05-01 | Phase 24 sealed 2026-05-01 — Strategy Robustness Polish 5-DEBT bundle (DEBT-030 / 031 / 032 / 033 / 034 — all 5 Low-priority items the 2026-04-30 3-agent audit batched as "robustness polish"). Two-pass cycle inside one Phase 24: initial bundle landed 5 fixes per spec (per-bar `EquityPoint` model + `BacktestResult.equity_curve` + `Backtester._build_equity_curve` mark-to-market, MA-crossover SL window roll-back, OOS Sharpe IS-floor SKIP guard, ticker-age freshness threshold, live cold-start `_cold_start_blocks_live` guard); quant-driven follow-up addressed 4 review concerns in same cycle (DEBT-030: `_bars_per_year` derived from `EquityPoint` median Δt so Sharpe annualization tracks candle cadence not fixed `trades_per_year`; DEBT-033: opt-in `EngineConfig.reject_if_stale_quote: bool = False` flag with `_record_no_live_data_rejection` rejection path on both stale + fetch-error branches, plumbed via `Settings.engine_reject_if_stale_quote` + `.env.example`; DEBT-032: `minimum_is_trades` default 5 → 10 with rationale on field; DEBT-034: new `ActivityEventType.COLD_START_BLOCKED` enum + structured event payload). 18 new tests across 5 test files: 3 intra-trade MDD (`TestEquityCurveMaxDrawdown`), 4 annualization (`TestEquityCurveSharpeAnnualization`, hand-computed √8760 ≈ 22.066), 2 MA SL window (long + short), 3 OOS IS-floor (boundary + default-pin + direction), 5 stale-quote (freshness × opt-in × both branches), 4 cold-start (live-block + paper-allow + threshold-release + mixed; live-block now also asserts ActivityEvent payload). pytest 1290 → 1311 (+21 incl. 3 fix-cycle additions on top of the initial 18). ruff / mypy / black clean. Quant sign-off granted on `strategies/ma_crossover.py` SL window change (Hard Rule #3 honored) — strict signal-quality improvement, no new false positives. Both reviewers 🟢 ship after fix cycle. Active TECH-DEBT count 27 → 22 (DEBT-030/031/032/033/034 Resolved); Low count 20 → 15; Resolved (All Time) 20 → 25. Cross-check `docs/cross-checks/2026-05-01-phase-24-strategy-robustness-polish.md` PASS (FR-006 / FR-008 / FR-024 / FR-025 / NFR-001 all ✅; 0 gaps; 0 new debt). Phase 24 single-sub-task — phase seals here. Session log: `docs/sessions/2026-05-01-phase-24-and-phase-24-seal.md`. | docs-auditor (lead-orchestrated due to upstream rate-limit) |
| 24.0 | 2026-05-01 | Phase 24 sealed (24.1 ✅) — DEBT-030 / 031 / 032 / 033 / 034 all Resolved; the 5-DEBT Low-priority bundle from the 2026-04-30 audit fully closed. Per-bar equity curve in the analyzer (intra-trade MDD now visible; Sharpe annualization tracks candle cadence). MA-crossover SL window excludes current candle (silently-dropped bullish/bearish crosses where current candle was the local 5-bar low/high now emit cleanly). OOS Sharpe gate SKIPs strategies with N<10 IS trades instead of FAILing them (Sharpe with N<10 has prohibitively high variance). Ticker freshness threshold + opt-in `reject_if_stale_quote` flag for live-mode safety. Live cold-start guard refuses live proposals when no technique has ≥ N closed trades + emits structured `COLD_START_BLOCKED` ActivityEvent for operator visibility. No new debt introduced. Recommended next phase: Phase 25 (Snapshot-Pinned Reproducible Baselines, DEBT-043) — the only remaining sub-task in the post-audit follow-up plan with a clear scope. DEBT-046 (concurrent-mutation atomic-write loss) remains a hard prerequisite for Phase 19.2 sub-account fan-out (carry-over flag, not a Phase 24 concern). | docs-auditor |
| 25.1 | 2026-05-01 | Phase 25.1 sealed 2026-05-01 — Snapshot Dataset + Format (FR-025 extending; partial DEBT-043 closure). New `src/backtest/snapshot.py` module: `SnapshotMetadata` Pydantic model (UTC-coerce field validator per Phase 21.2 pattern), `Snapshot` bundling metadata + `list[OHLCV]`, `SnapshotValidationError`, `load_snapshot` / `save_snapshot` (atomic via Phase 22.1 `atomic_write_text`), `is_snapshot_fresh` (90-day default, `now=` injectable), `baseline_directory` helper centralising `<SYMBOL>__<timeframe>` naming. Format chosen: CSV + JSON sidecar — rationale per session log (must be committed for reproducibility, version-control diff-friendly, no extra deps). `ohlcv.csv` header pinned at `timestamp,open,high,low,close,volume`; metadata.json carries `symbol / timeframe / source / fetched_at / candle_count / first_timestamp / last_timestamp / fetcher_version="phase-25.1"`. `Decimal(cell)` round-trip (no `float()` drift). Validation cross-checks: header order, row column count, `metadata.candle_count == len(ohlcv)`, UTC-coerce on read. `.gitignore` switched `data/` → `data/*` with carve-backs (`!data/backtest/`, `!data/backtest/snapshots/**`); verified other `data/` subdirs (logs, audit, feedback, trades) still ignored via `git check-ignore`. New `data/backtest/snapshots/baselines/.gitkeep` placeholder + `data/backtest/snapshots/README.md` operator documentation. 27 new tests covering round-trip, schema breach (8 cases), UTC contract, freshness boundary; pytest 1311 → 1338 (+27). ruff / mypy / black clean. Reviewers 🟢🟢. Quant carry-overs for 25.2: (a) slice bounds enforcement against `len(snapshot.ohlcv)`; (b) consider tighter active-use freshness window (30d for promotion gates, 90d as absolute stale ceiling). Session log: `docs/sessions/2026-05-01-phase-25.1-snapshot-format.md`. | docs-auditor (lead-orchestrated) |
| 25.2 | 2026-05-01 | Phase 25.2 sealed 2026-05-01 — `--snapshot` CLI flag + script changes (FR-025 extending; partial DEBT-043 closure). 4 new CLI flags on `scripts/backtest_baselines.py`: `--snapshot [PATH]` opt-in reproducible mode (default `data/backtest/snapshots`), `--refresh-snapshot` operator-gated mainnet fetch path (sole entry point that touches Binance live, prints two operator-visible warnings), `--max-snapshot-age-days INT` default 30 (env-overridable via `ENGINE_BASELINE_MAX_SNAPSHOT_AGE_DAYS`; quant-recommended active-use window — `DEFAULT_MAX_AGE_DAYS=90` in `snapshot.py` unchanged as absolute stale ceiling), `--snapshot-root PATH` companion. `--snapshot` and `--refresh-snapshot` mutually exclusive via `argparse.add_mutually_exclusive_group()`. New `SnapshotExchange` class in `src/backtest/snapshot.py` (free-standing, not BaseExchange subclass — regenerator only consumes connect/disconnect/get_ohlcv) with quant carry-over slice-bounds enforcement: `clamped_limit = min(limit, len(rows))` clamps oversized requests to snapshot length; `if since > last_ts_ms: return []` refuses extrapolation past `last_timestamp`. `refresh_snapshots` async helper writes via `save_snapshot` (atomic per Phase 22.1) with `now_utc()` `fetched_at` and `fetcher_version="phase-25.2"`. `Settings.engine_baseline_max_snapshot_age_days = 30` env-overridable. `rsi_universal` reconciliation: KEEP — quant verified against `strategies/rsi.py` lines 11-18 ("universal-cadence fallback"); 25.3 must enumerate all 5 baselines in `docs/baselines.md`. 10 new tests including `test_cross_operator_determinism_byte_identical` (runs `run_all` twice, scrubs `run_id` + `trade_id` UUIDs — quant-approved as operator-trace IDs not strategy state, asserts byte equality on remaining fields and `summary.json`). pytest 1338 → 1348 (+10), ruff/mypy/black clean. Reviewers 🟢🟢. Carry-over for 25.3: call out 30-day active vs 90-day absolute stale window in `docs/baselines.md`. New TECH-DEBT candidate (informational): `BacktestResult.run_id` / `Trade.trade_id` use `uuid.uuid4()` so byte-identical determinism requires UUID scrubbing today; future `--deterministic-ids` flag could land truly byte-identical artefacts. Session log: `docs/sessions/2026-05-01-phase-25.2-snapshot-cli.md`. | docs-auditor (lead-orchestrated) |
| 25.3 | 2026-05-01 | Phase 25.3 Part A sealed 2026-05-01 — operator runbook + doc restructure (FR-025 extending; partial DEBT-043 closure at infrastructure level). 25.3 split into Part A (autonomous, this sub-task) + Part B (one-time operator action with live Binance read-only credentials, post-seal). `docs/baselines.md` restructured with new sections: **Operator runbook** (5-step first-fetch procedure: credential setup → `--refresh-snapshot` → directory verification → `--snapshot` run → commit), **Snapshot freshness policy** (30-day active-use window via `--max-snapshot-age-days` default vs 90-day absolute stale ceiling per `DEFAULT_MAX_AGE_DAYS` in `snapshot.py`; quant carry-over from 25.2), **Reproducibility note** (cross-operator byte-equality contract; UUID divergence approved), all 5 baselines enumerated (`rsi_universal` + `rsi_4h` / `rsi_15m` / `bollinger_band_reversion` / `ma_crossover`). Two spec deviations documented + surfaced as DEBT-048 (Low): (1) 9-column table widening kept at 6 (autonomous-shipping `_TABLE_PATTERN` rewriter hard-wired to legacy header; widening would break 3 tests); (2) `_AWAITING_OPERATOR_FIRST_RUN_` placeholder kept as `_TBD_` (existing tests assert the literal). Both new semantics explained in surrounding prose. No code changes (Part A is docs-only). pytest 1348 unchanged from 25.2; ruff/mypy/black clean. Reviewers skipped for docs-only sub-task. Session log: `docs/sessions/2026-05-01-phase-25.3-and-phase-25-partial-seal.md`. | docs-auditor (lead-orchestrated) |
| 25.0 | 2026-05-01 | Phase 25 sealed (partial — 25.1 ✅, 25.2 ✅, 25.3 Part A ✅; 25.3 Part B operator action documented + non-gating) — DEBT-043 Resolved at infrastructure level. Reproducibility infrastructure for backtest baselines: snapshot CSV + JSON-sidecar format with UTC-aware Pydantic validation and atomic write (Phase 22.1 / 21.2 conventions); `--snapshot` / `--refresh-snapshot` / `--max-snapshot-age-days` / `--snapshot-root` CLI surface with mutually-exclusive guard between read and refresh modes; `SnapshotExchange` adapter with quant-mandated slice-bounds enforcement (no extrapolation past `last_timestamp`); 30-day active-use freshness vs 90-day absolute stale ceiling; cross-operator byte-determinism contract (`test_cross_operator_determinism_byte_identical`); operator runbook + reproducibility note in `docs/baselines.md`; new TECH-DEBT entries: DEBT-048 (Low — table widening polish deferred). Phase 25 cross-check `docs/cross-checks/2026-05-01-phase-25-snapshot-pinned-baselines.md` PASS — FR-025 ✅, NFR-006 ✅, NFR-007 ✅; 0 gaps blocking; 0 ⚠️ partial. pytest 1311 → 1348 (+37 across 25.x). Two minor stylistic carry-overs (implicit string concat at `scripts/backtest_baselines.py:773,834`) noted but non-blocking. | docs-auditor |

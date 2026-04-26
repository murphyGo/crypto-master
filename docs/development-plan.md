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
| Multi-Timeframe Strategy Support | ❌ Missing | 9 |

**Status Legend**: ✅ Complete | 🔄 In Progress | ❌ Missing

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

- [ ] Extend `PromptStrategy.format_prompt` to accept
  `ohlcv_by_timeframe: dict[str, list[OHLCV]]` and
  `current_price: Decimal`; fill `{ohlcv_<timeframe>}` and
  `{current_price}` placeholders alongside the existing three
- [ ] Adjust `BaseStrategy.analyze` (or add an opt-in companion
  method) so multi-TF data threads through without breaking
  single-TF strategies
- [ ] Extend `ProposalEngine._propose_for_symbol` to read
  `strategy.info.timeframes`, fetch each via `exchange.get_ohlcv`,
  and pass the dict to `strategy.analyze` — fall back to the
  current single-TF path when the strategy declares one timeframe
- [ ] Update `Backtester` to feed multi-TF candles per simulated
  step (or explicitly defer to a follow-up sub-task and document
  the gap in the session log)
- [ ] Verify `chasulang_ict_smc` runs end-to-end on the new
  contract, returns parseable JSON, and the engine produces
  proposals on its symbols (BTC/ETH/XRP)
- [ ] Write unit tests covering the multi-TF `format_prompt` path,
  the engine's multi-TF fetch flow, and a chasulang-style smoke
  test

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

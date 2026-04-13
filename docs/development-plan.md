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
| Backtesting | 🔄 In Progress | 5 |
| Feedback Loop | ❌ Missing | 5 |
| Trading Proposal | ❌ Missing | 6 |
| UI Dashboard | ❌ Missing | 7 |

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

- [ ] `src/backtest/analyzer.py` - PerformanceAnalyzer class
- [ ] Win rate calculation
- [ ] Total return / annualized return
- [ ] Maximum drawdown (MDD) calculation
- [ ] Sharpe ratio calculation
- [ ] Report generation (md format)
- [ ] Write unit tests

### 5.3 Claude-Based Technique Improvement

- [ ] `src/ai/improver.py` - StrategyImprover class
- [ ] Improvement prompt generation based on performance data
- [ ] New technique idea generation prompt
- [ ] User idea input → technique generation
- [ ] Generated technique storage (`strategies/experimental/`)
- [ ] Write unit tests

### 5.4 Automated Feedback Loop

- [ ] `src/feedback/loop.py` - FeedbackLoop orchestrator
- [ ] Loop execution: analysis → improvement → backtesting → evaluation
- [ ] Automatic decision based on performance thresholds
- [ ] Technique adoption flow (user approval)
- [ ] Loop state saving and resumption
- [ ] Write unit tests

---

## Phase 6: Trading Proposal System

**Related Requirements**: FR-011, FR-012, FR-013, FR-014, FR-015

### 6.1 Proposal Engine

- [ ] `src/proposal/engine.py` - ProposalEngine class
- [ ] Bitcoin trading proposal logic (apply best technique)
- [ ] Altcoin scan and proposal logic (multi-coin analysis)
- [ ] Proposal score calculation (performance prediction)
- [ ] Write unit tests

### 6.2 User Interaction

- [ ] `src/proposal/interaction.py` - User interaction handling
- [ ] Proposal display format (CLI)
- [ ] Accept/reject input handling
- [ ] Proposal history storage (`data/proposals/`)
- [ ] Write unit tests

### 6.3 Notification System

- [ ] `src/proposal/notification.py` - Notification module
- [ ] Console notification
- [ ] File-based notification log
- [ ] Write unit tests

---

## Phase 7: UI Dashboard

**Related Requirements**: FR-028, FR-029, FR-030, FR-031, FR-032, NFR-003

### 7.1 Streamlit App Basic Structure

- [ ] `src/dashboard/app.py` - Main Streamlit app
- [ ] App layout setup (sidebar, main area)
- [ ] Page navigation configuration
- [ ] Common style/theme settings

### 7.2 Analysis Technique Status Page

- [ ] `src/dashboard/pages/strategies.py` - Technique status page
- [ ] Display registered technique list
- [ ] Display technique-specific performance metrics
- [ ] Performance trend charts

### 7.3 Trading Status Page

- [ ] `src/dashboard/pages/trading.py` - Trading status page
- [ ] Display active positions (paper/live)
- [ ] Recent trade history
- [ ] Asset status and PnL summary
- [ ] Equity curve chart

### 7.4 Feedback Loop Status Page

- [ ] `src/dashboard/pages/feedback.py` - Feedback loop page
- [ ] Experimental technique list
- [ ] Backtesting result display
- [ ] Loop progress status

### 7.5 Tapbit Integration (Deferred)

- [ ] `src/exchange/tapbit.py` - TapbitExchange class implementation

---

## Requirements Mapping

| Phase | Related Requirements |
|-------|---------------------|
| Phase 1 | NFR-001, NFR-004, NFR-005 |
| Phase 2 | FR-016, FR-017, FR-018, FR-019, FR-020, NFR-009 |
| Phase 3 | FR-001, FR-002, FR-003, FR-004, FR-005, NFR-002, NFR-005, NFR-007, NFR-008, NFR-010 |
| Phase 4 | FR-006, FR-007, FR-008, FR-009, FR-010, NFR-012 |
| Phase 5 | FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, FR-027, NFR-006 |
| Phase 6 | FR-011, FR-012, FR-013, FR-014, FR-015 |
| Phase 7 | FR-028, FR-029, FR-030, FR-031, FR-032, NFR-003 |

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

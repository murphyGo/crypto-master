# Crypto Master - Development Plan

## Reference Documents

- `docs/requirements.md` - Requirements Specification
- `docs/inception.md` - Project Concept Document

---

## Current Status

| Component | Status | Phase |
|-----------|--------|-------|
| Project Setup | ❌ Missing | 1 |
| Configuration Management | ❌ Missing | 1 |
| Exchange Abstraction | ❌ Missing | 2 |
| Binance Integration | ❌ Missing | 2 |
| Bybit Integration | ❌ Missing | 2 |
| Analysis Technique Framework | ❌ Missing | 3 |
| Claude Integration | ❌ Missing | 3 |
| Trading Strategy | ❌ Missing | 4 |
| Paper Trading | ❌ Missing | 4 |
| Live Trading | ❌ Missing | 4 |
| Backtesting | ❌ Missing | 5 |
| Feedback Loop | ❌ Missing | 5 |
| Trading Proposal | ❌ Missing | 6 |
| UI Dashboard | ❌ Missing | 7 |

**Status Legend**: ✅ Complete | 🔄 In Progress | ❌ Missing

---

## Phase 1: Project Setup & Basic Infrastructure

**Related Requirements**: NFR-001, NFR-004, NFR-005

### 1.1 Project Structure Setup

- [ ] Create `src/` package structure (`src/__init__.py`)
- [ ] Configure `pyproject.toml` (dependencies, metadata)
- [ ] Create `requirements.txt` (pip compatible)
- [ ] Create `.env.example` template
- [ ] Update `.gitignore` (.env, __pycache__, .venv, etc.)

### 1.2 Configuration Management Module

- [ ] `src/config.py` - Environment variable loading (python-dotenv)
- [ ] Required configuration validation logic
- [ ] API key configuration structure per exchange

### 1.3 Common Utilities

- [ ] `src/logger.py` - Logging setup (file + console)
- [ ] `src/models.py` - Common type definitions (dataclass/Pydantic)
- [ ] Unit test setup (`tests/__init__.py`, `pytest.ini`)

---

## Phase 2: Exchange Integration Base

**Related Requirements**: FR-016, FR-017, FR-018, FR-019, FR-020, NFR-009

### 2.1 Exchange Abstraction Layer

- [ ] `src/exchange/base.py` - BaseExchange abstract class definition
- [ ] Common data model definitions (OHLCV, Order, Position, Balance)
- [ ] Exchange factory function implementation
- [ ] Write unit tests

### 2.2 Binance Integration

- [ ] `src/exchange/binance.py` - BinanceExchange class implementation
- [ ] Historical OHLCV data query (klines API)
- [ ] Current price query
- [ ] Balance query
- [ ] Order create/cancel/query interface
- [ ] Rate limit handling
- [ ] Write unit tests (API mocking)

### 2.3 Bybit Integration

- [ ] `src/exchange/bybit.py` - BybitExchange class implementation
- [ ] Historical OHLCV data query
- [ ] Current price query
- [ ] Balance query
- [ ] Order interface
- [ ] Write unit tests

### 2.4 Tapbit Integration — *deferred to later*

---

## Phase 3: Chart Analysis System

**Related Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-005, NFR-010

### 3.1 Analysis Technique Framework

- [ ] `src/strategy/base.py` - BaseStrategy abstract class
- [ ] `src/strategy/loader.py` - Technique loader (from md/py files)
- [ ] Create `strategies/` directory structure
- [ ] Define technique metadata schema (name, version, description)
- [ ] Write unit tests

### 3.2 Basic Analysis Technique Implementation

- [ ] `strategies/sample_prompt.md` - Sample md prompt technique
- [ ] `strategies/sample_code.py` - Sample Python code technique
- [ ] Technique execution and result return logic
- [ ] Write unit tests

### 3.3 Claude Integration

- [ ] `src/ai/claude.py` - Claude CLI wrapper (`claude -p "..."`)
- [ ] Chart analysis prompt template
- [ ] Response parsing logic (trading point extraction)
- [ ] Error handling (CLI failure, parsing failure)
- [ ] Write unit tests

### 3.4 Analysis Technique Performance Tracking

- [ ] `src/strategy/performance.py` - Performance data model
- [ ] Performance record storage (`data/performance/`)
- [ ] Performance query and aggregation functions
- [ ] Write unit tests

---

## Phase 4: Trading Strategy & Execution

**Related Requirements**: FR-006, FR-007, FR-008, FR-009, FR-010, NFR-007, NFR-008, NFR-012

### 4.1 Trading Strategy Module

- [ ] `src/trading/strategy.py` - Trading strategy calculator
- [ ] Risk/Reward (R/R) calculation function
- [ ] Entry/take-profit/stop-loss calculation function
- [ ] Leverage setting logic
- [ ] Position size calculation
- [ ] Write unit tests

### 4.2 Paper Trading Engine

- [ ] `src/trading/paper.py` - PaperTrader class
- [ ] Virtual asset (balance) management
- [ ] Order simulation (entry, take-profit, stop-loss)
- [ ] Trade history recording (`data/trades/paper/`)
- [ ] Write unit tests

### 4.3 Live Trading Engine

- [ ] `src/trading/live.py` - LiveTrader class
- [ ] Exchange-connected order execution
- [ ] User confirmation flow (approval before execution)
- [ ] Position monitoring
- [ ] Trade history recording (`data/trades/live/`)
- [ ] Write unit tests

### 4.4 Asset/PnL Management

- [ ] `src/trading/portfolio.py` - Portfolio management
- [ ] Asset history storage (`data/portfolio/`)
- [ ] PnL calculation (realized/unrealized)
- [ ] Separate storage by paper/live mode
- [ ] Write unit tests

---

## Phase 5: Feedback Loop System

**Related Requirements**: FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, FR-027, NFR-006

### 5.1 Backtesting Engine

- [ ] `src/backtest/engine.py` - Backtester class
- [ ] Strategy simulation with historical data
- [ ] Trade simulation (considering slippage, fees)
- [ ] Result storage (JSON/CSV - `data/backtest/`)
- [ ] Write unit tests

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
| Phase 3 | FR-001, FR-002, FR-003, FR-004, FR-005, NFR-002, NFR-005, NFR-010 |
| Phase 4 | FR-006, FR-007, FR-008, FR-009, FR-010, NFR-007, NFR-008, NFR-012 |
| Phase 5 | FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, FR-027, NFR-006 |
| Phase 6 | FR-011, FR-012, FR-013, FR-014, FR-015 |
| Phase 7 | FR-028, FR-029, FR-030, FR-031, FR-032, NFR-003 |

---

## Change History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-04-05 | Initial creation | Claude |

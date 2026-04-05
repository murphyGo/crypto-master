# Crypto Master - Requirements Specification

## 1. Overview

### 1.1 Project Purpose

Crypto Master is an automated crypto trading application. It leverages Claude AI Agent to automate chart analysis, trading strategy development, and execution, while continuously improving analysis techniques and enhancing performance through a self-feedback loop.

### 1.2 Scope

- Bitcoin and altcoin chart analysis
- Automated trading strategy development and execution
- Live and paper trading support
- AI-based automatic generation and improvement of analysis techniques
- Strategy validation through backtesting
- Status monitoring via web dashboard

### 1.3 Reference Documents

- `docs/inception.md` - Project concept document

---

## 2. Functional Requirements

### 2.1 Chart Analysis System

| ID | Requirement | Description | Priority |
|----|-------------|-------------|----------|
| FR-001 | Bitcoin Chart Analysis | Analyze Bitcoin charts to derive trading points | High |
| FR-002 | Altcoin Chart Analysis | Analyze altcoin charts to derive trading points | High |
| FR-003 | Chart Analysis Technique Definition | Define analysis techniques as md prompts or Python code snippets | High |
| FR-004 | Analysis Technique Storage/Management | Store and manage all analysis techniques in the file system | High |
| FR-005 | Analysis Technique Performance Tracking | Record and track the performance (win rate, profit rate, etc.) of each analysis technique | High |

### 2.2 Trading Strategy

| ID | Requirement | Description | Priority |
|----|-------------|-------------|----------|
| FR-006 | Risk/Reward Calculation | Automatically calculate Risk/Reward Ratio from trading points | High |
| FR-007 | Leverage Setting | Configure leverage multiplier | Medium |
| FR-008 | Entry/Take-Profit/Stop-Loss Setting | Automatically set each price point | High |
| FR-009 | Live Trading Mode | Execute trades with real funds | High |
| FR-010 | Paper Trading Mode | Simulate trading with virtual funds | High |

### 2.3 Trading Proposal System

| ID | Requirement | Description | Priority |
|----|-------------|-------------|----------|
| FR-011 | Bitcoin Trading Proposal | Analyze Bitcoin using the best analysis technique and propose trades when good opportunities are found | High |
| FR-012 | Altcoin Trading Proposal | Analyze multiple altcoins and propose trades for the token with the highest expected performance | High |
| FR-013 | User Accept/Reject | Users can accept or reject trading proposals | High |
| FR-014 | Proposal History Management | Store all proposals and their results (accept/reject, actual performance) as history | Medium |
| FR-015 | Proposal Notification | Notify users when good trading opportunities are found | Medium |

### 2.4 Exchange Integration

| ID | Requirement | Description | Priority |
|----|-------------|-------------|----------|
| FR-016 | Binance Integration | Execute trades and query data through Binance API | High |
| FR-017 | Bybit Integration | Execute trades and query data through Bybit API | High |
| FR-018 | Tapbit Integration | Execute trades and query data through Tapbit API | Medium |
| FR-019 | Exchange Abstraction | Abstract exchanges through a common interface to facilitate adding new exchanges | High |
| FR-020 | Historical Chart Data Query | Collect historical OHLCV data for backtesting through exchange APIs | High |

### 2.5 Feedback Loop System

| ID | Requirement | Description | Priority |
|----|-------------|-------------|----------|
| FR-021 | Technique Performance Analysis | Automatically analyze the performance of existing analysis techniques and generate reports | High |
| FR-022 | Technique Improvement Suggestion (Claude) | Claude automatically generates technique improvement suggestions based on performance data | High |
| FR-023 | New Technique Idea Generation | Claude generates entirely new analysis technique ideas | High |
| FR-024 | User Idea Input | Generate new analysis techniques based on ideas provided by users | Medium |
| FR-025 | Backtesting Execution | Validate analysis technique performance using historical data | High |
| FR-026 | Automated Feedback Loop | Automate the cycle of backtesting → analysis → improvement → revalidation | High |
| FR-027 | Technique Adoption | Adopt techniques with good backtesting performance as official techniques after user approval | High |

### 2.6 UI Dashboard

| ID | Requirement | Description | Priority |
|----|-------------|-------------|----------|
| FR-028 | Chart Analysis Technique Status | Display list of registered analysis techniques and performance of each technique | Medium |
| FR-029 | Active Trading | Display currently open positions and their status in real-time | Medium |
| FR-030 | Technique Generation Status | Display feedback loop progress (techniques under experimentation, backtesting results, etc.) | Medium |
| FR-031 | Asset and Performance Summary | Display performance metrics such as total assets, PnL, win rate with charts | Medium |
| FR-032 | Streamlit Web App | Implement web dashboard using Streamlit | Medium |

---

## 3. Non-Functional Requirements

### 3.1 Tech Stack

| ID | Requirement | Description |
|----|-------------|-------------|
| NFR-001 | Python 3.10+ | Use Python version 3.10 or higher |
| NFR-002 | Claude CLI Integration | Implement AI features by calling Claude CLI using `claude -p "..."` instead of Anthropic API |
| NFR-003 | Streamlit UI | Implement web dashboard using Streamlit |
| NFR-004 | Environment Variable Management | Manage sensitive information such as API keys through `.env` file and include in `.gitignore` |

### 3.2 Data Management

| ID | Requirement | Description |
|----|-------------|-------------|
| NFR-005 | Analysis Technique Storage | Store analysis techniques as md files (prompt-based) or Python code |
| NFR-006 | Backtesting Result Storage | Store backtesting results in structured format (JSON or CSV) |
| NFR-007 | Trading History Storage | Record all trading history including: entry/exit prices, quantities, leverage, fees, P&L, and timestamps. Implemented via `TradeHistory` model and `TradeHistoryTracker` in `src/strategy/performance.py` |
| NFR-008 | Asset/PnL History | Record asset changes and profit/loss history separately for backtest/paper/live modes. Storage structure: `data/trades/{mode}/trades.json` |

### 3.3 Extensibility

| ID | Requirement | Description |
|----|-------------|-------------|
| NFR-009 | Exchange Extensibility | Have a plugin architecture that minimizes existing code changes when adding new exchanges |
| NFR-010 | Analysis Technique Extensibility | Enable adding new analysis techniques by simply adding files without modifying existing code |

### 3.4 Security

| ID | Requirement | Description |
|----|-------------|-------------|
| NFR-011 | API Key Protection | Manage exchange API keys as environment variables, do not hardcode in source code |
| NFR-012 | Live Trading Confirmation | Require explicit user confirmation before executing live trades |

---

## 4. Constraints

| ID | Constraint | Description |
|----|------------|-------------|
| CON-001 | No Anthropic API | Do not call Anthropic API directly, only use Claude CLI |
| CON-002 | Rate Limit Compliance | Comply with each exchange's API rate limits |
| CON-003 | User Approval Required | Explicit user approval is required for live trading and new technique adoption |

---

## 5. Glossary

| Term | Definition |
|------|------------|
| **Chart Analysis Technique** | A methodology that derives trading signals using chart patterns, technical indicators, etc. Defined as md prompts or Python code |
| **Trading Point** | A set of price, conditions, and timing information for trade entry or exit |
| **Backtesting** | The process of retrospectively validating trading strategy performance using historical market data |
| **Feedback Loop** | A cyclical process that automatically improves strategies by analyzing trading results |
| **Risk/Reward (R/R)** | Risk/Reward Ratio. The ratio of expected profit to expected loss |
| **OHLCV** | Open, High, Low, Close, Volume. Basic candlestick chart data |
| **PnL** | Profit and Loss |

---

## 6. Requirements Traceability Matrix

### inception.md Features → Requirements Mapping

| inception.md Feature | Related Requirements |
|---------------------|---------------------|
| Bitcoin Chart Analysis | FR-001 |
| Altcoin Chart Analysis | FR-002 |
| Chart Analysis Technique Definition/Storage | FR-003, FR-004, NFR-005 |
| Analysis Technique Performance Tracking | FR-005 |
| Trading Strategy (R/R, Leverage, Price Setting) | FR-006, FR-007, FR-008 |
| Trading Modes (Live/Paper) | FR-009, FR-010 |
| Bitcoin Trading User Proposal | FR-011, FR-013 |
| Altcoin Trading User Proposal | FR-012, FR-013 |
| Exchange Support (Binance, Bybit, Tapbit) | FR-016, FR-017, FR-018, FR-019 |
| Feedback Loop (Technique Improvement, Backtesting) | FR-021 ~ FR-027 |
| Claude AI Agent | NFR-002 |
| UI Dashboard | FR-028 ~ FR-032, NFR-003 |
| Credentials (.env) | NFR-004, NFR-011 |

---

## Change History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-04-05 | Initial creation | Claude |

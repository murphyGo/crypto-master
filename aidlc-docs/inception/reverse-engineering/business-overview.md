# Business Overview

## Business Description

Crypto Master automates crypto trading research and execution workflows. It
combines exchange market data, technical strategies, Claude CLI-assisted
strategy improvement, backtesting, proposal review, paper/live execution, and a
Streamlit operator dashboard.

The system is operator-driven: automated components can generate analysis,
proposals, and candidate strategy changes, but live trading and official
strategy adoption remain constrained by explicit operator intent.

## Business Transactions

| Transaction | Description | Primary Unit |
|-------------|-------------|--------------|
| Market Data Collection | Fetch OHLCV, ticker, balance, and order data from exchanges | `exchange-integration` |
| Strategy Analysis | Convert candles into trading signals using prompt or Python strategies | `strategy-framework` |
| Strategy Improvement | Use Claude CLI and performance history to propose new or improved strategies | `ai-feedback-loop` |
| Backtest Validation | Validate strategies against historical or snapshot data with robustness gates | `backtesting-validation` |
| Trading Proposal | Rank opportunities, generate proposal records, and request operator accept/reject | `proposal-runtime` |
| Trade Execution | Execute accepted proposals in paper or live mode with risk controls | `trading-core` |
| Portfolio Monitoring | Track balances, positions, PnL, and account-level state | `trading-core` |
| Operator Monitoring | Surface runtime, strategy, trading, feedback, and sub-account status | `dashboard-operator-ui` |
| Notification Delivery | Send proposal/runtime notifications via configured channels | `notifications-ops` |
| Capital Segmentation | Isolate balances, histories, and strategy sets by sub-account | `sub-account-capital-segmentation` |

## Business Dictionary

| Term | Meaning |
|------|---------|
| Analysis Technique | Prompt or Python strategy that analyzes market data and emits signals |
| Proposal | Candidate trade opportunity requiring accept/reject handling |
| Paper Trading | Simulated execution with local persisted balances and trade history |
| Live Trading | Real exchange execution through configured credentials |
| Sub-Account | Isolated capital pool and strategy configuration within a mode |
| Robustness Gate | Validation checks such as OOS split, walk-forward, regime split, and sensitivity |
| Snapshot | Pinned market dataset for reproducible backtests |

## Component-Level Business Descriptions

- **Exchange Layer**: Provides market and order access through common exchange
  interfaces.
- **Strategy Layer**: Encapsulates market analysis techniques and performance
  metadata.
- **Backtest Layer**: Tests strategies before operator adoption or comparison.
- **Feedback Layer**: Uses performance data and Claude CLI to evolve strategy
  candidates.
- **Proposal/Runtime Layer**: Produces actionable trade proposals and executes
  runtime cycles.
- **Trading Layer**: Applies risk, sizing, paper/live execution, and portfolio
  accounting.
- **Dashboard Layer**: Gives the operator status and control visibility.


# API Documentation

## External APIs

Crypto Master does not expose a public HTTP API. It consumes external exchange
APIs through adapter classes and exposes operator workflows through CLI/runtime
entrypoints and a Streamlit dashboard.

## Internal Interfaces

### Exchange Interface

- **Location**: `src/exchange/base.py`
- **Purpose**: Common async operations for market data, balances, orders, and
  order cancellation.
- **Implementations**: Binance, Bybit.

### Strategy Interface

- **Location**: `src/strategy/base.py`
- **Purpose**: Analyze OHLCV inputs and return structured trading analysis.
- **Implementations**: Python strategy files and prompt-based strategies under
  `strategies/`.

### Trading Interfaces

- **Locations**: `src/trading/paper.py`, `src/trading/live.py`,
  `src/trading/strategy.py`, `src/trading/portfolio.py`
- **Purpose**: Calculate position sizing, execute paper/live trades, maintain
  portfolio state, and persist trade records.

### Proposal Runtime Interfaces

- **Locations**: `src/proposal/engine.py`, `src/proposal/interaction.py`,
  `src/runtime/engine.py`
- **Purpose**: Generate proposals, handle accept/reject decisions, execute
  runtime cycles, and record activity.

### Backtest Interfaces

- **Locations**: `src/backtest/engine.py`, `src/backtest/harness.py`,
  `src/backtest/snapshot.py`, `src/backtest/validator.py`
- **Purpose**: Evaluate strategies over historical or snapshot data and emit
  performance/robustness results.

### Claude CLI Interface

- **Location**: `src/ai/claude.py`
- **Purpose**: Wrap `claude -p` calls for JSON-shaped analysis and free-form
  completion.
- **Constraint**: Direct Anthropic API usage is out of scope under existing
  requirements.

## Data Models

Core models are defined in `src/models.py` and related component modules. Major
domains include OHLCV candles, orders, positions, analysis results, performance
records, trade histories, proposals, runtime cycle results, and sub-account
configuration/state.


# Crypto Master - Architecture Design

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Crypto Master                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │   Dashboard  │  │   Proposal   │  │   Feedback   │                  │
│  │  (Streamlit) │  │    Engine    │  │     Loop     │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                 │                 │                          │
│         └─────────────────┼─────────────────┘                          │
│                           │                                            │
│                    ┌──────┴───────┐                                    │
│                    │   Trading    │                                    │
│                    │   Engine     │                                    │
│                    └──────┬───────┘                                    │
│                           │                                            │
│         ┌─────────────────┼─────────────────┐                          │
│         │                 │                 │                          │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐                  │
│  │   Strategy   │  │   Claude AI  │  │   Exchange   │                  │
│  │   Framework  │  │  Integration │  │  Abstraction │                  │
│  └──────────────┘  └──────────────┘  └──────┬───────┘                  │
│                                             │                          │
│                           ┌─────────────────┼─────────────────┐        │
│                           │                 │                 │        │
│                    ┌──────┴───┐      ┌──────┴───┐      ┌──────┴───┐    │
│                    │ Binance  │      │  Bybit   │      │  Tapbit  │    │
│                    └──────────┘      └──────────┘      └──────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 2. Component Architecture

### 2.1 Exchange Layer (`src/exchange/`)

**Purpose**: Abstract exchange interactions through a common interface.

```python
# Base interface
class BaseExchange(ABC):
    @abstractmethod
    async def get_ohlcv(symbol, timeframe, limit) -> list[OHLCV]
    @abstractmethod
    async def get_ticker(symbol) -> Ticker
    @abstractmethod
    async def get_balance() -> Balance
    @abstractmethod
    async def create_order(order: OrderRequest) -> Order
    @abstractmethod
    async def cancel_order(order_id: str) -> bool
```

**Implementations**:
- `BinanceExchange` - Binance Futures/Spot
- `BybitExchange` - Bybit derivatives
- `TapbitExchange` - Tapbit (deferred)

### 2.2 Strategy Framework (`src/strategy/`)

**Purpose**: Define and manage analysis techniques.

```python
class BaseStrategy(ABC):
    name: str
    version: str
    description: str

    @abstractmethod
    def analyze(ohlcv: list[OHLCV]) -> AnalysisResult
```

**Technique Types**:
- **Prompt-based** (`.md` files): Claude analyzes chart with prompt
- **Code-based** (`.py` files): Python technical analysis

### 2.3 Claude AI Integration (`src/ai/`)

**Purpose**: Interface with Claude via CLI.

```python
class ClaudeClient:
    def analyze_chart(prompt: str, data: str) -> str
    def improve_strategy(performance: PerformanceData) -> str
    def generate_strategy(idea: str) -> str
```

**Constraint**: Uses `claude -p "..."` CLI only (NFR-002).

### 2.4 Trading Engine (`src/trading/`)

**Purpose**: Execute and manage trades.

```python
class TradingEngine:
    mode: Literal["paper", "live"]

    def calculate_position(analysis: AnalysisResult) -> Position
    def execute_trade(position: Position) -> Trade
    def monitor_positions() -> list[PositionStatus]
```

**Modes**:
- `PaperTrader` - Virtual execution with simulated balance
- `LiveTrader` - Real exchange execution with confirmation

### 2.5 Feedback Loop (`src/feedback/`)

**Purpose**: Continuous strategy improvement cycle.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Analyze   │────▶│   Improve   │────▶│  Backtest   │
│ Performance │     │  (Claude)   │     │    New      │
└─────────────┘     └─────────────┘     └──────┬──────┘
       ▲                                       │
       │            ┌─────────────┐            │
       └────────────│   Evaluate  │◀───────────┘
                    │   & Adopt   │
                    └─────────────┘
```

### 2.6 Proposal Engine (`src/proposal/`)

**Purpose**: Generate and manage trading proposals.

- Bitcoin proposals using best-performing technique
- Altcoin scan for highest expected value
- User accept/reject flow
- Notification system

### 2.7 Dashboard (`src/dashboard/`)

**Purpose**: Web UI for monitoring and control.

**Pages**:
- Strategy status and performance
- Active positions and trades
- Feedback loop progress
- Portfolio and PnL summary

## 3. Data Models (`src/models.py`, `src/strategy/performance.py`)

### 3.1 Core Models (`src/models.py`)

```python
@dataclass
class OHLCV:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

@dataclass
class Order:
    id: str
    symbol: str
    side: Literal["buy", "sell"]
    type: Literal["market", "limit"]
    price: Decimal | None
    quantity: Decimal
    status: OrderStatus

@dataclass
class Position:
    symbol: str
    side: Literal["long", "short"]
    entry_price: Decimal
    quantity: Decimal
    leverage: int
    stop_loss: Decimal
    take_profit: Decimal

@dataclass
class AnalysisResult:
    signal: Literal["long", "short", "neutral"]
    confidence: float
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    reasoning: str
```

### 3.2 Performance Models (`src/strategy/performance.py`)

```python
class PerformanceRecord(BaseModel):
    """Analysis/trade performance record with execution details."""
    id: str
    technique_name: str
    technique_version: str
    symbol: str
    signal: Literal["long", "short", "neutral"]
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    confidence: float
    outcome: TradeOutcome
    # Trade execution details
    quantity: Decimal | None
    leverage: int
    fees: Decimal
    mode: Literal["backtest", "paper", "live"]
    trade_id: str | None  # Link to TradeHistory

class TradeHistory(BaseModel):
    """Complete trade lifecycle record (NFR-007)."""
    id: str
    performance_record_id: str | None  # Link to PerformanceRecord
    symbol: str
    side: Literal["long", "short"]
    mode: Literal["backtest", "paper", "live"]
    entry_price: Decimal
    entry_quantity: Decimal
    entry_time: datetime
    exit_price: Decimal | None
    exit_time: datetime | None
    leverage: int
    fees: Decimal
    pnl: Decimal | None
    pnl_percent: float | None
    status: Literal["open", "closed", "cancelled"]
    close_reason: str | None
```

## 4. Data Storage

```
data/
├── logs/                  # Application logs
│   └── crypto-master.log
├── trades/                # Trade history (NFR-007, NFR-008)
│   ├── backtest/         # Backtesting trade records
│   │   └── trades.json
│   ├── paper/            # Paper trading records
│   │   └── trades.json
│   └── live/             # Live trading records
│       └── trades.json
├── backtest/             # Backtesting results
│   └── {strategy}_{date}.json
├── performance/          # Strategy performance (FR-005)
│   └── {technique_name}/
│       ├── records.json  # PerformanceRecord list
│       └── summary.json  # TechniquePerformance aggregate
├── portfolio/            # Portfolio history
│   ├── paper/
│   └── live/
└── proposals/            # Trading proposals
    └── {date}_{symbol}.json
```

## 5. Configuration Flow

```
.env → config.py → Application Components
         │
         ├── Exchange credentials
         ├── Trading mode
         ├── Risk parameters
         └── Logging settings
```

## 6. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Claude integration | CLI only | Constraint CON-001 |
| Exchange library | ccxt | Unified API, wide support |
| Data validation | Pydantic | Type safety, serialization |
| Dashboard | Streamlit | Rapid development, Python-native |
| Async operations | asyncio | Non-blocking exchange calls |

## 7. Security Considerations

- API keys in environment variables only (NFR-011)
- Live trading requires explicit confirmation (NFR-012)
- Paper/Live mode clearly separated
- No hardcoded credentials

## 8. Extensibility Points

1. **New Exchanges**: Implement `BaseExchange` interface
2. **New Strategies**: Add `.md` or `.py` file to `strategies/`
3. **New Indicators**: Extend strategy framework
4. **New Dashboard Pages**: Add to `src/dashboard/pages/`

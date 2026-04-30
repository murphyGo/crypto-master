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

## 9. Sub-Account Architecture (Planned, Phase 19)

### 9.1 Motivation

The current single-`Trader` / single-seed model (`PaperTrader` built once
in `src/main.py::build_trader`, all strategies share its USDT pool) makes
four operational scenarios impossible without architectural change:

1. **Per-strategy seed isolation** — drawdown in one strategy starves
   every other strategy of capital
2. **Multiple exchange-account operation** — one set of API keys means
   one logical account; spinning up a separate "altcoin swing" or
   "BTC-only" pool requires manual deployment duplication
3. **Strategy-combination A/B testing** — comparing "Set A {RSI 4h +
   chasulang}" vs. "Set B {Bollinger + breakout}" on equal capital is a
   manual orchestration today
4. **Risk segmentation** — a single global `risk_percent` cap can't
   express "1% on the experimental bucket, 0.3% on the main bucket"

Phase 19 introduces a `SubAccount` abstraction that owns one balance
pool, one trader instance, one strategy whitelist, and one risk-override
profile. The runtime engine fans out per sub-account; persistence paths
are scoped by sub-account; the dashboard surfaces per-sub-account equity
curves. A single `default` sub-account is always materialised so legacy
single-seed deployments work unchanged (backward-compat invariant).

### 9.2 Core Abstraction

```python
class SubAccount(BaseModel):
    id: str                         # stable key, e.g. "main", "btc_only"
    name: str                       # display name
    mode: Literal["paper", "live"]
    exchange_ref: str               # e.g. "binance_main", "binance_alt"
    initial_balance: dict[str, Decimal]   # paper-mode seed
    strategy_filter: list[str] | None     # None = all; list = whitelist
    risk_overrides: RiskOverrides
    enabled: bool

class RiskOverrides(BaseModel):
    risk_percent: Decimal | None
    max_open_positions_total: int | None
    max_open_positions_per_symbol: int | None
    leverage_cap: int | None
```

### 9.3 Registry

```python
class SubAccountRegistry:
    def list_active(self) -> list[SubAccount]: ...
    def get(self, sub_account_id: str) -> SubAccount: ...
    def get_trader(self, sub_account_id: str) -> Trader: ...
    def filter_strategies(
        self, sub_account_id: str, available: list[BaseStrategy]
    ) -> list[BaseStrategy]: ...
```

The registry owns one `Trader` per sub-account, each bound to its
declared `exchange_ref`. The cross-cycle position cap (Phase 12.1) is
naturally scoped because each sub-account has its own trader; the cap
becomes per-sub-account, not global, which matches the isolation invariant.

### 9.4 Engine Integration

Today's flow:

```
TradingEngine.cycle():
  proposals = ProposalEngine.propose_*(...)
  for p in proposals:
    _handle_proposal(p) → trader.open_position(...)
```

Sub-account flow:

```
TradingEngine.cycle():
  for sub in registry.list_active():
    strategies = registry.filter_strategies(sub.id, all_strategies)
    proposals = ProposalEngine.propose_*(
        strategies=strategies,
        balance=sub.live_balance(),
        risk_percent=sub.risk_overrides.risk_percent or default,
    )
    for p in proposals:
      p.sub_account_id = sub.id
      _handle_proposal(p) → registry.get_trader(sub.id).open_position(...)
```

`Proposal` and `TradeHistory` carry `sub_account_id`. `ProposalRecord`
gains the same field. `PerformanceTracker` keys by
`(sub_account_id, technique_name)` instead of `technique_name` alone.

### 9.5 Persistence Layout

```
data/
  trades/{mode}/{sub_account_id}/trades.json       # was: trades/{mode}/trades.json
  portfolio/{mode}/{sub_account_id}/snapshots.json
  performance/{sub_account_id}/{technique_name}/{records,summary}.json
  proposals/{sub_account_id}/{date}_{symbol}.json
```

**One-shot migration**: on first boot of v19, existing
`data/trades/{mode}/trades.json` is renamed in place to
`data/trades/{mode}/default/trades.json` (idempotent, guarded by a
marker file `data/.subaccounts_migrated`); same pattern for
`portfolio/`, `performance/`, `proposals/`.

### 9.6 Configuration

New file `config/sub_accounts.yaml` (Pydantic-validated):

```yaml
sub_accounts:
  - id: default
    name: "Default Account"
    mode: paper
    exchange_ref: binance_main
    initial_balance:
      USDT: 10000
    strategy_filter: null
    risk_overrides:
      risk_percent: 1.0
      max_open_positions_per_symbol: 1
    enabled: true
```

Absent file → registry materialises a single `default` sub-account from
existing `Settings.paper_initial_balance` / `Settings.engine_*`.

### 9.7 Multi-Credential Live Mode

Live operation requires distinct API credentials per sub-account.
`Settings.exchange_credentials: dict[str, ExchangeConfig]` enumerates
them; env vars follow `EXCHANGE_<REF>_API_KEY` / `EXCHANGE_<REF>_API_SECRET`
naming (e.g. `EXCHANGE_BINANCE_MAIN_API_KEY`,
`EXCHANGE_BINANCE_ALT_API_KEY`). A `SubAccount` with `enabled: true` and
`mode: live` whose `exchange_ref` cannot resolve to a credential set is
a **startup failure** — silent fallback would leak risk.

### 9.8 Dashboard Surface

- New "Sub-Account" selector at the top of the trading page; defaults to
  aggregated (sum across all active) so legacy operators see today's view
  unchanged
- Per-sub-account equity curves stacked on the engine page
- Comparative view: side-by-side equity / MDD / hit-rate when ≥2 active

### 9.9 Strategy-Combination A/B Backtesting

The backtester gains a `BacktestHarness.run_sub_accounts(...)` entry
point that takes a list of `SubAccount` configs and one historical
OHLCV window, then drives all sub-accounts through that window in
lockstep — each consuming only its whitelisted strategies and its own
risk profile. Output is one `MultiAccountReport` per run with:

- per-sub-account equity curve (aligned timestamps)
- per-sub-account `PerformanceAnalyzer` summary (Sharpe / MDD / hit rate)
- pairwise correlation of returns across sub-accounts
- merged trade ledger keyed by `sub_account_id`

This makes "Strategy Set A vs. Set B with controlled capital" a single
script invocation rather than a manual N-deployment exercise.

### 9.10 Risks & Open Decisions

| Risk | Mitigation |
|------|------------|
| Capital fragmentation: 5 sub × 1% risk ≠ 1% total exposure | New `EngineConfig.portfolio_risk_cap: Decimal` enforces a sum-of-exposures ceiling across all sub-accounts |
| Cross-account hedge: sub-A long BTC + sub-B short BTC = 2 fees + net-zero | Allow it (cost of isolation), but emit `CROSS_ACCOUNT_HEDGE_DETECTED` activity event for visibility |
| Notification volume scales with sub-account count | Per-sub-account routing override; default is shared dispatcher |
| AutoResearch (Phase 17) script targeting | New `--sub-account` flag enrolls candidates into one bucket; default `default` |
| Proposal-engine throughput: N sub × M techniques × K symbols | OHLCV cache (Phase 11.2) is keyed `(symbol, tf)`, not by sub-account, so it amortises across sub-accounts within one cycle |

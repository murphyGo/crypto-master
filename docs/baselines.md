# Baseline Strategies

The crypto-master engine ships three deterministic indicator
strategies alongside the LLM-driven techniques. They serve two
purposes:

1. **Comparison floor.** "Is the LLM strategy contributing real
   edge, or just confidently re-deriving simple TA?" — without a
   deterministic baseline you can't answer that. Backtest each
   baseline first; the LLM strategies should clear those numbers
   before you trust them.
2. **Degraded-mode safety net.** If every Claude call fails (rate
   limit, auth, parse error), the engine still produces proposals
   from indicator strategies. The runtime keeps working.

All three live under [`strategies/`](../strategies/) with
`status: experimental` and `symbols: []` (universal — they apply
to every USDT pair the engine scans).

## The three baselines

### `rsi.py` — RSI Mean Reversion

Wilder's RSI on the closes of whatever timeframe the engine passes.

| Setting | Value |
|---------|-------|
| Indicator | RSI (Wilder's) |
| Period | 14 |
| Long trigger | RSI < 30 (oversold) |
| Short trigger | RSI > 70 (overbought) |
| Stop loss | 2% adverse |
| Take profit | 4% favorable (R/R 2:1) |
| Confidence | Linear ramp from 0 (at threshold) to 1 (RSI 10 / 90) |

> **Future split**: Once Phase 9.1 lands multi-timeframe support,
> this becomes `rsi_4h.py` (swing) and `rsi_15m.py` (scalp) so the
> engine can evaluate both cadences in parallel. Today it runs on
> whichever timeframe `EngineConfig.timeframe` selects (default 1h).

### `bollinger_bands.py` — Bollinger Band Reversion

Mean-reversion when price pierces a band. Targets the middle band;
stops sit half a band-width outside the trigger.

| Setting | Value |
|---------|-------|
| Indicator | Bollinger Bands (SMA ± 2σ population) |
| Period | 20 |
| Std dev | 2.0 |
| Long trigger | Close < lower band |
| Short trigger | Close > upper band |
| Take profit | Middle band (the SMA) |
| Stop loss | Triggering band ± 0.5 × half-band-width |
| Confidence | Proportional to depth past the band, capped at 1 |

### `ma_crossover.py` — Dual SMA Crossover

Classic golden / death cross. Promoted from the original
`sample_code.py` scaffold.

| Setting | Value |
|---------|-------|
| Indicator | Two SMAs (fast / slow) |
| Fast period | 10 |
| Slow period | 20 |
| Long trigger | Fast crosses above slow on the latest bar |
| Short trigger | Fast crosses below slow on the latest bar |
| Take profit | ±5% from entry |
| Stop loss | Min/max of last 5 closes |
| Confidence | `\|short_ma − long_ma\| / current_price × 100`, capped at 0.8 |

## How to backtest these

The engine bundles a `Backtester` (Phase 5.1). Running each
baseline against historical OHLCV gives the win-rate / Sharpe / MDD
the LLM strategies need to beat. Phase 9.2 ships the strategies +
tests; running the actual backtests against fetched historical data
is a separate small task (it needs a historical-OHLCV fetcher we
don't bundle yet — Binance/Bybit klines REST is the obvious source).

The minimal call shape from the existing API:

```python
from datetime import datetime, timedelta
from src.backtest.engine import Backtester
from src.backtest.analyzer import PerformanceAnalyzer
from src.strategy.loader import load_strategy

strategy = load_strategy(Path("strategies/rsi.py"))
ohlcv = await exchange.get_ohlcv(
    symbol="BTC/USDT",
    timeframe="1h",
    limit=4380,  # ~6 months of hourly candles
)

backtester = Backtester()
result = await backtester.run(
    strategy=strategy,
    ohlcv=ohlcv,
    symbol="BTC/USDT",
    timeframe="1h",
    initial_balance=Decimal("10000"),
)
analyzer = PerformanceAnalyzer()
metrics = analyzer.analyze(result)

print(f"Win rate: {metrics.win_rate:.2%}")
print(f"Sharpe:   {metrics.sharpe_ratio:.2f}")
print(f"MDD:      {metrics.max_drawdown_pct:.2f}%")
```

Save the results under `data/backtest/baselines/<strategy>/` so the
dashboard's Strategies page can surface them next to the LLM
techniques.

## Reference numbers (TBD)

Once the baselines have been backtested on representative data,
fill this table:

| Strategy | Symbol | Period | Win Rate | Sharpe | MDD |
|----------|--------|--------|----------|--------|-----|
| `rsi_mean_reversion` | BTC/USDT | 6mo 1h | _TBD_ | _TBD_ | _TBD_ |
| `bollinger_band_reversion` | BTC/USDT | 6mo 1h | _TBD_ | _TBD_ | _TBD_ |
| `ma_crossover` | BTC/USDT | 6mo 1h | _TBD_ | _TBD_ | _TBD_ |

These numbers are the bar each LLM-driven technique needs to clear.

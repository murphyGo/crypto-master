"""Ad-hoc baseline: backtest all code strategies on ~90d of Binance data.

Standalone harness for the "+100% in 3 months" goal investigation.
Fetches public klines (no API key), runs each code strategy through the
Backtester, and prints return%, win rate, trades, and max drawdown so we
can see how far current strategies sit from the target.

Usage:
    python -m scripts.goal_baseline [--symbol BTCUSDT] [--interval 1h] [--days 90]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import urllib.request
import json

logging.disable(logging.WARNING)
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from src.models import OHLCV
from src.strategy.loader import load_strategy
from src.backtest.engine import Backtester, BacktestConfig
from src.backtest.metrics import (
    sharpe_from_trade_pnls,
    max_drawdown_from_equity_values,
)

BINANCE = "https://api.binance.com/api/v3/klines"
INTERVAL_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000,
               "4h": 14_400_000, "1d": 86_400_000}


def fetch_klines(symbol: str, interval: str, days: int) -> list[OHLCV]:
    step = INTERVAL_MS[interval]
    total = (days * 86_400_000) // step
    end = int(datetime.now(timezone.utc).timestamp() * 1000)
    start = end - total * step
    out: list[OHLCV] = []
    cur = start
    while cur < end:
        url = f"{BINANCE}?symbol={symbol}&interval={interval}&startTime={cur}&limit=1000"
        with urllib.request.urlopen(url, timeout=30) as r:
            rows = json.loads(r.read())
        if not rows:
            break
        for row in rows:
            out.append(OHLCV(
                timestamp=datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
                open=Decimal(row[1]), high=Decimal(row[2]), low=Decimal(row[3]),
                close=Decimal(row[4]), volume=Decimal(row[5]),
            ))
        cur = rows[-1][0] + step
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--interval", default="1h")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--leverage", type=int, default=1)
    ap.add_argument("--risk", type=float, default=1.0)
    args = ap.parse_args()

    ohlcv = fetch_klines(args.symbol, args.interval, args.days)
    pair = args.symbol.replace("USDT", "/USDT")
    print(f"Fetched {len(ohlcv)} candles {ohlcv[0].timestamp.date()} -> "
          f"{ohlcv[-1].timestamp.date()} ({pair} {args.interval})")
    px0, px1 = float(ohlcv[0].close), float(ohlcv[-1].close)
    print(f"Buy&hold over window: {(px1/px0 - 1)*100:+.1f}%")
    print(f"Config: leverage={args.leverage}x risk={args.risk}%/trade\n")

    config = BacktestConfig(
        initial_balance=Decimal("10000"),
        fee_rate=Decimal("0.0004"),
        slippage_bps=5,
        leverage=args.leverage,
        risk_percent=args.risk,
        min_risk_reward_ratio=1.5,
    )
    bt = Backtester(config=config)

    strat_dir = Path("strategies")
    files = sorted(f for f in strat_dir.glob("*.py") if not f.name.startswith("_"))
    print(f"{'strategy':<28}{'ret%':>9}{'win%':>8}{'trades':>8}{'maxDD%':>9}{'sharpe':>8}")
    print("-" * 70)
    rows = []
    for f in files:
        try:
            strat = load_strategy(f)
            tf = args.interval
            res = await bt.run(strategy=strat, ohlcv=ohlcv, symbol=pair, timeframe=tf)
            eq = [p.equity for p in res.equity_curve] if res.equity_curve else [res.initial_balance]
            _, mdd = max_drawdown_from_equity_values(eq, res.initial_balance)
            sharpe = (sharpe_from_trade_pnls(
                [t.pnl for t in res.trades], res.initial_balance
            ) or 0.0) if res.trades else 0.0
            rows.append((f.stem, res.return_percent, res.win_rate * 100,
                         res.total_trades, mdd, sharpe, res.liquidated))
        except Exception as e:  # noqa: BLE001
            print(f"{f.stem:<28}  ERROR: {type(e).__name__}: {str(e)[:40]}")
    rows.sort(key=lambda r: r[1], reverse=True)
    for name, ret, win, n, mdd, sh, liq in rows:
        flag = "  LIQUIDATED" if liq else ""
        print(f"{name:<28}{ret:>9.1f}{win:>8.1f}{n:>8}{mdd:>9.1f}{sh:>8.2f}{flag}")


if __name__ == "__main__":
    asyncio.run(main())

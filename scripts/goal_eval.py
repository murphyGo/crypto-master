"""Evaluate a single strategy on 4h data across assets, with a leverage sweep.

Used for the "+100% in 90 days" goal investigation. Confirms whether
tsmom_vol_breakout has real edge at 1x, then sweeps leverage to map the
return frontier.

Usage:
    python -m scripts.goal_eval --file strategies/experimental/tsmom_vol_breakout.py \
        --interval 4h --days 730 --symbols BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from decimal import Decimal
from pathlib import Path

logging.disable(logging.WARNING)

from scripts.goal_baseline import fetch_klines  # reuse fetcher
from src.strategy.loader import load_strategy
from src.backtest.engine import Backtester, BacktestConfig
from src.backtest.metrics import (
    sharpe_from_trade_pnls,
    max_drawdown_from_equity_values,
)


async def run_one(file: Path, ohlcv, pair, interval, leverage, risk):
    config = BacktestConfig(
        initial_balance=Decimal("10000"),
        fee_rate=Decimal("0.0004"),
        slippage_bps=5,
        leverage=leverage,
        risk_percent=risk,
        min_risk_reward_ratio=1.5,
    )
    bt = Backtester(config=config)
    strat = load_strategy(file)
    res = await bt.run(strategy=strat, ohlcv=ohlcv, symbol=pair, timeframe=interval)
    eq = [p.equity for p in res.equity_curve] if res.equity_curve else [res.initial_balance]
    _, mdd = max_drawdown_from_equity_values(eq, res.initial_balance)
    sharpe = (sharpe_from_trade_pnls([t.pnl for t in res.trades], res.initial_balance)
              or 0.0) if res.trades else 0.0
    return res, mdd, sharpe


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--interval", default="4h")
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT")
    ap.add_argument("--risk", type=float, default=1.0)
    ap.add_argument("--leverages", default="1")
    args = ap.parse_args()

    file = Path(args.file)
    symbols = args.symbols.split(",")
    leverages = [int(x) for x in args.leverages.split(",")]
    data = {}
    for sym in symbols:
        data[sym] = fetch_klines(sym, args.interval, args.days)

    for lev in leverages:
        print(f"\n===== leverage {lev}x  risk {args.risk}%/trade  "
              f"{args.interval} {args.days}d =====")
        print(f"{'symbol':<12}{'ret%':>10}{'win%':>8}{'trades':>8}"
              f"{'maxDD%':>9}{'sharpe':>8}")
        print("-" * 56)
        for sym in symbols:
            ohlcv = data[sym]
            pair = sym.replace("USDT", "/USDT")
            res, mdd, sh = await run_one(file, ohlcv, pair, args.interval, lev, args.risk)
            flag = "  LIQ" if res.liquidated else ""
            print(f"{pair:<12}{res.return_percent:>10.1f}{res.win_rate*100:>8.1f}"
                  f"{res.total_trades:>8}{mdd:>9.1f}{sh:>8.2f}{flag}")


if __name__ == "__main__":
    asyncio.run(main())

"""Characterize the "+100% in 90 days" leverage gamble honestly.

Runs the strategy over many rolling 90-day windows (fresh capital each
window, with warmup bars supplied before the window so trading starts on
day 0), at a sweep of risk-per-trade / leverage levels. Reports the full
distribution of 90-day outcomes: how often it doubles, how often it is
liquidated or suffers a deep drawdown. This is the eyes-open picture of
the bet, not a single cherry-picked backtest.

Usage:
    python -m scripts.goal_gamble --file strategies/experimental/tsmom_vol_breakout.py \
        --symbols BTCUSDT,ETHUSDT,SOLUSDT --days 730 --risks 1,5,10,20 --leverage 5
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import statistics
from decimal import Decimal
from pathlib import Path

logging.disable(logging.WARNING)

from scripts.goal_baseline import fetch_klines
from src.strategy.loader import load_strategy
from src.backtest.engine import Backtester, BacktestConfig

BARS_PER_DAY_4H = 6
WARMUP = 252            # tsmom minimum_candles
WINDOW_DAYS = 90
STEP_BARS = 60          # ~10-day step between window origins


async def run_window(strat_file, ohlcv, pair, leverage, risk, max_pos):
    config = BacktestConfig(
        initial_balance=Decimal("10000"),
        fee_rate=Decimal("0.0004"),
        slippage_bps=5,
        leverage=leverage,
        risk_percent=risk,
        max_position_size_percent=max_pos,
        min_risk_reward_ratio=1.5,
    )
    bt = Backtester(config=config)
    strat = load_strategy(strat_file)
    res = await bt.run(strategy=strat, ohlcv=ohlcv, symbol=pair, timeframe="4h")
    # Peak return within the window (best mark-to-market the bet ever showed).
    peak = res.return_percent
    if res.equity_curve:
        eqs = [float(p.equity) for p in res.equity_curve]
        peak = (max(eqs) / 10000.0 - 1) * 100
    return res.return_percent, peak, res.liquidated


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--risks", default="1,5,10,20")
    ap.add_argument("--leverage", type=int, default=5)
    ap.add_argument("--max-pos", type=float, default=100.0,
                    help="max_position_size_percent (cap on margin %% of balance)")
    args = ap.parse_args()

    strat_file = Path(args.file)
    symbols = args.symbols.split(",")
    risks = [float(x) for x in args.risks.split(",")]
    window_bars = WINDOW_DAYS * BARS_PER_DAY_4H

    data = {s: fetch_klines(s, "4h", args.days) for s in symbols}
    n_any = len(next(iter(data.values())))
    print(f"Data: {n_any} 4h candles/symbol (~{args.days}d), "
          f"window={WINDOW_DAYS}d ({window_bars} bars), warmup={WARMUP}, "
          f"leverage_cap={args.leverage}x")

    for risk in risks:
        finals, peaks, liqs, n = [], [], 0, 0
        for sym in symbols:
            ohlcv = data[sym]
            pair = sym.replace("USDT", "/USDT")
            start = WARMUP
            while start + window_bars <= len(ohlcv):
                sl = ohlcv[start - WARMUP : start + window_bars]
                final, peak, liq = await run_window(
                    strat_file, sl, pair, args.leverage, risk, args.max_pos)
                finals.append(final)
                peaks.append(peak)
                liqs += int(liq)
                n += 1
                start += STEP_BARS
        if not finals:
            continue
        finals.sort()
        p = lambda q: finals[int(q * (len(finals) - 1))]  # noqa: E731
        doubled_final = sum(1 for x in finals if x >= 100) / n * 100
        doubled_peak = sum(1 for x in peaks if x >= 100) / n * 100
        dd50 = sum(1 for x in finals if x <= -50) / n * 100
        print(f"\n--- risk {risk}%/trade  ({n} rolling 90d windows) ---")
        print(f"  90d return:  median {statistics.median(finals):+6.1f}%   "
              f"mean {statistics.mean(finals):+6.1f}%   "
              f"p10 {p(0.10):+6.1f}%   p90 {p(0.90):+6.1f}%   "
              f"max {max(finals):+6.1f}%")
        print(f"  P(+100% by end of window):   {doubled_final:5.1f}%")
        print(f"  P(+100% touched intra-window): {doubled_peak:5.1f}%")
        print(f"  P(<= -50% end):              {dd50:5.1f}%")
        print(f"  P(liquidated):               {liqs / n * 100:5.1f}%")


if __name__ == "__main__":
    asyncio.run(main())

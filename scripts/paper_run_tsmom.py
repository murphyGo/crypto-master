"""Standalone forward paper-trading runner for tsmom_vol_breakout.

Drives ONE strategy on live Binance public 4h data with a virtual
balance -- no API keys, no testnet, isolated from the main engine's
1h/200-candle envelope. State persists to disk so the runner can be
left running (or re-invoked by cron / `/loop`) for weeks; it only acts
when a new 4h candle has closed, so re-running it frequently is a no-op
until the next bar.

This is a genuine forward (out-of-sample) test: it sees only candles up
to each closed bar, sizes risk per the configured rules, and books fills
at close +/- slippage with fees -- the same mechanics as the backtester.

Honest note: tsmom_vol_breakout is ~breakeven at 1x. Sane defaults below
(risk 1%, 3x, 20% position cap) forward-test the strategy. The "+100%
gamble" config is `--risk 20 --leverage 20 --max-pos 100` -- negative EV;
see docs/research/goal-100pct-90d.md.

Usage:
    python -m scripts.paper_run_tsmom                      # one tick, then exit
    python -m scripts.paper_run_tsmom --watch --every 1800 # loop every 30 min
    python -m scripts.paper_run_tsmom --status             # print state, no trading
    python -m scripts.paper_run_tsmom --reset              # wipe virtual account
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

logging.disable(logging.WARNING)

from scripts.goal_baseline import fetch_klines
from src.strategy.loader import load_strategy

STRAT_FILE = Path("strategies/tsmom_vol_breakout.py")
STATE_DIR = Path("data/paper_forward/tsmom")
STATE_FILE = STATE_DIR / "state.json"
TRADES_FILE = STATE_DIR / "trades.jsonl"
WARMUP = 300            # > tsmom minimum_candles (251)
MAX_BARS_HELD = 60      # mirrors TECHNIQUE_INFO max_bars_held
FEE_RATE = Decimal("0.0004")
SLIPPAGE = Decimal("0.0005")  # 5 bps each side


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state(initial_balance: Decimal) -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "created": _now(),
        "initial_balance": str(initial_balance),
        "cash": str(initial_balance),     # free USDT
        "positions": {},                   # symbol -> open position dict
        "last_bar": {},                    # symbol -> last processed bar iso ts
        "closed": 0,
        "wins": 0,
        "realized_pnl": "0",
    }


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def append_trade(rec: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with TRADES_FILE.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def equity(state: dict, marks: dict[str, Decimal]) -> Decimal:
    """Cash + mark-to-market unrealized PnL of open positions."""
    eq = Decimal(state["cash"])
    for sym, pos in state["positions"].items():
        mark = marks.get(sym)
        if mark is None:
            continue
        entry = Decimal(pos["entry"])
        qty = Decimal(pos["qty"])
        margin = Decimal(pos["margin"])
        sign = Decimal(1) if pos["side"] == "long" else Decimal(-1)
        upnl = (mark - entry) * qty * sign
        eq += margin + upnl
    return eq


def _close_position(state, sym, pos, exit_px: Decimal, reason: str, bar_ts: str):
    entry = Decimal(pos["entry"])
    qty = Decimal(pos["qty"])
    margin = Decimal(pos["margin"])
    sign = Decimal(1) if pos["side"] == "long" else Decimal(-1)
    fill = exit_px * (1 - SLIPPAGE) if pos["side"] == "long" else exit_px * (1 + SLIPPAGE)
    gross = (fill - entry) * qty * sign
    fees = (entry * qty + fill * qty) * FEE_RATE
    pnl = gross - fees
    state["cash"] = str(Decimal(state["cash"]) + margin + pnl)
    state["closed"] += 1
    if pnl > 0:
        state["wins"] += 1
    state["realized_pnl"] = str(Decimal(state["realized_pnl"]) + pnl)
    append_trade({
        "ts": _now(), "bar": bar_ts, "symbol": sym, "side": pos["side"],
        "entry": str(entry), "exit": str(fill), "qty": str(qty),
        "pnl": str(pnl.quantize(Decimal("0.01"))), "reason": reason,
        "opened_bar": pos["opened_bar"],
    })
    del state["positions"][sym]
    return pnl


async def process_symbol(strat, state, symbol: str, interval: str,
                         risk_pct: Decimal, leverage: int, max_pos_pct: Decimal):
    pair = symbol.replace("USDT", "/USDT")
    candles = fetch_klines(symbol, interval, days=80)  # ~480 4h bars
    if len(candles) < WARMUP:
        print(f"  {pair}: only {len(candles)} candles (<{WARMUP}); skip")
        return
    # The most recent CLOSED bar is the second-to-last (last may be forming).
    closed_bar = candles[-2]
    closed_idx = len(candles) - 2
    bar_ts = closed_bar.timestamp.isoformat()
    if state["last_bar"].get(pair) == bar_ts:
        return  # already processed this bar
    mark = closed_bar.close

    # 1) Manage an open position against this bar's range / time-stop.
    pos = state["positions"].get(pair)
    if pos is not None:
        hit = None
        sl, tp = Decimal(pos["stop"]), Decimal(pos["tp"])
        if pos["side"] == "long":
            if closed_bar.low <= sl:
                hit = ("stop", sl)
            elif closed_bar.high >= tp:
                hit = ("target", tp)
        else:
            if closed_bar.high >= sl:
                hit = ("stop", sl)
            elif closed_bar.low <= tp:
                hit = ("target", tp)
        bars_held = closed_idx - pos["opened_idx"]
        if hit is None and bars_held >= MAX_BARS_HELD:
            hit = ("time", closed_bar.close)
        if hit:
            pnl = _close_position(state, pair, pos, hit[1], hit[0], bar_ts)
            print(f"  {pair}: CLOSE {pos['side']} ({hit[0]}) pnl={pnl.quantize(Decimal('0.01'))}")
            pos = None

    # 2) If flat, evaluate a fresh entry on candles up to the closed bar.
    if pair not in state["positions"]:
        window = candles[: closed_idx + 1]
        res = await strat.analyze(window, symbol=pair, timeframe=interval)
        if res.signal in ("long", "short"):
            eq = equity(state, {pair: mark})
            entry = Decimal(res.entry_price)
            fill = entry * (1 + SLIPPAGE) if res.signal == "long" else entry * (1 - SLIPPAGE)
            stop = Decimal(res.stop_loss)
            stop_dist = abs(fill - stop)
            if stop_dist > 0:
                risk_amt = eq * risk_pct / 100
                qty = risk_amt / stop_dist
                notional = qty * fill
                max_notional = eq * max_pos_pct / 100 * leverage
                if notional > max_notional:
                    qty = max_notional / fill
                    notional = qty * fill
                margin = notional / leverage
                if margin <= Decimal(state["cash"]) and qty > 0:
                    state["cash"] = str(Decimal(state["cash"]) - margin)
                    state["positions"][pair] = {
                        "side": res.signal, "entry": str(fill), "qty": str(qty),
                        "stop": str(stop), "tp": str(res.take_profit),
                        "margin": str(margin), "opened_idx": closed_idx,
                        "opened_bar": bar_ts, "conf": res.confidence,
                    }
                    print(f"  {pair}: OPEN {res.signal} @ {fill.quantize(Decimal('0.0001'))} "
                          f"qty={qty:.6f} stop={stop:.4g} tp={Decimal(res.take_profit):.4g} "
                          f"(conf {res.confidence:.2f})")

    state["last_bar"][pair] = bar_ts


async def tick(args, strat) -> None:
    state = load_state(Decimal(str(args.balance)))
    marks: dict[str, Decimal] = {}
    print(f"[{_now()}] tick  symbols={args.symbols}")
    for sym in args.symbols.split(","):
        await process_symbol(strat, state, sym, args.interval,
                             Decimal(str(args.risk)), args.leverage,
                             Decimal(str(args.max_pos)))
        # refresh mark for equity print
        c = fetch_klines(sym, args.interval, days=2)
        if c:
            marks[sym.replace("USDT", "/USDT")] = c[-1].close
    save_state(state)
    print_status(state, marks)


def print_status(state: dict, marks: dict[str, Decimal]) -> None:
    init = Decimal(state["initial_balance"])
    eq = equity(state, marks)
    ret = (eq / init - 1) * 100
    wr = (state["wins"] / state["closed"] * 100) if state["closed"] else 0.0
    print(f"  equity={eq.quantize(Decimal('0.01'))}  "
          f"return={ret:+.2f}%  closed={state['closed']}  winrate={wr:.0f}%  "
          f"realized={Decimal(state['realized_pnl']).quantize(Decimal('0.01'))}")
    for sym, pos in state["positions"].items():
        mark = marks.get(sym, Decimal(pos["entry"]))
        sign = Decimal(1) if pos["side"] == "long" else Decimal(-1)
        upnl = (mark - Decimal(pos["entry"])) * Decimal(pos["qty"]) * sign
        print(f"    OPEN {sym} {pos['side']} entry={Decimal(pos['entry']):.4g} "
              f"mark={mark:.4g} uPnL={upnl.quantize(Decimal('0.01'))}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--interval", default="4h")
    ap.add_argument("--balance", type=float, default=10000.0)
    ap.add_argument("--risk", type=float, default=1.0, help="risk %% per trade")
    ap.add_argument("--leverage", type=int, default=3)
    ap.add_argument("--max-pos", type=float, default=20.0,
                    help="max position notional as %% of equity * leverage cap")
    ap.add_argument("--watch", action="store_true", help="loop forever")
    ap.add_argument("--every", type=int, default=1800, help="seconds between ticks in --watch")
    ap.add_argument("--status", action="store_true", help="print state only")
    ap.add_argument("--reset", action="store_true", help="wipe virtual account")
    args = ap.parse_args()

    if args.reset:
        for f in (STATE_FILE, TRADES_FILE):
            if f.exists():
                f.unlink()
        print("Virtual account reset.")
        return

    strat = load_strategy(STRAT_FILE)

    if args.status:
        state = load_state(Decimal(str(args.balance)))
        marks = {}
        for sym in args.symbols.split(","):
            c = fetch_klines(sym, args.interval, days=2)
            if c:
                marks[sym.replace("USDT", "/USDT")] = c[-1].close
        print_status(state, marks)
        return

    if args.watch:
        print(f"Watch mode: tick every {args.every}s. Ctrl+C to stop.")
        while True:
            try:
                await tick(args, strat)
            except Exception as e:  # noqa: BLE001
                print(f"[{_now()}] tick error: {type(e).__name__}: {e}")
            time.sleep(args.every)
    else:
        await tick(args, strat)


if __name__ == "__main__":
    asyncio.run(main())

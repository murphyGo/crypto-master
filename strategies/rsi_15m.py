"""15-minute RSI mean-reversion baseline (Phase 9.4).

Scalp-cadence sibling of :mod:`strategies.rsi_4h`. Same Wilder RSI
math, same threshold logic — only the declared ``timeframes``
differs. The user originally asked for both a 4h RSI (swing) and a
15m RSI (scalp) baseline; this is the latter.

Operationally the 15m cadence runs the strategy at 16x the frequency
of the 4h variant and produces 16x as many candidate signals. Each
signal is evaluated independently — there is no cross-TF coupling.
Use the performance tracker to see which cadence accumulates real
edge over time.

Related Requirements:
- FR-001 / FR-002 / FR-003 / FR-004
"""

from strategies.rsi import RSIMeanReversionStrategy

# See ``rsi_4h.py`` for why we re-export under a distinct local name.
RSI15mMeanReversionStrategy = RSIMeanReversionStrategy

TECHNIQUE_INFO = {
    "name": "rsi_15m",
    "version": "1.1.0",
    "description": (
        "RSI mean-reversion locked to 15m candles. Scalp cadence: "
        "long when RSI<30, short when RSI>70. SL=2% / TP=5% (R/R "
        "2.5:1, see strategies/rsi.py v1.1.0 changelog)."
    ),
    "author": "system",
    "symbols": [],  # universal — applies to every USDT pair
    "timeframes": ["15m"],
    "status": "experimental",
    "changelog": (
        "1.1.0: inherits TAKE_PROFIT_PCT=0.05 (R/R 2.5:1) from "
        "shared RSIMeanReversionStrategy; see strategies/rsi.py "
        "v1.1.0 for full rationale. "
        "1.0.0: initial 15m split from rsi_universal."
    ),
    "counter_trend": True,
    # 15m mean-reversion: 24 bars (~6h) is the outer envelope before
    # an oversold/overbought reading is no longer the same trade.
    "max_bars_held": 24,
    # Sibling-dedup family (P0-E): see ``strategies/rsi.py`` header
    # comment. All three RSI cadence variants share this family.
    "strategy_family": "rsi_mean_reversion",
}

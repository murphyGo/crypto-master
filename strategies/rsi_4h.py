"""4-hour RSI mean-reversion baseline (Phase 9.4).

Locks the universal :mod:`strategies.rsi` strategy to 4h candles
specifically — the swing-cadence variant the user originally asked
for ("4시간봉 RSI"). Same Wilder RSI math, same threshold logic, same
fixed-percentage SL/TP — only the declared ``timeframes`` differs,
so the engine + dashboard can list this as a distinct baseline next
to ``rsi_universal`` and ``rsi_15m``.

Why a separate file rather than just running ``rsi_universal`` on 4h:
the engine fetches one timeframe per cycle for single-TF strategies,
so a single universal entry can only represent *one* cadence per run.
Splitting the swing and scalp cadences into separate files lets both
fire in the same scan and gives the performance tracker independent
edge histories.

Related Requirements:
- FR-001 / FR-002 / FR-003 / FR-004
"""

from strategies.rsi import RSIMeanReversionStrategy

# Re-export the strategy class under a local name so the loader's
# ``BaseStrategy`` subclass scan finds it inside this module without
# instantiating the universal variant by accident.
RSI4hMeanReversionStrategy = RSIMeanReversionStrategy

TECHNIQUE_INFO = {
    "name": "rsi_4h",
    "version": "1.0.0",
    "description": (
        "RSI mean-reversion locked to 4h candles. Swing cadence: "
        "long when RSI<30, short when RSI>70."
    ),
    "author": "system",
    "symbols": [],  # universal — applies to every USDT pair
    "timeframes": ["4h"],
    "status": "experimental",
    "changelog": "Initial version (4h split from rsi_universal)",
    "counter_trend": True,
    # 4h mean-reversion: 6 bars (~1 day) is plenty for a single
    # oversold/overbought reversion to play out before the thesis
    # stales.
    "max_bars_held": 6,
}

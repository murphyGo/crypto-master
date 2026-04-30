---
name: donchian_turtle_system_2
version: 1.0.0
description: Turtle System 2 long-only Donchian breakout (55-bar entry / 20-bar exit) on BTC/USDT daily with ATR(20) position sizing and 2×ATR stop-loss.
technique_type: prompt
hypothesis: On BTC/USDT daily bars, a close above the prior 55-bar high produces a positive expectancy long trade exited at a close below the prior 20-bar low, because crypto markets exhibit return-momentum continuation after multi-month range expansion that exceeds the cost of fakeouts when filtered by ATR-based volatility sizing — falsifiable by walk-forward backtest where mean trade R-multiple ≤ 0 net of 0.1% round-trip fees and 1×ATR slippage.
---

# Donchian Channel Breakout — Turtle System 2 (55/20)

Catalog reference: **rank 7 — Donchian System 2 (55/20) Turtle**, category `breakout`, composite 17 (`doc 03 §5.2` / `doc 03 §16`). Long-only on BTC/ETH validated.

## 1. Hypothesis (Falsifiable)

After a multi-month consolidation, a daily close above the 55-day high marks the resolution of an accumulation range. In crypto, range-expansion breakouts persist longer than indicator-style mean reversions can reabsorb because:

1. Long-horizon positioning (spot ETF flows, perp OI build-up) re-prices in steps, not ticks.
2. The 55-day window matches the typical accumulation-to-markup transition on BTC daily (Wyckoff phase B → C → D analogue).
3. The 20-day exit asymmetrically protects against give-back of the markup phase before regime change is statistically confirmable.

**Falsification rule:** If a walk-forward backtest on BTC/USDT 1D from 2018-01-01 forward (≥ 3 OOS folds) produces mean trade R-multiple ≤ 0 net of 0.1% round-trip fees + 1×ATR slippage, OR Sharpe ≤ 0 OOS, the technique is rejected.

## 2. Market & Timeframe

- **Universe:** BTC/USDT (primary). ETH/USDT (secondary, same rules). Skip alts initially — System 2 was validated on liquid majors only.
- **Timeframe:** Daily (1D) close-based.
- **Side:** Long-only. (Original Turtle Rules included shorts; we disable shorts in crypto bull-biased regime — re-enable only after OOS validation on a bear-period sample.)

## 3. Indicators

All on closed daily bars.

- **Donchian Upper (55):** `max(high[1..55])` — highest high of last 55 bars **excluding** the current forming bar.
- **Donchian Lower (20):** `min(low[1..20])` — lowest low of last 20 bars **excluding** current.
- **ATR(20):** Wilder's True Range averaged over 20 bars.
- **Account equity (E):** mark-to-market USD equity at decision time.

## 4. Entry Rule (single condition gate, no stacking)

Open a long market order on the **next bar's open** when:
# Goal investigation: "+100% PnL in 3 months"

**Date:** 2026-05-23
**Question posed:** build a strategy that achieves +100% PnL within 90 days.
**Verdict:** Achievable only as a negative-expected-value leverage bet on
variance, **not** as a robust edge. Documented below with the full
return/ruin distribution so the bet can be taken (or declined) with eyes open.

## 1. Baseline — does any existing strategy have edge?

All 12 code strategies, Binance public klines, 1x leverage, 1% risk/trade.

| Window | Universe | Best result | Typical | Sharpe |
|---|---|---|---|---|
| 90d (1h) | BTC/ETH/SOL/DOGE/BNB/XRP | +2.3% (momentum, XRP) | flat→negative | ~0 |
| 365d (1h) | BTC, ETH | +1.9% (weinstein, ETH) | flat→negative | ~0 |

Buy&hold over the 365d window: BTC −31.5%, ETH −21.4% (a real bear/chop
regime). Every strategy is noise around zero, slightly negative after fees.
**No harvestable edge exists in the OHLCV-only library.**

## 2. Purpose-built strategy — `tsmom_vol_breakout`

The most academically robust OHLCV-only crypto edge is time-series momentum.
Implemented as trend (EMA50/200) + regime gate (EMA200 slope ≥ 0.5·ATR,
forces flat in chop) + momentum sign (30d) + 20-bar Donchian breakout trigger,
ATR-sized 2:1 exits, 60-bar time-stop. All round-number params.

Result (4h, 2yr, BTC/ETH/SOL/BNB, 1x, 1% risk):

| Symbol | ret% | win% | trades | maxDD% | Sharpe |
|---|---|---|---|---|---|
| BTC | −2.1 | 33.8 | 77 | 3.8 | −0.07 |
| ETH | +2.3 | 38.8 | 80 | 3.7 | +0.04 |
| SOL | −4.7 | 31.9 | 69 | 5.6 | −0.10 |
| BNB | +2.2 | 43.5 | 69 | 2.7 | +0.07 |

Breakeven. Win rate ~33–43% against a 2:1 payoff sits right on the
breakeven line; fees push it slightly negative. A clean design does **not**
rescue a market with no trend to harvest. This is the honest ceiling.

## 3. The leverage gamble (eyes open)

The platform caps position size at `max_position_size_percent` (default 10%
of balance, `src/trading/strategy.py:98`). With that rail on, the best 90-day
outcome over 2 years is +44.6% and nothing ever liquidates — **+100%/90d is
structurally unreachable** at default risk settings.

Lifting the cap to 100% and applying 20x leverage, over 180 rolling 90-day
windows × {BTC,ETH,SOL}:

| risk/trade | median 90d | P(+100% by window end) | P(+100% touched) | P(end ≤ −50%) | max |
|---|---|---|---|---|---|
| 5% | +0.6% | 0% | 0% | 0% | +60% |
| 10% | −2.7% | 1.1% | 7.2% | 3.9% | +136% |
| 20% | −19.8% | 7.2% | 35.0% | 28.9% | +309% |
| 40% | −66.1% | 7.2% | 47.8% | 69.4% | +448% |

This matches the quant model: a Sharpe-≈0 signal levered to ~160% annualized
vol gives ~25–35% chance of *touching* +100% in a quarter, bought with a
comparable chance of halving the account. **Expected value is negative; the
upside lives entirely in the right tail.** Raising risk past ~20% trades a
little more tail upside for a lot more ruin.

## 4. Bottom line

- A strategy + config that *achieved* +100% in 90-day backtests exists
  (`tsmom_vol_breakout` at ~20% risk / 20x / cap lifted — max +309%).
- It is a gamble, not an edge. Negative median, ~1-in-3 chance of doubling,
  ~1-in-3 chance of a 50%+ loss in the same window.
- A genuinely better path requires widening the **data** edge (funding /
  open-interest / liquidation / basis), which is not wired in this repo.

## Reproduce

```bash
python -m scripts.goal_baseline --symbol BTCUSDT --interval 1h --days 365
python -m scripts.goal_eval   --file strategies/tsmom_vol_breakout.py --days 730
python -m scripts.goal_gamble --file strategies/tsmom_vol_breakout.py \
    --risks 5,10,20,40 --leverage 20 --max-pos 100
```

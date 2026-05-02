# Trade-Quality Analysis (2026-05-01)

## 0. Sample-Size Disclaimer

This analysis follows `docs/research/trade-quality-design-2026-05-01.md`,
but the live Fly volume has moved since the design pass. The design
expected 9 closed paper trades; the snapshot pulled on 2026-05-03
contains 12 paper trades: 11 closed and 1 still open. The 11 closed
trades are the measurement set below.

All aggregate conclusions are preliminary. Any `n < 30` metric is
directional only; sub-buckets with `n < 10` are especially fragile.

Data sources:

- Fly volume pull: `/data/trades/paper/trades.json`,
  `/data/proposals/*.json`, `/data/performance/`, `/data/portfolio/`,
  and `/data/runtime/`.
- Local analysis snapshot:
  `/private/tmp/crypto-master-phase18-2-data`.
- Public Binance klines: 1h BTC/USDT for regime tagging; 1m
  per-symbol klines for rejected-proposal hypothetical EV.

## 1. Per-Trade Table

`drift_bps` uses the persisted fill price except for sub-second
stop-loss exits, where the exit price is the first persisted live-price
proxy after fill. That recovers the two stale-fill cases that Phase
18.1 was designed to stop.

| trade | symbol | strategy | side | signal | latency_s | drift_bps | sl_bps | tp_bps | rr | exit | pnl | R | regime |
|-------|--------|----------|------|--------|-----------|-----------|--------|--------|----|------|-----|---|--------|
| `5d51cba3` | ETH/USDT | simple_trend_analysis | long | long | 193.4 | -99.0 | 77.5 | 116.2 | 1.50 | stop_loss | -10.70 | -1.38 | high |
| `63be591a` | BTC/USDT | simple_trend_analysis | short | short | 251.4 | 0.0 | 111.5 | 223.1 | 2.00 | stop_loss | -15.02 | -1.35 | high |
| `95d94ab1` | SOL/USDT | simple_trend_analysis | short | short | 125.7 | 0.0 | 84.7 | 159.8 | 1.89 | stop_loss | -9.39 | -1.11 | med |
| `d0ff4682` | ETH/USDT | chasulang_ict_smc | short | short | 201.9 | 0.0 | 26.2 | 78.7 | 3.00 | stop_loss | -5.61 | -2.14 | low |
| `43159653` | BTC/USDT | simple_trend_analysis | short | short | 816.4 | 0.0 | 35.0 | 165.8 | 4.74 | stop_loss | -6.31 | -1.80 | low |
| `4af968cd` | ETH/USDT | simple_trend_analysis | long | long | 183.3 | 0.0 | 75.4 | 155.0 | 2.06 | stop_loss | -8.54 | -1.13 | low |
| `0cc6d905` | AVAX/USDT | simple_trend_analysis | long | long | 0.0 | 0.0 | 71.0 | 111.9 | 1.58 | take_profit | 12.11 | 1.70 | low |
| `3b8d567c` | ADA/USDT | simple_trend_analysis | long | long | 40.9 | 0.0 | 209.0 | 331.2 | 1.58 | stop_loss | -26.03 | -1.25 | med |
| `e2302a9e` | BNB/USDT | simple_trend_analysis | long | long | 89.5 | 0.0 | 71.7 | 127.4 | 1.78 | stop_loss | -9.01 | -1.26 | med |
| `2c527297` | AVAX/USDT | simple_trend_analysis | long | long | 0.0 | -203.4 | 59.2 | 99.0 | 1.67 | stop_loss | -21.13 | -3.57 | high |
| `3e679810` | ETH/USDT | chasulang_ict_smc | short | short | 228.5 | 0.0 | 42.9 | 150.2 | 3.50 | take_profit | 37.97 | 8.85 | high |

Every closed trade resolved to a `ProposalRecord`; no orphan closed
trades were found. The current window also contains 18 accepted
proposal records with no linked trade. Those are not included in live
EV because no realised outcome exists.

## 2. Per-Strategy EV

`baseline_ev_usdt` cannot be computed: the repo and Fly snapshot do not
contain `data/backtest/baselines/<strategy>/summary.json` artefacts for
these live LLM strategies. `docs/baselines.md` still documents the
operator-first-run state for deterministic indicator baselines only.

| strategy | n | wins | losses | mean_win | mean_loss | expectancy_R | live_ev_usdt | baseline_ev_usdt | delta |
|----------|---|------|--------|----------|-----------|--------------|--------------|------------------|-------|
| chasulang_ict_smc | 2 | 1 | 1 | 37.97 | -5.61 | 3.35 | 16.18 | N/A | N/A |
| simple_trend_analysis | 9 | 1 | 8 | 12.11 | -13.27 | -1.24 | -10.45 | N/A | N/A |

## 3. Per-Regime EV

Regime tags use empirical tertiles of BTC/USDT 1h ATR(14) / close
at each proposal timestamp. The tertile boundaries for this sample
were 0.4326% and 0.4724%.

| regime | n | wins | losses | expectancy_R | mean_pnl_usdt |
|--------|---|------|--------|--------------|---------------|
| high | 4 | 1 | 3 | 0.64 | -2.22 |
| low | 4 | 1 | 3 | -0.84 | -2.09 |
| med | 3 | 0 | 3 | -1.20 | -14.81 |

## 4. Per-Exit-Reason

| exit_reason | n | mean_pnl_usdt | mean_r_multiple | pct_of_total |
|-------------|---|---------------|-----------------|--------------|
| stop_loss | 9 | -12.42 | -1.67 | 81.8% |
| take_profit | 2 | 25.04 | 5.28 | 18.2% |

The loss side is not merely frequent; it is deeper than -1R on
average. That points at stale-fill / instant-stop cases and fee/slip
effects, not just an ordinary 1R stop profile.

## 5. Latency vs Drift

The persisted fill price usually equals the proposal entry, so latency
does not show a clean monotonic relationship with recorded drift. The
two sub-second stop-loss exits are the important exceptions.

```text
latency_s  drift_bps  trade
0          0.0        0cc6d905
0          -203.4     2c527297
41         0.0        3b8d567c
90         0.0        e2302a9e
126        0.0        95d94ab1
183        0.0        4af968cd
193        -99.0      5d51cba3
202        0.0        d0ff4682
229        0.0        3e679810
251        0.0        63be591a
816        0.0        43159653
```

`5d51cba3` is the Phase 18.1 smoking-gun stale fill. `2c527297`
shows the same failure mode without LLM latency: the proposal was
accepted immediately, then closed 0.476s later at a price already
past the stop.

## 6. Rejected-vs-Accepted EV

The accepted bucket below is realised closed-trade R. Rejected
threshold proposals are walked over public Binance 1m klines for the
median realised holding period of the accepted set, 2.95h. If both SL
and TP are touched in the same 1m candle, the result is conservatively
counted as SL.

| bucket | n | expectancy_R | mean_composite_score | outcome_mix |
|--------|---|--------------|----------------------|-------------|
| accepted closed | 11 | -0.40 | 0.3150 | 2 TP / 9 SL |
| rejected threshold | 98 | -0.18 | 0.1803 | 11 TP / 42 SL / 45 neither |

Accepted expectancy is worse than rejected-threshold hypothetical
expectancy, and both buckets clear the Phase 18.2 minimum sample
requirement (`n >= 5`). The composite-gate inversion rule therefore
fires, with the usual small-sample caveat.

## 7. 50-bps Recalibration

Empirical absolute drift distribution, using the sub-second stop-loss
exit proxy described in section 1:

| percentile | abs_drift_bps |
|------------|---------------|
| p50 | 0.0 |
| p75 | 0.0 |
| p90 | 99.0 |
| p95 | 151.2 |
| p99 | 192.9 |

Two of 11 closed trades exceeded 50 bps by the live-price proxy.
There were no `slippage_exceeds_tolerance` rejection records in the
sample window, so the post-18.1 rejected tail could not be used to
augment the CDF.

The 30-bps tightening rule does not fire: p95 is well above 30 bps.
The immediate problem is not that 50 bps is too loose; it is that the
pre-18.1 accepted set contains fills that should not have happened at
all.

## 8. Findings

Q1 50-bps calibration: do not tighten on this sample. p95 absolute
drift is 151.2 bps and the two worst rows are stale/instant-stop
cases. Phase 18.1's gate, not a lower tolerance, is the right first
control. Re-run after at least 30 post-18.1 closed trades and include
slippage-rejection drift values.

Q2 SL / R:R appropriateness: `simple_trend_analysis` stop distances
cluster from 35.0 to 209.0 bps, but the losing realised R averages
-1.24R for that strategy and stop-loss exits average -1.67R overall.
The stop framework is being punished by stale/instant fills and
selection quality; this sample does not support an SL-width edit yet.

Q3 composite-gate inversion: rejected threshold proposals had a
hypothetical -0.18R versus accepted closed trades at -0.40R. With
n=11 accepted and n=98 rejected, the Phase 18.2 inversion rule fires.
The rejected bucket contains many "neither hit within 2.95h" outcomes
and uses public klines rather than engine-owned replay, so the result
should start a composite-score review rather than a blind threshold
edit.

Q4 strategy-loss attribution: `simple_trend_analysis` carries 8 of 9
losses and has expectancy -1.24R over 9 closed trades. That exceeds
the Phase 18.2 concentration trigger.

## 9. Recommendation

Two rules fire, ordered by Phase 18.2 severity:

1. Rule 7.2: composite-gate inversion. Accepted closed expectancy is
   -0.40R and rejected-threshold hypothetical expectancy is -0.18R,
   with n=11 and n=98 respectively. Recommend a top-priority follow-up
   that re-examines `src/proposal/engine.py::ProposalScore`; do not
   apply a quick global threshold tweak.
2. Rule 7.3: strategy-specific gate / removal. `simple_trend_analysis`
   is responsible for 8/9 losses, above the >= 6/9 threshold, and its
   expectancy is -1.24R over n=9, below the <= -0.5R threshold. The
   composite-score review should include either blocking
   `simple_trend_analysis` in paper runtime or giving it a higher
   strategy-specific threshold until enough post-18.1 evidence proves
   the stale-quote fix changed its realised EV.

Do not edit global slippage tolerance from this sample. Re-run the
diagnostic when the post-18.1 sample reaches 30 closed trades.

No new TECH-DEBT item is needed. The baseline-delta gap is already
covered by the documented Phase 25.3 Part B operator-first-run state,
and the accepted-without-trade persistence ambiguity is already
tracked as DEBT-015.

## 10. Methodology Cross-Check

- [x] All closed trades in the current Fly snapshot are present in
      section 1. Scope drift from 9 to 11 closed trades is documented.
- [x] Every closed trade has a back-linked `ProposalRecord`; no
      orphan closed trades were found.
- [x] Baseline delta checked; no applicable baseline summary artefacts
      exist for the touched LLM strategies.
- [x] Rejected hypothetical EV uses only post-`created_at` 1m candles
      and stops at the accepted-set median holding period, 2.95h.
- [x] Drift CDF notes that no `slippage_exceeds_tolerance` rejected
      tail exists in this sample.
- [x] Recommendation cites the fired rules and numerical thresholds.
- [x] Sample-size caveats are attached to the document and all
      aggregates carry `n`.
- [x] No new TECH-DEBT item required.
- [x] `docs/baselines.md` cross-reference pointer added.

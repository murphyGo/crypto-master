# Trade-Quality Diagnostic — Methodology Spec (2026-05-01)

> Methodology / design doc for the Phase 18.2 diagnostic. The
> analysis itself runs next cycle and lands as
> `docs/research/trade-quality-2026-05-01.md`. This document
> defines what data we pull, what we compute, what tables we
> emit, and what conclusion-by-conclusion next-step rule fires.
>
> **This is not the analysis. This is the framework the analyst
> will follow.**

---

## 1. Goal & Non-Goals

### 1.1 Goal

Produce a single research document
(`docs/research/trade-quality-2026-05-01.md`) that classifies
every closed paper trade currently on the Fly volume against
signal quality, regime, exit reason, realised slippage, and the
rejected-vs-accepted EV gap. The output answers four diagnostic
questions:

1. **50-bps calibration** — is `EngineConfig.fill_slippage_
   tolerance = Decimal("0.005")` (Phase 18.1 default) correctly
   sized against the empirical realised-drift distribution?
2. **SL / R:R appropriateness** — is the SL distance and R:R
   ratio configured by `simple_trend_analysis` and
   `bollinger_band_reversion` appropriate to the typical
   intra-cycle volatility we are actually seeing on Fly?
3. **Composite-gate inversion** — are the surviving accepted
   proposals systematically *worse* than the rejected ones?
   I.e. is the composite-score gate inverting selection?
4. **Strategy-loss attribution** — which strategy is responsible
   for which loss class? Is one strategy carrying >70% of the
   losers, or are the losses distributed?

The document ends with a single explicit recommendation that
feeds the next sub-task shape (see §7 Decision Rules).

### 1.2 Non-Goals

This is a **measurement pass**. The following are explicitly
out of scope and must not be done as part of Phase 18.2:

- No alternative SL / TP strategy testing. No "what if we used
  ATR-based SL instead?" experiments.
- No threshold edits to `EngineConfig.fill_slippage_tolerance`,
  `EngineConfig.reject_if_past_stop_loss`, the auto-approval
  composite threshold, or any other engine knob. The analysis
  *recommends* a number; Phase 18.3 (or successor) edits it.
- No strategy redesign of `simple_trend_analysis` or
  `bollinger_band_reversion`. No new `strategies/` files.
- No `src/` or `tests/` changes of any kind.
- No backfill of historical `data/portfolio/snapshots.json`
  rows pre-dating Phase 17.2 portfolio-snapshot wiring (commit
  `094a79d`). If snapshots only exist post-17.2, the equity
  curve is partial — flag and proceed.

---

## 2. Data Sources

All paths below are on the Fly persistent volume mounted at
`/data` (production) or in `data/` (local). The analyst pulls
from the production volume.

### 2.1 Closed Paper Trades

- **Path**: `/data/trades/paper/trades.json` on Fly volume.
- **Pull**:
  ```bash
  flyctl ssh console --app crypto-master \
      -C "cat /data/trades/paper/trades.json" > /tmp/trades.json
  ```
- **Schema**: `TradeHistory` model (see `src/strategy/
  performance.py`). Required fields: `trade_id`, `symbol`,
  `side`, `entry_price`, `exit_price`, `quantity`, `pnl`,
  `entry_time`, `exit_time`, `exit_reason`, `proposal_id`
  (back-link to the proposal record).
- **Volume on 2026-04-30**: 9 closed trades.

### 2.2 Proposals (Accepted + Rejected)

- **Path**: `/data/proposals/*.json` on Fly volume — one file
  per `ProposalRecord`.
- **Pull**: prefer `flyctl ssh sftp` for bulk download; fallback
  to `flyctl ssh console -C "tar czf - /data/proposals"` piped
  to local extraction. The file count is moderate (~hundreds at
  most after Phase 11.4 retention) so either works.
- **Schema**: `ProposalRecord` (see `src/proposal/history.py`).
  Required fields: `proposal_id`, `created_at`, `symbol`,
  `signal`, `entry_price`, `stop_loss`, `take_profit`,
  `composite_score`, `decision` (`accepted` / `rejected`),
  `decision_reason` (Phase 18.1 added
  `stale_quote_past_sl` / `slippage_exceeds_tolerance`;
  Phase 12.1 added cap-rejection reason; Phase 15.1 documented
  the `composite N below threshold M` form), `strategy_name`,
  `version`.
- **Cross-link**: every closed trade carries a `proposal_id`
  pointing back to one of these records (Phase 8.1
  `ProposalHistory.attach_trade`).

### 2.3 Equity Curve

- **Path**: `/data/portfolio/snapshots.json` (Phase 17.2).
- **Use**: drawdown context per trade. May be partial if some
  closed trades pre-date Phase 17.2 portfolio-snapshot wiring;
  flag in the analysis if so.

### 2.4 Baselines (Cross-Validation)

- **Path**: `data/backtest/baselines/<strategy>/summary.json` —
  Phase 10.3 baseline reference numbers.
- **Use**: per-strategy live-vs-baseline EV delta. If the live
  EV trails the baseline EV by more than the baseline's own
  noise floor, that's a slippage / fill-quality signal
  independent of the strategy's edge — surface as a separate
  row in the per-strategy table.

### 2.5 Strategy SL/TP Construction Logic

- **Path**: `strategies/*.md` (prompt-type) and `strategies/*.py`
  (code-type).
- **Use**: read the SL/TP construction text for
  `simple_trend_analysis` and `bollinger_band_reversion` so the
  analysis can attribute "SL too tight relative to ATR" vs
  "SL appropriate but signal selection bad" correctly.

---

## 3. Per-Trade Analysis Dimensions

For every closed trade in §2.1, compute the following columns
and persist as a structured table (markdown with sortable order
on `trade_id` is fine — no CSV / JSON output required, the doc
is the artefact):

| Field | Source | Formula / Notes |
|-------|--------|-----------------|
| `trade_id` | trades.json | shortened to first 8 chars for table readability |
| `symbol` | trades.json | e.g. `ETH/USDT` |
| `strategy` | proposal.strategy_name | back-linked via `proposal_id` |
| `side` | trades.json | `long` / `short` |
| `signal_direction` | proposal.signal | sanity check vs `side` |
| `latency_seconds` | `position.opened_at - proposal.created_at` | the chasulang/Claude CLI delay |
| `realised_drift_bps` | `(fill_price - proposal.entry_price) / proposal.entry_price * 10_000` | post-Phase-18.1, expect bounded by tolerance |
| `sl_distance_bps` | `abs(entry - sl) / entry * 10_000` | strategy-set, pre-trade |
| `tp_distance_bps` | `abs(entry - tp) / entry * 10_000` | strategy-set, pre-trade |
| `rr_ratio` | `tp_distance_bps / sl_distance_bps` | unitless |
| `exit_reason` | trades.json | `take_profit` / `stop_loss` / `time_stop` / `manual` |
| `pnl_realised` | trades.json | USDT, signed |
| `r_multiple` | `pnl / (qty × abs(entry - sl))` | unitless; see §5 |
| `regime_tag` | derived | `low` / `med` / `high` — see §3.1 |

### 3.1 Regime Tag Construction

Use a simple bucketed BTC 1H volatility classification at the
proposal's `created_at` timestamp:

- Pull BTC/USDT 1H OHLCV via `BinanceExchange.get_ohlcv` for a
  window of `[created_at - 14h, created_at]` (14 candles for
  ATR-14).
- Compute `ATR(14) / close` as a rolling pct.
- Buckets: `low` ≤ p33, `med` p33–p66, `high` ≥ p66 — using
  the empirical distribution from the same window of trades
  (not a hand-picked threshold). If `docs/baselines.md`
  documents a regime-threshold convention by the time the
  analyst runs, prefer that convention; otherwise document the
  empirical-tertile choice in the analysis doc and surface as
  TECH-DEBT.

---

## 4. Aggregation Views (Output Sections)

The analysis doc produces these tables and one chart, in this
order:

### 4.1 Per-Strategy EV Table

| strategy | n | wins | losses | mean_win | mean_loss | expectancy_R | live_ev_usdt | baseline_ev_usdt | delta |
|----------|---|------|--------|----------|-----------|--------------|--------------|------------------|-------|

`baseline_ev_usdt` from §2.4; `delta = live - baseline`. With
n=9 across 2 strategies the per-strategy n is small (~4-5 each)
— see §9 sample-size disclaimer.

### 4.2 Per-Regime EV Table

| regime | n | wins | losses | expectancy_R | mean_pnl_usdt |
|--------|---|------|--------|--------------|---------------|

### 4.3 Per-Exit-Reason Table

| exit_reason | n | mean_pnl_usdt | mean_r_multiple | pct_of_total |
|-------------|---|---------------|-----------------|--------------|

Expected: `stop_loss` carries 8/9 with a tight (≤ -1R)
distribution; `take_profit` 1/9. The analysis should examine
whether the `stop_loss` exits cluster at a specific drift bin —
if many fired ≤ 30 bps post-fill, that's a calibration signal
for §4.6.

### 4.4 Latency vs Adverse Drift Scatter

X axis: `latency_seconds`. Y axis: `realised_drift_bps`
(signed: positive = filled above entry for longs / below for
shorts; convert to "adverse" sign so up = bad).
Plot every closed trade as a point; if the relationship is
monotonic (longer latency → more adverse drift), Phase 18.1's
gate threshold needs to scale with latency, not be flat.

A markdown ASCII scatter or a linked PNG is acceptable; if PNG
the analyst saves under `docs/research/figures/2026-05-01-
latency-drift.png` and links inline.

### 4.5 Rejected-vs-Accepted EV Gap

For every rejected proposal in the same time window, compute a
**hypothetical** outcome by walking the post-`created_at` price
series against `entry / sl / tp`: if the price reaches `tp`
first, hypothetical `pnl = +R`; if `sl` first, `pnl = -1R`; if
neither within a configurable horizon (default = median holding
period of the accepted set), `pnl = 0`. Aggregate:

| bucket | n | hypothetical_expectancy_R | mean_composite_score |
|--------|---|----------------------------|----------------------|
| accepted | (live n) | (live R) | ... |
| rejected (threshold) | ... | ... | ... |
| rejected (cap) | ... | ... | ... |
| rejected (stale-quote, post-18.1) | ... | ... | ... |

If `accepted_expectancy_R ≤ rejected(threshold)_expectancy_R`,
the composite gate is selecting against us — top-priority
escalation per §7.

### 4.6 50-bps Recalibration — Empirical Drift CDF

Plot the empirical CDF of `realised_drift_bps` across the
accepted set. Report:

- p50, p75, p90, p95, p99 of `abs(realised_drift_bps)`.
- Recommended new tolerance per §7 decision rule.

Caveat: post-Phase-18.1 drift values are *truncated* at
50 bps by construction (anything beyond was rejected). The
analyst must either (a) augment with the rejection-recorded
drift values from `slippage_exceeds_tolerance` events to
recover the un-truncated tail, or (b) flag the truncation and
recommend conservatively. Prefer (a) when the rejected count
is non-zero on Fly.

---

## 5. EV / R-Multiple Formulae

Precise definitions, fixed in this spec so two analysts running
the spec independently arrive at the same number.

### 5.1 Per-Trade R-Multiple

```
risk_per_unit = abs(proposal.entry_price - proposal.stop_loss)
risk_total = trade.quantity * risk_per_unit
r_multiple = trade.pnl / risk_total
```

Notes:
- Use `proposal.entry_price`, **not** `trade.entry_price`. In
  the 9-trade window the two are equal by construction (Phase
  18.1's no-silent-switch contract); but using the proposal's
  price decouples the metric from any future fill-price
  semantics change.
- `trade.pnl` is the realised PnL after fees per Phase 4.3 fee
  simulation. R-multiple is therefore *post-fee* — an
  important detail for the SL-distance-vs-fee sanity check.
- For shorts, `entry - sl` is positive (sl > entry); the
  `abs()` keeps `risk_total` positive in both directions.

### 5.2 Expectancy

```
expectancy_R = mean(r_multiple over n trades)
```

Sample-size disclosure required: any expectancy reported with
n < 30 must carry a `(n=N, preliminary)` annotation. n < 10 must
additionally carry a "directional only — awaits more data"
caveat in the surrounding prose.

### 5.3 EV in USDT

```
ev_usdt = mean(trade.pnl over n trades)
```

Used for `live_ev_usdt` in §4.1. Not the same as expectancy_R
because pnl varies with `quantity`, not just R; expectancy_R is
the unitless trade-quality metric, ev_usdt is the operational
P&L metric.

---

## 6. Output Schema

The analysis doc `docs/research/trade-quality-2026-05-01.md`
follows this skeleton:

```
# Trade-Quality Analysis (2026-05-01)

## 0. Sample-Size Disclaimer
   (n=9 closed; conclusion strength tagged accordingly)

## 1. Per-Trade Table
   (full §3 table, all 9 trades)

## 2. Per-Strategy EV (§4.1)
## 3. Per-Regime EV (§4.2)
## 4. Per-Exit-Reason (§4.3)
## 5. Latency vs Drift (§4.4 + scatter)
## 6. Rejected-vs-Accepted EV (§4.5)
## 7. 50-bps Recalibration (§4.6)

## 8. Findings (one paragraph per diagnostic question §1.1)
   - Q1 50-bps calibration: <answer with numbers>
   - Q2 SL / R:R appropriateness: <answer>
   - Q3 Composite-gate inversion: <answer>
   - Q4 Strategy-loss attribution: <answer>

## 9. Recommendation (§7 decision rules applied)
## 10. Methodology Cross-Check (this doc)
```

### 6.1 Worked Example — ETH `5d51cba3`

The ETH `5d51cba3-900f-4415-a401-096df391860a` trade
(proposal `6ef8c07e...`) is the smoking-gun case from Phase
18.1's background. Pre-fill values are already known from the
Phase 18.1 dev-plan entry:

- `proposal.created_at` = `2026-04-30T14:43:21Z`
- `position.opened_at` = `2026-04-30T14:46:34Z`
- `latency_seconds` = `193`
- `proposal.entry_price` = `2323`
- `proposal.stop_loss` = `2305`
- `sl_distance_bps` = `(2323 - 2305) / 2323 * 10_000` ≈ `77.5`
- `trade.exit_price` = `2300`
- `pnl` (placeholder; pull from trades.json) ≈ `-` value
- `r_multiple` ≈ `-1.28` (slightly worse than 1R because the
  fill happened past SL — exact value depends on fees)
- `regime_tag` = TBD (analyst computes from BTC 1H window)
- `exit_reason` = `stop_loss`

This trade pre-dates Phase 18.1's gate, so its `realised_drift_
bps` is unbounded — useful as one data point in the un-truncated
tail per §4.6.

The analyst includes this row as the first row of §4.1's per-
trade table and references it in the Q1 finding.

---

## 7. Decision Rules

The recommendation in §9 of the analysis doc must be one of:

### 7.1 Tighten Slippage Tolerance — Phase 18.3 Trigger

**Trigger**: `p95(abs(realised_drift_bps))` over the accepted
+ rejected-by-slippage set ≤ 30.

**Action**: Recommend a Phase 18.3 sub-task that lowers
`EngineConfig.fill_slippage_tolerance` from `Decimal("0.005")`
(50 bps) to `Decimal("0.003")` (30 bps) with the corresponding
`Settings.engine_fill_slippage_tolerance` env override and
`.env.example` doc update. Cite the empirical CDF in the
sub-task background.

### 7.2 Composite-Gate Inversion — Phase 19 Top-Priority

**Trigger**: §4.5 shows `accepted_expectancy_R ≤
rejected(threshold)_expectancy_R` with n on both sides ≥ 5.

**Action**: Recommend a top-priority Phase 19 sub-task
(planner's call on numbering) that re-examines the composite
score formula in `src/proposal/engine.py::ProposalScore`. Cite
the rejected-vs-accepted gap. Do NOT recommend a quick
threshold tweak — gate inversion is a formula bug, not a knob
miscalibration.

### 7.3 Strategy-Specific Gate / Removal

**Trigger**: One strategy carries ≥ 70% of losses (i.e. ≥ 6/9
losers from one strategy) AND that strategy's expectancy_R is
≤ -0.5 over n ≥ 4 trades.

**Action**: Recommend either a strategy-specific composite
threshold floor or a removal of the strategy from production.
Cite the per-strategy EV table.

### 7.4 No Clear Signal — Return to Dev Plan

**Trigger**: None of the above fire, OR the sample size is too
small to fire any rule with the required minima.

**Action**: Document the partial findings, note "preliminary,
awaits more data after the next N trades", and return control
to the team-lead with a recommendation to re-run the
diagnostic when n reaches 30.

### 7.5 Multiple Triggers Fire

**Action**: Rules above are listed in increasing severity.
Multiple may fire; the recommendation reports all, ordered by
severity (Composite-Gate Inversion > Strategy Removal >
Tolerance Tighten > No-Signal). Phase 18.3 owns whichever the
team-lead picks up first.

---

## 8. Out of Scope (Restated)

- No `src/` changes.
- No `tests/` changes.
- No `strategies/` changes.
- No threshold edits.
- No alternative SL / TP strategy testing.
- No live or paper trade re-execution.
- No backfill of pre-Phase-17.2 portfolio snapshots.
- No new FRs / NFRs.

Anything that surfaces as needed-but-deferred during the
analysis becomes a one-line `docs/TECH-DEBT.md` entry, not an
in-scope edit.

---

## 9. Sample-Size Disclaimer

n = 9 closed trades is small. Any conclusion drawn from a
sub-bucket (per-strategy with n ≈ 4, per-regime with n ≈ 3,
per-exit-reason where `take_profit` has n=1) is preliminary.
The analyst must:

- Annotate every aggregate metric with `(n=N)`.
- Flag any conclusion needing > 9 samples for power as
  `preliminary, awaits more data`.
- Refrain from recommending strategy removal (§7.3) unless the
  loser concentration is unambiguous (≥ 6/9, not 5/9).
- Refrain from recommending composite-gate replacement (§7.2)
  unless the rejected-vs-accepted bucket comparison has n ≥ 5
  on both sides.

The 50-bps recalibration (§7.1) is the most data-hungry
recommendation — it requires the empirical drift CDF to be
informative, which it isn't if every accepted trade is bunched
near the gate. If p95 cannot be estimated reliably (n < 10 in
the un-truncated set), §7.1 falls back to §7.4.

---

## 10. Cross-Check Before Publishing

The analyst's pre-publish checklist:

- [ ] All 9 closed trades present in §1 per-trade table.
- [ ] Every trade has a back-linked `proposal_id` resolved to
      a real `ProposalRecord` — surface any orphans.
- [ ] §4.1 `delta` column computed against the same period as
      the baseline summary's quoted period (not a different
      window).
- [ ] §4.5 hypothetical-EV calculation does not look ahead
      past each rejected proposal's `created_at` by more than
      the median holding period of the accepted set.
- [ ] §4.6 CDF augmented with rejected-by-slippage drift
      values (or truncation explicitly flagged).
- [ ] §9 Recommendation cites which §7 rule fired and the
      numerical trigger threshold met.
- [ ] Sample-size annotations on every aggregate metric.
- [ ] One-line `docs/TECH-DEBT.md` entry for any newly-
      surfaced gap, or explicit "no new debt" statement.
- [ ] `docs/baselines.md` cross-reference pointer added for
      the strategies touched.

---

## 11. References

- `docs/development-plan.md` Phase 18.1 — stale-quote sanity
  gate (the prerequisite that bounded post-fill drift).
- `docs/development-plan.md` Phase 18.2 — this sub-task entry.
- `docs/baselines.md` — baseline reference numbers per Phase
  10.3 (consumed in §4.1).
- `docs/research/strategies/00-priority-matrix.md` — strategy
  taxonomy for §4.4 attribution.
- `src/strategy/performance.py::TradeHistory` — closed-trade
  record schema.
- `src/proposal/history.py::ProposalRecord` — proposal record
  schema.
- `src/proposal/engine.py::ProposalScore` — composite score
  formula (§7.2 escalation target).
- `src/runtime/engine.py::_stale_quote_gate` — Phase 18.1 gate
  (§4.6 truncation source).
- Session log `docs/sessions/2026-04-30-phase-18.1-stale-
  quote-gate.md` — the smoking-gun ETH `5d51cba3` worked
  example source.

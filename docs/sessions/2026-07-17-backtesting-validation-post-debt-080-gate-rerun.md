# Session: Post-DEBT-080 robustness-gate re-run (first hole-free verdicts)

- **Date**: 2026-07-17
- **Unit**: `backtesting-validation`
- **Task**: Re-run `scripts/run_robustness_gate.py --live` for all 9
  registered strategies now that DEBT-080 fixed the pagination holes.
  Pre-fix `--live` verdicts on >1500-bar 1h/15m windows (1h > 62d,
  15m > 15.6d at the default 90d window) were computed on data missing
  ~1/3 of its calendar span and are superseded by this run.
- **Related Requirements**: FR-026, FR-034, NFR-006
- **Data**: Binance USDT-perp public klines, live fetch via the fixed
  paginator (contiguity-asserted), default 90-day window ending
  2026-07-17. Note the window is one macro regime slice (the 2026 bear
  leg) — regime sub-gate diversity is limited by the calendar, not the
  data quality.

## Verdicts (BTC/USDT, 90d)

| Strategy | TF | Overall | OOS | Walk-fwd | Regime | Sensitivity |
|----------|----|---------|-----|----------|--------|-------------|
| `bollinger_band_reversion` | 1h | FAILED | FAILED | FAILED (0/5) | FAILED (bear, sideways) | FAILED |
| `rsi_universal` | 1h | FAILED | SKIPPED (OOS n=9) | FAILED (2/5) | FAILED (bull, bear) | FAILED |
| `rsi_4h` | 4h | FAILED | SKIPPED (OOS n=1) | FAILED (0/1) | SKIPPED (1 regime) | FAILED |
| `rsi_15m` | 15m | FAILED | SKIPPED (OOS n=8) | FAILED (1/5) | FAILED (all) | FAILED |
| `vwap_mean_reversion` | 15m | FAILED | FAILED | FAILED (0/5) | FAILED (all) | SKIPPED (no grid) |
| `session_vwap_pullback` | 15m | PASSED* | SKIPPED | SKIPPED | SKIPPED | SKIPPED |
| `vcp_breakout` | 4h | PASSED* | SKIPPED | SKIPPED | SKIPPED | SKIPPED |
| `raschke_holy_grail` | 1h | FAILED | FAILED | FAILED (1/5) | FAILED (all) | SKIPPED (no grid) |
| `ma_crossover` | 1h | FAILED | FAILED | FAILED (1/5) | FAILED (all) | FAILED |

Baseline Sharpes on the window are negative across the board (-0.005 to
-0.46). Consistent with the standing no-OHLCV-only-edge finding — now
established on hole-free data for the first time.

## \*Vacuous-pass observation (gate-semantics defect candidate)

`session_vwap_pullback` and `vcp_breakout` produced **zero trades** in the
window, so all four sub-gates SKIPPED — and
`RobustnessReport.overall_passed = all(g.status != FAILED)` reports
**PASSED** when every gate skipped. A strategy that never fires "passes"
the promotion gate, which inverts the gate's intent (promotion requires
positive evidence, not absence of negative evidence). Proposed follow-up:
`overall_passed` should require at least one PASSED sub-gate (or report a
distinct INSUFFICIENT_EVIDENCE outcome). Not filed as debt yet — operator
decision pending.

## Operator notes

- No config/promotion changes made from these results; all listed
  strategies remain `experimental` (except `tsmom_vol_breakout`, `active`,
  not in the gate spec list — 4h window ≤ 2000 bars was never affected by
  DEBT-080).
- The 90d single-regime window limits what "regime" sub-gate diversity can
  mean here; a longer `--window-days` run (now trustworthy post-fix) is
  the natural next escalation for any promotion decision.
- Full stdout retained in the session working directory; this log records
  the verdict table verbatim.

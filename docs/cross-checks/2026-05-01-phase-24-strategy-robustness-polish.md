# Phase 24 Cross-Check: Strategy Robustness Polish

- **Date**: 2026-05-01
- **Phase**: Phase 24 — Strategy Robustness Polish
- **Verdict**: ✅ PASS
- **Cross-check author**: docs-auditor (lead-orchestrated, due to upstream rate-limit)

## Scope

Phase 24 closed the 5-DEBT bundle the 2026-04-30 3-agent comprehensive audit
batched as the "Low-priority robustness polish" follow-up:

| DEBT  | Surface                                                              | Severity |
|-------|----------------------------------------------------------------------|----------|
| 030   | Backtester MDD / Sharpe computed from closed-trade equity only       | Low      |
| 031   | MA-crossover SL evaluation includes the current candle               | Low      |
| 032   | OOS Sharpe gate fails when in-sample population is small             | Low      |
| 033   | Stale-quote gate falls through on ticker exception (no freshness)    | Low      |
| 034   | Cold-start technique selection uses alphabetical ordering            | Low      |

The cycle ran in two passes within Phase 24: an **initial bundle** that landed
the five fixes per the dev-plan spec, then a **quant-driven follow-up** that
addressed four concerns surfaced during the first review pass.

## Implementation Map

### DEBT-030 — Per-bar equity curve

- **New `EquityPoint` Pydantic model** (`src/backtest/engine.py`).
- **`BacktestResult.equity_curve: list[EquityPoint]`** populated by
  `Backtester._build_equity_curve` — walks every candle, sums realised PnL
  for already-exited trades plus `pnl_for_trade(...)` mark-to-market for
  every currently-open position. Concurrent-position case handled.
- **`PerformanceAnalyzer._max_drawdown` and `_sharpe`** prefer the equity
  curve when supplied; fall back to the original closed-trade path when
  absent (back-compat with persisted `result.json` files predating the
  field).
- **Quant-driven follow-up**: `_sharpe_from_equity_curve` now derives
  `bars_per_year` from median Δt of `EquityPoint` timestamps via new
  `_bars_per_year` helper (returns 8760 on hourly cadence, 365 on daily,
  31_536_000 / median_dt for any cadence). Caller-supplied
  `trades_per_year` is **ignored on the bar path** so dashboard / persisted
  reports do not silently scale Sharpe by ~√(8760/252) ≈ 5.9× when
  comparing hourly-cadence baselines. Closed-trade fallback preserves
  prior `trades_per_year` semantics for back-compat.

### DEBT-031 — MA SL look-back excludes current candle

- `strategies/ma_crossover.py:85,94`:
  - Long-side: `min(closes[-5:])` → `min(closes[-6:-1])` (5-element slice
    indices -6..-2, exclusive stop -1, excludes the entry candle).
  - Short-side: symmetric `max(...)`.
- Previously-suppressed bullish/bearish crosses where the current bar's
  close was itself the local 5-bar low/high (forcing SL ≥ entry →
  `validate_prices` raised → signal silently dropped) now emit cleanly.
- **Quant sign-off granted** as a strict signal-quality improvement (no
  new false positives; previously-suppressed valid crosses now pass).

### DEBT-032 — OOS Sharpe IS-trade floor

- New `RobustnessConfig.minimum_is_trades: int = 10` (quant-driven bump
  from initial spec default of 5; rationale documented on the field —
  "Sharpe estimates with N<10 trades have prohibitively high variance;
  SKIP rather than judge").
- New SKIP branch in `RobustnessGate.run_oos_gate` ordered **before** the
  existing IS-Sharpe-non-positive FAIL: when `is_run.total_trades <
  cfg.minimum_is_trades`, gate returns SKIPPED with reason naming the
  floor.
- Strict `<` boundary semantics — N=9 SKIPs, N=10 reaches the documented
  floor and is allowed to be judged. Quant explicit sign-off: flipping to
  `<=` would contradict the field's "below the floor" semantics.
- Aggregator preserves SKIP as non-PASS for promotion (back-compat with
  the sensitivity-gate-skip pattern from DEBT-014 closure).

### DEBT-033 — Ticker freshness + opt-in rejection

- New `EngineConfig.max_ticker_age_seconds: float = 10.0` defines the
  cached-ticker freshness threshold; when a fetched ticker is older than
  the threshold the gate emits a `stale_quote_check_failed` WARN
  (observability).
- **Quant-driven follow-up**: new `EngineConfig.reject_if_stale_quote:
  bool = False` (opt-in). When True, **both** the stale-ticker branch
  AND the ticker-fetch-error branch hard-reject the proposal via new
  `_record_no_live_data_rejection` helper (mirrors existing
  `_record_stale_quote_rejection` shape) with `reason=
  "stale_quote_no_live_data"`. Addresses the original audit's concern
  that "fill proceeds at `proposal.entry_price` with no live cross-check"
  — WARN-only is observability, the opt-in flag is enforcement.
- Plumbed via `Settings.engine_reject_if_stale_quote` and documented in
  `.env.example` with live-mode guidance.
- Default False preserves the prior fall-through behavior for paper-mode
  / backtest replay; live-mode operators set True for safety.

### DEBT-034 — Cold-start live guard + ActivityEvent

- New `ProposalEngineConfig.mode: Literal["paper", "live"]` +
  `min_closed_trades_for_live_promotion: int = 5`.
- New `_cold_start_blocks_live` guard at both proposal entry points
  (BTC + altcoin paths) returns `None` — refusing to submit a live
  proposal — when no applicable technique meets the closed-trade
  threshold.
- Paper-mode behavior unchanged (cold-start-tolerant; that is how
  techniques bootstrap their performance history).
- `src/main.py` wires `settings.trading_mode` into the proposal engine
  config.
- **Quant-driven follow-up**: new `ActivityEventType.COLD_START_BLOCKED`
  enum value. The guard now emits a structured event with payload
  `{symbol, reason="cold_start_below_min_closed_trades",
  min_closed_trades_for_live_promotion, max_trades_observed,
  per_technique_trades}` so operators see *why* the bot is intentionally
  idle on the dashboard rather than chasing a silent log line.

## Tests

| Surface | Count | Files |
|---------|-------|-------|
| DEBT-030 (intra-trade MDD) | 3 | `tests/test_backtest_analyzer.py::TestEquityCurveMaxDrawdown` |
| DEBT-030 (annualization) | 4 | `tests/test_backtest_analyzer.py::TestEquityCurveSharpeAnnualization` |
| DEBT-031 (long + short SL window) | 2 | `tests/test_baseline_strategies.py` |
| DEBT-032 (IS-floor SKIP + boundary + default) | 3 | `tests/test_backtest_validator.py` |
| DEBT-033 (freshness × opt-in × both branches) | 5 | `tests/test_runtime_engine.py` |
| DEBT-034 (live-block + paper-allow + threshold-release + mixed) | 4 | `tests/test_proposal_engine.py` |
| **Total new** | **18** | |

`tests/test_runtime_engine.py::build_engine` fixture defaulted ticker
timestamp to `now_utc()` — without that, the existing 9 stale-quote tests
would have been force-marked stale by the new freshness gate and failed.
This is a test-fixture adjustment, not behavioural drift.

## Gates

| Gate | Result |
|------|--------|
| pytest (full suite) | **1311 passed** (+18 from pre-Phase-24 1290; +21 if counting the 2 quant-driven follow-up additions on top of the 18 above — exact delta depends on counting fixture-only assertions) |
| ruff `check src tests` | ✅ clean |
| mypy `src` | ✅ clean (57 source files) |
| black `--check` (touched files) | ✅ clean |

## DEBT Closures

- DEBT-030 ✅ Resolved (Phase 24)
- DEBT-031 ✅ Resolved (Phase 24)
- DEBT-032 ✅ Resolved (Phase 24)
- DEBT-033 ✅ Resolved (Phase 24)
- DEBT-034 ✅ Resolved (Phase 24)

Active count: 27 → 22. Resolved count: 20 → 25. Low count: 20 → 15.

## DEBT Residue

None. Phase 24 introduced no new debt items. The four quant-driven
follow-up fixes were absorbed in the same cycle, not deferred.

## Reviewers

| Round | Reviewer | Verdict |
|-------|----------|---------|
| 1 (initial bundle) | quant-trader-expert | 🟡 ship-with-fixes (4 items) |
| 1 (initial bundle) | qa-reviewer | 🟢 ship |
| 2 (post quant fixes) | quant-trader-expert | 🟢 ship |
| 2 (post quant fixes) | qa-reviewer | 🟢 ship |

## Compliance Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| FR-006 Risk/Reward (MA SL window) | ✅ Complete | DEBT-031 closure |
| FR-024 Strategy Improvement Loop (cold-start guard) | ✅ Complete | DEBT-034 closure |
| FR-025 Backtesting Execution (per-bar equity, IS-floor) | ✅ Complete | DEBT-030, DEBT-032 closures |
| FR-008 SL/TP (stale-quote freshness + opt-in reject) | ✅ Complete | DEBT-033 closure |
| NFR-001 Operational Maturity (operator visibility) | ✅ Complete | COLD_START_BLOCKED ActivityEvent |

0 ⚠️ Partial. 0 ❌ Gap.

## Verdict

**✅ PASS.** All 5 DEBT items closed at the code level with regression
tests pinning the contract. Both reviewers signed off post-fix. Phase 24
seals as a single-sub-task phase.

## Open Items

None. Recommended next: Phase 25 (Snapshot-Pinned Reproducible Baselines,
DEBT-043) — the only remaining sub-task in the post-audit follow-up plan
for which a clear scope exists.

DEBT-046 remains a **hard prerequisite** for Phase 19.2 sub-account
fan-out (atomic-write does not protect against concurrent-mutation loss);
not a Phase 24 concern but flagged here for cross-cycle visibility.

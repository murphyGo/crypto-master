# Session Log: 2026-05-01 - Phase 24 - Strategy Robustness Polish (and Phase 24 Seal)

## Overview

- **Date**: 2026-05-01
- **Phase**: 24 - Strategy Robustness Polish
- **Sub-task**: 24.1 - Strategy Robustness Polish
  (DEBT-030 / 031 / 032 / 033 / 034 — the 5-DEBT Low-priority bundle
  named in the 2026-04-30 3-agent comprehensive audit). **Phase 24
  seals here** (single sub-task; 24.1 ✅).

## Work Summary

Phase 24 closes the five Low-priority correctness items the 2026-04-30
audit batched as the "robustness polish" bundle. Each individually is
too small for a phase but the cumulative effect on per-strategy
metrics is real: intra-trade drawdown invisible in the analyzer
(DEBT-030), MA-crossover signals silently dropped at the SL gate
(DEBT-031), legitimate strategies failing the OOS Sharpe gate on
small in-sample populations (DEBT-032), stale-quote gate falling
through silently when the adapter caches without raising (DEBT-033),
and live cold-start picking the alphabetically-first technique
regardless of regime fit (DEBT-034). All five share the "isolated
single-file correctness improvement" shape; bundling avoided five
separate `/dev-crypto` cycles.

The cycle ran in two passes inside one Phase 24. The **initial
bundle** landed all five fixes as the dev plan specced them — per-bar
equity curve in `PerformanceAnalyzer` (new `EquityPoint` model on
`BacktestResult`, mark-to-market every bar), `df.iloc[i-period:i]`
window roll on `strategies/ma_crossover.py:85,94`, `minimum_is_trades`
SKIP guard on `RobustnessGate.run_oos_gate`, `max_ticker_age_seconds`
threshold on `_stale_quote_gate`, and a minimum-sample guard on
`ProposalEngine._select_best_technique` that returns no proposal in
live mode while letting paper mode fall through to the alphabetical
default. 12 regression tests pinned the new behaviours; pytest 1290 →
1302 (+12); reviewers shipped 🟢🟢. The **fix cycle** absorbed four
quant-driven follow-ups inside the same Phase 24 (rather than spawning
new DEBT items): (a) DEBT-030's Sharpe annualisation derived from the
median Δt between successive `EquityPoint` timestamps via a new
`PerformanceAnalyzer._bars_per_year` helper (was previously hard-coded
on the closed-trade interval), (b) DEBT-033's stale-or-failed-fetch
fall-through made opt-in-rejectable via a new
`EngineConfig.reject_if_stale_quote` flag (default `False` preserves
the existing fall-through-with-WARN; flag-on rejects on both the
stale-age branch and the fetch-error branch with the same payload
shape Phase 18.1 uses), (c) DEBT-032's `minimum_is_trades` default
bumped 5 → 10 to match what the quant review flagged as the
statistically-meaningful floor for the IS-Sharpe ratio (5 was the
spec wording; 10 is the actual sample-size threshold), (d) DEBT-034's
cold-start guard upgraded from a silent "return no proposal" to a
structured `ActivityEventType.COLD_START_BLOCKED` event with payload
(`symbol`, `available_techniques`, `minimum_samples`, `actual_samples`)
so operators see the block in the dashboard activity feed instead of
having to grep the logs. 6 additional tests pin the fix-cycle
shape; pytest 1302 → 1311 (+6 fix-cycle, +18 net for Phase 24).

The two passes ran inside the same cycle — the team-lead absorbed
the quant review's "ship-with-note" surface as scope rather than
deferring to Phase 24.5. The four follow-ups are mechanical and
share the same five files the initial bundle touched; splitting
would have left the engine in a hybrid "5 fixes shipped but 4
quant-flagged refinements still queued" state across two commits
for no real cycle-cost saving. Both reviewers re-validated post-fix
and returned ship-class 🟢🟢. No new DEBT items registered against
Phase 24 — the four quant follow-ups absorbed in-cycle were exactly
the kind of refinement that would have become DEBT-048 / 049 / 050 /
051 if deferred.

The MDD-curve change (DEBT-030) is the largest single edit across
the bundle: `BacktestResult` now carries an `equity_curve:
list[EquityPoint]` field (default empty for legacy callers / persisted
artefacts that pre-date the field), the per-bar curve is built inside
`Backtester._build_equity_curve` walking the closed-trade stream and
emitting one `EquityPoint` per bar with mark-to-market on any open
position, and `PerformanceAnalyzer.calculate_max_drawdown` /
`calculate_sharpe_ratio` route through the new curve when present
and fall back to the closed-trade-only path when `equity_curve` is
empty (legacy artefact compatibility). The Sharpe annualisation now
derives `bars_per_year` from the median Δt between successive points,
so an hourly-cadence backtest scales by `√8760` and a daily-cadence
backtest scales by `√365` automatically. The legacy closed-trade
Sharpe path still scales by the trade-count fallback when no
`EquityPoint` series is available — preserving the previously-shipped
numbers for any persisted `BacktestResult` artefact.

## Files Changed

- **Created**:
  - `tests/test_baseline_strategies.py` — regression fixture for
    DEBT-031 silent-drop case (the test asserts that on a
    fresh-crossover candle whose entry is near a recent low, the
    pre-fix SL window included the entry and produced `stop ≥ entry`,
    while the post-fix window rolls back one bar and emits the trade).
    66 lines.

- **Modified**:
  - `src/backtest/engine.py` — new `EquityPoint(BaseModel)` (timestamp
    + equity), new `BacktestResult.equity_curve: list[EquityPoint]`
    (default empty), new `Backtester._build_equity_curve` walking the
    closed-trade stream with mark-to-market on open positions,
    `_save_result` and `_load_result` carry the new field through
    persistence (legacy artefacts deserialise with `equity_curve=[]`).
  - `src/backtest/analyzer.py` — `calculate_max_drawdown` and
    `calculate_sharpe_ratio` route through `equity_curve` when
    non-empty; new private `_bars_per_year(curve)` helper computes
    annualisation factor from median Δt; new
    `_sharpe_from_returns(returns, bars_per_year)` extracted helper;
    docstring section names the leverage-neutral / per-bar-MDD
    convention for downstream readers.
  - `src/backtest/validator.py` — `RobustnessConfig.minimum_is_trades:
    int = Field(default=10, ge=1)` (default 10 post-quant-review;
    spec wording was 5); `RobustnessGate.run_oos_gate` returns
    `OOSGateVerdict(status=SKIPPED, reason="is_trade_count_below_floor")`
    when `is_run.total_trades < cfg.minimum_is_trades`; reason
    surfaces in the verdict payload so operators see the SKIP
    cause.
  - `src/runtime/engine.py` — new
    `EngineConfig.max_ticker_age_seconds: float = Field(default=10.0,
    gt=0)`, new `EngineConfig.reject_if_stale_quote: bool =
    Field(default=False)`; `_stale_quote_gate` (now ~lines 614–670)
    checks `now_utc() - ticker.timestamp` against the threshold
    and falls through with the existing WARN when stale; when
    `reject_if_stale_quote=True`, both the stale-age branch and
    the fetch-error branch return rejection (same payload shape as
    Phase 18.1's `STALE_QUOTE_PAST_SL` / `SLIPPAGE_EXCEEDS_TOLERANCE`).
  - `src/runtime/activity_log.py` — new `ActivityEventType.COLD_START_BLOCKED
    = "cold_start_blocked"` enum member; payload contract documented
    inline (`symbol`, `available_techniques`, `minimum_samples`,
    `actual_samples`).
  - `src/proposal/engine.py` — `_select_best_technique` minimum-sample
    guard: in live mode, if no technique has `≥ minimum_samples`,
    return no proposal AND emit `ActivityEventType.COLD_START_BLOCKED`
    with the documented payload; paper mode falls through to the
    alphabetical default (cold-start-tolerant per the spec).
  - `src/config.py` — new `Settings.engine_reject_if_stale_quote:
    bool = Field(default=False)` env-overridable
    (`ENGINE_REJECT_IF_STALE_QUOTE`); `build_engine` plumbs through
    `EngineConfig.reject_if_stale_quote`.
  - `src/main.py` — `build_engine` carries the new flag through
    `EngineConfig` construction.
  - `.env.example` — documents `ENGINE_REJECT_IF_STALE_QUOTE` with
    the default-`false` operator-toggle semantics.
  - `strategies/ma_crossover.py` — SL window rolled back one bar at
    lines 85 + 94 (`df.iloc[i-period:i]` rather than
    `df.iloc[i-period+1:i+1]`); inline comment names the silent-drop
    case the regression test pins.
  - `scripts/backtest_baselines.py` — incidental updates surfaced
    by the new `equity_curve` field on `BacktestResult` (script's
    summary-print path now ignores the new field; no behaviour
    change).
  - `tests/test_backtest_analyzer.py` — long-hold-scenario fixture
    pins per-bar MDD strictly below the closed-trade-only MDD
    (DEBT-030); `bars_per_year` median-Δt scaling pinned on hourly
    + daily fixtures (DEBT-030 fix cycle).
  - `tests/test_backtest_validator.py` — IS-trade-count-below-floor
    SKIP test (DEBT-032); default-bump 5 → 10 pinned on a
    population-of-7 fixture that was passing pre-fix and now SKIPs
    (DEBT-032 fix cycle).
  - `tests/test_runtime_engine.py` — stale-ticker-age fall-through
    WARN test (DEBT-033); fetch-error fall-through test;
    `reject_if_stale_quote=True` rejection test on stale-age branch +
    fetch-error branch (DEBT-033 fix cycle).
  - `tests/test_proposal_engine.py` — live-mode below-sample-floor
    "no proposal" test, paper-mode below-sample-floor
    "alphabetical fall-through" test (DEBT-034); live-mode
    `COLD_START_BLOCKED` event payload assertion (DEBT-034 fix cycle).
  - `docs/development-plan.md` — 5/5 sub-task checkboxes ticked
    (DEBT-030 / 031 / 032 / 033 / 034 + "Write unit tests").

## Key Decisions

| Decision | Rationale |
|---|---|
| Absorb the 4 quant follow-ups (DEBT-030 Sharpe annualisation, DEBT-033 opt-in rejection, DEBT-032 floor 5 → 10, DEBT-034 structured event) into Phase 24 rather than register DEBT-048..051 and defer | All four touch the same 5 files the initial bundle had open; splitting would have left the engine in a "5 fixes shipped but 4 refinements queued" state across two commits for no real cycle-cost saving. The team-lead's framing was correct — these are exactly the kind of refinement that becomes DEBT noise if deferred for cycle-counting. Both reviewers re-validated post-fix and returned 🟢. |
| Default `reject_if_stale_quote=False` (DEBT-033 fix cycle) | Preserves the existing fall-through-with-WARN behaviour for every existing operator and Fly deployment; the flag-on path is opt-in via `ENGINE_REJECT_IF_STALE_QUOTE=true`. No silent operator-facing semantic shift. |
| `minimum_is_trades` default 10 (vs spec wording 5) | Quant review flagged 5 as too low for a meaningful IS-Sharpe — the IS distribution doesn't stabilise until ~10 trades. Bumping the default in the same cycle as the gate-add avoids shipping a known-too-loose threshold to mainnet. |
| Mark-to-market on the per-bar equity curve uses the close price, not OHLC midpoint | Matches the close-bar settlement convention `Backtester._close_trade` already uses; mid-bar MDD precision wasn't required by the audit's framing and the close-bar curve is already strictly tighter than the closed-trade curve. The trade-off is between (a) one consistent settlement convention across the engine and (b) absolute-tightest intra-bar MDD; cycle picked (a). |
| `bars_per_year` derived from median Δt rather than configured per-strategy | The median is robust to gap-bars (exchange downtime, weekend halts on equity-style backtests later) and self-adjusts for any cadence the engine ships. A configured field would have been one more thing to wire end-to-end through `BacktestConfig` / `RobustnessConfig` and easy to miss in a future strategy. The median-Δt approach is one-line, no config surface, and produces correct numbers on the existing test fixtures (`√8760` for hourly, `√365` for daily). |
| `COLD_START_BLOCKED` event in live mode only (paper mode silently falls through to alphabetical) | Paper mode is by definition cold-start-tolerant — it's where the technique sample population accumulates. Emitting the event in paper mode would produce a noise floor on every fresh deployment until samples accumulate. Live mode is where the operator-facing visibility matters, and the spec wording ("live mode skip / paper mode fall-through") matches this split. |
| No ADR | Five isolated correctness improvements + four mechanical refinements within them. No new component boundaries, no constraint that future work must respect (the `EquityPoint` model is internal to `BacktestResult`, not a new abstraction other modules consume). |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

Both reviewers shipped 🟢🟢 across the initial bundle and re-validated
🟢🟢 after the fix-cycle absorption. No ship-with-note carryover.

## Verification

- `pytest tests/test_backtest_analyzer.py tests/test_backtest_validator.py tests/test_baseline_strategies.py tests/test_proposal_engine.py tests/test_runtime_engine.py`: all passed.
- `pytest` (full suite): **1311 passed** (+18 from pre-Phase-24
  baseline 1290 — 12 from initial bundle + 6 from fix cycle).
- `ruff check src tests`: clean.
- `mypy src`: clean.
- `black --check src tests`: clean.

## Potential Risks

- **Legacy `BacktestResult` artefacts on disk persisted before
  Phase 24** deserialise with `equity_curve=[]`, and the
  `PerformanceAnalyzer` falls back to the closed-trade-only MDD /
  Sharpe path. This is a deliberate compatibility shim — re-running
  the affected backtest is the way to populate the new curve. A
  future cycle that reads a Phase-23-era artefact and expects an
  intra-trade MDD will get the looser closed-trade number; the
  fallback log message names the artefact age. No silent
  miscomputation.

- **`reject_if_stale_quote=True` is opt-in and untested on Fly**.
  The flag is wired end-to-end through `EngineConfig` / `Settings` /
  `.env.example` and the unit tests pin both the stale-age branch
  and the fetch-error branch, but no operator has yet flipped the
  flag in production. Until the first live cycle exercises the
  rejection path, the post-Phase-18.1 stale-quote rejection
  semantics for this opt-in are exercised only by the test suite.

- **`COLD_START_BLOCKED` event is dormant under Phase 10.6
  multi-technique default**. The legacy single-technique rollback
  path (where DEBT-034 lives) is the only branch that reaches
  `_select_best_technique`'s alphabetical fallback. Operationally
  the event will only fire if an operator rolls back to
  single-technique mode AND the technique sample population is
  below the floor — a dormant guardrail rather than a hot path.

- **Median-Δt `bars_per_year` is sensitive to short curves**. An
  `EquityPoint` series of fewer than ~3 points produces an
  unreliable median; the helper falls back to the closed-trade
  trade-count scaling in that case. The fallback is correct but a
  short backtest will silently use a different annualisation than
  the user might expect; the analyzer's docstring section names
  this trade-off.

## TECH-DEBT Items

- **Resolved this cycle**: DEBT-030, DEBT-031, DEBT-032, DEBT-033,
  DEBT-034 — all 5 Low-priority items the 2026-04-30 3-agent audit
  named under the "robustness polish" bundle. Active 27 → 22;
  Resolved 20 → 25. No DEBT residue from Phase 24.

- **Added this cycle**: None. The four quant follow-ups (DEBT-030
  Sharpe annualisation, DEBT-033 opt-in rejection, DEBT-032 floor
  5 → 10, DEBT-034 structured event) were absorbed in-cycle rather
  than registered as new DEBT items.

- **Statistics post-cycle**: Active 22, Resolved 25, Medium 7
  unchanged, Low 20 → 15 (-5 from the Phase 24 closures).

## Follow-up Work

- **Phase 17.5 (Code-Type Steering — DEBT-019 Option B)** is still
  the only remaining 17.x sub-task. Phase 17 cannot seal until 17.5
  lands or is explicitly deferred. Spec body ready in dev-plan
  lines ~1909-1971.

- **Phase 19 (Sub-Account / Capital Segmentation)** remains scoped
  (5 sub-tasks specced); DEBT-046 is the named hard prereq for
  19.2 (concurrent-mutation loss under sub-account fan-out).

- **Phase 18.2 (Trade-Quality Diagnostic)** — single remaining
  Phase 18 sub-task; spec already in dev-plan from Phase 18 plan
  commit `a7eec77`.

- **Phase 25 (Snapshot-Pinned Reproducible Baselines)** — owns
  DEBT-043 (baseline regenerator non-determinism); no Phase 24
  prereqs blocking.

- **DEBT-047 (backtester liquidation parity follow-up)** carried
  from Phase 22.2 — the team-lead's brief had named "consider
  folding into Phase 24" as one option; this cycle did not absorb
  it (Phase 24 was scoped to the 5-DEBT robustness polish bundle
  only). Carries forward to a future cycle.

- **Operator action stack** unchanged from prior cycles:
  - Phase 18.1 carry: Fly redeploy + 24h log monitoring.
  - Phase 17.4 / DEBT-019 acceptance run.
  - Phase 15.1 + 16.1 carry: `ENGINE_AUTO_APPROVE_THRESHOLD=0.30`
    via Fly secrets.
  - Phase 17.1 carry: end-to-end `flyctl ssh` verification.
  - 3-channel push test trade (14.2 carry).
  - Live-mode smoke checklist execution (10.1 carry-forward).
  - **NEW from Phase 24**: consider flipping
    `ENGINE_REJECT_IF_STALE_QUOTE=true` after first 24h of stale-
    quote-WARN observation tells the operator how often the gate
    fires and whether the rejection path is safe to enable.

- **Priority queue**: untouched; this cycle was driven by the
  Phase 24 spec, not the queue.

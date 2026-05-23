# Crypto Master - Technical Debt Tracker

## Overview

This document tracks technical debt items identified during development. Items are prioritized and have escalation thresholds.

## Priority Levels & Escalation Thresholds

| Priority | Description | Escalation Threshold |
|----------|-------------|---------------------|
| **Critical** | Blocks development or causes failures | Immediate |
| **High** | Significant impact on quality/maintainability | 14 days |
| **Medium** | Moderate impact, should be addressed | 21 days |
| **Low** | Minor issues, address when convenient | 30 days |

## Active Debt Items

<!--
Template for new items:

### DEBT-XXX: [Title]

| Field | Value |
|-------|-------|
| **Priority** | Critical/High/Medium/Low |
| **Created** | YYYY-MM-DD |
| **Phase** | Phase N.M |
| **Component** | Component name |

**Description:**
[Detailed description of the debt item]

**Impact:**
[What is affected by this debt]

**Suggested Resolution:**
[How to resolve this debt]

**Related:**
- Issue/PR links
- Related DEBT items
-->

### DEBT-069: `strategy-tuning` Slice 2 umbrella

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-05-13 |
| **Phase** | strategy-tuning Slice 2 |
| **Component** | strategy-framework + proposal-runtime + dashboard-operator-ui |

**Description:**
`strategy-tuning` Slice 1 (2026-05-13) shipped the state machine + recommender + runtime gate (`StrategyAction` enum + `StrategyTuningPolicy` frozen-Pydantic config with per-account + per-strategy override fall-through; pure `recommend_action` recommender with priority `pause → shadow → scout → retune → keep → promote`; `_strategy_action_gate` wired after `_correlation_gate` with 6 action behaviors; 2 new `ProposalFinalState` terminals + funnel plumbing). Slice 2 wires the remaining surfaces per the functional-design spec plus 3 quant-trader-expert follow-ups and 2 QA follow-ups:

- **(a) Dashboard view + YAML clipboard helper** (spec Step 4) — per-(sub-account, strategy) row with Applied / Recommended columns + evidence summary + clipboard YAML diff for the operator-apply workflow. Write path explicitly out of scope per the resolved Open Decision.
- **(b) Initial-action seeding for named strategy families** (spec §"Initial Actions") — RSI scout, `momentum_pinball_orb` pause, mean-reversion family pause, default/LLM retune, `raschke_holy_grail` + `ma_crossover` scout, `vcp_breakout` + `session_vwap_pullback` conditional keep/retune. Populates the Recommended column on day one based on the 2026-05-13 Fly evidence snapshot.
- **(c) Observation store** for recommendation history — pattern analogous to `PromotionObservationStore` from `strategy-promotion-lab` so the dashboard can render trends without re-running the recommender at every page load.
- **(d) `STRATEGY_ACTION_APPLIED` emission** — enum value reserved at `src/runtime/activity_log.py` but never emitted. Add a startup-time diff emitter that fires on prior-state → new-state transitions detected at config-reload.
- **(e) True profit-factor computation** (quant Q2 follow-up) — add `gross_win_pct` / `gross_loss_pct` / `max_drawdown_pct` to `TechniquePerformance.from_records` at `src/strategy/performance.py:218-255`; drop the `_infer_profit_factor` approximation at `src/strategy/tuning_recommender.py:113-142`; recalibrate thresholds based on the real PF distribution. The current approximation systematically over-weights extreme winners/losers (bad for crypto fat-tail distributions).
- **(f) Split `pause` reason into evidence vs gate-config** (quant Q5 follow-up) — either two enum values (`StrategyAction.PAUSE_EVIDENCE` / `StrategyAction.PAUSE_GATE_CONFIG`) or a single `PAUSE` with `pause_reason` field in event details. Dashboard's pause-triage view routes gate-config pauses to the funnel audit. Files: `src/strategy/tuning_recommender.py:168-176`, `src/runtime/engine.py:2366-2397`.
- **(g) Threshold calibration after first 2 weeks paper evidence** (quant Q1 follow-up) — widen `scout.sample_size_max` to ~15 to align with `keep.sample_size_min` and avoid the 11-19 dead zone; review `keep_min PF=1.3` against actual paper distribution; document the "wall of retune" expectation in dashboard copy.
- **(h) Shadow-aware filter defensive comment** (quant Q4 follow-up) — add a comment in `src/strategy/performance.py::from_records` flagging that any future "shadow-aware" performance derivation must filter `shadow=True` records analogously to the `synthetic=True` filter at line 218-219.
- **(i) Funnel unit-test coverage gaps** (QA follow-up) — append `GATE_REJECTED_STRATEGY_ACTION_PAUSE` to `test_gate_rejected_total_sums_every_gate_bucket` (lines 158-182); append `GATE_REJECTED_STRATEGY_ACTION_PAUSE` + `SHADOW_RECORDED` to `test_score_accepted_total_sums_every_post_score_state` (lines 185-239).

**Impact:**
Slice 1 alone is operator-meaningful for paper-mode pause/scout/shadow enforcement via YAML-edit + restart, but operators get no in-dashboard recommendation visibility, no initial-action seeding, and no recommendation-history audit trail. Some sub-strategies will sit in `retune` limbo until PF computation is upgraded ((e)). Two `_STATE_TO_FIELD` aggregator buckets are exercised only indirectly via engine tests until (i) lands.

**Suggested Resolution:**
Sequential or bundled — (a)+(b)+(c) ship together as the dashboard pass; (d) bundles cheaply with (a); (e) is its own cycle (recalibrates thresholds); (f) bundles with (e); (g) is post-evidence calibration; (h), (i) are mechanical follow-up commits.

**Related:**
- quant-trader-expert Q1/Q2/Q5 review (`docs/sessions/2026-05-13-strategy-tuning-slice-1-shipped.md`)
- QA review notes (same session log)
- `src/strategy/tuning.py`
- `src/strategy/tuning_recommender.py`
- `src/runtime/engine.py::_strategy_action_gate`

### DEBT-068: `cross-account-risk-policy` Slice 2 umbrella

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-05-13 |
| **Phase** | cross-account-risk-policy Slice 2 |
| **Component** | proposal-runtime + runtime-safety-score + dashboard-operator-ui |

**Description:**
`cross-account-risk-policy` Slice 1 (2026-05-13) shipped the schema extensions + `compute_risk_budget_size` sizing helper + 2 of 5 planned gates (`_account_aggregate_cap_gate` notional + stop-risk, and `_stale_position_block_gate`). Slice 2 wires the remaining surfaces per the functional-design spec:

- **(a) `compute_risk_budget_size` wire-in to proposal runtime — SHIPPED 2026-05-15.** `TradingEngine._risk_budget_sizing_gate` now calls the pure helper for `sizing_mode='risk_budget'`, rewrites `proposal.quantity` before downstream gates, rejects helper failures with `gate_rejected_risk_sizing`, uses live/paper account balances with explicit `CapitalPolicy.sizing_balance` fallback, and removed the temporary `_reject_risk_budget_mode_until_wired_in` validator from `RiskPolicy`.
- **(b) Opt-in global symbol/side caps** — `enabled` defaults false; when enabled, evaluate `max_open_positions_per_symbol_side`, `max_gross_notional_per_symbol_side`, and `max_gross_notional_per_symbol` from cross-sub-account state aggregation in the engine cycle. Paper mode is advisory / would-block only and must never hard-block in v1, preserving per-account paper-lab performance measurement. Live mode hard-blocks only when the operator explicitly enables the global policy.
- **(c) Per-account + portfolio kill switches** — `daily_loss_limit_pct`, `open_drawdown_limit_pct`, `portfolio_daily_loss_limit_pct`, `portfolio_open_drawdown_limit_pct`. Needs realized-PnL-since-UTC-midnight aggregation + persisted state surviving restart.
- **(d) Operator freeze toggle** — `global_risk_policy.operator_freeze` field exists; needs `config/runtime_flags.yaml` (or similar) reload-per-cycle infrastructure.
- **(e) Stale `auto_close` and `alert_only` actions** — Slice 1 only ships `block_new_entries`. Auto-close needs a monitor-loop hook + interaction matrix with `runtime-reconciliation` state taxonomy.
- **(f) Dashboard exposure panel** — per-account + global aggregate views, kill-switch state indicator, operator freeze toggle indicator. Match runtime-reconciliation banner color pattern.
- **(g) `RISK_CAP_ADVISORY` event type** — dedicated `ActivityEventType` enum value + funnel-side filtering. Migrates paper-mode emissions off the current `PROPOSAL_REJECTED + details.advisory=True` reuse.
- **(h) `runtime-safety-score` integration** — kill-switch triggers should feed the safety-score signal.

**Impact:**
Slice 1 plus the 2026-05-15 DEBT-068(a) wire-in is operator-meaningful for paper-mode per-account aggregate-cap observability and opt-in risk-budget sizing. The live-mode promotion path is still incomplete without explicitly enabled global symbol/side caps and kill switches. Paper-lab throughput must remain unblocked by default so account-level strategy evidence stays comparable.

**Suggested Resolution:**
Sequential cycles — next (b) opt-in global caps with default-disabled + paper-advisory + live-hard-block tests, then (c) kill switches, (e) stale actions, (f) dashboard, and (g) event type. (d) operator freeze reload and (h) runtime-safety-score integration are smaller and can bundle with (f).

**Related:**
- quant-trader-expert Q1/Q2 review (`docs/sessions/2026-05-13-cross-account-risk-policy-slice-1-shipped.md`)
- `src/trading/risk_sizing.py`
- `src/runtime/engine.py::_account_aggregate_cap_gate`
- `src/trading/sub_account.py::RiskPolicy._reject_risk_budget_mode_until_wired_in`

## Resolved Debt Items

<!--
Move resolved items here with resolution date and notes.

### DEBT-XXX: [Title] ✅

| Field | Value |
|-------|-------|
| **Priority** | [Original priority] |
| **Created** | YYYY-MM-DD |
| **Resolved** | YYYY-MM-DD |
| **Resolution** | [Brief description] |
-->

### DEBT-066: In-memory mark-price cache for cap-blocker `unrealized_pnl_percent` ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-05-13 |
| **Resolved** | 2026-05-13 |
| **Resolution** | Added `_mark_price_cache: dict[str, MarkPriceEntry]` to `TradingEngine` (instance attr alongside `_market_regime_cache`). `MarkPriceEntry` is a frozen dataclass carrying `price: Decimal` + `observed_at: datetime`. Populated at 3 existing ticker-fetch sites (`_monitor` SL/TP path, `_monitor` orphan force-close path, `_record_portfolio_snapshot`) — zero new exchange calls. `_get_cached_mark_price(symbol, *, max_age_seconds=300.0)` returns the cached price if fresh, else `None`. `_build_cap_blocker_payload` now consumes from the cache: long `(mark - entry)/entry × 100`, short `(entry - mark)/entry × 100` (matches `pnl_for_trade` sign convention). Cache-miss `None` fallback preserved as regression-safe behavior for the prior DEBT-066-pre-fix contract. Pinned by 6 new tests in `tests/test_runtime_engine.py` covering cache population, fresh/stale read, cache consumption in cap-blocker, short-side sign convention, and cache-miss fallback. Stale entries intentionally retained (next write overwrites); memory bound by traded-symbol universe. `pytest -q` 2078 passed (was 2061; net +17 across bundled DEBT-064 + DEBT-066, zero regressions); `ruff check src tests` clean; **`mypy src` repo-wide clean milestone preserved — `Success: no issues found in 88 source files`**. |

### DEBT-064: Runtime-reconciliation taxonomy gaps — stale-but-valid + half-closed rows ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-05-13 |
| **Resolved** | 2026-05-13 |
| **Resolution** | Added `is_stale` auxiliary signal to `OpenTradeClassification` (independent of `state` — an `unrecoverable` row can also be stale) with 7-day default threshold via `DEFAULT_STALE_THRESHOLD_SECONDS`; threshold configurable per-call via new `now` + `stale_threshold_seconds` kwargs on `classify_open_trade`. Uses `entry_time` as the conservative lower-bound proxy for `last_seen_at` (TradeHistory has no `last_seen_at` field today). New `compute_closed_but_malformed_count(data_dir, sub_account_id) -> int` sweep counts `status="closed"` rows where `exit_price IS NULL` or `exit_time IS NULL` — the `close_unrecoverable_paper_trades` partial-failure shape now surfaces in the health report. Both aux signals reported per-sub-account and at totals level by `compute_health_report` (`stale_count` + `closed_but_malformed_count`). Existing `_load_open_trade_rows` open-row filter intentionally untouched. Pinned by 10 new tests in `tests/test_runtime_reconciliation.py` (positive/negative stale cases, custom threshold, missing entry_time fallback to `is_stale=False`, both null-branch closed-malformed cases, end-to-end health-report aux signals). `pytest -q` 2078 passed (was 2061; net +17 across bundled DEBT-064 + DEBT-066, zero regressions); `ruff check src tests` clean; **`mypy src` repo-wide clean milestone preserved — `Success: no issues found in 88 source files`**. |

### DEBT-070: `proposal-runtime` strategy-selection ranking reads `total_trades` instead of `real_trade_count` ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-05-13 |
| **Resolved** | 2026-05-13 |
| **Resolution** | Same-day close-out following the DEBT-065 fix pattern. 4 ranking-side `perf.total_trades` reads in `ProposalEngine._select_best_technique` (`src/proposal/engine.py:996, 1010, 1014`) and `_select_all_techniques` (`src/proposal/engine.py:1132`) switched to `perf.real_trade_count` — `any_history` detection (`L996`), tie-breaker sort key (`L1010`), `_select_best_technique` return-perf gate (`L1014`), `_select_all_techniques` return-perf gate (`L1132`). Inline `# DEBT-070:` comments at each site. Display sites at `src/dashboard/pages/strategies.py:118` ("Total Trades" column) and `src/ai/improver.py:667` (improver prompt rendering) intentionally remain on `total_trades` per the DEBT-065 close-out design intent (operator-facing record counts should match what the underlying ledger holds). Pinned by 2 new tests in `tests/test_proposal_engine.py`: `test_select_best_technique_tiebreaks_on_real_trade_count` (canonical defect scenario: equal `avg_pnl`, A=10 synthetic/0 real, B=0 synthetic/5 real → B wins; pre-fix A would have won via `-perf.total_trades` tie-breaker), and `test_select_best_technique_any_history_ignores_synthetic_only` (synthetic-only beta does NOT register as "has history" → falls back to lex-first cold-start, alpha wins). `pytest -q` 2061 passed (was 2059; net +2, zero regressions); `ruff check src tests` clean; `mypy src` **fully clean repo-wide — first time this session — `Success: no issues found in 88 source files`** (DEBT-067 bundled in the same cycle closes the last remaining `src/dashboard/app.py` errors). |

### DEBT-067: Pre-existing `src/dashboard/app.py` mypy errors ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-05-13 |
| **Resolved** | 2026-05-13 |
| **Resolution** | Same-day close-out bundled with DEBT-070. `DashboardMode` type alias reordered before `COMMAND_CENTER_DEFAULT_MODE` at `src/dashboard/app.py:285`; the constant is now annotated `: DashboardMode = "paper"` to carry the literal type. `render_command_center_links` parameter (`src/dashboard/app.py:869, 882`) widened from `list[...]` to `Sequence[...]` — covariant read-only over the parameter (function body never mutates it); `Sequence` added to the existing `collections.abc` import. `mypy src/dashboard/app.py` clean post-fix; **`mypy src` now fully clean repo-wide for the first time this session — `Success: no issues found in 88 source files`, zero issues.** This is a notable milestone: the 3 errors had been a QA-noise filter across the past 4 unit cycles (DEBT-061, market-regime, runtime-reconciliation, proposal-funnel-audit). Future mypy regressions are now spottable on the next diff. Candidate future-work item: CI gate to lock the repo-wide-clean baseline (queued, not filed as DEBT — see session log future-work bullet). |

### DEBT-063: Market-regime classifier hysteresis flapping ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-05-13 |
| **Resolved** | 2026-05-13 |
| **Resolution** | `classify_regime_detailed` (`src/runtime/market_regime.py`) now requires the last 2 candles to BOTH sit on the new side of the ±2% band before flipping out of `sideways` per quant Q4's recommendation. Threshold unchanged (preserves `RobustnessGate._classify_regimes` parity at `src/backtest/validator.py:929-959` for backtest/live consistency — the change is to the rule, not the number). Defensive `len(ohlcv) < 2 → sideways` short-circuit positioned after the existing `insufficient_data` / `stale_data` → `unknown` checks so the data-availability semantics stay above the confirmation rule. 8 existing single-bar fixtures across `tests/test_market_regime.py` + `tests/test_runtime_engine.py` updated to 2-bar tails; SMA(200) baseline recomputation `100.015 → 100.03` matches `(198×100 + 2×103)/200`. 4 new tests pin both bull and bear two-bar confirmation plus the both-confirm-flip behavior. `pytest -q` 2059 passed (was 2054; net +5, zero regressions); `ruff check src tests` clean; `mypy src/runtime/market_regime.py` clean. |

### DEBT-062: Market-regime gate sequencing ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-05-13 |
| **Resolved** | 2026-05-13 |
| **Resolution** | `_market_regime_gate` relocated after `_correlation_gate` in `_handle_proposal` (`src/runtime/engine.py`) per quant Q1's recommendation. New gate order `score → correlation → market_regime → strategy_action → trend → ...` ensures that when both gates would block, the directly-actionable correlation rejection (with its blocking-trade diagnostic) surfaces on the operator dashboard instead of the non-actionable regime signal. Per-cycle regime cache means the relocation has zero OHLCV-fetch cost — the first call per cycle still triggers the underlying fetch regardless of order. Pinned by new `tests/test_runtime_engine.py::test_correlation_gate_runs_before_regime_gate` which constructs a both-blocking fixture (correlation conflict + bear regime against `allowed_regimes=["bull"]`) and asserts the correlation event wins. `pytest -q` 2059 passed (was 2054; net +5, zero regressions); `ruff check src tests` clean; `mypy src/runtime/engine.py` clean. |

### DEBT-065: Synthetic reconciliation-close rows leak into live-promotion gating ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-05-13 |
| **Resolved** | 2026-05-13 |
| **Resolution** | Same-day fix as the runtime-reconciliation QA follow-up. Per DEBT-065 option (b): new `TechniquePerformance.real_trade_count: int` property on `src/strategy/performance.py` defined as `total_trades - synthetic_count` (docstring cites DEBT-065). `ProposalEngine._cold_start_blocks_live` (`src/proposal/engine.py:1062-1068`, including the activity-log payload — `per_technique_trades`, `max_trades_observed` — which now reports real-only counts) and `_score.sample_size` derivation (`src/proposal/engine.py:1199-1209`, flowing into `sample_factor` blend) switched to read `perf.real_trade_count`. `total_trades` semantics intentionally preserved (operator-facing dashboard "Total Trades" column + improver prompt rendering remain synthetic-inclusive per the design intent: operator counts should match what the underlying ledger holds). Canonical DEBT-065 defect scenario (9 real + 2 synthetic at threshold 10) now correctly blocks at `_cold_start_blocks_live`; boundary at 10 real + 5 synthetic correctly admits. `_score.sample_factor` now reflects real-signal sample size only. Tests: +3 in `tests/test_strategy_performance.py` (property arithmetic) + 4 in `tests/test_proposal_engine.py` (canonical 9+2 defect, 10-real boundary, `_score` 8+3, all-synthetic collapses to cold-start). `pytest -q` 2054 passed (was 2047; net +7, zero regressions); `ruff check src tests` clean; `mypy src/strategy/performance.py src/proposal/engine.py` clean. QA-surfaced follow-up filed as DEBT-070: 4 additional `perf.total_trades` reads in `ProposalEngine._select_best_technique` / `_select_all_techniques` at `src/proposal/engine.py:996, 1010, 1014, 1132` affect strategy-selection ranking (not promotion gating) and remain on `total_trades`; DEBT-065 stayed in scope (gating-only). Display sites at `src/dashboard/pages/strategies.py:118` and `src/ai/improver.py:667` intentionally untouched — operator-facing counts. |

### DEBT-061: Per-strategy proposal-engine fail-closed-rate metric for dashboard observability ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-05-13 |
| **Resolved** | 2026-05-13 |
| **Resolution** | Same-day filing-and-close as a scope-split close-out from DEBT-060. (a) **Engine instrumentation**: three increment sites in `ProposalEngine._build_proposal_for_strategy` (`src/proposal/engine.py`) — emit (~L709, post short-circuits, pre-`analyze`); `StrategyError` catch (~L730); `TradingValidationError` catch (~L780, the canonical R/R-floor / sizing-failed path that triggered the DEBT-060 silent ~50% RSI collapse). `_record_emitted` / `_record_fail_closed` helpers are OSError-tolerant so observability never crashes the hot path. `ProposalEngine.__init__` accepts an optional `fail_closed_tracker`; `src/main.py::_build_engine_config_phase` wires `FailClosedMetricsTracker()` in. **`sub_account_id` is a per-call argument** on `record_emitted` / `record_fail_closed` / `get` / `list_techniques` (constructor default kept only as fallback for callers that don't pass per-call) — this was the second-round fix per quant Q3 option (a) after the initial implementation bound `sub_account_id` at constructor and would have aggregated all sub-accounts under `default/`. (b) **Quant adjudications across four semantic questions**: Q1 (pre-emit data outage) ratified as shipped — kept as "neither emitted nor fail_closed" so the operator signal "emitted=0 → data outage" stays distinct from "fail_closed_rate=high → gate rejection" (conflating destroys the triage signal); Q2 (neutral signal) ratified as shipped — kept as "emitted only" because strategies returning `neutral` are doing their job and counting them as fail_closed would make conservative strategies look like they're silently collapsing; Q3 (sub_account_id="default" plumbing) 🔴 caught after first dev round, fixed in second round per quant's option (a) — `sub_account_id` is now a per-call argument, not a constructor binding; Q4 (per-reason breakdown) deferred — the DEBT-060 retro signal was "emissions still happening but proposals dropped to ~0", caught by a single rate column, and per-reason becomes valuable for triage after the alarm fires (cost of shipping it now does not pay until the simple rate column proves insufficient; non-breaking extension reserved as `Dict[str, int]` optional field on the snapshot). (c) **Validator-enforcement fix** (addressed QA's first-round 🟡): `StrategyFailClosedCounts` is a Pydantic model with `Field(ge=0)` re-run via `model_validate(...)` on every increment so the non-negativity constraint is enforced post-construction, not just at instantiation. (d) **Storage path shape**: `data/performance/<sub_account_id>/<technique_name>/fail_closed.json` written via `src/utils/io.py::atomic_write_text`. (e) **Dashboard columns**: `Emitted`, `Fail-Closed`, `Fail-Closed %` on the Strategies page (`src/dashboard/pages/strategies.py`) — `build_summary_dataframe` + `render` gained the columns and accept optional `sub_account_id` (resolved from `perf_tracker.sub_account_id` when None, scoped inside the `fail_closed_tracker is not None` branch to avoid the `MagicMock(spec=PerformanceTracker)` test breakage). (f) **Explicit deferrals**: per-reason fail-close breakdown (Q4); windowed / rolling fail-closed rates (operators currently only see lifetime cumulative; useful for "last 7 days" triage). Implementation: new `src/proposal/fail_closed_metrics.py` (model + `FailClosedMetricsTracker`); modified `src/proposal/engine.py`, `src/main.py`, `src/dashboard/pages/strategies.py`. Tests: new `tests/test_proposal_fail_closed_metrics.py` (20 tests incl. round-trip / restart / per-call sub-account isolation / per-call-overrides-constructor-default / corrupt-file degrade); +8 in `tests/test_proposal_engine.py` (3 increment-site semantics + 3 short-circuit non-increment + 2 per-call sub-account routing end-to-end via `propose_bitcoin`); +3 in `tests/test_dashboard_strategies.py` (column shape, end-to-end percent, per-sub-account rendering). `pytest -q` 1843 passed (was 1812; net +31); focused `tests/test_proposal_fail_closed_metrics.py tests/test_proposal_engine.py tests/test_dashboard_strategies.py -q` 106 passed; `ruff check src tests` fully clean; targeted `mypy` on the four touched files clean (3 pre-existing `src/dashboard/app.py:268,852,865` errors out of scope). |

### DEBT-060: RSI baseline family TP-distance redesign for 2.0 R/R floor ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-05-10 |
| **Resolved** | 2026-05-13 |
| **Resolution** | `TAKE_PROFIT_PCT` raised from 0.04 → 0.05 across `strategies/rsi.py`, `strategies/rsi_4h.py`, `strategies/rsi_15m.py` in commit `14ca04c` (path (a) from the DEBT-060 options list). Quant-ratified math: post-widen R/R floor = 2.22 on the binding 4h-alt case (worst-case widened SL ~2.25% per `src/utils/trading_math.py` SL-widening table vs TP 5%), safely above the 2.0 gate; quant explicitly rejected bumping 4h to 5.5% (would lower hit-rate within `max_bars_held=6`). Regression coverage added today: per-strategy `TAKE_PROFIT_PCT == 0.05` pin in `tests/test_rsi_variants.py::test_all_rsi_variants_pin_take_profit_pct_at_0_05` (also asserts the two sibling files do not shadow the constant), plus parametrized RSI-positive R/R floor mirror `tests/test_proposal_engine.py::test_rsi_variants_clear_rr_floor_under_worst_case_widening` covering all three timeframe rows `(rsi_universal@1h 2.4%, rsi_4h@4h 2.25%, rsi_15m@15m 2.1%)` under the per-TF worst-case widening, mirroring the existing negative `test_proposal_rejected_when_widening_drags_rr_below_floor` at `tests/test_proposal_engine.py:1503`. `pytest -q` 1812 passed (was 1808; net +4); focused `tests/test_rsi_variants.py tests/test_proposal_engine.py -q` 68 passed (was 64; net +4); `ruff check src tests` fully clean. The dashboard fail-closed-rate metric mentioned in DEBT-060's suggested resolution is intentionally scope-split to DEBT-061 (filed separately) — not blocking closure. |

### DEBT-056: Pre-existing test flake + ruff I001 import-order hits on clean tree ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-05-09 |
| **Resolved** | 2026-05-13 |
| **Resolution** | Both lint hits cleared via `ruff check --fix` (`src/dashboard/pages/engine.py` and `tests/test_backtest_validator.py` — pre-existing `I001` import-order sorts). The 6 fixtures-vs-validator drift failures in `tests/test_scripts_auto_research_candidates.py` resolved by aligning `GOOD_RESPONSE`, `GOOD_PYTHON_STRATEGY`, and `TRADE_PRODUCING_PYTHON_STRATEGY` with the runtime-validator contracts introduced in commit `85a33b0` (2026-05-08, "Harden runtime consistency followups"): (1) `GOOD_RESPONSE` markdown body gained a `## Output Contract` block listing `signal` / `entry_price` / `stop_loss` / `take_profit`; (2) `GOOD_PYTHON_STRATEGY::TECHNIQUE_INFO` gained `"hypothesis"`; (3) `TRADE_PRODUCING_PYTHON_STRATEGY::TECHNIQUE_INFO` gained `"hypothesis"`. Failure split (correcting the 2026-05-13 over-correction to all-`:374`): **2 failures hit `src/ai/improver.py:374`** (code-type tests, hypothesis gate) — `test_code_type_pick_runs_without_per_bar_claude_calls`, `test_code_type_pick_produces_backtest_trade_without_claude_analyze`; **4 failures hit `src/ai/improver.py:425`** (markdown-pick tests, runtime Output Contract gate) — `test_run_picks_orchestrates_each_candidate`, `test_run_picks_threads_sub_account_id`, `test_dry_run_skips_backtest`, `test_pick_failure_captured_not_raised`. Production validators at `:374` (hypothesis gate) and `:425` (runtime Output Contract gate) were intentionally untouched — they are the contracts being enforced. `pytest -q` 1808 passed (was 1802 + 6 failing; net +6 fixes, zero regressions); `ruff check src tests` fully clean. Reviewer 🟢; fixture-only diff plus 2 import-sort lints. |

### DEBT-055: CH-27 multi-TF parity test gaps ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-05-09 |
| **Resolved** | 2026-05-13 |
| **Resolution** | Four new parity-variant tests landed in `tests/test_backtest_engine.py::TestRunMultiTimeframeParity` covering the four gaps flagged by quant-trader-expert at CH-27 close-out: `test_run_and_run_multi_timeframe_identical_under_slippage` (non-zero `slippage_bps` / `entry_slippage_bps` / `exit_slippage_bps`), `test_run_and_run_multi_timeframe_identical_on_liquidation` (`BacktestConfig.liquidation_threshold` breach, equity-curve truncation parity), `test_run_and_run_multi_timeframe_identical_short_side` (explicit short-side entry/TP/SL/EOD-close/fees/pnl/equity fixture), and `test_run_and_run_multi_timeframe_diverge_when_higher_tf_gates_bars` — the divergence test pins the multi-TF warmup contract (`all(slice_dict[tf] >= warmup_candles)`) by asserting strict-subset entry-bar indices `[120,150,180,195]` vs `[10,30,60,90,120,150,180,195]`, so the parity claim cannot silently widen to "always identical, including when it shouldn't be". Superseded `tests/test_backtest_multi_timeframe.py::TestRunMultiTimeframeSemantics::test_single_and_multi_tf_modes_share_closed_trade_ledger` deleted outright (new parity pair is a strict superset); orphan helpers `exit_fixture_candles` / `trade_ledger` and the unused `BacktestResult` import removed; module docstring now points readers at `TestRunMultiTimeframeParity` as the canonical parity location. Test-only diff (`tests/test_backtest_engine.py` + `tests/test_backtest_multi_timeframe.py`); no production code touched. Focused suite 61 passed; full suite 1802 passed / 6 failed (all 6 pre-existing DEBT-056, independently confirmed via `git stash`). Reviewers 🟢🟢. |

### DEBT-059: PaperBalance.locked not reconciled across runtime restart ✅

| Field | Value |
|-------|-------|
| **Priority** | High |
| **Created** | 2026-05-10 |
| **Resolved** | 2026-05-12 |
| **Resolution** | `PaperTrader` now persists per-sub-account paper balances to `data/trades/paper/<sub_account>/balances.json` via atomic writes. Startup loads the snapshot before rehydrating open positions, so `free`, `locked`, realised PnL, and paid fees survive process restarts instead of reseeding from `paper_initial_balance`. For legacy ledgers that have open trades but no snapshot yet, rehydration performs a one-time margin/entry-fee reconciliation and writes the first snapshot. Regression tests cover snapshot loading without double-locking, legacy one-time reconciliation, and restart close behaviour. |

### DEBT-058: production trades.json backfill for legacy SL/TP-null rows ✅

| Field | Value |
|-------|-------|
| **Priority** | High |
| **Created** | 2026-05-10 |
| **Resolved** | 2026-05-12 |
| **Resolution** | The one-shot operator CLI `src/tools/backfill_paper_sl_tp.py` is present and covered by `tests/test_tools_backfill_paper_sl_tp.py`. It walks `data/trades/paper/<sub_account>/trades.json`, finds open rows with missing SL/TP and a linked `performance_record_id`, reads the matching performance record under `data/performance/<sub_account>/`, and rewrites the ledger atomically. Tests cover successful backfill, dry-run, sub-account filtering, idempotency, missing perf IDs, null perf bounds, missing perf records, malformed/missing roots, and CLI argument wiring. |

### DEBT-057: paper-mode entry-fee not persisted to TradeHistory ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-05-10 |
| **Resolved** | 2026-05-12 |
| **Resolution** | `PaperTrader.open_position` now passes the calculated entry fee into `TradeHistoryTracker.open_trade`, so open paper rows persist the entry-side fee and rehydration can restore `OpenPosition.entry_fee`. `close_position` now passes only the exit fee to `close_trade`, relying on `TradeHistoryTracker.close_trade` to add it to the already-persisted entry fee. Regression coverage extends `TestPaperRehydration::test_open_position_persists_sl_tp` to assert entry-fee persistence in both tracker memory and the serialized JSON ledger, while the existing fee tests pin final total-fee and PnL math. |

### DEBT-053: Persisted open-position hydration after runtime restart ✅

| Field | Value |
|-------|-------|
| **Priority** | High |
| **Created** | 2026-05-08 |
| **Resolved** | 2026-05-09 |
| **Resolution** | CH-07 extended `TradeHistory` with optional `stop_loss` / `take_profit`, persisted live entry fees and risk bounds at open time, and added `LiveTrader` startup rehydration for persisted open live trades that include those bounds. `LiveTrader.get_open_position()` now exposes monitorable in-memory state to the runtime orphan guard. Historical open live trades without persisted SL/TP remain visible but intentionally non-monitorable, requiring operator reconciliation instead of unsafe inferred bounds. |

### DEBT-054: Account-scoped exchange router for sub-account runtime ✅

| Field | Value |
|-------|-------|
| **Priority** | High |
| **Created** | 2026-05-08 |
| **Resolved** | 2026-05-09 |
| **Resolution** | CH-08 removed the runtime startup block for active non-default `exchange_ref` values and routes proposal scan, stale-quote checks, monitor ticker fetches, and portfolio mark prices through the exchange exposed by each active sub-account trader. `SubAccountRegistry` now binds paper sub-accounts to named-credential exchanges when configured, and the proposal engine's default exchange is restored after each account-scoped scan. |

### DEBT-014: `loop.propose_new` called without `param_grid` — sensitivity gate SKIPPED ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-04-29 |
| **Resolved** | 2026-05-05 |
| **Resolution** | Added per-pick `param_grid` declarations for all auto-research catalog picks, threaded those grids into `FeedbackLoop.propose_new`, and added an automatic generated-code strategy factory so code-type candidates can be instantiated with swept constructor tunables during the robustness sensitivity gate. The generation context now names the exact tunables Claude must expose. |

### DEBT-022: Cumulative / rate-based breaker counterpart for failure-rate ≫ 0 strategies ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-07 |
| **Resolution** | Added cumulative parse-failure counters alongside the existing consecutive breaker in both `Backtester.run` and `Backtester.run_multi_timeframe`. `BacktestConfig` now exposes `min_cumulative_parse_failures` and `max_cumulative_parse_failure_rate`, mirrored by `Settings.engine_backtest_*` env fields. Intermittent failure patterns now abort with `BacktestAbortedError(reason="cumulative_parse_failure_rate")` once the sample exceeds 50 cumulative failures and the failed-call ratio is above 50%. |

### DEBT-052: Per-sub-account notification routing overrides deferred ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-05-03 |
| **Resolved** | 2026-05-06 |
| **Resolution** | Added optional `notification_route` refs to sub-account config, parsed route-specific Slack webhooks through `Settings.notification_slack_webhook_urls`, and introduced `RoutedNotificationDispatcher` so a proposal's `sub_account_id` can choose a route-specific dispatcher while preserving default console/file notification logging. `src/main.py::build_engine` now builds route dispatchers from configured refs. |

### DEBT-026: Donchian experimental strategy file truncated and untracked ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-05 |
| **Resolution** | Archived the truncated Donchian artefact to `docs/archive/strategy-artifacts/donchian_turtle_system_2_20260430_002157.truncated.md` with an explicit warning that it is evidence only and must not be loaded or promoted. Removed it from `strategies/experimental/`, leaving only `.gitkeep`, and added `.gitignore` rules for generated `strategies/experimental/*.md` / `*.py` candidates so future auto-research runtime artefacts are not committed accidentally. |

### DEBT-023: No test pins improvement-prompt preservation of existing Output Contract block ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-06 |
| **Resolution** | Added a post-generation guard in `StrategyImprover.suggest_improvement`: when the original source contains `## Output Contract`, the improved body must preserve the heading and the original contract's runtime trade keys. Invalid improvements raise `GeneratedTechniqueError` before any file is saved. Added `TestImprovementOutputContract` coverage for preservation, dropped-contract rejection, and missing-key rejection. |

### DEBT-049: Phase 17.5 code-type integration test fixture uses `signal="neutral"` (does not exercise trade-producing path) ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-05-02 |
| **Resolved** | 2026-05-06 |
| **Resolution** | Added `TRADE_PRODUCING_PYTHON_STRATEGY` and `test_code_type_pick_produces_backtest_trade_without_claude_analyze` to `tests/test_scripts_auto_research_candidates.py`. The fixture emits a long signal, the real `Backtester` opens/closes at least one trade, the saved code strategy reloads through `load_strategy`, and `ClaudeCLI.analyze` remains at zero calls. |

### DEBT-051: `SubAccountRegistry._load` YAML config dead branch silently ignores pre-staged files ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-05-02 |
| **Resolved** | 2026-05-03 |
| **Resolution** | Phase 19.3 replaced the placeholder `if self.config_path.exists(): pass` branch with real YAML parsing, Pydantic validation, duplicate-id rejection, live-non-default rejection, and exchange-ref validation. |

### DEBT-021: Strategy warmup contract mismatch with `BacktestConfig.warmup_candles` ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-03 |
| **Resolution** | Added `TechniqueInfo.min_warmup_candles`, `BaseStrategy.minimum_candles`, and `Backtester.effective_warmup_candles(strategy)`. Single-TF, multi-TF, and robustness pre-check warmup gates now use `max(BacktestConfig.warmup_candles, strategy.minimum_candles)`. `RSIMeanReversionStrategy.minimum_candles` declares its dynamic `period * 3` floor. Added regression tests for single-TF, multi-TF, and RSI warmup declaration. |

### DEBT-016: `CycleResult.proposals_accepted` and `proposals_rejected` simultaneous increment — contract undocumented ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-03 |
| **Resolution** | Added `CycleResult` docstring language clarifying proposal counters are stage counters, not mutually-exclusive final-state counters. Post-acceptance gates can increment both accepted and rejected for the same proposal, so `accepted + rejected` is not an invariant. |

### DEBT-018: Phase 18.1 rejection tests don't assert simultaneous-counters contract ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-03 |
| **Resolution** | Added `result.proposals_accepted == 1` assertions to stale-quote past-SL, stale-quote short, slippage, no-live-data, and ticker-failure/fall-through runtime tests. `tests/test_runtime_engine.py` now pins the simultaneous-counters contract for post-acceptance gates. |

### DEBT-017: Stale-quote rejection event carries `entry_price` and `proposal_entry` for the same value ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-03 |
| **Resolution** | Removed explicit `proposal_entry` from stale-quote and no-live-data rejection activity payloads. The shared `_proposal_summary` `entry_price` field is now the single proposal-entry value across proposal events. Runtime tests assert `entry_price` remains present and `proposal_entry` is absent. |

### DEBT-013: `auto_research_candidates.run_async` self-constructs `FeedbackLoop` / `BinanceExchange` ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-29 |
| **Resolved** | 2026-05-03 |
| **Resolution** | `scripts/auto_research_candidates.py::main` now constructs the `FeedbackLoop` and Binance exchange through explicit `build_loop()` / `build_exchange()` factories and passes them into `run_async`. `run_async` now requires caller-built dependencies, owns connect/disconnect by default for the script entrypoint, and can be called with `owns_exchange=False` by future shared-runtime callers. Added tests pinning the dependency injection path and the `main` wiring. |

### DEBT-015: Rejection-path semantic divergence — Phase 18.1 rewrites `ProposalRecord`, Phase 12.1 emits activity-event only ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-03 |
| **Resolution** | The Phase 12.1 cap-rejection branch in `TradingEngine._handle_proposal` now rewrites the accepted `ProposalRecord` to `decision="rejected"` with the cap reason and fresh `decision_at`, then persists via `ProposalHistory.save`. Existing `PROPOSAL_REJECTED` activity event emission is preserved. Runtime tests now assert cap rejections are visible through both `ProposalHistory.load(...)` and the activity log. |

### DEBT-001: Pre-Existing Lint/Type Sweep ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 11.1 cleared all 18 ruff + 12 in-scope mypy errors; ruff config migrated to `[tool.ruff.lint]`; `types-PyYAML` added. |

### DEBT-002: OHLCV Per-Technique Refetch in Multi-Technique Scan ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 11.2 added per-call (symbol, tf) cache; verified 3-symbol × 4-technique example drops from 12 → 3 fetches. |

### DEBT-005: ccxt typing in `src/exchange/binance.py` ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 12.2 added `CCXTClient` Protocol covering 10 ccxt methods used (`load_markets`, `close`, `fetch_ohlcv`, `fetch_ticker`, `fetch_balance`, `create_market_order`, `create_limit_order`, `cancel_order`, `fetch_order`, `fetch_open_orders`); `_client` typed as `CCXTClient \| None`. mypy: 11 errors → 0. |

### DEBT-006: `src/exchange/factory.py` shape drift ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 12.2 investigated — NOT a behavioural mismatch. Registry's `type[BaseExchange]` widens away subclass `__init__` params. Resolved with tightly-scoped `cast(Any, exchange_class)(...)` + comment explaining the typing gap. mypy: 3 errors → 0. |

### DEBT-007: Dashboard Streamlit type errors ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 12.2 added `Literal` types for theme constants, `StreamlitPage` import for navigation, `cast(...)` on `st.metric` numeric values. mypy: 13 errors → 0. |

### DEBT-008: `src/main.py` lambda annotation ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 12.2 added targeted `# type: ignore[misc]` (canonical case for asyncio signal-handler callback shape mismatch). mypy: 1 error → 0. |

### DEBT-009: `scripts/lint.sh --fix` unsafe for CI ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 13.1 split `scripts/lint.sh` into CI-safe (no `--fix`) + dev-only `scripts/lint-fix.sh`. |

### DEBT-010: Long+Short Same-Symbol Test Gap ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 13.1 added `test_cap_blocks_opposite_side_same_symbol`; verifies long+short same-symbol cap path matches single-side cap behaviour. |

### DEBT-011: Dashboard `dict[str, object]` casts ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 13.1 introduced per-page TypedDicts (`TradingSummaryMetrics`, `EngineSummaryMetrics`) replacing `dict[str, object]`; `cast()` calls dropped. |

### DEBT-003: EngineConfig Remaining Fields Not Env-Overridable ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 13.2 added `engine_monitor_interval` / `engine_bitcoin_symbol` / `engine_altcoin_top_k` / `engine_actor` Settings fields with env override; `build_engine` wires all 4 to `EngineConfig`. |

### DEBT-004: Baseline Backtest Script Follow-ups ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 13.3 added `since: int | None = None` to `BaseExchange.get_ohlcv` ABC; Binance + Bybit forward to ccxt; `scripts/backtest_baselines.py` drops the `_client` reach-around. |

### DEBT-012: SMTP_SSL alternative for port 465 SMTP providers ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 14.2 added `email_use_ssl` Settings flag; `EmailNotifier` branches between `smtplib.SMTP`+STARTTLS (default) and `smtplib.SMTP_SSL` (port 465 providers). |

### DEBT-019: Auto-research script hangs indefinitely on prompt-type technique backtest ✅

| Field | Value |
|-------|-------|
| **Priority** | High |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-04-30 |
| **Resolution** | Phase 17.4 (originally tagged 17.2 in commit log; renumbered by Phase 23.2) shipped DEBT-019's Options A + C: (A) `_build_new_idea_prompt` mandates a `## Output Contract` block in the generated body matching chasulang's JSON schema (`signal` / `entry_price` / `stop_loss` / `take_profit`), pinned by 3 new `TestNewIdeaOutputContract` cases; (C) `Backtester.run` and `_run_multi_timeframe` gain per-bar `asyncio.wait_for` timeout + consecutive-parse-failures counter that aborts via new `BacktestAbortedError(reason, candle_index)` propagating to `LoopStatus.ERRORED`, pinned by 3 new `TestPerBarCircuitBreaker` cases. Refinement at implementation: `StrategyValidationError` ("data not ready") caught separately and skipped without incrementing the breaker counter so warmup-floor strategies (`rsi_universal`'s `period * 3 = 42` vs default `warmup_candles=20`) don't trip the breaker — surfaced as DEBT-021 for the long-term contract fix. New `Settings.engine_backtest_per_bar_timeout` (default 600s post-DEBT-020) + `engine_backtest_max_parse_failures` (default 5) env overrides. **Option B (code-type steering) shipped 2026-05-02 by Phase 17.5**: `Pick.code_type: bool = False` flag + `_build_new_idea_code_prompt` branch in `src/ai/improver.py:676` instructing Claude to emit `BaseStrategy` Python subclasses (with `async analyze` matching the abstract interface, not the spec's mistaken "sync `signal`"); all 9 catalog TOP_PICKS (Donchian, Supertrend, Connors RSI(2), Z-score, Larry Williams, TTM Squeeze, BB %B+RSI, Golden Cross, NR7) flagged `code_type=True`. Loader (`src/strategy/loader.py`) already supported `.py` files via existing `load_technique_info_from_py` — no changes needed. 6 new tests pin the contract; the load-bearing integration test asserts `claude.complete.call_count == 1` (single code-generation call) AND `claude.analyze.call_count == 0` during a real `Backtester.run_for_strategy` over 300 synthetic candles — proving zero per-bar LLM calls for code-type strategies. pytest 1361 → 1367 (+6); ruff/mypy/black clean. Reviewers: quant 🟡 (catalog/interface/invariant all correct; non-blocking note that fixture's `signal="neutral"` doesn't exercise real-trade path → recorded as DEBT-049), qa 🟢 ship. 9-hour hang failure mode now closed at root: deterministic strategies bypass the LLM hot path entirely. `donchian_turtle_system_2_20260430_002157.md` artefact (DEBT-026) becomes obsolete on next regenerate. |

### DEBT-020: `BacktestConfig.per_bar_timeout` default unsafe for chasulang ✅

| Field | Value |
|-------|-------|
| **Priority** | High |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-04-30 |
| **Resolution** | Same-cycle one-line bump caught by Phase 17.2 quant-trader-expert review before any chasulang backtest ran: `BacktestConfig.per_bar_timeout` default raised `60.0` → `600.0` (chasulang's actual 480s `claude_timeout_seconds` per-`analyze()` ceiling + 120s headroom). `Settings.engine_backtest_per_bar_timeout` default + `.env.example` operator prose + `TestBacktestEngineSettings::test_per_bar_timeout_default_and_env` parity test all updated to match. The dev-plan rationale at lines 1750–1754 referencing "240s" + "multi-bar amortised" is stale (actual: 480s, per-call) and superseded by this resolution; flagged as planner correction needed. Forward-pointer for cleaner long-term shape: `Backtester.__init__` could peek at `strategy.info.claude_timeout_seconds` and use `max(default, strategy_timeout + headroom)` so the breaker self-adjusts to whatever the loaded strategy declares — out of scope for the one-line bump, tracked under DEBT-019's broader circuit-breaker-hardening umbrella. |

### DEBT-029: Phase 5.4+ baseline figures need re-computation post-leverage fix ✅ (Reframed)

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 (**Reframed**, not implemented) |
| **Resolution** | Phase 20.3 deferral surfaced that DEBT-029's "operator-facing artefact regeneration" framing was vacuous: `data/backtest/baselines/` directory is absent on this checkout (gitignored), `docs/baselines.md` operator table is `_TBD_` for every metric (lines 124-136), and no inflated baseline figures had ever been persisted. The bug existed in the math (DEBT-024), not in any persisted operator surface — operator impact of the regeneration assumption was therefore 0. The math fix (DEBT-024) closed at the code level by Phase 20.1 (`pnl_for_trade` helper + four PnL sites routed through it) and Phase 20.2 (grep audit, convention docstrings, regression-guard test); cross-ledger numeric parity locked by `TestPnLConventionAlignment` (4 cases) and persistence parity by `test_close_trade_persisted_pnl_routes_through_helper{,_short}` (2 cases). What remains is reproducible baseline design work, not "re-compute" — `scripts/backtest_baselines.py` calls live Binance mainnet with no snapshot mode, so a re-run produces non-deterministic output that drifts day-to-day. That reproducibility debt is reassigned to new **DEBT-043** (Medium, owned by Phase 25: Snapshot-Pinned Reproducible Baselines). DEBT-029 itself closes as **Reframed** because the original problem statement was wrong; the math-correctness side is fully addressed by the chain DEBT-024 → 20.1 + 20.2, and the reproducibility side is now tracked under DEBT-043 with its own suggested resolution shape (snapshot dataset + `--snapshot` flag + freshness policy + first-time `docs/baselines.md` population). |

### DEBT-025: Exchange adapters and `JsonlRotator` use UTC-naive `datetime` ✅

| Field | Value |
|-------|-------|
| **Priority** | High |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Closed across Phase 21.1 (adapter read-side, 8 sites + helper module), 21.2 (write-side sweep, 12+ sites + 7 Pydantic UTC-coerce validators + 5 reader-boundary naive-tolerance shims), and 21.3 (stale-quote payload coherence — formal contract docstring + 3 regression tests pinning aware-on-write, cross-source aware math, and legacy-naive read tolerance). Every UTC-naive surface flagged in the 2026-04-30 audit is now closed. Phase 21.1: new `src/utils/time.py` with `from_unix_ms(ms) -> datetime` (`tz=UTC`) and `now_utc() -> datetime` wrapping `datetime.now(tz=UTC)`; 4 site swaps in `src/exchange/binance.py` (~lines 233, 273, 504, 506) and 4 in `src/exchange/bybit.py` (~lines 165, 202, 433-435); `JsonlRotator._coerce_timestamp` (read-side) UTC-normalised. Phase 21.2: new `ensure_utc(value)` helper added to `src/utils/time.py` (3-function module now); write-side `datetime.now()` swaps at 12+ sites across `src/runtime/jsonl_rotator.py:103` (the original 21.2 spec target), `src/runtime/engine.py` (multiple), `src/runtime/activity_log.py`, `src/feedback/loop.py` (~6 sites), `src/feedback/audit.py`, `src/proposal/interaction.py` (~3 sites), `src/proposal/engine.py`, `src/proposal/notification.py`, `src/strategy/performance.py` (~6 sites), `src/strategy/base.py`, `src/ai/improver.py:334`, `src/models.py`, `src/trading/portfolio.py`; Pydantic `field_validator(mode="after")` UTC-coerce hooks on 7 models / 9 fields (`ActivityEvent`, `AuditEvent`, `Proposal`, `CandidateRecord`, `AssetSnapshot`, `PerformanceRecord`×2, `TradeHistory`×2); reader-boundary naive-tolerance shims at 5 sites (`PortfolioTracker.load_snapshots`, `TradeHistoryTracker.get_trades_by_date_range`, `PerformanceTracker.get_records_by_date_range`, `ProposalHistory.purge_old`, `ProposalHistory.list_all` sort key). Phase 21.3: `_record_stale_quote_rejection` docstring extended with formal "Timestamp coherence contract (DEBT-025 / Phase 21.3)" section naming five UTC-aware sources (engine wall-clock, ticker candle, proposal entry, live price, persisted record); function body byte-identical below the new docstring section; 3 new regression tests in `tests/test_runtime_engine.py` (lines 992 / 1033 / 1082) pinning aware-on-write coherence, cross-source aware math (`decision_at - candle_ts`), and legacy-naive read tolerance. 1265 total tests passing across the chain. Reviewers ship-class throughout (21.1 🟢🟢, 21.2 🟢🟢, 21.3 🟢 quant + 🟡 qa with recorded out-of-scope linter-reformat note at `engine.py:436-440` not actioned per lead's standing guidance). Phase 21 cross-check: `docs/cross-checks/2026-05-01-phase-21-time-tz-hardening.md` (PASS, no gaps, no new debt). Session logs: `docs/sessions/2026-05-01-phase-21.1-utc-timestamp-helper.md`, `docs/sessions/2026-05-01-phase-21.2-utc-write-side-sweep.md`, `docs/sessions/2026-05-01-phase-21.3-and-phase-21-seal.md`. |

### DEBT-028: Persistence sites use non-atomic JSON write (load → mutate → save) ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 22.1 introduced `src/utils/io.py::atomic_write_text(path: Path, text: str) -> None` — writes to `path.with_suffix(path.suffix + ".tmp")` with a uuid-suffixed tmp name (concurrent-writer-tolerant on the tmp side) then `os.replace(...)`s into the destination, with cleanup-on-exception so a raise mid-write leaves no orphan tmp file. Migrated 5 named load → mutate → save sites: `PerformanceTracker._save_records` (`src/strategy/performance.py:439`), `PerformanceTracker._update_summary` (`src/strategy/performance.py:494`), `TradeHistoryTracker._save_trades` (`src/strategy/performance.py:1077`), `PortfolioTracker._save_snapshots` (`src/trading/portfolio.py:407`), `ProposalHistory.save` (`src/proposal/interaction.py:245`). `RuntimeEngine._record_stale_quote_rejection` covered transitively via `ProposalHistory.save`; doc comment added at the call-site naming the transitive coverage. 15 module-level helper unit tests (happy path, tmp-file present after crash, last-writer-wins under threads, cleanup-on-exception); 4 site regression tests (one per migrated tracker — crash-mid-write preserves prior record on disk; threaded last-writer-wins). pytest 1265 → 1284 (+19); ruff / mypy / black clean. Both reviewers ship-class (qa 🟢, quant 🟢). **Plan-text correction noted**: the DEBT-028 description and the Phase 22.1 spec line both pointed at `src/proposal/history.py`, but `ProposalHistory` actually lives in `src/proposal/interaction.py`. Plan text corrected in-place by Phase 22.1 docs-auditor (`docs/development-plan.md` Phase 22.1 sub-task block). **Caveat — atomicity ≠ concurrency-safety**: `atomic_write_text` resolves crash-mid-write durability (destination is either fully old or fully new, never partial) but does **not** solve concurrent-mutation loss — two workers doing load → mutate → save in the same wall-clock window will each see the same prior state, each write atomically, and the loser's mutation is silently dropped. Single-engine deployment is safe (one writer per file); Phase 19.2 sub-account fan-out introduces parallel workers and requires additional per-file locking (e.g. `fcntl.flock`) or per-account file partitioning. Captured as **DEBT-046 (Medium, hard prereq for Phase 19.2)** with the resolution-shape options enumerated; cross-referenced on the Phase 19.2 spec page (`docs/development-plan.md` Prerequisites line). Two adjacent-scope follow-ups also registered: **DEBT-044** (Low — `FeedbackLoop.save_state` not migrated; same shape, mechanical) and **DEBT-045** (Low — `Backtester._save_result` single-write not atomic; helper exists, one-line route). Session log: `docs/sessions/2026-05-01-phase-22.1-atomic-write-helper.md`. |

### DEBT-027: Paper trader silently zeroes balance instead of recording liquidation ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 22.2 closed the paper-vs-live divergence at the under-water close boundary. Under-water close detection rewritten via a projected-free predicate evaluated *before* the mutation lands (`projected_free = balance.free + (pnl - exit_fee) < 0`), splitting detection from remediation cleanly. Default branch records true negative equity AND emits a structured `LIQUIDATED` activity event with the documented payload contract (`symbol`, `side`, `entry`, `exit`, `qty`, `realized_pnl`, `balance_before`, `balance_after`). New `ActivityEventType.LIQUIDATED` enum member (`src/runtime/activity_log.py:109`) carries the contract on the type. `PaperBalance.free` Pydantic constraint relaxed (dropped `ge=0`) so the negative-equity round-trip survives `validate_assignment`; lock / deduct / reserve paths still enforce overdraw protection at their own boundaries — the relaxation is a permission to *report* negative equity, not to silently underflow during normal operations. `PaperTrader.__init__` gained 2 backward-compatible kwargs: `activity_log` (the bus the LIQUIDATED event emits onto, default `None` so legacy callers without an activity log still work) and `auto_deposit_on_liquidation` (default `False`, the new correctness-first behaviour). The legacy clamp-to-zero behaviour is preserved behind the opt-out flag for testing scenarios that need a continuing run after liquidation; **both branches emit the LIQUIDATED event** — the flag controls balance treatment, not event semantics. `EngineConfig` / `Settings` mirror the flag as `paper_auto_deposit_on_liquidation` (env-overridable via `PAPER_AUTO_DEPOSIT_ON_LIQUIDATION`); `.env.example` documents the toggle; `src/main.py::build_engine` plumbs `ActivityLog` and the flag into `build_trader`. 6 regression tests in `tests/test_paper_trading.py` pin the contract: under-water default emits LIQUIDATED, under-water default round-trips negative equity, auto-deposit opt-out clamps but still emits, exit-fee-only shortfall (the historical line-626 branch — fee alone pushes balance negative without any pnl loss component) takes the liquidation path, normal close stays silent, flag-on payload parity with default. pytest 1284 → 1290 (+6); ruff / mypy / black clean. Both reviewers ship-class (qa 🟢, quant 🟢). **Asymmetry surfaced**: backtester (`src/backtest/engine.py:371,396`) has no margin / liquidation modeling — `balance += pnl_delta` runs arbitrarily negative without an analogue. Captured as **DEBT-047 (Medium)** with two resolution shapes (`BacktestConfig.liquidation_threshold` + structural marker on `BacktestTrade` / `BacktestResult`, OR conservative clamp + log at threshold). **Plan-text drift noted**: DEBT-027's description cited `src/trading/paper.py:619,626` as the under-water clamp sites; by the time 22.2 shipped the actual liquidation branch lives around lines 656-720 — same pattern as DEBT-024 stale line references and DEBT-028 / Phase 22.1 path drift. Phase 22 cross-check `docs/cross-checks/2026-05-01-phase-22-persistence-atomicity-liquidation.md` PASS; phase sealed (22.1 ✅, 22.2 ✅). Session log: `docs/sessions/2026-05-01-phase-22.2-and-phase-22-seal.md`. |

### DEBT-024: Leverage applied twice in backtester / portfolio PnL math ✅

| Field | Value |
|-------|-------|
| **Priority** | High |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 20.1 extracted `pnl_for_trade(entry, exit, qty, side) -> Decimal` into new `src/utils/trading_math.py` (leverage NOT a parameter — qty already reflects the levered notional from `calculate_position_size`, so making leverage a parameter would invite a future caller to pass it again and reintroduce the bug). Routed every PnL site through the helper: `src/backtest/engine.py::_close_trade` (dropped `* leverage`), `src/trading/portfolio.py::calculate_unrealized_pnl` (dropped `* leverage`), `src/trading/paper.py::close_position` (already correct shape; routed for symmetry, bytewise-identical output). **Scope extension absorbed during quant-trader-expert review** (originally scheduled for 20.2): `src/strategy/performance.py::TradeHistory.calculate_pnl` (lines ~797-839) — both branches dropped `* self.leverage` from `pnl`, and `pnl_pct` reformulated as leverage-neutral (`(exit - entry) / entry` for longs, sign-inverted for shorts). Cross-ledger parity locked by `tests/test_backtest_engine.py::TestPnLConventionAlignment` (4 cases — long/short numeric equality between backtester and paper-trader on fixed (entry, exit, qty, leverage) fixture); persistence-layer parity by `test_close_trade_persisted_pnl_routes_through_helper{,_short}` (2 cases). 11 module-level helper unit tests; 19 cascaded assertion updates across `tests/test_paper_trading.py` (8 across 7), `tests/test_portfolio.py` (5), `tests/test_strategy_performance.py` (3 calculate_pnl) — purely mechanical fixture corrections to the new correct numbers. 1226 total passing. **Note on stale line-number references**: the original DEBT-024 description pointed at `src/backtest/engine.py:783-794` for `calculate_position_size` + per-trade PnL multiplication, but by the time the fix shipped the actual leverage site had moved to `_close_trade` ~lines 948-960. Recorded for future audit-trail readers reconstructing the diff. Session log: `docs/sessions/2026-05-01-phase-20.1-pnl-helper-unification.md`. **Phase 20.2 follow-up (2026-05-01)** locked the discipline side: grep audit across `src/backtest/`, `src/trading/`, `src/strategy/` confirmed no missed `* leverage` on the PnL surface (4 margin sites kept, 4 PnL sites confirmed routed); convention docstrings added on `AssetSnapshot.unrealized_pnl`, `Portfolio.unrealized_pnl`, `TradeHistory.pnl`, `TradeHistory.pnl_percent`, and `Position.calculate_pnl` naming the leverage-neutral convention; regression-guard test `tests/test_leverage_pnl_no_double_apply.py` (5 tests, 4 file scans + 1 self-test) pins the convention forward against text-shape reintroduction (alias-gap acknowledged in module docstring; defence-in-depth alongside Phase 20.1's `TestPnLConventionAlignment` numeric parity, not a sole gate). Session log: `docs/sessions/2026-05-01-phase-20.2-leverage-math-alignment.md`. DEBT-029 (Phase 5.4+ baseline re-computation, scheduled as Phase 20.3) remains the downstream consequence and stays open until 20.3 lands. |

### DEBT-037: Documentation drift — `CLAUDE.md` tree + `DESIGN.md` ClaudeClient + `TECH-DEBT.md` stats ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 23.1 closed all three drift items the 2026-04-30 audit named. (1) `CLAUDE.md`'s project-structure tree extended to include `src/runtime/` (engine, activity_log, jsonl_rotator), `src/tools/` (operator scripts), and `src/utils/` (`trading_math.py` from Phase 20.1, `time.py` from Phase 21.1, `io.py` from Phase 22.1) — three directories that had shipped without ever being listed in the contributor-facing tree. `src/main.py` also surfaced as a top-level entry point alongside the existing `config.py` / `logger.py` / `models.py` listing. (2) `DESIGN.md §2.3` rewritten end to end: `class ClaudeClient` (which never existed in code) replaced with the actual `class ClaudeCLI` from `src/ai/claude.py:46`, real method signatures listed verbatim (`__init__(timeout, claude_path, max_retries)`, `is_available()`, `async analyze(prompt) -> dict[str, Any]`, `async complete(prompt) -> str`); the parallel `class StrategyImprover` block from `src/ai/improver.py:98` added so the documentation matches the actual two-class shape (`generate_idea`, `generate_user_idea`, `improve`); the constraint line clarified to name the `analyze` / `complete` split. The DESIGN.md "ADR list" cross-reference flagged in the original spec did not need a corresponding edit (no ADR list exists in DESIGN.md; the project's ADRs would live as Markdown files under `docs/adr/` if any are written, and that directory is not present in the current checkout). (3) `docs/TECH-DEBT.md` ordering: DEBT-018 reordered above DEBT-021 (was below DEBT-019 / 20 / 21 / 22 / 23 separated by an internal `---` separator that the audit's traversal flagged as inconsistent); the stray `---` separator that had isolated DEBT-018 from the rest of the Active items removed. Statistics table recomputed by counting `### DEBT-` headings in Active vs Resolved sections (28 active → 27 active after DEBT-037 closes; 19 resolved → 20 resolved; Medium unchanged at 7; Low 21 → 20). Phase 23.1 also backfilled the missing artefacts the same audit surfaced (sessions for shipped Phase 17.2 portfolio-snapshot recording / 17.3 closed-trade performance records, the Phase 15 cross-check) — same audit finding, separate spec items, same cycle. Session log: `docs/sessions/2026-05-01-phase-23.1-docs-drift-backfill.md`. |

### DEBT-030: Backtester MDD / Sharpe computed from closed-trade equity only ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 24 introduced a per-bar equity curve. New `EquityPoint` Pydantic model + `BacktestResult.equity_curve: list[EquityPoint]` field; `Backtester._build_equity_curve` walks every candle and marks every open position to bar-close via `pnl_for_trade`, summing realised + unrealised + initial. `PerformanceAnalyzer._max_drawdown` and `_sharpe` prefer the equity curve when available, fall back to the original closed-trade path when absent (back-compat with persisted `result.json` lacking the field). **Quant-driven follow-up fix in same cycle**: `_sharpe_from_equity_curve` now derives `bars_per_year` from median Δt of `EquityPoint` timestamps via new `_bars_per_year` helper (returns 8760 on hourly cadence, 365 on daily); ignores caller-supplied `trades_per_year` on the bar path so dashboard / persisted reports do not silently scale Sharpe by ~5.9× when comparing hourly-cadence baselines. Closed-trade fallback preserves prior `trades_per_year` semantics. Tests: `TestEquityCurveMaxDrawdown` (3 cases, intra-trade MDD strictly > closed-trade MDD on a fixture that drops 800 then recovers to a 50-loss close) + `TestEquityCurveSharpeAnnualization` (4 cases, hand-computed √8760 ≈ 22.066, hourly+daily cadences, single-point edge, caller-trades-per-year-ignored invariant). Session log: `docs/sessions/2026-05-01-phase-24-and-phase-24-seal.md`. |

### DEBT-031: MA-crossover SL evaluation includes the current candle ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 24 rolled the SL look-back back by one bar. `strategies/ma_crossover.py` long-side `min(closes[-5:])` → `min(closes[-6:-1])` (5-element slice indices -6 through -2, exclusive stop at -1, excludes the current candle); same pattern on the short-side `max(...)`. Quant sign-off granted as a strict signal-quality improvement: previously-suppressed valid bullish/bearish crosses where the entry candle was itself the local 5-bar low/high (which forced SL ≥ entry → `validate_prices` raised → signal silently dropped) now emit cleanly. Tests: `tests/test_baseline_strategies.py::test_ma_long_sl_excludes_current_candle_lookback` + `..._short_...` (2 cases, both pin a fixture where the current close is the 5-bar low/high and assert the trade is now emitted). Session log: `docs/sessions/2026-05-01-phase-24-and-phase-24-seal.md`. |

### DEBT-032: OOS Sharpe gate fails when in-sample population is small ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 24 added an IS-trade floor SKIP guard. New `RobustnessConfig.minimum_is_trades: int = 10` (quant-driven follow-up bumped from initial default 5 since "Sharpe estimates with N<10 trades have prohibitively high variance"; field `description=` cites the rationale). New SKIP branch in `RobustnessGate.run_oos_gate` ordered *before* the existing IS-Sharpe-non-positive FAIL: when `is_run.total_trades < cfg.minimum_is_trades`, gate returns SKIPPED with reason naming the floor. Strict `<` boundary semantics — N=9 SKIPs, N=10 reaches the documented floor and is allowed to be judged (quant sign-off: flipping to `<=` would contradict the field's "below the floor" semantics). Aggregator preserves SKIP as non-PASS for promotion (back-compat with sensitivity-gate-skip pattern from DEBT-014). Tests: `test_skipped_when_is_trades_below_minimum_floor` + `test_minimum_is_trades_default_is_ten` + `test_below_floor_skips_but_at_or_above_floor_fails` (3 cases — boundary, default-pin, semantic-direction). Session log: `docs/sessions/2026-05-01-phase-24-and-phase-24-seal.md`. |

### DEBT-033: Stale-quote gate falls through on ticker exception without freshness check ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 24 added a ticker-age freshness check + opt-in hard-rejection. New `EngineConfig.max_ticker_age_seconds: float = 10.0` defines the cached-ticker freshness threshold; when a fetched ticker is older than the threshold the gate emits `stale_quote_check_failed` WARN (observability). **Quant-driven follow-up fix in same cycle**: new `EngineConfig.reject_if_stale_quote: bool = False` (opt-in) — when True, both stale-ticker AND ticker-fetch-error branches hard-reject the proposal via new `_record_no_live_data_rejection` helper (mirrors existing `_record_stale_quote_rejection` shape) with `reason="stale_quote_no_live_data"`, addressing the original audit concern that "fill proceeds at proposal.entry_price with no live cross-check" — WARN-only is observability, the opt-in flag is enforcement. Plumbed via `Settings.engine_reject_if_stale_quote` and `.env.example`. Default False preserves prior fall-through behavior; live-mode operators set True. Tests: `test_stale_quote_gate_falls_through_when_ticker_age_exceeds_threshold`, `test_stale_quote_gate_uses_fresh_ticker_when_within_threshold`, `test_reject_if_stale_quote_true_blocks_fill_on_stale_ticker`, `test_reject_if_stale_quote_false_preserves_fall_through_warn`, `test_reject_if_stale_quote_true_blocks_fill_on_ticker_fetch_error` (5 cases — both branches × both flag values, plus the freshness threshold itself). Session log: `docs/sessions/2026-05-01-phase-24-and-phase-24-seal.md`. |

### DEBT-034: Cold-start technique selection uses alphabetical ordering ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 24 added a live-mode cold-start guard. New `ProposalEngineConfig.mode: Literal["paper", "live"]` + `min_closed_trades_for_live_promotion: int = 5`. New `_cold_start_blocks_live` guard at both proposal entry points (`ProposalEngine` BTC + altcoin paths) returns None — refusing to submit a live proposal — when no applicable technique meets the closed-trade threshold. Paper-mode behavior unchanged (cold-start-tolerant; that is how techniques bootstrap their performance history). `src/main.py` wires `settings.trading_mode` into `ProposalEngineConfig.mode`. **Quant-driven follow-up fix in same cycle**: new `ActivityEventType.COLD_START_BLOCKED` enum value; the guard now emits a structured event with payload `{symbol, reason="cold_start_below_min_closed_trades", min_closed_trades_for_live_promotion, max_trades_observed, per_technique_trades}` so operators see why the bot is intentionally idle on the dashboard rather than chasing a silent log line. Tests: `test_live_mode_blocks_cold_start_proposal` (extended to assert ActivityEvent payload), `test_paper_mode_allows_cold_start_proposal`, `test_live_mode_releases_when_threshold_met`, `test_live_mode_blocks_when_only_cold_start_techniques_present` (4 cases — live-block + activity event, paper-allow, threshold-release, mixed-techniques). Session log: `docs/sessions/2026-05-01-phase-24-and-phase-24-seal.md`. |

### DEBT-043: Baseline regenerator is non-deterministic — live Binance, no snapshot mode ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-05-01 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 25 closed at the infrastructure level via 25.1 + 25.2 + 25.3 Part A (partial seal — Part B is a one-time operator action with live Binance read-only credentials, fully documented in `docs/baselines.md` runbook, non-gating for further phases). **25.1**: new `src/backtest/snapshot.py` with `SnapshotMetadata` (Pydantic UTC-coerce per Phase 21.2 pattern) + `Snapshot` + `SnapshotValidationError` + `load_snapshot` / `save_snapshot` (atomic via Phase 22.1) + `is_snapshot_fresh` (90-day default, `now=` injectable) + `baseline_directory` helper. Format: CSV (`ohlcv.csv`) + JSON sidecar (`metadata.json`). Decimal-as-string round-trip (no `float()` drift). `.gitignore` switched `data/` → `data/*` with carve-backs (`!data/backtest/snapshots/**`); other data subdirs remain ignored. 27 tests covering round-trip, schema breach × 8, UTC contract, freshness boundary. **25.2**: 4 new CLI flags on `scripts/backtest_baselines.py` (`--snapshot [PATH]` opt-in reproducible, `--refresh-snapshot` operator-gated mainnet entry, `--max-snapshot-age-days INT` default 30, `--snapshot-root PATH`); `--snapshot` and `--refresh-snapshot` mutually exclusive. New `SnapshotExchange` class — free-standing (not `BaseExchange` subclass), follows `_FakeBinanceExchange` injection pattern. Slice-bounds enforcement (quant carry-over from 25.1): `clamped_limit = min(limit, len(rows))`; `if since > last_ts_ms: return []`. Active-use freshness window: 30-day default operator path; 90-day absolute stale ceiling. `Settings.engine_baseline_max_snapshot_age_days` env-overridable. `rsi_universal` reconciliation: KEEP (verified against `strategies/rsi.py:11-18` "universal-cadence fallback"). 10 tests including `test_cross_operator_determinism_byte_identical` (UUID scrubbing approved by quant — operator-trace IDs not strategy state). **25.3 Part A**: `docs/baselines.md` restructured with operator runbook (5-step first-fetch procedure), snapshot freshness policy section (30-day active vs 90-day absolute), reproducibility note (cross-operator byte-equality contract), all 5 baselines enumerated. Spec deviations recorded as DEBT-048 (Low): table widening 6→9 columns + placeholder token rename `_TBD_` → `_AWAITING_OPERATOR_FIRST_RUN_` deferred since they conflict with the autonomous-shipping `_TABLE_PATTERN` rewriter and 2 existing tests; explicit semantics documented in surrounding prose. **Part B (operator action, post-seal)**: one-time live Binance read-only fetch + first-time number population per the runbook; not blocking any further phase. pytest 1311 → 1348 (+37 across all 25.x sub-tasks); ruff/mypy/black clean throughout; reviewers 🟢🟢 on 25.1 and 25.2; 25.3 Part A docs-only (no review needed; gates re-checked clean). Cross-check `docs/cross-checks/2026-05-01-phase-25-snapshot-pinned-baselines.md` PASS. Session logs: `docs/sessions/2026-05-01-phase-25.1-snapshot-format.md`, `docs/sessions/2026-05-01-phase-25.2-snapshot-cli.md`, `docs/sessions/2026-05-01-phase-25.3-and-phase-25-partial-seal.md`. |

### DEBT-044: `FeedbackLoop.save_state` not migrated to `atomic_write_text` ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-05-01 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 26.1 migrated `FeedbackLoop.save_state` (`src/feedback/loop.py:440`) from direct `Path.write_text(record.model_dump_json(indent=2), encoding="utf-8")` to `atomic_write_text(path, record.model_dump_json(indent=2))`. Output bytes byte-identical pre/post; only durability semantics changed (crash mid-write now leaves the prior state intact instead of producing a half-written file). Regression test `test_save_state_crash_preserves_prior_snapshot` injects `OSError` mid-write via `monkeypatch.setattr(...atomic_write_text..., raise OSError)` and asserts the prior bytes load cleanly. The other `Path.write_text` site in `feedback/loop.py:677` (`_promote_file`) was explicitly out of scope (fresh-path technique markdown write, not load → mutate → save). pytest 1348 → 1349 (+1); ruff/mypy/black clean. QA verdict: 🟢 ship. Session log: `docs/sessions/2026-05-01-phase-26.1-atomic-write-completion.md` (forthcoming via the seal commit). |

### DEBT-045: `Backtester._save_result` single-write not atomic ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-05-01 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 26.1 migrated `Backtester.save_result` (`src/backtest/engine.py:1106`) from `open(path, "w") + json.dump(payload, f, indent=2)` to `atomic_write_text(path, json.dumps(payload, indent=2))`. Output bytes byte-identical pre/post per CPython stdlib guarantee (`json.dump` is a thin wrapper over `json.dumps`); only durability semantics changed. Two regression tests pin the contract: `test_save_result_crash_leaves_no_half_written_file` (no prior file → fresh write injected with `OSError` → asserts no half-written file present) and `test_save_result_crash_preserves_prior_result` (prior file → mid-write injected → asserts prior bytes intact). pytest 1349 → 1351 (+2); ruff/mypy/black clean. QA verdict: 🟢 ship. Session log shared with DEBT-044 (Phase 26.1). |

### DEBT-035: `Trade` model in `src/models.py` is dead code ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 26.2 deleted the `Trade` Pydantic class from `src/models.py` (lines 199-227). Verified no instantiations or imports across `src/` or `tests/` (`grep -rn "from src.models import.*Trade\b"` and `grep -rn "models\.Trade\b"` both returned only `TradeHistory` / `BacktestTrade` siblings). Replaced 3 prior `TestTrade` test cases with single `TestTradeRemoved::test_trade_symbol_no_longer_resolves` regression that asserts `from src.models import Trade` raises `ImportError` (pinning the deletion against accidental reintroduction). Live / paper / backtest layers all use `TradeHistory` (`src/strategy/performance.py`) or `BacktestTrade` (`src/backtest/engine.py`); no callers needed to be updated. pytest 1351 → 1349 (-2 net from removing the 3 `TestTrade` tests + adding 1 regression; offset later in 26.2 cycle). |

### DEBT-036: Calendar-month math approximated via `30 * months` ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 26.2 replaced `cutoff = now - timedelta(days=30 * retention_months)` at `src/proposal/interaction.py:438` with `cutoff = now - relativedelta(months=retention_months)` from `dateutil.relativedelta`. Calendar-correct cutoff (no ~5-day-per-year drift). `python-dateutil>=2.8.2` added to runtime deps; `types-python-dateutil>=2.8` to dev deps. Two new regression tests pin the calendar boundary: `test_purge_old_uses_calendar_months_not_30_day_approximation` (record dated `2025-01-17` with `retention_months=12` from `2026-01-15` is *kept* — inside true calendar cutoff, would have archived under legacy `30*12=360 day` cutoff) and `test_purge_old_calendar_cutoff_archives_record_just_outside` (record dated `2025-01-14` is archived). pytest unchanged on calendar correctness; ruff/mypy/black clean. |

### DEBT-040: Two `# type: ignore[arg-type]` comments in `proposal/engine.py` undocumented ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 26.2 documented both `# type: ignore[arg-type]` sites at `src/proposal/engine.py:519,555` with the underlying-type-mismatch rationale: `tf` / `timeframe` are `str` in the calling layer (multi-technique scan) but `BaseExchange.get_ohlcv(timeframe: Literal[...])` is stricter. Strategy authors are trusted to declare valid timeframes via frontmatter; runtime validation happens at the exchange call site. Tightening the type properly would require a wider refactor (`StrategyInfo.timeframes` + every strategy frontmatter loader); deferred. The comment at each ignore site names the upstream type and the "out of scope for 26.2" boundary so future reviewers can act on the underlying drift if it ever fires in production. mypy clean on `src/proposal/engine.py`. |

### DEBT-041: `RuntimeEngine` accesses `ProposalInteraction._decision_callback` privately ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 26.2 added public `ProposalInteraction.set_decision_callback(callback: ProposalDecisionCallback)` setter (`src/proposal/interaction.py:516`) with docstring citing DEBT-041 rationale. `RuntimeEngine.__init__` (`src/runtime/engine.py:264`) now calls `proposal_interaction.set_decision_callback(self._auto_decide)` instead of mutating the private `_decision_callback` attribute; the `# type: ignore[attr-defined]` was dropped. Two new regression tests pin the contract: `test_set_decision_callback_swaps_callback_used_by_present` (setter overrides the constructor-injected callback at runtime) and `test_set_decision_callback_is_idempotent_with_default_constructor` (works on a default-constructed instance with no prior callback). mypy clean (no `[attr-defined]` ignore needed). |

### DEBT-048: `docs/baselines.md` table widening + placeholder rename ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-05-01 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 26.2 closed both spec deviations from Phase 25.3 Part A in lockstep. (1) `docs/baselines.md` table widened from 6 columns (`Strategy / Symbol / Period / Win Rate / Sharpe / MDD`) to 9 columns (`Strategy / Symbol / Timeframe / Trades / Win Rate / Sharpe / MDD / Total PnL (USDT) / Snapshot fetched_at`). (2) Placeholder token renamed `_TBD_` → `_AWAITING_OPERATOR_FIRST_RUN_`, exposed as `PLACEHOLDER_TOKEN` constant in `scripts/backtest_baselines.py:473` so future authors don't hard-code the literal. `_TABLE_HEADER`, `_TABLE_PATTERN`, `render_table`, `build_summary`, `write_baseline_artifacts`, `run_baseline`, and `run_all` updated in lockstep — `run_all` now threads `SnapshotMetadata.fetched_at` through to the docs table when running off `--snapshot`. Three pre-existing tests rewritten (`test_run_all_skips_doc_update_when_disabled`, `test_update_baselines_doc_replaces_tbd_rows`, period-startswith assertion); two new tests pin the 9-column layout (one all-fields-populated, one with `total_pnl`/`fetched_at` missing → graceful `PLACEHOLDER_TOKEN` fallback). pytest 1351 → 1355 (+4 net across 26.2 fixes); ruff/mypy/black clean. |

### DEBT-038: Notification dispatch failures swallowed without `NOTIFICATION_FAILED` event ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 26.3 added `ActivityEventType.NOTIFICATION_FAILED` (`src/runtime/activity_log.py`) with structured-fields docstring contract (`proposal_id`, `symbol`, `dispatcher_name`, `error_type`, `error_message`). The notifier `try/except` at `src/runtime/engine.py:451` now follows **emit-then-swallow** policy (lead's decision to preserve existing semantics — re-raising would change behavior beyond observability scope): logs warning (existing), appends `NOTIFICATION_FAILED` event with the structured payload + cycle_id, continues. Operators see notifier-reliability on the dashboard the same way they see `LLM_TIMEOUT`. Regression test `test_notifier_failure_emits_notification_failed_event` injects an `AsyncMock(side_effect=RuntimeError(...))` notifier (real raise, not stub), runs full `engine.run_cycle()`, asserts the event lands once with all 5 payload fields AND that proposal still flows through accept/open (behavior preservation pinned). pytest 1355 → 1356 (+1); ruff/mypy/black clean. QA verdict: 🟢 ship. |

### DEBT-039: Logger module global `_initialized_loggers` blocks handler reset ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 26.3 wired the public, idempotent `reset_loggers()` helper (already present in `src/logger.py`) into pytest test isolation. New `tests/conftest.py` autouse fixture calls `reset_loggers()` before and after each test (clears `_initialized_loggers` set + removes handlers from each tracked logger). Idempotent — does not collide with the per-file `clean_loggers` fixture in `tests/test_logger.py`. New regression test `test_clears_initialized_loggers_set_and_is_idempotent` pins the contract (handlers cleared on the same logger object, `_initialized_loggers == set()` after reset, second call is a no-op). `propagate = False` left untouched — out of scope (would require auditing all log-routing assumptions). pytest 1356 → 1357 (+1); ruff/mypy/black clean. QA verdict: 🟢 ship. |

### DEBT-047: Backtester has no leverage-liquidation modeling — `balance` can go arbitrarily negative without LIQUIDATED analogue ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-05-01 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 26.4 added structural marker + rollup with **no PnL math change** (observability only; backtester continues simulating after threshold crossing so existing analysis tools don't break, but downstream consumers can detect and surface "this strategy would have been liquidated at trade N"). New `BacktestConfig.liquidation_threshold: Decimal = Decimal("0")` field with rationale docstring (literal-zero default per lead policy; recommends `Decimal("1000")`-against-`Decimal("10000")`-initial = ~10% maintenance-margin proxy as the operationally useful setting). `BacktestTrade.liquidated: bool = False` structural marker (set when `balance_after_close ≤ threshold` per quant invariant — intra-trade dips are MDD's job, not liquidation). `BacktestResult.liquidated: bool = False` rollup (`any(t.liquidated for t in trades)`). New `Backtester._mark_if_liquidated(trade, balance)` helper wired into all 4 trade-close sites (single-TF + multi-TF × intra-candle + end-of-data). Equity curve **truncated** at first liquidating trade's `exit_time` so analyzer MDD/Sharpe don't compute against post-liquidation phantom bars (cleaner than per-point `liquidated` field on `EquityPoint` which is `frozen=True` and would break back-compat). `ActivityLog` deliberately not wired into the backtester — backtester is offline simulation; Phase 22.2's `LIQUIDATED` ActivityEvent already covers the live paper-trader path. 4 new regression tests in `TestBacktesterLiquidationParity`: liquidating trade marks (with `risk_percent=100 + slippage_bps=20 + fee_rate=0.001` to force literal-zero crossing), solvent run leaves no marker + preserves full equity-curve length, positive threshold (1000 of 10000) catches earlier than zero, default pin. pytest 1357 → 1361 (+4); ruff/mypy/black clean. Quant verdict: 🟢 ship (sizing-cap concern flagged: with `risk_percent ≤ 5%` literal-zero default rarely fires, positive threshold is operationally useful — addressed by docstring polish). QA verdict: 🟢 ship. |

### DEBT-042: `pyproject.toml` `black --check` formatter gate dormant; 47 files unformatted ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-30 |
| **Resolved** | 2026-05-01 |
| **Resolution** | Phase 26.5 ran `black src tests scripts` as a one-shot sweep + commit (lead chose this path over dropping black from `pyproject.toml`). 21 files reformatted (5 src + 1 scripts + 15 tests; the original "47 files" count cited in the audit had reduced through Phase 22-24 cycles which black-formatted some of the affected files inline as part of their touched-file gate). pytest 1361 → 1361 (zero delta — pure formatter, exactly as expected). ruff/mypy clean. `black --check src tests scripts` was **failing pre-sweep** (21 file delta) and is now **passing post-sweep** (115 files clean) — the gate is now enforceable. QA verdict: 🟢 ship — spot-checked 3 random files for logic-change smell, every diff is line-wrapping / paren-style collapse / whitespace; no conditional restructuring, no operator changes, no string-content edits, no parameter reordering. Two adjacent f-string concat warts at `src/trading/live.py:356` and `src/tools/purge_proposals.py` (purge message) noted as cosmetic-only follow-up; behaviour unchanged. Observational note for future planning: project has no `.github/workflows/` or `.pre-commit-config.yaml`, so the gate is *enforceable* (passes when run) but is still a *manual* gate; CI infrastructure is a separate phase if the lead wants automated regression blocking. |

---

## Statistics

| Metric | Value |
|--------|-------|
| Total Active | 2 |
| Critical | 0 |
| High | 0 |
| Medium | 2 |
| Low | 0 |
| Resolved (All Time) | 64 |

---

## Change History

| Date | Action | Item |
|------|--------|------|
| 2026-05-24 | Updated | DEBT-068 `cross-account-risk-policy` Slice 2(b) narrowed to opt-in global exposure caps: `enabled` defaults false, paper mode is advisory / would-block only and never hard-blocks in v1, and live mode hard-blocks only when the operator explicitly enables the global policy. This preserves per-account paper-lab performance measurement while keeping the live-money safety path available. |
| 2026-05-13 | Resolved | DEBT-066 In-memory mark-price cache for cap-blocker `unrealized_pnl_percent` (Low) — same-day close-out bundled with DEBT-064; `_mark_price_cache: dict[str, MarkPriceEntry]` added to `TradingEngine` (instance attr alongside `_market_regime_cache`); `MarkPriceEntry` is a frozen dataclass carrying `price: Decimal` + `observed_at: datetime`; populated at 3 existing ticker-fetch sites (`_monitor` SL/TP at L3243, orphan force-close at L3147, `_record_portfolio_snapshot` at L3431) — zero new exchange calls; `_get_cached_mark_price(symbol, *, max_age_seconds=300.0)` returns the cached price if fresh, else `None`; `_build_cap_blocker_payload` consumes from the cache (long `(mark - entry)/entry × 100`, short `(entry - mark)/entry × 100`, matching `pnl_for_trade` sign convention); cache-miss `None` fallback preserved as regression-safe behavior for the prior DEBT-066-pre-fix contract; 6 new tests in `tests/test_runtime_engine.py` (cache population, fresh/stale read, cap-blocker consumption, short-side sign convention, cache-miss fallback); stale entries intentionally retained (next write overwrites); memory bound by traded-symbol universe; pytest 2078 passed (was 2061; net +17 across bundled DEBT-064 + DEBT-066, zero regressions); ruff clean; `mypy src` repo-wide clean milestone preserved (88 source files, zero issues) |
| 2026-05-13 | Resolved | DEBT-064 Runtime-reconciliation taxonomy gaps — stale-but-valid + half-closed rows (Low) — same-day close-out bundled with DEBT-066; added `is_stale` auxiliary signal to `OpenTradeClassification` (independent of `state` — an `unrecoverable` row can also be stale) with 7-day default threshold via `DEFAULT_STALE_THRESHOLD_SECONDS`; threshold configurable per-call via new `now` + `stale_threshold_seconds` kwargs on `classify_open_trade`; uses `entry_time` as the conservative lower-bound proxy for `last_seen_at` (TradeHistory has no `last_seen_at` field today); new `compute_closed_but_malformed_count(data_dir, sub_account_id) -> int` sweep counts `status="closed"` rows where `exit_price IS NULL` or `exit_time IS NULL` — the `close_unrecoverable_paper_trades` partial-failure shape now surfaces in the health report; both aux signals reported per-sub-account and at totals level by `compute_health_report` (`stale_count` + `closed_but_malformed_count`); existing `_load_open_trade_rows` open-row filter intentionally untouched; 10 new tests in `tests/test_runtime_reconciliation.py` (positive/negative stale cases, custom threshold, missing entry_time fallback to `is_stale=False`, both null-branch closed-malformed cases, end-to-end health-report aux signals); pytest 2078 passed (was 2061; net +17 across bundled DEBT-064 + DEBT-066, zero regressions); ruff clean; `mypy src` repo-wide clean milestone preserved (88 source files, zero issues) |
| 2026-05-13 | Resolved | DEBT-070 `proposal-runtime` strategy-selection ranking reads `total_trades` instead of `real_trade_count` (Low) — same-day close-out bundled with DEBT-067; 4 ranking-side `perf.total_trades` reads in `ProposalEngine._select_best_technique` (`src/proposal/engine.py:996, 1010, 1014`) and `_select_all_techniques` (`src/proposal/engine.py:1132`) switched to `perf.real_trade_count` with inline `# DEBT-070:` comments at each site (`any_history` detection L996, tie-breaker sort key L1010, `_select_best_technique` return-perf gate L1014, `_select_all_techniques` return-perf gate L1132); display sites at `src/dashboard/pages/strategies.py:118` and `src/ai/improver.py:667` intentionally remain on `total_trades` (operator-facing record counts); 2 new tests in `tests/test_proposal_engine.py` — `test_select_best_technique_tiebreaks_on_real_trade_count` (canonical defect: equal `avg_pnl`, A=10 synthetic/0 real, B=0 synthetic/5 real → B wins; pre-fix A would have won via `-perf.total_trades` tie-breaker) and `test_select_best_technique_any_history_ignores_synthetic_only` (synthetic-only beta does NOT register as "has history" → cold-start lex-first picks alpha); pytest 2061 passed (was 2059; net +2, zero regressions); ruff clean; `mypy src` fully clean repo-wide (88 source files, zero issues) |
| 2026-05-13 | Resolved | DEBT-067 Pre-existing `src/dashboard/app.py` mypy errors (Low) — same-day close-out bundled with DEBT-070; `DashboardMode` type alias reordered before `COMMAND_CENTER_DEFAULT_MODE` at `src/dashboard/app.py:285` with the constant now annotated `: DashboardMode = "paper"` to carry the literal type; `render_command_center_links` parameter (`src/dashboard/app.py:869, 882`) widened from `list[...]` to `Sequence[...]` (covariant read-only over the param), `Sequence` added to the existing `collections.abc` import; `mypy src/dashboard/app.py` clean post-fix; **`mypy src` now fully clean repo-wide for the first time this session — `Success: no issues found in 88 source files`, zero issues** — the 3 errors had been a QA-noise filter across the past 4 unit cycles (DEBT-061, market-regime, runtime-reconciliation, proposal-funnel-audit); candidate future-work item flagged in session log (optional CI gate to lock the repo-wide-clean baseline, NOT filed as DEBT pending explicit user approval) |
| 2026-05-13 | Resolved | DEBT-063 Market-regime classifier hysteresis flapping (Medium) — `classify_regime_detailed` (`src/runtime/market_regime.py`) now requires the last 2 candles to BOTH sit on the new side of the ±2% band before flipping out of `sideways` per quant Q4's recommendation; threshold unchanged (preserves `RobustnessGate._classify_regimes` parity at `src/backtest/validator.py:929-959` for backtest/live consistency); defensive `len(ohlcv) < 2 → sideways` short-circuit positioned after the existing `insufficient_data` / `stale_data` → `unknown` checks; 8 existing single-bar fixtures across `tests/test_market_regime.py` + `tests/test_runtime_engine.py` updated to 2-bar tails (SMA(200) baseline recomputation `100.015 → 100.03` matches `(198×100 + 2×103)/200`); 4 new tests pin both bull/bear two-bar confirmation + both-confirm-flip behavior; pytest 2059 passed (was 2054; net +5 across both DEBT-062 + DEBT-063, zero regressions); ruff + mypy clean |
| 2026-05-13 | Resolved | DEBT-062 Market-regime gate sequencing (Medium) — `_market_regime_gate` relocated after `_correlation_gate` in `_handle_proposal` (`src/runtime/engine.py`) per quant Q1's recommendation; new gate order `score → correlation → market_regime → strategy_action → trend → ...` ensures when both gates would block, the directly-actionable correlation rejection (with its blocking-trade diagnostic) surfaces on the operator dashboard instead of the non-actionable regime signal; per-cycle regime cache means the relocation has zero OHLCV-fetch cost; pinned by new `tests/test_runtime_engine.py::test_correlation_gate_runs_before_regime_gate` which constructs a both-blocking fixture (correlation conflict + bear regime against `allowed_regimes=["bull"]`) and asserts the correlation event wins; pytest 2059 passed, ruff + mypy clean |
| 2026-05-13 | Resolved | DEBT-065 Synthetic reconciliation-close rows leak into live-promotion gating (Medium) — same-day fix per option (b) from the DEBT-065 suggested resolution; new `TechniquePerformance.real_trade_count` property (`total_trades - synthetic_count`) added on `src/strategy/performance.py`; `ProposalEngine._cold_start_blocks_live` (`src/proposal/engine.py:1062-1068`, incl. `per_technique_trades` / `max_trades_observed` payload) and `_score.sample_size` derivation (`src/proposal/engine.py:1199-1209`, flowing into `sample_factor`) switched to read it; `total_trades` semantics preserved for operator-facing display (`src/dashboard/pages/strategies.py:118` "Total Trades" column + `src/ai/improver.py:667` prompt rendering); canonical 9+2 defect at threshold 10 now correctly blocks at `_cold_start_blocks_live`; boundary at 10 real + 5 synthetic correctly admits; tests +3 in `tests/test_strategy_performance.py` (property arithmetic) + 4 in `tests/test_proposal_engine.py` (canonical 9+2 defect, 10-real boundary, `_score` 8+3, all-synthetic collapses to cold-start); pytest 2054 passed (was 2047; net +7, zero regressions); ruff + mypy clean; QA-surfaced follow-up filed as DEBT-070 |
| 2026-05-13 | Added | DEBT-070 `proposal-runtime` strategy-selection ranking reads `total_trades` instead of `real_trade_count` (Low) — surfaced from QA during DEBT-065 close-out (`docs/sessions/2026-05-13-debt-065-synthetic-row-leak-fix.md`); 4 additional `perf.total_trades` reads in `ProposalEngine._select_best_technique` / `_select_all_techniques` at `src/proposal/engine.py:996, 1010, 1014, 1132` (QA corrected dev's :1128 mis-cite to :1132) affect strategy-selection ranking — not promotion gating — so DEBT-065 correctly stayed in scope (gating-only); with current `total_trades` semantics, a strategy with only synthetic reconciliation-close rows registers as "has history" (line 996), wins tie-breakers over real-history-light strategies (line 1010), and passes through downstream as if it had history (lines 1014, 1132); blast radius is narrow (operator-driven path, composite/edge dominates the actual scoring formula) but synthetic-heavy strategies can win "best technique" ranking on a per-(symbol, sub-account) cycle over genuine cold-start strategies; suggested resolution is the same pattern as the DEBT-065 fix (switch all 4 reads to `perf.real_trade_count`) plus regression tests pinning that a synthetic-heavy strategy does NOT win ranking over a real-history strategy at equal composite; display sites at `src/dashboard/pages/strategies.py:118` and `src/ai/improver.py:667` intentionally remain synthetic-inclusive (operator-facing counts) |
| 2026-05-13 | Added | DEBT-069 `strategy-tuning` Slice 2 umbrella (Medium) — filed at the close of `strategy-tuning` Slice 1 (2026-05-13); Slice 1 shipped the state machine + recommender + runtime gate (`StrategyAction` enum + `StrategyTuningPolicy` frozen-Pydantic config with per-account + per-strategy override fall-through; pure `recommend_action` recommender with priority `pause → shadow → scout → retune → keep → promote`; `_strategy_action_gate` wired after `_correlation_gate` with 6 action behaviors — keep/promote pass-through, retune pass-through + `RETUNE_FLAGGED` advisory, scout scales `proposal.quantity *= scout_size_factor`, shadow persists `shadow=True` record without opening, pause rejects with `gate_rejected_strategy_action_pause`; 2 new `ProposalFinalState` terminals + funnel plumbing) at ~805 LoC well under the 1200-LoC scope-split guard; Slice 2 wires the remaining surfaces per the functional-design spec plus 3 quant-trader-expert follow-ups (Q1 threshold calibration after first 2 weeks of paper evidence, Q2 true profit-factor computation replacing the `_infer_profit_factor` approximation, Q5 pause-reason split between evidence-driven and gate-config-driven causes) and 2 QA follow-ups (funnel `_STATE_TO_FIELD` aggregator coverage gaps for the 2 new states) — (a) dashboard view + YAML clipboard helper (spec Step 4); (b) initial-action seeding for named strategy families per spec §"Initial Actions"; (c) observation store for recommendation history analogous to `PromotionObservationStore`; (d) `STRATEGY_ACTION_APPLIED` emission (enum reserved at `src/runtime/activity_log.py` but never emitted); (e) true profit-factor computation via new `gross_win_pct`/`gross_loss_pct`/`max_drawdown_pct` on `TechniquePerformance.from_records`; (f) split `pause` reason; (g) threshold calibration (widen `scout.sample_size_max` to ~15 to align with `keep.sample_size_min`); (h) shadow-aware filter defensive comment in `src/strategy/performance.py::from_records`; (i) funnel unit-test gaps — append `GATE_REJECTED_STRATEGY_ACTION_PAUSE` to `test_gate_rejected_total_sums_every_gate_bucket` and `GATE_REJECTED_STRATEGY_ACTION_PAUSE` + `SHADOW_RECORDED` to `test_score_accepted_total_sums_every_post_score_state`; suggested sequencing — (a)+(b)+(c) bundle as the dashboard pass, (d) bundles cheaply with (a), (e) is its own cycle (recalibrates thresholds), (f) bundles with (e), (g) is post-evidence calibration, (h) and (i) are mechanical follow-up commits |
| 2026-05-13 | Added | DEBT-068 `cross-account-risk-policy` Slice 2 umbrella (Medium) — filed at the close of `cross-account-risk-policy` Slice 1 (2026-05-13); Slice 1 shipped schema extensions + `compute_risk_budget_size` pure helper + 2 of 5 planned gates (`_account_aggregate_cap_gate` notional + stop-risk, `_stale_position_block_gate`) under the 1357-LoC scope-split guard (~706 LoC actual); Slice 2 wires the remaining surfaces per the functional-design spec — (a) `compute_risk_budget_size` wire-in to `ProposalEngine` + removal of the `_reject_risk_budget_mode_until_wired_in` validator added in R2 as a footgun-prevention measure; (b) global symbol/side caps with cross-sub-account state aggregation; (c) per-account + portfolio kill switches with realized-PnL-since-UTC-midnight aggregation + persisted state surviving restart; (d) operator freeze toggle reload-per-cycle infrastructure; (e) stale `auto_close` + `alert_only` actions (monitor-loop hook + interaction matrix with `runtime-reconciliation` state taxonomy); (f) dashboard exposure panel matching the runtime-reconciliation banner color pattern; (g) dedicated `RISK_CAP_ADVISORY` `ActivityEventType` migrating paper-mode emissions off the current `PROPOSAL_REJECTED + details.advisory=True` reuse; (h) `runtime-safety-score` integration of kill-switch triggers; suggested sequencing — (a) first as a small slice, then (b)/(c)/(e)/(f)/(g) sequentially, with (d) and (h) bundling into (f); risk-budget sizing mode is currently fail-closed at `RiskPolicy` validation until (a) lands |
| 2026-05-13 | Added | DEBT-067 Pre-existing `src/dashboard/app.py` mypy errors (Low) — QA observation across the past 4 unit cycles (DEBT-061, market-regime, runtime-reconciliation, proposal-funnel-audit); 3 errors at lines 285 (Literal default), 869, 882 (List invariance / Sequence covariance) make `mypy src` not fully clean repo-wide and force reviewers to filter known noise on every diff; resolution is a mechanical 2-line + 2-line fix (explicit `Literal[...]` cast at 285, `list[X]` → `Sequence[X]` covariant-read parameters at 869 + 882) |
| 2026-05-13 | Added | DEBT-066 In-memory mark-price cache for cap-blocker `unrealized_pnl_percent` (Low) — surfaced from quant-trader-expert (Q1) during proposal-funnel-audit unit close-out review; R1 of `_build_cap_blocker_payload` did per-blocker `await exchange.get_ticker()` on the hot path (10+ sequential ticker fetches per cap rejection, and cap rejections are the dominant rejection path per the 2026-05-13 Fly snapshot); R2 dropped the fetch and set `unrealized_pnl_percent=None` per the spec's documented fallback, but no in-memory mark cache exists anywhere in `src/runtime/engine.py` / `src/trading/portfolio.py` / `src/trading/paper.py` (`PortfolioManager` only sees marks via `record_snapshot(current_prices=...)`); suggested resolution is a `dict[str, Decimal]` cache on `TradingEngine` populated by `_record_asset_snapshot` + the monitor-pass ticker reads (which already happen) with TTL or last-seen-timestamp freshness — zero new exchange calls on the rejection path; not a money-handling defect, first-order signal (`entry_price + age_seconds + monitorable + symbol + record_id`) intact |
| 2026-05-13 | Added | DEBT-065 Synthetic reconciliation-close rows leak into live-promotion gating (Medium) — surfaced from QA during runtime-reconciliation final review; `TechniquePerformance.total_trades = len(records)` (`src/strategy/performance.py:244`) includes synthetic reconciliation-close rows, and `ProposalEngine._cold_start_blocks_live` (`src/proposal/engine.py:1061-1064`) + `_score.sample_size` (`src/proposal/engine.py:1200`) read it directly, so a strategy with 9 real + 2 synthetic closes can pass `threshold=10` live promotion despite `src/strategy/performance.py:214`'s comment explicitly stating synthetic rows "must not feed CON-003 promotion gating"; smaller-diff resolution is option (b) — switch the two consumer sites to `perf.total_trades - perf.synthetic_count` (or a new `real_trade_count` property) and update `tests/test_strategy_performance.py:2066` to match; narrow blast radius (operator-driven path, conservative threshold) but contract gap grows with every operator reconciliation event |
| 2026-05-13 | Added | DEBT-064 Runtime-reconciliation taxonomy gaps — stale-but-valid + half-closed rows (Low) — surfaced from quant-trader-expert (Q1) during runtime-reconciliation unit close-out review; `OpenTradeState` (`monitorable`/`degraded`/`unrecoverable`/`legacy_no_perf_link`) covers ledger-shape but misses (a) stale-but-valid rows whose monitor loop hasn't ticked in >N days (currently classified `monitorable`) and (b) half-closed rows (`status="closed"` with no `exit_price`/`exit_time` — `_load_open_trade_rows` at `src/runtime/reconciliation.py:286` filters by `status == "open"` so they're never classified, yet `close_unrecoverable_paper_trades` can write exactly this shape on partial failure); suggested resolution is auxiliary signals on the existing classifier (per-row warning counter from `last_seen_at` vs `now` for (a); separate "closed-but-malformed" sweep pass for (b)) rather than new enum states |
| 2026-05-13 | Added | DEBT-063 Market-regime classifier hysteresis flapping (Medium) — surfaced from quant-trader-expert (Q4) during market-regime unit close-out review; single-candle band crossings flip the regime label every cycle when price chops in the 1.5%-2.5% range around SMA(200), producing correlated entries at the band edges and noise-driven strategy throughput; suggested resolution is two-bar confirmation in `classify_regime_detailed` (`src/runtime/market_regime.py:207-217`) — keep the ±2% threshold (matches `RobustnessGate._classify_regimes` at `src/backtest/validator.py:929-959`), change the rule not the number |
| 2026-05-13 | Added | DEBT-062 Market-regime gate sequencing (Medium) — surfaced from quant-trader-expert (Q1) during market-regime unit close-out review; `_market_regime_gate` is wired before `_correlation_gate` in `_handle_proposal` (`src/runtime/engine.py:1089-1131`), so when both gates would block, the non-actionable regime signal displaces the directly-fixable correlation signal on the operator dashboard; suggested resolution is to move the regime call below the correlation call (per-cycle cache means relocation has zero OHLCV cost) |
| 2026-05-13 | Resolved | DEBT-061 Per-strategy proposal-engine fail-closed-rate metric for dashboard observability — same-day filing-and-close scope-split from DEBT-060; new `src/proposal/fail_closed_metrics.py` (`StrategyFailClosedCounts` Pydantic model with `Field(ge=0)` re-validated via `model_validate(...)` on every increment + `FailClosedMetricsTracker` writing `data/performance/<sub_account_id>/<technique_name>/fail_closed.json` via `atomic_write_text`); three increment sites threaded into `ProposalEngine._build_proposal_for_strategy` (emit, `StrategyError` catch, `TradingValidationError` catch) with OSError-tolerant helpers so observability never crashes the hot path; `sub_account_id` plumbed as per-call argument on tracker public methods (second-round 🔴 fix per quant Q3 option (a) after first round had bound it at constructor and would have aggregated all sub-accounts under `default/`); `src/main.py` wires `FailClosedMetricsTracker()` into `_build_engine_config_phase`; `src/dashboard/pages/strategies.py` adds `Emitted` / `Fail-Closed` / `Fail-Closed %` columns scoped under the `fail_closed_tracker is not None` branch (avoids MagicMock-spec test breakage); quant Q1/Q2/Q4 ratified-as-shipped (Q1: pre-emit outage = neither counter; Q2: neutral = emitted only; Q4: per-reason breakdown deferred as non-breaking `Dict[str, int]` extension); `pytest -q` 1843 passed (net +31); `ruff check src tests` clean; targeted `mypy` clean |
| 2026-05-13 | Added | DEBT-061 Per-strategy proposal-engine fail-closed-rate metric for dashboard observability (Low) — surfaced from quant-trader-expert during DEBT-060 close-out review; observability scope-split from DEBT-060 (silent ~50% RSI throughput collapse went undetected for ~12 days because per-strategy fail-closed rates are not aggregated on the dashboard); resolution shape is `proposals_emitted` / `proposals_fail_closed` counter pair persisted alongside performance data + Strategies-page "fail-closed rate" column, optionally with per-reason breakdown (R/R floor, ATR-data-insufficient, sizing-failed, correlation-rejected); explicitly *not* a regression of `14ca04c` |
| 2026-05-13 | Resolved | DEBT-060 RSI baseline family TP-distance redesign for 2.0 R/R floor — `TAKE_PROFIT_PCT` raised from 0.04 → 0.05 across `strategies/rsi.py`, `strategies/rsi_4h.py`, `strategies/rsi_15m.py` in commit `14ca04c` (path (a) from the DEBT-060 options list); quant-ratified math gives post-widen R/R floor = 2.22 on the binding 4h-alt case (worst-case widened SL ~2.25% vs TP 5%), safely above the 2.0 gate; regression coverage added today via `tests/test_rsi_variants.py::test_all_rsi_variants_pin_take_profit_pct_at_0_05` (TP constant pin + no-shadow assertions on sibling files) and parametrized `tests/test_proposal_engine.py::test_rsi_variants_clear_rr_floor_under_worst_case_widening` (3-row positive R/R floor mirror under per-TF worst-case widening); pytest 1812 passed (net +4); dashboard fail-closed-rate metric scope-split to DEBT-061 |
| 2026-05-13 | Resolved | DEBT-056 Pre-existing test flake + ruff I001 import-order hits — `ruff --fix` cleared the 2 lint sites; 6 fixture-vs-validator drift failures resolved by adding `## Output Contract` block to `GOOD_RESPONSE` (fixes 4 markdown-pick tests at `src/ai/improver.py:425`) and adding `"hypothesis"` to `GOOD_PYTHON_STRATEGY` + `TRADE_PRODUCING_PYTHON_STRATEGY` `TECHNIQUE_INFO` (fixes 2 code-type tests at `src/ai/improver.py:374`); corrected the prior all-`:374` split to the accurate 2×`:374` + 4×`:425` split; production validators untouched; pytest 1808 passed |
| 2026-05-13 | Resolved | DEBT-055 CH-27 multi-TF parity test gaps — landed 4 parity-variant tests (slippage, liquidation, short-side, true non-degenerate multi-TF divergence) in `tests/test_backtest_engine.py::TestRunMultiTimeframeParity`; divergence test pins multi-TF warmup contract via strict-subset entry-bar indices; superseded `test_single_and_multi_tf_modes_share_closed_trade_ledger` deleted outright |
| 2026-05-13 | Updated | DEBT-056 Pre-existing test flake refreshed — failure count widened from 1 → 6 tests in `tests/test_scripts_auto_research_candidates.py` on clean tree (all 6 fail through the same `GeneratedTechniqueError` path); raise-site line corrected from `src/ai/improver.py:425` to `src/ai/improver.py:374` |
| 2026-05-12 | Resolved | DEBT-059 PaperBalance.locked not reconciled across runtime restart — added atomic per-sub-account `balances.json` snapshots, snapshot-first startup load, and one-time legacy open-position balance reconciliation |
| 2026-05-12 | Resolved | DEBT-058 production trades.json backfill for legacy SL/TP-null rows — confirmed and documented the existing `src.tools.backfill_paper_sl_tp` one-shot operator tool and its targeted test coverage |
| 2026-05-12 | Resolved | DEBT-057 paper-mode entry-fee not persisted to TradeHistory — persisted entry fees at open time and changed close-time fee addition to pass only the exit fee |
| 2026-05-10 | Added | DEBT-060 RSI baseline family TP-distance redesign for 2.0 R/R floor (Medium) — Flagged by senior-developer during P1 (I) (commit 7e9162e); RSI rr_med=2.00 in 12-day Fly data, ~50% throughput drop expected after R/R floor + SL widening interact |
| 2026-05-10 | Added | DEBT-057 paper-mode entry-fee not persisted to TradeHistory (Medium) — Surfaced by P0 trading-correctness work (commits 36eb2f3 / 4428035 / 9f57708) |
| 2026-05-10 | Added | DEBT-058 production trades.json backfill for legacy SL/TP-null rows (High) — Surfaced by P0 trading-correctness work (commits 36eb2f3 / 4428035 / 9f57708) |
| 2026-05-10 | Added | DEBT-059 PaperBalance.locked not reconciled across runtime restart (High) — Surfaced by P0 trading-correctness work (commits 36eb2f3 / 4428035 / 9f57708) |
| 2026-05-09 | Added | DEBT-055 CH-27 multi-TF parity test gaps (Medium) — surfaced during CH-27 close-out; quant-trader-expert flagged 4 parity variants (slippage, liquidation, short-side, non-degenerate multi-TF) not covered by the new `TestRunMultiTimeframeParity` regression pair; older `test_single_and_multi_tf_modes_share_closed_trade_ledger` superseded and queued for removal/rescope |
| 2026-05-09 | Added | DEBT-056 Pre-existing test flake + ruff I001 import-order hits (Low) — surfaced during CH-27 close-out QA full-suite run; `tests/test_scripts_auto_research_candidates.py::test_run_picks_orchestrates_each_candidate` fails on clean tree from `src/ai/improver.py:425`; two pre-existing ruff I001 hits at `src/dashboard/pages/engine.py:25` and `tests/test_backtest_validator.py:3` |
| 2026-05-07 | Resolved | DEBT-022 Cumulative / rate-based breaker counterpart — added single-TF and multi-TF cumulative parse-failure-rate aborts plus env-backed thresholds |
| 2026-05-06 | Resolved | DEBT-052 Per-sub-account notification routing overrides — added `notification_route` refs, env-backed route-specific Slack webhook map, and runtime routed dispatcher wiring |
| 2026-04-05 | Created | Initial TECH-DEBT tracker |
| 2026-04-28 | Added | DEBT-001 Pre-Existing Lint/Type Sweep (Medium) — surfaced during Phase 10.5 |
| 2026-04-28 | Added | DEBT-002 OHLCV Per-Technique Refetch in Multi-Technique Scan (Low) — surfaced during Phase 10.6 |
| 2026-04-28 | Added | DEBT-003 EngineConfig Remaining Fields Not Env-Overridable (Low) — surfaced during Phase 10.2 |
| 2026-04-28 | Added | DEBT-004 Baseline Backtest Script Follow-ups (Low) — surfaced during Phase 10.3 |
| 2026-04-28 | Resolved | DEBT-001 Pre-Existing Lint/Type Sweep — Phase 11.1 cleared all in-scope ruff + mypy errors |
| 2026-04-28 | Added | DEBT-005 ccxt typing in `src/exchange/binance.py` (Low) — surfaced during Phase 11.1 |
| 2026-04-28 | Added | DEBT-006 `src/exchange/factory.py` shape drift (Low) — surfaced during Phase 11.1 |
| 2026-04-28 | Added | DEBT-007 Dashboard Streamlit type errors (Low) — surfaced during Phase 11.1 |
| 2026-04-28 | Added | DEBT-008 `src/main.py:220` lambda annotation (Low) — surfaced during Phase 11.1 |
| 2026-04-28 | Added | DEBT-009 `scripts/lint.sh --fix` unsafe for CI (Low) — surfaced during Phase 11.1 |
| 2026-04-28 | Resolved | DEBT-002 OHLCV Per-Technique Refetch in Multi-Technique Scan — Phase 11.2 added per-call (symbol, tf) cache |
| 2026-04-28 | Added | DEBT-010 Long+Short Same-Symbol Test Gap (Low) — surfaced during Phase 12.1 |
| 2026-04-28 | Resolved | DEBT-005 ccxt typing in `src/exchange/binance.py` — Phase 12.2 added `CCXTClient` Protocol (10 methods) |
| 2026-04-28 | Resolved | DEBT-006 `src/exchange/factory.py` shape drift — Phase 12.2 confirmed typing-system gap (not behavioural); `cast(Any, ...)` + comment |
| 2026-04-28 | Resolved | DEBT-007 Dashboard Streamlit type errors — Phase 12.2 `Literal` types + `StreamlitPage` + numeric casts |
| 2026-04-28 | Resolved | DEBT-008 `src/main.py` lambda annotation — Phase 12.2 targeted `# type: ignore[misc]` |
| 2026-04-28 | Added | DEBT-011 Dashboard `dict[str, object]` casts (Low) — surfaced during Phase 12.2 |
| 2026-04-28 | Resolved | DEBT-009 `scripts/lint.sh --fix` unsafe for CI — Phase 13.1 split into CI-safe lint.sh (no `--fix`) + dev-only lint-fix.sh |
| 2026-04-28 | Resolved | DEBT-010 Long+Short Same-Symbol Test Gap — Phase 13.1 added `test_cap_blocks_opposite_side_same_symbol` |
| 2026-04-28 | Resolved | DEBT-011 Dashboard `dict[str, object]` casts — Phase 13.1 introduced per-page TypedDicts (TradingSummaryMetrics, EngineSummaryMetrics); `cast()` calls dropped |
| 2026-04-28 | Resolved | DEBT-003 EngineConfig Remaining Fields Not Env-Overridable — Phase 13.2 added `engine_monitor_interval` / `engine_bitcoin_symbol` / `engine_altcoin_top_k` / `engine_actor` Settings fields; `build_engine` wires all 4 |
| 2026-04-28 | Resolved | DEBT-004 Baseline Backtest Script Follow-ups — Phase 13.3 added `since: int | None = None` to `BaseExchange.get_ohlcv` ABC; Binance + Bybit forward to ccxt; `scripts/backtest_baselines.py` drops the `_client` reach-around |
| 2026-04-28 | Added | DEBT-012 SMTP_SSL alternative for port 465 SMTP providers (Low) — surfaced during Phase 13.4 (deliberate scope deferral; STARTTLS-only Phase 13.4 ships) |
| 2026-04-28 | Resolved | DEBT-012 SMTP_SSL alternative for port 465 SMTP providers — Phase 14.2 added `email_use_ssl` Settings flag; `EmailNotifier` branches between `smtplib.SMTP`+STARTTLS (default) and `smtplib.SMTP_SSL` (port 465 providers) |
| 2026-04-29 | Added | DEBT-013 `auto_research_candidates.run_async` self-constructs `FeedbackLoop` / `BinanceExchange` (Low) — surfaced during Phase 17.1 quant-trader-expert review Issue 3 |
| 2026-04-29 | Added | DEBT-014 `loop.propose_new` called without `param_grid` — sensitivity gate SKIPPED for every Phase 17.1 candidate (Medium) — surfaced during Phase 17.1 quant-trader-expert review Issue 5 |
| 2026-04-30 | Added | DEBT-015 Rejection-path semantic divergence — Phase 18.1 rewrites `ProposalRecord`, Phase 12.1 emits activity-event only (Medium) — surfaced during Phase 18.1 qa-reviewer review note 1 |
| 2026-04-30 | Added | DEBT-016 `CycleResult.proposals_accepted` and `proposals_rejected` simultaneous increment — contract undocumented (Low) — surfaced during Phase 18.1 qa-reviewer review note 2 |
| 2026-04-30 | Added | DEBT-017 Stale-quote rejection event carries `entry_price` and `proposal_entry` for the same value (Low / cosmetic) — surfaced during Phase 18.1 qa-reviewer review note 3 |
| 2026-04-30 | Added | DEBT-018 Phase 18.1 rejection tests don't assert simultaneous-counters contract (Low) — surfaced during Phase 18.1 qa-reviewer review note 4 |
| 2026-05-03 | Resolved | DEBT-016 / DEBT-018 Runtime proposal simultaneous-counters contract — `CycleResult` now documents accepted/rejected as non-exclusive stage counters; runtime rejection tests assert `proposals_accepted == 1` for post-acceptance rejection paths; `tests/test_runtime_engine.py` 40 passed |
| 2026-05-03 | Resolved | DEBT-017 Stale-quote rejection duplicate entry payload — removed explicit `proposal_entry`; `entry_price` from `_proposal_summary` is now the single proposal-entry field for rejection events |
| 2026-04-30 | Added | DEBT-019 Auto-research script hangs indefinitely on prompt-type technique backtest (High) — surfaced during first real run of `auto_research_candidates.py --picks 5`; ~9-hour API-spend with one well-formed candidate generated and zero gated |
| 2026-04-30 | Added | DEBT-020 `BacktestConfig.per_bar_timeout` default unsafe for chasulang (High) — surfaced during Phase 17.2 quant-trader-expert review; default 60s was 8× smaller than chasulang's 480s per-`analyze()` ceiling |
| 2026-04-30 | Resolved | DEBT-020 `BacktestConfig.per_bar_timeout` default unsafe for chasulang — same-cycle one-line bump 60→600 (chasulang's 480s + 120s headroom); dynamic derivation flagged as forward-pointer follow-up |
| 2026-04-30 | Resolved | DEBT-019 Auto-research script hangs indefinitely on prompt-type technique backtest — Phase 17.2 shipped Options A (mandatory `## Output Contract` injection in `_build_new_idea_prompt`) + C (per-bar timeout + consecutive-parse-failures circuit breaker raising `BacktestAbortedError` → `LoopStatus.ERRORED`); `StrategyValidationError` skip-only refinement applied; Option B (code-type steering) deferred to Phase 17.3 |
| 2026-04-30 | Added | DEBT-021 Strategy warmup contract mismatch with `BacktestConfig.warmup_candles` (Medium) — surfaced during Phase 17.2 quant-trader-expert review Q2; `StrategyValidationError` skip-only refinement is a workaround, not a fix; declared `BaseStrategy.minimum_candles` is the long-term shape |
| 2026-05-03 | Resolved | DEBT-021 Strategy warmup contract mismatch with `BacktestConfig.warmup_candles` — added `TechniqueInfo.min_warmup_candles`, `BaseStrategy.minimum_candles`, and `Backtester.effective_warmup_candles(strategy)`; single-TF, multi-TF, and robustness pre-check warmup gates now use `max(config, strategy)`; RSI declares `period * 3`; targeted 3 tests + related 79-test suite passed |
| 2026-04-30 | Added | DEBT-022 Cumulative / rate-based breaker counterpart for failure-rate ≫ 0 strategies (Low) — surfaced during Phase 17.2 quant-trader-expert review Q3; consecutive-only counter never trips on alternating fail-success patterns; secondary cumulative-rate guard recommended |
| 2026-04-30 | Added | DEBT-023 No test pins improvement-prompt preservation of existing Output Contract block (Low) — surfaced during Phase 17.2 quant-trader-expert review Q5; `_build_improvement_prompt` deliberately doesn't re-inject the contract (correct), but no regression test that Claude's improvement output preserves the existing block |
| 2026-04-30 | Added | DEBT-024 Leverage applied twice in backtester / portfolio PnL math (High) — surfaced during 3-agent comprehensive audit; backtester `calculate_position_size` already returns leverage-neutral qty, then PnL multiplies by leverage again; paper trader convention divergent |
| 2026-04-30 | Added | DEBT-025 Exchange adapters and `JsonlRotator` use UTC-naive `datetime` (High) — surfaced during 3-agent comprehensive audit; `datetime.fromtimestamp(ms/1000)` (no tz) at 4 adapter sites + 3 rotator sites; dormant on Fly UTC, live in non-UTC dev |
| 2026-04-30 | Added | DEBT-026 Donchian experimental strategy file truncated and untracked (Medium) — surfaced during 3-agent comprehensive audit; body cut at line 39, fill semantics mismatch with backtester, `git status ??` |
| 2026-04-30 | Added | DEBT-027 Paper trader silently zeroes balance instead of recording liquidation (Medium) — surfaced during 3-agent comprehensive audit; under-water close clamps `balance.free = 0` with no `LIQUIDATED` event |
| 2026-04-30 | Added | DEBT-028 Persistence sites use non-atomic JSON write (Medium) — surfaced during 3-agent comprehensive audit; `TradeHistoryTracker` / `PortfolioTracker` / `ProposalHistory` + Phase 18.1 stale-quote rewrite all load→mutate→`write_text` |
| 2026-04-30 | Added | DEBT-029 Phase 5.4+ baseline figures need re-computation post-leverage fix (Medium) — surfaced during 3-agent comprehensive audit; downstream of DEBT-024 |
| 2026-04-30 | Added | DEBT-030 Backtester MDD / Sharpe computed from closed-trade equity only (Low) — surfaced during 3-agent comprehensive audit; intra-trade drawdown invisible |
| 2026-04-30 | Added | DEBT-031 MA-crossover SL evaluation includes the current candle (Low) — surfaced during 3-agent comprehensive audit; backtester silently drops the signal |
| 2026-04-30 | Added | DEBT-032 OOS Sharpe gate fails when in-sample population is small (Low) — surfaced during 3-agent comprehensive audit; need `minimum_is_trades` SKIP guard |
| 2026-04-30 | Added | DEBT-033 Stale-quote gate falls through on ticker exception without freshness check (Low) — surfaced during 3-agent comprehensive audit; need max_ticker_age_seconds threshold |
| 2026-04-30 | Added | DEBT-034 Cold-start technique selection uses alphabetical ordering (Low) — surfaced during 3-agent comprehensive audit; dormant under Phase 10.6 multi-technique default but live in legacy single-technique rollback path |
| 2026-04-30 | Added | DEBT-035 `Trade` model in `src/models.py` is dead code (Low) — surfaced during 3-agent comprehensive audit |
| 2026-04-30 | Added | DEBT-036 Calendar-month math approximated via `30 * months` (Low) — surfaced during 3-agent comprehensive audit; `src/proposal/interaction.py:413` |
| 2026-04-30 | Added | DEBT-037 Documentation drift — `CLAUDE.md` tree + `DESIGN.md` ClaudeClient + `TECH-DEBT.md` stats (Low) — surfaced during 3-agent comprehensive audit |
| 2026-04-30 | Added | DEBT-038 Notification dispatch failures swallowed without `NOTIFICATION_FAILED` event (Low) — surfaced during 3-agent comprehensive audit |
| 2026-04-30 | Added | DEBT-039 Logger module global `_initialized_loggers` blocks handler reset (Low) — surfaced during 3-agent comprehensive audit |
| 2026-04-30 | Added | DEBT-040 Two `# type: ignore[arg-type]` comments in `proposal/engine.py` undocumented (Low) — surfaced during 3-agent comprehensive audit |
| 2026-04-30 | Added | DEBT-041 `RuntimeEngine` accesses `ProposalInteraction._decision_callback` privately (Low) — surfaced during 3-agent comprehensive audit |
| 2026-04-30 | Added | DEBT-042 `pyproject.toml` `black --check` formatter gate dormant; 47 files unformatted (Low) — surfaced during 3-agent comprehensive audit |
| 2026-05-01 | Resolved | DEBT-024 Leverage applied twice in backtester / portfolio PnL math — Phase 20.1 extracted `pnl_for_trade(entry, exit, qty, side)` into new `src/utils/trading_math.py` (leverage NOT a parameter) and routed `_close_trade` / `Portfolio.calculate_unrealized_pnl` / `PaperTrader.close_position` (symmetry) through it; scope extension absorbed `TradeHistory.calculate_pnl` (both branches drop `* leverage` from `pnl`; `pnl_pct` reformulated leverage-neutral). Cross-ledger parity locked by `TestPnLConventionAlignment` (4 cases) + persistence parity by `test_close_trade_persisted_pnl_routes_through_helper{,_short}` (2 cases). Note: the DEBT-024 description's line-number references (`engine.py:783-794`) were stale — the actual leverage site had moved to `_close_trade` ~lines 948-960. DEBT-029 (Phase 5.4+ baseline re-computation) remains downstream-open until Phase 20.3 lands |
| 2026-05-01 | Resolved | DEBT-029 Phase 5.4+ baseline figures need re-computation post-leverage fix — closed as **Reframed** during Phase 20.3 deferral. The "operator-facing artefact regeneration" framing was vacuous: `data/backtest/baselines/` directory absent on this checkout, `docs/baselines.md` operator table all `_TBD_`, no inflated figures had ever been persisted (operator impact = 0). Math side fully closed by chain DEBT-024 → 20.1 + 20.2; reproducibility side reassigned to new DEBT-043 (Medium, owned by Phase 25) |
| 2026-05-01 | Added | DEBT-043 Baseline regenerator is non-deterministic — live Binance, no snapshot mode (Medium) — surfaced during Phase 20.3 deferral; `scripts/backtest_baselines.py:26-30` (docstring) + `:511-518` (live exchange construction) make real network calls every run, output drifts day-to-day, cross-operator / cross-day reproducibility broken; owned by Phase 25 (snapshot dataset + `--snapshot` flag + freshness policy + first-time `docs/baselines.md` population) |
| 2026-05-01 | Updated | DEBT-025 Exchange adapters and `JsonlRotator` use UTC-naive `datetime` — Phase 21.1 closed the adapter read-side (4 sites in `binance.py` + 4 in `bybit.py` routed through new `src/utils/time.py::from_unix_ms`) and the `JsonlRotator._coerce_timestamp` read-side. DEBT-025 remains Active: write-side `datetime.now()` sweep is Phase 21.2, stale-quote payload coherence is Phase 21.3. Status note appended to Active entry |
| 2026-05-01 | Updated | DEBT-025 Exchange adapters and `JsonlRotator` use UTC-naive `datetime` — Phase 21.2 closed the engine-side write-half: 12+ naive `datetime.now()` write-sites swept to `now_utc()` across runtime / feedback / proposal / strategy / ai / models / portfolio modules; Pydantic `field_validator(mode="after")` UTC-coerce hooks added on 7 models (9 timestamp fields: `ActivityEvent`, `AuditEvent`, `Proposal`, `CandidateRecord`, `AssetSnapshot`, `PerformanceRecord`×2, `TradeHistory`×2); reader-boundary naive-tolerance shims at 5 sites (`PortfolioTracker.load_snapshots`, `TradeHistoryTracker.get_trades_by_date_range`, `PerformanceTracker.get_records_by_date_range`, `ProposalHistory.purge_old`, `ProposalHistory.list_all` sort key); new `src/utils/time.py::ensure_utc(value)` helper. DEBT-025 remains Active: stale-quote payload coherence (Phase 21.3) is the only remaining surface. Status note rewritten on Active entry |
| 2026-05-01 | Resolved | DEBT-025 Exchange adapters and `JsonlRotator` use UTC-naive `datetime` — Phase 21.3 sealed stale-quote payload coherence (formal contract docstring on `_record_stale_quote_rejection` naming all 5 UTC-aware timestamp sources + 3 regression tests in `tests/test_runtime_engine.py` lines 992 / 1033 / 1082 pinning aware-on-write coherence, cross-source aware math, and legacy-naive read tolerance). Function body byte-identical below the new docstring section. Closes DEBT-025 fully across the 21.1 / 21.2 / 21.3 chain — every UTC-naive surface flagged in the 2026-04-30 audit is now closed. Phase 21 sealed; cross-check `docs/cross-checks/2026-05-01-phase-21-time-tz-hardening.md` PASS with no gaps and no new debt |
| 2026-05-01 | Resolved | DEBT-028 Persistence sites use non-atomic JSON write — Phase 22.1 introduced `src/utils/io.py::atomic_write_text` (uuid-suffixed tmp + `os.replace` + cleanup-on-exception); 5 named sites migrated (`PerformanceTracker._save_records` / `_update_summary`, `TradeHistoryTracker._save_trades`, `PortfolioTracker._save_snapshots`, `ProposalHistory.save`); `_record_stale_quote_rejection` covered transitively via `ProposalHistory.save`. 15 helper unit tests + 4 site regression tests; pytest 1265 → 1284 (+19); reviewers 🟢🟢. Caveat: atomicity ≠ concurrency-safety — tracked as DEBT-046 (Medium, hard prereq for Phase 19.2). Plan-text correction noted (`src/proposal/history.py` → `src/proposal/interaction.py`) |
| 2026-05-01 | Added | DEBT-044 `FeedbackLoop.save_state` not migrated to `atomic_write_text` (Low) — surfaced during Phase 22.1 senior-developer review; same load → mutate → save shape as the 5 migrated sites, out of Phase 22.1 named scope; mechanical one-line fix |
| 2026-05-01 | Added | DEBT-045 `Backtester._save_result` single-write not atomic (Low) — surfaced during Phase 22.1 quant-trader-expert review; single-write (no load → mutate) but benefits from atomicity if backtest run crashes during persistence; helper exists, one-line route |
| 2026-05-01 | Added | DEBT-046 Atomic write does not protect against concurrent-mutation loss — Phase 19.2 prereq (Medium) — surfaced during Phase 22.1 implementation as the durability-vs-concurrency caveat; `atomic_write_text` is last-writer-wins under concurrent load → mutate → save; **hard prereq for Phase 19.2 sub-account fan-out**; resolution shapes: per-file lock helper (`fcntl.flock`) layered over atomic-write OR per-account file partitioning (Phase 19.2 planner picks); cross-referenced in `docs/development-plan.md` Phase 19.2 Prerequisites line |
| 2026-05-01 | Resolved | DEBT-027 Paper trader silently zeroes balance instead of recording liquidation — Phase 22.2 rewrote `PaperTrader.close_position` under-water branch with projected-free predicate (`projected_free = balance.free + (pnl - exit_fee) < 0`); default behaviour records true negative equity AND emits structured `LIQUIDATED` activity event (`symbol`, `side`, `entry`, `exit`, `qty`, `realized_pnl`, `balance_before`, `balance_after`); legacy clamp-to-zero preserved behind opt-out flag `auto_deposit_on_liquidation` (still emits the event — flag controls balance treatment, not event semantics). New `ActivityEventType.LIQUIDATED` enum member; `PaperBalance.free` Pydantic constraint relaxed (lock / deduct / reserve paths still enforce overdraw protection); `PaperTrader.__init__` gained `activity_log` + `auto_deposit_on_liquidation` kwargs; `EngineConfig` / `Settings.paper_auto_deposit_on_liquidation` (env-overridable `PAPER_AUTO_DEPOSIT_ON_LIQUIDATION`); `.env.example` documented; `build_engine` plumbs through. 6 regression tests pin the contract; pytest 1284 → 1290 (+6); reviewers 🟢🟢. Backtester asymmetry surfaced as DEBT-047 (Medium). Plan-text drift noted (DEBT-027 cited `paper.py:619,626`; actual liquidation branch lives ~656-720). Phase 22 sealed (22.1 ✅, 22.2 ✅); cross-check `docs/cross-checks/2026-05-01-phase-22-persistence-atomicity-liquidation.md` PASS |
| 2026-05-01 | Added | DEBT-047 Backtester has no leverage-liquidation modeling (Medium) — surfaced during Phase 22.2 quant-trader-expert review; `src/backtest/engine.py:371,396` does `balance += pnl_delta` with no margin lock / clamp / event; asymmetric with `PaperTrader` post-22.2 (paper now emits `LIQUIDATED`, backtester continues simulating against arbitrarily negative equity); operators reading backtest equity curves can't distinguish "would have been liquidated" from "deep drawdown but recovered"; resolution shapes: `BacktestConfig.liquidation_threshold` + structural marker on `BacktestTrade` / `BacktestResult` OR conservative clamp + log at threshold; consider folding into Phase 24 |
| 2026-05-01 | Resolved | DEBT-037 Documentation drift — `CLAUDE.md` tree + `DESIGN.md` ClaudeClient + `TECH-DEBT.md` stats — Phase 23.1 backfilled `src/runtime/` / `src/tools/` / `src/utils/` directories + `src/main.py` entry point in `CLAUDE.md` project tree; renamed `class ClaudeClient` → actual `class ClaudeCLI` in `DESIGN.md §2.3` with verbatim method signatures from `src/ai/claude.py:46`, added parallel `class StrategyImprover` block from `src/ai/improver.py:98`; reordered DEBT-018 above DEBT-021 in TECH-DEBT.md (was below DEBT-019..23 separated by an internal `---` separator), removed the stray `---`; recomputed Statistics by counting Active vs Resolved `### DEBT-` headings (28 → 27 active; 19 → 20 resolved; Medium 7 unchanged; Low 21 → 20). Same-cycle Phase 23.1 also backfilled the missing session logs for shipped Phase 17.2 + 17.3 cycles and the Phase 15 cross-check (separate spec items, same audit finding) |
| 2026-05-01 | Resolved | DEBT-030 Backtester MDD/Sharpe computed from closed-trade equity only — Phase 24 introduced per-bar equity curve (`EquityPoint` model + `BacktestResult.equity_curve` field; `Backtester._build_equity_curve` mark-to-market every bar); analyzer prefers equity curve, falls back to closed-trade for back-compat; quant-driven follow-up derives `bars_per_year` from `EquityPoint` median Δt so Sharpe annualization matches candle cadence (8760 hourly / 365 daily) instead of silently scaling by ~5.9× via fixed `trades_per_year` |
| 2026-05-01 | Resolved | DEBT-031 MA-crossover SL evaluation includes the current candle — Phase 24 rolled SL look-back back by one bar (`min(closes[-5:])` → `min(closes[-6:-1])`, symmetric on short side); previously-suppressed bullish/bearish crosses where current candle was the local 5-bar low/high now emit cleanly; quant sign-off granted as strict signal-quality improvement |
| 2026-05-01 | Resolved | DEBT-032 OOS Sharpe gate fails when in-sample population is small — Phase 24 added `RobustnessConfig.minimum_is_trades: int = 10` (quant-driven bump from initial default 5); SKIP-on-tiny-IS branch precedes IS-Sharpe-non-positive FAIL; strict `<` boundary (N=9 SKIP, N=10 reaches floor and is judged); aggregator preserves SKIP as non-PASS for promotion |
| 2026-05-01 | Resolved | DEBT-033 Stale-quote gate falls through on ticker exception without freshness check — Phase 24 added `EngineConfig.max_ticker_age_seconds: float = 10.0` for cached-ticker freshness; quant-driven follow-up added opt-in `EngineConfig.reject_if_stale_quote: bool = False` flag — when True, both stale-ticker AND ticker-fetch-error branches hard-reject via new `_record_no_live_data_rejection` (mirrors stale-quote rejection shape) with reason `stale_quote_no_live_data`, addressing the original audit's "fill proceeds at proposal.entry_price with no live cross-check" concern; plumbed via `Settings.engine_reject_if_stale_quote` and `.env.example` |
| 2026-05-01 | Resolved | DEBT-034 Cold-start technique selection uses alphabetical ordering — Phase 24 added `ProposalEngineConfig.mode: Literal["paper", "live"]` + `min_closed_trades_for_live_promotion: int = 5`; `_cold_start_blocks_live` guard refuses live proposals when no applicable technique meets threshold; paper-mode bootstrap behavior unchanged; `src/main.py` wires `settings.trading_mode` into engine config; quant-driven follow-up added `ActivityEventType.COLD_START_BLOCKED` enum + structured event payload (symbol / threshold / max_trades_observed / per_technique_trades) so operators see why bot is intentionally idle |
| 2026-05-01 | Resolved | DEBT-043 Baseline regenerator is non-deterministic — Phase 25 closed at infrastructure level via 25.1 (snapshot format + loader + 27 tests) + 25.2 (`--snapshot` / `--refresh-snapshot` / `--max-snapshot-age-days` CLI flags + `SnapshotExchange` adapter + slice-bounds enforcement + 10 tests including `test_cross_operator_determinism_byte_identical`) + 25.3 Part A (operator runbook + freshness policy guidance + reproducibility note in `docs/baselines.md`). Phase 25 partial seal — Part B (one-time operator action with live Binance read-only credentials to populate first-time numbers) documented in runbook, non-gating for further phases. Cross-check PASS |
| 2026-05-01 | Added | DEBT-048 `docs/baselines.md` table widening + placeholder rename (Low) — surfaced during Phase 25.3 Part A; spec asked for 6→9 column widening (`Trades / Total PnL (USDT) / Snapshot fetched_at` columns) + `_TBD_` → `_AWAITING_OPERATOR_FIRST_RUN_` rename, but both conflict with the autonomous-shipping `_TABLE_PATTERN` rewriter and 2 existing tests; deferred to a future docs-polish bundle that updates regex + `render_table` + tests in lockstep |
| 2026-05-01 | Resolved | DEBT-044 `FeedbackLoop.save_state` not migrated to `atomic_write_text` — Phase 26.1 routed through Phase 22.1 helper; output bytes byte-identical, only durability semantics changed; 1 regression test |
| 2026-05-01 | Resolved | DEBT-045 `Backtester._save_result` single-write not atomic — Phase 26.1 routed through `atomic_write_text`; CPython `json.dump` ≡ `json.dumps` so bytes identical; 2 regression tests |
| 2026-05-01 | Resolved | DEBT-035 `Trade` model dead code — Phase 26.2 deleted from `src/models.py:199-227`; regression test pins ImportError on attempted re-import |
| 2026-05-01 | Resolved | DEBT-036 Calendar-month math — Phase 26.2 swapped `timedelta(days=30*N)` for `relativedelta(months=N)`; `python-dateutil` added; 2 calendar-boundary regression tests |
| 2026-05-01 | Resolved | DEBT-040 Undocumented `# type: ignore[arg-type]` — Phase 26.2 documented both sites at `src/proposal/engine.py:519,555` with upstream-type-mismatch rationale; tightening deferred (wider refactor) |
| 2026-05-01 | Resolved | DEBT-041 `_decision_callback` private access — Phase 26.2 added public `ProposalInteraction.set_decision_callback`; runtime engine uses it; `# type: ignore[attr-defined]` dropped; 2 setter tests |
| 2026-05-01 | Resolved | DEBT-048 baselines table widening + placeholder rename — Phase 26.2 widened to 9 columns + `_TBD_` → `_AWAITING_OPERATOR_FIRST_RUN_` (`PLACEHOLDER_TOKEN` constant); rewriter + 3 tests updated in lockstep |
| 2026-05-01 | Resolved | DEBT-038 Notifier failure swallowed — Phase 26.3 added `NOTIFICATION_FAILED` ActivityEvent with 5-field structured payload; emit-then-swallow at runtime/engine.py:451; behavior preserved + observability added |
| 2026-05-01 | Resolved | DEBT-039 Logger reset for test isolation — Phase 26.3 wired existing `reset_loggers()` into autouse pytest fixture (`tests/conftest.py`); 1 contract test |
| 2026-05-01 | Resolved | DEBT-047 Backtester leverage-liquidation parity — Phase 26.4 added `BacktestConfig.liquidation_threshold` (default `Decimal("0")`), `BacktestTrade.liquidated` marker, `BacktestResult.liquidated` rollup, `_mark_if_liquidated` wired to 4 close sites, equity-curve truncation at first liquidating trade; 4 regression tests; PnL math unchanged |
| 2026-05-01 | Resolved | DEBT-042 Black formatter gate dormant — Phase 26.5 ran one-shot `black src tests scripts` sweep; 21 files reformatted; pytest 1361 → 1361 (zero delta — pure formatter); gate now enforceable (115 files clean) |
| 2026-05-02 | Updated | DEBT-019 Resolution prose extended — Option B (code-type steering) shipped by Phase 17.5: `Pick.code_type` flag, `_build_new_idea_code_prompt` branch instructing `BaseStrategy` Python emission, all 9 catalog TOP_PICKS flagged; integration test pins `claude.analyze.call_count == 0` during 300-candle backtest |
| 2026-05-02 | Added | DEBT-049 Phase 17.5 integration fixture uses `signal="neutral"` (Low) — surfaced during quant-trader-expert review; trade-producing path not exercised; trivial follow-up to flip fixture to `signal="long"` on a Donchian-shaped trigger |
| 2026-05-02 | Added | DEBT-050 `engine.sub_account_registry` post-hoc attribute set in `src/main.py:339` (Low) — surfaced during Phase 19.1; `# type: ignore[attr-defined]` workaround until Phase 19.2 lifts `registry` into `TradingEngine.__init__`; auto-resolves with 19.2's spec |
| 2026-05-02 | Added | DEBT-051 `SubAccountRegistry._load` YAML config dead branch silently ignores pre-staged files (Low) — surfaced during Phase 19.1; `if self.config_path.exists(): pass` placeholder, inert in 19.1; resolved naturally by Phase 19.3 YAML parsing |
| 2026-05-02 | Updated | DEBT-046 Active status confirmed unchanged at Phase 19.1 close — atomic write does not protect against concurrent-mutation loss; remains hard prereq for Phase 19.2 sub-account fan-out (no concurrent writers in 19.1's scope, so 19.1 didn't touch it) |
| 2026-05-03 | Resolved | DEBT-046 Atomic write does not protect against concurrent-mutation loss — Phase 19.2 picked the per-account file-partitioning resolution shape instead of adding a POSIX file lock. Proposal history, performance records, trade history, and portfolio snapshots now write under a `{sub_account_id}` directory (`data/proposals/{sub_account_id}/`, `data/performance/{sub_account_id}/{technique}/`, `data/trades/{mode}/{sub_account_id}/`, `data/portfolio/{mode}/{sub_account_id}/`), so sub-account fan-out does not share load → mutate → save files across accounts. Performance-tree migration uses separate marker `.performance_migrated_v19_2` so 19.1-completed deployments still pick it up |
| 2026-05-03 | Resolved | DEBT-050 `engine.sub_account_registry` post-hoc attribute set — Phase 19.2 promoted `registry` to a real `TradingEngine.__init__` parameter and removed the post-construction `engine.sub_account_registry = registry  # type: ignore[attr-defined]` assignment from `src/main.py` |
| 2026-05-03 | Resolved | DEBT-013 `auto_research_candidates.run_async` self-constructs `FeedbackLoop` / `BinanceExchange` — `main()` now builds dependencies explicitly via `build_loop()` / `build_exchange()` and passes them into `run_async`; `run_async` owns exchange lifecycle by default and supports `owns_exchange=False` for future shared-runtime callers |
| 2026-05-03 | Resolved | DEBT-015 Rejection-path semantic divergence — cap rejections now rewrite the persisted `ProposalRecord` to `REJECTED` with the cap reason, matching the stale-quote rejection pattern while preserving the existing activity event |

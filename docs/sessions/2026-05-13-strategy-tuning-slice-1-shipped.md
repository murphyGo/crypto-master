# Session: strategy-tuning Slice 1 shipped

## Unit

- `strategy-tuning` (primary)
- Secondary units: `proposal-runtime`, `strategy-framework`

## Related Requirements

- FR-001
- FR-002
- FR-005
- FR-013
- FR-027
- FR-034
- FR-036
- FR-039
- NFR-006
- NFR-007

## Scope

Shipped **Slice 1** of the `strategy-tuning` unit — the state machine + recommender + runtime gate subset of the full functional-design spec. Concretely: `StrategyAction` enum (`keep`, `shadow`, `scout`, `pause`, `promote`, `retune`); `StrategyTuningPolicy` + `StrategyOverride` + per-bucket `ThresholdSpec` (frozen Pydantic) on `SubAccount` with `enabled=False` default and per-strategy override fall-through; pure `recommend_action(RecommenderEvidence, ThresholdSpec) -> StrategyAction | None` with priority order `pause → shadow → scout → retune → keep → promote` plus `evidence_from_performance` helper; `_strategy_action_gate` wired after `_correlation_gate` in `_handle_proposal` with 6 per-action behaviors (keep/promote pass-through; retune pass-through + `RETUNE_FLAGGED` advisory; scout scales `proposal.quantity *= scout_size_factor`; shadow persists `shadow=True` record + `shadow_recorded` terminal without opening; pause rejects with `gate_rejected_strategy_action_pause`). 2 new `ProposalFinalState` terminals (`shadow_recorded`, `gate_rejected_strategy_action_pause`) with funnel plumbing (2 new counters + extended `_STATE_TO_FIELD` + derived `gate_rejected_total` and `score_accepted_total` sums). `STRATEGY_ACTION_APPLIED` activity event reserved on the enum but not yet emitted; `RETUNE_FLAGGED` emitted live.

**Slice 2 (deferred under DEBT-069 umbrella)**: dashboard view + YAML clipboard helper (spec Step 4); initial-action seeding for named strategy families per spec §"Initial Actions" (RSI scout, `momentum_pinball_orb` pause, mean-reversion family pause, default/LLM retune, `raschke_holy_grail` + `ma_crossover` scout, `vcp_breakout` + `session_vwap_pullback` conditional keep/retune); observation store for recommendation history analogous to `PromotionObservationStore`; `STRATEGY_ACTION_APPLIED` emission; true profit-factor computation upgrade; `pause`-reason split; funnel test-completeness gaps. Slice 1 came in at ~805 LoC, well under the spec's 1200-LoC scope-split guard, and the spec explicitly admits Step 4 + Step 5 as acceptable splits.

## Changes

- `src/strategy/tuning.py` (NEW) — `StrategyAction` enum + `StrategyTuningPolicy` + `StrategyOverride` + per-bucket `ThresholdSpec` (frozen Pydantic). `enabled=False` default; per-strategy override fall-through; `scout_size_factor <= 1` field validator. Default thresholds documented inline.
- `src/strategy/tuning_recommender.py` (NEW) — pure `recommend_action(RecommenderEvidence, ThresholdSpec) -> StrategyAction | None`; priority order `pause → shadow → scout → retune → keep → promote`; `evidence_from_performance` helper. PF approximated from `(wins * best_pnl) / (losses * |worst_pnl|)` because `TechniquePerformance` doesn't expose `gross_win`/`gross_loss` yet (DEBT-069(e) upgrade).
- `src/trading/sub_account.py` — `SubAccount.strategy_tuning: StrategyTuningPolicy` field.
- `src/proposal/interaction.py` — `ProposalRecord.shadow: bool = False` field; 2 new `ProposalFinalState` terminals (`shadow_recorded`, `gate_rejected_strategy_action_pause`).
- `src/proposal/funnel.py` — 2 new counters + extended `_STATE_TO_FIELD` + derived `gate_rejected_total` (including pause) + `score_accepted_total` (including shadow) sums.
- `src/runtime/activity_log.py` — `STRATEGY_ACTION_APPLIED` enum value (reserved, not yet emitted — DEBT-069(d)) + `RETUNE_FLAGGED` (emitted on retune path).
- `src/runtime/engine.py::_strategy_action_gate` — wired after `_correlation_gate`. Per-action behavior: keep/promote pass-through; retune pass-through + `RETUNE_FLAGGED` advisory; scout scales `proposal.quantity *= scout_size_factor`; shadow persists record with `shadow=True` + `shadow_recorded`, no open; pause rejects with `gate_rejected_strategy_action_pause`.
- Tests — net `+39` (2008 → 2047) across recommender, gate, config-parsing, and funnel paths; zero regressions.

## Quant adjudications (Q1-Q5)

- **Q1** (default thresholds): 🟡 — defaults are reasonable starting points; `keep_min PF=1.3` may put most strategies in retune limbo initially; `scout.sample_size_max=10` AND `retune.sample_size_min=20` creates a dead zone for strategies with 11-19 samples. Recommend Slice 2 dashboard copy explains "wall of retune flags" is by design; widen `scout.sample_size_max` to ~15 after first 1-2 weeks of paper evidence. Captured as DEBT-069(g).
- **Q2** (PF approximation): 🟡 — ship v1 with the `(wins * best_pnl) / (losses * |worst_pnl|)` approximation; recalibrate when `TechniquePerformance` exposes `gross_win`/`gross_loss`. The approximation systematically over-weights extreme winners/losers (bad for crypto fat-tail distributions). Captured as DEBT-069(e).
- **Q3** (scout quantity scaling order): 🟢 ratified-as-shipped — sequencing in `_handle_proposal` is correct. Pre-scout gates (score, regime, correlation) are quantity-insensitive; post-scout gates (trend, aggregate cap, stale-position) correctly see the scout-sized quantity.
- **Q4** (shadow record contamination of recommender): 🟢 ratified-as-shipped — `PerformanceRecord` is written only on actual `Trade` close; shadow proposals short-circuit at the gate before any `Trade` is opened. Recommender reads only `PerformanceRecord` rows. Clean separation. One defensive comment recommended in `from_records` for future-proofing — captured as DEBT-069(h).
- **Q5** (pause priority): 🟡 — current `pause` conflates "evidence-based" (PnL-driven) and "gate-config" (fail-closed-rate-driven) reasons. Both safe to pause for v1; Slice 2 should split into distinct pause reasons so operator triage knows whether to investigate gates or retire the strategy. Captured as DEBT-069(f).

## QA observations

- 🟡 `tests/test_proposal_funnel.py::test_gate_rejected_total_sums_every_gate_bucket` (lines 158-182) does NOT include the new `GATE_REJECTED_STRATEGY_ACTION_PAUSE` bucket — aggregator fold is exercised only indirectly via engine tests.
- 🟡 `tests/test_proposal_funnel.py::test_score_accepted_total_sums_every_post_score_state` (lines 185-239) omits the two new members (`GATE_REJECTED_STRATEGY_ACTION_PAUSE`, `SHADOW_RECORDED`).

Both gaps are unit-test-completeness; engine tests already cover the increment paths. Folded into DEBT-069(i) for the Slice 2 follow-up commit.

## Scope-split rationale

The functional-design spec explicitly admits Step 4 (dashboard) and Step 5 (initial-action seeding + observation store) as acceptable splits when the implementation slice would otherwise push past the 1200-LoC scope-split guard. The Slice 1 deliverable (state machine + recommender + runtime gate) came in at ~805 LoC, with the deferred surfaces forming a coherent dashboard-pass bundle for Slice 2. Three quant-trader-expert follow-ups and two QA follow-ups bundled into the same DEBT-069 umbrella rather than filed as separate items — the quant follow-ups all touch the recommender / threshold tuning surface and naturally sequence with (a)/(b)/(c); the QA follow-ups are mechanical aggregator-test additions that bundle cheaply with any Slice 2 commit.

## Verification

- `pytest -q` — **2047 passed** (was 2008; net +39, zero regressions).
- `ruff check` — clean.
- `mypy` on the 7 changed source files (`src/strategy/tuning.py`, `src/strategy/tuning_recommender.py`, `src/trading/sub_account.py`, `src/proposal/interaction.py`, `src/proposal/funnel.py`, `src/runtime/activity_log.py`, `src/runtime/engine.py`) — clean.

## Risks

- **`enabled=False` default is a back-compat floor.** Operators must opt in via YAML on each sub-account before the gate has any effect. Existing deployments that don't touch the YAML get pure pass-through behavior — Slice 1 ships safe. This is deliberate (no surprise rejections on Slice 1 land) but means operators get no enforcement benefit until they configure.
- **`STRATEGY_ACTION_APPLIED` enum reserved but not emitted.** The enum value is present at `src/runtime/activity_log.py` for forward-compat, but no emit site exists yet — operators reading the activity log won't see applied-state transitions until DEBT-069(d) lands the startup-time diff emitter. `RETUNE_FLAGGED` is the only new event firing on the runtime path in Slice 1.
- **PF approximation over-weights fat tails.** The `(wins * best_pnl) / (losses * |worst_pnl|)` shortcut in `recommend_action` systematically over-weights extreme winners/losers, which is the opposite of what crypto's fat-tail return distribution demands. Strategies with one huge winner or one huge loser will be mis-scored until DEBT-069(e) exposes the real `gross_win`/`gross_loss` aggregates on `TechniquePerformance`. Quant Q2 ratified ship-and-recalibrate.
- **Funnel aggregator buckets exercised only via engine integration tests for now.** The two new states (`shadow_recorded`, `gate_rejected_strategy_action_pause`) are covered indirectly through `_handle_proposal` integration tests but not via the dedicated `test_gate_rejected_total_sums_every_gate_bucket` / `test_score_accepted_total_sums_every_post_score_state` parametrized contract tests. DEBT-069(i) closes the test-completeness gap; until then, a future fold-bug in `_STATE_TO_FIELD` could pass the dedicated funnel tests while failing the engine integration path.

## Reviewer notes

- quant-trader-expert: 🟡 across Q1/Q2/Q5 (all ship-and-follow-up, captured as DEBT-069(g)/(e)/(f)); 🟢 on Q3 and Q4 ratified-as-shipped (with one defensive-comment ask captured as DEBT-069(h)). No 🔴 verdicts on the diff.
- qa-reviewer: 🟡 with two unit-test-completeness gaps on `tests/test_proposal_funnel.py` (lines 158-182 and 185-239); engine integration tests already cover the increment paths. Captured as DEBT-069(i). No 🔴 verdicts.

## Future work

- **DEBT-069** (Slice 2 umbrella) — nine sub-items:
  - **(a)** Dashboard view + YAML clipboard helper per spec Step 4 (per-(sub-account, strategy) row with Applied / Recommended columns + evidence summary + clipboard YAML diff for operator-apply workflow; write path explicitly out of scope per resolved Open Decision).
  - **(b)** Initial-action seeding for named strategy families per spec §"Initial Actions" (RSI scout, `momentum_pinball_orb` pause, mean-reversion family pause, default/LLM retune, `raschke_holy_grail` + `ma_crossover` scout, `vcp_breakout` + `session_vwap_pullback` conditional keep/retune) based on the 2026-05-13 Fly evidence snapshot.
  - **(c)** Observation store for recommendation history (pattern analogous to `PromotionObservationStore`) so the dashboard can render trends without re-running the recommender at every page load.
  - **(d)** `STRATEGY_ACTION_APPLIED` emission — enum value reserved at `src/runtime/activity_log.py` but never emitted; add startup-time diff emitter that fires on prior-state → new-state transitions detected at config-reload.
  - **(e)** True profit-factor computation (quant Q2) — add `gross_win_pct` / `gross_loss_pct` / `max_drawdown_pct` to `TechniquePerformance.from_records` at `src/strategy/performance.py:218-255`; drop `_infer_profit_factor` approximation at `src/strategy/tuning_recommender.py:113-142`; recalibrate thresholds based on real PF distribution.
  - **(f)** Split `pause` reason into evidence-driven vs gate-config-driven (quant Q5) — either two enum values (`StrategyAction.PAUSE_EVIDENCE` / `StrategyAction.PAUSE_GATE_CONFIG`) or a single `PAUSE` with `pause_reason` field in event details; dashboard's pause-triage view routes gate-config pauses to the funnel audit. Files: `src/strategy/tuning_recommender.py:168-176`, `src/runtime/engine.py:2366-2397`.
  - **(g)** Threshold calibration after first 2 weeks paper evidence (quant Q1) — widen `scout.sample_size_max` to ~15 to align with `keep.sample_size_min` and avoid the 11-19 dead zone; review `keep_min PF=1.3` against actual paper distribution; document the "wall of retune" expectation in dashboard copy.
  - **(h)** Shadow-aware filter defensive comment (quant Q4) in `src/strategy/performance.py::from_records` flagging that any future "shadow-aware" performance derivation must filter `shadow=True` records analogously to the `synthetic=True` filter at line 218-219.
  - **(i)** Funnel unit-test coverage gaps (QA) — append `GATE_REJECTED_STRATEGY_ACTION_PAUSE` to `test_gate_rejected_total_sums_every_gate_bucket` (lines 158-182); append `GATE_REJECTED_STRATEGY_ACTION_PAUSE` + `SHADOW_RECORDED` to `test_score_accepted_total_sums_every_post_score_state` (lines 185-239).

  Suggested sequencing: (a)+(b)+(c) ship together as the dashboard pass; (d) bundles cheaply with (a); (e) is its own cycle (recalibrates thresholds); (f) bundles with (e); (g) is post-evidence calibration; (h) and (i) are mechanical follow-up commits.

# Code Generation Plan: strategy-tuning

## Task

Implement the existing `strategy-tuning` functional design: per
(sub-account, strategy) action states (`keep`, `shadow`, `scout`, `pause`,
`promote`, `retune`), an evidence-driven recommender, runtime proposal
gating that enforces the applied state, sub-account config schema
additions, operator audit trail, and dashboard visibility plus an "Apply
recommendation" workflow.

## Related Context

- Unit: `strategy-tuning`
- Stage: Code Generation
- Requirements: FR-001, FR-002, FR-005, FR-013, FR-027, FR-034, FR-036,
  FR-039, NFR-006, NFR-007
- Functional design: `aidlc-docs/construction/strategy-tuning/functional-design/spec.md`
- Source evidence: 2026-05-13 Fly snapshot rank-and-act analysis flagged
  `raschke_holy_grail` and `ma_crossover` as promising but under-sampled;
  RSI variants, default/simple trend, `momentum_pinball_orb`, and several
  mean-reversion accounts as pause or scout candidates.
- Related units: `strategy-promotion-lab`, `sub-account-experiment-marketplace`,
  `market-regime`, `proposal-runtime`, `runtime-safety-score`,
  `strategy-framework`, DEBT-061 fail-closed metrics surface.

## Steps

- [x] Implement the action-state recommender as a pure function over
      `PerformanceTracker` aggregates and DEBT-061 fail-closed metrics.
      (Slice 1, 2026-05-13. DEBT-069(e) shipped 2026-05-24: true
      `TechniquePerformance.gross_win_pct` / `gross_loss_pct` /
      `max_drawdown_pct` aggregates replace the earlier best/worst PnL
      PF approximation.)
- [x] Add `strategy_tuning` block to sub-account YAML schema with parsing,
      defaults, and validation; default `enabled: false`. (Slice 1.)
- [x] Persist applied/recommended state and evidence snapshots via an
      observation store analogous to `PromotionObservationStore`.
      (Slice 2 — DEBT-069(c), shipped 2026-06-10. Added
      `StrategyTuningObservationStore` with atomic per-pair snapshots,
      bounded recommendation history, evidence snapshots, and dashboard
      observation metadata.)
- [x] Wire runtime proposal gating: `pause` rejects with structured reason,
      `shadow` records without opening, `scout` applies
      `scout_size_factor`, `retune` and `keep` pass through, `promote`
      mirrors the underlying state. (Slice 1; `_strategy_action_gate` after
      `_correlation_gate`.)
- [x] Emit activity events for applied-state changes with operator/system
      attribution and evidence snapshot. (`STRATEGY_ACTION_APPLIED` enum
      reserved at `src/runtime/activity_log.py` but not yet emitted —
      Slice 2 / DEBT-069(d). `RETUNE_FLAGGED` advisory already emitted.
      Shipped 2026-05-28.)
- [x] Surface applied/recommended state, evidence columns, history, and
      the "Apply recommendation" affordance on the Strategies dashboard.
      **Scope-split — Slice 2 (DEBT-069(a)).** Write path explicitly out of
      scope per resolved Open Decision; YAML clipboard helper instead.
      Applied/Recommended/YAML diff shipped 2026-05-28; observation metadata
      columns shipped 2026-06-10.
- [x] Seed initial recommendations for RSI family, `momentum_pinball_orb`,
      mean-reversion family, `raschke_holy_grail`, `ma_crossover`,
      `vcp_breakout`, `session_vwap_pullback`, and default/LLM strategies.
      (Slice 2 — DEBT-069(b), shipped 2026-05-28.)
- [x] Add tests for recommender, runtime gating, config parsing, activity
      events, and dashboard rendering. (Slice 1 covers recommender +
      runtime gating + config parsing + `RETUNE_FLAGGED` event; dashboard
      tests and `STRATEGY_ACTION_APPLIED` emission tests deferred to
      Slice 2. Funnel `_STATE_TO_FIELD` aggregator unit-test gaps for the
      2 new states — DEBT-069(i).)
- [x] Add true PF / closed-trade drawdown tests for DEBT-069(e). (2026-05-24:
      `tests/test_strategy_performance.py` pins gross win/loss, synthetic
      exclusion, and cumulative drawdown; `tests/test_strategy_tuning_recommender.py`
      pins true gross-win/gross-loss PF input.)
- [x] Calibrate thresholds after fresh paper evidence, especially
      `scout.sample_size_max`, `keep.profit_factor_min`, and the expected
      retune wall. (DEBT-069(g), shipped 2026-06-30. Fly evidence showed no
      active 11-14 sample rows, but the structural scout/keep sample gap was
      closed by aligning `scout.sample_size_max` to 15; `keep` PF/win-rate
      defaults were retained.)

## Verification

- [x] `uv run pytest tests/test_strategy_performance.py tests/test_strategy_tuning_recommender.py -q`
      (2026-05-24 DEBT-069(e): 119 passed.)
- [x] `uv run pytest tests/test_strategy_tuning_observations.py tests/test_dashboard_strategies.py -q`
      (2026-06-10 DEBT-069(c): 36 passed.)
- [x] `uv run pytest tests/test_strategy_tuning_recommender.py -q`
      (2026-06-10 DEBT-069(c) regression: 38 passed.)
- [ ] `uv run pytest tests/test_runtime_engine.py tests/test_trading_sub_account.py tests/test_proposal_engine.py tests/test_baseline_strategies.py -q`
- [x] Targeted dashboard tests for strategy applied/recommended visibility
      and the "Apply recommendation" affordance.
- [x] Targeted recommender tests covering each action threshold path.

## Completion Checklist

- [x] Code implemented for all DEBT-069 Slice 2 sub-tasks.
- [x] Tests pass for all DEBT-069 Slice 2 sub-tasks.
- [x] Session log and cross-check added for all DEBT-069 Slice 2 sub-tasks.
- [x] `aidlc-docs/aidlc-state.md` updated for all DEBT-069 Slice 2 sub-tasks.

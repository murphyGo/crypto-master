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
      (Slice 1, 2026-05-13. PF approximation via best/worst PnL until
      `TechniquePerformance.gross_win`/`gross_loss` exposed — DEBT-069(e).)
- [x] Add `strategy_tuning` block to sub-account YAML schema with parsing,
      defaults, and validation; default `enabled: false`. (Slice 1.)
- [ ] Persist applied/recommended state and evidence snapshots via an
      observation store analogous to `PromotionObservationStore`.
      (Slice 2 — DEBT-069(c).)
- [x] Wire runtime proposal gating: `pause` rejects with structured reason,
      `shadow` records without opening, `scout` applies
      `scout_size_factor`, `retune` and `keep` pass through, `promote`
      mirrors the underlying state. (Slice 1; `_strategy_action_gate` after
      `_correlation_gate`.)
- [ ] Emit activity events for applied-state changes with operator/system
      attribution and evidence snapshot. (`STRATEGY_ACTION_APPLIED` enum
      reserved at `src/runtime/activity_log.py` but not yet emitted —
      Slice 2 / DEBT-069(d). `RETUNE_FLAGGED` advisory already emitted.)
- [ ] Surface applied/recommended state, evidence columns, history, and
      the "Apply recommendation" affordance on the Strategies dashboard.
      **Scope-split — Slice 2 (DEBT-069(a)).** Write path explicitly out of
      scope per resolved Open Decision; YAML clipboard helper instead.
- [ ] Seed initial recommendations for RSI family, `momentum_pinball_orb`,
      mean-reversion family, `raschke_holy_grail`, `ma_crossover`,
      `vcp_breakout`, `session_vwap_pullback`, and default/LLM strategies.
      (Slice 2 — DEBT-069(b).)
- [x] Add tests for recommender, runtime gating, config parsing, activity
      events, and dashboard rendering. (Slice 1 covers recommender +
      runtime gating + config parsing + `RETUNE_FLAGGED` event; dashboard
      tests and `STRATEGY_ACTION_APPLIED` emission tests deferred to
      Slice 2. Funnel `_STATE_TO_FIELD` aggregator unit-test gaps for the
      2 new states — DEBT-069(i).)

## Verification

- [ ] `uv run pytest tests/test_runtime_engine.py tests/test_trading_sub_account.py tests/test_proposal_engine.py tests/test_baseline_strategies.py -q`
- [ ] Targeted dashboard tests for strategy applied/recommended visibility
      and the "Apply recommendation" affordance.
- [ ] Targeted recommender tests covering each action threshold path.

## Completion Checklist

- [ ] Code implemented.
- [ ] Tests pass.
- [ ] Session log and cross-check added.
- [ ] `aidlc-docs/aidlc-state.md` updated.

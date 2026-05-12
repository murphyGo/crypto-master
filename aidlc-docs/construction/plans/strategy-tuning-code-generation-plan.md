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

- [ ] Implement the action-state recommender as a pure function over
      `PerformanceTracker` aggregates and DEBT-061 fail-closed metrics.
- [ ] Add `strategy_tuning` block to sub-account YAML schema with parsing,
      defaults, and validation; default `enabled: false`.
- [ ] Persist applied/recommended state and evidence snapshots via an
      observation store analogous to `PromotionObservationStore`.
- [ ] Wire runtime proposal gating: `pause` rejects with structured reason,
      `shadow` records without opening, `scout` applies
      `scout_size_factor`, `retune` and `keep` pass through, `promote`
      mirrors the underlying state.
- [ ] Emit activity events for applied-state changes with operator/system
      attribution and evidence snapshot.
- [ ] Surface applied/recommended state, evidence columns, history, and
      the "Apply recommendation" affordance on the Strategies dashboard.
- [ ] Seed initial recommendations for RSI family, `momentum_pinball_orb`,
      mean-reversion family, `raschke_holy_grail`, `ma_crossover`,
      `vcp_breakout`, `session_vwap_pullback`, and default/LLM strategies.
- [ ] Add tests for recommender, runtime gating, config parsing, activity
      events, and dashboard rendering.

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

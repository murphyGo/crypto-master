# Functional Design Plan: strategy-tuning

## Task

Define data-driven strategy-family actions for paper labs: pause, scout-size,
keep, promote, or retune based on deployed outcomes, open exposure, proposal
quality, and account-level evidence.

## Related Context

- Unit: `strategy-tuning`
- Stage: Functional Design
- Requirements: FR-001, FR-002, FR-005, FR-013, FR-027, FR-034, FR-036,
  FR-039, NFR-006, NFR-007
- Source evidence: 2026-05-13 Fly snapshot ranked `raschke_holy_grail` and
  `ma_crossover` as promising but under-sampled; RSI variants, default/simple
  trend, momentum ORB, and several mean-reversion accounts as pause or scout
  candidates.
- Related units: `strategy-framework`, `strategy-promotion-lab`,
  `sub-account-experiment-marketplace`, `market-regime`, `proposal-runtime`

## Steps

- [x] Specify strategy action states: `pause`, `shadow`, `scout`, `keep`,
      `promote`, `retune`.
- [x] Specify evidence thresholds for each action using closed PnL, win rate,
      profit factor, drawdown, sample size, open exposure, and proposal quality.
- [x] Specify initial actions for RSI family, mean-reversion family,
      `momentum_pinball_orb`, `vcp_breakout`, `raschke_holy_grail`,
      `ma_crossover`, `session_vwap_pullback`, and default/LLM strategies.
- [x] Specify dashboard/operator presentation and config-change workflow.
- [x] Create implementation plan covering strategy files, sub-account config,
      proposal gates, dashboard recommendations, and tests.

## Verification

- [x] Design artifact under `aidlc-docs/construction/strategy-tuning/`.
- [x] Target tests identified for strategy behavior, proposal policy, runtime
      account actions, and dashboard strategy evidence.

## Completion Checklist

- [x] Functional design complete.
- [x] Code-generation plan created.
- [ ] Session log and cross-check added when implemented.

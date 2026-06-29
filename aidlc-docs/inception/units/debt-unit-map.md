# Technical Debt Unit Map

## Purpose

This document maps active `docs/TECH-DEBT.md` items to AI-DLC units. It is a
planning index, not the debt source of truth. Update `docs/TECH-DEBT.md` first
when debt is added or resolved, then refresh this map.

## Active Debt by Unit

| Unit | Active Debt | Priority Mix | Notes |
|------|-------------|--------------|-------|
| `cross-account-risk-policy` | DEBT-068 | Medium | Slice 2 umbrella; next slice is opt-in global exposure caps with default-disabled, paper-advisory, live-hard-block semantics. |
| `strategy-tuning` | DEBT-069 | Medium | Slice 2 umbrella; remaining (g) threshold calibration. |
| `strategy-framework` | DEBT-076 | Low | Regime-gate score/threshold observability (076). DEBT-073 (fee-inclusive edge metrics) resolved 2026-06-26 — `net_*` aggregates on `TechniquePerformance` now feed the recommender's PF/closed-PnL. |

## Debt Details

| Debt | Priority | Primary Unit | Secondary Unit | Suggested Next Action |
|------|----------|--------------|----------------|-----------------------|
| DEBT-068 | Medium | `cross-account-risk-policy` | `proposal-runtime`, `runtime-safety-score`, `dashboard-operator-ui` | Implement opt-in global symbol/side caps with default-disabled config, paper advisory pass-through, live hard-block, and targeted runtime/config tests. |
| DEBT-069 | Medium | `strategy-tuning` | `proposal-runtime`, `dashboard-operator-ui`, `strategy-framework` | Implement Slice 2 dashboard/recommendation-history pass, then pause-reason and threshold-calibration follow-ups. |
| DEBT-076 | Low | `strategy-framework` | — | Set `score=avg, threshold=0` in the average-expectancy branch of the regime gate; add a test. |

## Promotion Candidates

No additional promotion candidates beyond DEBT-068 and DEBT-069.

## Update Rules

- If `docs/TECH-DEBT.md` moves an item to resolved, remove it here in the same
  change.
- If a new debt item references a legacy phase, map it through
  `legacy-phase-map.md` before assigning a unit.
- If a debt item spans multiple units, choose the unit that owns the first code
  change as primary and list the other as secondary.

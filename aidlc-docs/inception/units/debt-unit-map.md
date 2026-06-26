# Technical Debt Unit Map

## Purpose

This document maps active `docs/TECH-DEBT.md` items to AI-DLC units. It is a
planning index, not the debt source of truth. Update `docs/TECH-DEBT.md` first
when debt is added or resolved, then refresh this map.

## Active Debt by Unit

| Unit | Active Debt | Priority Mix | Notes |
|------|-------------|--------------|-------|
| `cross-account-risk-policy` | DEBT-068 | Medium | Slice 2 umbrella; next slice is opt-in global exposure caps with default-disabled, paper-advisory, live-hard-block semantics. |
| `strategy-tuning` | DEBT-069, DEBT-075 | Medium | Slice 2 umbrella; remaining (g) threshold calibration. DEBT-075 adds entry-time regime tagging (shared with strategy-framework) to unblock the promotion robustness gate. |
| `runtime-reconciliation` | DEBT-078 | Medium | DEBT-071/072 resolved 2026-06-26 (orphan age-backstop + SL/TP rehydration backfill + balance reconcile — both balance and position-state self-heal on restart). DEBT-077 (resolver fail-safe unit tests) resolved 2026-06-26. Residual: DEBT-078 (backfilled-then-stale SL/TP mislabel edge + consolidation of three duplicate bounds-resolution walks). |
| `strategy-framework` | DEBT-076 | Low | Regime-gate score/threshold observability (076). DEBT-073 (fee-inclusive edge metrics) resolved 2026-06-26 — `net_*` aggregates on `TechniquePerformance` now feed the recommender's PF/closed-PnL. |
| `proposal-funnel-audit` | DEBT-074 | Medium | Investigate why `vcp_breakout` emits ~6,400 proposals but opens zero trades. |

## Debt Details

| Debt | Priority | Primary Unit | Secondary Unit | Suggested Next Action |
|------|----------|--------------|----------------|-----------------------|
| DEBT-068 | Medium | `cross-account-risk-policy` | `proposal-runtime`, `runtime-safety-score`, `dashboard-operator-ui` | Implement opt-in global symbol/side caps with default-disabled config, paper advisory pass-through, live hard-block, and targeted runtime/config tests. |
| DEBT-069 | Medium | `strategy-tuning` | `proposal-runtime`, `dashboard-operator-ui`, `strategy-framework` | Implement Slice 2 dashboard/recommendation-history pass, then pause-reason and threshold-calibration follow-ups. |
| DEBT-074 | Medium | `proposal-funnel-audit` | `strategy-framework` | Trace one `vcp_breakout` proposal through the funnel; identify the terminating gate / persistence gap; file the concrete follow-up. |
| DEBT-075 | Medium | `strategy-framework` | `strategy-tuning` | Stamp each trade/proposal with a pre-entry SMA regime label so per-regime expectancy and the promotion robustness gate work. |
| DEBT-076 | Low | `strategy-framework` | — | Set `score=avg, threshold=0` in the average-expectancy branch of the regime gate; add a test. |
| DEBT-078 | Medium | `runtime-reconciliation` | `strategy-framework` | Route a backfilled-then-stale SL/TP breach to `orphan_force_close` instead of stamping a phantom `stop_loss`/`take_profit` at a stale price; consolidate the three duplicate bounds-resolution walks (new resolver + operator tools' `_PerfIndex` / `_proposal_bounds_index`) behind one implementation. |

## Promotion Candidates

No additional promotion candidates beyond DEBT-068 and DEBT-069.

## Update Rules

- If `docs/TECH-DEBT.md` moves an item to resolved, remove it here in the same
  change.
- If a new debt item references a legacy phase, map it through
  `legacy-phase-map.md` before assigning a unit.
- If a debt item spans multiple units, choose the unit that owns the first code
  change as primary and list the other as secondary.

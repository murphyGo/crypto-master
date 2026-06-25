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
| `runtime-reconciliation` | DEBT-077, DEBT-078 | Low/Medium | DEBT-071 (paper open-position rehydration / SL-TP enforcement) and its linked DEBT-072 (paper lock/unlock accounting drift) both resolved 2026-06-26 — the orphan age-backstop + SL/TP rehydration backfill closed the orphan-recurrence root cause; both balance and position-state now self-heal on restart. Residual follow-ups from that cycle: DEBT-077 (direct unit tests for the new `resolve_bounds_from_performance_record` fail-safe branches) and DEBT-078 (residual backfilled-then-stale SL/TP mislabel edge + consolidation of three duplicate bounds-resolution walks). |
| `strategy-framework` | DEBT-073, DEBT-076 | Medium/Low | Fee-inclusive edge metrics (073) and regime-gate score/threshold observability (076). |
| `proposal-funnel-audit` | DEBT-074 | Medium | Investigate why `vcp_breakout` emits ~6,400 proposals but opens zero trades. |

## Debt Details

| Debt | Priority | Primary Unit | Secondary Unit | Suggested Next Action |
|------|----------|--------------|----------------|-----------------------|
| DEBT-068 | Medium | `cross-account-risk-policy` | `proposal-runtime`, `runtime-safety-score`, `dashboard-operator-ui` | Implement opt-in global symbol/side caps with default-disabled config, paper advisory pass-through, live hard-block, and targeted runtime/config tests. |
| DEBT-069 | Medium | `strategy-tuning` | `proposal-runtime`, `dashboard-operator-ui`, `strategy-framework` | Implement Slice 2 dashboard/recommendation-history pass, then pause-reason and threshold-calibration follow-ups. |
| DEBT-073 | Medium | `strategy-framework` | `strategy-tuning` | Add a fee-netted percent and route PF/expectancy/closed_pnl_pct through it; fix stale `pnl_percent` docstring formula. |
| DEBT-074 | Medium | `proposal-funnel-audit` | `strategy-framework` | Trace one `vcp_breakout` proposal through the funnel; identify the terminating gate / persistence gap; file the concrete follow-up. |
| DEBT-075 | Medium | `strategy-framework` | `strategy-tuning` | Stamp each trade/proposal with a pre-entry SMA regime label so per-regime expectancy and the promotion robustness gate work. |
| DEBT-076 | Low | `strategy-framework` | — | Set `score=avg, threshold=0` in the average-expectancy branch of the regime gate; add a test. |
| DEBT-077 | Low | `runtime-reconciliation` | — | Add direct unit tests for `resolve_bounds_from_performance_record` fail-safe branches (missing file / null-bounds-on-found-record / corrupt JSON → `None`); only the happy path is covered end-to-end today. Test-only. |
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

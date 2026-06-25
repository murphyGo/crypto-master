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
| `runtime-reconciliation` | DEBT-071 | High | From 2026-06-26 Fly strategy-improvement analysis: paper open-position rehydration / SL-TP enforcement (071) gates strategy-logic work per §5. The linked DEBT-072 (paper lock/unlock accounting drift) was resolved 2026-06-26; its reconcile is the safety net that lets DEBT-071's stranded-margin scenario self-heal on restart, but DEBT-071's orphan-recurrence root cause is still open. |
| `strategy-framework` | DEBT-073, DEBT-076 | Medium/Low | Fee-inclusive edge metrics (073) and regime-gate score/threshold observability (076). |
| `proposal-funnel-audit` | DEBT-074 | Medium | Investigate why `vcp_breakout` emits ~6,400 proposals but opens zero trades. |

## Debt Details

| Debt | Priority | Primary Unit | Secondary Unit | Suggested Next Action |
|------|----------|--------------|----------------|-----------------------|
| DEBT-068 | Medium | `cross-account-risk-policy` | `proposal-runtime`, `runtime-safety-score`, `dashboard-operator-ui` | Implement opt-in global symbol/side caps with default-disabled config, paper advisory pass-through, live hard-block, and targeted runtime/config tests. |
| DEBT-069 | Medium | `strategy-tuning` | `proposal-runtime`, `dashboard-operator-ui`, `strategy-framework` | Implement Slice 2 dashboard/recommendation-history pass, then pause-reason and threshold-calibration follow-ups. |
| DEBT-071 | High | `runtime-reconciliation` | `proposal-runtime` | Rehydrate persisted open paper positions into in-memory state so the monitor enforces SL/TP; stop weeks-long orphan opens force-closed at stale prices. (DEBT-072 resolved 2026-06-26 — its restart reconcile lets the stranded-margin scenario self-heal, but does not rehydrate positions.) |
| DEBT-073 | Medium | `strategy-framework` | `strategy-tuning` | Add a fee-netted percent and route PF/expectancy/closed_pnl_pct through it; fix stale `pnl_percent` docstring formula. |
| DEBT-074 | Medium | `proposal-funnel-audit` | `strategy-framework` | Trace one `vcp_breakout` proposal through the funnel; identify the terminating gate / persistence gap; file the concrete follow-up. |
| DEBT-075 | Medium | `strategy-framework` | `strategy-tuning` | Stamp each trade/proposal with a pre-entry SMA regime label so per-regime expectancy and the promotion robustness gate work. |
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

# Technical Debt Unit Map

## Purpose

This document maps active `docs/TECH-DEBT.md` items to AI-DLC units. It is a
planning index, not the debt source of truth. Update `docs/TECH-DEBT.md` first
when debt is added or resolved, then refresh this map.

## Active Debt by Unit

| Unit | Active Debt | Priority Mix | Notes |
|------|-------------|--------------|-------|
| `backtesting-validation` | DEBT-022 | 1 Low | Circuit breaker completeness. |

## Debt Details

| Debt | Priority | Primary Unit | Secondary Unit | Suggested Next Action |
|------|----------|--------------|----------------|-----------------------|
| DEBT-022 | Low | `backtesting-validation` | | Add cumulative/rate-based parse failure breaker when a real workload needs it. |

## Promotion Candidates

No Medium-or-higher active debt remains in this map. The remaining candidate is
a Low-priority hardening item selected by operational need.

## Update Rules

- If `docs/TECH-DEBT.md` moves an item to resolved, remove it here in the same
  change.
- If a new debt item references a legacy phase, map it through
  `legacy-phase-map.md` before assigning a unit.
- If a debt item spans multiple units, choose the unit that owns the first code
  change as primary and list the other as secondary.

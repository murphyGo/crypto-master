# Technical Debt Unit Map

## Purpose

This document maps active `docs/TECH-DEBT.md` items to AI-DLC units. It is a
planning index, not the debt source of truth. Update `docs/TECH-DEBT.md` first
when debt is added or resolved, then refresh this map.

## Active Debt by Unit

| Unit | Active Debt | Priority | Next Action |
|------|-------------|----------|-------------|
| `dashboard-operator-ui` | DEBT-083 | 1 Critical | Shared-CPU read-side follow-up deployed on Fly v60 (`38876fc`); 2743 tests, source/health/first cycle and full Home/Trading protocol responses verified. Existing capacity retained; performance CPU / added-cost proposal remains deferred. Home/million cold and native/resource acceptance remain open. |

## Debt Details

| Debt | Priority | Primary Unit | Secondary Units | Resolution Path |
|------|----------|--------------|-----------------|-----------------|
| DEBT-083 | Critical | `dashboard-operator-ui` | `dashboard-operator-command-center`, `persistence-data-integrity`, `notifications-ops` | Fly v60 / `38876fc`: 2743 tests, 175 deployed hashes, health/first cycle and full Home/Trading protocol responses verified; Home 17.502s / Trading 2.480s. Unrelated-directory revalidation improves; million cold p95 remains 10.872s (>5s). Native/concurrency/guest acceptance remains open. Shared CPU 1 / 2048 MiB retained; performance CPU / cost proposal deferred. |

DEBT-082 is resolved by native production verification. The concurrent
DEBT-074/078/084/085/086 implementation closures are preserved in
`docs/TECH-DEBT.md`; their later source changes are not deployed as part of
the source35e14b4 production image.

## Promotion Candidates

No additional promotion candidates.

## Update Rules

- If `docs/TECH-DEBT.md` moves an item to resolved, remove it here in the same
  change.
- If a new debt item references a legacy phase, map it through
  `legacy-phase-map.md` before assigning a unit.
- If a debt item spans multiple units, choose the unit that owns the first code
  change as primary and list the other as secondary.

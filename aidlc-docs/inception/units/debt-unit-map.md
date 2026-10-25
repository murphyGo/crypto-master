# Technical Debt Unit Map

## Purpose

This document maps active `docs/TECH-DEBT.md` items to AI-DLC units. It is a
planning index, not the debt source of truth. Update `docs/TECH-DEBT.md` first
when debt is added or resolved, then refresh this map.

## Active Debt by Unit

| Unit | Active Debt | Priority | Next Action |
|------|-------------|----------|-------------|
| `dashboard-operator-ui` | DEBT-083 | 1 Critical | v62 / `d86f76f`: 2823 tests, 175 hashes/health/cycles pass. Final 4-session run records 276/280 complete views and four 30s timeouts; guest peak 1293.313 MiB fails 768. Cold/native/depleted/1 GiB remain open. Base Functional Designs approved; two NFR designs and typed safety-failure monitoring amendment await review. Current capacity/cost gate retained. |

## Debt Details

| Debt | Priority | Primary Unit | Secondary Units | Resolution Path |
|------|----------|--------------|-----------------|-----------------|
| DEBT-083 | Critical | `dashboard-operator-ui` | `dashboard-operator-command-center`, `persistence-data-integrity`, `notifications-ops`, `runtime-safety-score`, `proposal-runtime` | v62 / `d86f76f`, 2823 tests, 175 hashes/health/cycles pass. Four 30s views and 1293.313 MiB guest peak fail final qualification. Engine full-history safety input and pause consumer traced; base checkpoint/streaming-time Functional Designs approved. Concrete NFR candidates and monitoring-isolation amendment pending review. Native/depleted/1 GiB and cold goals remain open; cost upgrade stays deferred. |

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

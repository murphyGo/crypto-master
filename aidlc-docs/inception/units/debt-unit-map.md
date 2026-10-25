# Technical Debt Unit Map

## Purpose

This document maps active `docs/TECH-DEBT.md` items to AI-DLC units. It is a
planning index, not the debt source of truth. Update `docs/TECH-DEBT.md` first
when debt is added or resolved, then refresh this map.

## Active Debt by Unit

| Unit | Active Debt | Priority | Next Action |
|------|-------------|----------|-------------|
| `dashboard-operator-ui` | DEBT-083 | 1 Critical | Production v63 / `f0f3e52`, 177 hashes and health checked. Runtime NFR and typed-failure monitoring amendment approved 2026-10-26; bounded source implementation passes 3,008 tests and independent review, rollout pending. Dashboard checkpoint remains the separate next step. Original cold/native/depleted/concurrency/1 GiB guest targets remain open; capacity/cost deferral retained. |

## Debt Details

| Debt | Priority | Primary Unit | Secondary Units | Resolution Path |
|------|----------|--------------|-----------------|-----------------|
| DEBT-083 | Critical | `dashboard-operator-ui` | `dashboard-operator-command-center`, `persistence-data-integrity`, `notifications-ops`, `runtime-safety-score`, `proposal-runtime` | Runtime streaming and explicit failure-isolation amendment approved 2026-10-26; source implementation/compatibility and archived 229,677-row/million-row parity pass with 3,008 tests. Authorized same-capacity rollout pending. Production remains v63 / `f0f3e52`. Prior failed readiness/guest evidence remains; dashboard checkpoints, native/depleted/declared 1 GiB acceptance and deferred CPU/cost are separate. |

DEBT-087/088/089 were registered and resolved in source/tests on 2026-10-25.
Primary units: `proposal-runtime`, `proposal-funnel-audit`, `strategy-framework`.
Combined three-fix verification: 2,865 tests and fixed-snapshot replay pass.
All three were individually pushed and deployed on Fly v63 / f0f3e52 on
2026-10-26 KST. Source hashes, health/first-cycle and deployed read-only replay
pass; new natural proposal/cap events were absent in the observed cycle.
Existing DEBT-083 design/activation gates remain independent.
Actual funding settlement accounting is outside DEBT-089's closed scope.

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

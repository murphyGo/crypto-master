# Technical Debt Unit Map

## Purpose

This document maps active `docs/TECH-DEBT.md` items to AI-DLC units. It is a
planning index, not the debt source of truth. Update `docs/TECH-DEBT.md` first
when debt is added or resolved, then refresh this map.

## Active Debt by Unit

| Unit | Active Debt | Priority | Next Action |
|------|-------------|----------|-------------|
| `dashboard-operator-ui` | DEBT-083 | 1 Critical | V71/0e14f9d includes the resolved exchange containment repair;3,127tests,183hashes pass. Prior v70 rearming observation remains historical.144/144complete and145/145health in repeated sample, but one exchange engine error fails full gate. Initial snapshot parser improvement delivered as v72/source71c8787 (36.3% standalone probe,3,161tests,183hashes).1387s/277complete/275health and12-account natural cycle pass; p95 Home0.584/Trading0.678s. Four13.19–15.18s tail responses retained. Codec threshold-sizing follow-up passes3197tests/242comparisons and improves isolated activity rebuild13.34%; delivery pending. Retain native/cold/depleted/original1GiB/cost gates and all failed samples. |

## Debt Details

| Debt | Priority | Primary Unit | Secondary Units | Resolution Path |
|------|----------|--------------|-----------------|-----------------|
| DEBT-083 | Critical | `dashboard-operator-ui` | `dashboard-operator-command-center`, `persistence-data-integrity`, `notifications-ops`, `runtime-safety-score`, `proposal-runtime` | V71/0e14f9d source and deployment integrity pass; DEBT-090 is resolved. Both operational samples remain failed (host sleep; exchange418). Initial Home13.10s, later6.38s; remaining original gates unchanged. |

DEBT-090 resolved2026-11-11: source0e14f9d/Flyv71, shared endpoint cooldown and
transport containment;3,127 tests,183hashes/settings, deployed mock fault checks
and12-account natural monitor cycle pass. See the exchange containment session.
This does not reopen or qualify prior DEBT-083 failed samples.

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

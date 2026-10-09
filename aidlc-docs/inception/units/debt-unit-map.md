# Technical Debt Unit Map

## Purpose

This document maps active `docs/TECH-DEBT.md` items to AI-DLC units. It is a
planning index, not the debt source of truth. Update `docs/TECH-DEBT.md` first
when debt is added or resolved, then refresh this map.

## Active Debt by Unit

| Unit | Active Debt | Priority | Next Action |
|------|-------------|----------|-------------|
| `notifications-ops` | DEBT-082 | 1 Medium | Complete native CLI help/flag acceptance and the now-authorized commit/push/rollout with production verification. |
| `proposal-funnel-audit` | DEBT-086 | 1 Low | Correct neutral/unknown funnel interpretations while retaining legacy evidence. |

## Debt Details

| Debt | Priority | Primary Unit | Secondary Units | Resolution Path |
|------|----------|--------------|-----------------|-----------------|
| DEBT-082 | Medium | `notifications-ops` | `ai-feedback-loop` | Replace unsupported Node/CLI image composition using pinned compatible versions and strict build assertions; preserve CLI/auth/trading boundaries. Approved Dockerfile repair applied; 171 focused tests and static QA pass. Target amd64 build, packaging, and isolated health pass; runtime acceptance is PARTIAL (CLI help on local emulation). Production rollout remains pending. |
| DEBT-086 | Low | `proposal-funnel-audit` | `dashboard-operator-ui` | Keep unknown acceptance separate; show observed/unknown counts without guessing or rewriting historical terminal state. |

## Promotion Candidates

No additional promotion candidates.

## Update Rules

- If `docs/TECH-DEBT.md` moves an item to resolved, remove it here in the same
  change.
- If a new debt item references a legacy phase, map it through
  `legacy-phase-map.md` before assigning a unit.
- If a debt item spans multiple units, choose the unit that owns the first code
  change as primary and list the other as secondary.

# Session Log: 2026-05-03 - quality-governance - Debt Unit Map

## Overview

- **Date**: 2026-05-03
- **Unit**: `quality-governance`
- **Task**: Map active technical debt to AI-DLC units.

## Work Summary

Added a unit-oriented debt planning index so active `docs/TECH-DEBT.md` items
can be selected and promoted by AI-DLC unit. Connected the new index from
`AGENTS.md`, `aidlc-state.md`, `unit-of-work.md`, and the `dev-crypto` /
`tech-debt` skills.

## Files Changed

- Created: `aidlc-docs/inception/units/debt-unit-map.md`
- Modified: `aidlc-docs/aidlc-state.md`
- Modified: `aidlc-docs/inception/units/unit-of-work.md`
- Modified: `AGENTS.md`
- Modified: `.agents/skills/dev-crypto/SKILL.md`
- Modified: `.agents/skills/tech-debt/SKILL.md`
- Created: `docs/sessions/2026-05-03-quality-governance-debt-unit-map.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Keep `docs/TECH-DEBT.md` as source of truth | Avoids splitting debt lifecycle state across two documents. |
| Use `debt-unit-map.md` as a planning index | Makes unit selection and promotion easier without mutating historical debt entries. |
| List promotion candidates | Gives `/dev-crypto` a practical next-work queue after brownfield adoption. |

## Verification

- Documentation-only change.
- No source code or tests changed.

## Risks

- The debt map can drift if `docs/TECH-DEBT.md` changes without updating this
  index. The update rules in `debt-unit-map.md` call this out explicitly.

## TECH-DEBT Items

- None.


---
name: tech-debt
description: Inspect and manage Crypto Master technical debt by priority and brownfield unit.
---

# Crypto Master Tech Debt Skill

## Arguments

- `$ARGUMENTS`
  - empty or `all`: show all active debt
  - `aged`: show items past escalation thresholds
  - `critical`, `high`, `medium`, `low`: filter by priority
  - `unit:<unit>`: show debt related to a brownfield unit
  - `promote DEBT-NNN`: propose a development task for a debt item

## Objective

Keep debt visible and actionable. New issues discovered during development or
review should be fixed immediately when small and safe, or tracked in
`docs/TECH-DEBT.md` with enough context to act later.

## Escalation Thresholds

| Priority | Threshold |
|----------|-----------|
| Critical | Immediate |
| High | 14 days |
| Medium | 21 days |
| Low | 30 days |

## Execution Steps

1. Read `docs/TECH-DEBT.md`.
2. Parse active items, priority, creation date, component, and related paths.
3. Map items to units using `aidlc-docs/inception/units/unit-of-work.md`.
4. Present a concise dashboard or filtered list.
5. For promotion, propose a unit-oriented task and target tests.

## Promotion Output

```markdown
## Debt Promotion Proposal

**Debt**: DEBT-NNN - <title>
**Unit**: <unit>
**Priority/Age**: <priority>, <age>

### Proposed Task
- [ ] <implementation step>
- [ ] <test step>
- [ ] Update session/cross-check docs
- [ ] Mark debt resolved
```


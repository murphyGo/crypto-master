---
name: cross-check
description: Verify Crypto Master implementation against requirements by brownfield unit.
---

# Crypto Master Cross-Check Skill

## Arguments

- `$ARGUMENTS`
  - `<unit>`: verify a unit from `aidlc-docs/inception/units/unit-of-work.md`
  - `phase<N>`: verify legacy phase context
  - empty: infer from current changes

## Objective

Verify that implementation, tests, and documentation satisfy the relevant
requirements without regressing brownfield behavior.

## Execution Steps

1. Read `aidlc-docs/inception/requirements/requirements.md`.
2. Read `aidlc-docs/inception/requirements/requirement-verification-questions.md`.
3. Read `aidlc-docs/inception/user-stories/stories.md`.
4. Read `aidlc-docs/inception/application-design/unit-of-work-story-map.md`.
5. Read `aidlc-docs/inception/units/unit-of-work.md`.
6. Read `aidlc-docs/inception/units/legacy-phase-map.md` when the argument
   references a legacy phase, component, or historical cross-check.
7. Read `aidlc-docs/inception/units/debt-unit-map.md` when the work closes,
   promotes, or discovers technical debt.
8. Identify related FR/NFR IDs, user stories, and owned files.
9. Read implementation and tests in scope.
10. Compare behavior against:
   - `aidlc-docs/inception/requirements/requirements.md`
   - `aidlc-docs/inception/user-stories/stories.md`
   - `DESIGN.md`
   - `docs/requirements.md` for historical detailed requirement text
   - relevant session logs and previous cross-checks
11. Run targeted tests when practical.
12. Generate or update a report in `docs/cross-checks/`.

## Report Template

```markdown
# Cross-Check: <unit or phase>

## Scope

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|

## Story Matrix

| Story | Status | Evidence |
|-------|--------|----------|

## Implementation Evidence

## Test Evidence

## Gaps and Risks

## Unit and Debt Mapping

- **Primary Unit**:
- **Secondary Units**:
- **Related Debt**:
- **Legacy Phase Context**:

## Recommendations
```

## Status Criteria

| Status | Criteria |
|--------|----------|
| Complete | Implemented, tested, documented, no known blocking gaps |
| Partial | Implemented but test/docs/edge case coverage is incomplete |
| Gap | Requirement not implemented or behavior contradicts requirement |
| Deferred | Explicitly deferred with documented reason |

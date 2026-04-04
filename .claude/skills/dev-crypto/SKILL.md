# Crypto Master Development Skill

Incrementally develops the Crypto Master service following the development plan.

## Arguments

- `$ARGUMENTS` - (Optional) Specific Phase or task (e.g., `phase2`, `2.1`)

## Objective

Execute one sub-task at a time from the development plan to incrementally build the Crypto Master service. Ensure quality through requirements compliance, best practices, and unit tests.

---

## Execution Steps

### Step 0: Health Check (Automatic)

Automatic status check before starting development:

1. **TECH-DEBT Escalation Check**:
   - Read `docs/TECH-DEBT.md`
   - Check items exceeding thresholds:
     - Critical: Any age → Alert
     - High: > 14 days → Alert
     - Medium: > 21 days → Warn
   - Display if escalation candidates found:
     ```
     ⚠️ TECH-DEBT Alert

     | DEBT ID | Priority | Age | Action Suggested |
     |---------|----------|-----|------------------|
     | DEBT-001 | High | 16d | Consider /tech-debt promote |

     Continue with development? (yes/no/review-debt)
     ```

2. **Phase Completion Check**:
   - Scan completed Phases in `docs/development-plan.md`
   - Check existing reviews in `docs/cross-checks/`
   - If unchecked Phase found:
     ```
     📋 Phase Review Pending

     Phase 1 is complete but no cross-check document exists.
     Run cross-check now? (yes/no/later)
     ```

**Note**: Health check alerts are informational. You can proceed with "yes" or address issues first.

### Step 1: Environment Validation

1. **Verify Path Existence**:
   - `docs/development-plan.md`
   - `docs/TECH-DEBT.md`
   - `docs/requirements.md`
   - `CLAUDE.md`
   - `DESIGN.md`

### Step 2: Analyze Development Plan

1. **Read**: `docs/development-plan.md`

2. **Parse Plan**:
   - Current status table (component completion status)
   - All Phases and sub-tasks
   - Checkbox status: `[x]` = complete, `[ ]` = incomplete

3. **Find Next Development Target** (scan top to bottom):
   - Skip fully checked `[x]` Phases/sub-tasks
   - Skip items marked "deferred" or "— *deferred*"
   - Select **first sub-task** with at least one unchecked `[ ]` item
   - For mixed-status sub-tasks, target only unchecked items

### Step 3: Present Development Target

Present identified sub-task in this format:

```
## Next Development Target

**Phase**: [Phase number and name]
**Sub-task**: [Sub-task number and title]

### Items to Develop:
- [ ] Item 1 description
- [ ] Item 2 description
...

### Related Requirements:
- FR-XXX: [Requirement description]
- NFR-XXX: [Requirement description]

### Estimated Files:
- New: [List of files to create]
- Modified: [List of files to modify]

Proceed with this development? (yes/no)
```

**Wait for user approval before proceeding.**

### Step 4: Development (Plan Mode)

After user approval:

1. **Enter Plan Mode**: Use `EnterPlanMode` tool

2. **Research Phase**:
   - Read related requirements from `docs/requirements.md`
   - Check design patterns in `DESIGN.md`
   - Explore existing codebase for patterns and dependencies

3. **Write Implementation Plan**:
   - Files to create/modify
   - Implementation approach aligned with requirements
   - Test strategy (unit tests for all new features)
   - Integration points with existing code

4. **Exit Plan Mode** and implement:
   - Strictly follow Python best practices
   - Write clean, idiomatic Python code
   - Include comprehensive unit tests
   - Run tests to verify: `pytest`

### Step 5: Self-Review & Documentation

After successful implementation:

**5.1 Code Review** (Automatic):
- Run `/code-review git` on changed files
- If 🔴 Critical/High issues found, fix before proceeding or document in TECH-DEBT

**5.2 Create Session Log** (`docs/sessions/YYYY-MM-DD-<phase>-<task>.md`):

```markdown
# Session Log: YYYY-MM-DD - Phase N.M - [Task Title]

## Overview
- **Date**: YYYY-MM-DD
- **Phase**: N - [Phase Name]
- **Sub-task**: N.M - [Sub-task Name]

## Work Summary
[Brief description of completed work]

## Files Changed
- Created: [List]
- Modified: [List]

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| [What] | [Why] |

## Code Review Results
| Category | Status |
|----------|--------|
| Error Handling | ✅/⚠️/🔴 |
| Resource Management | ✅/⚠️/🔴 |
| Security | ✅/⚠️/🔴 |
| Type Hints | ✅/⚠️/🔴 |
| Tests | ✅/⚠️/🔴 |

## Potential Risks
- [Identified risks]

## TECH-DEBT Items
- [New items to track, if any]
```

**5.3 Update TECH-DEBT.md** (if applicable):
- Add new debt items discovered during implementation
- Add unfixed issues from code review
- Mark resolved debt items

**5.4 Create ADR** (if significant architectural decision was made):

ADR-worthy decisions:
- Affects system architecture or component boundaries
- Chooses between multiple valid approaches
- Has long-term implications worth documenting

If ADR needed:
1. Find highest existing number in `docs/adr/`
2. Create `docs/adr/NNNN-<short-title>.md` using `docs/adr/TEMPLATE.md`
3. Reference ADR in session log


### Step 6: Update Development Plan

After documentation:

1. **Update Checkboxes**:
   - Mark completed items with `[x]`
   - When all items in a sub-task are complete, consider sub-task header complete

2. **Update Current Status Table**:
   - `✅ Complete` - All related sub-tasks complete
   - `🔄 In Progress` - Some sub-tasks complete
   - `❌ Missing` - No sub-tasks started

3. **Suggest Additions** (if applicable):
   - If additional needs discovered during implementation, suggest new sub-task
   - Format: "Suggested addition to Phase X: [description]"

4. **Phase Completion Auto-Action** (if Phase just completed):
   - Detect: All sub-tasks in current Phase are `[x]`
   - Trigger automatic cross-check:
     ```
     🎉 Phase [N] Complete!

     All sub-tasks in Phase [N] are complete.
     Running automatic cross-check against requirements...
     ```
   - Execute `/cross-check` logic inline:
     - Verify implementation vs requirements
     - Generate compliance matrix
     - Create `docs/cross-checks/phase-N-[name].md`
   - Report found gaps:
     ```
     Cross-Check Results:
     - ✅ Complete: X requirements
     - ⚠️ Partial: Y requirements
     - ❌ Gap: Z requirements

     [If gaps exist] Add gap items to next Phase? (yes/no)
     ```

### Step 7: Summary Report

Provide completion summary:

```
## Development Complete

**Sub-task**: [Sub-task number and title]
**Status**: Complete

### Changes Made:
- Created: [List of new files]
- Modified: [List of modified files]

### Tests:
- Added: [count] new tests
- All tests passing: Yes/No

### Documentation:
- Session Log: [filename]
- TECH-DEBT: [Added/resolved items, if any]

### Feedback Loop Actions:
- TECH-DEBT: [Added/resolved items]
- Cross-Check: [Generated on Phase completion / Not needed]

### Phase Completion: (if applicable)
- Phase [N] complete: Yes/No
- Cross-check generated: [filename]
- Compliance rate: [X]% complete
- Gaps added to next Phase: [count]

### Development Plan Updated:
- [List of checkbox changes]
- Current status: [Component] → [New status]

### Next Sub-task Preview:
[Brief description of next incomplete sub-task, if any]
```

---

## Guidelines

### Commit Policy

**No Auto-Commit**: Do not automatically commit changes. Always show changes to the user and get explicit approval before committing.

### Sub-task Selection Rules

1. **One sub-task per execution** - Don't develop multiple sub-tasks in a single run
2. **Skip deferred items** - Items marked "deferred" or "— *deferred to Phase X*" are not development targets
3. **Partial completion** - For sub-tasks with some completed items, only develop remaining incomplete items
4. **Sequential order** - Always process Phases and sub-tasks in document order (top to bottom)

### Development Standards

1. **Requirements Compliance**:
   - All implementations must match `docs/requirements.md`
   - Reference requirement IDs in code comments (e.g., FR-001, NFR-001)

2. **Python Best Practices**:
   - Follow PEP 8 style guide
   - Use type hints
   - Error handling with context
   - Test with pytest

3. **Test Requirements**:
   - Unit tests required for all new functions/methods
   - Test both success and error paths
   - Use `tmp_path` fixture for file-based tests
   - Mock external dependencies

4. **Code Structure**:
   - New code goes in `src/` package
   - Follow existing project structure patterns

### Development Plan Update Rules

1. **Checkbox Updates**:
   ```markdown
   - [x] Completed item    # Check when complete
   - [ ] Pending item      # Unchecked when incomplete
   ```

2. **Status Mapping**:
   | Condition | Status |
   |-----------|--------|
   | All sub-tasks complete | `✅ Complete` |
   | At least one sub-task complete | `🔄 In Progress` |
   | No sub-tasks started | `❌ Missing` |

3. **Adding New Sub-tasks**:
   - Suggest only, don't add without user approval
   - Format suggestions clearly with rationale

---

## Error Handling

- **No incomplete sub-tasks**: Report "All sub-tasks in development plan are complete!"
- **Test failures**: Don't mark sub-task as complete; report failures and suggest fixes
- **Build errors**: Fix before proceeding; don't update development plan until resolved

---

## Example Invocations

Develop next pending task:
```
/dev-crypto
```

Work on specific Phase:
```
/dev-crypto phase2
```

Work on specific sub-task:
```
/dev-crypto 2.1
```

# Cross-Check Skill

Verifies alignment between design documents and implementation, generating compliance reports.

## Arguments

- `$ARGUMENTS` - Component or Phase to verify (e.g., `analyzer`, `strategy`, `phase2`)

## Objective

Systematically verify that implementation matches requirements from design documents (CLAUDE.md, DESIGN.md, docs/requirements.md), identify gaps, and generate actionable reports for development plan updates.

---

## Execution Steps

### Step 1: Input Validation

1. **Parse Arguments**:
   - Component name or Phase identifier

2. **Verify Path Existence**:
   - `CLAUDE.md`
   - `DESIGN.md`
   - `docs/requirements.md`
   - `docs/development-plan.md`

3. **Identify Scope**:
   - Map arguments to related requirements and implementation files

### Component-to-File Mapping Guide

| Component | Related Files | Requirements |
|-----------|---------------|--------------|
| analyzer | `src/analyzer/*.py` | FR-001, FR-002 |
| strategy | `src/strategy/*.py` | FR-003, FR-004 |
| trader | `src/trader/*.py` | FR-005, FR-006 |
| exchange | `src/exchange/*.py` | FR-007, FR-008 |
| dashboard | `src/dashboard/*.py` | FR-009, FR-010 |
| config | `src/config.py` | NFR-001, NFR-002 |

### Step 2: Load Requirements

1. **Read Requirements Document**: `docs/requirements.md`

2. **Extract Requirements**:
   - Functional Requirements (FR-XXXX)
   - Non-Functional Requirements (NFR-XXXX)
   - Status information

3. **Generate Requirements Checklist** (organized by category)

### Step 3: Analyze Implementation

1. **Read Implementation Files in Scope**:
   - Source code in `src/` directory
   - Test files (for coverage analysis)

2. **Map Requirements to Code**:
   - Search for requirement ID references in code comments
   - Trace function implementations to requirements
   - Verify test coverage per requirement

3. **Check Non-Functional Requirements**:
   - Error handling patterns
   - Security: environment variable usage
   - Logging implementation

### Step 4: Generate Compliance Matrix

Determine status for each requirement:

| Status | Criteria |
|--------|----------|
| ✅ Complete | Fully implemented, tested, documented |
| ⚠️ Partial | Implemented but missing tests/docs/edge cases |
| ❌ Gap | Not implemented |
| 🔄 Deferred | Explicitly deferred (with reason) |

### Step 5: Identify Gaps and Actions

1. **For each Gap (❌)**:
   - Document what's missing
   - Assess impact
   - Suggest development plan addition

2. **For each Partial (⚠️)**:
   - Document remaining work
   - Classify as Critical vs Enhancement

3. **Generate Suggested Tasks**:
   ```
   GAP-001: [Description] → Add to Phase X
   ```

### Step 6: Generate Cross-Check Document

1. **Generate Filename**: `docs/cross-checks/<component>-check.md`

2. **Write Sections**:
   - Scope overview
   - Compliance matrix with all requirements
   - Gap analysis with suggested actions
   - Partial implementation details
   - Test coverage summary
   - Recommendations

### Step 7: Suggest Development Plan Updates

If gaps are found, present suggested changes:

```
## Suggested Development Plan Updates

### New Tasks from Cross-Check

**Phase X.Y - [New Task Title]**
Source: GAP-001 from cross-check
- [ ] [Item derived from gap 1]
- [ ] [Item derived from gap 2]

Add to development-plan.md? (yes/no)
```

### Step 8: Summary Report

```
## Cross-Check Complete

**Component**: [identifier]
**Date**: YYYY-MM-DD

### Compliance Summary
| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | N | X% |
| ⚠️ Partial | N | X% |
| ❌ Gap | N | X% |
| 🔄 Deferred | N | X% |

### Generated Actions
- Gaps → Development Plan: [count]
- Partial → TECH-DEBT: [count]
- Test Gaps Identified: [count]

### Generated Documents
- Cross-Check: `docs/cross-checks/[filename]`

### Recommended Next Steps
1. [Priority action]
2. [Secondary action]
```

---

## Requirement Status Criteria

### Complete (✅)
- Code implements the requirement
- Unit tests exist and pass
- Error cases handled
- Documented (comments or docs)

### Partial (⚠️)
- Core functionality works but:
  - Edge case handling missing
  - Tests incomplete
  - Performance unverified
  - Documentation missing

### Gap (❌)
- Requirement not addressed in code
- Causes:
  - Missed during implementation
  - Blocked by dependencies
  - Out of current scope

### Deferred (🔄)
- Explicitly marked as "deferred" in plan
- Documented reason exists
- Planned for future Phase

---

## Integration with Other Skills

### Cross-Check Triggers
- Automatically after `/dev-crypto` Phase completion
- Manual invocation for re-verification

### Cross-Check Output Targets
- **Development Plan**: New tasks from gaps
- **TECH-DEBT**: Partial implementations
- **Session Log**: Referenced in related sessions

---

## Guidelines

### Scope Control
- One component per cross-check
- Don't combine unrelated features
- Keep compliance matrix focused

### Gap Prioritization
| Gap Type | Priority | Action |
|----------|----------|--------|
| Core functionality | Critical | Blocks Phase completion |
| Edge cases | High | Add to current Phase |
| Nice-to-have | Medium | Defer to next Phase |
| Documentation | Low | Add to Tech debt |

### Verification Methods
- **Code Review**: Manual inspection
- **Test Execution**: Run related tests
- **Static Analysis**: Pattern checking
- **Spec Comparison**: Line-by-line verification

---

## Example Invocations

Verify analyzer:
```
/cross-check analyzer
```

Verify strategy:
```
/cross-check strategy
```

Verify entire Phase:
```
/cross-check phase1
```

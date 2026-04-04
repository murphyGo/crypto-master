# Tech Debt Skill

Displays technical debt dashboard and manages debt items.

## Arguments

- `$ARGUMENTS` - One of the following:
  - (empty) or `all` - Show full dashboard
  - `critical`, `high`, `medium`, `low` - Filter by priority
  - `category:<name>` - Filter by category (e.g., `category:security`)
  - `aged` - Show items exceeding escalation threshold
  - `promote DEBT-NNN` - Promote specific debt item to development plan
  - `promote auto` - Auto-select and promote based on escalation criteria

## Objective

Provide a comprehensive view of technical debt and enable promotion of debt items to development tasks.

---

## Execution Steps

### Step 1: Parse Arguments

| Argument | Mode |
|----------|------|
| (empty), `all` | Dashboard mode |
| `critical`, `high`, `medium`, `low` | Filter mode |
| `category:<name>` | Filter mode |
| `aged` | Filter mode |
| `promote DEBT-NNN` | Promote mode (specific) |
| `promote auto` | Promote mode (auto-select) |

---

## Dashboard Mode

### Step 2: Load TECH-DEBT

1. **Read**: `docs/TECH-DEBT.md`
2. **Parse**: All sections:
   - Summary table
   - Active items by priority
   - Resolved items

### Step 3: Calculate Statistics

Extract from each active debt item:
- DEBT ID, title, priority, category
- Added date, days elapsed
- Location, Blocked by (if any)

### Step 4: Apply Filters (if filter mode)

| Filter | Behavior |
|--------|----------|
| `all` (default) | Show all active items |
| `critical` | Critical priority only |
| `high` | High priority only |
| `medium` | Medium priority only |
| `low` | Low priority only |
| `category:<name>` | Filter by category |
| `aged` | Items exceeding escalation threshold |

### Step 5: Generate Dashboard

```
## TECH-DEBT Dashboard

**Service**: crypto-master
**Generated**: YYYY-MM-DD HH:MM

---

### Health Status: 🟢 Good / 🟡 Warning / 🔴 Critical

[Description based on health indicators]

---

### Summary

| Priority | Count | Oldest | Avg Age |
|----------|-------|--------|---------|
| Critical | 0 | - | - |
| High | N | Xd | Yd |
| Medium | N | Xd | Yd |
| Low | N | Xd | Yd |
| **Total** | **N** | - | **Zd** |

---

### Escalation Alerts

| DEBT ID | Priority | Age | Threshold | Status |
|---------|----------|-----|-----------|--------|
| DEBT-001 | High | 16d | 14d | ⚠️ Promotion recommended |

---

### Active Items by Priority

#### Critical Priority
_No critical items._

#### High Priority
| ID | Title | Category | Age | Location |
|----|-------|----------|-----|----------|
| DEBT-001 | [Title] | Performance | 16d | `src/file.py:NN` |

#### Medium Priority
| ID | Title | Category | Age | Location |
|----|-------|----------|-----|----------|
| DEBT-002 | [Title] | Testing | 25d | `src/file.py:NN` |

---

### Quick Actions

- Promote aged item: `/tech-debt promote DEBT-001`
- Auto promote: `/tech-debt promote auto`
- View specific priority: `/tech-debt high`
```

---

## Promote Mode

### Step 2P: Select Promotion Candidate

#### If `promote DEBT-NNN`:
1. **Find**: Specified debt item
2. **Validate**: Exists and is active
3. **Proceed**: To Step 3P

#### If `promote auto`:
1. **Apply Escalation Criteria**:
   - Critical priority → Always promote
   - High priority + over 14 days → Promote
   - Medium priority + over 21 days → Consider
   - 3+ items in same category → Promote oldest

2. **Rank Candidates** (by urgency)
3. **Select Top Candidate** or present list for user selection:
   ```
   ## Auto-Promote Candidates

   | # | DEBT ID | Priority | Age | Reason |
   |---|---------|----------|-----|--------|
   | 1 | DEBT-001 | High | 16d | Exceeds 14d threshold |
   | 2 | DEBT-002 | Medium | 25d | Exceeds 21d threshold |

   Select item to promote (1-N) or 'cancel':
   ```

### Step 3P: Analyze Debt Item

1. **Read Debt Item Details**:
   - Description, Impact, Remediation steps
   - Estimated effort, Location

2. **Determine Target Phase**:
   - If blocking → Current Phase
   - If improvement → Next Phase

### Step 4P: Generate Sub-task

Convert debt to development plan format:

```markdown
### X.Y - Resolve [DEBT-NNN]: [Short Title]

**Source**: TECH-DEBT promotion
**Original Priority**: [Priority]

- [ ] [Remediation step 1]
- [ ] [Remediation step 2]
- [ ] Add/update tests
- [ ] Mark DEBT-NNN resolved
```

### Step 5P: Present Proposal

```
## Debt Promotion Proposal

### Source Item

**DEBT ID**: DEBT-NNN
**Title**: [Title]
**Priority**: [Priority] | **Age**: [X days]
**Category**: [Category]

**Description**:
[Description from TECH-DEBT]

### Proposed Development Task

**Target**: Phase X, Sub-task X.Y

```markdown
### X.Y - Resolve DEBT-NNN: [Title]

- [ ] [Task 1]
- [ ] [Task 2]
- [ ] Update tests
- [ ] Mark DEBT-NNN resolved
```

Add to development-plan.md? (yes/no)
```

### Step 6P: Update Documents (on approval)

1. **Update development-plan.md**:
   - Add new sub-task to appropriate Phase
   - Include `[DEBT-NNN]` reference

2. **Update TECH-DEBT.md**:
   - Add note: "Promoted to Phase X.Y on YYYY-MM-DD"
   - Keep active until resolved

### Step 7P: Summary

```
## Promotion Complete

**DEBT Item**: DEBT-NNN - [Title]
**Promoted To**: Phase X.Y

### Changes Made
- development-plan.md: Sub-task X.Y added
- TECH-DEBT.md: Promotion note added

### Next Steps
1. Run /dev-crypto to work on promoted task
2. Mark DEBT-NNN resolved when complete
```

---

## Escalation Criteria

| Priority | Age Threshold | Action |
|----------|---------------|--------|
| Critical | 0 days | Auto promote |
| High | 14 days | Recommend promotion |
| Medium | 21 days | Suggest promotion |
| Low | 30 days | Consider promotion |

### Additional Triggers

| Condition | Action |
|-----------|--------|
| Blocking current work | Immediate promotion |
| 3+ items in same category | Promote oldest |
| Security related | Elevate priority |

---

## Health Indicators

| Indicator | 🟢 Good | 🟡 Warning | 🔴 Critical |
|-----------|---------|------------|-------------|
| Total count | < 5 | 5-10 | > 10 |
| Critical items | 0 | 1 | > 1 |
| High items > 14d | 0 | 1-2 | > 2 |
| Average age | < 7d | 7-14d | > 14d |

---

## Example Invocations

Full dashboard:
```
/tech-debt
```

Filter by priority:
```
/tech-debt high
/tech-debt critical
```

Filter by category:
```
/tech-debt category:security
```

Show aged items:
```
/tech-debt aged
```

Promote specific item:
```
/tech-debt promote DEBT-001
```

Auto-select and promote:
```
/tech-debt promote auto
```

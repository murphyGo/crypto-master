# Code Review Skill

Automatically analyzes Python code for quality issues and best practice compliance.

## Arguments

- `$ARGUMENTS` - One of the following:
  - `git` - Review files changed in git (staged + unstaged)
  - `session:<path>` - Review files listed in "Files Modified" section of session log
  - `files:<path1>,<path2>` - Review specific files
  - `dir:<path>` - Review all Python files in directory

## Objective

Proactively identify common issues, security vulnerabilities, and best practice violations by analyzing actual source code.

```
/code-review
─────────────
• Actual code analysis
• Proactive (issue detection)
• Automated verification
• Runs in /dev-crypto Step 5
```

---

## Execution Steps

### Step 1: Identify Files to Review

#### If `git`:
```bash
git diff --name-only HEAD
git diff --name-only --cached
```
- Combine staged and unstaged changes
- Filter only `*.py` files
- Separate `*_test.py` for special handling

#### If `session:<path>`:
- Read session log file
- Parse "Files Modified" section
- Extract file paths

#### If `files:<paths>`:
- Split comma-separated paths
- Verify file existence

#### If `dir:<path>`:
- Glob `<path>/**/*.py`
- Separate test files

### Step 2: Error Handling Check

Scan each Python file:

| Pattern | Issue | Severity |
|---------|-------|----------|
| `except:` (bare except) | Too broad exception handling | High |
| `except Exception:` without logging | Swallowed exception | Medium |
| `pass` in except block | Ignored exception | High |
| `raise` without `from` | Re-raise without chaining | Low |

### Step 3: Resource Management Check

Scan for resource acquisition without cleanup:

| Pattern | Check | Severity |
|---------|-------|----------|
| `open()` without `with` | Context manager not used | High |
| `requests.get/post` without timeout | Missing timeout | High |
| DB connection without close | Connection not closed | High |
| Thread/Process without join | Resource leak | Medium |

### Step 4: Security Check

Scan for security issues:

| Pattern | Issue | Severity |
|---------|-------|----------|
| `password = "..."` | Hardcoded password | Critical |
| `secret = "..."` | Hardcoded secret | Critical |
| `api_key = "..."` | Hardcoded API key | Critical |
| `"sk-..."`, `"api_..."` | API key in string | Critical |
| `pickle.loads` on untrusted data | Unsafe deserialization | Critical |
| `eval()`, `exec()` | Code injection risk | Critical |
| SQL string concatenation | Potential SQL injection | Critical |
| `subprocess.shell=True` | Shell injection risk | High |

### Step 5: Edge Cases & Potential Bugs Check

Scan for common edge cases and bug patterns:

| Pattern | Issue | Severity |
|---------|-------|----------|
| `if x is None` after `x.attr` | Late None check | High |
| `len(list)` without None check | Potential None list | Medium |
| Mutable default argument | Mutable default arg | High |
| `==` for None comparison | Should use `is None` | Low |
| f-string with `{obj}` without `__str__` | Potential repr output | Low |

### Step 6: Type Hints Check

Scan for type-related issues:

| Pattern | Issue | Severity |
|---------|-------|----------|
| Public function without type hints | Missing type hints | Low |
| `Any` type overuse | Reduced type safety | Low |
| `# type: ignore` without reason | Unexplained type ignore | Low |

### Step 7: Performance & Memory Check

Scan for performance and memory issues:

| Pattern | Issue | Severity |
|---------|-------|----------|
| `+` for string concatenation in loop | Inefficient string concat | Medium |
| List comprehension with side effects | Side effects in comprehension | Medium |
| `global` keyword usage | Global state modification | Medium |
| Large list instead of generator | Memory inefficient | Low |

### Step 8: Code Quality Check

Scan for code quality issues:

| Pattern | Issue | Severity |
|---------|-------|----------|
| `# TODO` without `DEBT-` | Untracked TODO | Low |
| `# FIXME` without `DEBT-` | Untracked FIXME | Medium |
| `# HACK` | Unexplained hack | Medium |
| `print()` in non-test code | Leftover debug output | Low |
| Magic numbers | Unexplained literals | Low |
| Unused imports | Unused import | Low |

### Step 9: Test Coverage Check

For each new/modified function:

| Check | Method | Severity |
|-------|--------|----------|
| Test exists | Find `test_<func_name>` in `*_test.py` | Medium |
| Error path tested | Find tests with exception assertions | Medium |
| pytest used | Check for `pytest` patterns | Low |

### Step 10: Generate Report

```markdown
## Code Review Report

**Scope**: [N files reviewed]
**Date**: YYYY-MM-DD HH:MM

---

### Summary

| Category | ✅ Pass | ⚠️ Warn | 🔴 Fail |
|----------|---------|---------|---------|
| Error Handling | X | Y | Z |
| Resource Management | X | Y | Z |
| Security | X | Y | Z |
| Edge Cases & Bugs | X | Y | Z |
| Type Hints | X | Y | Z |
| Performance & Memory | X | Y | Z |
| Code Quality | X | Y | Z |
| Test Coverage | X | Y | Z |
| **Total** | **X** | **Y** | **Z** |

**Status**: ✅ All Clear / ⚠️ Warnings Found / 🔴 Issues Found

---

### Issues Detail

#### 🔴 Critical/High Severity

| # | File:Line | Category | Issue | Suggestion |
|---|-----------|----------|-------|------------|
| 1 | collectors/arxiv.py:45 | Resource | open() without with | Use `with open() as f:` |

#### 🟡 Medium Severity

| # | File:Line | Category | Issue | Suggestion |
|---|-----------|----------|-------|------------|
| 2 | summarizer.py:78 | Error | Swallowed exception | Add logging |

#### 🟢 Low Severity

| # | File:Line | Category | Issue | Suggestion |
|---|-----------|----------|-------|------------|
| 3 | main.py:12 | Quality | TODO without DEBT | Add DEBT-XXX reference |

---

### Self-Review Checklist (Auto-generated)

| Item | Status | Evidence |
|------|--------|----------|
| All exceptions properly handled | ⚠️ | 2 bare excepts found |
| Resource cleanup complete | ✅ | with statement used |
| No hardcoded secrets | ✅ | None detected |
| Edge cases handled | ⚠️ | 1 None check missing |
| Type hints added | 🔴 | 3 functions missing |
| Tests cover error paths | ⚠️ | 1 error path untested |

---

### TECH-DEBT Candidates

Issues to track as technical debt:

```markdown
### DEBT-XXX: Bare except in collectors/arxiv.py

**Category**: Reliability
**Priority**: Medium
**Location**: `src/collectors/arxiv.py:45,67`

**Description**:
Too broad exception handling makes debugging difficult

**Remediation**:
Specify exception types and add logging

**Estimated Effort**: 15 min
```

Add to TECH-DEBT.md? (yes/no)
```

---

## Ignore Directives

You can exclude code from review with comments:

```python
# code-review:ignore-next-line
password = os.getenv("PASSWORD")  # Read from env var, OK

# code-review:ignore-block-start
# Legacy code, refactoring planned for Phase 3
def old_function():
    ...
# code-review:ignore-block-end
```

---

## Severity Definitions

| Severity | Meaning | Action |
|----------|---------|--------|
| 🔴 Critical | Security vulnerability or data loss risk | Must fix before commit |
| 🔴 High | Potential bug or resource leak | Recommended fix before commit |
| 🟡 Medium | Code quality issue | Fix or record in TECH-DEBT |
| 🟢 Low | Style/convention issue | Fix if easy, otherwise ignore |

---

## Example Invocations

Review git changes:
```
/code-review git
```

Review from session log:
```
/code-review session:docs/sessions/2024-04-03-phase2-testing.md
```

Review specific files:
```
/code-review files:src/collectors/arxiv.py,src/summarizer.py
```

Review directory:
```
/code-review dir:src/collectors
```

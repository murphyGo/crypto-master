# Crypto Master - Technical Debt Tracker

## Overview

This document tracks technical debt items identified during development. Items are prioritized and have escalation thresholds.

## Priority Levels & Escalation Thresholds

| Priority | Description | Escalation Threshold |
|----------|-------------|---------------------|
| **Critical** | Blocks development or causes failures | Immediate |
| **High** | Significant impact on quality/maintainability | 14 days |
| **Medium** | Moderate impact, should be addressed | 21 days |
| **Low** | Minor issues, address when convenient | 30 days |

## Active Debt Items

<!--
Template for new items:

### DEBT-XXX: [Title]

| Field | Value |
|-------|-------|
| **Priority** | Critical/High/Medium/Low |
| **Created** | YYYY-MM-DD |
| **Phase** | Phase N.M |
| **Component** | Component name |

**Description:**
[Detailed description of the debt item]

**Impact:**
[What is affected by this debt]

**Suggested Resolution:**
[How to resolve this debt]

**Related:**
- Issue/PR links
- Related DEBT items
-->

### DEBT-001: Pre-Existing Lint/Type Sweep

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-04-28 |
| **Phase** | Surfaced during Phase 10.5 |
| **Component** | Cross-cutting (src/ai, src/strategy, src/feedback, src/trading, tests/, project tooling) |

**Description:**
Phase 10.5's touch-and-verify discipline surfaced lint/type errors that pre-exist this cycle but had not been recorded as debt. Two groups:

1. **18 pre-existing ruff errors:**
   - `B904` raise-from in `src/ai/claude.py`, `src/strategy/loader.py`, `src/feedback/loop.py`
   - `UP035` typing imports
   - `F841` / `F401` in tests

2. **24 pre-existing mypy errors:**
   - `src/trading/live.py` untyped object returns at lines 235, 244, 252, 438, 445
   - `src/ai/improver.py:280` arg-type
   - `types-PyYAML` missing from dev dependencies

**Impact:**
- The errors do not block development today (each module's tests still pass).
- They obscure new errors: future cycles that touch these files cannot rely on a "ruff/mypy clean" baseline as a gate signal — every cycle has to triage which errors are pre-existing vs newly introduced.
- The mypy `live.py` cluster in particular is on the live trading path; tightening those return types would surface real type-narrowing opportunities.

**Suggested Resolution:**
- One focused sweep cycle: fix all 18 ruff errors and the 24 mypy errors in a single PR. No functional change; pure typing/lint hygiene.
- Add `types-PyYAML` to `pyproject.toml`'s dev extras to drop the mypy import-untyped warning permanently.
- Once clean, consider adding a CI gate on ruff + mypy so future regressions are blocked at PR time rather than recorded as debt.

**Related:**
- Surfaced in: `docs/sessions/2026-04-28-phase-10.5-volume-aware-default-paths.md`
- Dev report flagged these as suggested TECH-DEBT items; auditor judged groups 1 + 2 worth recording, group 3 (`DEFAULT_*_PATH` rename) skipped as not worth the noise.

---

## Resolved Debt Items

<!--
Move resolved items here with resolution date and notes.

### DEBT-XXX: [Title] ✅

| Field | Value |
|-------|-------|
| **Priority** | [Original priority] |
| **Created** | YYYY-MM-DD |
| **Resolved** | YYYY-MM-DD |
| **Resolution** | [Brief description] |
-->

*No resolved items yet.*

---

## Statistics

| Metric | Value |
|--------|-------|
| Total Active | 1 |
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 0 |
| Resolved (All Time) | 0 |

---

## Change History

| Date | Action | Item |
|------|--------|------|
| 2026-04-05 | Created | Initial TECH-DEBT tracker |
| 2026-04-28 | Added | DEBT-001 Pre-Existing Lint/Type Sweep (Medium) — surfaced during Phase 10.5 |

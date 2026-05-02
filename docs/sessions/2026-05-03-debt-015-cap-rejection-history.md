# Session Log: 2026-05-03 - DEBT-015 - Cap Rejection History

## Overview

- **Date**: 2026-05-03
- **Scope**: DEBT-015
- **Status**: ✅ Resolved

## Work Summary

Aligned the Phase 12.1 symbol-cap rejection path with the Phase 18.1
stale-quote rejection path. Cap rejections now update the persisted
`ProposalRecord` to `REJECTED` with the cap reason instead of only
emitting an activity event.

## Files Changed

- Modified: `src/runtime/engine.py`
- Modified: `tests/test_runtime_engine.py`
- Modified: `docs/TECH-DEBT.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Rewrite the already-accepted record in the cap branch | Keeps `ProposalHistory` authoritative for rejected-proposal queries. |
| Preserve the existing activity event | Dashboard activity stream behavior remains unchanged while history becomes complete. |
| Keep simultaneous accepted/rejected counters unchanged | That accounting contract is tracked separately as DEBT-016 and is intentionally not changed here. |

## Validation

- `uv run pytest tests/test_runtime_engine.py -q` — 40 passed
- `uv run pytest -q` — 1415 passed

## TECH-DEBT

- DEBT-015 moved to Resolved.
- Active debt count: 11 → 10.

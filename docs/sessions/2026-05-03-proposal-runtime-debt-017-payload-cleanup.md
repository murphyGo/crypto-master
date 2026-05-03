# Session Log: 2026-05-03 - proposal-runtime - DEBT-017 Payload Cleanup

## Overview

- **Date**: 2026-05-03
- **Unit**: `proposal-runtime`
- **Task**: Resolve DEBT-017 by removing duplicate proposal-entry fields from
  stale-quote rejection payloads.

## Work Summary

Removed explicit `proposal_entry` from stale-quote and no-live-data rejection
activity payloads. The shared `_proposal_summary` field `entry_price` remains
the single proposal-entry field across proposal events.

## Files Changed

- Modified: `src/runtime/engine.py`
- Modified: `tests/test_runtime_engine.py`
- Modified: `docs/TECH-DEBT.md`
- Modified: `aidlc-docs/inception/units/debt-unit-map.md`
- Created: `docs/sessions/2026-05-03-proposal-runtime-debt-017-payload-cleanup.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Keep `entry_price` | It comes from `_proposal_summary` and is already common to proposal-related events. |
| Remove `proposal_entry` | It duplicated `entry_price` and made event consumers choose between equivalent fields. |
| Apply the same cleanup to no-live-data rejection | That helper mirrors stale-quote rejection and had the same redundancy. |

## Verification

```bash
uv run pytest tests/test_runtime_engine.py -q
uv run ruff check src/runtime/engine.py tests/test_runtime_engine.py
uv run mypy src/runtime/engine.py
```

Result: 40 passed; ruff passed; mypy passed on touched source file.

## Risks

- Consumers reading `proposal_entry` must switch to `entry_price`. Existing
  in-repo tests now pin `entry_price` as the supported field.

## TECH-DEBT Items

- Resolved: DEBT-017.

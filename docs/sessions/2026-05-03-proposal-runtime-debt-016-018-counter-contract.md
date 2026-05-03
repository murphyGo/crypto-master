# Session Log: 2026-05-03 - proposal-runtime - DEBT-016/018 Counter Contract

## Overview

- **Date**: 2026-05-03
- **Unit**: `proposal-runtime`
- **Task**: Resolve DEBT-016 and DEBT-018 by documenting and testing proposal
  accepted/rejected counter semantics.

## Work Summary

Clarified that `CycleResult.proposals_accepted` and
`proposals_rejected` are non-exclusive stage counters. A proposal can be
accepted by the composite proposal gate and later rejected by a post-acceptance
gate such as cap, stale-quote, slippage, or no-live-data. Runtime tests now pin
that simultaneous counter behavior.

## Files Changed

- Modified: `src/runtime/engine.py`
- Modified: `tests/test_runtime_engine.py`
- Modified: `docs/TECH-DEBT.md`
- Modified: `aidlc-docs/inception/units/debt-unit-map.md`
- Created: `docs/sessions/2026-05-03-proposal-runtime-debt-016-018-counter-contract.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Document counters on `CycleResult` | This is where tests and dashboard summary readers encounter the fields. |
| Treat counters as stage counters | Preserves existing cap/stale-quote accounting without pretending accepted/rejected are mutually exclusive final states. |
| Add assertions to stale/no-live-data tests | Locks the same contract already covered by cap-rejection tests. |

## Verification

```bash
uv run pytest tests/test_runtime_engine.py -q
uv run ruff check src/runtime/engine.py tests/test_runtime_engine.py
uv run mypy src/runtime/engine.py
```

Result: 40 passed; ruff passed; mypy passed on touched source file.

## Risks

- Dashboard summaries that assume `accepted + rejected == processed` still need
  to read the documented contract; this task documents and tests the runtime
  behavior but does not change dashboard presentation.

## TECH-DEBT Items

- Resolved: DEBT-016.
- Resolved: DEBT-018.

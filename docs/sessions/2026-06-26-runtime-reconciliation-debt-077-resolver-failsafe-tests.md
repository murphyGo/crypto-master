# Session: DEBT-077 resolver fail-safe unit tests

- **Date**: 2026-06-26
- **Unit**: `runtime-reconciliation`
- **Stage**: Code Generation (test-only)
- **Workflow**: `/dev-crypto` (single-agent)

## Related debt

- DEBT-077 (resolved here); follow-up from the DEBT-071 cycle.

## Problem

DEBT-071 introduced `resolve_bounds_from_performance_record(...)` in
`src/strategy/performance.py` — a raw-JSON walk used by paper/live rehydration
to recover an open trade's SL/TP from its linked performance record. It fails
safe to `None` on missing files, corrupt JSON, null bounds, and malformed
values. Those defensive branches were exercised only **indirectly** by the
paper/live rehydrate-backfill happy-path tests; no direct unit test asserted
each branch returns `None` without raising. Coverage gap, not a defect.

## Change (test-only — no source change)

Added `TestResolveBoundsFromPerformanceRecord` (12 tests) to
`tests/test_strategy_performance.py`, covering:

- Happy path → `(Decimal, Decimal)`.
- Returns `None`: missing performance root, missing sub-account dir, record-id
  not found, null `stop_loss`, null `take_profit`, corrupt JSON, rows-not-a-list
  (a dict), malformed Decimal value.
- Skips-not-crashes (then resolves from a valid row): non-dict row in the list,
  stray non-directory file under the sub-account root, a technique dir without
  `records.json`.

Imported the resolver into the test module.

## Files changed

- `tests/test_strategy_performance.py` (+1 import, +`TestResolveBoundsFromPerformanceRecord`)
- `docs/TECH-DEBT.md` (DEBT-077 → ✅, Statistics 7→6 active / 67→68 resolved, Change History)
- `aidlc-docs/inception/units/debt-unit-map.md`

## Tests / checks

- `uv run pytest tests/test_strategy_performance.py::TestResolveBoundsFromPerformanceRecord -q` → 12 passed
- `uv run pytest tests/test_strategy_performance.py -q` → 117 passed
- `uv run ruff check tests/test_strategy_performance.py` → clean
- `uv run black --check tests/test_strategy_performance.py` → clean
- `mypy` not re-run (no `src/` change).

## Decisions

- Test home is `tests/test_strategy_performance.py` (where the resolver lives),
  not the rehydration test files, since these pin the resolver's contract in
  isolation rather than the rehydrate integration.

## Risks

- None — test-only, behaviour was already correct as shipped in DEBT-071.

## Debt

- Resolved: DEBT-077. No new debt.

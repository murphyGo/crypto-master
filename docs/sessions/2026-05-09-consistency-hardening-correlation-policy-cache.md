# Session: consistency-hardening CH-34 Correlation Policy Cache

## Unit

- `consistency-hardening`
- Primary owner unit: `proposal-runtime`

## Related Requirements

- FR-013 Proposal approval workflow
- FR-036 Sub-account capital isolation

## Changes

- Cached `_runtime_policy_for_id(proposal.sub_account_id)` in
  `_correlation_gate()`.
- Reused that policy for the correlation gate config and activity log detail.

## Tests

- `uv run pytest tests/test_runtime_engine.py -q`
  - 56 passed.
- `uv run ruff check src/runtime/engine.py`
  - passed.
- `uv run black --check src/runtime/engine.py`
  - passed.
- `uv run mypy src/runtime/engine.py`
  - failed on existing unrelated type errors:
    `src/proposal/engine.py:651`, `src/runtime/engine.py:1671`,
    `src/runtime/engine.py:1682`.

## Decisions

- Kept this as a behavior-preserving cache slice. Broader per-cycle caches for
  safety score and open-trade strategy lookup remain separate work.

## Risks

- CH-34 remains open for the rest of the cache-extension backlog.

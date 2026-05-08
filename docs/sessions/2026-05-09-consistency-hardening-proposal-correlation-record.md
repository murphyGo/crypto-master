# Session: consistency-hardening CH-29 Proposal Correlation Record Reuse

## Unit

- `consistency-hardening`
- Primary owner units: `proposal-runtime`, `persistence-data-integrity`

## Related Requirements

- FR-011 Automated proposal generation
- FR-013 Proposal approval workflow
- NFR-007 Trading history / proposal persistence

## Changes

- Changed `_handle_proposal()` to pass the current `ProposalRecord` into
  `_correlation_gate()`.
- Changed `_correlation_gate()` to build rejected records from that in-flight
  record rather than reloading the same proposal from `ProposalHistory`.

## Tests

- `uv run pytest tests/test_runtime_engine.py -q`
  - 56 passed.
- `uv run ruff check src/runtime/engine.py`
  - passed.
- `uv run black --check src/runtime/engine.py`
  - passed.
- `uv run mypy src/runtime/engine.py`
  - failed on existing unrelated type errors:
    `src/proposal/engine.py:651`, `src/runtime/engine.py:1678`,
    `src/runtime/engine.py:1689`.

## Decisions

- Kept this as a narrow CH-29 slice. Full `GateOutcome` consolidation remains
  queued because it changes the full notify/decision/safety/cap pipeline.

## Risks

- CH-29 remains open for a unified decision envelope and single save/log path.

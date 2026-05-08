# Cross-Check: consistency-hardening CH-29 Proposal Correlation Record Reuse

## Scope

Verify that the correlation gate no longer reloads the current proposal record
before writing a rejection.

## Requirements

- FR-011 Automated proposal generation
- FR-013 Proposal approval workflow
- NFR-007 Trading history / proposal persistence

## Evidence

- `_handle_proposal()` passes its current `ProposalRecord` to
  `_correlation_gate()`.
- `_correlation_gate()` now uses `record.model_copy(...)` instead of
  `self.proposal_history.load(proposal.proposal_id).model_copy(...)`.
- Existing runtime engine correlation/cap/stale-quote tests remain green.

## Verification

- `uv run pytest tests/test_runtime_engine.py -q`
  - 56 passed.
- `uv run ruff check src/runtime/engine.py`
  - passed.
- `uv run black --check src/runtime/engine.py`
  - passed.
- `uv run mypy src/runtime/engine.py`
  - blocked by existing unrelated type errors in `src/proposal/engine.py:651`,
    `src/runtime/engine.py:1678`, and `src/runtime/engine.py:1689`.

## Result

PASS with a known mypy limitation. The correlation rejection path now reuses
the in-flight proposal record and avoids the previous reload-modify-save race.
CH-29 remains open for full gate-envelope consolidation.

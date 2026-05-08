# Code Generation Plan: consistency-hardening - CH-29 Correlation record reuse

## Task

Start CH-29 proposal gate decision-envelope cleanup by removing the
correlation gate's reload-modify-save path for the current proposal record.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-29 correlation record reuse
- Primary owner units: `proposal-runtime`, `persistence-data-integrity`

## Related Requirements

- FR-011 Automated proposal generation
- FR-013 Proposal approval workflow
- NFR-007 Trading history / proposal persistence

## Steps

- [x] Pass the current `ProposalRecord` into `_correlation_gate()`.
- [x] Build the rejected record from the in-flight record instead of reloading
      it from `ProposalHistory`.
- [x] Keep existing correlation warning and rejection activity events unchanged.
- [x] Run targeted runtime engine tests.

## Verification

- [x] `uv run pytest tests/test_runtime_engine.py -q`
- [x] `uv run ruff check src/runtime/engine.py`
- [x] `uv run black --check src/runtime/engine.py`
- [ ] `uv run mypy src/runtime/engine.py` - blocked by existing unrelated type
      errors in `src/proposal/engine.py:651`, `src/runtime/engine.py:1678`,
      and `src/runtime/engine.py:1689`.

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] State/spec updated.
- [x] Session log and cross-check written.

# Code Generation Plan: consistency-hardening - CH-34 Correlation policy cache

## Task

Start CH-34 per-cycle cache extension by avoiding repeated runtime policy
resolution inside the correlation gate.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-34 correlation policy cache
- Primary owner unit: `proposal-runtime`

## Related Requirements

- FR-013 Proposal approval workflow
- FR-036 Sub-account capital isolation

## Steps

- [x] Resolve the proposal runtime policy once inside `_correlation_gate()`.
- [x] Reuse the local policy for enabled/warning config and activity detail.
- [x] Keep correlation warnings and rejection behavior unchanged.

## Verification

- [x] `uv run pytest tests/test_runtime_engine.py -q`
- [x] `uv run ruff check src/runtime/engine.py`
- [x] `uv run black --check src/runtime/engine.py`
- [ ] `uv run mypy src/runtime/engine.py` - blocked by existing unrelated type
      errors in `src/proposal/engine.py:651`, `src/runtime/engine.py:1671`,
      and `src/runtime/engine.py:1682`.

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] State/spec updated.
- [x] Session log and cross-check written.

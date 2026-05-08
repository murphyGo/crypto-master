# Code Generation Plan: consistency-hardening - CH-10 Post-incident safety score

## Task

Recompute runtime safety score after same-proposal notification and advisory
correlation incidents before evaluating the runtime hard-pause gate.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-10
- Primary owner units: `runtime-safety-score`, `proposal-runtime`

## Related Requirements

- FR-013 Support operator accept/reject decisions
- FR-014 Store proposal history and outcomes
- FR-042 Compute an operator-facing runtime safety score
- NFR-012 Require explicit live trading confirmation

## Steps

- [x] Add a helper for current runtime safety score calculation.
- [x] Keep notification payload score as the pre-notification score.
- [x] Recompute safety after notification/correlation events before the
      hard-pause gate.
- [x] Tests: same-proposal notification failure can trigger hard-pause.
- [x] Targeted pytest: `uv run pytest tests/test_runtime_engine.py -q`.

## Verification

- [x] Targeted tests pass.
- [x] Formatting/lint run for changed source/test files where practical.

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Tests added.
- [x] Plan steps closed.
- [x] State/spec updated.
- [x] Session log and cross-check written.

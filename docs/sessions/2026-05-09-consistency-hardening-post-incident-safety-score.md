# Session: consistency-hardening CH-10 Post-Incident Safety Score

## Unit

- `consistency-hardening`
- Primary owner units: `runtime-safety-score`, `proposal-runtime`

## Related Requirements

- FR-013 Support operator accept/reject decisions
- FR-014 Store proposal history and outcomes
- FR-042 Compute an operator-facing runtime safety score
- NFR-012 Require explicit live trading confirmation

## Changes

- Added `TradingEngine._current_runtime_safety_score()`.
- Kept notification dispatch using the pre-notification score.
- Recomputed runtime safety after notification dispatch and correlation-gate
  processing before evaluating the hard-pause gate.
- Added a regression test where same-proposal notification failure drops the
  safety score and blocks the accepted fill.

## Tests

- `uv run pytest tests/test_runtime_engine.py -q`
  - 56 passed.
- `uv run black --check src/runtime/engine.py tests/test_runtime_engine.py`
  - passed.
- `uv run ruff check src/runtime/engine.py tests/test_runtime_engine.py`
  - passed.

## Type Check

- `uv run mypy src/runtime/engine.py`
  - failed on existing nullable-type errors in `src/proposal/engine.py` and
    runtime policy construction.

## Decisions

- Do not change the score sent to notification backends; that remains the
  score at notification time.
- Only the execution hard-pause gate receives the post-incident score.

## Risks

- Existing runtime policy nullable typing still needs a separate cleanup slice.

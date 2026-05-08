# Cross-Check: consistency-hardening CH-10 Post-Incident Safety Score

## Scope

Verify that runtime hard-pause gating sees notification/correlation incidents
emitted earlier in the same proposal handling path.

## Requirements

- FR-013 Support operator accept/reject decisions
- FR-014 Store proposal history and outcomes
- FR-042 Compute an operator-facing runtime safety score
- NFR-012 Require explicit live trading confirmation

## Evidence

- `TradingEngine._handle_proposal()` computes the notification payload score
  before notification dispatch.
- After notification/correlation processing, it recomputes safety score before
  `_runtime_safety_pause_gate()`.
- Regression test proves a same-proposal `NOTIFICATION_FAILED` event can lower
  safety to 90 and block a fill when pause minimum is 95.

## Verification

- `uv run pytest tests/test_runtime_engine.py -q`
  - 56 passed.
- `uv run black --check src/runtime/engine.py tests/test_runtime_engine.py`
  - passed.
- `uv run ruff check src/runtime/engine.py tests/test_runtime_engine.py`
  - passed.

## Result

PASS. CH-10 closes the stale pre-incident safety-score gap for runtime
hard-pause decisions.

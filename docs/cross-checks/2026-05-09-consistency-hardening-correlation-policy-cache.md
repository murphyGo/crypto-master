# Cross-Check: consistency-hardening CH-34 Correlation Policy Cache

## Scope

Verify that correlation gate policy lookup caching preserves runtime behavior.

## Requirements

- FR-013 Proposal approval workflow
- FR-036 Sub-account capital isolation

## Evidence

- `_correlation_gate()` now resolves runtime policy once into `policy`.
- Correlation warning thresholds and `gate_enabled` details read from that
  local policy.
- Runtime engine tests remain green.

## Verification

- `uv run pytest tests/test_runtime_engine.py -q`
  - 56 passed.
- `uv run ruff check src/runtime/engine.py`
  - passed.
- `uv run black --check src/runtime/engine.py`
  - passed.

## Result

PASS. Correlation gate policy lookup is now locally cached without changing
gate behavior.

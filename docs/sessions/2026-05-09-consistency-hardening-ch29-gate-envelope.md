# Session: consistency-hardening CH-29 gate envelope

Date: 2026-05-09

## Scope

- Completed CH-29 follow-up for proposal gate decision persistence.
- Added a `GateOutcome` envelope for final proposal decision, rejection reason, ordered activity events, and final `ProposalRecord`.
- Added a non-persisting `ProposalInteraction.decide()` path so runtime gates can compute notify, decision, correlation, safety, and cap outcomes before a single final history save.
- Converted correlation, runtime-safety, total-cap, and per-symbol-cap rejection paths to return staged events instead of saving directly.

## Verification

- `uv run pytest tests/test_runtime_engine.py -q`
- `uv run pytest tests/test_runtime_engine.py tests/test_proposal_interaction.py -q`
- `uv run black --check src/runtime/engine.py src/proposal/interaction.py src/proposal/engine.py tests/test_runtime_engine.py`
- `uv run ruff check src/runtime/engine.py src/proposal/interaction.py src/proposal/engine.py tests/test_runtime_engine.py`
- `uv run mypy src/runtime/engine.py src/proposal/interaction.py src/proposal/engine.py`

## Notes

- Added regression coverage proving cap rejection saves only the final rejected record.
- Added crash-path coverage showing an ordered activity batch failure leaves the on-disk proposal record at the final verdict rather than an intermediate accepted state.

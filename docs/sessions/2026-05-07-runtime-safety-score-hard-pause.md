# Session: runtime-safety-score Hard Pause Gate

## Unit

- `runtime-safety-score`

## Related Requirements

- FR-014, FR-015, FR-042
- NFR-007

## Files Changed

- `src/runtime/engine.py`
- `src/config.py`
- `src/main.py`
- `tests/test_runtime_engine.py`
- `tests/test_config.py`
- `aidlc-docs/construction/plans/runtime-safety-score-hard-pause-code-generation-plan.md`
- `aidlc-docs/construction/runtime-safety-score/code/hard-pause-gate.md`
- `docs/sessions/2026-05-07-runtime-safety-score-hard-pause.md`

## Checks Run

```bash
uv run pytest tests/test_runtime_engine.py tests/test_config.py tests/test_main_dispatch.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

## Decisions

- Made the gate opt-in with a `None` default to avoid silently changing live or
  paper trading behavior.
- Placed the gate after proposal acceptance but before correlation, cap, stale
  quote, and execution gates so the proposal history records an explicit
  rejected decision.
- Reused the same recent activity safety score already sent with proposal
  notifications.

## Risks

- Operators must choose and configure the minimum score. No default pause
  threshold is enforced yet.

## Debt

- No new TECH-DEBT item added.

# Code Generation Plan: runtime-safety-score Hard Pause Gate

## Unit

- **Unit**: `runtime-safety-score`
- **Stage**: Code Generation
- **Task**: Add an opt-in runtime safety hard-pause gate before proposal fills.
- **Related Requirements**: FR-014, FR-015, FR-042, NFR-007.
- **Related Stories**: US-020, US-022, US-023.
- **Related Debt**: none active.

## Implementation Steps

- [x] Add an optional engine config field for the minimum allowed runtime
  safety score.
- [x] Thread the setting through environment-driven `Settings` and main engine
  construction.
- [x] Block accepted proposal fills when runtime safety score is below the
  configured minimum.
- [x] Persist the blocked proposal as rejected and write structured activity
  evidence.
- [x] Add targeted runtime/config/main tests.
- [x] Run targeted runtime safety tests and formatting checks.
- [x] Write implementation notes/session log.

## Verification

```bash
uv run pytest tests/test_runtime_engine.py tests/test_config.py tests/test_main_dispatch.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

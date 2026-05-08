# Session: consistency-hardening CH-30 Notification Dispatcher Bootstrap

## Unit

- `consistency-hardening`
- Primary owner units: `proposal-runtime`, `notifications-ops`

## Related Requirements

- FR-011 Automated proposal generation
- FR-014 Proposal notifications
- NFR-012 Operator notification safety

## Changes

- Added `build_notification_dispatcher()` in `src/main.py`.
- Moved console/file, Slack, Telegram, email, and routed sub-account notifier
  construction out of `build_engine()`.
- Kept dispatcher min-score and route behavior unchanged.

## Tests

- `uv run pytest tests/test_main_dispatch.py -q`
  - 31 passed.
- `uv run ruff check src/main.py`
  - passed.
- `uv run black --check src/main.py`
  - passed.
- `uv run mypy src/main.py`
  - failed on existing unrelated type errors:
    `src/proposal/engine.py:651`, `src/runtime/engine.py:1678`,
    `src/runtime/engine.py:1689`.

## Decisions

- Started CH-30 with a pure bootstrap extraction before touching policy
  resolution. This keeps the runtime construction behavior stable.

## Risks

- CH-30 remains open for the larger `_runtime_policy_for()` resolver
  decomposition.

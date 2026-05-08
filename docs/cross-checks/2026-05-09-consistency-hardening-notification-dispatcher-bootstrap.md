# Cross-Check: consistency-hardening CH-30 Notification Dispatcher Bootstrap

## Scope

Verify that notification dispatcher extraction preserves `build_engine()`
bootstrap behavior.

## Requirements

- FR-011 Automated proposal generation
- FR-014 Proposal notifications
- NFR-012 Operator notification safety

## Evidence

- `build_engine()` now delegates notifier wiring to
  `build_notification_dispatcher()`.
- The helper still constructs console/file defaults, optional Slack/Telegram
  and email push notifiers, route-specific Slack dispatchers, and routed
  sub-account min-score dispatching.
- Main dispatch tests remain green.

## Verification

- `uv run pytest tests/test_main_dispatch.py -q`
  - 31 passed.
- `uv run ruff check src/main.py`
  - passed.
- `uv run black --check src/main.py`
  - passed.
- `uv run mypy src/main.py`
  - blocked by existing unrelated type errors in `src/proposal/engine.py:651`,
    `src/runtime/engine.py:1678`, and `src/runtime/engine.py:1689`.

## Result

PASS with a known mypy limitation. Notification bootstrap is now isolated from
the main engine construction flow without changing notifier behavior.

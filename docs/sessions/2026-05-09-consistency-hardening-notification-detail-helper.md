# Session: consistency-hardening CH-33 Notification Detail Helper

## Unit

- `consistency-hardening`
- Primary owner unit: `notifications-ops`

## Related Requirements

- FR-014 Proposal notifications
- NFR-012 Operator notification safety

## Changes

- Added `_build_notification_detail()` for the shared proposal detail lines.
- Added `_build_notification_code_block()` for fenced detail rendering.
- Routed Slack and Telegram payloads through the shared helper; email continues
  to reuse Telegram text.

## Tests

- `uv run pytest tests/test_proposal_notification.py -q`
  - 55 passed.
- `uv run ruff check src/proposal/notification.py`
  - passed.
- `uv run black --check src/proposal/notification.py`
  - passed.
- `uv run mypy src/proposal/notification.py`
  - failed on existing `src/proposal/engine.py:651` import-path type error.

## Decisions

- Kept wire output byte-equivalent and let existing Slack/Telegram/email tests
  pin payload content.

## Risks

- CH-33 remains open for proposal engine and AI improver decomposition.

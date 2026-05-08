# Cross-Check: consistency-hardening CH-33 Notification Detail Helper

## Scope

Verify that notification detail helper extraction preserves notifier payload
content.

## Requirements

- FR-014 Proposal notifications
- NFR-012 Operator notification safety

## Evidence

- Slack payloads call `_build_notification_code_block()`.
- Telegram payloads call `_build_notification_code_block()`.
- Email still reuses Telegram text, so it inherits the shared detail block.
- Existing notification tests remain green.

## Verification

- `uv run pytest tests/test_proposal_notification.py -q`
  - 55 passed.
- `uv run ruff check src/proposal/notification.py`
  - passed.
- `uv run black --check src/proposal/notification.py`
  - passed.

## Result

PASS. Notification detail payload construction is now shared without changing
Slack, Telegram, or email outputs.

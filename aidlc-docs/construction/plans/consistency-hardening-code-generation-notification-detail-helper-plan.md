# Code Generation Plan: consistency-hardening - CH-33 Notification detail helper

## Task

Start CH-33 long-function/payload decomposition by extracting the shared
proposal detail block used by Slack, Telegram, and email notification payloads.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-33 notification detail helper
- Primary owner unit: `notifications-ops`

## Related Requirements

- FR-014 Proposal notifications
- NFR-012 Operator notification safety

## Steps

- [x] Add `_build_notification_detail()`.
- [x] Add `_build_notification_code_block()`.
- [x] Route Slack payload detail through the helper.
- [x] Route Telegram text detail through the helper.

## Verification

- [x] `uv run pytest tests/test_proposal_notification.py -q`
- [x] `uv run ruff check src/proposal/notification.py`
- [x] `uv run black --check src/proposal/notification.py`
- [ ] `uv run mypy src/proposal/notification.py` - blocked by existing
      `src/proposal/engine.py:651` import-path type error.

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] State/spec updated.
- [x] Session log and cross-check written.

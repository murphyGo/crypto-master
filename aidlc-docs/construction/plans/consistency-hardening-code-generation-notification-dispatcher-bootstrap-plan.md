# Code Generation Plan: consistency-hardening - CH-30 Notification dispatcher bootstrap

## Task

Start CH-30 engine bootstrap decomposition by extracting notification
dispatcher wiring from `build_engine()`.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-30 notification dispatcher bootstrap
- Primary owner units: `proposal-runtime`, `notifications-ops`

## Related Requirements

- FR-011 Automated proposal generation
- FR-014 Proposal notifications
- NFR-012 Operator notification safety

## Steps

- [x] Add `build_notification_dispatcher()`.
- [x] Preserve base console/file notifiers and optional Slack, Telegram, and
      email push backends.
- [x] Preserve per-sub-account Slack route and min-score routing.
- [x] Route `build_engine()` through the extracted helper.

## Verification

- [x] `uv run pytest tests/test_main_dispatch.py -q`
- [x] `uv run ruff check src/main.py`
- [x] `uv run black --check src/main.py`
- [ ] `uv run mypy src/main.py` - blocked by existing unrelated type errors
      in `src/proposal/engine.py:651`, `src/runtime/engine.py:1678`, and
      `src/runtime/engine.py:1689`.

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] State/spec updated.
- [x] Session log and cross-check written.

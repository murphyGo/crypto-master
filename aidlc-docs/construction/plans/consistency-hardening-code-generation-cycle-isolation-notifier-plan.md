# Code Generation Plan: consistency-hardening — CH-03 Sub-account cycle isolation + per-notifier failure visibility

## Task

1. Add a per-sub-account `try`/`except` inside `TradingEngine.run_cycle` so a
   single account's exception cannot skip scan, monitor, or snapshot work for
   later accounts in the same cycle. Emit `CYCLE_ERRORED` tagged with
   `sub_account_id` and append to `result.errors`.
2. Make per-notifier failures (Slack 5xx, Telegram 401, SMTP timeout, …)
   surface as `NOTIFICATION_FAILED` activity events so the runtime safety
   score's `recent_notification_failures` aggregate sees them. Add an
   `on_notifier_failure` callback to `NotificationDispatcher` and have the
   engine wire it on every dispatcher reachable through
   `RoutedNotificationDispatcher` fan-out.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-03
- Primary owner units: `proposal-runtime`, `sub-account-capital-segmentation`,
  `notifications-ops`, `runtime-safety-score`

## Related Requirements

- FR-015 Proposal Notification
- NFR-007 Runtime Resilience
- NFR-012 Operational Observability

## Steps

- [x] Wrap per-sub-account block in `run_cycle` with try/except; emit
      `CYCLE_ERRORED` carrying `sub_account_id`.
- [x] Add `on_notifier_failure` callable to `NotificationDispatcher`.
- [x] Engine constructor walks `default_dispatcher` + `route_dispatchers`
      to install the callback.
- [x] Engine callback emits `NOTIFICATION_FAILED` activity events with
      `notifier_name`, `proposal_id`, `symbol`, `dispatcher_name`,
      `error_type`, `error_message`.
- [x] Tests: per-sub-account isolation, dispatcher callback wiring,
      callback invocation, callback-failure resilience.
- [x] Targeted pytest + broader regression.
- [x] Lint/format/type clean for changed files.
- [x] Update aidlc-state and write session log.

## Verification

- 172 / 172 tests pass across runtime engine, notification, safety score,
  and dashboard surfaces.
- Pre-existing mypy errors at `src/runtime/engine.py:1554`, `1565`,
  `src/proposal/engine.py:651`, `src/backtest/harness.py:113` are unrelated
  (confirmed by stashing CH-03 changes and re-running mypy on the same
  files).

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Tests added/updated.
- [x] Plan steps closed.
- [x] State row updated.
- [x] Session log written.

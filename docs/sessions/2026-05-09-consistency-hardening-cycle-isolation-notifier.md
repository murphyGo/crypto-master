# Session: consistency-hardening — CH-03 Sub-account cycle isolation + per-notifier failure visibility

## Unit

- `consistency-hardening` (primary owner units: `proposal-runtime`,
  `sub-account-capital-segmentation`, `notifications-ops`,
  `runtime-safety-score`)
- Stage: Code Generation
- Slice ID: CH-03

## Related Requirements

- FR-015 Proposal Notification
- NFR-007 Runtime Resilience
- NFR-012 Operational Observability

## Problems

1. `TradingEngine.run_cycle` looped through active sub-accounts with no
   per-account guard. Any exception inside a sub-account block —
   registry mismatch, trader bug, snapshot crash, anything not caught
   inside `_scan` — propagated up and skipped scan, monitor, and
   snapshot for every later sub-account. The outer
   `_run_one_cycle_with_guard` only catches at cycle granularity, which
   is too coarse once multiple sub-accounts share a runtime.
2. The dispatcher's per-notifier `try/except` only emitted
   `logger.warning(...)`. Slack 5xx, Telegram 401, and SMTP timeouts
   never reached the activity log, so the runtime safety score's
   `recent_notification_failures` input never bumped — operators lost
   the operator-facing safety signal exactly when notifications were
   degrading. The existing `NOTIFICATION_FAILED` event was only emitted
   for dispatcher-level failures (one event for the whole call), not
   per backend.

## Fix

- `run_cycle` now wraps the per-sub-account block in `try/except`,
  emits a `CYCLE_ERRORED` event tagged with `sub_account_id`, appends
  the error to `result.errors`, and continues to the next account.
- `NotificationDispatcher` accepts an optional `on_notifier_failure`
  callback. The engine installs its own callback at construction time
  on every dispatcher reachable through `RoutedNotificationDispatcher`
  fan-out (default + route dispatchers). The callback emits a
  `NOTIFICATION_FAILED` activity event tagged with the notifier class
  name, proposal id, symbol, dispatcher class, exception type, and
  message. The callback path is itself guarded so a buggy callback
  cannot mask the original notifier failure.

## Files Changed

- `src/runtime/engine.py`
- `src/proposal/notification.py`
- `tests/test_runtime_engine.py`
- `tests/test_proposal_notification.py`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/plans/consistency-hardening-code-generation-cycle-isolation-notifier-plan.md`

## Tests / Checks Run

- `uv run pytest tests/test_runtime_engine.py tests/test_proposal_notification.py
  tests/test_runtime_safety_score.py tests/test_dashboard_engine.py
  tests/test_dashboard_app.py` — 172/172 passed (4 new tests).
- `uv run ruff check` clean for all four changed files.
- `uv run black` applied (auto-format).
- `uv run mypy` shows only the four pre-existing errors at
  `src/runtime/engine.py:1554`, `:1565`, `src/proposal/engine.py:651`,
  `src/backtest/harness.py:113`. Confirmed pre-existing by stashing CH-03
  diff and re-running.

## Decisions

- The dispatcher's `_on_notifier_failure` is set after construction
  (rather than re-threaded through every existing call site). Tradeoff:
  one underscore-prefixed attribute access in
  `TradingEngine.__init__`. Benefit: zero churn on
  `build_engine`/test fixtures and on the `RoutedNotificationDispatcher`
  override that already preserves notifier lists by hand.
- Walked dispatcher fan-out via `default_dispatcher` and
  `route_dispatchers` attributes. Visiting via `getattr` keeps the
  helper agnostic to future dispatcher subclasses; the visit set
  guards against cycles.
- Callback receives the full `Notification` (not just the proposal) so
  the safety-score / dashboard side has access to `level`, `safety_score`,
  and any future fields without another constructor change.
- Per-account exception logs at `logger.exception` so the runtime keeps
  a full traceback in the operator's logs even though the activity log
  payload only carries the short error type/message.

## Risks

- Low. The per-account isolation fail-closes to the same outer cycle
  semantics: cycle still completes, the failing account's work is
  skipped exactly as it would have been if the exception had aborted
  the cycle previously, but later accounts now make progress. The
  per-notifier callback is opt-in (defaults to `None`) so existing
  callers and tests are unaffected unless they construct an engine.

## Debt Added / Resolved

- No new tech-debt items opened. Pre-existing mypy errors above are
  separately tracked and unaffected by this slice.

## Follow-up

- CH-04: split `StrategyValidationError` into a warmup subclass so the
  backtest engine stops swallowing structural strategy contract failures
  as benign data-insufficiency skips.

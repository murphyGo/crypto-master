# Session: consistency-hardening — CH-05 Dashboard scope + aggregate equity (+ CH-19 caption)

## Unit

- `consistency-hardening` (primary owner units:
  `dashboard-operator-command-center`, `dashboard-operator-ui`)
- Stage: Code Generation
- Slice IDs: CH-05 (P1) + CH-19 (P2 fold-in)

## Related Requirements

- FR-032 Streamlit Web App
- NFR-003 Streamlit UI
- NFR-012 Operational Observability

## Problems

1. `discover_command_center_sub_accounts` only used
   `discover_sub_account_ids` (snapshot-derived). A freshly-configured
   sub-account from `config/sub_accounts.yaml` with no persisted
   trades or snapshots was invisible to Home, even though Trading
   already merged configured + persisted ids via
   `merge_sub_account_ids`.
2. `latest_snapshot_equity` returned the equity of the single newest
   snapshot across every sub-account. For the aggregate scope this
   understates by `N - 1` sub-accounts and proportionally inflates the
   `notional_pct_of_equity` figure shown alongside.
3. `ActivityLog().read_all()`, `feedback_page.load_candidate_records`,
   and `build_incident_rows(events, ...)` were unconditional and
   never filtered by `scope`. When the operator picked a single
   sub-account, three of the four command-center panels still came
   from every sub-account.
4. The Home page's "Getting started" caption pointed operators at
   `docs/development-plan.md`, which `aidlc-docs/aidlc-state.md`
   already flags as the legacy archive pointer. New roadmap lives at
   `aidlc-docs/inception/units/unit-of-work.md` (CH-19 in spec.md).

## Fix

- `discover_command_center_sub_accounts` now calls
  `merge_sub_account_ids(discover_configured_sub_account_ids(...),
  discover_sub_account_ids(...))` so configured-only accounts surface
  immediately.
- `latest_snapshot_equity(snapshots, *, aggregate_per_sub_account=False)`
  groups by `sub_account_id` and sums latest-per-account when set.
- `build_command_center_status` filters `events` by
  `details.sub_account_id` for non-aggregate scope and recomputes
  `cycles`, `cycle_metrics`, `safety`, `incident_rows`, and
  `latest_equity` from the scoped slice. `load_command_center_status`
  filters `candidate_records` by `record.sub_account_id` before
  rolling up `candidate_metrics`.
- Active-queue caption now points at
  `aidlc-docs/inception/units/unit-of-work.md`.

## Files Changed

- `src/dashboard/app.py`
- `tests/test_dashboard_app.py`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/consistency-hardening/functional-design/spec.md`
- `aidlc-docs/construction/plans/consistency-hardening-code-generation-dashboard-scope-equity-plan.md`

## Tests / Checks Run

- `uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py
  tests/test_dashboard_engine.py tests/test_dashboard_feedback.py
  tests/test_dashboard_autopsy.py tests/test_dashboard_replay.py
  tests/test_dashboard_ops.py tests/test_dashboard_strategies.py` —
  130/130 passed (3 new regression tests).
- `uv run ruff check` clean.
- `uv run black` applied (auto-format).
- `uv run mypy src/dashboard/app.py` reports the pre-existing
  covariance and `Literal["paper", "live"]` mode-default errors.
  Confirmed unrelated by stashing CH-05 and re-running mypy on the
  same module.

## Decisions

- Empty/missing `sub_account_id` on an event passes through the scoped
  filter so legacy events without explicit account tagging stay
  visible regardless of selection. The alternative — dropping
  untagged events — would break older dashboards that were written
  before sub-account routing.
- `latest_snapshot_equity` keeps its old single-snapshot behaviour as
  the default so non-Home callers (Trading single-account view) are
  unaffected.
- CH-19 (caption) folded in here rather than as a separate commit. It
  is a one-liner in the same file and the same review pass; splitting
  it adds churn without value.

## Risks

- Low. The single-account scope was already documented as the
  user-visible filter; this slice just makes the four panels honour
  it. The aggregate-equity change is pure addition (a new optional
  flag) and only fires on aggregate scope, where the prior behaviour
  was already understating equity.

## Debt Added / Resolved

- No new tech-debt entries opened. Pre-existing dashboard mypy errors
  are unaffected and remain queued under CH-25 cleanup scope.

## Follow-up

- CH-06: live fill attribution (actual exit price + fees on
  `LiveTrader`). The next P1 slice; `src/trading/live.py` lines 236
  and 429 — the LiveTrader currently records realised P&L using the
  caller-passed exit price and zero fees, so live vs paper P&L drift
  arbitrarily.

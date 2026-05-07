# Session: notifications-ops Runtime Diagnostics Dashboard

## Unit

- `notifications-ops`

## Related Requirements

- FR-032
- NFR-003, NFR-007

## Files Changed

- `src/dashboard/app.py`
- `src/dashboard/pages/ops.py`
- `tests/test_dashboard_ops.py`
- `aidlc-docs/construction/plans/notifications-ops-runtime-diagnostics-dashboard-code-generation-plan.md`
- `aidlc-docs/construction/notifications-ops/code/runtime-diagnostics-dashboard.md`
- `docs/sessions/2026-05-07-notifications-ops-runtime-diagnostics-dashboard.md`

## Checks Run

```bash
uv run pytest tests/test_dashboard_ops.py tests/test_dashboard_app.py tests/test_dashboard_engine.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_autopsy.py tests/test_dashboard_ops.py tests/test_dashboard_replay.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

## Decisions

- Used a generic optional health URL instead of hard-coding Fly-specific
  commands into the dashboard.
- Checked rotated activity files because the runtime activity log uses
  `JsonlRotator`.
- Kept diagnostics read-only and synchronous.

## Risks

- Health probing depends on the operator providing the correct deployed URL.
  The page does not authenticate to Fly or inspect Fly release metadata.

## Debt

- No new TECH-DEBT item added.

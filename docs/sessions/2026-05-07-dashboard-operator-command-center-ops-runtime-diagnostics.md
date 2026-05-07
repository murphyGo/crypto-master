# Session: dashboard-operator-command-center Ops Runtime Diagnostics

## Unit

- `dashboard-operator-command-center`

## Related Requirements

- FR-029, FR-031, FR-032, FR-036, FR-042, FR-044
- NFR-003, NFR-007, NFR-008

## Files Changed

- `src/dashboard/app.py`
- `tests/test_dashboard_app.py`
- `aidlc-docs/construction/plans/dashboard-operator-command-center-ops-runtime-diagnostics-code-generation-plan.md`
- `aidlc-docs/construction/dashboard-operator-command-center/code/ops-runtime-diagnostics.md`
- `docs/sessions/2026-05-07-dashboard-operator-command-center-ops-runtime-diagnostics.md`

## Checks Run

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

## Decisions

- Reused existing Home read-model inputs instead of introducing new runtime
  probes.
- Kept diagnostics read-only and routed remediation through existing Engine,
  snapshot, safety, and incident surfaces.
- Used explicit `pass`, `watch`, and `stop` states so the table can be scanned
  quickly without hidden scoring rules.

## Risks

- Diagnostics are only as fresh as the activity log and portfolio snapshots.
  Runtime-state checks that require live process probing remain outside this
  dashboard slice.

## Debt

- No new TECH-DEBT item added.

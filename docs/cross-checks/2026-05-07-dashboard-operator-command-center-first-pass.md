# Cross-Check: dashboard-operator-command-center First Pass

## Scope

First-pass Home command center across safety/freshness, account context, open
exposure, and strategy evidence summaries.

## Requirements

| Requirement | Result | Evidence |
|-------------|--------|----------|
| FR-028 | PASS | Home strategy-evidence summary exposes persisted candidate counts. |
| FR-029 | PASS | Home summarizes open positions and renders grouped open exposure. |
| FR-030 | PASS | Home surfaces Feedback candidate states without raw-file inspection. |
| FR-031 | PASS | Home shows snapshot freshness and estimated open notional. |
| FR-032 / NFR-003 | PASS | Streamlit Home AppTest covers command-center controls and metrics. |
| FR-036 | PASS | Home supports mode/scope context and discovered sub-account count. |
| FR-039 | PASS | Home summarizes candidate promotion workflow state read-only. |
| FR-042 | PASS | Home reuses runtime safety score band, score, and factors. |
| FR-044 | PASS | Home treats correlation warnings as actionable events and flags duplicate same-side exposure across sub-accounts. |
| NFR-007 / NFR-008 | PASS | Home reads persisted runtime/trading/portfolio/feedback state without mutation. |

## Files Checked

- `src/dashboard/app.py`
- `tests/test_dashboard_app.py`
- `aidlc-docs/construction/dashboard-operator-command-center/code/home-command-center-summary.md`
- `aidlc-docs/construction/dashboard-operator-command-center/code/account-context-controls.md`
- `aidlc-docs/construction/dashboard-operator-command-center/code/open-exposure-summary.md`
- `aidlc-docs/construction/dashboard-operator-command-center/code/strategy-evidence-summary.md`

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_feedback.py -q
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```

## Findings

- No blocking gaps found for the first-pass command center.
- The command center remains read-only and does not call exchanges during
  render.
- Estimated notional is entry-price based, not mark-to-market.

## Result

PASS.

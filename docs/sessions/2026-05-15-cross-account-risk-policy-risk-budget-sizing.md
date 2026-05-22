# Session: cross-account-risk-policy risk-budget sizing wire-in

Date: 2026-05-15
Unit: `cross-account-risk-policy`
Stage: Code Generation
Related debt: DEBT-068(a)
Related requirements: FR-036, FR-038, NFR-012

## Scope

Closed the smallest remaining `cross-account-risk-policy` Slice 2 item:
wire the already-tested `compute_risk_budget_size` helper into the proposal
runtime so `RiskPolicy.sizing_mode='risk_budget'` is no longer config-time
blocked.

## Changes

- `src/runtime/engine.py`
  - Added `_risk_budget_sizing_gate`.
  - Calls `Trader.get_balances()` for account quote-currency equity.
  - Falls back only to explicit `CapitalPolicy.sizing_balance`.
  - Rewrites `proposal.quantity` on success.
  - Rejects helper failures with `gate_rejected_risk_sizing` and structured
    `PROPOSAL_REJECTED` details.
- `src/trading/sub_account.py`
  - Removed the temporary `_reject_risk_budget_mode_until_wired_in` validator.
  - `risk_budget` mode still requires `risk_budget_pct`.
- `tests/test_runtime_engine.py`
  - Added risk-budget runtime coverage for quantity rewrite before aggregate
    caps, stop-distance rejection, and explicit sizing-balance fallback.
- `tests/test_trading_risk_sizing.py`
  - Updated validator coverage to accept configured `risk_budget` mode.
- AI-DLC docs
  - Updated construction plan, code summary, state tracking, and TECH-DEBT
    wording to mark DEBT-068(a) shipped while leaving the umbrella active.

## Verification

- `uv run pytest tests/test_trading_risk_sizing.py tests/test_trading_sub_account.py tests/test_runtime_engine.py -q`
  - Result: 174 passed.
- `uv run pytest tests/test_trading_sub_account_registry.py -q`
  - Result: 20 passed.
- `uv run ruff check src tests`
  - Result: passed.
- `uv run mypy src`
  - Result: passed, 88 source files.
- `uv run black --check src/runtime/engine.py src/trading/sub_account.py tests/test_runtime_engine.py tests/test_trading_risk_sizing.py`
  - Result: passed after formatting the touched files.
- `git diff --check`
  - Result: passed.

## Remaining Work

DEBT-068 remains active for global symbol/side caps, kill switches, operator
freeze, stale auto-close / alert-only actions, dashboard exposure panel,
`RISK_CAP_ADVISORY`, and runtime-safety-score integration.

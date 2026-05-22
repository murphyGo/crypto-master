# Risk-Budget Sizing Wire-In

Date: 2026-05-15
Unit: `cross-account-risk-policy`
Stage: Code Generation
Debt: DEBT-068(a)

## Summary

`RiskPolicy.sizing_mode='risk_budget'` now has a production runtime caller.
`TradingEngine._risk_budget_sizing_gate` runs after composite acceptance and
market-regime gating, before strategy-action scaling and downstream cap gates.
For opted-in sub-accounts it calls `compute_risk_budget_size`, rewrites
`proposal.quantity` with the computed Decimal size, and lets the existing
execution path continue.

The gate sources account equity from `Trader.get_balances()` for the
sub-account quote currency. If that balance is unavailable, it falls back only
to explicit `CapitalPolicy.sizing_balance`. If neither source is available, the
existing helper returns a structured `missing_equity` rejection.

## Runtime Semantics

- `fixed_notional` accounts preserve existing proposal quantities.
- `risk_budget` accounts require `risk_budget_pct` at config load.
- Helper rejections become `ProposalFinalState.GATE_REJECTED_RISK_SIZING`.
- Rejection events reuse `ActivityEventType.PROPOSAL_REJECTED` with
  `details.gate_reason == "risk_sizing"` and
  `details.risk_sizing_reason` set to the helper reason.
- The temporary `RiskPolicy._reject_risk_budget_mode_until_wired_in` validator
  was removed because the runtime no longer silently ignores the mode.

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

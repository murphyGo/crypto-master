# Cross-Check: cross-account-risk-policy risk-budget sizing

Date: 2026-05-15
Unit: `cross-account-risk-policy`
Scope: DEBT-068(a)

## Requirement Mapping

- FR-036: Risk-budget sizing reads account-scoped equity from the account
  trader / explicit capital policy, not a shared global sizing value.
- FR-038: Opted-in accounts size by `equity * risk_budget_pct / stop_distance`
  through `compute_risk_budget_size`.
- NFR-012: Sizing failures emit structured proposal rejection details.

## Evidence

- `RiskPolicy(sizing_mode='risk_budget', risk_budget_pct=...)` parses.
- `TradingEngine._risk_budget_sizing_gate` rewrites the accepted proposal
  quantity before downstream account aggregate caps and execution.
- Stop-distance-floor failures produce
  `ProposalFinalState.GATE_REJECTED_RISK_SIZING` plus
  `details.gate_reason == "risk_sizing"`.
- Missing quote-currency balance falls back to explicit
  `CapitalPolicy.sizing_balance`.

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

## Result

PASS for DEBT-068(a). The broader DEBT-068 umbrella remains open for the
remaining Slice 2 gates and dashboard surfaces.

# Cross-Check: Strategy Paper-Lab Sub-Accounts

## Scope

Verify that the runtime can fan out one active paper sub-account per loaded
strategy, with account-specific policy blocks for proposal decisions, scan
scope, risk, execution, notifications, and dashboard visibility.

## Result

PASS.

## Evidence

| Requirement | Result | Evidence |
|-------------|--------|----------|
| FR-036 | PASS | `config/sub_accounts.yaml` defines isolated paper sub-accounts, each with its own id and `USDT` initial balance. Registry parsing produced 12 active accounts with one strategy filter each. |
| FR-038 | PASS | Each configured account whitelists a single loaded strategy through `strategy_policy`, enabling dashboard equity and trade comparison by account. Runtime scans now read per-account symbols, top-k, sizing balance, and risk where configured. |
| FR-040 | PASS | Runtime config follows explicit `capital_policy`, `strategy_policy`, `proposal_policy`, `risk_policy`, `execution_policy`, and `notification_policy` blocks, while legacy fields remain readable for compatibility. |
| FR-028 - FR-032 | PASS | `src/dashboard/pages/trading.py` discovers configured account ids before persisted snapshots exist and still merges persisted ids for historical data. |

## Verification

- `uv run python - <<'PY' ... SubAccountRegistry(... config/sub_accounts.yaml) ... PY`
- `uv run pytest tests/test_trading_sub_account.py tests/test_trading_sub_account_registry.py tests/test_trading_experiment_marketplace.py tests/test_runtime_engine.py tests/test_proposal_notification.py tests/test_main_dispatch.py tests/test_dashboard_trading.py -q`
- `uv run black --check ...`
- `uv run ruff check ...`

## Notes

`proposal_policy.auto_approve_threshold: 0.0` removes composite-score threshold
rejections for these lab accounts. Their paper-lab `execution_policy` disables
past-SL and stale-quote hard rejections and raises slippage tolerance so
observable paper fills are favored. Invalid sizing, neutral strategy output, and
configured position caps can still prevent trades.

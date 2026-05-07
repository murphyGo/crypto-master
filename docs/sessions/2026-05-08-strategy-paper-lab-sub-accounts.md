# Strategy Paper-Lab Sub-Accounts

## Unit

`sub-account-experiment-marketplace`, with runtime/dashboard integration through
`sub-account-capital-segmentation` and `dashboard-operator-ui`.

## Related Requirements

- FR-036: Isolate capital, positions, history, and equity by sub-account.
- FR-038: Compare strategy experiments by sub-account.
- FR-040: Package sub-account configurations as reusable experiment templates.
- FR-028 - FR-032: Show strategy/trading/performance state in the dashboard.

## Summary

Created a runtime `config/sub_accounts.yaml` with one active paper account per
currently loaded non-deprecated strategy. Each account whitelists exactly one
strategy and sets `proposal_policy.auto_approve_threshold: 0.0` so the
proposal decision gate accepts every generated proposal for that strategy. The
default all-strategy account is present but disabled to keep the runtime focused
on strategy-by-strategy comparison.

Follow-up in the same cycle moved account-specific runtime knobs out of ad-hoc
global checks into explicit policy blocks:

- `capital_policy`: initial balance, quote currency, and proposal sizing balance.
- `strategy_policy`: strategy whitelist and optional per-account scan universe.
- `proposal_policy`: decision threshold and notification score threshold.
- `risk_policy`: risk percent, leverage cap, and open-position caps.
- `execution_policy`: stale-quote, runtime-safety, and correlation gate settings.
- `notification_policy`: notification route and score threshold.

The Docker image now copies `config/` so the Fly runtime can actually load the
sub-account config. The Trading dashboard now merges configured account ids
with persisted account ids, which makes strategy accounts visible before their
first trade or portfolio snapshot is written.

## Files Changed

- `config/sub_accounts.yaml`
- `config/sub_accounts.yaml.example`
- `Dockerfile`
- `src/backtest/harness.py`
- `src/dashboard/pages/trading.py`
- `src/main.py`
- `src/proposal/notification.py`
- `src/runtime/engine.py`
- `src/trading/experiment_marketplace.py`
- `src/trading/sub_account.py`
- `src/trading/sub_account_registry.py`
- `tests/test_dashboard_trading.py`
- `tests/test_proposal_notification.py`
- `tests/test_runtime_engine.py`
- `tests/test_trading_experiment_marketplace.py`
- `tests/test_trading_sub_account.py`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/plans/sub-account-experiment-marketplace-code-generation-plan.md`

## Tests and Checks

- `uv run python - <<'PY' ... SubAccountRegistry(... config/sub_accounts.yaml) ... PY`
- `uv run pytest tests/test_trading_sub_account.py tests/test_trading_sub_account_registry.py tests/test_trading_experiment_marketplace.py tests/test_runtime_engine.py tests/test_proposal_notification.py tests/test_main_dispatch.py tests/test_dashboard_trading.py -q`
- `uv run black --check ...`
- `uv run ruff check ...`

## Decisions

| Decision | Rationale |
|----------|-----------|
| Keep the lab accounts paper-only | The user asked for performance comparison, and automatic approval must not weaken live-mode intent or credential safeguards. |
| Split policy blocks by concern | Proposal decisions, execution gates, risk sizing, strategy scope, and notifications change independently by account and should not be hidden inside `risk_overrides` or global `EngineConfig` only. |
| Use `proposal_policy.auto_approve_threshold: 0.0` per lab account | This removes composite-score threshold rejections for paper labs. |
| Use permissive paper-lab stale-quote settings in config | Strategy comparison accounts should generate paper fills for observable proposals; live accounts can retain conservative global defaults or account-specific stricter policy. |
| Disable the default YAML account | The all-strategy default would obscure one-strategy-per-account comparison and consume paper cycles alongside the labs. |
| Discover configured ids in the dashboard | Waiting for persisted snapshots makes new accounts invisible until after the first engine cycle, which is confusing for operator setup verification. |

## Risks

- Strategies that return neutral or fail sizing still produce no trade; this is
  not a proposal decision rejection.
- Paper-lab `execution_policy` is intentionally permissive for stale-quote
  gates. Keep live accounts on conservative defaults or explicit stricter
  account policy.

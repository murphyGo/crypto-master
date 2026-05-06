# Cross-Check: DEBT-052 Sub-Account Notification Routing

## Scope

Verify that proposal notifications can be routed by sub-account without putting
secrets in sub-account YAML and without losing default local notification
evidence.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Sub-account config can declare a route ref | Complete | `SubAccount.notification_route` is parsed from YAML and pinned in `tests/test_trading_sub_account_registry.py`. |
| Route-specific Slack webhooks stay env-backed | Complete | `Settings.notification_slack_webhook_urls` parses comma-separated and JSON env values. |
| Runtime dispatch uses `proposal.sub_account_id` | Complete | `RoutedNotificationDispatcher` chooses a route dispatcher from `sub_account_routes`. |
| Default local notification evidence is preserved | Complete | `src/main.py::build_engine` builds route dispatchers with the base console/file notifiers plus the route-specific Slack notifier. |
| Operator docs describe setup | Complete | `.env.example`, `config/sub_accounts.yaml.example`, and `docs/deployment.md` document the route ref and env binding. |
| Debt and AI-DLC maps are updated | Complete | `docs/TECH-DEBT.md` resolves DEBT-052 and `aidlc-docs/inception/units/debt-unit-map.md` removes it from active debt. |

## Implementation Evidence

- `src/config.py`
- `src/main.py`
- `src/proposal/notification.py`
- `src/trading/sub_account.py`
- `.env.example`
- `config/sub_accounts.yaml.example`
- `docs/deployment.md`

## Test Evidence

- `uv run pytest tests/test_proposal_notification.py tests/test_config.py tests/test_main_dispatch.py tests/test_trading_sub_account_registry.py -q`
- `uv run ruff check src/config.py src/main.py src/proposal/notification.py src/trading/sub_account.py tests/test_proposal_notification.py tests/test_config.py tests/test_main_dispatch.py tests/test_trading_sub_account_registry.py`
- `uv run mypy src`

## Gaps and Risks

- Route-specific overrides currently cover Slack push routes. Telegram/email
  remain global push backends until an operator needs per-route credentials for
  those channels.

## Unit and Debt Mapping

- **Primary Unit**: `notifications-ops`
- **Secondary Unit**: `proposal-runtime`
- **Related Debt**: DEBT-052 resolved
- **Legacy Phase Context**: Phase 19.3 follow-up

# Code Generation Plan: sub-account-experiment-marketplace

## Migration Status

New product-intelligence unit built on the existing sub-account foundation.

## Planned Code Generation Steps

- [x] Register the sub-account experiment marketplace unit and construction plan.
- [x] Define reusable experiment template schema.
- [x] Render template examples into `config/sub_accounts.yaml` fragments.
- [x] Validate template risk overrides and notification routes.
- [x] Add runtime paper-lab sub-account config with one active account per
      loaded strategy and decision-gate auto-approval.
- [x] Include `config/` in the production image so Fly runtime can load
      `config/sub_accounts.yaml`.
- [x] Let the Trading dashboard discover configured accounts before first
      persisted snapshots exist.
- [x] Split account-specific settings into capital, strategy, proposal, risk,
      execution, and notification policy blocks while preserving legacy YAML
      fallback fields.
- [x] Route runtime scan scope, decision thresholds, execution gates, position
      caps, and notification thresholds through resolved sub-account policy.

## Evidence

- Requirements: FR-036, FR-038, FR-040.
- Primary paths: `config/sub_accounts.yaml.example`, `src/trading/sub_account*.py`, `src/backtest/harness.py`.

## Future Work

Add dashboard/operator tooling once the template schema is stable.

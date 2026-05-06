# Code Generation Plan: sub-account-experiment-marketplace

## Migration Status

New product-intelligence unit built on the existing sub-account foundation.

## Planned Code Generation Steps

- [x] Register the sub-account experiment marketplace unit and construction plan.
- [ ] Define reusable experiment template schema.
- [ ] Render template examples into `config/sub_accounts.yaml` fragments.
- [ ] Validate template risk overrides and notification routes.

## Evidence

- Requirements: FR-036, FR-038, FR-040.
- Primary paths: `config/sub_accounts.yaml.example`, `src/trading/sub_account*.py`, `src/backtest/harness.py`.

## Future Work

Add dashboard/operator tooling once the template schema is stable.

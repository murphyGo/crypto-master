# Code Generation Plan: sub-account-capital-segmentation

## Migration Status

Legacy Phase work is migrated as brownfield-complete. This plan is not a queue
of unfinished historical tasks.

## Source Legacy Components

| Component | Phase | Secondary Unit |
|-----------|-------|----------------|
| Sub-Account Foundation | 19 | `trading-core` |
| Sub-Account Engine Integration | 19 | `proposal-runtime` |
| Multi-Paper-Account Support + YAML Config + Dashboard | 19 | `dashboard-operator-ui` |
| Multi-Credential Live Mode | 19 | `exchange-integration` |
| Strategy-Combination A/B Backtest Harness | 19 | `backtesting-validation` |

## Completed Code Generation Steps

- [x] Implement sub-account entity, registry, and default migration behavior.
- [x] Integrate sub-accounts with runtime engine and proposal flow.
- [x] Add multi-paper-account YAML config and dashboard support.
- [x] Add multi-credential live-mode behavior.
- [x] Add strategy-combination A/B backtest harness support.

## Evidence

- Requirements: FR-036, FR-037, FR-038.
- Primary paths: `src/trading/sub_account*.py`, `config/sub_accounts.yaml.example`, `src/backtest/harness.py`, `tests/test_trading_sub_account*`.
- Cross-checks: `docs/cross-checks/2026-05-03-phase-19-sub-account-capital-segmentation.md`.
- Session logs: related Phase 19 entries under `docs/sessions/`.

## Future Work

Add future account allocation, capital isolation, credential binding, or
multi-account experiment changes as new unchecked steps here.

# Cross-Check: Sub-Account Experiment Marketplace Template Schema

## Scope

Verify that the marketplace has a reusable experiment template schema that can
produce existing sub-account runtime records.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Template schema exists | Complete | `ExperimentTemplate` in `src/trading/experiment_marketplace.py`. |
| Template materialises runtime account | Complete | `to_sub_account` returns a validated `SubAccount`. |
| Unsafe ids are rejected | Complete | Test covers path-like template id rejection. |
| Quote currency is normalized by contract | Complete | Test rejects lowercase quote currency. |
| Ambiguous strategy filters are rejected | Complete | Test rejects an empty strategy filter while preserving `None` semantics for all strategies. |
| Templates render YAML fragments | Complete | `render_sub_account_yaml_fragment` emits a `sub_accounts` document. |
| Rendered fragments round-trip | Complete | Test writes rendered YAML and loads it through `SubAccountRegistry`. |
| Risk overrides are guarded before publish | Complete | Test rejects `risk_percent` outside `(0, 100]`. |
| Notification routes are validated | Complete | Tests accept configured route keys and reject unknown route keys. |

## Implementation Evidence

- `src/trading/experiment_marketplace.py`
- `src/trading/__init__.py`
- `tests/test_trading_experiment_marketplace.py`

## Test Evidence

- `uv run pytest tests/test_trading_experiment_marketplace.py -q`
- `uv run ruff check src/trading/experiment_marketplace.py src/trading/__init__.py tests/test_trading_experiment_marketplace.py`
- `uv run black --check src/trading/experiment_marketplace.py src/trading/__init__.py tests/test_trading_experiment_marketplace.py`

## Gaps and Risks

- Dashboard/operator tooling is not part of this code-generation pass.

## Unit Mapping

- **Primary Unit**: `sub-account-experiment-marketplace`
- **Related Units**: `sub-account-capital-segmentation`, `backtesting-validation`

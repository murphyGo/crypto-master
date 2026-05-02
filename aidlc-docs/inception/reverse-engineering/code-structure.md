# Code Structure

## Build System

- **Package metadata**: `pyproject.toml`
- **Lock file**: `uv.lock`
- **Pip compatibility**: `requirements.txt`
- **Test runner**: `pytest`
- **Format/lint/type tools**: Black, Ruff, mypy
- **Deployment**: `Dockerfile`, `fly.toml`, `start.sh`

## Source Inventory

| Path | Purpose |
|------|---------|
| `src/main.py` | Engine entrypoint and dispatch/factory behavior |
| `src/config.py` | Environment and runtime configuration |
| `src/models.py` | Shared market/trading data models |
| `src/logger.py` | Logging setup |
| `src/exchange/` | Exchange base, factory, Binance, Bybit |
| `src/strategy/` | Strategy base/factory/loader, indicators, performance |
| `src/backtest/` | Backtest engine, analyzer, harness, snapshots, validators |
| `src/ai/` | Claude CLI wrapper, exceptions, improver |
| `src/feedback/` | Feedback loop and audit |
| `src/proposal/` | Proposal engine, interaction, notification |
| `src/runtime/` | Runtime engine, activity log, JSONL rotator |
| `src/trading/` | Paper/live traders, portfolio, profiles, sub-accounts |
| `src/dashboard/` | Streamlit app and theme |
| `src/utils/` | Atomic write, UTC time, trading math helpers |
| `strategies/` | Prompt and Python strategies, including experimental strategies |
| `scripts/` | Operator and backtest/research scripts |
| `tests/` | Pytest suite by component |

## Design Patterns

| Pattern | Location | Purpose |
|---------|----------|---------|
| Adapter / Interface | `src/exchange/base.py`, exchange implementations | Normalize exchange APIs |
| Strategy Pattern | `src/strategy/base.py`, `strategies/` | Pluggable analysis techniques |
| Factory | `src/exchange/factory.py`, `src/strategy/factory.py` | Runtime instantiation |
| File Repository | trade/proposal/performance persistence paths | Local JSON/JSONL state |
| Runtime Orchestrator | `src/runtime/engine.py` | Cycle-level workflow coordination |
| Validation Gate | `src/backtest/validator.py` and feedback flow | Promote only robust strategy candidates |

## Critical Dependencies

| Dependency | Purpose |
|------------|---------|
| `ccxt` | Exchange API access |
| `streamlit` | Operator dashboard |
| `pandas`, `numpy` | Backtesting and market data analysis |
| `pydantic`, `pydantic-settings` | Configuration/data validation |
| `pyyaml` | Trading profile and sub-account YAML config |
| `pytest`, `pytest-asyncio` | Test suite |
| `black`, `ruff`, `mypy` | Formatting, linting, type checks |


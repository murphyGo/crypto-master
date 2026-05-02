# Technology Stack

## Languages

| Language | Version | Usage |
|----------|---------|-------|
| Python | 3.10+ | Application, tests, scripts |
| Markdown | N/A | Requirements, strategies, AI-DLC artifacts |
| YAML/TOML | N/A | Profiles, config, build/deployment metadata |

## Python Dependencies

| Dependency | Usage |
|------------|-------|
| `ccxt` | Exchange API integration |
| `streamlit` | Operator dashboard |
| `pandas`, `numpy` | Backtesting and market data processing |
| `pydantic`, `pydantic-settings` | Configuration/model validation |
| `python-dotenv` | Local environment loading |
| `pyyaml` | Profile and sub-account configuration |
| `python-dateutil` | Time parsing/support |

## Development Tools

| Tool | Usage |
|------|-------|
| `uv` | Environment and dependency workflow |
| `pytest`, `pytest-asyncio` | Tests |
| `black` | Formatting |
| `ruff` | Linting/imports |
| `mypy` | Static typing |

## Runtime and Operations

| Tool/Service | Usage |
|--------------|-------|
| Claude CLI | AI analysis and strategy generation |
| Fly.io | Deployment target |
| Docker | Container packaging |
| Local JSON/JSONL files | Runtime state, audit, trades, snapshots |


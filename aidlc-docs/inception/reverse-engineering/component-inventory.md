# Component Inventory

## Application Packages

| Package | Purpose |
|---------|---------|
| `src/exchange` | Exchange abstraction and adapters |
| `src/strategy` | Strategy framework and performance tracking |
| `src/backtest` | Backtesting, snapshots, validation, reports |
| `src/ai` | Claude CLI integration and strategy improver |
| `src/feedback` | Feedback loop and audit |
| `src/proposal` | Proposal generation, interaction, notifications |
| `src/runtime` | Runtime cycle orchestration and activity logs |
| `src/trading` | Paper/live execution, portfolio, profiles, sub-accounts |
| `src/dashboard` | Streamlit dashboard |
| `src/tools` | Operator tools |
| `src/utils` | Shared IO, time, and math utilities |

## Support Directories

| Path | Purpose |
|------|---------|
| `strategies/` | Active and experimental strategy artifacts |
| `scripts/` | Research and backtest operator scripts |
| `trading_profiles/` | Risk/profile YAML files |
| `config/` | Example runtime configuration |
| `docs/` | Requirements, legacy plan, sessions, cross-checks, debt |
| `data/` | Runtime and operator data |
| `tests/` | Unit and integration-style pytest coverage |

## Infrastructure Packages

| Path | Purpose |
|------|---------|
| `Dockerfile` | Container build |
| `fly.toml` | Fly.io deployment |
| `start.sh` | Runtime start script |
| `.env.example` | Credential/configuration example |

## Counts

- **Application units**: 11
- **Exchange implementations**: 2 current, 1 deferred by requirements
- **Primary runtime modes**: paper, live, backtest
- **Quality artifact groups**: sessions, cross-checks, technical debt,
  AI-DLC overlay


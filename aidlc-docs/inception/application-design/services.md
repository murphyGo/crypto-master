# Services

Crypto Master is a Python modular monolith rather than a distributed service
architecture. In AI-DLC terms, the "services" below are internal service
boundaries with clear runtime responsibilities.

| Service Boundary | Entry Points | Responsibilities | External Boundaries |
|------------------|--------------|------------------|---------------------|
| Runtime Service | `src/main.py`, `src/runtime/engine.py` | Run proposal cycles, apply gates, coordinate trading, record activity | Local files, proposal/trading modules |
| Proposal Service | `src/proposal/engine.py`, `src/proposal/interaction.py` | Analyze candidates, rank proposals, handle accept/reject records | Exchange adapters, strategy framework, notifications |
| Trading Service | `src/trading/` | Paper/live execution, balances, portfolios, sub-account state | Exchange APIs for live mode, local files for paper mode |
| Exchange Service | `src/exchange/` | Abstract Binance/Bybit data and order operations | `ccxt`, exchange APIs, credentials |
| Strategy Service | `src/strategy/`, `strategies/` | Load and execute strategy artifacts | Local strategy files, pandas/numpy |
| Backtest Service | `src/backtest/`, `scripts/backtest_*` | Run simulations, validation, and strategy comparison | Historical OHLCV, snapshots, strategy framework |
| AI Feedback Service | `src/ai/`, `src/feedback/` | Generate and improve strategy candidates through Claude CLI | Local `claude -p` subprocess boundary |
| Dashboard Service | `src/dashboard/app.py` | Present operator-facing state | Streamlit, persisted runtime/trading/feedback data |
| Operations Service | `Dockerfile`, `fly.toml`, `start.sh`, notification config | Package and run the system safely | Fly.io, environment variables, notification channels |

## Service Rules

- Keep application code in the workspace root. AI-DLC docs belong under
  `aidlc-docs/`.
- Keep runtime/operator data under `data/`; do not migrate or delete it during
  AI-DLC documentation work.
- Keep Claude integration on the CLI boundary unless requirements change.
- Keep live-trading startup conservative: missing credentials must not silently
  degrade into unsafe behavior.

# Crypto Master - Claude Code Guide

## Project Overview

Crypto Master is an automated crypto trading application that uses CLI-based AI for chart analysis, trading strategy development, and continuous improvement through feedback loops.

**Key Features:**
- Bitcoin and altcoin chart analysis using CLI-based AI
- Multiple exchange support (Binance, Bybit)
- Live and paper trading modes
- Automated technique generation and improvement
- Backtesting and performance tracking
- Streamlit web dashboard

## Project Structure

```
crypto-master/
├── src/                    # Main application package
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── logger.py          # Logging setup
│   ├── models.py          # Common data models
│   ├── main.py            # Engine entry point / build_engine factory
│   ├── exchange/          # Exchange integrations (Binance, Bybit, base, factory)
│   ├── strategy/          # Analysis techniques + performance tracker
│   ├── trading/           # Trading engine (paper, live, portfolio, strategy)
│   ├── ai/                # CLI AI adapters (CodexCLI, ClaudeCLI, StrategyImprover)
│   ├── backtest/          # Backtesting engine
│   ├── proposal/          # Trading proposals (engine, interaction, notification)
│   ├── feedback/          # Feedback loop + audit
│   ├── runtime/           # Engine runtime (engine.py, activity_log.py, jsonl_rotator.py)
│   ├── tools/             # Operator scripts (purge_proposals, etc.)
│   ├── utils/             # Shared utilities (trading_math.py, time.py, io.py)
│   └── dashboard/         # Streamlit UI
├── strategies/            # Analysis technique files
├── tests/                 # Test files
├── data/                  # Runtime data (not in git)
│   ├── logs/
│   ├── trades/
│   ├── backtest/
│   └── performance/
├── docs/                  # Documentation
│   ├── requirements.md
│   ├── development-plan.md
│   ├── TECH-DEBT.md
│   ├── sessions/          # Session logs
│   ├── adr/               # Architecture Decision Records
│   └── cross-checks/      # Phase completion reviews
├── pyproject.toml         # Project configuration
├── requirements.txt       # Pip dependencies
├── .env.example           # Environment template
├── DESIGN.md              # Architecture document
└── CLAUDE.md              # This file
```

## Development Commands

```bash
# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Format code
black src tests
ruff check src tests --fix

# Type checking
mypy src

# Run dashboard
streamlit run src/dashboard/app.py
```

## Key Design Patterns

1. **Exchange Abstraction**: All exchanges implement `BaseExchange` interface
2. **Strategy Pattern**: Analysis techniques implement `BaseStrategy`
3. **Factory Pattern**: Exchange and strategy instantiation via factory functions
4. **Repository Pattern**: Data storage abstracted via repository classes

## Configuration

All sensitive configuration via environment variables (`.env` file):
- Exchange API keys
- Trading mode (paper/live)
- Risk parameters

See `.env.example` for all available options.

## Related Requirements

- `docs/requirements.md` - Full requirements specification
- `docs/development-plan.md` - Development roadmap
- `DESIGN.md` - Architecture and design details

## AI Integration

Fly explicitly selects Codex CLI 0.153.4 / `gpt-6-astra`. The provider factory
returns `LLMClient`; Claude remains an explicit rollback/local compatibility
option. NFR-002 / CON-001 prohibit direct paid LLM API fallback. Dedicated
Codex auth persists on `/data`; see `docs/codex-runtime.md`.

## Testing Guidelines

- All new features require unit tests
- Use `pytest` with `tmp_path` fixture for file operations
- Mock external APIs (exchanges, Claude CLI)
- Test both success and error paths

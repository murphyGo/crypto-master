# Crypto Master

Crypto Master is a brownfield automated crypto trading system for Claude
CLI-assisted strategy generation, backtesting, proposal review, paper/live
trading, and operator dashboard workflows.

The project predates the AI-DLC overlay. Existing implementation, session logs,
cross-checks, technical debt records, and runtime behavior are treated as source
of truth unless a current task intentionally updates them.

## What It Does

- Runs paper or live crypto trading loops against exchange adapters.
- Generates and evaluates trading proposals with Claude CLI assistance.
- Supports strategy loading, backtesting, promotion analysis, and performance
  tracking.
- Persists local runtime state through JSON/JSONL files under `data/`.
- Provides a Streamlit dashboard for operator review and control.
- Tracks new brownfield work through unit-oriented AI-DLC construction plans.

## Project Layout

| Path | Purpose |
|------|---------|
| `src/` | Main Python package |
| `src/main.py` | Trading runtime entry point and engine wiring |
| `src/dashboard/` | Streamlit operator dashboard |
| `src/exchange/` | Binance, Bybit, and exchange abstractions |
| `src/strategy/` | Strategy framework, loader, indicators, performance helpers |
| `src/trading/` | Paper/live traders, portfolio, profiles, sub-account support |
| `src/backtest/` | Backtest engine and validation helpers |
| `src/proposal/` | Proposal engine, interactions, history, notifications |
| `src/runtime/` | Runtime engine, activity log, safety/correlation controls |
| `strategies/` | Strategy and technique files |
| `scripts/` | Operator and research scripts |
| `tests/` | Pytest suite |
| `data/` | Runtime/operator data; do not migrate or delete casually |
| `docs/` | Legacy docs, requirements, debt registry, sessions, cross-checks |
| `aidlc-docs/` | Brownfield AI-DLC overlay and active construction plans |

## Setup

Python 3.10 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This repository also includes `uv.lock`, so `uv` can be used for test and tool
commands when available.

```bash
uv run pytest
uv run black src tests
uv run ruff check src tests
```

## Configuration

Create a local `.env` from the example file and fill in only the credentials and
runtime settings needed for your mode.

```bash
cp .env.example .env
```

Important defaults:

- `TRADING_MODE=paper` keeps the runtime in paper mode.
- Paper mode uses testnet exchange wiring when credentials are configured.
- Live mode requires explicit live exchange credentials and fails fast when they
  are missing.
- `DATA_DIR=data` stores runtime/operator state locally by default.
- Claude integration is through the CLI path, `claude -p`; the Anthropic API is
  not the project integration path.

Never commit `.env` or exchange credentials.

## Run

Run the trading runtime:

```bash
python -m src.main
```

Run the operator dashboard:

```bash
streamlit run src/dashboard/app.py
```

Run selected operator scripts:

```bash
python scripts/backtest_baselines.py
python scripts/backtest_combinations.py
python scripts/auto_research_candidates.py
```

## Test And Format

Run the full test suite:

```bash
pytest
```

Run a targeted test:

```bash
pytest tests/test_runtime_engine.py
```

Format and lint:

```bash
black src tests scripts
ruff check src tests scripts
```

Type check:

```bash
mypy src
```

## AI-DLC Workflow

For new work, start from the brownfield AI-DLC state rather than the archived
legacy development plan.

1. Check `aidlc-docs/aidlc-state.md` for current unit status.
2. Use `aidlc-docs/inception/requirements/requirements.md` and
   `aidlc-docs/inception/user-stories/stories.md` for requirement and story
   context.
3. Use `aidlc-docs/inception/application-design/unit-of-work-story-map.md` and
   `aidlc-docs/inception/units/unit-of-work.md` for ownership and likely test
   scope.
4. Use `aidlc-docs/inception/units/debt-unit-map.md` when work starts from
   technical debt or cleanup language.
5. Track active work in `aidlc-docs/construction/plans/` and write artifacts
   under the relevant `aidlc-docs/construction/<unit>/` directory.
6. Update tests, session logs, cross-checks, and `docs/TECH-DEBT.md` when the
   change scope requires it.

`docs/development-plan.md` is a pointer to the archived chronological plan.
`docs/legacy/development-plan.md` remains historical reference, not the active
queue.

## Key References

- `CLAUDE.md` - developer guide and command reference
- `DESIGN.md` - architecture design
- `docs/requirements.md` - historical detailed requirements
- `docs/TECH-DEBT.md` - active and resolved technical debt registry
- `docs/deployment.md` - deployment notes
- `docs/sessions/` - implementation session logs
- `docs/cross-checks/` - compliance and completion reviews
- `aidlc-docs/construction/README.md` - construction artifact guidance

## Safety Notes

- Preserve existing runtime behavior unless a task explicitly changes it.
- Treat `data/` as operator/runtime state.
- Keep live trading conservative: live mode requires credentials and explicit
  operator intent.
- Prefer additive migrations and compatibility shims for paper/live state.
- Track significant decisions in session logs, and create ADRs only for durable
  architecture choices.

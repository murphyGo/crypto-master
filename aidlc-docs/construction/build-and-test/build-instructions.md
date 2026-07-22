# Build Instructions: backtesting-validation Derivatives Data Slice 4

## Current scope

These instructions build the operator-approved LC-11 snapshot replay and
robustness integration. Verification is offline and does not invoke the
explicit live `--refresh-snapshot` or exploratory `--live` paths.

## Prerequisites

- Python 3.10 or newer; verified with Python 3.13.0.
- uv 0.7.15 and the existing `uv.lock`.
- Development dependencies from `pyproject.toml`.
- No environment variable, exchange credential, service, or repository
  runtime-data preparation is required.

## Locked dependency check

```bash
uv lock --check
```

Verified result: 91 packages resolved with no lock/dependency mutation.

## Compile and offline import

```bash
uv run python -m compileall -q src/backtest scripts/run_robustness_gate.py
uv run python -c '<socket connection guard plus replay/snapshot/engine/gate/harness/CLI imports>'
```

Verified imports: `ReplayIdentity`, `SnapshotReplaySource`, `SnapshotV2`,
`Backtester`, `BacktestResult`, `RobustnessGate`,
`GateStatus.INSUFFICIENT_DATA`, `BacktestHarness`, and the robustness CLI.
The socket guard observed no connection attempt.

## Verified tool versions

| Tool or library | Version |
|-----------------|---------|
| Python | 3.13.0 |
| uv | 0.7.15 |
| Pydantic | 2.13.3 |
| pytest | 9.0.2 |
| coverage.py | 7.13.5 |
| Black | 26.3.1 |
| Ruff | 0.15.9 |
| mypy | 1.20.0 |

## Build acceptance

- Lock, compile, public imports, and offline-import guard pass.
- Python source remains the executable artifact; no package or deployment
  artifact is generated.
- Dependencies, credentials, deployment, migrations, and repository `data/`
  remain unchanged.

---

# Prior Build Instructions: exchange-integration Derivatives Data Slice 3

## Current scope

These instructions build the operator-approved disabled-by-default runtime
Funding/OI context service and its in-process consumer seams. They do not
enable the feature in production, connect to Binance during verification,
reuse a trading account exchange, require credentials, or mutate `data/`.

## Prerequisites

- Python 3.10 or newer; verified with Python 3.13.0.
- uv 0.7.15 and the committed `uv.lock`.
- Development dependencies declared by `pyproject.toml`.
- No environment variable or exchange credential is required while the
  feature remains disabled, which is the default.

## Locked dependency check

```bash
uv lock --check
```

Verified result: 91 packages resolved with no lock or dependency mutation.

## Compile and import

```bash
uv run python -m compileall -q \
  src/exchange src/strategy src/proposal src/runtime src/dashboard \
  src/config.py src/main.py

uv run python -c 'from src.config import DerivativesDataConfig; from src.exchange.derivatives import MarketContext, DerivativesDataSource; from src.strategy.market_context import MarketContextBuilder; from src.runtime.derivatives_context import DerivativesContextService; from src.proposal.engine import ProposalEngine; from src.runtime.engine import TradingEngine; from src.dashboard.pages.ops import build_ops_diagnostic_rows; print(DerivativesDataConfig.__name__, MarketContext.__name__, DerivativesDataSource.__name__, MarketContextBuilder.__name__, DerivativesContextService.__name__, ProposalEngine.__name__, TradingEngine.__name__, build_ops_diagnostic_rows.__name__)'
```

Verified import output:

```text
DerivativesDataConfig MarketContext DerivativesDataSource MarketContextBuilder DerivativesContextService ProposalEngine TradingEngine build_ops_diagnostic_rows
```

## Verified tool versions

| Tool or library | Version |
|-----------------|---------|
| Python | 3.13.0 |
| uv | 0.7.15 |
| ccxt | 4.5.51 |
| Pydantic | 2.13.3 |
| pytest | 9.0.2 |
| pytest-cov | 7.1.0 |
| Black | 26.3.1 |
| Ruff | 0.15.9 |
| mypy | 1.20.0 |

## Build acceptance

- Locked resolution, compilation, and all declared imports pass.
- Import succeeds while socket connection attempts are forced to fail.
- Python source is the executable artifact; no package/deployment artifact is
  generated.
- `pyproject.toml`, `uv.lock`, dependencies, credentials, deployment files,
  production enablement, and runtime `data/` remain unchanged.

---

# Prior Build Instructions: backtesting-validation Derivatives Snapshot Schema v2

## Current scope

These instructions build the operator-approved LC-10 Snapshot Schema v2 store.
They compile and import an offline persistence module only. They do not start a
runtime process, connect to an exchange, require credentials, or mutate
repository `data/`.

## Prerequisites

- Python 3.10 or newer; verified with Python 3.13.0.
- uv 0.7.15 and the committed `uv.lock`.
- Development dependencies declared by `pyproject.toml`.
- No environment variables or exchange credentials.

## Locked dependency check

```bash
uv lock --check
```

Verified result: 91 packages resolved with no lock or dependency mutation.

## Compile and import

```bash
uv run python -m compileall -q src/backtest
uv run python -c 'from src.backtest.snapshot_v2 import SnapshotV2, SnapshotV2Manifest, load_snapshot_versioned, save_snapshot_v2; print(SnapshotV2.__name__, SnapshotV2Manifest.__name__, load_snapshot_versioned.__name__, save_snapshot_v2.__name__)'
```

Expected and verified import output:

```text
SnapshotV2 SnapshotV2Manifest load_snapshot_versioned save_snapshot_v2
```

## Verified tool versions

| Tool or library | Version |
|-----------------|---------|
| Python | 3.13.0 |
| uv | 0.7.15 |
| Pydantic | 2.13.3 |
| pytest | 9.0.2 |
| pytest-cov | 7.1.0 |
| Black | 26.3.1 |
| Ruff | 0.15.9 |
| mypy | 1.20.0 |

## Build acceptance

- Locked resolution, compilation, and imports pass.
- The build creates no package/deployment artifact; Python source is the
  executable artifact.
- `pyproject.toml`, `uv.lock`, dependencies, configuration, credentials,
  deployment files, and runtime `data/` remain unchanged.

---

# Prior Build Instructions: exchange-integration Derivatives Data Slice 1

## Scope

These instructions build the operator-approved exchange/domain foundation for
Funding Rate and Open Interest data. They do not start a runtime service,
connect to Binance, mutate `data/`, or require trading credentials.

## Prerequisites

- Python 3.10 or newer. The verified environment used Python 3.13.0.
- `uv` with the repository `uv.lock`. The verified version was 0.7.15.
- Development dependencies from `pyproject.toml`.

## Prepare the environment

```bash
uv sync --locked --extra dev
uv lock --check
```

No environment variable is required. Do not add Binance API keys for this
public-data Slice 1 build.

## Compile and import

```bash
uv run python -m compileall -q src/exchange
uv run python -c 'from src.exchange.binance import BinanceExchange; from src.exchange.derivatives import FundingRate, OpenInterestHistory; print(BinanceExchange.name, FundingRate.__name__, OpenInterestHistory.__name__)'
```

Expected import output:

```text
binance FundingRate OpenInterestHistory
```

## Verified dependency/tool versions

| Tool or library | Version |
|-----------------|---------|
| Python | 3.13.0 |
| uv | 0.7.15 |
| ccxt | 4.5.51 |
| Pydantic | 2.13.3 |
| pytest | 9.0.2 |
| pytest-cov | 7.1.0 |
| Black | 26.3.1 |
| Ruff | 0.15.9 |
| mypy | 1.20.0 |

## Build acceptance

- `uv lock --check` resolves without changing the lock file.
- `src/exchange` compiles without syntax errors.
- The generated Binance adapter and derivatives domain contracts import.
- No dependency, configuration, credential, runtime-data, or deployment file
  is changed by the build.

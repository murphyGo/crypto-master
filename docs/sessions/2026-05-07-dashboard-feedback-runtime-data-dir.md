# Dashboard Feedback Runtime Data Directory

- **Date**: 2026-05-07
- **Unit**: `dashboard-operator-ui`
- **Stage**: Code Generation / Build and Test
- **Related Requirements**: FR-030, FR-032, NFR-003
- **Related Story**: US-012

## Context

Fly runtime inspection showed `DATA_DIR=/data`, but the Feedback Loop dashboard
and Home command center read candidate state from the relative
`data/feedback/state` path. In the deployed container that resolves under
`/app/data/...`, so generated feedback candidates persisted under `/data` would
not be visible in the dashboard.

The same inspection initially showed that `/data/feedback`, `/data/audit`, and
`/data/research_runs` did not yet exist, so no feedback-loop candidates had
been generated in the Fly runtime.

## Changes

- Added `default_candidate_state_dir()` and `default_promotion_state_dir()` in
  `src/dashboard/pages/feedback.py` backed by `get_settings().data_dir`.
- Updated the Feedback Loop page default paths to use those helpers.
- Updated Home command-center candidate metrics to use the same runtime
  feedback state path.
- Updated Fly image packaging so `scripts.auto_research_candidates` and its
  strategy catalog are available inside `/app`.
- Updated `scripts.auto_research_candidates.build_exchange()` to construct a
  credential-free public-data Binance exchange, preventing invalid Fly trading
  keys from blocking OHLCV fetches.
- Added connect-failure cleanup so owned exchanges are disconnected even when
  initial connection fails.
- Removed full priority-matrix catalog injection from code-type new-idea prompts;
  selected auto-research picks already carry their own context and tunables.
- Routed auto-research run artifact defaults through `Settings.data_dir`, so Fly
  writes snapshots under `/data/research_runs` instead of `/app/data`.
- Added `Settings.claude_cli_model` and passed it through to `claude --model`.
  Fly sets this to `sonnet` for feedback candidate generation latency/cost.
- Added regression coverage for `DATA_DIR`-aware defaults and Home command
  center path usage.

## Verification

```bash
uv run pytest tests/test_dashboard_feedback.py tests/test_dashboard_app.py -q
```

Result: 50 passed.

```bash
uv run pytest tests/test_scripts_auto_research_candidates.py -q
```

Result: 22 passed.

```bash
uv run pytest tests/test_ai_improver.py tests/test_scripts_auto_research_candidates.py -q
```

Result: 65 passed.

```bash
uv run pytest tests/test_ai_claude.py tests/test_config.py -q
```

Result: 130 passed.

Additional checks:

```bash
uv run black src/dashboard/pages/feedback.py src/dashboard/app.py \
  tests/test_dashboard_feedback.py tests/test_dashboard_app.py
uv run ruff check src/dashboard/pages/feedback.py src/dashboard/app.py \
  tests/test_dashboard_feedback.py tests/test_dashboard_app.py
uv run ruff check scripts/auto_research_candidates.py \
  tests/test_scripts_auto_research_candidates.py
uv run ruff check src/ai/improver.py scripts/auto_research_candidates.py \
  tests/test_ai_improver.py tests/test_scripts_auto_research_candidates.py
uv run ruff check src/ai/claude.py src/config.py \
  tests/test_ai_claude.py tests/test_config.py
```

Result: clean.

## Fly Runtime Evidence

After deployment, a one-off Fly auto-research run was executed with an extended
Claude timeout:

```bash
CLAUDE_CLI_TIMEOUT_SECONDS=600 CLAUDE_CLI_MAX_RETRIES=0 \
  python -m scripts.auto_research_candidates --picks 1 --symbol BTC/USDT
```

The run generated `donchian_turtle_s2`, but robustness validation discarded the
candidate. It failed `oos`, `walk_forward`, `regime`, and `sensitivity` gates.
The run artifact was written to `/data/research_runs/run_20260507_124121.json`.

Follow-up Fly inspection confirmed the dashboard feedback state path now has
one candidate record:

```text
1
[('8b2d9b5c-f6f1-409b-8d4e-3ff28b1e966f', 'discarded', 'donchian_turtle_s2', False, ['oos', 'walk_forward', 'regime', 'sensitivity'])]
```

Therefore, the current Fly runtime has feedback-loop data, but zero
`AWAITING_APPROVAL` proposals because the generated candidate correctly failed
the robustness gate.

## Runtime Claude Cost Control

Follow-up Fly runtime inspection showed that the trading engine was running
every 300 seconds and repeatedly generating paper proposals through
`simple_trend_analysis`, a prompt-based `PromptStrategy` that invokes
`ClaudeCLI.analyze()` during the engine scan hot path.

To stop routine engine cycles from consuming Claude tokens:

- `strategies/sample_prompt.md` now marks `simple_trend_analysis` as
  `deprecated`, so `load_all_strategies()` skips it for runtime scans while
  direct loader tests can still validate the historical prompt artifact.
- `fly.toml` sets `ENGINE_CYCLE_INTERVAL=1800`, reducing Fly engine scan
  frequency from every 5 minutes to every 30 minutes.
- `tests/test_strategy_integration.py` now pins that
  `simple_trend_analysis` is directly loadable but excluded from the runtime
  strategy list.

Verification:

```bash
uv run pytest tests/test_strategy_integration.py tests/test_config.py -q
```

Result: 100 passed.

Fly deployment `v34` completed successfully. Runtime verification showed:

```text
cycle=1800
model='sonnet'
timeout=120
Skipping deprecated strategy: simple_trend_analysis
['bollinger_band_reversion', 'ma_crossover', 'rsi_15m', 'rsi_4h', 'rsi_universal']
False
```

Follow-up structural guard:

- Added `TechniqueInfo.prompt_trigger`, defaulting to `none`.
- Added `src/strategy/prompt_filters.py` with an `ict_smc_setup` pre-Claude
  filter. It allows prompt execution only when recent OHLCV shows a liquidity
  sweep, order-block revisit, or fair-value-gap revisit.
- `ProposalEngine` now evaluates the prompt trigger after OHLCV fetch and
  before `PromptStrategy.analyze()`, so failed filters do not call Claude and
  do not start the prompt cooldown.
- `strategies/chasulang_ict_smc.md` declares `prompt_trigger: ict_smc_setup`.
- Fly keeps `ENGINE_PROMPT_STRATEGY_MIN_INTERVAL_SECONDS=300`; current prompt
  strategies remain deprecated, so this setting is only a guard for future
  reactivation.

Verification:

```bash
uv run pytest tests/test_proposal_engine.py tests/test_strategy_base.py tests/test_strategy_loader.py tests/test_strategy_integration.py tests/test_config.py tests/test_main_dispatch.py -q
uv run ruff check src/strategy/base.py src/strategy/prompt_filters.py src/proposal/engine.py tests/test_proposal_engine.py tests/test_strategy_base.py src/config.py src/main.py tests/test_config.py tests/test_main_dispatch.py tests/test_strategy_integration.py
git diff --check
```

Result: 236 passed; lint and diff checks clean.

Fly deployment `v36` completed successfully. Runtime verification showed:

```text
prompt_interval=300
chasulang_status=deprecated
chasulang_trigger=ict_smc_setup
proposal_prompt_interval=300
['bollinger_band_reversion', 'ma_crossover', 'rsi_15m', 'rsi_4h', 'rsi_universal']
```

Prompt-trigger relaxation:

- Reframed prompt triggers as broad context filters instead of strict setup
  confirmation filters.
- Added `ict_smc_context` for Chasulang-style prompts. It now permits Claude
  when the market shows a recent liquidity sweep, OB/FVG revisit, swing
  liquidity proximity, or compressed range-boundary context. The older
  `ict_smc_setup` value remains accepted as a compatibility alias.
- Added `trend_context` for simple trend/support-resistance prompts. It permits
  Claude on directional movement, support/resistance proximity, volume
  expansion, or range expansion.
- `strategies/chasulang_ict_smc.md` now declares
  `prompt_trigger: ict_smc_context`.
- `strategies/sample_prompt.md` now declares `prompt_trigger: trend_context`.

Verification:

```bash
uv run pytest tests/test_proposal_engine.py tests/test_strategy_base.py tests/test_strategy_loader.py tests/test_strategy_integration.py tests/test_config.py tests/test_main_dispatch.py -q
uv run ruff check src/strategy/prompt_filters.py src/strategy/base.py src/proposal/engine.py tests/test_proposal_engine.py tests/test_strategy_base.py
git diff --check
```

Result: 238 passed; lint and diff checks clean.

Fly deployment `v37` completed successfully. Runtime verification showed:

```text
chasulang_ict_smc|deprecated|ict_smc_context
simple_trend_analysis|deprecated|trend_context
```

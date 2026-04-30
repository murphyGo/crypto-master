# Crypto Master - Development Plan

## Reference Documents

- `docs/requirements.md` - Requirements Specification
- `docs/inception.md` - Project Concept Document

---

## Current Status

| Component | Status | Phase |
|-----------|--------|-------|
| Project Setup | ✅ Complete | 1 |
| Configuration Management | ✅ Complete | 1 |
| Exchange Abstraction | ✅ Complete | 2 |
| Binance Integration | ✅ Complete | 2 |
| Bybit Integration | ✅ Complete | 2 |
| Analysis Technique Framework | ✅ Complete | 3 |
| Claude Integration | ✅ Complete | 3 |
| Trading Strategy | ✅ Complete | 4 |
| Exchange Testnet Support | ✅ Complete | 4 |
| Paper Trading (Local) | ✅ Complete | 4 |
| Paper Trading (Testnet) | ✅ Complete | 4 |
| Paper Trading (Fees) | ✅ Complete | 4 |
| Live Trading | ✅ Complete | 4 |
| Portfolio / Asset Management | ✅ Complete | 4 |
| Trading Strategy Profiles | ✅ Complete | 4 |
| Backtesting | ✅ Complete | 5 |
| Performance Analyzer | ✅ Complete | 5 |
| Strategy Improver (Hypothesis-Driven) | ✅ Complete | 5 |
| Robustness Validation Gate | ✅ Complete | 5 |
| Feedback Loop | ✅ Complete | 5 |
| Trading Proposal | ✅ Complete | 6 |
| UI Dashboard | ✅ Complete | 7 |
| Trading Engine Runtime | ✅ Complete | 8 |
| Engine Status Dashboard Page | ✅ Complete | 8 |
| Fly.io Deployment | ✅ Complete | 8 |
| Multi-Timeframe Strategy Support | ✅ Complete | 9 |
| Baseline Indicator Strategies | ✅ Complete | 9 |
| Multi-Timeframe Backtester | ✅ Complete | 9 |
| Per-Timeframe RSI Baselines | ✅ Complete | 9 |
| Live Trading Wiring | ✅ Complete | 10 |
| EngineConfig Env Override | ✅ Complete | 10 |
| Baseline Reference Numbers | ✅ Complete | 10 |
| Log Retention Policy | ✅ Complete | 10 |
| Volume-Aware Default Paths | ✅ Complete | 10 |
| Multi-Technique Per-Symbol Scan | ✅ Complete | 10 |
| Pre-Existing Lint/Type Sweep | ✅ Complete | 11 |
| OHLCV Cache for Multi-Technique Scan | ✅ Complete | 11 |
| Notification Push Backend | ✅ Complete | 11 |
| ProposalHistory.purge_old Wiring | ✅ Complete | 11 |
| Cross-Cycle Position Cap | ✅ Complete | 12 |
| Residual mypy Sweep | ✅ Complete | 12 |
| LLM Strategy Timeout Handling | ✅ Complete | 12 |
| Telegram Notification Backend | ✅ Complete | 12 |
| Cleanup Batch (DEBT-009/010/011) | ✅ Complete | 13 |
| EngineConfig Remaining-Fields Env Override | ✅ Complete | 13 |
| BaseExchange.get_ohlcv `since` Parameter | ✅ Complete | 13 |
| Email Notification Backend | ✅ Complete | 13 |
| Chasulang Timeout Mitigation | ✅ Complete | 14 |
| SMTP_SSL Alternative | ✅ Complete | 14 |
| Diagnostic Clarity | ✅ Complete | 15 |
| chasulang Parse + Wedge Mitigation | ✅ Complete | 16 |
| Auto-Research Operator Workflow + Catalog-Aware Improver | ✅ Complete | 17 |
| Stale-Quote Sanity Gate at Proposal Fill | ✅ Complete | 18 |

**Status Legend**: ✅ Complete | 🔄 In Progress | ❌ Missing

---

## Phase 1: Project Setup & Basic Infrastructure

**Related Requirements**: NFR-001, NFR-004, NFR-005

### 1.1 Project Structure Setup

- [x] Create `src/` package structure (`src/__init__.py`)
- [x] Configure `pyproject.toml` (dependencies, metadata)
- [x] Create `requirements.txt` (pip compatible)
- [x] Create `.env.example` template
- [x] Update `.gitignore` (.env, __pycache__, .venv, etc.)

### 1.2 Configuration Management Module

- [x] `src/config.py` - Environment variable loading (python-dotenv)
- [x] Required configuration validation logic
- [x] API key configuration structure per exchange

### 1.3 Common Utilities

- [x] `src/logger.py` - Logging setup (file + console)
- [x] `src/models.py` - Common type definitions (dataclass/Pydantic)
- [x] Unit test setup (`tests/__init__.py`, `pytest.ini`)

---

## Phase 2: Exchange Integration Base

**Related Requirements**: FR-016, FR-017, FR-018, FR-019, FR-020, NFR-009

### 2.1 Exchange Abstraction Layer

- [x] `src/exchange/base.py` - BaseExchange abstract class definition
- [x] Common data model definitions (OHLCV, Order, Position, Balance)
- [x] Exchange factory function implementation
- [x] Write unit tests

### 2.2 Binance Integration

- [x] `src/exchange/binance.py` - BinanceExchange class implementation
- [x] Historical OHLCV data query (klines API)
- [x] Current price query
- [x] Balance query
- [x] Order create/cancel/query interface
- [x] Rate limit handling
- [x] Write unit tests (API mocking)

### 2.3 Bybit Integration

- [x] `src/exchange/bybit.py` - BybitExchange class implementation
- [x] Historical OHLCV data query
- [x] Current price query
- [x] Balance query
- [x] Order interface
- [x] Write unit tests

### 2.4 Tapbit Integration — *deferred to later*

---

## Phase 3: Chart Analysis System

**Related Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-005, NFR-007, NFR-008, NFR-010

### 3.1 Analysis Technique Framework

- [x] `src/strategy/base.py` - BaseStrategy abstract class
- [x] `src/strategy/loader.py` - Technique loader (from md/py files)
- [x] Create `strategies/` directory structure
- [x] Define technique metadata schema (name, version, description)
- [x] Write unit tests

### 3.2 Basic Analysis Technique Implementation

- [x] `strategies/sample_prompt.md` - Sample md prompt technique
- [x] `strategies/sample_code.py` - Sample Python code technique
- [x] Technique execution and result return logic
- [x] Write unit tests

### 3.3 Claude Integration

- [x] `src/ai/claude.py` - Claude CLI wrapper (`claude -p "..."`)
- [x] Chart analysis prompt template
- [x] Response parsing logic (trading point extraction)
- [x] Error handling (CLI failure, parsing failure)
- [x] Write unit tests

### 3.4 Analysis Technique Performance Tracking

- [x] `src/strategy/performance.py` - Performance data model
- [x] Performance record storage (`data/performance/`)
- [x] Performance query and aggregation functions
- [x] Write unit tests

### 3.5 Trade History Enhancement

- [x] Enhance `PerformanceRecord` with trade execution fields (quantity, leverage, fees, mode)
- [x] Create `TradeHistory` model for complete trade lifecycle
- [x] Create `TradeHistoryTracker` class with CRUD operations
- [x] Separate storage by mode (`data/trades/{backtest,paper,live}/`)
- [x] Link between `PerformanceRecord` and `TradeHistory`
- [x] Write unit tests

---

## Phase 4: Trading Strategy & Execution

**Related Requirements**: FR-006, FR-007, FR-008, FR-009, FR-010, NFR-007, NFR-008, NFR-012

### 4.1 Trading Strategy Module

- [x] `src/trading/strategy.py` - Trading strategy calculator
- [x] Risk/Reward (R/R) calculation function
- [x] Entry/take-profit/stop-loss calculation function
- [x] Leverage setting logic
- [x] Position size calculation
- [x] Write unit tests

### 4.2 Exchange Testnet Support

- [x] Add `testnet: bool` parameter to `BaseExchange` abstract class
- [x] Add testnet URL configuration to `BinanceExchange` (testnet.binance.vision)
- [x] Add testnet URL configuration to `BybitExchange` (testnet.bybit.com)
- [x] Add testnet API key configuration to Settings (separate from live keys)
- [x] Write unit tests for testnet mode

### 4.3 Paper Trading Engine

**Local Simulation (Complete):**
- [x] `src/trading/paper.py` - PaperTrader class
- [x] Virtual asset (balance) management
- [x] Order simulation (entry, take-profit, stop-loss)
- [x] Trade history recording (`data/trades/paper/`)
- [x] Write unit tests

**Exchange Testnet Integration (Primary):**
- [x] Update PaperTrader to accept exchange instance in testnet mode
- [x] Use exchange testnet for order execution when available
- [x] Fetch real testnet balances from exchange
- [x] Write integration tests with testnet

**Fee Simulation (Fallback):**
- [x] Add fee configuration to PaperTrader (maker/taker fees per exchange)
- [x] Calculate and deduct fees on order execution
- [x] Include fees in P&L calculation
- [x] Write unit tests for fee calculation

### 4.4 Live Trading Engine

- [x] `src/trading/live.py` - LiveTrader class
- [x] Exchange-connected order execution
- [x] User confirmation flow (approval before execution)
- [x] Position monitoring
- [x] Trade history recording (`data/trades/live/`)
- [x] Write unit tests

### 4.5 Asset/PnL Management

- [x] `src/trading/portfolio.py` - Portfolio management
- [x] Asset history storage (`data/portfolio/`)
- [x] PnL calculation (realized/unrealized)
- [x] Separate storage by paper/live mode
- [x] Write unit tests

### 4.6 Trading Strategy Profiles

- [x] `src/trading/profiles.py` - TradingProfile model (risk params, entry/exit rules)
- [x] `src/trading/profile_loader.py` - Load profiles from YAML/JSON files
- [x] Create `trading_profiles/` directory for profile storage
- [x] Sample profiles (conservative, moderate, aggressive, scalping)
- [x] Combine Analysis Technique + Trading Profile for execution
- [x] Update PerformanceTracker to track by technique+profile combination
- [x] Write unit tests

---

## Phase 5: Feedback Loop System

**Related Requirements**: FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, FR-027, NFR-006

### 5.1 Backtesting Engine

- [x] `src/backtest/engine.py` - Backtester class
- [x] Strategy simulation with historical data
- [x] Trade simulation (considering slippage, fees)
- [x] Result storage (JSON/CSV - `data/backtest/`)
- [x] Write unit tests

### 5.2 Performance Analyzer

- [x] `src/backtest/analyzer.py` - PerformanceAnalyzer class
- [x] Win rate calculation
- [x] Total return / annualized return
- [x] Maximum drawdown (MDD) calculation
- [x] Sharpe ratio calculation
- [x] Report generation (md format)
- [x] Write unit tests

### 5.3 Claude-Based Technique Improvement

- [x] `src/ai/improver.py` - StrategyImprover class
- [x] Improvement prompt generation based on performance data
- [x] New technique idea generation prompt
- [x] User idea input → technique generation
- [x] Generated technique storage (`strategies/experimental/`)
- [x] Write unit tests
- [x] **Hypothesis-driven prompt redesign** (FR-033, FR-035): mandatory
  `hypothesis` frontmatter field; new-idea prompt rejects generic
  indicator mashups and steers toward market-structure hypotheses
  (funding/liquidation/OI/basis/stablecoin flow); improvement prompt
  enforces a structural Failure Analysis section and caps added
  conditions to ≤ 2 per revision.

### 5.4 Robustness Validation Gate

**Related Requirements**: FR-034, FR-027, NFR-006

- [x] `src/backtest/validator.py` - `RobustnessGate`, `RobustnessReport`,
  `RobustnessConfig`, `GateResult`, `GateStatus`
- [x] **Out-of-sample (OOS) gate** — chronological 70/30 split; OOS
  Sharpe must retain ≥ 70% of in-sample Sharpe; SKIPPED if either
  split has too few trades.
- [x] **Walk-forward gate** — N consecutive non-overlapping windows;
  ≥ 60% of evaluable windows must be profitable.
- [x] **Regime gate** — classify each entry candle by SMA-relative
  regime (bull/bear/sideways); require non-negative expectancy in
  every regime that has enough trades.
- [x] **Parameter sensitivity gate** — sweep caller-supplied
  `param_grid` via `strategy_factory`; require mean Sharpe across
  grid ≥ 50% of baseline AND ≥ 60% of grid points profitable;
  hard cap on combo count to prevent grid explosion.
- [x] Aggregate `RobustnessReport` with overall verdict (PASSED if no
  FAILED gates), per-gate diagnostics, and human-readable summary.
- [x] Write unit tests (18 tests covering each gate's PASS / FAIL /
  SKIP paths plus aggregate report).

### 5.5 Automated Feedback Loop

**Related Requirements**: FR-026, FR-027, FR-034, CON-003

- [x] `src/feedback/loop.py` - `FeedbackLoop` orchestrator with
  `CandidateRecord`, `LoopStatus`, `FeedbackLoopError`
- [x] Loop execution: improvement → backtesting → **robustness gate** → decision
  via `improve_existing` / `propose_new` / `from_user_idea` / `reevaluate`
- [x] Automatic decision based on `RobustnessReport.overall_passed`
  (FAILED → `DISCARDED`; PASSED → `AWAITING_APPROVAL`)
- [x] Technique adoption flow — `approve(candidate_id, approver)` moves
  the file from `strategies/experimental/` to `strategies/` and
  rewrites frontmatter `status: active`; `reject(...)` keeps the file
  in experimental for further iteration. CON-003 enforced.
- [x] Loop state persistence at `data/feedback/state/<candidate_id>.json`
  with `save_state` / `load_state` / `list_pending` for manual resumption.
- [x] Append-only JSONL audit log at `data/audit/feedback.jsonl`
  (`src/feedback/audit.py`) recording every
  GENERATED / BACKTESTED / GATE_PASSED / GATE_FAILED / APPROVED /
  REJECTED / PROMOTED / DISCARDED / ERRORED event.
- [x] Write unit tests (23 tests across audit and loop covering
  happy paths, gate failure, approve/reject, state persistence,
  error propagation, frontmatter rewrite).

---

## Phase 6: Trading Proposal System

**Related Requirements**: FR-011, FR-012, FR-013, FR-014, FR-015

### 6.1 Proposal Engine

- [x] `src/proposal/engine.py` - `ProposalEngine` class with
  `Proposal`, `ProposalScore`, `ProposalEngineConfig`,
  `ProposalEngineError`.
- [x] Bitcoin trading proposal logic (FR-011) — `propose_bitcoin`
  selects the best technique by historical edge × sample size and
  produces a fully-priced `Proposal` (entry / SL / TP / quantity /
  leverage) via `TradingStrategy.create_position`.
- [x] Altcoin scan and proposal logic (FR-012) — `propose_altcoins`
  scans a list of symbols, ranks by composite score, returns the
  top-K. Per-symbol exchange and strategy errors are logged and
  skipped so one bad pair doesn't kill the scan.
- [x] Proposal score calculation — `composite = confidence × edge ×
  sample_factor` with a confidence-only fallback when the technique
  has no history. All factors surfaced in `ProposalScore` so callers
  can explain the ranking.
- [x] Write unit tests (19 tests covering happy paths, neutral
  signals, missing strategies, exchange errors, ranking,
  best-technique selection, score formula).

### 6.2 User Interaction

- [x] `src/proposal/interaction.py` - User interaction handling
- [x] Proposal display format (CLI)
- [x] Accept/reject input handling
- [x] Proposal history storage (`data/proposals/`)
- [x] Write unit tests

### 6.3 Notification System

- [x] `src/proposal/notification.py` - Notification module
- [x] Console notification
- [x] File-based notification log
- [x] Write unit tests

---

## Phase 7: UI Dashboard

**Related Requirements**: FR-028, FR-029, FR-030, FR-031, FR-032, NFR-003

### 7.1 Streamlit App Basic Structure

- [x] `src/dashboard/app.py` - Main Streamlit app
- [x] App layout setup (sidebar, main area)
- [x] Page navigation configuration
- [x] Common style/theme settings

### 7.2 Analysis Technique Status Page

- [x] `src/dashboard/pages/strategies.py` - Technique status page
- [x] Display registered technique list
- [x] Display technique-specific performance metrics
- [x] Performance trend charts

### 7.3 Trading Status Page

- [x] `src/dashboard/pages/trading.py` - Trading status page
- [x] Display active positions (paper/live)
- [x] Recent trade history
- [x] Asset status and PnL summary
- [x] Equity curve chart

### 7.4 Feedback Loop Status Page

- [x] `src/dashboard/pages/feedback.py` - Feedback loop page
- [x] Experimental technique list
- [x] Backtesting result display
- [x] Loop progress status

### 7.5 Tapbit Integration (Deferred)

- [ ] `src/exchange/tapbit.py` - TapbitExchange class implementation

---

## Phase 8: Production Runtime & Deployment

**Goal**: Wrap the existing components into a long-running headless
service and deploy to Fly.io. Auto-approves proposals based on a
configurable composite-score threshold; surfaces every cycle event
to the dashboard via an append-only activity log.

### 8.1 Trading Engine Runtime

- [x] `src/runtime/activity_log.py` - Append-only JSONL event stream
- [x] `src/runtime/engine.py` - `TradingEngine` orchestrator (scan → auto-decide → execute → monitor loop)
- [x] `src/runtime/engine.py` - `EngineConfig` (cycle interval, auto-approve threshold, symbol list, balance)
- [x] `src/main.py` - Production entrypoint with signal-based graceful shutdown
- [x] `ProposalHistory.attach_trade` - Link a proposal to its executed `TradeHistory.id` at open time
- [x] Write unit tests

### 8.2 Engine Status Dashboard Page

- [x] `src/dashboard/pages/engine.py` - Engine activity page
- [x] Current cycle status + summary cards (last cycle, recent activity)
- [x] Activity log timeline with event-type filter
- [x] Cycle-time histogram
- [x] Write unit tests

### 8.3 Fly.io Deployment

- [x] `Dockerfile` (Claude CLI + Python deps)
- [x] `fly.toml` (multi-process: trader + dashboard, single volume)
- [x] `.dockerignore`
- [x] `docs/deployment.md` (Cloudflare Access setup, secrets list, region pick, rollout flow)

---

## Phase 9: Framework Extensions

**Goal**: Extend the strategy framework to support methodologies
that need richer input than the current single-timeframe contract.
The first driver is multi-timeframe top-down analysis (ICT/SMC and
similar) where one decision needs candles across 4h / 1h / 15m / 5m
plus the current spot price.

### 9.1 Multi-Timeframe Strategy Support

**Background**: Phase 8.1's production rollout exposed that
`chasulang_ict_smc` (and any other multi-TF technique) cannot run
on the current framework. `PromptStrategy.format_prompt` only
substitutes `{symbol}`, `{timeframe}`, `{ohlcv_data}`; templates
asking for `{ohlcv_4h}` / `{ohlcv_1h}` / `{ohlcv_15m}` / `{ohlcv_5m}`
/ `{current_price}` correctly fail-fast (introduced post-deploy)
but the strategy is dormant. This sub-task lifts the
single-timeframe restriction.

**Related Requirements**: FR-001, FR-002, FR-003 (chart analysis
methodology — generalising the existing contract; no new FR
introduced)

- [x] Extend `PromptStrategy.format_prompt` to accept
  `ohlcv_by_timeframe: dict[str, list[OHLCV]]` and
  `current_price: Decimal`; fill `{ohlcv_<timeframe>}` and
  `{current_price}` placeholders alongside the existing three
- [x] Adjust `BaseStrategy.analyze` (or add an opt-in companion
  method) so multi-TF data threads through without breaking
  single-TF strategies — extended the abstract signature with
  keyword-only `ohlcv_by_timeframe` / `current_price` defaulting to
  `None`; added explicit `requires_multi_timeframe: bool = False`
  to `TechniqueInfo` so the engine has an unambiguous opt-in flag
  (existing strategies use `timeframes` as "compatible TFs", so
  list length isn't a safe multi-TF signal)
- [x] Extend `ProposalEngine._propose_for_symbol` to read
  `strategy.info.requires_multi_timeframe` (with `timeframes` as the
  list of required TFs), fetch each via `exchange.get_ohlcv`, and
  pass the dict + derived `current_price` to `strategy.analyze` —
  falls back to the current single-TF path otherwise
- [x] Update `Backtester` to feed multi-TF candles per simulated
  step — delivered by Phase 9.3 (`Backtester.run_multi_timeframe`
  with bisect-based per-TF slicing + per-TF warmup gating, plus
  `Backtester.run_for_strategy` dispatcher and full
  `RobustnessGate` / `FeedbackLoop` integration).
- [x] Verify `chasulang_ict_smc` runs end-to-end on the new
  contract — `tests/test_multi_timeframe_smoke.py` loads the real
  template through `load_strategy` and confirms `format_prompt`
  fills every placeholder with no fail-fast. Live Claude call is
  out of scope for unit tests; manual REPL verification documented
  in the session log
- [x] Write unit tests covering the multi-TF `format_prompt` path,
  the engine's multi-TF fetch flow, and a chasulang-style smoke
  test (7 new tests across loader / engine / smoke)

### 9.2 Baseline Indicator Strategies ✅

**Background**: The LLM-driven techniques (`chasulang_ict_smc`,
`simple_trend_analysis`) need a reference point. Without
deterministic indicator strategies running side-by-side, we can't
tell whether the LLM is contributing real edge or just
confidently agreeing with simple TA. These baselines are also a
useful safety net — even if every Claude call fails (rate limit,
auth, parse), the engine still produces proposals from the
indicator strategies.

**Related Requirements**: FR-001, FR-002, FR-003, FR-004
(extending the strategy library; reusing the existing
``BaseStrategy`` interface — no framework changes here)

- [x] `src/strategy/indicators.py` — shared `rsi`, `sma`,
  `bollinger_bands` math so the strategies don't duplicate the
  arithmetic
- [x] `strategies/rsi.py` — RSI mean-reversion. Long when RSI < 30
  on the close; short when RSI > 70. Operates on whatever
  timeframe the engine passes; a per-timeframe split into
  `rsi_4h.py` / `rsi_15m.py` is deferred to a follow-up sub-task
  once Phase 9.1 (multi-TF) lands
- [x] `strategies/bollinger_bands.py` — Bollinger Band mean
  reversion. Long when close pierces the lower band; short on
  the upper band
- [x] `strategies/ma_crossover.py` — Rename the existing
  `sample_code.py` (already implements SMA crossover) into a
  proper baseline; its `sample_*` framing stops mattering as soon
  as it's a real registered strategy
- [x] Mark all three with `status: experimental` and `symbols: []`
  (universal) so they run on every symbol the engine scans
- [x] Update tests that referenced `sample_code.py` by path to use
  the new filename
- [x] Add `docs/baselines.md` describing each baseline's signal
  logic + the exact `Backtester` invocation an operator runs to
  populate win-rate / Sharpe / MDD numbers (running the actual
  backtest needs historical OHLCV fetching that this sub-task
  does not bundle)
- [x] Write unit tests for the indicators (`rsi`, `sma`,
  `bollinger_bands`) and each strategy's signal logic (clear
  triggers above/below threshold, edge cases at exactly the
  threshold, neutral when no setup)

### 9.3 Multi-Timeframe Backtester

**Background**: Phase 9.1 wired multi-TF through the live
``ProposalEngine`` but the offline path (backtester → robustness gate
→ feedback loop) still operated on a single candle stream. A
multi-TF strategy declaring ``requires_multi_timeframe=True`` reached
``format_prompt`` with ``ohlcv_by_timeframe=None`` → unfilled
placeholders → ``StrategyValidationError``. So ``chasulang_ict_smc``
could not pass through the four robustness gates, blocking promotion
through the feedback loop.

**Related Requirements**: FR-025 (Backtesting Execution), FR-027 /
FR-034 (Robustness Validation Gate) — extending existing backtester +
gate; no new FR introduced.

- [x] ``Backtester.run_multi_timeframe(strategy, ohlcv_by_timeframe,
  symbol, primary_timeframe, profile=None)`` — walks the primary TF,
  slices higher TFs by timestamp at each step using ``bisect`` for
  O(N log M) total work, calls ``strategy.analyze`` with the full
  per-TF dict + ``current_price`` derived from the primary candle's
  close. Reuses every existing helper (``_check_intra_candle_exit`` /
  ``_close_trade`` / ``_apply_slippage`` / ``_build_result``). All
  strategy-irrelevant logic — fees, slippage, sizing, end-of-data
  force-close — driven by the primary TF.
- [x] Module-level ``slice_multi_tf_by_index(primary, by_tf, start,
  end)`` helper used by the run loop and the gate splits. Single-TF
  callers pass ``by_tf=None`` and get a clean passthrough.
- [x] ``Backtester.run_for_strategy`` dispatcher — picks
  ``run`` / ``run_multi_timeframe`` from
  ``strategy.info.requires_multi_timeframe``. Raises
  ``BacktestError`` early when a multi-TF strategy has no dict.
- [x] ``RobustnessGate`` — ``evaluate``, ``_gate_oos``,
  ``_gate_walk_forward``, ``_gate_sensitivity``, and ``_run_subset``
  thread an opt-in ``ohlcv_by_timeframe`` keyword through. The OOS
  and walk-forward splits use ``slice_multi_tf_by_index`` to derive
  aligned per-TF subsets — no future leakage. ``_gate_regime``
  unchanged (operates on baseline trades + primary SMA only).
- [x] ``FeedbackLoop`` — every entry point
  (``improve_existing`` / ``propose_new`` / ``from_user_idea`` /
  ``reevaluate``) accepts ``ohlcv_by_timeframe``; ``_run_cycle``
  calls ``backtester.run_for_strategy`` and forwards the dict to
  ``gate.evaluate``. ``chasulang_ict_smc`` (and any future multi-TF
  technique) can now reach ``AWAITING_APPROVAL`` end-to-end.
- [x] Validation: empty dict / missing primary key / empty primary
  series each raise ``BacktestError`` with a useful message.
- [x] Warmup gates every TF, not just the primary — multi-TF
  top-down strategies are useless without a full higher-TF context
  window.
- [x] Write unit tests — 13 in
  ``tests/test_backtest_multi_timeframe.py`` (slicer, validation,
  no-future-leakage, warmup gating, dispatcher); 1 in
  ``tests/test_backtest_validator.py`` (multi-TF gate routing
  preserves no-leakage); 1 in ``tests/test_feedback_loop.py``
  (``ohlcv_by_timeframe`` reaches both backtester and gate).

### 9.4 Per-Timeframe RSI Baselines

**Background**: Phase 9.2 shipped a single universal-cadence
``rsi_mean_reversion`` baseline that ran on whichever timeframe the
engine passed. The user's original ask included both a 4h RSI
(swing) and a 15m RSI (scalp) baseline as distinct strategies — but
in a single-TF engine cycle a universal entry only covers *one*
cadence at a time, so the swing and scalp behaviours can't fire side
by side. This sub-task adds the explicit-cadence siblings and
renames the universal entry for symmetry.

**Related Requirements**: FR-001 / FR-002 / FR-003 / FR-004 —
extending the strategy library only; reuses Phase 9.2's
``RSIMeanReversionStrategy`` class verbatim.

- [x] ``strategies/rsi_4h.py`` — declares ``timeframes: ["4h"]``,
  imports ``RSIMeanReversionStrategy`` so signal logic equivalence
  is automatic.
- [x] ``strategies/rsi_15m.py`` — same logic, ``timeframes: ["15m"]``.
- [x] Renamed universal ``rsi.py``'s ``TECHNIQUE_INFO["name"]``
  from ``rsi_mean_reversion`` → ``rsi_universal`` for symmetry with
  the new siblings. Module file path / class names unchanged so
  every existing import keeps working.
- [x] Updated ``docs/baselines.md`` to list all five baselines and
  describe what each cadence is good for.
- [x] Wrote unit tests (``tests/test_rsi_variants.py``, 6 tests)
  covering loader pickup, metadata, signal-equivalence on identical
  input, and ``TECHNIQUE_INFO`` dict isolation between variants.

---

## Phase 10: Operational Maturation

**Goal**: Take the system from "feature-complete + deployable" to
"operable in production". Each sub-task closes a specific
operational gap surfaced in prior-phase session logs and risk
lists. No new framework abstractions — production wiring of
existing components plus operator tooling.

### 10.1 Live Trading Wiring

**Background**: Phase 8.3 deployed paper-only — `src/main.py::build_exchange`
always returns a testnet exchange even when `Settings.trading_mode == "live"`.
The Phase 8 cross-check explicitly carried this as a deliberate deferral.

**Related Requirements**: FR-009, FR-010, NFR-012.

- [x] `src/main.py::build_exchange` switches on `Settings.trading_mode`
  — testnet for paper (with either live or testnet keys accepted),
  mainnet for live (requires live keys; raises a friendly error
  otherwise).
- [x] `src/main.py::build_trader` factory dispatches on
  `Settings.trading_mode`: returns `PaperTrader` for paper,
  `LiveTrader` for live. Engine code path is now mode-agnostic
  (consumes the new `Trader` protocol).
- [x] Introduced `src/trading/base.py::Trader` Protocol —
  `open_position` / `close_position` async, `get_open_trades` /
  `check_exit_conditions` sync. Both `PaperTrader` and `LiveTrader`
  satisfy it; `TradingEngine` now takes `trader: Trader` instead of
  `paper_trader: PaperTrader`.
- [x] `LiveTrader.close_position` signature aligned with PaperTrader's
  (`(trade_id, exit_price, reason="manual")`); auto-exit reasons
  (`stop_loss` / `take_profit`) skip the confirmation callback —
  the user pre-authorized those bounds at open time.
- [x] Wired live confirmation callback to a `_engine_auto_confirmation`
  shim that auto-approves (the engine's threshold gate has already
  authorized the proposal). Interactive sessions can still swap in
  `default_confirmation` for stdin prompts per NFR-012.
- [x] Updated `docs/deployment.md` with a 9-step live-mode checklist
  covering key rotation, threshold tuning, sizing, notifications,
  start-small advice, confirmation policy, exit policy, monitoring,
  and rollback.
- [x] Tests: 11 new dispatch tests in `tests/test_main_dispatch.py`;
  refactored `tests/test_runtime_engine.py` to mock the new `Trader`
  protocol; converted PaperTrader tests to async (open/close
  methods are now async). Existing live-trader tests adjusted to
  the new signature.

### 10.2 EngineConfig Env Override

**Background**: `EngineConfig` (cycle interval, auto-approve threshold,
symbol list, balance) is built from literals in `src/main.py`. Changing
any value requires a code edit + redeploy — bad operability. Phase 8
cross-check tracked this as a documented small follow-up.

**Related Requirements**: NFR-004 (env-driven config); operational concern.

- [x] Add `engine_*` fields to `Settings` (`engine_cycle_interval`,
  `engine_auto_approve_threshold`, `engine_symbols`,
  `engine_balance`).
- [x] `src/main.py` builds `EngineConfig` from `Settings`, not from
  literals.
- [x] `.env.example` documents each new env var with sensible
  defaults that match today's hardcoded values (so existing
  deployments don't change behaviour without an explicit env
  setting).
- [x] `docs/deployment.md` lists the new env vars in the Fly secrets
  / config section.
- [x] Tests: settings-load tests for the new fields; smoke that env
  override propagates through to `EngineConfig`.

### 10.3 Baseline Reference Numbers

**Background**: `docs/baselines.md` shows TBD for win-rate / Sharpe / MDD
on every baseline. Without numbers, "is the LLM beating the baselines?"
isn't answerable. Phase 9.3's multi-TF backtester is in place; this
sub-task is purely operational glue: fetch historical OHLCV, run the
existing `Backtester`, write the table.

**Related Requirements**: FR-025 (consumed); operator tooling.

- [x] `scripts/backtest_baselines.py` — operator script (not a service):
  fetch Binance historical OHLCV (3 months × 1h for swing baselines;
  1 month × 15m for `rsi_15m`), run `Backtester.run` per baseline,
  run `PerformanceAnalyzer`, persist results under
  `data/backtest/baselines/<strategy>/`. Idempotent — re-runnable
  to refresh the numbers.
- [x] Update `docs/baselines.md` reference-numbers table from the
  latest run.
- [x] No automated tests required (one-off operator script); a smoke
  test that mocks the exchange and verifies the script writes the
  expected output files is sufficient.

### 10.4 Log Retention Policy

**Background**: `data/audit/feedback.jsonl`, `data/runtime/activity.jsonl`,
and `data/proposals/` all grow unbounded. Phase 5 / 7 / 8 risk lists
all flagged this. Today's volumes are tiny but post-deployment the
files balloon — a few MB/day at current scan cadence.

**Related Requirements**: NFR-008 (mode-separated storage extends to
retention); operational concern.

- [x] Add a small `JsonlRotator` utility that wraps an append-only
  JSONL file with **time-based monthly rotation**: writes go to
  `<base>.YYYY-MM.jsonl`; reads merge across the active month +
  the most recent N archives in timestamp order.
- [x] `AuditLog` and `ActivityLog` use the rotator. ProposalHistory
  (which uses one file per proposal) gets its own age-based purge:
  records older than the retention window move to
  `data/proposals/archive/<YYYY-MM>/`.
- [x] Retention default: 12 months active + archives. Configurable
  via `Settings.log_retention_months`.
- [x] Tests: rotation triggers at month boundary; reads see merged
  history; archives don't affect new writes; corrupt archive lines
  don't kill the read.

### 10.5 Volume-Aware Default Paths

**Background**: Cycle 1's runtime verification (see
`docs/sessions/2026-04-28-priorities-fly-zero-trades-diagnosis.md`,
Runtime Verification Addendum) confirmed that `fly.toml` mounts the
persistent volume at `/data` but the Dockerfile sets `WORKDIR=/app`.
`src/runtime/activity_log.py:34` defaults `DEFAULT_ACTIVITY_PATH` to
`Path("data/runtime/activity.jsonl")` — a relative path that resolves
to `/app/data/runtime/activity.jsonl` (ephemeral container root), not
`/data/runtime/activity.jsonl` (persistent volume). Same defect in
`src/feedback/audit.py`, `src/feedback/loop.py`,
`src/proposal/interaction.py`, `src/proposal/notification.py`, and
`src/trading/portfolio.py`. `PerformanceTracker` and
`TradeHistoryTracker` already thread `Settings.data_dir` correctly
and are the pattern to copy. Impact: every Fly machine recycle
(auto-deploy, OOM, host migration) wipes the activity log, audit
log, proposal history, and portfolio history — producing dashboard
timeline holes and breaking the audit trail Phase 5.5 was designed
to provide.

**Related Requirements**: NFR-008 (mode-separated storage extends to
retention); operational concern — no new FR introduced.

- [x] Route `src/runtime/activity_log.py`'s default activity path
  through `Settings.data_dir` (replicate the
  `PerformanceTracker.__init__` pattern: read `data_dir` from
  settings, build the JSONL path under it).
- [x] Same fix in `src/feedback/audit.py` (`data/audit/feedback.jsonl`).
- [x] Same fix in `src/feedback/loop.py` (loop state directory
  `data/feedback/state/`).
- [x] Same fix in `src/proposal/interaction.py` (`data/proposals/`
  history directory).
- [x] Same fix in `src/proposal/notification.py` (file-notifier
  JSONL path).
- [x] Same fix in `src/trading/portfolio.py` (`data/portfolio/`
  history directory).
- [x] Tests: each component's existing test file gains a "respects
  `data_dir` override" case using `tmp_path` — assert the default
  path is rooted under the configured `data_dir`, not the literal
  string `data/...`.

### 10.6 Multi-Technique Per-Symbol Scan

**Background**: Cycle 1's runtime verification (see
`docs/sessions/2026-04-28-priorities-fly-zero-trades-diagnosis.md`,
Runtime Verification Addendum) showed that
`ProposalEngine._select_best_technique` (`src/proposal/engine.py:391`)
returns exactly one strategy per symbol per cycle, with an
alphabetic-by-name tiebreaker in cold-start. On the live Fly
deployment this means only `bollinger_band_reversion` ever runs —
every other strategy (`rsi`, `ma_crossover`, `chasulang_ict_smc`,
`simple_trend_analysis`, `sample_prompt`) is loaded but never
analyses a candle. Bollinger reversion has a low-base-rate signal
(price piercing the bands), so most cycles produce zero proposals
and the threshold gate never fires. The Phase 9.2 stated goal of
"side-by-side LLM-vs-deterministic comparison + degraded-mode safety
net" is structurally broken by this single-selection design. Note
that Phase 9.4's `rsi_4h` / `rsi_15m` strategies are not on the
deployed Fly image today; once 10.6 ships, the user will manually
redeploy so those siblings actually fire alongside the existing
baselines (out of scope for this sub-task).

**Related Requirements**: FR-005 (Analysis Technique Performance
Tracking — multi-strategy diversification feeds the tracker), FR-012
(Altcoin Trading Proposal — ranking semantics extend to multiple
proposals per symbol).

- [x] Change `ProposalEngine._propose_for_symbol` (or add a sibling)
  so it iterates over **every** applicable technique for the symbol,
  generating one candidate `Proposal` per `(symbol, technique)` pair.
  Neutral signals are still filtered out as today.
- [x] **Per-symbol dedup (trading-correctness — required)**: each
  public entry point (`propose_bitcoin` / `propose_altcoins`) must
  guarantee **at most one proposal per symbol** in its return value.
  When multiple non-neutral techniques produce candidates on the same
  symbol — including the long-vs-short conflict case — the
  highest-composite candidate wins; the others are dropped. Group key
  is the symbol alone, never `(symbol, side)`. Without this guard the
  runtime engine would call `trader.open_position` once per
  technique per symbol per cycle, opening N positions on the same
  pair at N× the intended `risk_percent` — a real-money defect.
- [x] `propose_altcoins` aggregation order: **dedup-by-symbol first,
  then top-K**. With ≤ 1 candidate per symbol and `top_k=3`, the
  result is the 3 best symbols (preserves FR-012's diversification
  semantic). Sorting first then deduping would change the K-th
  selection — don't.
- [x] `propose_bitcoin` returns the single highest-scoring candidate
  from the BTC set. Existing single-proposal contract preserved.
- [x] Add a `ProposalEngineConfig` flag (e.g.
  `multi_technique_per_symbol: bool = True`) for backwards-compatible
  opt-out. Default behaviour is multi-technique. When `False`, the
  legacy `_select_best_technique` path is used unchanged. Decide
  whether to keep `_select_best_technique` as live code (gated by the
  flag) or retire it; document the choice in the session log.
- [x] Tests: new `tests/test_proposal_engine_multi_technique.py`
  covering —
  - multiple non-neutral techniques each produce one proposal on the
    same symbol → only the highest-composite one is returned (long+long
    case);
  - one long candidate and one short candidate on the same symbol with
    different composites → only the highest-composite one is returned
    (long+short conflict case — explicit, not implicit);
  - neutral techniques are filtered out before the dedup;
  - cold-start techniques (no history, composite = `confidence × 0.5`)
    don't crowd out proven techniques (existing scoring semantic
    preserved);
  - top-K across the combined cross-symbol set after per-symbol dedup;
  - single-applicable-technique still works (back-compat smoke);
  - `multi_technique_per_symbol=False` produces identical output to
    the pre-10.6 behaviour (legacy-path smoke).

---

## Phase 11: Operational Hardening + Observability

**Goal**: Take the system from "operationally complete" to
"observable and clean". Phase 10 wired live mode and closed the
audit-trail / multi-technique / config gaps; Phase 11 hardens the
codebase (lint/type sweep), reduces operational drift (OHLCV cache,
`purge_old` wiring), and adds a paging backend for unattended live
operation. No new framework abstractions — production hygiene + one
new notifier.

### 11.1 Pre-Existing Lint/Type Sweep

**Background**: Phase 10's cycles surfaced 18 pre-existing ruff
errors and 24 mypy errors across `src/ai/claude.py`,
`src/strategy/loader.py`, `src/feedback/loop.py`, `src/trading/live.py`,
`src/ai/improver.py`, `src/exchange/binance.py`, `src/trading/paper.py`,
`src/trading/profile_loader.py`, `src/backtest/analyzer.py`, plus the
`pyproject.toml` ruff-deprecation warning and missing `types-PyYAML`.
None new since the project's start; they accumulate friction on every
cycle that touches those modules. Tracked as DEBT-001 (Medium).

**Related Requirements**: NFR-001 (code quality); operational concern
— no new FR introduced.

- [x] Fix ruff errors in `src/ai/claude.py`, `src/strategy/loader.py`,
  `src/feedback/loop.py` (B904 raise-from), test files (F841 / F401
  unused), and any UP035 typing imports.
- [x] Fix mypy errors in `src/trading/live.py` (untyped `Order`
  returns at lines 235 / 244 / 252 / 438 / 445), `src/ai/improver.py:280`
  (arg-type mismatch), `src/trading/paper.py`,
  `src/trading/profile_loader.py`, `src/backtest/analyzer.py`.
- [x] Move `pyproject.toml` ruff config from deprecated top-level
  `select` / `ignore` / `isort` keys to `[tool.ruff.lint]` section.
- [x] Add `types-PyYAML` to dev extras in `pyproject.toml`.
- [x] Document the clean-baseline contract: `ruff check src tests &&
  mypy src` should pass clean. Add a small `scripts/lint.sh` (or
  CONTRIBUTING note) so future cycles can gate on it.
- [x] Tests: existing test suite must remain green; this is a
  refactor, not a feature — no new tests.

### 11.2 OHLCV Cache for Multi-Technique Scan

**Background**: Phase 10.6's `_propose_all_for_symbol` re-fetches
OHLCV per technique → N×M `get_ohlcv` calls per symbol per cycle
(vs 1×M previously). Quant flagged temporal-drift risk (techniques
seeing different candle T's mid-cycle) and rate-limit pressure at
scale. Tracked as DEBT-002 (Low).

**Related Requirements**: FR-005 (consumed); operational concern —
no new FR introduced.

- [x] Add a per-call OHLCV cache keyed by `(symbol, timeframe)`
  threaded through `_propose_all_for_symbol` and
  `_build_proposal_for_strategy`. The simplest shape is a
  `dict[(str, str), list[OHLCV]]` instantiated at the public entry
  point.
- [x] Cache MUST be per-call, not per-engine — strategy decisions
  need fresh data each cycle. Lifetime is exactly one
  `propose_bitcoin` / `propose_altcoins` invocation.
- [x] Multi-TF strategies: keying by `(symbol, tf)` means each
  timeframe is fetched at most once per call regardless of how many
  strategies request it.
- [x] Tests: extend `tests/test_proposal_engine_multi_technique.py`
  with a "fetch is called once per (symbol, tf) even when N
  techniques request it" test (mock `exchange.get_ohlcv`, assert
  call count).

### 11.3 Notification Push Backend

**Background**: Phase 10.1 carried this forward in its session log.
Live mode runs unattended; current notifier backends are Console +
File which page nobody. A push-style backend (Slack via webhook —
simplest setup, no OAuth, easy operator-side mute/redirect) lets the
operator know when a real-money trade fires. Telegram / email left
as future sub-tasks.

**Related Requirements**: FR-015 (Notification System — extending
existing); NFR-012 (live trading awareness).

- [x] `src/proposal/notification.py` — add `SlackNotifier` class
  implementing the existing `Notifier` protocol. Reads
  `SLACK_WEBHOOK_URL` from `Settings` (add field; optional —
  notifier is silent / disabled when not set).
- [x] Notification text: 1-line summary
  (`{symbol} {side} score={composite:.2f} entry={price}`) + a
  thread-style detail block (rationale / SL / TP) in Slack
  code-fence formatting.
- [x] `src/main.py::build_engine` adds `SlackNotifier()` to the
  dispatcher's notifier list when `Settings.slack_webhook_url` is
  set.
- [x] `.env.example` and `docs/deployment.md` document
  `SLACK_WEBHOOK_URL` (operator setup: incoming-webhook creation
  steps).
- [x] Tests: mock the webhook POST; verify (a) notifier is created
  and dispatches when env set, (b) notifier is silent / not
  registered when env unset, (c) message format matches spec, (d)
  HTTP failure does not crash the dispatch path (existing
  per-channel failure isolation contract from Phase 6.3 preserved).

### 11.4 ProposalHistory.purge_old Wiring

**Background**: Phase 10.4 implemented
`ProposalHistory.purge_old(now, retention_months)` but left it
unwired — the method ships and is tested, but no runtime path
invokes it. Long-running Fly deploys will accumulate proposal
records indefinitely until something calls it. The 10.4 session log
explicitly deferred the wiring to a separate sub-task.

**Related Requirements**: NFR-008 (mode-separated storage extends
to retention); operational concern — no new FR introduced.

- [x] `src/main.py::run` (or equivalent startup hook) calls
  `ProposalHistory(...).purge_old(retention_months=settings.log_retention_months)`
  once after `build_engine` returns and before `engine.run_forever()`
  is awaited. Log the count of records purged at INFO level.
- [x] New `src/tools/__init__.py` + `src/tools/purge_proposals.py`
  operator CLI: constructs `ProposalHistory()` from `Settings`,
  calls `purge_old(...)`, prints a summary line. Invocable as
  `python -m src.tools.purge_proposals`.
- [x] `docs/deployment.md` documents the CLI (operator manual
  lever) and notes that the startup hook handles always-on cases.
- [x] Tests: smoke test for the startup hook (`build_engine`
  followed by purge call doesn't crash; mock `ProposalHistory`); CLI
  test (mock `ProposalHistory.purge_old`, assert it was called with
  the retention value from `Settings`).

---

## Phase 12: Risk Hardening + Reliability

**Goal**: Phase 11 closed the operational hardening agenda (lint,
cache, push notifier, purge wiring). Phase 12 closes two real-money
risks surfaced by live Fly monitoring (cross-cycle position
accumulation; LLM-strategy timeouts that silently drop proposals),
batches the residual lint/type debt that Phase 11.1 deferred to
other modules, and adds a second push backend so live mode isn't
single-channel.

### 12.1 Cross-Cycle Position Cap

**Background**: The Fly redeploy on 2026-04-28 produced two BNB short
positions in 14 minutes (05:40:51 and 05:54:30) — the second cycle's
proposal opened a second BNB position because Phase 10.6's per-cycle
dedup only operates *within* a cycle, not *across* cycles. The
`Trader` protocol has no `if symbol in self._open_positions` guard.
Quant flagged this risk during Phase 10.6 design ("Option (b) cap at
TradingEngine — defensible belt-and-braces, follow-up sub-task") but
it was deferred. With the runtime now actively trading, deferring it
any further is a real-money concern: 4× cycle = 4× position
concentration on a single pair, 4× the intended `risk_percent`. This
is independent of Phase 10.6's per-cycle dedup which stays in place.

**Related Requirements**: FR-006, FR-007, FR-008 (Trading Strategy —
risk/leverage/sizing — extending the existing contract; no new FR
introduced).

- [x] Add `max_open_positions_per_symbol: int = 1` field to
  `EngineConfig` — env-overridable as
  `ENGINE_MAX_OPEN_POSITIONS_PER_SYMBOL` via `Settings.engine_*` (10.2
  pattern).
- [x] In `TradingEngine._handle_proposal` (or earlier in `_scan`
  filtering), check `trader.get_open_trades()` for any open position
  on the proposal's symbol; if count ≥ cap, log `proposal_rejected`
  with reason "symbol cap N reached" and skip execution.
- [x] Hard cap at the engine layer, NOT at the proposal-engine layer
  — proposal generation continues unchanged; cap operates at the
  execution gate. Rationale: the proposal still gets recorded for
  audit; only execution is blocked.
- [x] Activity log records the cap rejection so the dashboard
  timeline surfaces it (re-uses the existing `proposal_rejected`
  event shape).
- [x] Tests: extend `tests/test_runtime_engine.py` — proposal
  accepted but symbol already has cap-reached open positions →
  execution is skipped, activity log records the cap rejection, no
  `trader.open_position` call.

### 12.2 Residual mypy Sweep

**Background**: Phase 11.1 fixed the in-scope mypy errors (12 → 0)
but logged 4 follow-up clusters as DEBT-005..008. With the type-clean
baseline established, these can be tackled as a single mini-sweep
cycle. DEBT-006 in particular needs quant review before fix lands —
the factory shape drift looks like genuine API mismatch, not typing
hygiene.

**Related Requirements**: NFR-001 (code quality); operational concern
— no new FR introduced.

- [x] DEBT-005: ccxt typing in `src/exchange/binance.py` (11
  errors). Hand-rolled Protocol covering the 8+ ccxt methods used,
  or runtime `cast(Any, ...)` if Protocol is too noisy — pick the
  lower-friction path.
- [x] DEBT-006: `src/exchange/factory.py` shape drift (3 errors).
  Genuine API mismatch — quant review before fix lands.
- [x] DEBT-007: Dashboard Streamlit type errors (~13 errors across
  `src/dashboard/{theme,app,pages/trading,pages/engine}.py`). Local
  annotations / casts.
- [x] DEBT-008: `src/main.py:271` lambda annotation (1 error).
  One-line fix.
- [x] After: `mypy src` should be fully clean. Add a CI/local check
  (pairs naturally with the DEBT-009 `scripts/lint.sh --fix` safety
  fix if the operator wants both in one PR).
- [x] Tests: existing test suite must remain green; no new tests
  (refactor, not a feature).

### 12.3 LLM Strategy Timeout Handling

**Background**: Live Fly monitoring on 2026-04-28 showed
`chasulang_ict_smc` failing twice within 12 minutes with `Claude CLI
timed out after 120.0 seconds`. The error is logged but the strategy
silently drops out of that cycle's multi-technique scan — no
fallback, no retry, no operational visibility beyond the log line.
As LLM strategies multiply this becomes a reliability concern.

**Related Requirements**: FR-022 (Technique Improvement Suggestion —
extending existing Claude CLI integration); operational concern.

- [x] Add `claude_cli_timeout_seconds: int = Field(default=120)` to
  `Settings` so operators can tune without redeploy.
- [x] Add `claude_cli_max_retries: int = Field(default=1)` — on
  timeout, retry once with a longer timeout (e.g. 1.5×). After max
  retries, fall back to a neutral signal cleanly so the strategy
  doesn't kill the cycle.
- [x] `src/ai/claude.py` — wrap the existing `subprocess.run(...,
  timeout=...)` call with the new retry logic. Log each attempt
  explicitly.
- [x] Add an `ActivityEventType.LLM_TIMEOUT` event so the dashboard
  can show LLM reliability over time.
- [x] Tests: mock subprocess to time out N times; verify retry
  count, eventual neutral fallback, activity event recorded.

### 12.4 Telegram Notification Backend

**Background**: Phase 11.3 shipped Slack-via-webhook. Phase 10.1's
"notification redundancy for live mode" follow-up listed Slack OR
Telegram OR email as candidates — Slack was the first ship, Telegram
is the second logical addition (also webhook-style, also no OAuth
dance, easier setup than email infrastructure).

**Related Requirements**: FR-015 (Proposal Notification — extending
existing); NFR-012 (live trading awareness redundancy).

- [x] `src/proposal/notification.py` — `TelegramNotifier` class
  implementing the existing `Notifier` protocol. Reads
  `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` from `Settings` (both
  required for activation; if either missing, notifier is silent /
  not registered).
- [x] Telegram Bot API URL:
  `https://api.telegram.org/bot<TOKEN>/sendMessage` with
  form-encoded `chat_id` + `text` (Markdown). Use stdlib
  `urllib.request.urlopen` + `asyncio.to_thread` (matches Slack's
  stdlib pattern from Phase 11.3 — zero new dep).
- [x] Message format: same proposal summary line + code-fenced
  detail block as Slack — easier to maintain a single payload spec.
- [x] `src/main.py::build_engine` adds `TelegramNotifier(...)` to
  the dispatcher's notifier list when both env vars set; logs
  presence not values.
- [x] `.env.example` and `docs/deployment.md` document
  `TELEGRAM_BOT_TOKEN` (secret) + `TELEGRAM_CHAT_ID`.
- [x] Tests: mock the HTTP POST; verify (a) created when both env
  set, (b) silent when either missing, (c) message format matches
  spec, (d) HTTP 5xx doesn't crash dispatch (existing per-channel
  failure-isolation contract from Phase 6.3 preserved).

---

## Phase 13: Cleanup + Operational Polish

**Goal**: Phase 13 closes the carry-forward TECH-DEBT items
(DEBT-003, 004, 009, 010, 011), extends the engine env-override
surface to the remaining `EngineConfig` fields, generalises the
exchange OHLCV fetch with a `since` parameter (unblocking 10.3's
pagination reach-around), and adds an email notification backend for
redundancy. Pure cleanup + small ops improvements — no new
architectural directions.

### 13.1 Cleanup Batch (DEBT-009/010/011)

**Background**: Three small cleanup items accumulated across Phases
11 and 12. DEBT-009 (Low): `scripts/lint.sh` uses `ruff check src
tests --fix` which silently rewrites source on lintable regressions
— unsafe for CI gates. DEBT-010 (Low): Phase 12.1's cross-cycle
position cap correctly blocks the long+short same-symbol case (cap
counts trades regardless of side, preventing synthetic hedge), but
the test suite doesn't explicitly cover that path. DEBT-011 (Low):
Phase 12.2 left `dict[str, object]` returns in `build_summary_metrics`
(`src/dashboard/pages/{trading,engine}.py`) forcing
`cast(int|float|str, ...)` at consumer sites — a `TypedDict` rewrite
drops the casts cleanly.

**Related Requirements**: NFR-001 (code quality + test coverage);
operational concern — no new FR introduced.

- [x] DEBT-009: split `scripts/lint.sh` into `scripts/lint.sh`
  (`ruff check src tests && mypy src` — no `--fix`; for CI /
  pre-commit) and `scripts/lint-fix.sh` (`ruff check src tests --fix
  && mypy src` — for dev convenience). Both executable. Update any
  docs that reference `scripts/lint.sh` to clarify which to use.
- [x] DEBT-010: add `test_cap_blocks_opposite_side_same_symbol` to
  `tests/test_runtime_engine.py` — existing trade is long, new
  proposal is short same-symbol, cap=1; verify execution skipped +
  cap-rejection event recorded.
- [x] DEBT-011: define a `SummaryMetrics` `TypedDict` (in
  `src/dashboard/pages/{trading,engine}.py` or a shared
  `src/dashboard/_types.py`); update `build_summary_metrics` returns
  + consumer call sites; drop the `cast()` calls.
- [x] Tests: 13.1 only NEEDS the DEBT-010 test added; existing tests
  must remain green for the lint-script split + dashboard TypedDict
  refactor (refactor only, no behavioural change).

### 13.2 EngineConfig Remaining-Fields Env Override

**Background**: Phase 10.2 wired 4 `EngineConfig` fields
(`cycle_interval`, `auto_approve_threshold`, `symbols`, `balance`)
through `Settings`. The remaining 4 fields are still hardcoded in
`EngineConfig` defaults: `monitor_interval_seconds`,
`bitcoin_symbol`, `altcoin_top_k`, `actor`. Tracked as DEBT-003
(Low). Now that real operators run the system on Fly, the
rare-but-real cases for tuning these without a redeploy justify the
small extension.

**Related Requirements**: NFR-004 (env-driven config); operational
concern — no new FR introduced.

- [x] Add 4 fields to `Settings` in `src/config.py`:
  `engine_monitor_interval: int = Field(default=60, ge=10)` (env
  `ENGINE_MONITOR_INTERVAL`), `engine_bitcoin_symbol: str =
  Field(default="BTC/USDT")` (env `ENGINE_BITCOIN_SYMBOL`),
  `engine_altcoin_top_k: int = Field(default=3, ge=1)` (env
  `ENGINE_ALTCOIN_TOP_K`), `engine_actor: str =
  Field(default="auto-engine")` (env `ENGINE_ACTOR`).
- [x] `src/main.py::build_engine` passes all 4 through to
  `EngineConfig(...)` (10.2 explicit-config-wins back-compat
  preserved).
- [x] Defaults bytewise-equal to the pre-13.2 hardcoded values so
  existing deployments are unchanged without an env setting.
- [x] `.env.example` and `docs/deployment.md` document the 4 new env
  vars.
- [x] Tests: extend `tests/test_config.py::TestEngineSettings` with
  default-value + env-override tests for each (4 new tests); extend
  `tests/test_main_dispatch.py` with one smoke test verifying env
  propagates to `EngineConfig`.

### 13.3 BaseExchange.get_ohlcv with `since` Parameter

**Background**: `scripts/backtest_baselines.py` (Phase 10.3) needs
`since` to paginate past the 1500-candle ccxt cap, but
`BaseExchange.get_ohlcv` doesn't expose it — the script reaches into
`BinanceExchange._client` to access ccxt's `since` arg directly.
Tracked as DEBT-004 (Low). Now that there's a real consumer, the
abstraction should grow the parameter so the reach-around can go
away.

**Related Requirements**: FR-020 (Historical Chart Data Query —
extending the existing contract; no new FR introduced).

- [x] Extend `BaseExchange.get_ohlcv` abstract signature to include
  `since: int | None = None` (timestamp in ms). Update docstring.
- [x] Update `BinanceExchange.get_ohlcv` and `BybitExchange.get_ohlcv`
  to forward `since` to ccxt. Default behaviour (no `since`)
  unchanged.
- [x] Update `scripts/backtest_baselines.py` to use the public API
  instead of the `_client` reach-around. Drop the inline comment
  about the reach-around.
- [x] Tests: add `since`-parameter tests for both Binance and Bybit
  (mock ccxt, verify `since` is forwarded); existing OHLCV tests
  must remain green.

### 13.4 Email Notification Backend

**Background**: Phase 11.3 shipped Slack and Phase 12.4 shipped
Telegram. Phase 10.1's "notification redundancy for live mode"
follow-up listed Slack/Telegram/email as candidates — email is the
third logical addition with a different failure mode (SMTP can fail
when chat APIs are up, and vice versa).

**Related Requirements**: FR-015 (Proposal Notification — extending
existing); NFR-012 (live trading awareness redundancy).

- [x] `src/proposal/notification.py` — `EmailNotifier` class
  implementing the existing `Notifier` protocol. Reads SMTP config
  from `Settings`: `email_smtp_host`, `email_smtp_port`,
  `email_smtp_user`, `email_smtp_password`, `email_from`,
  `email_to`. All 6 required for activation; partial config silent
  (matches Slack/Telegram pattern).
- [x] Use stdlib `smtplib.SMTP` + `email.message.EmailMessage` wrapped
  in `asyncio.to_thread` (zero new dep — matches Slack/Telegram). Subject:
  `"Crypto Master: {symbol} {side} score={c:.2f}"`; body: same
  Markdown content as Telegram (works in any client; plain-text
  fallback included).
- [x] STARTTLS by default; SMTP_SSL as alternative (config option).
  Set socket timeout to 10s. `__repr__` masks password — never log
  credentials.
- [x] `src/main.py::build_engine` appends `EmailNotifier(...)` to the
  dispatcher's notifier list when ALL 6 fields set; logs presence
  not values.
- [x] `.env.example` and `docs/deployment.md` document the 6 SMTP
  env vars.
- [x] Tests: mock `smtplib.SMTP`; verify (a) created when all 6 env
  set, (b) silent when any missing, (c) message format (subject +
  body) matches spec, (d) STARTTLS handshake called, (e) SMTP error
  doesn't crash dispatch (existing per-channel failure-isolation
  contract from Phase 6.3 preserved).

---

## Phase 14: Production Reliability

**Goal**: Phase 14 closes two prod-observed and tracked items: the
persistent chasulang Claude CLI timeouts that Phase 12.3's retry
didn't eliminate, and the SMTP_SSL alternative DEBT-012 that emerged
in 13.4. Compact two-sub-task phase — production reliability polish,
no new framework abstractions.

### 14.1 Chasulang Timeout Mitigation

**Background**: Phase 12.3 added Claude CLI retry-with-1.5×-backoff
(default `max_retries=1`, base timeout 120s → 180s on retry). Live
Fly logs after the Phase 12 redeploy still show `chasulang_ict_smc`
timing out after 120s on every BTC scan cycle (~once per 5 minutes).
Two probable causes worth investigating: (a) the chasulang prompt
template is too long for 120s on the Fly machine's shared CPU /
1 GB RAM, and (b) the retry is firing but both attempts time out —
meaning even 180s isn't enough. Operator tuning of
`CLAUDE_CLI_TIMEOUT_SECONDS` / `CLAUDE_CLI_MAX_RETRIES` only delays
the actual problem if the prompt is the issue; the right fix
combines a per-strategy timeout override (so chasulang can run on a
longer leash without slowing baselines like `rsi_4h.analyze` that
don't need 120s) with observability on the retry path.

**Related Requirements**: FR-022 (Claude AI Integration — extending
the existing contract; no new FR introduced); NFR-001 (operational
reliability).

- [x] Read recent Fly logs (`fly logs -a crypto-master`) and grep
  for `chasulang_ict_smc` + `LLM_TIMEOUT` to confirm actual
  frequency and whether the retry path is being hit (look for the
  Phase 12.3 `retrying with timeout=180s` warning).
- [x] Add per-strategy timeout override to `BaseStrategy.info`
  (e.g. `claude_timeout_seconds: int | None = None` on
  `TechniqueInfo`). When set, `PromptStrategy` passes that to
  `ClaudeCLI` instead of the `Settings.claude_cli_timeout_seconds`
  default; `None` (existing strategies unaffected) falls back to
  Settings.
- [x] Update `strategies/chasulang_ict_smc.md` frontmatter with
  `claude_timeout_seconds: 240` (240s × 1.5 = 360s total with one
  retry).
- [x] Extend `LLM_TIMEOUT` activity event details with
  `attempt_number` (1, 2, ...) + `final_timeout_seconds` so the
  dashboard / operator can verify retry path execution.
- [x] Tests: `BaseStrategy.info` gains a new optional field —
  default `None` keeps existing strategies unaffected; per-strategy
  override path tested with mocked subprocess; `LLM_TIMEOUT` event
  payload tests verify `attempt_number` + `final_timeout_seconds`
  fields.

### 14.2 SMTP_SSL Alternative (DEBT-012)

**Background**: Phase 13.4's `EmailNotifier` ships STARTTLS-only
(`smtplib.SMTP` + `starttls()`). Some SMTP providers (Yahoo Mail,
AT&T, ProtonMail) only offer SMTP-over-SSL on port 465 with no
STARTTLS option. Tracked as DEBT-012 (Low). Now that Phase 13's
notifier shipped, the gap can close cleanly.

**Related Requirements**: FR-015 (Proposal Notification — extending
existing); operational concern.

- [x] Add `email_use_ssl: bool = Field(default=False)` to
  `Settings` in `src/config.py`. Env `EMAIL_USE_SSL=true` activates
  SMTP_SSL on port 465 instead of SMTP+STARTTLS on port 587.
- [x] `src/proposal/notification.py::EmailNotifier` constructor
  accepts a `use_ssl: bool` flag. When True: `smtplib.SMTP_SSL(host,
  port, timeout=...)` with NO `starttls()` call (already encrypted).
  When False (default): existing `smtplib.SMTP` + `starttls()`
  path.
- [x] `src/main.py::build_engine` reads `settings.email_use_ssl`
  and forwards to `EmailNotifier(...)`.
- [x] `.env.example` documents the new env var with provider-specific
  guidance ("Set `EMAIL_USE_SSL=true` and `EMAIL_SMTP_PORT=465` for
  Yahoo / AT&T / ProtonMail").
- [x] `docs/deployment.md` extends the Email subsection with an
  SMTP_SSL note.
- [x] Tests: extend `tests/test_proposal_notification.py` with two
  tests — `test_email_notifier_uses_smtp_ssl_when_flag_set`
  (verifies `smtplib.SMTP_SSL` constructor called, `starttls` NOT
  called) and `test_email_notifier_uses_starttls_when_flag_unset`
  (existing default path stays correct).

---

## Phase 15: Diagnostic Clarity

**Goal**: Surface diagnostic signals that would have prevented the
2026-04-28 misdiagnosis where 139 rejected proposals showed as "0
trades on the dashboard, must be a bug" instead of "threshold gate
working as designed". Two concrete fixes — log message rename for
the proposal sizing path, and a dashboard rejection-reason summary
so operators can see *why* the trade table is empty. No new
framework abstractions.

### 15.1 Diagnostic Clarity (Log + Dashboard)

**Background**: While monitoring the 2026-04-28 Phase 12 redeploy,
the `crypto_master.trading.strategy` logger emitted lines like
`Created position: short BTC/USDT @ 76750.0` — which read like a
trade was opened, but is actually emitted from
`TradingStrategy.create_position` during proposal sizing
(`src/trading/strategy.py:473`), called from
`ProposalEngine._propose_for_symbol` (`src/proposal/engine.py:548`),
**before** the threshold gate runs. The actual trade-open log lives
in `PaperTrader.open_position` at `src/trading/paper.py:546`
(`Opened paper position: ...`) and never fired because every
proposal was rejected at `auto_approve_threshold = 1.0` while
composite scores topped out around 0.35. Result: an hour of
mistaken "trades are happening" reads on logs that turned into
"why does the dashboard show 0?" — both assumptions wrong.
The fix is two safe, mechanical changes plus the operator action
(setting `ENGINE_AUTO_APPROVE_THRESHOLD=0.30` via Fly secrets) that
unblocks actual execution. The operator action is out-of-scope for
this sub-task; only the code clarity follow-up is in scope.

**Related Requirements**: NFR-001 (operability / observability);
operational concern.

- [x] `src/trading/strategy.py` — rename the
  `Created position: ...` log emit at line ~473 to
  `Sized position candidate: ...` so it can't be misread as a
  trade-execution event. Same fields and verbosity; only the verb
  changes. The existing `PaperTrader` "Opened paper position" log
  stays unchanged so the two events are clearly distinct in `fly
  logs` greps.
- [x] `src/dashboard/pages/trading.py` — extend
  `build_summary_metrics` (and the `TradingSummaryMetrics` TypedDict
  from Phase 13.1) with a `proposals_rejected_threshold_count`
  field. Read from `ProposalHistory.list_all()` and count records
  with `decision == "rejected"` whose rejection reason matches the
  threshold-gate pattern (`"composite … below threshold …"`) — the
  cap-rejected pattern (Phase 12.1) is a different cause. Render as
  a compact metric card next to "Active Positions" so an operator
  seeing 0 active positions immediately sees how many proposals
  were rejected and why.
- [x] Tests: extend `tests/test_dashboard_trading.py` with a fixture
  that seeds `ProposalHistory` with one threshold-rejected, one
  cap-rejected (Phase 12.1 pattern), one accepted, and one neutral;
  assert the count surfaces only the threshold-rejected one. Also a
  smoke test that the existing trade renderer still works when the
  new field is `0`.

---

## Phase 16: Chasulang Stability

**Goal**: Address two prod-observed chasulang failures from the
Phase 15.1 redeploy on 2026-04-28: (a) every successful Claude
return parses with `KeyError: 'signal'` because the response is
nested under `trade.*` rather than flat, and (b) the engine
wedged at `15:02:15` for 12+ hours on a 360s chasulang retry —
the subprocess never released, so the wrapper's declared
timeout was a lie. Both render chasulang effectively disabled in
prod and pose a wedge risk for the engine. No new framework
abstractions.

### 16.1 chasulang Parse + Wedge Mitigation

**Background**: After 2026-04-28's Phase 15.1 redeploy, fly logs
showed every chasulang Claude response failing with
`Invalid Claude response format: 'signal'` (a `KeyError` on
`response["signal"]`). The actual response from
`strategies/chasulang_ict_smc.md` returns trade fields nested
under `trade`: `{"external_structure": ..., "liquidity_map":
..., "order_blocks": [...], "trade": {"signal": "neutral", ...},
"wait_conditions": ...}`. Intentional per the chasulang SMC
methodology — top-level keys are the analysis frame; the
actionable trade is the synthesis. Parser needs to look in
`trade.*` first, fall back to top-level for back-compat.

Separately, the engine wedged at `2026-04-28T15:02:15Z` on a
chasulang retry attempt with `timeout=360.0s` and stayed silent
for 12+ hours until the operator manually restarted. Likely
cause: `subprocess.run(..., timeout=...)` under `asyncio.to_thread`
fires the timeout but the child process doesn't get killed
cleanly — stdout buffer fills, child blocks on write, parent
blocks on the timeout exit path. Need explicit kill.

**Related Requirements**: FR-022 (Claude AI Integration —
extending), NFR-001 (operational reliability).

- [x] `src/ai/claude.py::_parse_response` — accept the nested
  `trade.*` form. When the response has a `trade` sub-dict,
  prefer its keys (`signal`, `entry_price`, `stop_loss`,
  `take_profit`, `confidence`, `reasoning`) over top-level. Keep
  top-level fallback for back-compat (`sample_prompt.md`,
  `simple_trend_analysis.md`). When neither form has `signal`,
  raise a clearer error mentioning both candidate paths.
- [x] When the nested form carries `take_profit_1` + `take_profit_2`,
  pick `take_profit_1` (closest target, conservative). Document
  the choice in a parser comment.
- [x] Subprocess wedge: harden `_execute_cli_once` so a timeout
  actually terminates the child. Replace `subprocess.run(...,
  timeout=...)` with explicit `Popen` + `proc.kill()` +
  `proc.wait(timeout=5)` on timeout. Drain stdout/stderr via
  `communicate(timeout=...)` so the process can complete writes.
- [x] Tests:
  - `test_parse_response_handles_nested_trade_form` — chasulang
    shape; `signal` resolved from `trade.signal`.
  - `test_parse_response_handles_top_level_form` — legacy flat
    shape still works.
  - `test_parse_response_picks_take_profit_1_when_tp2_present`.
  - `test_parse_response_raises_clear_error_when_neither_has_signal` —
    error mentions both candidate paths.
  - `test_subprocess_kill_on_timeout` — mock `Popen` to never
    complete; assert `proc.kill()` was called and
    `ClaudeTimeoutError` is raised within bounded wall-clock time.

---

## Phase 17: Strategy-Evolution Operator Workflow

**Goal**: Phase 5.5 shipped `FeedbackLoop` (orchestrator) +
`StrategyImprover` (Claude-driven idea generation) + `RobustnessGate`
(OOS / walk-forward / regime / sensitivity), and Phase 9.3 threaded
multi-timeframe data through the loop end-to-end. The components are
unit-tested but never invoked at runtime — `src/main.py` only has a
FR-026 placeholder comment, and `/app/data/feedback/state/` +
`/app/data/audit/` are empty on Fly. Phase 17 closes the
**operator-driven** path first: a manual `python -m
scripts.auto_research_candidates` invocation that turns Top-N
OHLCV-only picks from `docs/research/strategies/00-priority-matrix.md`
into `AWAITING_APPROVAL` candidate records, leaving promotion to the
operator per CON-003. Nightly auto-execution wiring is deferred to a
later phase.

### 17.1 Auto-Research Operator Workflow + Catalog-Aware Improver

**Background**: The strategy-evolution stack
(`StrategyImprover` → `Backtester` → `PerformanceAnalyzer` →
`RobustnessGate` → `FeedbackLoop._run_cycle` → `CandidateRecord`) has
shipped and is tested in isolation, but no caller has ever exercised
the full chain on Fly — `data/feedback/state/` and `data/audit/` are
empty in production, and `src/main.py` only carries a FR-026 comment.
At the same time the operator built a research catalog under
`docs/research/strategies/` (priority matrix + 9 technique briefs)
that the current `StrategyImprover._build_new_idea_prompt` doesn't
see, so Claude regenerates from-scratch ideas every time instead of
picking from the curated OHLCV-only first-wave list. Two surgical
changes close both gaps without introducing scheduling or
auto-promotion: (a) inject the catalog (priority matrix + per-strategy
docs) into the `generate_idea` / `generate_from_user_idea` prompts so
Claude has the full taxonomy in context, and (b) ship
`scripts/auto_research_candidates.py` — an operator entry point that
reads the priority matrix, picks Top-N OHLCV-only entries, and runs
each through `improver.generate_idea` → `FeedbackLoop._run_cycle()`,
landing every robustness-gate-passing result in `AWAITING_APPROVAL`
for explicit operator approval (CON-003). Nightly scheduling and
`main.py` wiring are deferred to a follow-up sub-task — operator
control comes first.

**Related Requirements**: FR-023 (New Technique Idea Generation),
FR-026 (Automated Feedback Loop), FR-034 (Robustness Validation Gate),
CON-003 (User Approval Required — no auto-promotion); operator
tooling on top of existing components, no new FR/NFR introduced.

**In Scope**:
- `scripts/auto_research_candidates.py` operator entry point
  (`python -m scripts.auto_research_candidates`).
- Catalog-aware `StrategyImprover`: new-idea + user-idea prompts read
  `docs/research/strategies/00-priority-matrix.md` and the per-strategy
  briefs and inject them into the prompt; improvement prompts
  (`generate_improvement`) deliberately do NOT receive the catalog
  (failure-mode analysis stays focused on the existing strategy's
  trace, not the wider taxonomy).
- Fail-soft when the catalog file is missing — improver logs a warning
  and continues with the pre-17.1 prompt, so the path stays usable in
  environments that don't ship the catalog.
- Robustness-gate-passing candidates land in `AWAITING_APPROVAL`;
  failing ones land in `DISCARDED`; errored picks land in `ERRORED`.
  An error on one pick does NOT abort the batch — every pick gets its
  own try/except.
- `--picks N` (default 5; matrix's first-wave OHLCV picks) and
  `--dry-run` flags. Dry-run generates the experimental strategy file
  but skips backtest + robustness gate.
- Run snapshot persisted to `data/research_runs/run_{ts}.json` with
  per-pick status, candidate id, and final state.
- State + audit files (`data/feedback/state/*.json`,
  `data/audit/*.jsonl`) are written end-to-end through the existing
  `FeedbackLoop` machinery — no new persistence code in 17.1.
- Operator-facing summary printed to stdout after the batch (counts +
  per-pick status line).
- README / module-level docstring telling the operator how to invoke,
  what the flags do, and where the output files land.

**Out of Scope**:
- Nightly scheduling / cron / `main.py` wiring (deferred to a later
  sub-task — explicitly out so this stays a single `/dev-crypto`
  cycle).
- Auto-promotion: every passing candidate stops at
  `AWAITING_APPROVAL`; the operator runs `FeedbackLoop.approve()`
  separately. No new approval-flow logic in 17.1.
- Dashboard changes (the existing Phase 7.4 feedback page already
  renders `AWAITING_APPROVAL` records).
- Funding-rate / open-interest / on-chain data wiring — the matrix's
  first-wave picks are OHLCV-only by design; non-OHLCV data sources
  belong to a later phase.

- [x] `scripts/auto_research_candidates.py` — argparse entry point
  with `--picks N` (default 5) and `--dry-run` flags. Reads
  `docs/research/strategies/00-priority-matrix.md`, parses the
  first-wave OHLCV-only picks, and dispatches each through the
  improver + feedback loop. Module docstring documents invocation,
  flags, output locations, and the FR mapping (FR-023 / FR-026 /
  FR-034 / CON-003).
- [x] `src/ai/improver.py::StrategyImprover.__init__` accepts
  `catalog_path: Path | None = None` (defaults to
  `docs/research/strategies/`); add a private `_load_catalog` helper
  that reads the priority matrix + per-strategy briefs, caches the
  joined string on the instance, and fail-softs (logs WARNING +
  returns empty string) when the path is missing.
- [x] `_build_new_idea_prompt` injects the cached catalog content
  under a clearly-labelled section (`## Reference Catalog`).
  `_build_user_idea_prompt` deliberately omits the catalog (the user
  has already described their idea — injecting the catalog would
  redirect Claude away from the user's intent). `_build_improvement_prompt`
  is left untouched — improvement is a focused failure-mode analysis,
  not a fresh-idea exercise. (Deviation from spec wording per
  quant-trader-expert review Issue 4.)
- [x] Dispatch loop in the script: for each pick, call
  `improver.generate_idea(context=<pick description>)` to land the
  new template in `strategies/experimental/`, then
  `FeedbackLoop._run_cycle(strategy_path, ohlcv, ...)` to run
  backtest → robustness gate → state persistence. One pick failing
  raises an exception caught at the per-pick boundary and recorded as
  `ERRORED` in the run snapshot — the batch continues.
- [x] After the batch, persist a JSON run snapshot to
  `data/research_runs/run_{YYYYMMDD-HHMMSS}.json` containing the
  picks list, per-pick `{slug, status, candidate_id, error?}`
  records, and a totals summary. `data/research_runs/` is created on
  first invocation.
- [x] Print an operator-facing summary to stdout: total picks,
  counts by status (`AWAITING_APPROVAL` / `DISCARDED` / `ERRORED`),
  and a per-pick line showing the slug + final state, so the operator
  can immediately spot which candidates need review without opening
  the JSON. Each row is followed by an indented continuation line
  carrying ``decision_reason`` + ``robustness_summary`` so a
  DISCARDED pick's *why* is visible without opening the JSON.
- [x] `--dry-run` short-circuits before the feedback-loop call:
  generates the experimental strategy file under
  ``strategies/experimental/dry_runs/`` (so it never mixes with real
  gated candidates), prints the planned-pick list, but does NOT run
  the backtest / robustness gate / state persistence. Useful for
  validating catalog parsing + prompt output against `claude -p`
  without paying the backtest cost.
- [x] Tests:
  - `tests/test_ai_improver.py` — extend with three catalog-injection
    cases: (a) catalog content appears in `_build_new_idea_prompt`
    output, (b) catalog content does NOT appear in
    `_build_user_idea_prompt` output (regression guard — user-idea is
    anchored on the user's described idea; injecting the catalog
    would redirect Claude away from the user's intent — deviation
    from the original spec wording per quant-trader-expert review
    Issue 4), (c) catalog content does NOT appear in
    `_build_improvement_prompt` output (regression guard that
    improvement stays focused). One additional case for the fail-soft
    branch: missing `catalog_path` produces an INFO log
    (operator-friendly, fail-soft) + empty string, prompts still
    build successfully.
  - `tests/test_scripts_auto_research_candidates.py` — full mocked
    Binance + Claude CLI coverage. Cases: (a) end-to-end happy path
    with N=2 picks, both reaching `AWAITING_APPROVAL`, run snapshot
    written + stdout summary correct; (b) `--dry-run` generates
    strategy files but skips `_run_cycle`; (c) one pick raises,
    other completes — batch does NOT abort, errored pick recorded
    in snapshot. State-file / audit-log persistence under
    `data/feedback/state/` and `data/audit/` is owned by
    `src/feedback/loop.py` + `src/feedback/audit.py` and pinned by
    those modules' own test suites; pinning it again at the script
    level is duplication, so 17.1 inherits the existing coverage
    rather than re-asserting at the script boundary. The
    "matrix-missing" branch and end-to-end persistence behaviour are
    instead exercised by the operator's Fly verification run.

**Verification Criteria**:
- All 4 currently-uncommitted files (`scripts/auto_research_candidates.py`,
  `tests/test_scripts_auto_research_candidates.py`, `src/ai/improver.py`,
  `tests/test_ai_improver.py`) are committed alongside any new files
  this sub-task adds.
- Test count delta: ~+5 to +8 net new tests (1170 → ~1175–1178).
- `scripts/lint.sh` passes (ruff + mypy clean across 53 source files,
  unchanged file count expected — `scripts/` is not in the mypy scope
  so the new script's typing is best-effort).
- One operator-driven Fly run produces ≥1 `CandidateRecord` under
  `/data/feedback/state/` and ≥1 audit entry under `/data/audit/`.
  **This is an operator action, not a code task** — flagged here as a
  follow-up to be checked off after the sub-task ships, not a
  blocker for `/dev-crypto` completion.
- No ADR — see `src/ai/improver.py` and `src/feedback/loop.py` for
  the canonical loop semantics. 17.1 wires existing components into
  an operator script and extends one prompt; no new architectural
  seam.

---

## Phase 18: Live Trading Quality

**Goal**: Close trading-correctness gaps surfaced by the 2026-04-30
production review of `/data/trades/paper/trades.json` (1W/8L,
-78.50 USDT, EV -8.73/trade). The first defect is a stale-quote class
of bug at proposal fill: the runtime engine copies
`proposal.entry_price` into the opened `Position` with no live-price
sanity check, so when chasulang/Claude CLI takes minutes to return
the auto-approved fill happens at a price the live ticker has already
crossed past the proposal's stop-loss. Phase 18 starts with the fill
boundary; later sub-tasks will address the next-largest contributors
the production review surfaces.

### 18.1 Stale-Quote Sanity Gate at Proposal Fill

**Background**: Production paper-trading data on Fly volume
`/data/trades/paper/trades.json` shows trade
`5d51cba3-900f-4415-a401-096df391860a` (ETH long, proposal
`6ef8c07e...`) as a smoking-gun for the stale-quote class of bug:
proposal created at `14:43:21` with `entry=2323`, `SL=2305`;
chasulang/Claude CLI took 3 min 13 sec to return; auto-approval +
fill at `14:46:34` recorded the position at the stale `entry=2323`;
the position closed `0.48s` later at `2300` because the live ticker
had already crossed past the SL by the time of fill. The runtime
engine (`src/runtime/engine.py::_execute` →
`_proposal_to_position`) copies `proposal.entry_price` into the
`Position` with no live-price sanity check, so any LLM latency
spike turns into a guaranteed-loss fill at a price the market has
already moved through. The fix is a sanity gate between
auto-approval and `trader.open_position`: fetch a fresh ticker,
reject the fill if live has crossed the SL or drifted beyond a
configurable slippage tolerance, otherwise fill at
`proposal.entry_price` exactly as today (no silent switch to live
price — that would defeat the proposal's R/R math). Ticker fetch
failure falls back to fill so a transient exchange hiccup doesn't
silently disable trading; the WARN log is the operator's signal.

**Related Requirements**: FR-008 (Entry/Take-Profit/Stop-Loss
Setting — extending the fill boundary so SL is enforced at fill,
not just at exit), FR-013 (User Accept/Reject — auto-approval is
the system's stand-in; the gate is the system's reject path),
NFR-012 (Live Trading Confirmation — paper-trading correctness
boundary; same code path runs live).

- [x] `src/runtime/engine.py::_execute` — between auto-approval and
  `trader.open_position`, call `exchange.get_ticker(symbol).price`
  to fetch a fresh live price. On `Exception`, log WARN
  (`stale_quote_check_failed`) and fall through to fill (preserve
  current behaviour — transient exchange errors must not silently
  disable trading).
- [x] When `EngineConfig.reject_if_past_stop_loss` is `True` and
  live has crossed the SL (live ≤ `proposal.stop_loss` for longs,
  live ≥ `proposal.stop_loss` for shorts), record the proposal as
  `rejected` with `decision_reason="stale_quote_past_sl"` and emit
  the existing rejection activity event with structured fields
  (`live_price`, `proposal_entry`, `proposal_stop_loss`, `side`).
  Skip `trader.open_position`; do not increment `positions_opened`.
- [x] When the absolute drift `abs(live - proposal.entry_price) /
  proposal.entry_price` exceeds
  `EngineConfig.fill_slippage_tolerance`, record the proposal as
  `rejected` with `decision_reason="slippage_exceeds_tolerance"`
  and emit the same rejection activity event shape. Order matters:
  the past-SL check runs first (more specific signal); only if it
  passes does the slippage check run.
- [x] Otherwise fill at `proposal.entry_price` as today — no
  silent switch to the live price. The proposal's R/R math is
  predicated on `entry_price`; mutating it at fill would corrupt
  every downstream metric.
- [x] `EngineConfig.fill_slippage_tolerance: Decimal = Decimal("0.005")`
  (50 bps default; `Field(ge=0)`) and
  `EngineConfig.reject_if_past_stop_loss: bool = True` defaults in
  `src/runtime/engine.py`. Defaults are deliberately conservative —
  reject_if_past_sl on by default closes the smoking-gun bug
  without an env flip.
- [x] `Settings.engine_fill_slippage_tolerance: Decimal` and
  `Settings.engine_reject_if_past_stop_loss: bool` env overrides
  in `src/config.py` (`ENGINE_FILL_SLIPPAGE_TOLERANCE` and
  `ENGINE_REJECT_IF_PAST_STOP_LOSS`); follow the Phase 10.2 /
  13.2 pattern (`Field(default=...)`, parity assertion via the
  existing `test_settings_defaults_match_engine_config` style).
- [x] `src/main.py::build_engine` — wire the two new
  `Settings.engine_*` fields into the `EngineConfig(...)`
  constructor call alongside the existing eight fields; explicit-
  config-wins back-compat preserved. `.env.example` documents both
  new env vars with operator-facing prose.
- [x] Tests in `tests/test_runtime_engine.py` — four cases:
  (a) live past SL → proposal recorded `rejected` with
  `decision_reason="stale_quote_past_sl"`, rejection activity
  event emitted, no `trader.open_position` call,
  `positions_opened == 0`; (b) live within tolerance → fill at
  `proposal.entry_price` (regression guard — pin the no-silent-
  switch contract); (c) live drift beyond tolerance → proposal
  recorded `rejected` with
  `decision_reason="slippage_exceeds_tolerance"`, rejection event
  emitted; (d) `exchange.get_ticker` raises → fill proceeds as
  before, WARN logged with `stale_quote_check_failed`.

---

## Requirements Mapping

| Phase | Related Requirements |
|-------|---------------------|
| Phase 1 | NFR-001, NFR-004, NFR-005 |
| Phase 2 | FR-016, FR-017, FR-018, FR-019, FR-020, NFR-009 |
| Phase 3 | FR-001, FR-002, FR-003, FR-004, FR-005, NFR-002, NFR-005, NFR-007, NFR-008, NFR-010 |
| Phase 4 | FR-006, FR-007, FR-008, FR-009, FR-010, NFR-012 |
| Phase 5 | FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, FR-027, FR-033, FR-034, FR-035, NFR-006 |
| Phase 6 | FR-011, FR-012, FR-013, FR-014, FR-015 |
| Phase 7 | FR-028, FR-029, FR-030, FR-031, FR-032, NFR-003 |
| Phase 8 | FR-009, FR-010, FR-013, FR-014, FR-015, FR-026 (production wiring of existing requirements; no new FR/NFR introduced) |
| Phase 9 | FR-001, FR-002, FR-003 (extending the strategy framework's input contract; no new FR introduced) |
| Phase 10 | FR-005, FR-009, FR-010, FR-012, FR-025, NFR-004, NFR-008, NFR-012 (production wiring + operator tooling for previously-shipped requirements; no new FR/NFR introduced) |
| Phase 11 | FR-005, FR-015, NFR-001, NFR-008, NFR-012 (operational hardening + observability — lint/type sweep, OHLCV cache, Slack notifier, `purge_old` wiring; no new FR/NFR introduced) |
| Phase 12 | FR-006, FR-007, FR-008, FR-015, FR-022, NFR-001, NFR-012 (risk hardening + reliability — cross-cycle position cap, residual mypy sweep, LLM timeout retry/fallback, Telegram notifier; no new FR/NFR introduced) |
| Phase 13 | FR-015, FR-020, NFR-001, NFR-004, NFR-012 (cleanup + operational polish — DEBT-009/010/011 batch, EngineConfig remaining-fields env override, `BaseExchange.get_ohlcv` `since` param, email notifier; no new FR/NFR introduced) |
| Phase 14 | FR-015, FR-022, NFR-001 (production reliability — chasulang per-strategy Claude CLI timeout override + retry observability, SMTP_SSL alternative for `EmailNotifier`; no new FR/NFR introduced) |
| Phase 15 | NFR-001 (diagnostic clarity — proposal-sizing log rename, dashboard threshold-rejection count; no new FR/NFR introduced) |
| Phase 16 | FR-022, NFR-001 (chasulang stability — JSON parse path now accepts nested `trade.signal`, subprocess wedge mitigation; no new FR/NFR introduced) |
| Phase 17 | FR-023, FR-026, FR-034, CON-003 (operator-driven strategy-evolution workflow — catalog-aware idea generation + auto-research script landing candidates in `AWAITING_APPROVAL`; no new FR/NFR introduced) |
| Phase 18 | FR-008, FR-013, NFR-012 (live-trading quality — stale-quote sanity gate at proposal fill enforces SL + slippage tolerance against a fresh ticker; extending the fill boundary, no new FR/NFR introduced) |

---

## Change History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-04-05 | Initial creation | Claude |
| 1.1 | 2026-04-05 | Phase 1.1 complete | Claude |
| 1.2 | 2026-04-05 | Phase 1.2 complete | Claude |
| 1.3 | 2026-04-05 | Phase 1.3 complete, Phase 1 complete | Claude |
| 2.1 | 2026-04-05 | Phase 2.1 complete - Exchange Abstraction Layer | Claude |
| 2.2 | 2026-04-05 | Phase 2.2 complete - Binance Integration | Claude |
| 2.3 | 2026-04-05 | Phase 2.3 complete - Bybit Integration | Claude |
| 3.1 | 2026-04-05 | Phase 3.1 complete - Analysis Technique Framework | Claude |
| 3.2 | 2026-04-05 | Phase 3.2 complete - Basic Analysis Technique Implementation | Claude |
| 3.3 | 2026-04-05 | Phase 3.3 complete - Claude Integration | Claude |
| 3.4 | 2026-04-05 | Phase 3.4 complete - Performance Tracking, Phase 3 complete | Claude |
| 3.5 | 2026-04-05 | Phase 3.5 complete - Trade History Enhancement (NFR-007, NFR-008) | Claude |
| 4.1 | 2026-04-05 | Phase 4.1 complete - Trading Strategy Module (FR-006, FR-007, FR-008) | Claude |
| 4.5 | 2026-04-06 | Added Phase 4.5 - Trading Strategy Profiles (technique+profile combinations) | Claude |
| 4.2 | 2026-04-06 | Phase 4.2 complete - Paper Trading Engine (FR-010, NFR-007, NFR-008) | Claude |
| 4.x | 2026-04-06 | Restructured Phase 4: Added 4.2 Exchange Testnet Support, split 4.3 Paper Trading into Local/Testnet/Fees, renumbered Live→4.4, Asset→4.5, Profiles→4.6 | Claude |
| 4.2 | 2026-04-06 | Phase 4.2 complete - Exchange Testnet Support (FR-010, NFR-009, NFR-011) | Claude |
| 4.3 | 2026-04-06 | Phase 4.3 complete - Paper Trading Testnet Integration (FR-010, NFR-007, NFR-008) | Claude |
| 4.3 | 2026-04-10 | Phase 4.3 complete - Paper Trading Fee Simulation (FR-010, NFR-008) | Claude |
| 4.4 | 2026-04-10 | Phase 4.4 complete - Live Trading Engine (FR-009, NFR-007, NFR-008, NFR-012) | Claude |
| 4.5 | 2026-04-10 | Phase 4.5 complete - Asset/PnL Management (NFR-007, NFR-008) | Claude |
| 4.6 | 2026-04-10 | Phase 4.6 complete - Trading Strategy Profiles (FR-005, FR-006, FR-007, FR-008) | Claude |
| 4.0 | 2026-04-10 | Phase 4 complete - all sub-tasks checked | Claude |
| 5.1 | 2026-04-11 | Phase 5.1 complete - Backtesting Engine (FR-025, NFR-006) | Claude |
| 5.2 | 2026-04-13 | Phase 5.2 complete - Performance Analyzer (FR-021, NFR-006) | Claude |
| 5.3 | 2026-04-13 | Phase 5.3 complete - Claude-Based Technique Improvement (FR-022, FR-023, FR-024, NFR-002) | Claude |
| 5.3a | 2026-04-14 | Phase 5.3 prompt redesign - hypothesis-driven generation (FR-033, FR-035); rejects generic indicator mashups; mandatory `hypothesis` frontmatter; Failure Analysis required for improvements | Claude |
| 5.4 | 2026-04-14 | Phase 5.4 complete - Robustness Validation Gate (FR-034); 4 gates: OOS / walk-forward / regime / parameter sensitivity; 18 tests | Claude |
| 5.x | 2026-04-14 | Renumbered prior 5.4 (Automated Feedback Loop) → 5.5 to slot the Robustness Gate before the loop orchestrator | Claude |
| 5.5 | 2026-04-25 | Phase 5.5 complete - Automated Feedback Loop (FR-026, FR-027, FR-034, CON-003); FeedbackLoop orchestrator + JSONL audit log + state persistence; 23 tests | Claude |
| 5.0 | 2026-04-25 | Phase 5 complete - all sub-tasks (5.1–5.5) checked | Claude |
| 6.1 | 2026-04-25 | Phase 6.1 complete - Proposal Engine (FR-011, FR-012); ProposalEngine + Proposal/ProposalScore + composite score formula; 19 tests | Claude |
| 6.2 | 2026-04-26 | Phase 6.2 complete - User Interaction (FR-013, FR-014); format_proposal + default_decision_prompt + ProposalHistory + ProposalInteraction; 22 tests | Claude |
| 6.3 | 2026-04-26 | Phase 6.3 complete - Notification System (FR-015); ConsoleNotifier + FileNotifier (JSONL) + NotificationDispatcher with min_score gate and per-channel failure isolation; 20 tests | Claude |
| 6.0 | 2026-04-26 | Phase 6 complete - all sub-tasks (6.1–6.3) checked | Claude |
| 7.1 | 2026-04-27 | Phase 7.1 complete - Streamlit App Basic Structure (FR-032, NFR-003); src/dashboard/{app,theme}.py + st.navigation chassis + AppTest smoke; 7 tests | Claude |
| 7.2 | 2026-04-27 | Phase 7.2 complete - Analysis Technique Status Page (FR-028, FR-005); src/dashboard/pages/strategies.py with summary table + per-technique cumulative-P&L trend chart; 14 tests | Claude |
| 7.3 | 2026-04-27 | Phase 7.3 complete - Trading Status Page (FR-029, FR-031); src/dashboard/pages/trading.py with paper/live mode toggle, summary metrics, active positions, recent trades, equity curve; 18 tests | Claude |
| 7.4 | 2026-04-27 | Phase 7.4 complete - Feedback Loop Status Page (FR-030); src/dashboard/pages/feedback.py with status summary cards, candidates table, per-candidate detail + audit timeline; 15 tests | Claude |
| 7.0 | 2026-04-27 | Phase 7 complete - all sub-tasks (7.1–7.4) checked; 7.5 Tapbit deferred | Claude |
| 8.0 | 2026-04-27 | Phase 8 added to plan - production runtime + Fly.io deployment (8.1 engine, 8.2 dashboard page, 8.3 Fly packaging) | Claude |
| 8.1 | 2026-04-27 | Phase 8.1 complete - Trading Engine Runtime; src/runtime/{engine,activity_log}.py + src/main.py + ProposalHistory.attach_trade; auto-decide + interruptible loop + JSONL activity log; 26 tests | Claude |
| 8.2 | 2026-04-27 | Phase 8.2 complete - Engine Status Dashboard Page; src/dashboard/pages/engine.py with cycle aggregation + summary cards + recent-cycles table + duration bar chart + filterable timeline; 21 tests | Claude |
| 8.3 | 2026-04-27 | Phase 8.3 complete - Fly.io Deployment; Dockerfile (Python 3.13 + Node 18 + Claude CLI + tini) + start.sh (signal-forwarding two-process supervisor) + fly.toml (single machine, single volume, Streamlit healthcheck) + .dockerignore + docs/deployment.md | Claude |
| 8.0 | 2026-04-27 | Phase 8 complete - all sub-tasks (8.1–8.3) checked | Claude |
| 9.0 | 2026-04-27 | Phase 9 added to plan - framework extensions; 9.1 multi-timeframe strategy support (driven by chasulang_ict_smc dormancy under single-TF contract) | Claude |
| 9.2 | 2026-04-27 | Phase 9.2 added to plan - baseline indicator strategies (RSI 4h, RSI 15m, Bollinger Bands, MA crossover) for LLM-vs-deterministic comparison + degraded-mode safety net | Claude |
| 9.2 | 2026-04-27 | Phase 9.2 complete - Baseline Indicator Strategies (FR-001/002/003/004); src/strategy/indicators.py + strategies/{rsi,bollinger_bands,ma_crossover}.py + docs/baselines.md; 30 tests. Per-timeframe RSI split (rsi_4h/rsi_15m) deferred until Phase 9.1 multi-TF lands | Claude |
| 9.1 | 2026-04-27 | Phase 9.1 complete - Multi-Timeframe Strategy Support (FR-001/002/003); `requires_multi_timeframe` flag on `TechniqueInfo`, `BaseStrategy.analyze` extended with keyword-only `ohlcv_by_timeframe` / `current_price`, `PromptStrategy.format_prompt` fills `{ohlcv_<tf>}` + `{current_price}`, `ProposalEngine` dispatches per-TF fetches; `chasulang_ict_smc` template wakes up. 7 new tests + chasulang smoke. Backtester multi-TF iteration deferred to a follow-up. | Claude |
| 9.3 | 2026-04-27 | Phase 9.3 complete - Multi-Timeframe Backtester (FR-025, FR-027, FR-034); `Backtester.run_multi_timeframe` with bisect-based per-TF slicing + warmup gating across every TF; `Backtester.run_for_strategy` dispatcher; `RobustnessGate` threads `ohlcv_by_timeframe` through OOS / walk-forward / sensitivity gates with no future leakage; `FeedbackLoop` accepts `ohlcv_by_timeframe` end-to-end. 15 new tests across backtester / validator / loop suites. Multi-TF strategies (chasulang) can now reach AWAITING_APPROVAL. | Claude |
| 9.4 | 2026-04-27 | Phase 9.4 complete - Per-Timeframe RSI Baselines (FR-001/002/003/004); strategies/rsi_4h.py + rsi_15m.py reuse RSIMeanReversionStrategy with locked timeframes; rsi.py renamed `rsi_mean_reversion` → `rsi_universal` for symmetry; 6 new tests + docs/baselines.md updated. Closes the user's original "4시간봉 RSI / 15분봉 RSI" request. | Claude |
| 10.0 | 2026-04-27 | Phase 10 added to plan - Operational Maturation; 10.1 Live Trading Wiring, 10.2 EngineConfig Env Override, 10.3 Baseline Reference Numbers, 10.4 Log Retention Policy. Closes accumulated operational gaps from prior-phase session logs. | Claude |
| 10.1 | 2026-04-28 | Phase 10.1 complete - Live Trading Wiring (FR-009, FR-010, NFR-012); introduced `src/trading/base.py::Trader` Protocol; `PaperTrader` open/close converted to async; `LiveTrader` aligned to the protocol (close signature, get_open_trades, check_exit_conditions, SL/TP-skips-confirm); `TradingEngine.trader: Trader` (replaces `paper_trader`); `src/main.py::build_exchange` + `build_trader` dispatch on `Settings.trading_mode`; engine auto-confirmation shim for headless live; `docs/deployment.md` 9-step live checklist. 11 new tests + extensive test churn (~50 PaperTrader call sites converted to async). 1027 total passing. | Claude |
| 10.5 | 2026-04-28 | Phase 10.5 complete - Volume-Aware Default Paths (NFR-008); replicated `PerformanceTracker` / `TradeHistoryTracker` `data_dir` pattern across `ActivityLog`, `AuditLog`, `FeedbackLoop`, `ProposalHistory`, `FileNotifier`, and `Portfolio` (latter already correct, comment added); each `__init__` now accepts a keyword-only `data_dir: Path \| None = None` and derives default storage from `Settings.data_dir` at construction time. Closes the Fly persistence-loss defect Cycle 1 diagnosed: relative `Path("data/...")` defaults resolved to ephemeral `/app/data/...` instead of the `/data` volume mount. 6 new "respects `Settings.data_dir`" tests (1027 → 1033). | Claude |
| 10.6 | 2026-04-28 | Phase 10.6 complete - Multi-Technique Per-Symbol Scan (FR-005, FR-012); `ProposalEngine` now iterates every applicable technique per symbol via sibling `_select_all_techniques` / `_propose_all_for_symbol`; `_dedup_by_symbol` keeps the highest-composite winner per symbol (long+long and long+short conflicts both resolved by symbol-only key); `propose_altcoins` aggregation order is dedup-first-then-top-K to preserve FR-012 diversification; new `multi_technique_per_symbol: bool = True` flag on `ProposalEngineConfig` for backwards-compatible opt-out (legacy `_select_best_technique` kept as live code for op-emergency rollback). Closes the single-strategy lockout Cycle 1 diagnosed: only `bollinger_band_reversion` ever ran on Fly. 7 new tests (1033 → 1040). Quant design-phase review caught 2 🔴 blockers before code was written. | Claude |
| 10.2 | 2026-04-28 | Phase 10.2 complete - EngineConfig Env Override (NFR-004); `Settings.engine_*` fields (`engine_cycle_interval`, `engine_auto_approve_threshold`, `engine_symbols`, `engine_balance`) drive `EngineConfig` in `build_engine`. Defaults bytewise-equal to the pre-10.2 hardcoded values so existing deployments are unchanged without an env setting. `engine_symbols` uses `Annotated[list[str], NoDecode]` + `field_validator(mode="before")` for comma-separated env parsing (operationally natural over JSON literals). `build_engine` explicit-config-wins back-compat preserved. `.env.example` and `docs/deployment.md` updated. 12 new tests (1040 → 1052). 4 remaining `EngineConfig` fields (`monitor_interval_seconds`, `bitcoin_symbol`, `altcoin_top_k`, `actor`) deferred as DEBT-003 (Low). | Claude |
| 10.3 | 2026-04-28 | Phase 10.3 complete - Baseline Reference Numbers (FR-025 consumed; operator tooling); `scripts/backtest_baselines.py` (620 lines) operator script fetches Binance public OHLCV with pagination (>1500 candles needs reaching past `BaseExchange.get_ohlcv` contract via `BinanceExchange._client`), runs `Backtester.run_for_strategy` + `PerformanceAnalyzer` per baseline, persists `result.json` + `analysis.md` + `summary.json` under `data/backtest/baselines/<strategy>/`. Idempotent overwrite. `--no-update-doc` flag. Updates `docs/baselines.md` operator-instructions section + period labels; metric cells stay `_TBD_` until operator runs the script (no synthesised numbers). 6 new smoke tests (1052 → 1058). 1 mypy nit at lines 241/248 + `_client` reach-around recorded as DEBT-004 (Low). | Claude |
| 10.4 | 2026-04-28 | Phase 10.4 complete - Log Retention Policy (NFR-008); new `src/runtime/jsonl_rotator.py` (`JsonlRotator`) wraps append-only JSONL with time-based monthly rotation (`<base>.YYYY-MM.jsonl`) + retention-bounded timestamp-ordered merged reads + corrupt-line tolerance + legacy un-rotated file read-as-oldest-archive (never written). `AuditLog` and `ActivityLog` compose the rotator (`self.path` preserved as `.jsonl`-form for back-compat; trailing-suffix stripped to derive rotator base). `ProposalHistory.purge_old(now, retention_months)` ships as operator-callable age-based archive into `<data_dir>/proposals/archive/<YYYY-MM>/` keyed on the proposal's own creation month — idempotent, no startup hook (deferred). `Settings.log_retention_months: int = 12` (`Field(ge=1)`) + `LOG_RETENTION_MONTHS` env var documented in `.env.example`. 25 new tests (1058 → 1083). No new debt. | Claude |
| 11.1 | 2026-04-28 | Phase 11.1 complete - Pre-Existing Lint/Type Sweep (NFR-001; resolves DEBT-001); cleared all in-scope ruff + mypy errors (18 ruff → 0; 12 in-scope mypy → 0; total mypy 39 → 29 with remainder out-of-scope per spec). In-scope fixes: `src/ai/claude.py` (2 B904 with `from e`), `src/strategy/loader.py` (5 B904), `src/strategy/factory.py` (UP035 `Callable` from `collections.abc`), `src/ai/improver.py` (str-coerce `fm.get(...) or fallback` at parse-time), `src/trading/live.py` (`Order` import + return-type widening + `Literal["buy","sell"]` for closing_side), `src/trading/paper.py` (same Literal fix), `src/backtest/analyzer.py` (`float(...)` cast for no-any-return), 6 test files (F401/F841/I001 cleanup via `ruff --fix`). `pyproject.toml` ruff config migrated from deprecated top-level `select`/`ignore` to `[tool.ruff.lint]`. `types-PyYAML>=6.0` added to dev extras. New `scripts/lint.sh` (uses `--fix` — flagged by qa as unsafe for CI; recorded as DEBT-009). 1083 tests pass (no behaviour change, no new tests). Zero `# noqa` / `# type: ignore` added. Remaining 29 mypy errors clustered in 4 modules (binance / factory / dashboard / main lambda) recorded as DEBT-005 / 006 / 007 / 008. | Claude |
| 11.2 | 2026-04-28 | Phase 11.2 complete - OHLCV Cache for Multi-Technique Scan (FR-005 consumed; resolves DEBT-002); per-call OHLCV cache keyed by `(symbol, tf)` threaded through `propose_bitcoin` / `propose_altcoins` → `_propose_for_symbol` / `_propose_all_for_symbol` → `_build_proposal_for_strategy` (Option A). Local dict per call, no module/class state. Both single-TF and multi-TF branches use it; legacy `_select_best_technique` path also threads cache for consistency (no per-path divergence). Fetch counts verified: 3 sym × 4 tech 12 → 3, multi-TF (2 strategies sharing 3 TFs) 6 → 3, sequential 2× `propose_bitcoin` 2 (no leak), legacy 3 sym × 1 tech 3 (no regression). 4 new tests in `tests/test_proposal_engine_multi_technique.py` (1083 → 1087). ruff clean; mypy zero new errors on `engine.py`. 23 existing `test_proposal_engine.py` tests pass unchanged. PEP 604 union syntax for type hints. No new debt. | Claude |
| 10.0 | 2026-04-28 | Phase 10 complete - all sub-tasks (10.1, 10.2, 10.3, 10.4, 10.5, 10.6) checked. Phase 10 cross-check: `docs/cross-checks/2026-04-28-phase-10-operational-maturation.md`. | Claude |
| 11.3 | 2026-04-28 | Phase 11.3 complete - Notification Push Backend (FR-015, NFR-012); `SlackNotifier` in `src/proposal/notification.py` posts to incoming webhook via `urllib.request.urlopen` + `asyncio.to_thread` (no new dep) implementing the existing `Notifier` protocol. `Settings.slack_webhook_url: Optional[str] = None` (non-breaking; notifier silent / not registered when unset). `src/main.py::build_engine` appends `SlackNotifier()` to the dispatcher's notifier list when URL set; logs presence not URL. Payload: `text` line summary `{symbol} {side} score={c:.2f} entry={p}` + 2 mrkdwn blocks (bolded summary + code-fenced detail w/ proposal_id, technique, SL, TP, qty, leverage, rr). `__repr__` redacts URL. `send` deliberately does NOT swallow `HTTPError` — dispatcher's existing try/except handles failure isolation per Phase 6.3 contract. `.env.example` + `docs/deployment.md` document `SLACK_WEBHOOK_URL` + incoming-webhook setup. 9 new tests across 2 test files (1087 → 1096) — incl. exact-string spec match, failure-isolation, build_engine both-branches, `__repr__` redaction. ruff clean; mypy zero new errors (14 mypy errors all pre-existing in untouched modules per 11.1 carry). No new debt. | Claude |
| 11.4 | 2026-04-28 | Phase 11.4 complete - ProposalHistory.purge_old Wiring (NFR-008); `src/main.py::_purge_old_proposals` helper (extracted for testability) called from `run()` between `build_engine` and signal-handler installation; logs INFO only when records were archived (silent on empty so daily restarts don't generate noise). New `src/tools/purge_proposals.py` operator CLI with `argparse --retention-months` override; reads `Settings`; prints informative summary on both "purged N" and "nothing to purge" branches; exit 0 in both. New `src/tools/__init__.py` package marker (operator tooling that imports only project code lives under `src/tools/`; `scripts/` reserved for tools that talk to external services). `docs/deployment.md` got a new "Operator Tools" section. 8 new tests (1096 → 1104) — `TestPurgeOldProposalsHook` (4: forwarding / count / silent-on-empty `caplog` / build-engine→hook smoke against real `ProposalHistory`) + `tests/test_tools_purge_proposals.py` (4: Settings-default / flag override / end-to-end Jan-2024-archives-fresh-stays / empty-print). ruff clean; mypy zero new errors (DEBT-008 lambda error shifted line 232 → 271, same code). No new debt. | Claude |
| 11.0 | 2026-04-28 | Phase 11 complete - all sub-tasks (11.1, 11.2, 11.3, 11.4) checked. Phase 11 cross-check: `docs/cross-checks/2026-04-28-phase-11-operational-hardening.md`. | Claude |
| 12.1 | 2026-04-28 | Phase 12.1 complete - Cross-Cycle Position Cap (FR-006, FR-007, FR-008; REAL-MONEY risk closure); `EngineConfig.max_open_positions_per_symbol: int = Field(default=1, ge=1)` env-overridable as `ENGINE_MAX_OPEN_POSITIONS_PER_SYMBOL` via `Settings.engine_max_open_positions_per_symbol` (Phase 10.2 pattern). `TradingEngine._handle_proposal` checks `trader.get_open_trades()` filtered by symbol *after* the composite-accept gate; on count ≥ cap increments `proposals_rejected`, logs `PROPOSAL_REJECTED` with reason `"symbol X cap N reached (M open)"` + structured `cap` / `open_count` event details, skips `_execute`. Phase 10.6 within-cycle dedup untouched (orthogonal: within-cycle vs across-cycle). Backward-compatible: cap=1 = pre-12.1 effective behaviour. Closes the 2026-04-28 Fly redeploy real-money concern (two BNB shorts in 14 min — 4× cycle = 4× position concentration). 5 new tests in `tests/test_runtime_engine.py` (default value / env wiring / cap-hit rejection / cap-not-reached execution / other-symbol-doesn't-block). 1104 → 1109 tests. ruff clean; mypy zero new errors (14 pre-existing in entry-point chain land in 12.2). One test gap recorded as DEBT-010 (Low): long+short same-symbol — implementation correct (counts both sides, prevents synthetic hedge) but suite doesn't explicitly cover. | Claude |
| 12.2 | 2026-04-28 | Phase 12.2 complete - Residual mypy Sweep (NFR-001; resolves DEBT-005 / 006 / 007 / 008); `mypy src` 29 errors → 0 across 53 source files. DEBT-005 (binance.py, 11 errors): hand-rolled `CCXTClient` Protocol covering the 10 ccxt methods used (`load_markets`, `close`, `fetch_ohlcv`, `fetch_ticker`, `fetch_balance`, `create_market_order`, `create_limit_order`, `cancel_order`, `fetch_order`, `fetch_open_orders`); `_client` typed `CCXTClient \| None`. DEBT-006 (factory.py, 3 errors): investigated — NOT a behavioural mismatch; registry's `type[BaseExchange]` widens away subclass `__init__` params; resolved with tightly-scoped `cast(Any, exchange_class)(...)` + comment explaining the typing gap (runtime preserves exact call shape). DEBT-007 (dashboard cluster, 13 errors across `theme.py`, `app.py`, `pages/trading.py`, `pages/engine.py`): `Literal` types for theme constants (verified against streamlit `commands/page_config.py`), `StreamlitPage` import for navigation, `cast(...)` on `st.metric` numeric values. DEBT-008 (main.py lambda, 1 error): targeted `# type: ignore[misc]` (canonical case for asyncio signal-handler callback shape mismatch). 1109 tests pass (no behaviour change, no new tests — refactor not a feature). 8 files modified. Public API preserved. QA-flagged follow-up (TypedDict for `build_summary_metrics` to drop consumer-side casts) recorded as DEBT-011 (Low). | Claude |
| 12.3 | 2026-04-28 | Phase 12.3 complete - LLM Strategy Timeout Handling (FR-022; operational reliability — closes the 2026-04-28 Fly `chasulang_ict_smc` 120s-timeout silent-drop-out concern); retry-on-timeout with 1.5× backoff for the Claude CLI in `src/ai/claude.py` (120 → 180 → 270 escalation; retry only on `asyncio.TimeoutError` — verified via `test_non_timeout_errors_do_not_trigger_retry`, `mock_exec.call_count == 1`; per-attempt process cleanup, no zombie risk). `ClaudeTimeoutError` now multiply-inherits `ClaudeError + StrategyError` (MRO `[ClaudeTimeoutError, ClaudeError, StrategyError, Exception, ...]`) so the engine's existing `StrategyError` catch handles it without a new except block at every call site. `PromptStrategy.analyze` re-raises `ClaudeTimeoutError` UNWRAPPED (other `ClaudeError` subtypes still wrap into `StrategyError(...)` per pre-existing contract) so the engine emits `LLM_TIMEOUT` with original `timeout_seconds` payload intact — locked by `test_unwrap_propagation`. `Settings.claude_cli_timeout_seconds: int = Field(default=120, ge=10)` + `claude_cli_max_retries: int = Field(default=1, ge=0)` (0 = single shot). `ActivityEventType.LLM_TIMEOUT` added; `ProposalEngine` accepts optional `activity_log` (None default — backward-compat preserved) and emits `LLM_TIMEOUT` with `strategy_name`/`version`/`symbol`/`timeout_seconds` on final exhaustion. `build_engine` creates one `ActivityLog` and shares it between `ProposalEngine` and `TradingEngine`. 12 files modified (src/ai/claude.py, src/ai/exceptions.py, src/strategy/loader.py, src/proposal/engine.py, src/runtime/activity_log.py, src/config.py, src/main.py, .env.example, docs/development-plan.md, plus 3 test files). 1109 → 1119 tests (+10 — 6 retry tests + 3 LLM_TIMEOUT event tests + 1 unwrap-propagation test). ruff/mypy clean. No new debt. | Claude |
| 12.4 | 2026-04-28 | Phase 12.4 complete - Telegram Notification Backend (FR-015, NFR-012; second push backend so live mode isn't single-channel — closes Phase 11 cross-check carry-forward); `TelegramNotifier` in `src/proposal/notification.py` POSTs form-encoded `chat_id` + `text` + `parse_mode=Markdown` to `https://api.telegram.org/bot<TOKEN>/sendMessage` via stdlib `urllib.request.urlopen` + `asyncio.to_thread` (zero new dep — mirrors Slack's Phase 11.3 pattern exactly). `Settings.telegram_bot_token: str \| None = Field(default=None)` + `telegram_chat_id: str \| None = Field(default=None)` (non-breaking; both required for activation). `src/main.py::build_engine` appends `TelegramNotifier(...)` to the dispatcher's notifier list when both env vars set; logs presence only. Activation gate `bool(token and chat_id)` — partial config (token-only, chat-id-only, neither) silent in all three (locked by `test_telegram_notifier_silent_when_either_missing`). Message format collapses Slack's two-block payload into one Markdown string (bolded headline + code-fenced detail) so on-the-wire content of Slack and Telegram alerts stays in sync. `__repr__` masks BOTH token AND chat id (chat id treated as a secret since it identifies the operator's destination channel — tighter contract than Slack's URL-only redaction). `send` does not catch `HTTPError` — dispatcher's existing per-channel failure-isolation contract (Phase 6.3) handles it. `.env.example` + `docs/deployment.md` document `TELEGRAM_BOT_TOKEN` (secret) + `TELEGRAM_CHAT_ID`. 8 files modified (src/proposal/notification.py, src/config.py, src/main.py, .env.example, docs/deployment.md, docs/development-plan.md, plus 2 test files). 1119 → 1127 tests (+8 — 6 in test_proposal_notification.py + 2 in test_main_dispatch.py). ruff/mypy clean. No new debt. | Claude |
| 12.0 | 2026-04-28 | Phase 12 complete - all sub-tasks (12.1, 12.2, 12.3, 12.4) checked. Phase 12 cross-check: `docs/cross-checks/2026-04-28-phase-12-risk-hardening.md`. | Claude |
| 13.1 | 2026-04-28 | Phase 13.1 complete - Cleanup Batch (NFR-001; resolves DEBT-009 / DEBT-010 / DEBT-011); DEBT-009 split `scripts/lint.sh` (no `--fix` — CI / pre-commit safe) + new `scripts/lint-fix.sh` (with `--fix` — dev convenience), both executable. DEBT-010 added `test_cap_blocks_opposite_side_same_symbol` to `tests/test_runtime_engine.py` (1 BNB long open + BNB short proposal at composite=2.0; cap=1 → positions_opened=0, no open_position call, PROPOSAL_REJECTED with BNB + "cap 1 reached") — pins the synthetic-hedge prevention invariant against future regression. DEBT-011 replaced `dict[str, object]` returns with per-page TypedDicts (`TradingSummaryMetrics` in `src/dashboard/pages/trading.py`, `EngineSummaryMetrics` in `src/dashboard/pages/engine.py`) since shapes differ; consumer-side `cast(...)` calls dropped at every access site; no leftover `from typing import cast` in either file. Refactor only — no behavioural change for DEBT-009 / DEBT-011; DEBT-010 adds the single new test. 5 files modified (scripts/lint.sh, scripts/lint-fix.sh, tests/test_runtime_engine.py, src/dashboard/pages/trading.py, src/dashboard/pages/engine.py) plus dev plan. 1127 → 1128 tests (+1 cap test). ruff/mypy clean (53 files). No new debt. | Claude |
| 13.2 | 2026-04-28 | Phase 13.2 complete - EngineConfig Remaining-Fields Env Override (NFR-004; resolves DEBT-003); third application of the Phase 10.2 pattern (10.2 first, 12.1 second). 4 new `Settings.engine_*` fields in `src/config.py` — `engine_monitor_interval: int = Field(default=60, ge=10)` (env `ENGINE_MONITOR_INTERVAL`), `engine_bitcoin_symbol: str = Field(default="BTC/USDT")` (env `ENGINE_BITCOIN_SYMBOL`), `engine_altcoin_top_k: int = Field(default=3, ge=1)` (env `ENGINE_ALTCOIN_TOP_K`), `engine_actor: str = Field(default="auto-engine")` (env `ENGINE_ACTOR`). `ge=` validators mirror `EngineConfig`'s own floors so env input gets the same validation as direct construction. `src/main.py::build_engine` constructs `EngineConfig(...)` with the 4 new fields alongside the existing 4 (10.2 explicit-config-wins back-compat preserved); docstring rewritten to drop the "not yet env-overridable" note. Defaults bytewise-match `EngineConfig` so existing deployments are unchanged without an env setting; parity locked by `test_settings_defaults_match_engine_config`. `.env.example` + `docs/deployment.md` document every new env var with operator-facing prose. Tests: 4 new methods in `tests/test_config.py::TestEngineSettings` (default + env override + `ge=` validators where applicable), 4 new parity assertions in the existing default-match test, 1 new end-to-end smoke test in `tests/test_main_dispatch.py` (`test_build_engine_propagates_all_engine_env_overrides`). 7 files modified (src/config.py, src/main.py, .env.example, docs/deployment.md, tests/test_config.py, tests/test_main_dispatch.py, plus dev plan). 1128 → 1134 tests (+6). ruff/mypy clean (53 files). No new debt. | Claude |
| 13.3 | 2026-04-28 | Phase 13.3 complete - BaseExchange.get_ohlcv `since` Parameter (FR-020 extended; resolves DEBT-004); `BaseExchange.get_ohlcv` ABC now declares `since: int | None = None` (timestamp ms, inclusive on start; None = pre-13.3 most-recent-page semantics). `BinanceExchange.get_ohlcv` and `BybitExchange.get_ohlcv` forward `since` to `ccxt.fetch_ohlcv(since=...)`; both adapters preserve default behaviour bytewise — locked by `test_get_ohlcv_defaults_since_to_none` for each. `scripts/backtest_baselines.py::fetch_ohlcv_window` switched from `exchange._client.fetch_ohlcv(...)` to `exchange.get_ohlcv(..., since=...)` end-to-end; the `_client` reach-around block + the `RuntimeError` it gated + the local `Decimal` import + the bottom-of-function raw-row → `OHLCV` reconstructor are all deleted (real adapter already returns `OHLCV`). The "deliberately reach past the BaseExchange contract" comment removed. `MockExchange` (`tests/test_exchange_base.py`) and `_FakeBinanceExchange` (`tests/test_scripts_backtest_baselines.py`) grew the new `since` parameter for ABC parity; the latter absorbs the pagination-cursor logic that previously lived in the deleted `_FakeCCXTClient`. 9 files modified (src/exchange/base.py, src/exchange/binance.py, src/exchange/bybit.py, scripts/backtest_baselines.py, tests/test_exchange_base.py, tests/test_exchange_binance.py, tests/test_exchange_bybit.py, tests/test_scripts_backtest_baselines.py, plus dev plan). 1134 → 1138 tests (+4 — 2 per adapter: default-None forwarding + explicit-since forwarding). ruff/mypy clean (53 files). No new debt. | Claude |
| 13.4 | 2026-04-28 | Phase 13.4 complete - Email Notification Backend (FR-015, NFR-012; third push backend so live-mode notification redundancy spans webhook + chat + SMTP failure modes). `EmailNotifier` in `src/proposal/notification.py` uses stdlib `smtplib.SMTP` + `email.message.EmailMessage` wrapped in `asyncio.to_thread` (zero new dep — mirrors Slack/Telegram pattern); STARTTLS-only handshake (port 587 default), SMTP_SSL deferred as DEBT-012 (Low). Subject format: `"Crypto Master: {symbol} {side} score={c:.2f}"`. Body reuses `_build_telegram_text` via thin `_build_email_body` helper so all three push backends carry identical content (locked by `test_build_email_body_matches_telegram_text`). 6 SMTP `Settings` fields in `src/config.py`: `email_smtp_host` / `email_smtp_user` / `email_smtp_password` / `email_from` / `email_to` (all `str \| None`, default None) + `email_smtp_port: int = Field(default=587, ge=1, le=65535)`; activation gate is the 5 string fields (port has default so it can't fail `all([...])` — note dev-plan-text "all 6" is loose vs the 5-string code gate; code is correct). `EmailNotifier.__repr__` masks password unconditionally; host/user/from/to remain visible (operationally useful for log triage, not secrets in the same sense). `send` does NOT swallow `smtplib` errors — Phase 6.3 dispatcher's per-channel failure-isolation contract is the single owner. `src/main.py::build_engine` appends `EmailNotifier(...)` when 5 string fields set; logs presence only. `.env.example` + `docs/deployment.md` document the SMTP quintet. Configurable `timeout: float = 10.0` so a slow server can't stall the cycle. 8 files modified (src/proposal/notification.py, src/config.py, src/main.py, .env.example, docs/deployment.md, docs/development-plan.md, plus 2 test files). 1138 → 1149 tests (+11 — 9 in test_proposal_notification.py: subject format / body parity / end-to-end via `_FakeSMTP` / repr masks password / STARTTLS called / login called / SMTP error doesn't crash dispatch / password not in logs / configured timeout reaches `smtplib.SMTP`; 2 in test_main_dispatch.py: created when env set + silent across 6 partial scenarios). ruff/mypy clean (53 files). One new debt: DEBT-012 SMTP_SSL alternative (Low). | Claude |
| 13.0 | 2026-04-28 | Phase 13 complete - all sub-tasks (13.1, 13.2, 13.3, 13.4) checked. Phase 13 cross-check: `docs/cross-checks/2026-04-28-phase-13-cleanup-polish.md`. | Claude |
| 14.1 | 2026-04-28 | Phase 14.1 complete - Chasulang Timeout Mitigation (FR-022 extended, NFR-001; closes prod-observed `chasulang_ict_smc` 120s timeouts that Phase 12.3's retry didn't eliminate — Fly logs confirmed retry path was firing but 180s still timing out, so per-strategy 240s override is the right fix). `TechniqueInfo` gains `claude_timeout_seconds: int \| None = Field(default=None, ge=1)` in `src/strategy/base.py` — `None` keeps existing strategies on `Settings.claude_cli_timeout_seconds`, integer overrides go straight to `ClaudeCLI`; `ge=1` rejects zero at load time as a config bug. `PromptStrategy.analyze` (`src/strategy/loader.py`) reads `self.info.claude_timeout_seconds`; when set constructs `ClaudeCLI(timeout=float(override))`, when `None` constructs `ClaudeCLI()` so the wrapper resolves Settings lazily. `strategies/chasulang_ict_smc.md` frontmatter gains `claude_timeout_seconds: 240` (240 × 1.5 = 360s worst case with one retry, comfortably above the observed timeout floor on Fly's shared-CPU/1GB machine). `ClaudeTimeoutError` (`src/ai/exceptions.py`) grows `attempt_number: int = 1` on `__init__` (default preserves Phase 12.3 single-shot semantics for unmigrated callers); `_execute_cli_once` (`src/ai/claude.py`) accepts the kwarg and stamps it onto raised errors, while the retry loop forwards `attempt + 1` so the surfacing error carries the final attempt's index. `_log_llm_timeout` (`src/proposal/engine.py`) extends the `LLM_TIMEOUT` event payload with `attempt_number` (from `error.attempt_number`) and `final_timeout_seconds` (alias of `error.timeout_seconds`, intent-revealing for the dashboard) so operators can distinguish "first attempt fails, retry didn't fire" (wiring bug) from "every attempt timed out" (leash too short); legacy `timeout_seconds` key preserved for back-compat. 11 files modified (src/ai/exceptions.py, src/ai/claude.py, src/strategy/base.py, src/strategy/loader.py, src/proposal/engine.py, strategies/chasulang_ict_smc.md, plus 5 test files and dev plan). 1153 → 1158 tests (+5 net new — 2 in test_ai_claude.py covering attempt_number through retry loop, 2 in test_ai_exceptions.py for the new field, 2 in test_strategy_base.py for the schema field + ge=1 rejection, 2 in test_strategy_loader.py pinning `ClaudeCLI(timeout=240.0)` vs `ClaudeCLI()`, 1 in test_proposal_engine.py for the `LLM_TIMEOUT` payload). ruff/mypy clean (53 files). No new debt. No ADR — extends existing per-strategy frontmatter pattern. | Claude |
| 14.2 | 2026-04-28 | Phase 14.2 complete - SMTP_SSL Alternative (FR-015 extended, NFR-001; resolves DEBT-012 — Phase 13.4 carry). `Settings.email_use_ssl: bool = Field(default=False)` in `src/config.py` (env `EMAIL_USE_SSL=true` activates the SMTP_SSL path; default `False` keeps the Phase 13.4 STARTTLS path bytewise unchanged for every existing deployment — strict back-compat). `EmailNotifier.__init__` (`src/proposal/notification.py`) accepts keyword-only `use_ssl: bool = False` stored as `self._use_ssl`; class docstring expanded to describe both transports (STARTTLS default for Gmail / Mailgun / SendGrid / corporate; SMTP_SSL for Yahoo Mail / AT&T / ProtonMail). Inner `_send` closure branches at send-time: `use_ssl=True` → `smtplib.SMTP_SSL(host, port, timeout=...)` with NO `starttls()` call (channel already encrypted on connect); `use_ssl=False` → existing `smtplib.SMTP(host, port, timeout=...)` + `starttls()`. `with smtp:` socket cleanup, `login`, `send_message` shared by both paths. `src/main.py::build_engine` reads `settings.email_use_ssl` and forwards to `EmailNotifier(use_ssl=...)`. `.env.example` + `docs/deployment.md` document `EMAIL_USE_SSL` with the Yahoo / AT&T / ProtonMail pairing guidance (`EMAIL_USE_SSL=true` + `EMAIL_SMTP_PORT=465`); deployment doc adds a `fly secrets set` example for Yahoo. 7 files modified (src/config.py, src/proposal/notification.py, src/main.py, .env.example, docs/deployment.md, tests/test_proposal_notification.py, plus dev plan). 1158 → 1160 tests (+2 net new — `test_email_notifier_uses_smtp_ssl_when_flag_set` and `test_email_notifier_uses_starttls_when_flag_unset`, each with cross-protection: patches BOTH constructors, raises on the wrong one so a regression where both branches accidentally call the same constructor fails loudly rather than silently passing). ruff/mypy clean (53 files). No new debt. No ADR — extends Phase 13.4's `EmailNotifier` with one config branch; `Notifier` protocol and dispatcher failure-isolation contract unchanged. | Claude |
| 14.0 | 2026-04-28 | Phase 14 complete - all sub-tasks (14.1, 14.2) checked. Phase 14 cross-check: `docs/cross-checks/2026-04-28-phase-14-production-reliability.md`. | Claude |
| 15.1 | 2026-04-28 | Phase 15.1 complete - Diagnostic Clarity (NFR-001; closes the 2026-04-28 misdiagnosis where 139 rejected proposals read as "0 trades, must be a bug" instead of "threshold gate working as designed"). Two surgical changes. (1) `src/trading/strategy.py:474` log verb rename: `"Created position: ..."` → `"Sized position candidate: ..."` so the proposal-sizing emit can't be misread as a trade-execution event in `fly logs` greps; same fields and verbosity, only the verb changes. The `PaperTrader.open_position` "Opened paper position" log (`src/trading/paper.py:546`) stays unchanged so the two events are clearly distinct. (2) `src/dashboard/pages/trading.py` extends `TradingSummaryMetrics` (Phase 13.1 TypedDict) with `proposals_rejected_threshold_count: int`; `build_summary_metrics` accepts an optional `proposal_history: ProposalHistory \| None = None` (defaults to `ProposalHistory()` so existing callers don't need to wire it up — backward-compat) and counts records where `decision == "rejected"` and `rejection_reason` matches `^composite \d+\.\d+ below threshold \d+\.\d+$` (the exact format from `RuntimeEngine._auto_decide` at `src/runtime/engine.py:586`); cap-rejected records (Phase 12.1, reason starts with `"symbol "`) are excluded so the metric stays interpretable. New helper `_count_threshold_rejections` wraps `history.list_all()` in `try/except` so a malformed proposals dir warns + returns 0 rather than crashing the page render. Render layout: `st.columns([3, 1])` next to "Active Positions" so an operator seeing 0 active positions immediately sees how many proposals were rejected and why. `render(...)` accepts `proposal_history=` for test injection; defaults to `ProposalHistory()`. 4 files modified (src/trading/strategy.py, src/dashboard/pages/trading.py, tests/test_dashboard_trading.py, plus dev plan). 1160 → 1162 tests (+2 net new — `test_summary_metrics_counts_threshold_rejections` seeds 4 records (accepted / threshold-rejected / cap-rejected / no-reason) and asserts the count surfaces only the threshold-rejected one; `test_summary_metrics_handles_empty_proposal_history` pins backward-compat for an absent proposals dir). Existing `test_summary_metrics_empty_inputs` extended with a `tmp_path: Path` fixture and the new field assertion. AppTest smoke tests updated to inject `ProposalHistory(data_dir=...)` and assert the metric card renders with value `"0"`. ruff/mypy clean. No new debt. No ADR — log-string rename + one new dashboard field is mechanical clarity, not a component-shape decision. | Claude |
| 16.1 | 2026-04-29 | Phase 16.1 complete - chasulang Parse + Wedge Mitigation (FR-022 extended, NFR-001; closes two prod-observed defects from the 2026-04-28 redeploy: (a) every chasulang Claude response failed with `KeyError: 'signal'` because chasulang_ict_smc.md returns the trade nested under `trade.*` rather than flat top-level, and (b) at `2026-04-28T15:02:15Z` a chasulang retry timed out at 360s and the engine wedged silent for 12+ hours, the prior `asyncio.create_subprocess_exec` + `asyncio.wait_for` path failing to actually kill the child). `src/ai/claude.py::_parse_response` now calls a new `_normalize_trade_fields` helper after JSON extraction; helper promotes nested `trade.*` keys (`signal`, `entry_price`, `stop_loss`, `take_profit`, `confidence`, `reasoning`) to top level when present (non-destructive — original `trade` sub-dict preserved in returned result for callers wanting full nested view, e.g. `take_profit_2`). Take-profit precedence: explicit `trade.take_profit` > `trade.take_profit_1` > nothing — TP1 is the conservative target, deliberately picked over TP2 stretch. When neither top-level nor `trade.signal` carries a signal, raises `ClaudeParseError` with a message naming both candidate paths so operators can spot the failing template fast. `src/ai/claude.py::_execute_cli_once` rebuilt on `subprocess.Popen` run via `asyncio.to_thread` (decades-stable blocking subprocess semantics, event loop unblocked); `proc.communicate(timeout=...)` drives the timeout, `proc.kill()` (SIGKILL — not soft-terminate) + `proc.wait(timeout=5)` on `subprocess.TimeoutExpired` guarantees the child is reaped or surfaces as a distinct error. SIGKILL-itself-fails branch raises a distinct `ClaudeTimeoutError` ("did not respond to SIGKILL within 5s") so operators can spot zombie / kernel-stuck children in logs; same exception type so the proposal engine's `except StrategyError` path still treats it as a clean per-strategy skip. `ClaudeTimeoutError` continues to carry `attempt_number` per Phase 14.1 contract on both branches. `FileNotFoundError` re-raised unchanged. Test mock surface fully migrated from `asyncio.create_subprocess_exec` / `AsyncMock` to `subprocess.Popen` / `MagicMock(spec=Popen)` — `_make_popen_success` / `_make_popen_timeout` helpers factor the new pattern; `TestClaudeCLIRetryOnTimeout` rewired (timeout-escalation test now captures `proc.communicate(timeout=...)` kwarg instead of patching `asyncio.wait_for`). 3 files modified (src/ai/claude.py, tests/test_ai_claude.py, plus dev plan). 1162 → 1170 tests (+8 net new — 6 `TestParseResponseNestedTradeForm`: chasulang nested-form / top-level back-compat / TP1-over-TP2 / explicit-tp-beats-TP1 / clear-error-names-both-paths / top-level-signal-wins-when-trade-lacks-one; 2 `TestSubprocessKillOnTimeout`: kill-called-once + wait(timeout=5) with attempt_number/timeout_seconds preserved on normal timeout, distinct ClaudeTimeoutError when SIGKILL itself hangs). ruff/mypy clean (53 files). No new debt. No ADR — bug fix to existing component, `ClaudeCLI` public contract unchanged (same `analyze` signature, same exception types, same retry semantics, same `attempt_number` propagation from Phase 14.1). | Claude |
| 16.0 | 2026-04-29 | Phase 16 complete - all sub-tasks (16.1) checked. Phase 16 cross-check: `docs/cross-checks/2026-04-29-phase-16-chasulang-stability.md`. | Claude |
| 17.1 | 2026-04-29 | Phase 17.1 complete - Auto-Research Operator Workflow + Catalog-Aware Improver (FR-023, FR-026, FR-034, CON-003; first end-to-end exercise of the strategy-evolution stack — `StrategyImprover` → `Backtester` → `PerformanceAnalyzer` → `RobustnessGate` → `FeedbackLoop._run_cycle` → `CandidateRecord` — landing every robustness-gate-passing pick in `AWAITING_APPROVAL` for explicit operator approval per CON-003; promotion stays manual). New `scripts/auto_research_candidates.py` operator entry point (`python -m scripts.auto_research_candidates [--picks N] [--dry-run]`) parses the priority matrix's first-wave OHLCV-only Top-N picks from `docs/research/strategies/00-priority-matrix.md`, dispatches each through `improver.generate_idea(context=<pick description>)` → `loop.propose_new(...)`, persists run snapshot to `data/research_runs/run_{ts}.json`, and prints an operator-facing summary with `decision_reason` + `robustness_summary` continuation lines so DISCARDED reasons are visible without opening the JSON. `--dry-run` short-circuits before the loop call and routes generated experimental files under `strategies/experimental/dry_runs/` so they never mix with real gated candidates. `src/ai/improver.py::StrategyImprover.__init__` accepts `catalog_path: Path | None = None` (default `docs/research/strategies/00-priority-matrix.md`); new private `_load_catalog` helper reads the file at most once per improver lifetime, fail-softs on missing path with INFO log + empty string. `_build_new_idea_prompt` injects the cached catalog under a `## Reference Catalog` section. `_build_user_idea_prompt` deliberately omits the catalog (the user has already described their idea — injecting the catalog would redirect Claude away from the user's intent; deviation from original spec wording per quant-trader-expert review Issue 4). `_build_improvement_prompt` also untouched (improvement is failure-mode analysis on an existing strategy, not a fresh-idea exercise). Quant review surfaced 4 in-scope fixes shipped in the dev's commit: per-timeframe candle defaults bumped (1h: 4380, 15m: 8760) so the regime gate sees both bull and bear; summary surfaces `decision_reason` + `robustness_summary` so DISCARDED reasons are terminal-visible; dry-run output routes under `strategies/experimental/dry_runs/`; the user-idea catalog-injection deletion above (Issue 4). 14 files in commit `10bbd7f` (`scripts/auto_research_candidates.py`, `src/ai/improver.py`, `tests/test_ai_improver.py`, `tests/test_scripts_auto_research_candidates.py`, plus the operator-curated catalog under `docs/research/strategies/{00-priority-matrix,01-ict-smc,02-chart-patterns,03-breakout-range,04-mean-reversion,05-trend-indicators,06-crypto-specific,README}.md`, `.gitignore` for `data/research_runs/`, and dev plan). 1170 → 1189 tests (+19 net new — improver gains catalog-injection / catalog-not-in-user-idea / catalog-not-in-improvement / fail-soft-when-absent cases plus existing-test churn for the new `catalog_path` constructor kwarg; new `tests/test_scripts_auto_research_candidates.py` covers happy-path / dry-run / one-pick-raises). ruff/mypy clean (53 source files; `scripts/` not in mypy scope per spec). Two new debt items: DEBT-013 `auto_research_candidates.run_async` constructs its own `FeedbackLoop` / `BinanceExchange` (Low — fine until a second caller materialises; quant Issue 3) and DEBT-014 `loop.propose_new` called without `param_grid` so the sensitivity gate is `SKIPPED` for every Phase 17.1 candidate (Medium — fix needs `Pick`-level parameter-grid declaration or strategy-introspection helper; quant Issue 5; partial-robustness-verdict consequence). One operator action deferred and standing: `flyctl ssh console --app crypto-master -C "python -m scripts.auto_research_candidates --picks 2"` to populate `/data/feedback/state/` + `/data/audit/` end-to-end. No ADR — wires existing components into an operator script + extends one prompt; no new architectural seam. | Claude |
| 17.0 | 2026-04-29 | Phase 17 complete - all sub-tasks (17.1) checked. Phase 17 cross-check: `docs/cross-checks/2026-04-29-phase-17-strategy-evolution-operator.md`. | Claude |
| 18.1 | 2026-04-30 | Phase 18.1 added - Stale-Quote Sanity Gate at Proposal Fill (FR-008, FR-013, NFR-012); driven by 2026-04-30 production review of `/data/trades/paper/trades.json` (1W/8L, EV -8.73/trade) — proposal `6ef8c07e...` filled 3 min 13 sec stale at `entry=2323` then closed `0.48s` later at `2300` because live had already crossed `SL=2305`. | product-planner |
| 18.1 | 2026-04-30 | Phase 18.1 sealed — stale-quote sanity gate shipped, full suite 1198 pass. Sanity gate inserted between auto-approval and `trader.open_position` in `src/runtime/engine.py::_execute` via new `_stale_quote_gate` helper; past-SL check (side-dispatched off `proposal.signal`) + symmetric slippage check (`abs(live - entry)/entry > tolerance`); rejection rewrites `ProposalRecord` to `REJECTED` (load + `model_copy` + save) + emits activity event with `proposal_entry` / `proposal_stop_loss` / `live_price` / `drift_bps`; ticker fetch failure → fall through to fill, log WARN `stale_quote_check_failed`. New `EngineConfig.fill_slippage_tolerance: Decimal = Decimal("0.005")` (50 bps, `Field(ge=0)`) and `EngineConfig.reject_if_past_stop_loss: bool = True`; env overrides `ENGINE_FILL_SLIPPAGE_TOLERANCE` + `ENGINE_REJECT_IF_PAST_STOP_LOSS` via `Settings.engine_*` (Phase 10.2 / 13.2 pattern); `build_engine` wires alongside existing eight fields. Two pre-existing tests (`test_proposal_executes_when_cap_not_reached`, `test_cap_counts_only_matching_symbol`) had inverted-SL fixtures for short proposals that the new gate exposed; dev fixed both fixtures in same diff. 7 files in working-tree diff (not yet committed): src/runtime/engine.py, src/config.py, src/main.py, .env.example, tests/test_runtime_engine.py, tests/test_config.py, docs/development-plan.md. 1193 → 1198 tests (+5 net new in `test_runtime_engine.py`, total 23 → 28). ruff/mypy clean. Quant validated 50-bps default against 1H BTC/ETH expected drift over a 4-min latency window (~26 bps ≈ 2σ at 50 bps); confirmed smoking-gun ETH case caught with 49 bps headroom; flagged `bollinger_band_reversion` will see visible rejection-rate uptick (intended behaviour, not regression). QA verdict: 🟡 Ship with note — four observations recorded as DEBT-015 (Medium — rejection-path semantic divergence vs Phase 12.1) / DEBT-016 (Low — simultaneous-counters contract undocumented) / DEBT-017 (Low / cosmetic — `entry_price` + `proposal_entry` redundancy in event payload) / DEBT-018 (Low — rejection tests don't assert `proposals_accepted == 1`). One operator action standing: Fly redeploy + 24h log monitoring for first `stale_quote_past_sl` / `slippage_exceeds_tolerance` rejection. No ADR — guard inserted into existing seam, `Trader` Protocol unchanged. | docs-auditor |

# Phase 9 Cross-Check: Framework Extensions

**Date**: 2026-04-27
**Phase**: 9 - Framework Extensions
**Status**: All non-deferred sub-tasks complete (9.1, 9.2, 9.3)

## Scope

Phase 9 generalises the strategy framework to support input shapes
the original Phases 3 / 5 contract did not anticipate, and seeds the
strategy library with deterministic baselines that the LLM-driven
techniques can be measured against.

- **9.1 Multi-Timeframe Strategy Support** —
  `BaseStrategy.analyze` now accepts keyword-only
  `ohlcv_by_timeframe: dict[str, list[OHLCV]] | None` and
  `current_price: Decimal | None`. `PromptStrategy.format_prompt`
  fills `{ohlcv_<tf>}` per dict key and `{current_price}` (fixed-point
  Decimal). `TechniqueInfo.requires_multi_timeframe: bool = False`
  is the explicit opt-in flag — the legacy `timeframes` field
  retains its "compatible TFs" meaning for single-TF strategies, so
  RSI / Bollinger / MA crossover / sample_prompt / simple_trend keep
  working unchanged. `ProposalEngine._propose_for_symbol` branches
  on the flag, fetches every declared TF, derives `current_price`
  from the primary (last-listed) TF's last close, and dispatches
  the dict. The dormant `chasulang_ict_smc` template is now
  functional through the live engine path.
- **9.2 Baseline Indicator Strategies** — `src/strategy/indicators.py`
  bundles shared `rsi`, `sma`, `bollinger_bands` math.
  `strategies/rsi.py`, `strategies/bollinger_bands.py`, and
  `strategies/ma_crossover.py` (renamed from `sample_code.py`) are
  registered universal-symbol baselines (`symbols: []`) at
  `status: experimental`. `docs/baselines.md` documents each
  baseline's signal logic + the `Backtester` invocation an operator
  runs to populate metrics.
- **9.3 Multi-Timeframe Backtester** — closed the offline gap left by
  9.1. `Backtester.run_multi_timeframe` walks the primary TF and
  slices higher TFs by timestamp at each step using `bisect` for
  O(N log M) total work; warmup gates every TF (not just primary).
  `Backtester.run_for_strategy` is the unified dispatcher used by
  the gate and the loop. `RobustnessGate` threads
  `ohlcv_by_timeframe` through `evaluate` / `_gate_oos` /
  `_gate_walk_forward` / `_gate_sensitivity` / `_run_subset` using
  the new `slice_multi_tf_by_index` helper — chronological splits
  preserve no-future-leakage. `_gate_regime` unchanged (it only
  reads baseline trades + primary SMA). `FeedbackLoop` accepts the
  dict end-to-end across `improve_existing` / `propose_new` /
  `from_user_idea` / `reevaluate`, so multi-TF candidates can now
  reach `AWAITING_APPROVAL`.

Phase 9 added no new functional or non-functional requirements —
every sub-task generalised an existing requirement's contract. The
Requirements Mapping table in `docs/development-plan.md` lists Phase
9 against FR-001 / FR-002 / FR-003 only. The list below additionally
records which Phase-5 / Phase-6 requirements 9.3 *touches without
introducing*.

## Compliance Matrix

### Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| FR-001 | Bitcoin Chart Analysis | ✅ Complete (extended) | The single-TF contract that powered Phase 3 still works — every existing technique runs unchanged. Multi-TF templates (chasulang) now run too: `tests/test_multi_timeframe_smoke.py::test_chasulang_format_prompt_fills_every_placeholder` loads the real template through `load_strategy` and confirms zero unfilled placeholders. `ProposalEngine._propose_for_symbol` integrates the multi-TF fetch loop verified by `tests/test_proposal_engine.py::test_propose_multi_timeframe_*` (4 tests). |
| FR-002 | Altcoin Chart Analysis | ✅ Complete (extended) | Same dispatch path as FR-001 — the engine treats every symbol uniformly. `propose_altcoins` loops over symbols and reuses `_propose_for_symbol`. Multi-TF strategies declaring `symbols: []` (universal) — like the 9.2 baselines — automatically apply to every USDT pair. |
| FR-003 | Chart Analysis Technique Definition | ✅ Complete (extended) | `BaseStrategy.analyze` signature extension is keyword-only and backward compatible — every prior `BaseStrategy` subclass continues to satisfy the abstract method. `requires_multi_timeframe: bool` is the explicit opt-in. `tests/test_strategy_loader.py::test_format_prompt_substitutes_multi_timeframe_placeholders` and the partial-dict / scientific-notation cases cover the new substitution logic. |
| FR-004 | Analysis Technique Storage/Management | ✅ Complete | The 9.2 baselines added 4 strategy files (3 new + the rename of `sample_code.py` → `ma_crossover.py`). `discover_strategies` and `load_all_strategies` find them with no engine wiring change. Existing tests (`tests/test_strategy_loader.py::TestDiscoverStrategies` and `TestLoadAllStrategies`) cover the discovery contract. |
| FR-025 | Backtesting Execution | ✅ Complete (extended) | 9.3 added `Backtester.run_multi_timeframe` and `Backtester.run_for_strategy`. The 13 tests in `tests/test_backtest_multi_timeframe.py` cover input validation, no-future-leakage, warmup gating, primary-TF derivation, current_price propagation, and the dispatcher's single-TF / multi-TF / missing-dict paths. The 58 prior `tests/test_backtest_engine.py` tests still pass — the single-TF path is untouched. |
| FR-027 | Technique Adoption | ✅ Complete (extended) | `FeedbackLoop` accepts `ohlcv_by_timeframe` end-to-end so a multi-TF candidate (chasulang) can be backtested → gated → reach `AWAITING_APPROVAL`, where the existing `approve()` / `reject()` flow takes over. CON-003 enforcement unchanged — automatic promotion still impossible. `tests/test_feedback_loop.py::test_improve_existing_threads_multi_tf_dict_to_backtester` verifies the dict reaches both the backtester and the gate. |
| FR-034 | Robustness Validation Gate | ✅ Complete (extended) | `RobustnessGate.evaluate` and the OOS / walk-forward / sensitivity gates accept a keyword-only `ohlcv_by_timeframe`. Splits use `slice_multi_tf_by_index` — `tests/test_backtest_validator.py::TestMultiTimeframeRouting::test_oos_gate_does_not_leak_future_higher_tf` asserts no higher-TF candle in any per-step slice has a timestamp past the primary cutoff. `_gate_regime` is correctly left untouched (operates on baseline trades + primary SMA only — higher TFs do not enter the calculation). |

### Non-Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| NFR-005 | Analysis Technique Storage | ✅ Complete (consumed) | The 9.2 baselines all use the existing `.py` storage convention (`TECHNIQUE_INFO` dict + `BaseStrategy` subclass). `chasulang_ict_smc.md` extends with a single new YAML key (`requires_multi_timeframe: true`); existing `.md` parsing accepts arbitrary keys via Pydantic — no schema migration. |
| NFR-010 | Analysis Technique Extensibility | ✅ Complete (extended) | The two extension axes opened in Phase 9 — multi-TF input and indicator-based baselines — both happen *without modifying* any prior strategy's source. New multi-TF strategies just declare `requires_multi_timeframe: true`; new baselines just drop a `.py` file into `strategies/`. The framework code is the only thing that grew. |

### Constraints

| ID | Constraint | Status | Evidence |
|----|------------|--------|----------|
| CON-003 | User approval for technique adoption | ✅ Complete (preserved) | The 9.3 multi-TF wiring routes through the same `FeedbackLoop` `approve()` / `reject()` API. Automatic promotion remains impossible for multi-TF candidates as for single-TF ones. No new automatic-adoption path was introduced. |

## Phase-Adjacent Requirements Touched (No New Coverage Added)

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-005 | Performance Tracking | ✅ Complete (consumed) | `BacktestResult.timeframe` keeps a single-string primary TF — no schema drift. `PerformanceTracker` reads it as before. |
| FR-011 / FR-012 | BTC + altcoin proposals | ✅ Complete (consumed) | Multi-TF dispatch is internal to `ProposalEngine`; both top-level entry points continue to work. The runtime engine (`src/runtime/engine.py`) needed no change because it never passed a timeframe explicitly. |
| FR-026 | Automated Feedback Loop | ✅ Complete (consumed) | The loop's `_run_cycle` now calls `Backtester.run_for_strategy` instead of `Backtester.run` directly — single-TF candidates take the same path they always did. |

## Test Summary

- **Phase 9 tests at phase completion**:
  - 9.1: 7 new tests in `tests/test_strategy_loader.py` +
    `tests/test_proposal_engine.py` + `tests/test_multi_timeframe_smoke.py`.
  - 9.2: 30 new tests across the 3 baseline strategies + the
    indicators module.
  - 9.3: 15 new tests — 13 in `tests/test_backtest_multi_timeframe.py`,
    1 in `tests/test_backtest_validator.py` (gate routing),
    1 in `tests/test_feedback_loop.py` (loop threading).
- **Full suite at phase completion**: **1010 passing, 0 failing**.
- **Lint/format**: `ruff check` clean across all Phase 9 source.
  `mypy` clean on the modified source files (pre-existing transitive
  errors in unrelated modules not addressed; tracked as background
  toil, not new debt).

## Gaps

None blocking. Two intentional deferrals tracked on the development
plan, both unblocked by Phase 9 but not in scope here:

1. **Per-timeframe RSI baseline split** (`rsi_4h.py` /
   `rsi_15m.py`) — deferred from 9.2 pending 9.1; now also unblocked
   by 9.3 for backtesting. A small follow-up sub-task.
2. **Phase 7.5 Tapbit Integration** — deferred since Phase 7. Not
   related to Phase 9; carried forward unchanged.

Two implementation deferrals documented in the 9.3 session log (not
gaps against any FR/NFR):

1. **Per-TF warmup configuration** — `BacktestConfig.warmup_candles`
   is one int applied to every TF. A future strategy that legitimately
   wants different warmups per TF would need `dict[str, int]` support.
2. **Live Claude smoke against `chasulang_ict_smc`** — every layer
   has unit-test coverage but a real-Claude run against historical
   OHLCV through the new multi-TF backtester is still a manual
   validation step, not an automated test.

## Risks Carried Forward

1. **Multi-TF strategies make N exchange calls per scan cycle** —
   chasulang declares 4 TFs × 3 symbols = 12 OHLCV calls per cycle
   for that strategy. Still well within Binance public rate limits;
   worth watching as more multi-TF strategies are added. (9.1)
2. **`ProposalEngine` fetches multi-TF data sequentially**, not in
   parallel — `asyncio.gather` is a future optimisation but adds
   error-aggregation complexity. Today: any TF failure cleanly bubbles
   to the existing per-symbol skip pattern. (9.1)
3. **Multi-TF backtests are slower than single-TF** by a constant
   factor — the per-step bisect is cheap but every analyze call now
   serializes a per-TF dict. For LLM-backed strategies the bottleneck
   is still the LLM, not the slicing. (9.3)
4. **Sensitivity gate's `strategy_factory` is a strategy-author
   concern** — when sweeping params for a multi-TF strategy, the
   factory must produce strategies whose `info.requires_multi_timeframe`
   matches. Not enforced by the framework; documented in the gate's
   docstring. (9.3)
5. **`Proposal.timeframe` and `BacktestResult.timeframe` both store
   a single string** for the primary TF. If a future feature surfaces
   "this strategy used these N TFs" in the dashboard, a separate
   metadata field will be needed. (9.1 / 9.3)
6. **No live-engine multi-TF validation against real Claude yet** —
   manual validation should precede promoting any chasulang variant
   to active. (9.1 / 9.3)

## Cross-Check Result

- ✅ Complete: 11 requirements (7 FR + 2 NFR + 1 CON + 3 phase-adjacent
  consumed)
- ⚠️ Partial: 0 requirements
- ❌ Gap: 0 requirements

**Phase 9 closes. The development plan's mainline now has no
non-deferred unchecked items. Carried-forward deferrals: 7.5 Tapbit
(longstanding) and the per-timeframe RSI baseline split (small
follow-up unblocked by 9.1 + 9.3).**

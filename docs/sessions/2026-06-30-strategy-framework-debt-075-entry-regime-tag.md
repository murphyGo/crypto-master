# Session: strategy-framework DEBT-075 entry regime tag

## Unit

- Primary: `strategy-framework`
- Secondary: `strategy-tuning`
- Debt: DEBT-075
- Requirements: FR-005, FR-027, FR-034, FR-039, NFR-006, NFR-007

## Summary

Resolved the missing entry-time regime tag that blocked per-regime expectancy
and the promotion robustness gate. Proposals now carry `market_regime` from the
primary pre-entry OHLCV stream, closed-trade performance records persist that
label, and `TechniquePerformance` exposes fee-aware per-regime expectancy.

## Files Changed

- `src/backtest/validator.py`
- `src/proposal/engine.py`
- `src/runtime/snapshot_recorder.py`
- `src/strategy/performance.py`
- `src/strategy/__init__.py`
- `tests/test_backtest_validator.py`
- `tests/test_proposal_engine.py`
- `tests/test_runtime_engine.py`
- `tests/test_strategy_performance.py`
- `docs/TECH-DEBT.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/inception/units/debt-unit-map.md`
- `aidlc-docs/construction/plans/strategy-framework-code-generation-debt-075-entry-regime-tag-plan.md`

## Verification

- `uv run pytest tests/test_backtest_validator.py::TestRegimeClassifier tests/test_proposal_engine.py::test_propose_bitcoin_returns_full_proposal tests/test_proposal_engine.py::test_propose_bitcoin_stamps_entry_market_regime tests/test_strategy_performance.py::TestPerformanceRecord::test_create_record_with_defaults tests/test_strategy_performance.py::TestTechniquePerformance tests/test_runtime_engine.py::test_closed_trade_performance_record_uses_trade_sub_account_path -q`
- `uv run ruff check src/backtest/validator.py src/proposal/engine.py src/runtime/snapshot_recorder.py src/strategy/performance.py src/strategy/__init__.py tests/test_backtest_validator.py tests/test_proposal_engine.py tests/test_runtime_engine.py tests/test_strategy_performance.py`
- `uv run mypy src`

## Decisions

- The proposal stamp uses the existing trailing-SMA robustness classifier via a
  small public wrapper, so runtime and robustness-gate semantics stay aligned.
- The helper classifies only the latest provided candle and returns `unknown`
  when the pre-entry window is insufficient. It does not fetch or infer future
  candles.
- Legacy proposal/performance payloads default to `unknown`, preserving old
  JSON compatibility.
- Per-regime expectancy uses the same fee-aware closed-real-record filter as
  the existing `net_*` aggregates.

## Risks

- Historical trades remain untagged unless an operator runs a future read-only
  backfill. Those rows load as `unknown` and do not fabricate regime evidence.

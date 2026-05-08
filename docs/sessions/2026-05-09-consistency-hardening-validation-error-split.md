# Session: consistency-hardening — CH-04 Split warmup vs structural StrategyValidationError

## Unit

- `consistency-hardening` (primary owner units: `strategy-framework`,
  `backtesting-validation`)
- Stage: Code Generation
- Slice ID: CH-04

## Related Requirements

- FR-034 Robustness Validation Gate
- NFR-007 Runtime Resilience
- NFR-012 Operational Observability

## Problem

`StrategyValidationError` was raised both by `BaseStrategy.validate_input`
("not enough data yet") and by the strategy/loader pipeline for genuine
contract failures: prompt-template placeholder errors
(`PromptStrategy._format_prompt`), `validate_python_strategy_source`
banned imports/syntax, and `load_technique_info_from_*` invalid
`TECHNIQUE_INFO`. The backtest engine caught the base class as a benign
"warmup skip" without incrementing the per-strategy parse-failure
breaker. A structurally broken candidate would therefore skip every
bar and emerge with a clean 0-trade `BacktestResult` — visually
indistinguishable from a healthy run that simply produced no signals.
That defeats the entire point of the breaker, which exists to surface
these silent failures within `max_parse_failures` candles.

## Fix

- Added `StrategyDataInsufficient(StrategyValidationError)` in
  `src/strategy/base.py`. Reserves the new subclass for the warmup
  meaning; keeps the parent class for structural failures.
- `BaseStrategy.validate_input` now raises `StrategyDataInsufficient`
  on empty / too-short OHLCV.
- The single-TF and multi-TF loops in `src/backtest/engine.py` catch
  `StrategyDataInsufficient` for the skip path. Non-warmup
  `StrategyValidationError` paths (prompt placeholders, banned
  imports, malformed metadata) inherit from `StrategyError` and now
  fall through to the existing
  `except (ClaudeParseError, StrategyError)` breaker clause.

## Files Changed

- `src/strategy/base.py`
- `src/backtest/engine.py`
- `tests/test_backtest_engine.py`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/plans/consistency-hardening-code-generation-validation-error-split-plan.md`

## Tests / Checks Run

- `uv run pytest tests/test_backtest_engine.py tests/test_strategy_base.py
  tests/test_strategy_loader.py tests/test_backtest_validator.py
  tests/test_backtest_harness.py tests/test_backtest_multi_timeframe.py`
  — 149/149 passed (2 new tests).
- `uv run ruff check` clean for changed files.
- `uv run black --check` clean.
- `uv run mypy src/strategy/base.py src/backtest/engine.py` — clean for
  both. The pre-existing `src/backtest/harness.py:113` mypy error is
  unrelated and falls under CH-09.

## Decisions

- Subclass relationship preserved
  (`StrategyDataInsufficient` extends `StrategyValidationError`) so any
  existing test or caller that catches the parent still works. New
  callers can be more precise without churn.
- Backtest engine drops the now-unused `StrategyValidationError`
  import — the breaker clause still catches structural validation
  errors via the `StrategyError` parent.

## Risks

- Low. The new subclass is the only path through `validate_input`, and
  the only existing in-repo strategies use `validate_input` for warmup,
  so behaviour is unchanged for healthy backtests. The change only
  exposes the previously-hidden failure mode for structurally broken
  strategies — exactly the surface the breaker was built to catch.

## Debt Added / Resolved

- No new tech-debt entries. Pre-existing `src/backtest/harness.py:113`
  is tracked separately (CH-09 scope).

## Follow-up

- CH-05: dashboard command-center scope + aggregate equity consistency
  (`src/dashboard/app.py`).

# Session: strategy-framework DEBT-076 regime score

## Unit

- Primary: `strategy-framework`
- Debt: DEBT-076
- Requirements: FR-005, FR-027, FR-034, FR-039, NFR-006

## Summary

Resolved the regime-gate telemetry mismatch in average-expectancy mode.
`_gate_regime` already made the correct pass/fail decision from the average
expectancy when `regime_require_positive_in_all=False`; it now reports that
same average as `score` with `threshold=0.0`.

All-positive mode is unchanged and still reports evaluable-pass count over
evaluable count.

## Files Changed

- `src/backtest/validator.py`
- `tests/test_backtest_validator.py`
- `docs/TECH-DEBT.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/inception/units/debt-unit-map.md`
- `aidlc-docs/construction/plans/strategy-framework-code-generation-debt-076-regime-score-plan.md`

## Verification

- `uv run pytest tests/test_backtest_validator.py::TestRegimeGate::test_average_mode_reports_average_score_and_zero_threshold -q`
- `uv run ruff check src/backtest/validator.py tests/test_backtest_validator.py`
- `uv run mypy src`

## Decisions

- Kept branch-local `score`/`threshold` variables so future branch changes do
  not accidentally leak count-mode telemetry into average mode again.
- Used a monkeypatched classifier in the regression test to isolate telemetry
  behavior from price-pattern construction.

## Risks

- None known. This changes operator-facing telemetry only; pass/fail behavior is
  unchanged.

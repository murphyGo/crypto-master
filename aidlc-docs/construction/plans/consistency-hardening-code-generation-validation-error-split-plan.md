# Code Generation Plan: consistency-hardening — CH-04 Split warmup vs structural StrategyValidationError

## Task

Introduce `StrategyDataInsufficient(StrategyValidationError)` for the
"warmup not ready" case and have the backtest engine catch only that
subclass as a benign skip. Other `StrategyValidationError` paths (bad
prompt placeholders, banned imports, malformed `TECHNIQUE_INFO`) now
fall through to the breaker so a structurally broken strategy cannot
silently skip every bar and emerge with a 0-trade pass.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-04
- Primary owner units: `strategy-framework`, `backtesting-validation`

## Related Requirements

- FR-034 Robustness Validation Gate
- NFR-007 Runtime Resilience
- NFR-012 Operational Observability

## Steps

- [x] Add `StrategyDataInsufficient` subclass in `src/strategy/base.py`.
- [x] Switch `BaseStrategy.validate_input` to raise the new subclass.
- [x] Backtest engine (single-TF + multi-TF) catches the subclass for
      skip semantics; `(ClaudeParseError, StrategyError)` clause now
      catches non-warmup `StrategyValidationError` paths via the parent
      class.
- [x] Tests: `test_structural_validation_error_counts_toward_breaker`
      and `test_warmup_data_insufficient_does_not_trip_breaker` pin
      both branches.
- [x] Targeted pytest: 149 / 149 across backtest engine, validator,
      harness, multi-timeframe, strategy base, and strategy loader.
- [x] Lint/format/types clean for changed files (pre-existing harness.py
      mypy error unaffected).
- [x] State row updated.
- [x] Session log written.

## Verification

- 149 / 149 targeted tests pass; 2 new regression tests pin the
  warmup vs structural split.
- ruff/black clean. mypy clean for the two changed source files.

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Tests added.
- [x] Plan steps closed.
- [x] State row updated.
- [x] Session log written.

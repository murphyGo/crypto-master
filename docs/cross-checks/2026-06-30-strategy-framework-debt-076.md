# Cross-Check: strategy-framework DEBT-076

## Scope

Verify DEBT-076: regime-gate score/threshold telemetry must match the active
average-expectancy branch.

## Result

PASS.

## Evidence

- All-positive mode still sets `score` to evaluable regimes without negative
  expectancy and `threshold` to evaluable count.
- Average mode now sets `score` to the average expectancy and `threshold` to
  `0.0`, matching `passed = avg >= 0`.
- Regression test pins a two-regime average of `(+10 + -4) / 2 = 3.0`.

## Verification

- Targeted pytest: 1 passed.
- Touched-file ruff: passed.
- `uv run mypy src`: passed.

## Residual Risk

None. The gate outcome was already correct; only reported telemetry changed.

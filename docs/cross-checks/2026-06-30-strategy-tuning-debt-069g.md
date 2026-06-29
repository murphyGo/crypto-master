# Cross-Check: strategy-tuning DEBT-069(g)

## Scope

Verify the final DEBT-069(g) threshold-calibration slice.

## Result

PASS.

## Evidence

- Fresh Fly `/data/performance` evidence was downloaded read-only and reviewed.
- `ScoutThresholds.sample_size_max` default is now `15`.
- Functional design default YAML now documents `sample_size_max: 15`.
- Recommender tests pin the boundary: 15 closed trades scouts; 16 closed trades
  no longer scouts when PF is still below keep.
- `keep.profit_factor_min` and `keep.win_rate_min` are unchanged, with the
  decision recorded in the session log.

## Verification

- Targeted pytest: 2 passed.
- Touched-file ruff: passed.
- `uv run mypy src`: passed.

## Residual Risk

Future evidence drift may require a new calibration item. DEBT-069 Slice 2 is
complete as of this cross-check.

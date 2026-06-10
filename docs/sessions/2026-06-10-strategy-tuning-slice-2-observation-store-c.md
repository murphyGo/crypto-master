# Strategy Tuning Slice 2(c): Observation Store

## Unit

- `strategy-tuning`
- Debt: DEBT-069(c)
- Stage: Code Generation / Build and Test

## Summary

Implemented a durable recommendation-history store for strategy-tuning so each
`(sub_account_id, strategy)` pair can persist the applied action, displayed
recommendation, raw live recommendation, and exact evidence snapshot used by the
recommender.

## Files Changed

- `src/strategy/tuning_observations.py`
  - Added `StrategyTuningObservationStore`.
  - Stores atomic JSON snapshots under `data/strategy_tuning/observations` by
    default.
  - URL-encodes account and strategy path components.
  - Preserves `first_seen_at`, increments `observations_count`, and keeps a
    bounded recent recommendation history.
- `src/dashboard/pages/strategies.py`
  - Added explicit no-write-by-default observation integration.
  - Added `record_strategy_tuning_observations(...)` for side-effecting
    observation capture.
  - Added `Observed` and `Observations` metadata columns when persisted
    observations are supplied.
- `src/strategy/__init__.py`
  - Exported the observation models/store.
- `tests/test_strategy_tuning_observations.py`
  - Covered first write/load, first-seen preservation, history cap, malformed
    file skip, and encoded paths.
- `tests/test_dashboard_strategies.py`
  - Covered persisted observation metadata in tuning rows/dataframe.

## Decisions

- Dashboard persistence is explicit. Supplying a
  `StrategyTuningObservationStore` records observations; omitting it preserves
  the prior no-write dashboard behavior and avoids surprising writes during
  tests or read-only operator views.
- The displayed recommendation is persisted after the seed fallback, while
  `live_recommendation` is also stored separately. This keeps the operator-visible
  history faithful to the dashboard and still preserves whether the recommendation
  came from live evidence or from the seed fallback.
- A bounded snapshot history is enough for this slice. Full time-series
  analytics can build on the persisted `history` list later without changing the
  on-disk top-level contract.

## Verification

- `uv run pytest tests/test_strategy_tuning_observations.py tests/test_dashboard_strategies.py -q`
  - 36 passed
- `uv run pytest tests/test_strategy_tuning_recommender.py -q`
  - 38 passed

## Risks

- The store is not yet wired into the runtime engine loop. It is exposed as a
  side-effecting helper for dashboard/operator integration; DEBT-069(g) threshold
  calibration remains the only open DEBT-069 umbrella item.

## Status

DEBT-069(c) shipped. Remaining DEBT-069 work: (g) post-evidence threshold
calibration.

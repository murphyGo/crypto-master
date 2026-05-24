# Cross-Check: strategy-tuning true profit factor

Date: 2026-05-24
Unit: `strategy-tuning`
Scope: DEBT-069(e)

## Requirement Mapping

- FR-005: Strategy performance aggregates expose gross win/loss and drawdown
  evidence from real closed trades.
- FR-027 / FR-039: Recommendation decisions consume fair paper-lab evidence
  instead of the prior best/worst-trade PF approximation.
- NFR-006 / NFR-007: Existing JSON persistence remains backwards-compatible;
  new aggregate fields have safe defaults for existing constructors and records.

## Evidence

- `TechniquePerformance.from_records` excludes `synthetic=True` rows from
  `gross_win_pct`, `gross_loss_pct`, `max_drawdown_pct`, and existing money
  aggregates.
- `evidence_from_performance` computes PF from true gross win/loss and returns
  `None` when gross loss is zero.
- The recommender's default drawdown input now uses the cumulative closed-trade
  drawdown aggregate.
- No runtime gate, account policy, proposal state, or strategy logic changed.

## Verification

- `uv run pytest tests/test_strategy_performance.py tests/test_strategy_tuning_recommender.py -q`
  - Result: 119 passed.
- `uv run ruff check src/strategy/performance.py src/strategy/tuning_recommender.py tests/test_strategy_performance.py tests/test_strategy_tuning_recommender.py`
  - Result: passed.
- `uv run mypy src/strategy/performance.py src/strategy/tuning_recommender.py`
  - Result: passed.

## Result

PASS for DEBT-069(e). The broader DEBT-069 umbrella remains open for dashboard,
recommendation-history, applied-action emission, pause-reason, threshold
calibration, and funnel-test follow-ups.

# Session: strategy-tuning DEBT-069(g) threshold calibration

## Unit

- Primary: `strategy-tuning`
- Secondary: `strategy-framework`, `dashboard-operator-ui`
- Debt: DEBT-069(g)
- Requirements: FR-005, FR-013, FR-027, FR-034, FR-039, NFR-006, NFR-007

## Summary

Completed the final DEBT-069 Slice 2 threshold-calibration follow-up.
Downloaded the deployed Fly `/data/performance` snapshot to
`/private/tmp/crypto-master-performance-debt069g.tgz` and reviewed current
closed-trade evidence.

Calibration decision:

- `scout.sample_size_max`: changed from `10` to `15`, aligning it with
  `keep.sample_size_min` and removing the structural 11-14 sample dead zone.
- `keep.profit_factor_min`: retained at `1.3`.
- `keep.win_rate_min`: retained at `0.40`.

The only active 11-19 closed-trade row was `rsi_universal` with 16 closed
trades, PF 3.78, win rate 0.375, and positive net PnL. That does not justify
relaxing the keep win-rate floor; it is just outside keep on win rate and above
the new scout cap.

## Files Changed

- `src/strategy/tuning.py`
- `tests/test_strategy_tuning_recommender.py`
- `aidlc-docs/construction/strategy-tuning/functional-design/spec.md`
- `aidlc-docs/construction/plans/strategy-tuning-code-generation-plan.md`
- `docs/TECH-DEBT.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/inception/units/debt-unit-map.md`

## Verification

- `uv run pytest tests/test_strategy_tuning_recommender.py::test_scout_fires_for_under_sampled_positive_edge tests/test_strategy_tuning_recommender.py::test_scout_does_not_fire_above_sample_size_cap -q`
- `uv run ruff check src/strategy/tuning.py tests/test_strategy_tuning_recommender.py`
- `uv run mypy src`

## Evidence Snapshot

- `rsi_universal`: 16 closed, PF 3.78, win rate 0.375, net PnL +84.96%, fail-closed 1.2%.
- `session_vwap_pullback`: 21 closed, PF 1.72, win rate 0.524.
- `vwap_mean_reversion`: 23 closed, PF 2.41, win rate 0.478.
- `rsi_15m`: 26 closed, PF 3.84, win rate 0.192.
- No current strategy occupied the 11-14 closed-trade interval.

## Decisions

- Close the structural sample-size gap even though the current snapshot has no
  11-14 row. This is a low-risk threshold alignment: a positive PF 1.0-1.5
  strategy with 11-15 samples remains reduced-risk scout instead of falling to
  no recommendation.
- Do not relax keep thresholds from this snapshot. A lower win-rate floor would
  change capital posture for borderline evidence and needs stronger proof.

## Risks

- The calibration is based on the deployed snapshot available on 2026-06-30.
  If distributions drift materially, future changes should be filed as a new
  strategy-tuning debt item rather than reopening DEBT-069.

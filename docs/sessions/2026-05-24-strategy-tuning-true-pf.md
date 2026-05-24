# Session: strategy-tuning true profit factor

## Unit

- `strategy-tuning`
- Related debt: DEBT-069(e); partial DEBT-069(h)

## Scope

Implemented the true profit-factor follow-up from the DEBT-069 umbrella.
This is a recommender-evidence change only; no strategy entry/exit logic,
runtime gates, account config, or Fly `/data` state was changed.

## Fly Evidence Context

The work followed the 2026-05-24 deployed paper-lab analysis:

- Fly app: `crypto-master`
- Machine/version observed: `6835752b711958` / `46`
- Snapshot:
  `/private/tmp/crypto-master-strategy-snapshots/fly-data-20260524-054152.tgz`
- Key driver: strategy ranking should not depend on the prior best/worst-trade
  PF approximation because the paper-lab sample has fat-tail winners/losers and
  many low-sample accounts.

## Changes

- `src/strategy/performance.py`
  - Added `TechniquePerformance.gross_win_pct`,
    `TechniquePerformance.gross_loss_pct`, and
    `TechniquePerformance.max_drawdown_pct`.
  - `from_records` computes the fields from closed real records only, preserving
    the existing `synthetic=True` exclusion contract.
  - Added the DEBT-069(h) defensive comment: future shadow-aware performance
    derivations must filter proposal-only `shadow=True` rows before money
    aggregates.
- `src/strategy/tuning_recommender.py`
  - Removed `_infer_profit_factor`, which approximated PF from
    `wins * best_trade_pnl / losses * abs(worst_trade_pnl)`.
  - `evidence_from_performance` now computes true PF as
    `gross_win_pct / gross_loss_pct`, returning `None` when gross loss is zero.
  - Default drawdown input now reads `perf.max_drawdown_pct`.
- Tests
  - Added gross win/loss and cumulative closed-trade drawdown assertions.
  - Pinned synthetic-row exclusion for the new aggregates.
  - Updated recommender evidence tests to prove the old best/worst approximation
    is ignored.

## Verification

- `uv run pytest tests/test_strategy_performance.py tests/test_strategy_tuning_recommender.py -q`
  - Result: 119 passed.
- `uv run black src/strategy/performance.py src/strategy/tuning_recommender.py tests/test_strategy_performance.py tests/test_strategy_tuning_recommender.py`
  - Result: 2 files reformatted.
- `uv run ruff check src/strategy/performance.py src/strategy/tuning_recommender.py tests/test_strategy_performance.py tests/test_strategy_tuning_recommender.py`
  - Result: passed.
- `uv run mypy src/strategy/performance.py src/strategy/tuning_recommender.py`
  - Result: passed.

## Remaining Work

DEBT-069 remains active for:

- Dashboard view + YAML helper.
- Initial recommendation seeding.
- Observation store.
- `STRATEGY_ACTION_APPLIED` emission.
- Pause reason split.
- Threshold calibration after more paper-lab evidence.
- Funnel unit-test gaps.

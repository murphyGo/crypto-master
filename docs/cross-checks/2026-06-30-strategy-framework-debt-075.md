# Cross-Check: strategy-framework DEBT-075

## Scope

Verify DEBT-075: every new proposal/performance record can carry an entry-time
market regime label, and performance summaries expose per-regime expectancy.

## Result

PASS.

## Evidence

- `classify_entry_regime` reuses the existing trailing-SMA classifier in
  `src/backtest/validator.py` and returns `unknown` for insufficient pre-entry
  data.
- `ProposalEngine._build_proposal_for_strategy` stamps `Proposal.market_regime`
  from the primary OHLCV stream used for analysis.
- `SnapshotRecorder._save_performance_record` copies the proposal label onto
  `PerformanceRecord.market_regime`.
- `TechniquePerformance.from_records` emits `regime_performance` with
  per-regime closed-trade count, fee-aware expectancy, and total PnL percent.
- Legacy records without `market_regime` validate with the default `unknown`.

## Verification

- Targeted pytest: 15 passed.
- Touched-file ruff: passed.
- `uv run mypy src`: passed.

## Residual Risk

Existing historical records are not backfilled in this unit. They remain
compatible via `unknown`, which is conservative for promotion gating.

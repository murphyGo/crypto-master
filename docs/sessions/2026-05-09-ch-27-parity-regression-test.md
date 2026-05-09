# Session: consistency-hardening CH-27 multi-TF parity regression test

Date: 2026-05-09

## Unit

- `consistency-hardening`
- Slice: CH-27 (close-out)
- Primary owner unit: `backtesting-validation`
- Specialists this cycle: senior-developer, qa-reviewer, quant-trader-expert,
  docs-auditor

## Scope

- Closed out CH-27 by adding the missing strong regression test for the
  `Backtester._execute_bar` dedup that was already shipped in commit
  `382d3b9 Deduplicate backtest bar execution`.
- No `src/` changes this cycle. `Backtester._execute_bar`
  (`src/backtest/engine.py:761`) remains the sole per-bar entry point shared by
  `Backtester.run` (single-TF) and `Backtester.run_multi_timeframe` (multi-TF).
- Quant review surfaced four parity variants (slippage, liquidation, short-side,
  non-degenerate multi-TF) that are out of scope for this cycle and recorded as
  a single follow-up TECH-DEBT entry instead of blocking close-out.

## Changes

- Added `tests/test_backtest_engine.py::TestRunMultiTimeframeParity` with two
  parity tests:
  - `test_run_and_run_multi_timeframe_identical_ledger` — 200-candle
    deterministic fixture exercising 4 TP hits, 3 SL hits, 1 end-of-data close,
    and 6 parse-error candles for breaker bookkeeping. Asserts byte-identical
    full ledger, equity curve, balance, fees, pnl, and `liquidated` flag across
    `Backtester.run` and `Backtester.run_multi_timeframe`.
  - `test_run_and_run_multi_timeframe_identical_breaker_abort` — locks down
    `BacktestAbortedError.reason` and `candle_index` parity for the abort path
    so a future divergence in breaker bookkeeping between the two callers is
    caught.
- Doc updates this cycle:
  - `aidlc-docs/construction/consistency-hardening/functional-design/spec.md`
    CH-27 row status changed to
    `Shipped 2026-05-09 (parity regression test added; dedup body in 382d3b9; followups in DEBT-055)`.
  - `aidlc-docs/aidlc-state.md` `consistency-hardening` row progress cell
    extended with the CH-27 parity regression test entry. State stays
    `In progress` because CH-28..CH-36 close-outs and CH-36 follow-up are still
    open.
  - `docs/TECH-DEBT.md` appended `DEBT-055 CH-27 multi-TF parity test gaps`
    (Medium, backtesting-validation / consistency-hardening) and `DEBT-056`
    (Low) for the pre-existing test flake + ruff I001 hits surfaced during the
    QA full-suite run; Statistics block bumped to 2 Active (1 Medium + 1 Low);
    Change History rows added for both.

## Tests

- `pytest tests/test_backtest_engine.py -q` — focused run of the new parity
  tests (and the rest of the file) passed.
- Full suite: 1257 pass / 1 pre-existing fail
  (`tests/test_scripts_auto_research_candidates.py::test_run_picks_orchestrates_each_candidate`,
  `GeneratedTechniqueError` from `src/ai/improver.py:425`, unrelated to CH-27;
  recorded as `DEBT-056`).
- `ruff check` / `black --check` / `mypy` clean on the changed files.
- Two pre-existing `ruff` `I001` import-order hits in unrelated files
  (`src/dashboard/pages/engine.py:25`, `tests/test_backtest_validator.py:3`)
  also recorded as `DEBT-056`.

## Decisions

- Closed CH-27 on the spec.md row instead of leaving it "in progress for parity
  test": the dedup body has been in `382d3b9` since the originally-claimed ship
  date, and the new regression test pair locks down the parity guarantee for
  the dispatch-mirroring case. The four quant-flagged parity variants
  (slippage, liquidation, short-side, non-degenerate multi-TF) are real gaps
  but they extend the parity claim rather than gate the close-out, so they were
  written up as `DEBT-055` follow-up rather than a CH-27 blocker.
- Kept the older
  `tests/test_backtest_multi_timeframe.py::TestRunMultiTimeframeSemantics::test_single_and_multi_tf_modes_share_closed_trade_ledger`
  test in place for now. Its assertions are subsumed by the new parity pair,
  but removing it in the same commit as the parity-test addition would mix two
  intents; the drop/rescope decision is queued under `DEBT-055` for a
  follow-up.

## Risks

- Parity claim now publicly covers only the dispatch-mirroring case. Until
  `DEBT-055`'s four variants land, a refactor that diverges
  `_execute_bar` callers under slippage, liquidation, short-side, or
  non-degenerate multi-TF conditions would not be caught by the regression
  suite.

## Follow-up

- `DEBT-055` — add the four parity variants and either drop or rescope the
  superseded `test_single_and_multi_tf_modes_share_closed_trade_ledger` in a
  follow-up commit.
- `DEBT-056` — fix the pre-existing
  `test_run_picks_orchestrates_each_candidate` failure and run
  `ruff check --fix` against the two named files.
- CH-27 closed; CH-28 next on the consistency-hardening backlog close-out.

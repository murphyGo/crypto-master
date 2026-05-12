# Session: DEBT-055 multi-TF parity test gaps closeout

## Unit

- `backtesting-validation`
- Secondary unit: `consistency-hardening`

## Related Requirements

- FR-025: Execute backtests against historical data
  (`aidlc-docs/inception/requirements/requirements.md`)
- FR-034: Gate strategy promotion through robustness validation
  (`aidlc-docs/inception/requirements/requirements.md`)

No clean dedicated mapping exists for "regression hygiene of internal
backtester parity claims". The closest requirements above cover the backtester
and robustness/promotion contracts that the parity guarantee underwrites.

## Scope

Resolved DEBT-055 (CH-27 multi-TF parity test gaps) and refreshed DEBT-056
statistics. Test-only diff; no production code touched.

## Changes

- `tests/test_backtest_engine.py`
  - Added module-level helpers `_ledger`, `_build_short_parity_fixture`, and
    `_MultiModeShortStrategy`.
  - Added 4 new tests inside `TestRunMultiTimeframeParity`:
    `test_run_and_run_multi_timeframe_identical_under_slippage`,
    `test_run_and_run_multi_timeframe_identical_on_liquidation`,
    `test_run_and_run_multi_timeframe_identical_short_side`,
    `test_run_and_run_multi_timeframe_diverge_when_higher_tf_gates_bars`.
  - Divergence test pins the multi-TF warmup contract
    (`all(slice_dict[tf] >= warmup_candles)`) by asserting strict-subset
    entry-bar indices `[120,150,180,195]` vs
    `[10,30,60,90,120,150,180,195]`, so the parity claim cannot silently
    widen to "always identical, including when it shouldn't be".
- `tests/test_backtest_multi_timeframe.py`
  - Deleted superseded
    `TestRunMultiTimeframeSemantics::test_single_and_multi_tf_modes_share_closed_trade_ledger`
    (new parity pair is a strict superset).
  - Removed orphan helpers `exit_fixture_candles` / `trade_ledger` and the
    unused `BacktestResult` import.
  - Module docstring now points readers at `TestRunMultiTimeframeParity` as
    the canonical parity location.
- `docs/TECH-DEBT.md`
  - Moved DEBT-055 to Resolved with 2026-05-13 resolution note.
  - Refreshed DEBT-056: failure count 1 → 6 in
    `tests/test_scripts_auto_research_candidates.py` on a clean tree, all 6
    affected tests listed; raise-site line corrected from
    `src/ai/improver.py:425` to `src/ai/improver.py:374`; Description and
    Related sections updated.
  - Statistics: Active 3 → 2, Medium 2 → 1, Resolved 53 → 54.
  - Change History: added 2026-05-13 Resolved DEBT-055 + Updated DEBT-056
    rows.
- `aidlc-docs/aidlc-state.md`
  - Appended DEBT-055 closeout note under the `consistency-hardening` row.

## Verification

- `uv run pytest tests/test_backtest_engine.py tests/test_backtest_multi_timeframe.py -q`
  - Result: 61 passed.
- `uv run pytest` (full suite)
  - Result: 1802 passed, 6 failed.
  - All 6 failures are pre-existing DEBT-056
    (`tests/test_scripts_auto_research_candidates.py`), independently
    confirmed by QA via `git stash` on a clean tree.
- `ruff check src tests`
  - Result: only the 2 pre-existing I001 hits already tracked under
    DEBT-056 (`src/dashboard/pages/engine.py:25`,
    `tests/test_backtest_validator.py:3`).
- `mypy src`
  - Result: 3 pre-existing errors in `src/dashboard/app.py`, unrelated to a
    test-only diff.

## Risks

None. Test-only diff; no production code touched.

## Reviewer Notes

- quant-trader-expert: 🟢. One optional polish flagged: the liquidation
  parity test could add `len(single_result.trades) == len(multi_result.trades)`
  if the fixture ever grows beyond the current single-signal /
  single-liquidation setup. Currently moot. Captured below under
  Future-work; not filed as a new DEBT.
- qa-reviewer: 🟢.

## Future-work

- Optional: add `len(single_result.trades) == len(multi_result.trades)` to
  `test_run_and_run_multi_timeframe_identical_on_liquidation` if the
  fixture is ever extended beyond single-signal / single-liquidation.
  Non-blocking; not tracked as DEBT.

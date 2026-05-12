# Cross-Check: trading-core paper persistence follow-ups

## Scope

Verify DEBT-059, DEBT-058, and DEBT-057 closeout against trading-core and
persistence-data-integrity requirements.

## Result

PASS

## Checks

| Debt | Expected | Evidence |
|------|----------|----------|
| DEBT-059 | Paper restart must not reseed full free balance while open margins remain locked. | `PaperTrader` loads `balances.json` before rehydration; missing snapshots trigger one-time open-position reconciliation. Covered by `TestPaperRehydration::test_rehydrate_loads_balance_snapshot_without_double_locking` and `test_rehydrate_reconciles_balance_when_snapshot_missing`. |
| DEBT-058 | Legacy open paper trades with null SL/TP must have an operator backfill path from linked performance records. | `src.tools.backfill_paper_sl_tp` walks paper ledgers, reads linked performance records, writes SL/TP atomically, supports dry-run and sub-account filtering. Covered by `tests/test_tools_backfill_paper_sl_tp.py`. |
| DEBT-057 | Paper entry fees must be persisted on open trade rows and included exactly once at close. | `PaperTrader.open_position` passes `fees=entry_fee`; `close_position` passes only `exit_fee` to `TradeHistoryTracker.close_trade`. Covered by entry-fee persistence and existing fee/PnL tests in `tests/test_paper_trading.py`. |

## Verification

- `uv run pytest tests/test_paper_trading.py tests/test_tools_backfill_paper_sl_tp.py -q`
  - 108 passed.

## Residual Risk

The one-time legacy balance reconciliation only applies to monitorable open
trades. Rows still missing SL/TP remain intentionally non-monitorable until the
operator runs `python -m src.tools.backfill_paper_sl_tp`.

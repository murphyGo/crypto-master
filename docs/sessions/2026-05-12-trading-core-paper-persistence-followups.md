# Session: trading-core paper persistence follow-ups

## Unit

- `trading-core`
- Secondary unit: `persistence-data-integrity`

## Related Requirements

- FR-010: Paper Trading Mode
- NFR-007: Trading History Storage
- NFR-008: Asset/PnL History

## Scope

Resolved DEBT-059, DEBT-058, and DEBT-057 in the requested order.

## Changes

- `src/trading/paper.py`
  - Added per-sub-account paper balance snapshots at `data/trades/paper/<sub_account>/balances.json`.
  - Loaded balance snapshots before open-position rehydration so restart state preserves `free`, `locked`, realised PnL, and paid fees.
  - Added one-time legacy reconciliation for ledgers with open paper trades but no balance snapshot.
  - Persisted entry fees on paper open trades and changed close-time fee addition to pass only the exit fee.
- `tests/test_paper_trading.py`
  - Added regression coverage for snapshot load, legacy balance reconciliation, restart close behaviour, and entry-fee persistence.
- `docs/TECH-DEBT.md`
  - Moved DEBT-059, DEBT-058, and DEBT-057 to Resolved.
- `aidlc-docs/aidlc-state.md`
  - Recorded the trading-core follow-up closeout.
- `aidlc-docs/construction/plans/trading-core-code-generation-plan.md`
  - Added the completed follow-up step and evidence links.

## DEBT-058 Note

`src/tools/backfill_paper_sl_tp.py` and `tests/test_tools_backfill_paper_sl_tp.py`
were already present. This session confirmed the operator tool and coverage, then
closed the stale active debt entry.

## Verification

- `uv run pytest tests/test_paper_trading.py tests/test_tools_backfill_paper_sl_tp.py -q`
  - Result: 108 passed.

## Risks

- Existing production ledgers without `balances.json` will receive one-time
  margin/entry-fee reconciliation at next startup only for monitorable open
  trades with persisted SL/TP.
- Legacy open trades still missing SL/TP remain intentionally skipped until the
  operator backfill tool is run.

# Session: runtime-reconciliation proposal-linked paper bounds repair

## Unit

- `runtime-reconciliation`

## Related Requirements

- FR-010, FR-014, FR-029
- NFR-007, NFR-008, NFR-012

## Context

The 2026-06-10 Fly `/data` paper-lab analysis found that current open paper
trades were not clean strategy-edge evidence. The decisive runtime issue was
that open rows were stale and not monitorable after restart:

- 46 open paper trades.
- 44 open rows had no persisted `stop_loss` / `take_profit`.
- 46 open rows had no `performance_record_id`.
- 46/46 open rows did have a `ProposalRecord.trade_id` join back to proposal
  history.

The existing repair tools were insufficient for this shape:

- `backfill_paper_sl_tp` requires `trade.performance_record_id`.
- `close_unrecoverable_paper_trades` only closes rows missing core fields.

The safe repair is to restore only SL/TP from proposal history. The runtime
close path writes realized performance from the proposal once a trade closes,
so this tool deliberately does not create pending `PerformanceRecord` rows.

## Changes

- Added `src/tools/repair_paper_trade_bounds_from_proposals.py`.
  - Joins open paper trades to proposal history by `trade_id`.
  - Refuses cross-account proposal/trade matches.
  - Restores missing `stop_loss` / `take_profit` from the proposal.
  - Re-reads the latest trade ledger before live writes and merges only
    per-trade SL/TP patches into current rows.
  - Supports `--dry-run` and `--sub-account`.
  - Emits one live-run activity event with summary counters.
- Added `ActivityEventType.RECONCILIATION_REPAIRED_PAPER_BOUNDS`.
- Added `tests/test_tools_repair_paper_trade_bounds_from_proposals.py`.
- Updated `aidlc-docs/construction/plans/runtime-reconciliation-code-generation-plan.md`
  with the operational repair follow-up.

## Verification

- `uv run pytest tests/test_tools_repair_paper_trade_bounds_from_proposals.py -q`
  - 11 passed.
- `uv run pytest tests/test_tools_backfill_paper_sl_tp.py tests/test_tools_close_unrecoverable_paper_trades.py tests/test_runtime_reconciliation.py -q`
  - 65 passed.
- `uv run black src/tools/repair_paper_trade_bounds_from_proposals.py tests/test_tools_repair_paper_trade_bounds_from_proposals.py src/runtime/activity_events.py`
- `uv run ruff check src/tools/repair_paper_trade_bounds_from_proposals.py tests/test_tools_repair_paper_trade_bounds_from_proposals.py src/runtime/activity_events.py`
  - All checks passed.
- `uv run mypy src/tools/repair_paper_trade_bounds_from_proposals.py src/runtime/activity_events.py`
  - Success.
- Combined targeted regression:
  `uv run pytest tests/test_tools_repair_paper_trade_bounds_from_proposals.py tests/test_tools_backfill_paper_sl_tp.py tests/test_tools_close_unrecoverable_paper_trades.py tests/test_runtime_reconciliation.py -q`
  - 76 passed.
- Snapshot dry-run against
  `/private/tmp/crypto-master-strategy-snapshots/fly-data-20260610-223147`:
  `ProposalBoundsRepairSummary(examined=172, repaired=44, already_set=2,
  skipped_closed=126, skipped_no_proposal=0, skipped_account_mismatch=0,
  skipped_proposal_unset=0, skipped_malformed=0, failed_files=0)`.
- Sub-agent review:
  - Data-integrity review found a cross-account proposal/trade mismatch risk;
    fixed with an explicit `bounds.sub_account_id == sub_account_id` guard and
    regression test.
  - Operator review found concurrent ledger-write risk; mitigated with latest
    snapshot merge-before-write and the live-run quiesce requirement below.

## Risks

- A live repair writes `trades.json` rows on the Fly `/data` volume. Dry-run
  evidence shows every repair candidate has a proposal join, but the live run
  should still be preceded by a fresh Fly backup.
- The Fly trader process also writes the same ledgers. Live repair must be run
  only while the trader is quiesced or stopped; the tool's latest-snapshot merge
  reduces stale-write blast radius but is not a replacement for quiescing the
  writer.
- Repairing persisted bounds does not affect the currently running process's
  in-memory `PaperTrader` state. A restart/redeploy is required for rehydrate
  to pick up the repaired rows and stop the `monitor_errored` loop.
- Rows remain `legacy_no_perf_link` after repair because no
  `performance_record_id` is created. That is intentional and monitorable.

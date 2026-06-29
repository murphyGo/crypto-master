"""Operator CLI: repair open paper-trade SL/TP from proposal history.

Some deployed paper ledgers can contain open rows that were linked to a
proposal but persisted before paper ``stop_loss`` / ``take_profit`` bounds were
written to ``trades.json``. Those rows are classified as ``degraded`` by
runtime-reconciliation and cannot be rehydrated into in-memory paper positions
after a Fly restart.

This tool repairs only the persisted exit bounds by joining
``trades/paper/<sub_account>/trades.json`` rows to
``proposals/**/<proposal_id>.json`` records via ``ProposalRecord.trade_id``.
It does not create or mutate ``PerformanceRecord`` rows: the runtime's close
path writes realized performance from the proposal once the trade actually
closes, and pre-creating pending records here would risk duplicate metrics.

Usage::

    python -m src.tools.repair_paper_trade_bounds_from_proposals --dry-run
    python -m src.tools.repair_paper_trade_bounds_from_proposals
    python -m src.tools.repair_paper_trade_bounds_from_proposals --sub-account rsi_15m

Idempotent: rows with both bounds already present are left untouched.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from src.config import get_settings
from src.logger import get_logger
from src.proposal.bounds import ProposalBounds, load_proposal_trade_bounds_index
from src.runtime.activity_log import ActivityEventType, ActivityLog
from src.utils.io import atomic_write_text

logger = get_logger("crypto_master.tools.repair_paper_trade_bounds_from_proposals")


@dataclass
class ProposalBoundsRepairSummary:
    """Aggregated counters for one proposal-bounds repair pass."""

    examined: int = 0
    repaired: int = 0
    already_set: int = 0
    skipped_closed: int = 0
    skipped_no_proposal: int = 0
    skipped_account_mismatch: int = 0
    skipped_proposal_unset: int = 0
    skipped_malformed: int = 0
    failed_files: int = 0

    def merge(self, other: ProposalBoundsRepairSummary) -> None:
        self.examined += other.examined
        self.repaired += other.repaired
        self.already_set += other.already_set
        self.skipped_closed += other.skipped_closed
        self.skipped_no_proposal += other.skipped_no_proposal
        self.skipped_account_mismatch += other.skipped_account_mismatch
        self.skipped_proposal_unset += other.skipped_proposal_unset
        self.skipped_malformed += other.skipped_malformed
        self.failed_files += other.failed_files


@dataclass(frozen=True)
class _TradeBoundsPatch:
    stop_loss: str
    take_profit: str


def _iter_sub_account_dirs(
    paper_root: Path,
    sub_account: str | None,
) -> list[Path]:
    if sub_account is not None:
        return [paper_root / sub_account]
    if not paper_root.exists():
        return []
    return sorted(d for d in paper_root.iterdir() if d.is_dir())


def _repair_one_file(
    trades_path: Path,
    sub_account_id: str,
    bounds_by_trade_id: dict[str, ProposalBounds],
    dry_run: bool,
) -> ProposalBoundsRepairSummary:
    summary = ProposalBoundsRepairSummary()
    if not trades_path.exists():
        return summary

    try:
        rows = json.loads(trades_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read %s: %s", trades_path, exc)
        summary.failed_files += 1
        return summary

    if not isinstance(rows, list):
        logger.error(
            "Unexpected ledger shape at %s (expected list, got %s); skipping",
            trades_path,
            type(rows).__name__,
        )
        summary.failed_files += 1
        return summary

    patches: dict[str, _TradeBoundsPatch] = {}
    for row in rows:
        if not isinstance(row, dict):
            summary.skipped_malformed += 1
            continue
        summary.examined += 1
        if row.get("status") != "open":
            summary.skipped_closed += 1
            continue

        if row.get("stop_loss") is not None and row.get("take_profit") is not None:
            summary.already_set += 1
            continue

        trade_id_raw = row.get("id")
        trade_id = trade_id_raw if isinstance(trade_id_raw, str) else None
        if trade_id is None:
            logger.warning(
                "Open paper trade %s (%s) has no string id; cannot repair SL/TP",
                row.get("id"),
                sub_account_id,
            )
            summary.skipped_no_proposal += 1
            continue

        bounds = bounds_by_trade_id.get(trade_id)
        if bounds is None:
            logger.warning(
                "Open paper trade %s (%s) has no linked proposal record; "
                "cannot repair SL/TP",
                row.get("id"),
                sub_account_id,
            )
            summary.skipped_no_proposal += 1
            continue

        if bounds.sub_account_id != sub_account_id:
            logger.warning(
                "Open paper trade %s (%s) is linked to proposal %s for "
                "sub-account %s; refusing cross-account SL/TP repair",
                row.get("id"),
                sub_account_id,
                bounds.proposal_id,
                bounds.sub_account_id,
            )
            summary.skipped_account_mismatch += 1
            continue

        if bounds.stop_loss is None or bounds.take_profit is None:
            logger.warning(
                "Open paper trade %s (%s) is linked to proposal %s but "
                "the proposal has unset SL/TP; cannot repair",
                row.get("id"),
                sub_account_id,
                bounds.proposal_id,
            )
            summary.skipped_proposal_unset += 1
            continue

        patches[trade_id] = _TradeBoundsPatch(
            stop_loss=bounds.stop_loss,
            take_profit=bounds.take_profit,
        )
        summary.repaired += 1

    if patches and not dry_run:
        if not _write_trade_bounds_patches(trades_path, patches):
            summary.failed_files += 1

    return summary


def _write_trade_bounds_patches(
    trades_path: Path,
    patches: dict[str, _TradeBoundsPatch],
) -> bool:
    """Merge SL/TP patches into the latest ledger snapshot and write it."""

    try:
        latest_rows = json.loads(trades_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to re-read %s before repair write: %s", trades_path, exc)
        return False

    if not isinstance(latest_rows, list):
        logger.error(
            "Unexpected ledger shape at %s before repair write "
            "(expected list, got %s); skipping",
            trades_path,
            type(latest_rows).__name__,
        )
        return False

    for row in latest_rows:
        if not isinstance(row, dict) or row.get("status") != "open":
            continue
        trade_id_raw = row.get("id")
        trade_id = trade_id_raw if isinstance(trade_id_raw, str) else None
        patch = patches.get(trade_id or "")
        if patch is None:
            continue
        if row.get("stop_loss") is None:
            row["stop_loss"] = patch.stop_loss
        if row.get("take_profit") is None:
            row["take_profit"] = patch.take_profit

    atomic_write_text(trades_path, json.dumps(latest_rows, indent=2, default=str))
    return True


def repair_paper_trade_bounds_from_proposals(
    data_dir: Path,
    sub_account: str | None = None,
    dry_run: bool = False,
    *,
    activity_log: ActivityLog | None = None,
) -> ProposalBoundsRepairSummary:
    """Repair missing SL/TP on open paper trades from proposal records."""

    paper_root = data_dir / "trades" / "paper"
    bounds_by_trade_id = load_proposal_trade_bounds_index(data_dir)
    totals = ProposalBoundsRepairSummary()

    for sub_dir in _iter_sub_account_dirs(paper_root, sub_account):
        sub_id = sub_dir.name
        sub_summary = _repair_one_file(
            trades_path=sub_dir / "trades.json",
            sub_account_id=sub_id,
            bounds_by_trade_id=bounds_by_trade_id,
            dry_run=dry_run,
        )
        prefix = "[dry-run] " if dry_run else ""
        skipped = (
            sub_summary.skipped_no_proposal
            + sub_summary.skipped_account_mismatch
            + sub_summary.skipped_proposal_unset
            + sub_summary.skipped_malformed
        )
        logger.info(
            "%sRepaired SL/TP for %d open paper trade(s) in %s "
            "(%d rows examined, %d already set, %d skipped)",
            prefix,
            sub_summary.repaired,
            sub_id,
            sub_summary.examined,
            sub_summary.already_set,
            skipped,
        )
        totals.merge(sub_summary)

    if not dry_run and activity_log is not None:
        activity_log.append(
            ActivityEventType.RECONCILIATION_REPAIRED_PAPER_BOUNDS,
            (
                f"Repaired proposal-linked SL/TP on {totals.repaired} "
                f"paper trade(s) ({totals.examined} examined)"
            ),
            details={
                "sub_account": sub_account,
                "examined": totals.examined,
                "repaired": totals.repaired,
                "already_set": totals.already_set,
                "skipped_closed": totals.skipped_closed,
                "skipped_no_proposal": totals.skipped_no_proposal,
                "skipped_account_mismatch": totals.skipped_account_mismatch,
                "skipped_proposal_unset": totals.skipped_proposal_unset,
                "skipped_malformed": totals.skipped_malformed,
                "failed_files": totals.failed_files,
            },
        )

    return totals


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Repair missing SL/TP on open paper trades from linked proposal "
            "records. Idempotent and dry-run-supporting."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the repair without writing trades.json.",
    )
    parser.add_argument(
        "--sub-account",
        type=str,
        default=None,
        help="Restrict the repair to one paper sub-account.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = get_settings()
    activity_log = ActivityLog(data_dir=settings.data_dir)
    totals = repair_paper_trade_bounds_from_proposals(
        data_dir=settings.data_dir,
        sub_account=args.sub_account,
        dry_run=args.dry_run,
        activity_log=activity_log,
    )
    prefix = "[dry-run] " if args.dry_run else ""
    skipped = (
        totals.skipped_no_proposal
        + totals.skipped_account_mismatch
        + totals.skipped_proposal_unset
        + totals.skipped_malformed
    )
    logger.info(
        "%sTotal: repaired %d open paper trade(s) "
        "(%d examined, %d already set, %d skipped)",
        prefix,
        totals.repaired,
        totals.examined,
        totals.already_set,
        skipped,
    )
    if totals.failed_files:
        logger.error("Repair completed with %d failed file(s)", totals.failed_files)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

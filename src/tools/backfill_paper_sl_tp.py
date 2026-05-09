"""Operator CLI: backfill missing SL/TP on legacy open paper trades.

DEBT-058 / one-shot ops tool. Trades opened before commit ``36eb2f3``
(paper SL/TP persistence) were written to
``data/trades/paper/<sub_account>/trades.json`` without
``stop_loss`` / ``take_profit`` columns. The
``PaperTrader._rehydrate_open_positions`` path (added in ``36eb2f3``)
skip-and-warns these legacy rows, leaving them as
``MONITOR_ERRORED:orphan_open_trade`` events on every restart.

This script walks the persisted paper ledger and recovers the missing
bounds from the linked ``PerformanceRecord``
(``trade.performance_record_id`` -> ``record.id``). Closed trades are
ignored — their null SL/TP is benign, the runtime never re-monitors
them.

Usage::

    # Actually backfill, all sub-accounts:
    python -m src.tools.backfill_paper_sl_tp

    # Preview without writing anything:
    python -m src.tools.backfill_paper_sl_tp --dry-run

    # Restrict to a single sub-account:
    python -m src.tools.backfill_paper_sl_tp --sub-account rsi_15m

Reads :class:`Settings` so ``DATA_DIR`` applies the same way it does
for the runtime. Idempotent — re-running on already-backfilled data is
a no-op (rows where SL or TP is already set are skipped silently).

Related Requirements:
- NFR-007: Trading History Storage.
- NFR-008: Asset/PnL History (mode separation).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

from src.config import get_settings
from src.logger import get_logger
from src.utils.io import atomic_write_text

logger = get_logger("crypto_master.tools.backfill_paper_sl_tp")


@dataclass
class BackfillSummary:
    """Per-sub-account counters describing one backfill pass.

    Attributes:
        examined: Total rows inspected (any status).
        backfilled: Open rows that received SL/TP from a perf record.
        skipped_no_perf: Open rows missing ``performance_record_id``.
        skipped_perf_unset: Open rows whose linked perf record had
            null ``stop_loss`` / ``take_profit`` (cannot recover).
        skipped_perf_missing: Open rows whose linked perf record could
            not be located on disk.
        already_set: Open rows where SL or TP was already populated
            (idempotency path).
    """

    examined: int = 0
    backfilled: int = 0
    skipped_no_perf: int = 0
    skipped_perf_unset: int = 0
    skipped_perf_missing: int = 0
    already_set: int = 0

    def merge(self, other: BackfillSummary) -> None:
        """Accumulate ``other`` into ``self`` (used for the global tally)."""
        self.examined += other.examined
        self.backfilled += other.backfilled
        self.skipped_no_perf += other.skipped_no_perf
        self.skipped_perf_unset += other.skipped_perf_unset
        self.skipped_perf_missing += other.skipped_perf_missing
        self.already_set += other.already_set


@dataclass
class _PerfIndex:
    """In-memory cache of ``record_id -> (stop_loss, take_profit)`` per sub-account.

    Built lazily on first lookup so we only pay the JSON-decode cost
    for sub-accounts that actually contain backfill candidates.
    """

    data_dir: Path
    sub_account_id: str
    _by_id: dict[str, tuple[str | None, str | None]] | None = field(default=None)

    def lookup(self, record_id: str) -> tuple[str | None, str | None] | None:
        """Return ``(stop_loss, take_profit)`` strings or ``None`` if not found.

        SL/TP are returned as their on-disk string form (the JSON
        records.json stores Decimals as strings) so the trades.json
        rewrite preserves identical formatting.
        """
        if self._by_id is None:
            self._by_id = self._build()
        return self._by_id.get(record_id)

    def _build(self) -> dict[str, tuple[str | None, str | None]]:
        # Read the on-disk JSON directly rather than going through
        # ``PerformanceTracker.load_records``: the latter parses every
        # row into a strict ``PerformanceRecord`` (non-null SL/TP), so
        # any legacy record with null bounds — exactly the case the
        # operator wants to surface as ``skipped_perf_unset`` — would
        # raise ValidationError and abort the whole pass. We only need
        # three fields per record, so a raw JSON walk is both safer
        # and cheaper.
        index: dict[str, tuple[str | None, str | None]] = {}
        sub_root = self.data_dir / "performance" / self.sub_account_id
        if not sub_root.exists():
            return index
        for technique_dir in sub_root.iterdir():
            if not technique_dir.is_dir():
                continue
            records_path = technique_dir / "records.json"
            if not records_path.exists():
                continue
            try:
                with open(records_path, encoding="utf-8") as f:
                    rows = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Failed to read perf records at %s: %s", records_path, exc)
                continue
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                rec_id = row.get("id")
                if not isinstance(rec_id, str):
                    continue
                sl_raw = row.get("stop_loss")
                tp_raw = row.get("take_profit")
                sl = str(sl_raw) if sl_raw is not None else None
                tp = str(tp_raw) if tp_raw is not None else None
                index[rec_id] = (sl, tp)
        return index


def _iter_sub_account_dirs(
    paper_root: Path,
    sub_account: str | None,
) -> list[Path]:
    """Return the sub-account directories the script should walk.

    When ``sub_account`` is provided, only that one is returned (even
    if it does not exist on disk — the caller logs the empty pass).
    Otherwise every immediate subdirectory of ``paper_root`` that
    looks like a sub-account ledger is returned, sorted for stable
    operator output.
    """
    if sub_account is not None:
        return [paper_root / sub_account]
    if not paper_root.exists():
        return []
    return sorted(d for d in paper_root.iterdir() if d.is_dir())


def _backfill_one_file(
    trades_path: Path,
    sub_account_id: str,
    perf_index: _PerfIndex,
    dry_run: bool,
) -> BackfillSummary:
    """Backfill SL/TP on a single ``trades.json`` file.

    Mutates ``trades.json`` in place (via ``atomic_write_text``) only
    when at least one row was actually backfilled and ``dry_run`` is
    ``False``. The dry-run path computes the same summary counts but
    leaves the file untouched.
    """
    summary = BackfillSummary()
    if not trades_path.exists():
        return summary

    try:
        with open(trades_path, encoding="utf-8") as f:
            rows = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read %s: %s", trades_path, exc)
        return summary

    if not isinstance(rows, list):
        logger.error(
            "Unexpected ledger shape at %s (expected list, got %s); skipping",
            trades_path,
            type(rows).__name__,
        )
        return summary

    mutated = False
    for row in rows:
        summary.examined += 1
        if not isinstance(row, dict):
            continue
        if row.get("status") != "open":
            # Closed/cancelled trades don't need monitoring; their
            # null SL/TP is benign and intentionally ignored.
            continue
        if row.get("stop_loss") is not None or row.get("take_profit") is not None:
            # Idempotency: anything with at least one bound already
            # set is treated as already-backfilled. We do not
            # overwrite a partially-set row from perf, because the
            # operator may have hand-edited it.
            summary.already_set += 1
            continue

        perf_id = row.get("performance_record_id")
        if perf_id is None:
            logger.warning(
                "Open paper trade %s (%s, %s) has no performance_record_id; "
                "cannot recover SL/TP",
                row.get("id"),
                sub_account_id,
                row.get("symbol"),
            )
            summary.skipped_no_perf += 1
            continue

        bounds = perf_index.lookup(perf_id)
        if bounds is None:
            logger.warning(
                "Open paper trade %s (%s, %s) references performance record "
                "%s which was not found in %s/performance/%s/",
                row.get("id"),
                sub_account_id,
                row.get("symbol"),
                perf_id,
                perf_index.data_dir,
                sub_account_id,
            )
            summary.skipped_perf_missing += 1
            continue

        sl, tp = bounds
        if sl is None or tp is None:
            logger.warning(
                "Open paper trade %s (%s, %s) is linked to perf record %s "
                "but its stop_loss/take_profit are also null; "
                "cannot recover",
                row.get("id"),
                sub_account_id,
                row.get("symbol"),
                perf_id,
            )
            summary.skipped_perf_unset += 1
            continue

        row["stop_loss"] = sl
        row["take_profit"] = tp
        summary.backfilled += 1
        mutated = True

    if mutated and not dry_run:
        # Use atomic_write_text so a crash mid-backfill cannot leave
        # the operator with a half-rewritten ledger.
        atomic_write_text(
            trades_path,
            json.dumps(rows, indent=2, default=str),
        )

    return summary


def backfill_paper_sl_tp(
    data_dir: Path,
    sub_account: str | None = None,
    dry_run: bool = False,
) -> BackfillSummary:
    """Walk every paper sub-account ledger and backfill SL/TP from perf records.

    Args:
        data_dir: Engine data root (``Settings.data_dir``); the script
            looks under ``<data_dir>/trades/paper/`` and
            ``<data_dir>/performance/``.
        sub_account: Optional sub-account id filter. When set, only
            that sub-account's ledger is touched.
        dry_run: When ``True``, compute the summary counts but write
            nothing back to disk.

    Returns:
        Aggregated :class:`BackfillSummary` across every sub-account
        examined. Per-sub-account summaries are emitted at INFO as a
        side effect for operator visibility.
    """
    paper_root = data_dir / "trades" / "paper"
    totals = BackfillSummary()

    for sub_dir in _iter_sub_account_dirs(paper_root, sub_account):
        sub_id = sub_dir.name
        trades_path = sub_dir / "trades.json"
        perf_index = _PerfIndex(data_dir=data_dir, sub_account_id=sub_id)

        sub_summary = _backfill_one_file(
            trades_path=trades_path,
            sub_account_id=sub_id,
            perf_index=perf_index,
            dry_run=dry_run,
        )

        prefix = "[dry-run] " if dry_run else ""
        skipped = (
            sub_summary.skipped_no_perf
            + sub_summary.skipped_perf_unset
            + sub_summary.skipped_perf_missing
        )
        logger.info(
            "%sBackfilled SL/TP for %d open paper trades in %s "
            "(%d rows examined, %d skipped)",
            prefix,
            sub_summary.backfilled,
            sub_id,
            sub_summary.examined,
            skipped,
        )
        totals.merge(sub_summary)

    return totals


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill missing SL/TP on legacy open paper trades from the "
            "linked PerformanceRecord. Idempotent and dry-run-supporting."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Preview the backfill without writing anything. Per-sub-account "
            "INFO summaries still appear so the operator can review counts."
        ),
    )
    parser.add_argument(
        "--sub-account",
        type=str,
        default=None,
        help=(
            "Restrict the backfill to a single sub-account id (e.g. "
            "``rsi_15m``). Default: process every sub-account under "
            "``<DATA_DIR>/trades/paper/``."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code (always ``0``).

    Args:
        argv: Optional argv override; tests pass a list to avoid
            depending on the real ``sys.argv``.

    Returns:
        ``0`` on success. Empty ledgers are not an error — a freshly
        deployed Fly machine with no paper trades is a valid state.
    """
    args = _build_parser().parse_args(argv)
    settings = get_settings()

    totals = backfill_paper_sl_tp(
        data_dir=settings.data_dir,
        sub_account=args.sub_account,
        dry_run=args.dry_run,
    )

    prefix = "[dry-run] " if args.dry_run else ""
    skipped_total = (
        totals.skipped_no_perf + totals.skipped_perf_unset + totals.skipped_perf_missing
    )
    logger.info(
        "%sTotal: backfilled %d open paper trades across all sub-accounts "
        "(%d examined, %d already set, %d skipped: "
        "no_perf=%d, perf_unset=%d, perf_missing=%d)",
        prefix,
        totals.backfilled,
        totals.examined,
        totals.already_set,
        skipped_total,
        totals.skipped_no_perf,
        totals.skipped_perf_unset,
        totals.skipped_perf_missing,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

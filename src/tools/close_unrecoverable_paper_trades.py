"""Operator CLI: close ``unrecoverable`` open paper trades (runtime-reconciliation §2).

The runtime-reconciliation health check classifies open paper-trade
rows that are missing one or more of ``entry_price`` / ``side`` /
``size`` / ``symbol`` as ``unrecoverable`` — the monitor loop cannot
mark them to market and cannot price a close, so they accumulate as
``MONITOR_ERRORED:orphan_open_trade`` events forever. There is no
automatic recovery path; the operator runs this tool to close those
rows with ``status="closed"``, ``close_reason="reconciliation_close"``,
and ``exit_price=None``.

Per the 2026-05-13 spec resolution, each closed row also generates a
**synthetic** ``PerformanceRecord`` so the feedback-loop counters
don't silently lose the trade. The synthetic record is tagged with
``synthetic=True`` and ``reconciliation_close=True`` keys on disk so
future analytics can distinguish reconciliation-generated outcomes
from real trade outcomes; both flags are dropped on the load path's
Pydantic re-hydration (extra="ignore" by default) but persist on
disk for downstream analytics.

Usage::

    # Preview without writing anything (recommended first):
    python -m src.tools.close_unrecoverable_paper_trades --dry-run

    # Actually close every ``unrecoverable`` open trade:
    python -m src.tools.close_unrecoverable_paper_trades

    # Restrict to a single sub-account:
    python -m src.tools.close_unrecoverable_paper_trades --sub-account rsi_15m

Idempotent — a re-run after a successful pass is a no-op because the
rows are already ``status="closed"``.

Related Requirements:
- FR-029: Active Trading (operator-visible repair flow).
- NFR-007: Trading History Storage.
- NFR-008: Asset/PnL History (mode separation).
"""

from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.config import get_settings
from src.logger import get_logger
from src.runtime.activity_log import ActivityEventType, ActivityLog
from src.runtime.reconciliation import (
    OpenTradeState,
    _load_perf_record_ids,
    classify_open_trade,
)
from src.utils.io import atomic_write_text
from src.utils.time import now_utc

logger = get_logger("crypto_master.tools.close_unrecoverable_paper_trades")


# Default sentinel used when writing the synthetic PerformanceRecord.
# A real PerformanceRecord requires non-null Decimal entry/SL/TP
# (FR-005 schema), but an ``unrecoverable`` trade by definition is
# missing one or more of those. We persist ``Decimal("0")`` so the
# row deserializes cleanly on every consumer; the on-disk
# ``synthetic`` + ``reconciliation_close`` flags are what readers
# should branch on, not the price fields.
_RECONCILIATION_ZERO_PRICE = "0"


@dataclass
class CloseSummary:
    """Per-sub-account counters describing one close pass.

    Attributes:
        examined: Total open rows inspected (any classification).
        closed: Rows newly transitioned to ``status="closed"`` with
            ``close_reason="reconciliation_close"``.
        skipped_not_unrecoverable: Open rows whose classification was
            not ``unrecoverable`` and so were left alone.
        synthetic_records_written: Synthetic ``PerformanceRecord``
            files appended (one per closed row, unless the row had no
            ``technique_name`` we could infer — see CLI docs).
    """

    examined: int = 0
    closed: int = 0
    skipped_not_unrecoverable: int = 0
    synthetic_records_written: int = 0
    # Per-row trace for the activity-event emitter.
    closed_rows: list[dict[str, object]] = field(default_factory=list)

    def merge(self, other: CloseSummary) -> None:
        self.examined += other.examined
        self.closed += other.closed
        self.skipped_not_unrecoverable += other.skipped_not_unrecoverable
        self.synthetic_records_written += other.synthetic_records_written
        self.closed_rows.extend(other.closed_rows)


def _iter_sub_account_dirs(
    paper_root: Path,
    sub_account: str | None,
) -> list[Path]:
    if sub_account is not None:
        return [paper_root / sub_account]
    if not paper_root.exists():
        return []
    return sorted(d for d in paper_root.iterdir() if d.is_dir())


def _write_synthetic_perf_record(
    data_dir: Path,
    sub_account_id: str,
    row: dict[str, object],
    closed_at: datetime,
) -> str | None:
    """Append a synthetic ``PerformanceRecord``-shaped row.

    Returns the synthetic record's id on success, ``None`` if the row
    didn't carry enough hints to choose a technique directory. We use
    a raw JSON write rather than ``PerformanceTracker.save_record`` so
    we can keep the ``synthetic=True`` / ``reconciliation_close=True``
    flags on disk (the strict ``PerformanceRecord`` model would drop
    them on round-trip).
    """
    technique_name = _infer_technique_name(row)
    if technique_name is None:
        logger.warning(
            "Cannot synthesize perf record for trade %s in %s: "
            "no technique hint on row",
            row.get("id"),
            sub_account_id,
        )
        return None

    technique_dir = data_dir / "performance" / sub_account_id / technique_name
    technique_dir.mkdir(parents=True, exist_ok=True)
    records_path = technique_dir / "records.json"

    if records_path.exists():
        try:
            with open(records_path, encoding="utf-8") as f:
                existing = json.load(f)
            if not isinstance(existing, list):
                existing = []
        except (json.JSONDecodeError, OSError):
            existing = []
    else:
        existing = []

    record_id = str(uuid.uuid4())
    entry_price = _str_or_default(row.get("entry_price"), _RECONCILIATION_ZERO_PRICE)
    stop_loss = _str_or_default(row.get("stop_loss"), _RECONCILIATION_ZERO_PRICE)
    take_profit = _str_or_default(row.get("take_profit"), _RECONCILIATION_ZERO_PRICE)
    side = row.get("side") if row.get("side") in {"long", "short"} else "long"
    symbol = row.get("symbol") if isinstance(row.get("symbol"), str) else "UNKNOWN"
    timeframe = row.get("timeframe") if isinstance(row.get("timeframe"), str) else "1h"

    synthetic_row: dict[str, object] = {
        "id": record_id,
        "technique_name": technique_name,
        "technique_version": str(row.get("technique_version", "reconciliation")),
        "symbol": symbol,
        "timeframe": timeframe,
        "signal": side,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "confidence": 0.0,
        "analysis_timestamp": closed_at.isoformat(),
        "outcome": "breakeven",
        "exit_price": None,
        "exit_timestamp": closed_at.isoformat(),
        "pnl_percent": 0.0,
        "quantity": _str_or_default(row.get("entry_quantity"), None),
        "leverage": _coerce_leverage(row.get("leverage")),
        "fees": "0",
        "actual_entry_price": None,
        "actual_exit_price": None,
        "mode": "paper",
        "trade_id": row.get("id"),
        "sub_account_id": sub_account_id,
        "profile_name": row.get("profile_name"),
        # Synthetic markers — first-class fields on
        # ``PerformanceRecord`` (Q2 follow-up). ``TechniquePerformance.
        # from_records`` excludes ``synthetic=True`` rows from win-rate
        # / Sharpe / expectancy / profit-factor so reconciliation
        # closes don't pollute CON-003 promotion gating, while still
        # reporting them under ``synthetic_count``.
        "synthetic": True,
        "reconciliation_close": True,
    }
    existing.append(synthetic_row)
    atomic_write_text(
        records_path,
        json.dumps(existing, indent=2, default=str),
    )
    return record_id


def _infer_technique_name(row: dict[str, object]) -> str | None:
    """Pick a technique directory for the synthetic record.

    Preference order:
      1. Explicit ``technique_name`` on the row (rare — paper-trade
         rows don't usually carry one, but tests / hand-edited rows
         can).
      2. ``"_reconciliation"`` as a top-level catch-all when the row
         carries nothing usable. Using a sentinel directory keeps
         these synthetic rows out of every real strategy's
         performance aggregate so the technique dashboards stay clean.
    """
    technique = row.get("technique_name")
    if isinstance(technique, str) and technique:
        return technique
    return "_reconciliation"


def _str_or_default(value: object, default: str | None) -> str | None:
    if value is None:
        return default
    return str(value)


def _coerce_leverage(value: object) -> int:
    """Best-effort coerce a row's ``leverage`` field to a positive int.

    Falls back to ``1`` on missing / unparseable values so the synthetic
    record always has a valid leverage column.
    """
    if value is None:
        return 1
    try:
        leverage = int(str(value))
    except (TypeError, ValueError):
        return 1
    return leverage if leverage > 0 else 1


def _close_one_file(
    trades_path: Path,
    sub_account_id: str,
    data_dir: Path,
    perf_record_ids: set[str],
    dry_run: bool,
) -> CloseSummary:
    """Close every ``unrecoverable`` open row in one ``trades.json`` file."""
    summary = CloseSummary()
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
            "Unexpected ledger shape at %s (expected list); skipping", trades_path
        )
        return summary

    mutated = False
    closed_at = now_utc()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("status") != "open":
            continue
        summary.examined += 1

        classification = classify_open_trade(row, perf_record_ids)
        if classification.state != OpenTradeState.UNRECOVERABLE.value:
            summary.skipped_not_unrecoverable += 1
            continue

        trade_id = str(row.get("id", "<unknown>"))
        symbol_val = row.get("symbol")
        symbol = symbol_val if isinstance(symbol_val, str) else None
        synthetic_id: str | None = None
        if not dry_run:
            row["status"] = "closed"
            row["close_reason"] = "reconciliation_close"
            row["exit_price"] = None
            row["exit_quantity"] = row.get("entry_quantity")
            row["exit_time"] = closed_at.isoformat()
            row["pnl"] = None
            row["pnl_percent"] = None
            mutated = True

            synthetic_id = _write_synthetic_perf_record(
                data_dir=data_dir,
                sub_account_id=sub_account_id,
                row=row,
                closed_at=closed_at,
            )
            if synthetic_id is not None:
                summary.synthetic_records_written += 1
                # Link the trade row to the new perf record so the
                # ledger row remains discoverable from the perf side.
                if not row.get("performance_record_id"):
                    row["performance_record_id"] = synthetic_id

        summary.closed += 1
        summary.closed_rows.append(
            {
                "trade_id": trade_id,
                "sub_account_id": sub_account_id,
                "symbol": symbol,
                "missing_fields": list(classification.missing_fields),
                "performance_record_id": synthetic_id,
            }
        )

    if mutated and not dry_run:
        atomic_write_text(
            trades_path,
            json.dumps(rows, indent=2, default=str),
        )

    return summary


def close_unrecoverable_paper_trades(
    data_dir: Path,
    sub_account: str | None = None,
    dry_run: bool = False,
    *,
    activity_log: ActivityLog | None = None,
) -> CloseSummary:
    """Walk paper sub-accounts and close every ``unrecoverable`` open row.

    Args:
        data_dir: Engine data root (``Settings.data_dir``).
        sub_account: Optional sub-account id filter. When set, only
            that sub-account's ledger is touched.
        dry_run: When ``True``, compute the summary counts but write
            nothing back to disk.
        activity_log: Optional :class:`ActivityLog`. When supplied and
            ``dry_run`` is ``False``, one
            :attr:`ActivityEventType.RECONCILIATION_CLOSED_UNRECOVERABLE`
            event is appended per closed row. Defaults to ``None``
            so tests can opt out; ``main`` wires the live engine log.

    Returns:
        Aggregated :class:`CloseSummary`.
    """
    paper_root = data_dir / "trades" / "paper"
    totals = CloseSummary()

    for sub_dir in _iter_sub_account_dirs(paper_root, sub_account):
        sub_id = sub_dir.name
        trades_path = sub_dir / "trades.json"
        perf_ids = _load_perf_record_ids(data_dir, sub_id)
        sub_summary = _close_one_file(
            trades_path=trades_path,
            sub_account_id=sub_id,
            data_dir=data_dir,
            perf_record_ids=perf_ids,
            dry_run=dry_run,
        )
        prefix = "[dry-run] " if dry_run else ""
        logger.info(
            "%sClosed %d unrecoverable paper trade(s) in %s "
            "(%d examined, %d skipped)",
            prefix,
            sub_summary.closed,
            sub_id,
            sub_summary.examined,
            sub_summary.skipped_not_unrecoverable,
        )
        totals.merge(sub_summary)

    if not dry_run and activity_log is not None:
        for entry in totals.closed_rows:
            symbol = entry.get("symbol")
            activity_log.append(
                ActivityEventType.RECONCILIATION_CLOSED_UNRECOVERABLE,
                (
                    f"Closed unrecoverable paper trade {entry.get('trade_id')} "
                    f"({symbol or 'no-symbol'})"
                ),
                details={
                    "trade_id": entry.get("trade_id"),
                    "sub_account_id": entry.get("sub_account_id"),
                    "symbol": symbol,
                    "missing_fields": entry.get("missing_fields", []),
                    "performance_record_id": entry.get("performance_record_id"),
                },
            )

    return totals


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Close 'unrecoverable' open paper trades — rows missing one of "
            "entry_price / side / size / symbol — and write a synthetic "
            "PerformanceRecord for each so feedback-loop counters stay correct."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Preview the close without writing anything. Per-sub-account INFO "
            "summaries still appear so the operator can review counts."
        ),
    )
    parser.add_argument(
        "--sub-account",
        type=str,
        default=None,
        help=(
            "Restrict the close to a single sub-account id. Default: process "
            "every sub-account under <DATA_DIR>/trades/paper/."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code (always ``0``)."""
    args = _build_parser().parse_args(argv)
    settings = get_settings()

    # On live runs we always emit the activity event so the dashboard
    # timeline confirms the operator's manual close.
    activity_log = ActivityLog(data_dir=settings.data_dir)

    totals = close_unrecoverable_paper_trades(
        data_dir=settings.data_dir,
        sub_account=args.sub_account,
        dry_run=args.dry_run,
        activity_log=activity_log,
    )

    prefix = "[dry-run] " if args.dry_run else ""
    logger.info(
        "%sTotal: closed %d unrecoverable paper trade(s) "
        "(%d examined, %d skipped, %d synthetic perf records written)",
        prefix,
        totals.closed,
        totals.examined,
        totals.skipped_not_unrecoverable,
        totals.synthetic_records_written,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

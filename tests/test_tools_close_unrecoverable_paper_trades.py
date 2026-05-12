"""Tests for ``src.tools.close_unrecoverable_paper_trades`` (runtime-reconciliation §2)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from src.runtime.activity_log import ActivityEventType, ActivityLog
from src.tools.close_unrecoverable_paper_trades import (
    CloseSummary,
    close_unrecoverable_paper_trades,
    main,
)

# =============================================================================
# Helpers
# =============================================================================


def _seed_ledger(data_dir: Path, sub_account_id: str, rows: list[dict]) -> Path:
    path = data_dir / "trades" / "paper" / sub_account_id / "trades.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2))
    return path


def _row(
    *,
    trade_id: str = "t1",
    symbol: str | None = "BTC/USDT",
    side: str | None = "long",
    entry_price: str | None = "50000",
    entry_quantity: str | None = "0.1",
    leverage: int = 10,
    stop_loss: str | None = "49500",
    take_profit: str | None = "51500",
    status: str = "open",
    technique_name: str | None = None,
    performance_record_id: str | None = None,
) -> dict:
    row: dict = {
        "id": trade_id,
        "sub_account_id": "default",
        "symbol": symbol,
        "side": side,
        "entry_price": entry_price,
        "entry_quantity": entry_quantity,
        "leverage": leverage,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "performance_record_id": performance_record_id,
        "status": status,
        "mode": "paper",
    }
    if technique_name is not None:
        row["technique_name"] = technique_name
    return row


def _read_ledger(path: Path) -> list[dict]:
    return json.loads(path.read_text())


# =============================================================================
# Tests
# =============================================================================


def test_close_closes_unrecoverable_row(tmp_path: Path) -> None:
    """An ``unrecoverable`` row (missing symbol) transitions to closed."""
    path = _seed_ledger(
        tmp_path,
        "default",
        [_row(trade_id="bad", symbol=None)],
    )

    summary = close_unrecoverable_paper_trades(data_dir=tmp_path)

    assert summary.closed == 1
    rows = _read_ledger(path)
    assert rows[0]["status"] == "closed"
    assert rows[0]["close_reason"] == "reconciliation_close"
    assert rows[0]["exit_price"] is None


def test_close_skips_monitorable_row(tmp_path: Path) -> None:
    """A fully-populated monitorable row is left untouched."""
    path = _seed_ledger(
        tmp_path,
        "default",
        [_row(trade_id="ok")],
    )
    before = path.read_text()

    summary = close_unrecoverable_paper_trades(data_dir=tmp_path)

    assert summary.closed == 0
    assert summary.skipped_not_unrecoverable == 1
    assert path.read_text() == before


def test_close_skips_degraded_row(tmp_path: Path) -> None:
    """A ``degraded`` row (missing SL/TP) is NOT closed — it has a backfill path."""
    _seed_ledger(
        tmp_path,
        "default",
        [_row(trade_id="deg", stop_loss=None, take_profit=None)],
    )

    summary = close_unrecoverable_paper_trades(data_dir=tmp_path)

    assert summary.closed == 0
    assert summary.skipped_not_unrecoverable == 1


def test_close_dry_run_does_not_mutate(tmp_path: Path) -> None:
    """``--dry-run`` counts the row but leaves the ledger byte-identical."""
    path = _seed_ledger(
        tmp_path,
        "default",
        [_row(trade_id="bad", entry_price=None)],
    )
    before = path.read_text()

    summary = close_unrecoverable_paper_trades(data_dir=tmp_path, dry_run=True)

    # Counted as closeable but not actually mutated.
    assert summary.closed == 1
    assert path.read_text() == before


def test_close_writes_synthetic_perf_record_with_flags(tmp_path: Path) -> None:
    """Closed row generates a synthetic ``PerformanceRecord`` on disk.

    Resolution 2026-05-13: write synthetic record so feedback-loop
    counters don't silently lose the trade; flagged via
    ``synthetic=True`` / ``reconciliation_close=True`` extras.
    """
    _seed_ledger(
        tmp_path,
        "default",
        [_row(trade_id="bad", entry_price=None)],
    )

    summary = close_unrecoverable_paper_trades(data_dir=tmp_path)

    assert summary.synthetic_records_written == 1
    perf_path = (
        tmp_path / "performance" / "default" / "_reconciliation" / "records.json"
    )
    assert perf_path.exists()
    rows = json.loads(perf_path.read_text())
    assert len(rows) == 1
    record = rows[0]
    # The synthetic flags are the load-time signal future analytics
    # use to distinguish reconciliation-generated outcomes.
    assert record["synthetic"] is True
    assert record["reconciliation_close"] is True
    assert record["mode"] == "paper"
    assert record["outcome"] == "breakeven"
    # Trade-id linkage is preserved so the perf row can be joined
    # back to the trade ledger entry.
    assert record["trade_id"] == "bad"


def test_close_synthetic_record_uses_technique_name_when_provided(
    tmp_path: Path,
) -> None:
    """When the row carries a ``technique_name`` hint we use that directory."""
    _seed_ledger(
        tmp_path,
        "default",
        [
            _row(
                trade_id="bad",
                entry_price=None,
                technique_name="rsi_15m",
            )
        ],
    )

    close_unrecoverable_paper_trades(data_dir=tmp_path)

    perf_path = (
        tmp_path / "performance" / "default" / "rsi_15m" / "records.json"
    )
    assert perf_path.exists()


def test_close_emits_activity_event_per_row(tmp_path: Path) -> None:
    """One ``RECONCILIATION_CLOSED_UNRECOVERABLE`` event per closed row."""
    _seed_ledger(
        tmp_path,
        "default",
        [
            _row(trade_id="bad-1", symbol=None),
            _row(trade_id="bad-2", side=None),
            _row(trade_id="ok-1"),
        ],
    )
    activity_log = ActivityLog(path=tmp_path / "activity.jsonl")

    close_unrecoverable_paper_trades(
        data_dir=tmp_path,
        activity_log=activity_log,
    )

    events = activity_log.filter(
        event_type=ActivityEventType.RECONCILIATION_CLOSED_UNRECOVERABLE
    )
    assert len(events) == 2
    trade_ids = {event.details["trade_id"] for event in events}
    assert trade_ids == {"bad-1", "bad-2"}


def test_close_dry_run_does_not_emit_activity_event(tmp_path: Path) -> None:
    """Dry-run must not write activity events (mirrors backfill-tool contract)."""
    _seed_ledger(
        tmp_path,
        "default",
        [_row(trade_id="bad", symbol=None)],
    )
    activity_log = ActivityLog(path=tmp_path / "activity.jsonl")

    close_unrecoverable_paper_trades(
        data_dir=tmp_path,
        dry_run=True,
        activity_log=activity_log,
    )

    events = activity_log.filter(
        event_type=ActivityEventType.RECONCILIATION_CLOSED_UNRECOVERABLE
    )
    assert events == []


def test_close_sub_account_filter_restricts_walk(tmp_path: Path) -> None:
    """``--sub-account`` only touches the named sub-account ledger."""
    path_a = _seed_ledger(
        tmp_path, "alpha", [_row(trade_id="a-bad", symbol=None)]
    )
    path_b = _seed_ledger(
        tmp_path, "beta", [_row(trade_id="b-bad", symbol=None)]
    )
    before_b = path_b.read_text()

    summary = close_unrecoverable_paper_trades(
        data_dir=tmp_path, sub_account="alpha"
    )

    assert summary.closed == 1
    rows_a = _read_ledger(path_a)
    rows_b = _read_ledger(path_b)
    assert rows_a[0]["status"] == "closed"
    assert rows_b[0]["status"] == "open"  # beta untouched
    assert path_b.read_text() == before_b


def test_close_idempotent_on_rerun(tmp_path: Path) -> None:
    """Re-running after a successful close is a no-op (rows are closed already)."""
    path = _seed_ledger(
        tmp_path,
        "default",
        [_row(trade_id="bad", symbol=None)],
    )
    close_unrecoverable_paper_trades(data_dir=tmp_path)
    after_first = path.read_text()

    second = close_unrecoverable_paper_trades(data_dir=tmp_path)

    assert second.closed == 0
    assert path.read_text() == after_first


def test_main_cli_invokes_helper_with_settings_data_dir(tmp_path: Path) -> None:
    """The CLI entry point reads ``Settings.data_dir`` and forwards flags."""
    with (
        patch(
            "src.tools.close_unrecoverable_paper_trades."
            "close_unrecoverable_paper_trades"
        ) as mock_close,
        patch(
            "src.tools.close_unrecoverable_paper_trades.get_settings"
        ) as mock_get_settings,
    ):
        mock_get_settings.return_value.data_dir = tmp_path
        mock_close.return_value = CloseSummary()

        rc = main(["--dry-run", "--sub-account", "rsi_15m"])

    assert rc == 0
    mock_close.assert_called_once()
    kwargs = mock_close.call_args.kwargs
    assert kwargs["data_dir"] == tmp_path
    assert kwargs["sub_account"] == "rsi_15m"
    assert kwargs["dry_run"] is True
    assert kwargs["activity_log"] is not None

"""Tests for the operator CLI ``src.tools.backfill_paper_sl_tp`` (DEBT-058)."""

from __future__ import annotations

import json
import logging
import time
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from src.strategy.performance import (
    PerformanceRecord,
    PerformanceTracker,
    TradeHistory,
    TradeHistoryTracker,
)
from src.tools.backfill_paper_sl_tp import (
    BackfillSummary,
    backfill_paper_sl_tp,
    main,
)

# =============================================================================
# Helpers
# =============================================================================


def _seed_perf_record(
    data_dir: Path,
    sub_account_id: str,
    technique_name: str = "tech_a",
    *,
    stop_loss: Decimal | None = Decimal("49500"),
    take_profit: Decimal | None = Decimal("51500"),
) -> PerformanceRecord:
    """Persist a single ``PerformanceRecord`` and return it."""
    tracker = PerformanceTracker(
        data_dir=data_dir / "performance",
        sub_account_id=sub_account_id,
    )
    # ``PerformanceRecord`` requires non-null SL/TP; for the
    # "perf record exists but bounds are null" test we have to write
    # the record then null the columns on disk afterwards.
    record = PerformanceRecord(
        technique_name=technique_name,
        technique_version="1.0.0",
        symbol="BTC/USDT",
        timeframe="1h",
        signal="long",
        entry_price=Decimal("50000"),
        stop_loss=stop_loss if stop_loss is not None else Decimal("49500"),
        take_profit=take_profit if take_profit is not None else Decimal("51500"),
        confidence=0.8,
        mode="paper",
        sub_account_id=sub_account_id,
    )
    tracker.save_record(record)

    if stop_loss is None or take_profit is None:
        # Simulate a perf record whose bounds are null on disk.
        path = (
            data_dir / "performance" / sub_account_id / technique_name / "records.json"
        )
        rows = json.loads(path.read_text())
        for row in rows:
            if row["id"] == record.id:
                if stop_loss is None:
                    row["stop_loss"] = None
                if take_profit is None:
                    row["take_profit"] = None
        path.write_text(json.dumps(rows, indent=2))

    return record


def _seed_paper_trade(
    data_dir: Path,
    sub_account_id: str,
    *,
    performance_record_id: str | None,
    status: str = "open",
    stop_loss: Decimal | None = None,
    take_profit: Decimal | None = None,
    symbol: str = "BTC/USDT",
) -> TradeHistory:
    """Persist a single paper ``TradeHistory`` row."""
    tracker = TradeHistoryTracker(
        data_dir=data_dir / "trades",
        sub_account_id=sub_account_id,
    )
    trade = tracker.open_trade(
        symbol=symbol,
        side="long",
        entry_price=Decimal("50000"),
        entry_quantity=Decimal("0.1"),
        mode="paper",
        leverage=10,
        performance_record_id=performance_record_id,
        sub_account_id=sub_account_id,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )
    if status != "open":
        # Mutate status on disk; ``open_trade`` always writes ``open``.
        path = data_dir / "trades" / "paper" / sub_account_id / "trades.json"
        rows = json.loads(path.read_text())
        for row in rows:
            if row["id"] == trade.id:
                row["status"] = status
        path.write_text(json.dumps(rows, indent=2))
    return trade


def _read_trade_row(data_dir: Path, sub_account_id: str, trade_id: str) -> dict:
    path = data_dir / "trades" / "paper" / sub_account_id / "trades.json"
    rows = json.loads(path.read_text())
    for row in rows:
        if row["id"] == trade_id:
            return row
    raise AssertionError(f"trade {trade_id} not found in {path}")


# =============================================================================
# Tests
# =============================================================================


def test_backfill_populates_open_trade_with_sl_tp_from_perf(
    tmp_path: Path,
) -> None:
    """Open trade with null SL/TP and a matching perf record gets rewritten."""
    record = _seed_perf_record(tmp_path, "default")
    trade = _seed_paper_trade(tmp_path, "default", performance_record_id=record.id)

    summary = backfill_paper_sl_tp(data_dir=tmp_path)

    assert summary.backfilled == 1
    assert summary.examined == 1
    row = _read_trade_row(tmp_path, "default", trade.id)
    assert row["stop_loss"] == "49500"
    assert row["take_profit"] == "51500"


def test_backfill_skips_already_set(tmp_path: Path) -> None:
    """Open trade that already has SL/TP is not rewritten."""
    record = _seed_perf_record(tmp_path, "default")
    trade = _seed_paper_trade(
        tmp_path,
        "default",
        performance_record_id=record.id,
        stop_loss=Decimal("48000"),
        take_profit=Decimal("52000"),
    )
    path = tmp_path / "trades" / "paper" / "default" / "trades.json"
    before_mtime = path.stat().st_mtime_ns
    before_content = path.read_text()

    # Sleep ensures any rewrite would change mtime (some FS have ns
    # resolution, but the safer signal is content equality below).
    time.sleep(0.01)

    summary = backfill_paper_sl_tp(data_dir=tmp_path)

    assert summary.already_set == 1
    assert summary.backfilled == 0
    assert path.read_text() == before_content
    assert path.stat().st_mtime_ns == before_mtime
    # Also confirm the existing bounds are untouched.
    row = _read_trade_row(tmp_path, "default", trade.id)
    assert row["stop_loss"] == "48000"
    assert row["take_profit"] == "52000"


def test_backfill_skips_closed_trades(tmp_path: Path) -> None:
    """Closed trade with null SL/TP is ignored (no warning, no rewrite)."""
    record = _seed_perf_record(tmp_path, "default")
    trade = _seed_paper_trade(
        tmp_path,
        "default",
        performance_record_id=record.id,
        status="closed",
    )

    summary = backfill_paper_sl_tp(data_dir=tmp_path)

    assert summary.backfilled == 0
    assert summary.skipped_no_perf == 0
    row = _read_trade_row(tmp_path, "default", trade.id)
    assert row["stop_loss"] is None
    assert row["take_profit"] is None


def test_backfill_skips_no_performance_record_id(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Open trade without performance_record_id logs a warning and is left alone."""
    trade = _seed_paper_trade(tmp_path, "default", performance_record_id=None)

    target_logger = logging.getLogger("crypto_master.tools.backfill_paper_sl_tp")
    target_logger.addHandler(caplog.handler)
    target_logger.setLevel(logging.WARNING)
    try:
        summary = backfill_paper_sl_tp(data_dir=tmp_path)
    finally:
        target_logger.removeHandler(caplog.handler)

    assert summary.skipped_no_perf == 1
    assert summary.backfilled == 0
    row = _read_trade_row(tmp_path, "default", trade.id)
    assert row["stop_loss"] is None
    assert any(
        "no performance_record_id" in rec.getMessage() and trade.id in rec.getMessage()
        for rec in caplog.records
    )


def test_backfill_skips_perf_record_with_null_sl_tp(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Open trade linked to a perf record whose bounds are also null is skipped."""
    record = _seed_perf_record(tmp_path, "default", stop_loss=None, take_profit=None)
    trade = _seed_paper_trade(tmp_path, "default", performance_record_id=record.id)

    target_logger = logging.getLogger("crypto_master.tools.backfill_paper_sl_tp")
    target_logger.addHandler(caplog.handler)
    target_logger.setLevel(logging.WARNING)
    try:
        summary = backfill_paper_sl_tp(data_dir=tmp_path)
    finally:
        target_logger.removeHandler(caplog.handler)

    assert summary.skipped_perf_unset == 1
    assert summary.backfilled == 0
    row = _read_trade_row(tmp_path, "default", trade.id)
    assert row["stop_loss"] is None
    assert any(
        "stop_loss/take_profit are also null" in rec.getMessage()
        and trade.id in rec.getMessage()
        for rec in caplog.records
    )


def test_backfill_skips_perf_record_not_found(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Open trade pointing at a missing perf record id is skipped with a warning."""
    trade = _seed_paper_trade(
        tmp_path,
        "default",
        performance_record_id="00000000-0000-0000-0000-000000000000",
    )

    target_logger = logging.getLogger("crypto_master.tools.backfill_paper_sl_tp")
    target_logger.addHandler(caplog.handler)
    target_logger.setLevel(logging.WARNING)
    try:
        summary = backfill_paper_sl_tp(data_dir=tmp_path)
    finally:
        target_logger.removeHandler(caplog.handler)

    assert summary.skipped_perf_missing == 1
    assert summary.backfilled == 0
    row = _read_trade_row(tmp_path, "default", trade.id)
    assert row["stop_loss"] is None
    assert any(
        "was not found" in rec.getMessage() and trade.id in rec.getMessage()
        for rec in caplog.records
    )


def test_backfill_dry_run_does_not_write(tmp_path: Path) -> None:
    """``--dry-run`` computes the summary but leaves the ledger untouched."""
    record = _seed_perf_record(tmp_path, "default")
    trade = _seed_paper_trade(tmp_path, "default", performance_record_id=record.id)
    path = tmp_path / "trades" / "paper" / "default" / "trades.json"
    before_content = path.read_text()

    summary = backfill_paper_sl_tp(data_dir=tmp_path, dry_run=True)

    # Counts still reflect what *would* have happened.
    assert summary.backfilled == 1
    # File on disk is byte-for-byte identical.
    assert path.read_text() == before_content
    row = _read_trade_row(tmp_path, "default", trade.id)
    assert row["stop_loss"] is None
    assert row["take_profit"] is None


def test_backfill_sub_account_filter(tmp_path: Path) -> None:
    """``--sub-account`` restricts the walk to one ledger only."""
    rec_a = _seed_perf_record(tmp_path, "alpha")
    rec_b = _seed_perf_record(tmp_path, "beta")
    trade_a = _seed_paper_trade(tmp_path, "alpha", performance_record_id=rec_a.id)
    trade_b = _seed_paper_trade(tmp_path, "beta", performance_record_id=rec_b.id)

    summary = backfill_paper_sl_tp(data_dir=tmp_path, sub_account="alpha")

    assert summary.backfilled == 1
    # alpha was rewritten, beta was not touched at all.
    row_a = _read_trade_row(tmp_path, "alpha", trade_a.id)
    row_b = _read_trade_row(tmp_path, "beta", trade_b.id)
    assert row_a["stop_loss"] == "49500"
    assert row_b["stop_loss"] is None


def test_backfill_idempotent_on_rerun(tmp_path: Path) -> None:
    """A second pass over already-backfilled data is a no-op."""
    record = _seed_perf_record(tmp_path, "default")
    _seed_paper_trade(tmp_path, "default", performance_record_id=record.id)

    first = backfill_paper_sl_tp(data_dir=tmp_path)
    assert first.backfilled == 1

    path = tmp_path / "trades" / "paper" / "default" / "trades.json"
    after_first = path.read_text()
    after_first_mtime = path.stat().st_mtime_ns
    time.sleep(0.01)

    second = backfill_paper_sl_tp(data_dir=tmp_path)
    assert second.backfilled == 0
    assert second.already_set == 1
    assert path.read_text() == after_first
    assert path.stat().st_mtime_ns == after_first_mtime


def test_backfill_summary_counts_match_actions(tmp_path: Path) -> None:
    """Every counter in :class:`BackfillSummary` increments correctly."""
    # rec_full: a healthy perf record we can backfill from.
    rec_full = _seed_perf_record(tmp_path, "default")
    # rec_null: perf record with null bounds (skipped_perf_unset).
    rec_null = _seed_perf_record(
        tmp_path,
        "default",
        technique_name="tech_b",
        stop_loss=None,
        take_profit=None,
    )

    # 1 backfill candidate (open + null bounds + valid perf id).
    _seed_paper_trade(tmp_path, "default", performance_record_id=rec_full.id)
    # 1 already-set (open + bounds present + valid perf id).
    _seed_paper_trade(
        tmp_path,
        "default",
        performance_record_id=rec_full.id,
        stop_loss=Decimal("48000"),
        take_profit=Decimal("52000"),
    )
    # 1 closed (ignored entirely; counted in examined only).
    _seed_paper_trade(
        tmp_path,
        "default",
        performance_record_id=rec_full.id,
        status="closed",
    )
    # 1 skipped_no_perf (open + null bounds + missing perf id).
    _seed_paper_trade(tmp_path, "default", performance_record_id=None)
    # 1 skipped_perf_unset (perf record has null bounds).
    _seed_paper_trade(tmp_path, "default", performance_record_id=rec_null.id)
    # 1 skipped_perf_missing (perf id not present in records.json).
    _seed_paper_trade(
        tmp_path,
        "default",
        performance_record_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
    )

    summary = backfill_paper_sl_tp(data_dir=tmp_path)

    assert summary.examined == 6
    assert summary.backfilled == 1
    assert summary.already_set == 1
    assert summary.skipped_no_perf == 1
    assert summary.skipped_perf_unset == 1
    assert summary.skipped_perf_missing == 1


def test_backfill_atomic_write(tmp_path: Path) -> None:
    """Backfill rewrites go through ``atomic_write_text`` (no half-written file)."""
    record = _seed_perf_record(tmp_path, "default")
    _seed_paper_trade(tmp_path, "default", performance_record_id=record.id)

    with patch("src.tools.backfill_paper_sl_tp.atomic_write_text") as mock_write:
        summary = backfill_paper_sl_tp(data_dir=tmp_path)

    assert summary.backfilled == 1
    assert mock_write.call_count == 1
    call_args = mock_write.call_args
    assert (
        call_args.args[0] == tmp_path / "trades" / "paper" / "default" / "trades.json"
    )
    # Payload is valid JSON containing the populated bounds.
    payload = json.loads(call_args.args[1])
    assert any(
        row["stop_loss"] == "49500" and row["take_profit"] == "51500" for row in payload
    )


def test_main_invokes_backfill_with_settings_data_dir(
    tmp_path: Path,
) -> None:
    """The CLI entry point reads ``Settings.data_dir`` and forwards args."""
    with (
        patch("src.tools.backfill_paper_sl_tp.backfill_paper_sl_tp") as mock_backfill,
        patch("src.tools.backfill_paper_sl_tp.get_settings") as mock_get_settings,
    ):
        mock_get_settings.return_value.data_dir = tmp_path
        mock_backfill.return_value = BackfillSummary()

        rc = main([])

    assert rc == 0
    mock_backfill.assert_called_once_with(
        data_dir=tmp_path, sub_account=None, dry_run=False
    )


def test_main_passes_dry_run_and_sub_account_flags(tmp_path: Path) -> None:
    """``--dry-run`` and ``--sub-account`` flags wire through to the helper."""
    with (
        patch("src.tools.backfill_paper_sl_tp.backfill_paper_sl_tp") as mock_backfill,
        patch("src.tools.backfill_paper_sl_tp.get_settings") as mock_get_settings,
    ):
        mock_get_settings.return_value.data_dir = tmp_path
        mock_backfill.return_value = BackfillSummary()

        rc = main(["--dry-run", "--sub-account", "rsi_15m"])

    assert rc == 0
    mock_backfill.assert_called_once_with(
        data_dir=tmp_path, sub_account="rsi_15m", dry_run=True
    )


def test_main_handles_missing_paper_root(tmp_path: Path) -> None:
    """A data dir with no paper ledger yet returns cleanly with zero counts."""
    with patch("src.tools.backfill_paper_sl_tp.get_settings") as mock_get_settings:
        mock_get_settings.return_value.data_dir = tmp_path

        rc = main([])

    assert rc == 0

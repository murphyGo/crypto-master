"""Tests for the snapshot-pinned baseline dataset format (Phase 25.1 / DEBT-043).

Covers the CSV + JSON sidecar schema, round-trip integrity, schema
breach detection, freshness-policy semantics, and the Phase 21 UTC
contract on loaded metadata.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.backtest.snapshot import (
    DEFAULT_MAX_AGE_DAYS,
    FETCHER_VERSION,
    OHLCV_HEADER,
    Snapshot,
    SnapshotMetadata,
    SnapshotValidationError,
    baseline_directory,
    is_snapshot_fresh,
    load_snapshot,
    save_snapshot,
)
from src.models import OHLCV

# =============================================================================
# Fixtures
# =============================================================================


def _make_candles(n: int = 3) -> list[OHLCV]:
    """Build ``n`` synthetic OHLCV rows with deterministic values."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows: list[OHLCV] = []
    for i in range(n):
        rows.append(
            OHLCV(
                timestamp=base + timedelta(hours=i),
                open=Decimal("50000.10") + Decimal(i),
                high=Decimal("50200.20") + Decimal(i),
                low=Decimal("49800.30") + Decimal(i),
                close=Decimal("50100.40") + Decimal(i),
                volume=Decimal("1.5") + Decimal(i),
            )
        )
    return rows


def _make_metadata(
    candle_count: int = 3,
    fetched_at: datetime | None = None,
    first_timestamp: datetime | None = None,
    last_timestamp: datetime | None = None,
) -> SnapshotMetadata:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return SnapshotMetadata(
        symbol="BTC/USDT",
        timeframe="1h",
        source="binance",
        fetched_at=fetched_at or datetime(2026, 4, 30, tzinfo=timezone.utc),
        candle_count=candle_count,
        first_timestamp=first_timestamp or base,
        last_timestamp=last_timestamp or (base + timedelta(hours=candle_count - 1)),
        fetcher_version=FETCHER_VERSION,
    )


def _make_snapshot(n: int = 3) -> Snapshot:
    rows = _make_candles(n)
    metadata = _make_metadata(
        candle_count=n,
        first_timestamp=rows[0].timestamp,
        last_timestamp=rows[-1].timestamp,
    )
    return Snapshot(metadata=metadata, ohlcv=rows)


# =============================================================================
# Round-trip
# =============================================================================


def test_round_trip_save_then_load_preserves_data(tmp_path: Path) -> None:
    """save_snapshot → load_snapshot recovers the same Snapshot."""
    original = _make_snapshot(n=5)
    target = tmp_path / "BTCUSDT__1h"

    save_snapshot(original, target)
    loaded = load_snapshot(target)

    assert loaded.metadata == original.metadata
    assert loaded.ohlcv == original.ohlcv


def test_save_creates_expected_files(tmp_path: Path) -> None:
    snap = _make_snapshot()
    target = tmp_path / "BTCUSDT__1h"

    save_snapshot(snap, target)

    assert (target / "ohlcv.csv").exists()
    assert (target / "metadata.json").exists()


def test_save_csv_header_matches_spec(tmp_path: Path) -> None:
    """First CSV row must be the canonical header tuple."""
    snap = _make_snapshot()
    target = tmp_path / "BTCUSDT__1h"

    save_snapshot(snap, target)

    csv_text = (target / "ohlcv.csv").read_text(encoding="utf-8")
    first_line = csv_text.splitlines()[0]
    assert first_line == ",".join(OHLCV_HEADER)


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    """Nested target directories are created automatically."""
    snap = _make_snapshot()
    target = tmp_path / "nested" / "deeper" / "BTCUSDT__1h"

    save_snapshot(snap, target)

    assert (target / "ohlcv.csv").exists()


# =============================================================================
# Schema breach detection
# =============================================================================


def test_load_missing_metadata_raises(tmp_path: Path) -> None:
    target = tmp_path / "BTCUSDT__1h"
    target.mkdir()
    (target / "ohlcv.csv").write_text(",".join(OHLCV_HEADER) + "\n", encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="missing metadata.json"):
        load_snapshot(target)


def test_load_missing_csv_raises(tmp_path: Path) -> None:
    target = tmp_path / "BTCUSDT__1h"
    target.mkdir()
    metadata = _make_metadata(candle_count=0)
    (target / "metadata.json").write_text(metadata.model_dump_json(), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="missing ohlcv.csv"):
        load_snapshot(target)


def test_load_metadata_missing_required_field_raises(tmp_path: Path) -> None:
    """Pydantic validation error wraps to SnapshotValidationError."""
    snap = _make_snapshot()
    target = tmp_path / "BTCUSDT__1h"
    save_snapshot(snap, target)

    # Strip the ``symbol`` field — required by SnapshotMetadata.
    raw = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
    raw.pop("symbol")
    (target / "metadata.json").write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="failed schema validation"):
        load_snapshot(target)


def test_load_metadata_bad_json_raises(tmp_path: Path) -> None:
    snap = _make_snapshot()
    target = tmp_path / "BTCUSDT__1h"
    save_snapshot(snap, target)

    (target / "metadata.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="not valid JSON"):
        load_snapshot(target)


def test_load_wrong_csv_header_raises(tmp_path: Path) -> None:
    snap = _make_snapshot()
    target = tmp_path / "BTCUSDT__1h"
    save_snapshot(snap, target)

    # Replace the canonical header with a permutation — column order
    # is part of the contract, so this must be rejected.
    csv_text = (target / "ohlcv.csv").read_text(encoding="utf-8")
    body = "\n".join(csv_text.splitlines()[1:])
    bad_header = "ts,o,h,l,c,v"
    (target / "ohlcv.csv").write_text(bad_header + "\n" + body, encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="header mismatch"):
        load_snapshot(target)


def test_load_candle_count_mismatch_raises(tmp_path: Path) -> None:
    snap = _make_snapshot(n=3)
    target = tmp_path / "BTCUSDT__1h"
    save_snapshot(snap, target)

    # Bump the metadata candle_count without touching the CSV.
    raw = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
    raw["candle_count"] = 99
    (target / "metadata.json").write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="candle_count mismatch"):
        load_snapshot(target)


def test_load_unparseable_timestamp_raises(tmp_path: Path) -> None:
    snap = _make_snapshot(n=2)
    target = tmp_path / "BTCUSDT__1h"
    save_snapshot(snap, target)

    csv_path = target / "ohlcv.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    # Corrupt the first data row's timestamp.
    fields = lines[1].split(",")
    fields[0] = "not-a-timestamp"
    lines[1] = ",".join(fields)
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="cannot parse timestamp"):
        load_snapshot(target)


def test_load_unparseable_decimal_raises(tmp_path: Path) -> None:
    snap = _make_snapshot(n=2)
    target = tmp_path / "BTCUSDT__1h"
    save_snapshot(snap, target)

    csv_path = target / "ohlcv.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    # Corrupt the first data row's open price.
    fields = lines[1].split(",")
    fields[1] = "not-a-number"
    lines[1] = ",".join(fields)
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="cannot parse open"):
        load_snapshot(target)


def test_load_wrong_column_count_raises(tmp_path: Path) -> None:
    snap = _make_snapshot(n=2)
    target = tmp_path / "BTCUSDT__1h"
    save_snapshot(snap, target)

    csv_path = target / "ohlcv.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    # Drop a column from a data row.
    fields = lines[1].split(",")
    lines[1] = ",".join(fields[:-1])
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="expected 6 columns"):
        load_snapshot(target)


def test_load_empty_csv_raises(tmp_path: Path) -> None:
    target = tmp_path / "BTCUSDT__1h"
    target.mkdir()
    metadata = _make_metadata(candle_count=0)
    (target / "metadata.json").write_text(metadata.model_dump_json(), encoding="utf-8")
    (target / "ohlcv.csv").write_text("", encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="empty ohlcv.csv"):
        load_snapshot(target)


# =============================================================================
# Phase 21 UTC contract
# =============================================================================


def test_loaded_metadata_is_utc_aware(tmp_path: Path) -> None:
    """All loaded metadata datetimes carry tzinfo=UTC."""
    snap = _make_snapshot()
    target = tmp_path / "BTCUSDT__1h"
    save_snapshot(snap, target)

    loaded = load_snapshot(target)

    assert loaded.metadata.fetched_at.tzinfo is not None
    assert loaded.metadata.fetched_at.utcoffset() == timedelta(0)
    assert loaded.metadata.first_timestamp.tzinfo is not None
    assert loaded.metadata.first_timestamp.utcoffset() == timedelta(0)
    assert loaded.metadata.last_timestamp.tzinfo is not None
    assert loaded.metadata.last_timestamp.utcoffset() == timedelta(0)


def test_metadata_coerces_naive_datetimes_on_load(tmp_path: Path) -> None:
    """Naive on-disk datetimes are coerced to UTC at the read boundary."""
    snap = _make_snapshot()
    target = tmp_path / "BTCUSDT__1h"
    save_snapshot(snap, target)

    # Rewrite metadata with naive timestamps (legacy on-disk shape).
    raw = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
    raw["fetched_at"] = "2026-04-30T00:00:00"  # naive
    raw["first_timestamp"] = "2026-01-01T00:00:00"
    raw["last_timestamp"] = "2026-01-01T02:00:00"
    (target / "metadata.json").write_text(json.dumps(raw), encoding="utf-8")

    loaded = load_snapshot(target)

    assert loaded.metadata.fetched_at.tzinfo is not None
    assert loaded.metadata.fetched_at.utcoffset() == timedelta(0)


def test_loaded_ohlcv_timestamps_are_utc_aware(tmp_path: Path) -> None:
    snap = _make_snapshot(n=4)
    target = tmp_path / "BTCUSDT__1h"
    save_snapshot(snap, target)

    loaded = load_snapshot(target)

    for row in loaded.ohlcv:
        assert row.timestamp.tzinfo is not None
        assert row.timestamp.utcoffset() == timedelta(0)


# =============================================================================
# Freshness policy
# =============================================================================


def test_is_snapshot_fresh_returns_true_within_window() -> None:
    fetched = datetime(2026, 4, 1, tzinfo=timezone.utc)
    metadata = _make_metadata(fetched_at=fetched)
    now = datetime(2026, 4, 15, tzinfo=timezone.utc)  # 14 days later

    assert is_snapshot_fresh(metadata, max_age_days=90, now=now) is True


def test_is_snapshot_fresh_returns_false_outside_window() -> None:
    fetched = datetime(2026, 1, 1, tzinfo=timezone.utc)
    metadata = _make_metadata(fetched_at=fetched)
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)  # 120 days later

    assert is_snapshot_fresh(metadata, max_age_days=90, now=now) is False


def test_is_snapshot_fresh_at_exact_boundary_is_fresh() -> None:
    """Boundary policy: ``age == max_age_days`` is fresh, not stale."""
    fetched = datetime(2026, 1, 1, tzinfo=timezone.utc)
    metadata = _make_metadata(fetched_at=fetched)
    now = fetched + timedelta(days=90)

    assert is_snapshot_fresh(metadata, max_age_days=90, now=now) is True


def test_is_snapshot_fresh_default_max_age_is_90_days() -> None:
    """The documented default freshness window."""
    assert DEFAULT_MAX_AGE_DAYS == 90


def test_is_snapshot_fresh_uses_default_when_unspecified() -> None:
    fetched = datetime(2026, 1, 1, tzinfo=timezone.utc)
    metadata = _make_metadata(fetched_at=fetched)
    # 30 days later — well within the 90-day default.
    now = fetched + timedelta(days=30)

    assert is_snapshot_fresh(metadata, now=now) is True


def test_is_snapshot_fresh_coerces_naive_now() -> None:
    """A naive ``now`` argument is coerced to UTC rather than crashing."""
    fetched = datetime(2026, 1, 1, tzinfo=timezone.utc)
    metadata = _make_metadata(fetched_at=fetched)
    now_naive = datetime(2026, 1, 15)  # naive

    # Should not raise; treats now_naive as UTC.
    assert is_snapshot_fresh(metadata, max_age_days=90, now=now_naive) is True


# =============================================================================
# Directory layout
# =============================================================================


def test_baseline_directory_uses_no_slash_symbol(tmp_path: Path) -> None:
    """``BTC/USDT`` renders as ``BTCUSDT`` for filesystem safety."""
    target = baseline_directory(tmp_path, "BTC/USDT", "1h")

    assert target == tmp_path / "baselines" / "BTCUSDT__1h"


def test_baseline_directory_for_multi_segment_symbol(tmp_path: Path) -> None:
    target = baseline_directory(tmp_path, "ETH/USDT", "4h")

    assert target == tmp_path / "baselines" / "ETHUSDT__4h"


# =============================================================================
# Metadata contract surface
# =============================================================================


def test_metadata_rejects_unknown_timeframe() -> None:
    with pytest.raises(ValidationError):
        SnapshotMetadata(
            symbol="BTC/USDT",
            timeframe="3h",  # type: ignore[arg-type]
            source="binance",
            fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            candle_count=0,
            first_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            fetcher_version=FETCHER_VERSION,
        )


def test_metadata_candle_count_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        SnapshotMetadata(
            symbol="BTC/USDT",
            timeframe="1h",
            source="binance",
            fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            candle_count=-1,
            first_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            fetcher_version=FETCHER_VERSION,
        )

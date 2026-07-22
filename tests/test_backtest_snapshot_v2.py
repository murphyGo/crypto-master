"""Schema-v2 immutable generation snapshot tests."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

import src.backtest.snapshot_v2 as snapshot_v2_module
from src.backtest.snapshot import (
    FETCHER_VERSION,
    OHLCV_HEADER,
    Snapshot,
    SnapshotMetadata,
    SnapshotValidationError,
    save_snapshot,
)
from src.backtest.snapshot_v2 import (
    CURRENT_FILENAME,
    FUNDING_FILENAME,
    FUNDING_HEADER,
    GENERATION_FILENAMES,
    GENERATIONS_DIRECTORY,
    MANIFEST_DATA_FILENAMES,
    MANIFEST_FILENAME,
    METADATA_FILENAME,
    OHLCV_FILENAME,
    OPEN_INTEREST_FILENAME,
    OPEN_INTEREST_HEADER,
    SnapshotManifestFile,
    SnapshotSeriesMetadata,
    SnapshotV2,
    SnapshotV2Manifest,
    SnapshotV2Metadata,
    load_snapshot_versioned,
    save_snapshot_v2,
)
from src.exchange.derivatives import (
    FundingRate,
    OpenInterestHistory,
    OpenInterestPoint,
)
from src.models import OHLCV

UTC = timezone.utc
START = datetime(2026, 7, 1, tzinfo=UTC)
CREATED_AT = START + timedelta(days=7)


def _ohlcv(count: int = 4, *, start: datetime = START) -> tuple[OHLCV, ...]:
    return tuple(
        OHLCV(
            timestamp=start + timedelta(hours=index),
            open=Decimal("100") + index,
            high=Decimal("102") + index,
            low=Decimal("99") + index,
            close=Decimal("101") + index,
            volume=Decimal("10") + index,
        )
        for index in range(count)
    )


def _funding(
    count: int = 3,
    *,
    start: datetime = START,
    symbol: str = "BTC/USDT",
) -> tuple[FundingRate, ...]:
    return tuple(
        FundingRate(
            symbol=symbol,
            timestamp=start + timedelta(hours=8 * index),
            rate=Decimal("0.0001") + Decimal(index) / Decimal("1000000"),
        )
        for index in range(count)
    )


def _open_interest(
    count: int = 4,
    *,
    start: datetime = START,
    symbol: str = "BTC/USDT",
    requested_since: datetime | None = None,
    requested_until: datetime | None = None,
    truncated: bool = False,
    null_value_index: int | None = None,
) -> OpenInterestHistory:
    points = tuple(
        OpenInterestPoint(
            symbol=symbol,
            timestamp=start + timedelta(hours=index),
            open_interest=Decimal("1000") + index,
            open_interest_value=(
                None if index == null_value_index else Decimal("10000000") + index
            ),
        )
        for index in range(count)
    )
    return OpenInterestHistory(
        symbol=symbol,
        requested_since=requested_since,
        requested_until=requested_until,
        actual_since=points[0].timestamp if points else None,
        actual_until=points[-1].timestamp if points else None,
        truncated_at_venue_retention=truncated,
        points=points,
    )


def _series_metadata(
    timestamps: tuple[datetime, ...],
    granularity: str,
    *,
    fetched_at: datetime = CREATED_AT,
    requested_since: datetime | None = None,
    requested_until: datetime | None = None,
    truncated: bool = False,
) -> SnapshotSeriesMetadata:
    return SnapshotSeriesMetadata(
        fetched_at=fetched_at,
        requested_since=requested_since,
        requested_until=requested_until,
        actual_since=timestamps[0] if timestamps else None,
        actual_until=timestamps[-1] if timestamps else None,
        granularity=granularity,
        point_count=len(timestamps),
        truncated_at_venue_retention=truncated,
    )


def _snapshot(
    *,
    ohlcv: tuple[OHLCV, ...] | None = None,
    funding: tuple[FundingRate, ...] | None = None,
    open_interest: OpenInterestHistory | None = None,
    created_at: datetime = CREATED_AT,
    source: str = "binance",
) -> SnapshotV2:
    ohlcv_points = _ohlcv() if ohlcv is None else ohlcv
    funding_points = _funding() if funding is None else funding
    oi_history = _open_interest() if open_interest is None else open_interest
    oi_times = tuple(point.timestamp for point in oi_history.points)
    metadata = SnapshotV2Metadata(
        source=source,
        symbol="BTC/USDT",
        timeframe="1h",
        created_at=created_at,
        ohlcv=_series_metadata(
            tuple(point.timestamp for point in ohlcv_points),
            "1h",
            fetched_at=created_at,
        ),
        funding=_series_metadata(
            tuple(point.timestamp for point in funding_points),
            "8h",
            fetched_at=created_at,
        ),
        open_interest=_series_metadata(
            oi_times,
            "1h",
            fetched_at=created_at,
            requested_since=oi_history.requested_since,
            requested_until=oi_history.requested_until,
            truncated=oi_history.truncated_at_venue_retention,
        ),
    )
    return SnapshotV2(
        metadata=metadata,
        ohlcv=ohlcv_points,
        funding=funding_points,
        open_interest=oi_history,
    )


def _legacy_snapshot() -> Snapshot:
    points = list(_ohlcv(3))
    return Snapshot(
        metadata=SnapshotMetadata(
            symbol="BTC/USDT",
            timeframe="1h",
            source="binance",
            fetched_at=CREATED_AT,
            candle_count=len(points),
            first_timestamp=points[0].timestamp,
            last_timestamp=points[-1].timestamp,
            fetcher_version=FETCHER_VERSION,
        ),
        ohlcv=points,
    )


def _current_id(directory: Path) -> str:
    return (directory / CURRENT_FILENAME).read_text(encoding="utf-8").strip()


def _generation_directory(directory: Path, generation_id: str | None = None) -> Path:
    selected = generation_id or _current_id(directory)
    return directory / GENERATIONS_DIRECTORY / selected


def _canonical_json(payload: dict[str, object]) -> str:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def _csv_row_count(raw: bytes) -> int:
    reader = csv.reader(io.StringIO(raw.decode("utf-8"), newline=""))
    next(reader)
    return sum(1 for _ in reader)


def _rewrite_identity(
    directory: Path,
    *,
    manifest_overrides: dict[str, object] | None = None,
) -> str:
    """Recompute a coherent generation identity after a test mutates data."""
    old_id = _current_id(directory)
    old_dir = _generation_directory(directory, old_id)
    data = {name: (old_dir / name).read_bytes() for name in MANIFEST_DATA_FILENAMES}
    new_id = snapshot_v2_module._generation_id(data)
    metadata = json.loads(data[METADATA_FILENAME])
    manifest: dict[str, object] = {
        "schema_version": 2,
        "generation_id": new_id,
        "created_at": metadata["created_at"],
        "source": metadata["source"],
        "symbol": metadata["symbol"],
        "timeframe": metadata["timeframe"],
        "files": {
            name: {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "byte_size": len(raw),
                "row_count": None if name == METADATA_FILENAME else _csv_row_count(raw),
            }
            for name, raw in data.items()
        },
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)
    (old_dir / MANIFEST_FILENAME).write_text(
        _canonical_json(manifest), encoding="utf-8"
    )
    new_dir = directory / GENERATIONS_DIRECTORY / new_id
    if new_dir != old_dir:
        old_dir.rename(new_dir)
    (directory / CURRENT_FILENAME).write_text(f"{new_id}\n", encoding="utf-8")
    return new_id


def test_snapshot_v2_models_are_frozen() -> None:
    snapshot = _snapshot()

    with pytest.raises(ValidationError):
        snapshot.metadata.source = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        snapshot.funding = ()  # type: ignore[misc]


def test_v2_round_trip_preserves_full_bundle_and_layout(tmp_path: Path) -> None:
    original = _snapshot(open_interest=_open_interest(null_value_index=1))

    generation_id = save_snapshot_v2(original, tmp_path)
    loaded = load_snapshot_versioned(tmp_path)

    assert len(generation_id) == 64
    assert loaded.schema_version == 2
    assert loaded.generation_id == generation_id
    assert loaded.derivatives_available is True
    assert loaded.snapshot_v2 == original
    assert set(_generation_directory(tmp_path).iterdir()) == {
        _generation_directory(tmp_path) / name for name in GENERATION_FILENAMES
    }
    assert (tmp_path / CURRENT_FILENAME).read_text(encoding="utf-8") == (
        generation_id + "\n"
    )


def test_v2_csv_headers_and_null_oi_value_are_canonical(tmp_path: Path) -> None:
    save_snapshot_v2(
        _snapshot(open_interest=_open_interest(null_value_index=1)), tmp_path
    )
    generation = _generation_directory(tmp_path)

    assert (generation / OHLCV_FILENAME).read_text().splitlines()[0] == ",".join(
        OHLCV_HEADER
    )
    assert (generation / FUNDING_FILENAME).read_text().splitlines()[0] == ",".join(
        FUNDING_HEADER
    )
    oi_lines = (generation / OPEN_INTEREST_FILENAME).read_text().splitlines()
    assert oi_lines[0] == ",".join(OPEN_INTEREST_HEADER)
    assert oi_lines[2].endswith(",")


def test_identical_inputs_produce_identical_files_and_generation_id(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot()
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    first_id = save_snapshot_v2(snapshot, first_root)
    second_id = save_snapshot_v2(snapshot, second_root)

    assert first_id == second_id
    for name in GENERATION_FILENAMES:
        assert (_generation_directory(first_root) / name).read_bytes() == (
            _generation_directory(second_root) / name
        ).read_bytes()


def test_manifest_hash_size_and_row_counts_match_files(tmp_path: Path) -> None:
    snapshot = _snapshot()
    save_snapshot_v2(snapshot, tmp_path)
    generation = _generation_directory(tmp_path)
    manifest = json.loads((generation / MANIFEST_FILENAME).read_text())

    assert set(manifest["files"]) == set(MANIFEST_DATA_FILENAMES)
    expected_counts = {
        OHLCV_FILENAME: len(snapshot.ohlcv),
        FUNDING_FILENAME: len(snapshot.funding),
        OPEN_INTEREST_FILENAME: len(snapshot.open_interest.points),
        METADATA_FILENAME: None,
    }
    for name, expected_count in expected_counts.items():
        raw = (generation / name).read_bytes()
        assert manifest["files"][name]["sha256"] == hashlib.sha256(raw).hexdigest()
        assert manifest["files"][name]["byte_size"] == len(raw)
        assert manifest["files"][name]["row_count"] == expected_count


def test_empty_derivatives_series_remain_explicit_v2_data(tmp_path: Path) -> None:
    empty_oi = _open_interest(
        0,
        requested_since=START,
        requested_until=START + timedelta(days=1),
    )
    snapshot = _snapshot(funding=(), open_interest=empty_oi)

    save_snapshot_v2(snapshot, tmp_path)
    loaded = load_snapshot_versioned(tmp_path)

    assert loaded.derivatives_available is True
    assert loaded.snapshot_v2 is not None
    assert loaded.snapshot_v2.funding == ()
    assert loaded.snapshot_v2.open_interest.points == ()
    assert loaded.snapshot_v2.metadata.funding.point_count == 0
    assert loaded.snapshot_v2.metadata.open_interest.point_count == 0


def test_schema_v1_fallback_is_explicit_and_does_not_mutate_files(
    tmp_path: Path,
) -> None:
    save_snapshot(_legacy_snapshot(), tmp_path)
    before = {
        path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()
    }

    loaded = load_snapshot_versioned(tmp_path)

    after = {
        path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()
    }
    assert loaded.schema_version == 1
    assert loaded.generation_id is None
    assert loaded.derivatives_available is False
    assert loaded.legacy_snapshot == _legacy_snapshot()
    assert before == after
    assert not (tmp_path / CURRENT_FILENAME).exists()
    assert not (tmp_path / GENERATIONS_DIRECTORY).exists()


def test_v2_writer_never_rewrites_existing_v1_root_files(tmp_path: Path) -> None:
    save_snapshot(_legacy_snapshot(), tmp_path)
    v1_before = {
        name: (tmp_path / name).read_bytes()
        for name in (OHLCV_FILENAME, METADATA_FILENAME)
    }

    save_snapshot_v2(_snapshot(), tmp_path)

    assert {
        name: (tmp_path / name).read_bytes()
        for name in (OHLCV_FILENAME, METADATA_FILENAME)
    } == v1_before


def test_pinned_generation_is_stable_after_current_advances(tmp_path: Path) -> None:
    first = _snapshot()
    first_id = save_snapshot_v2(first, tmp_path)
    second = _snapshot(source="binance-refresh")
    second_id = save_snapshot_v2(second, tmp_path)

    pinned = load_snapshot_versioned(tmp_path, generation_id=first_id)
    current = load_snapshot_versioned(tmp_path)

    assert first_id != second_id
    assert pinned.generation_id == first_id
    assert pinned.snapshot_v2 == first
    assert current.generation_id == second_id
    assert current.snapshot_v2 == second


def test_republishing_same_content_reuses_valid_generation(tmp_path: Path) -> None:
    snapshot = _snapshot()

    first = save_snapshot_v2(snapshot, tmp_path)
    second = save_snapshot_v2(snapshot, tmp_path)

    assert first == second
    committed = [
        path
        for path in (tmp_path / GENERATIONS_DIRECTORY).iterdir()
        if not path.name.startswith(".staging-")
    ]
    assert committed == [_generation_directory(tmp_path)]


@pytest.mark.parametrize(
    "bad_id",
    ["../escape", "/tmp/escape", "A" * 64, "a" * 63, "a" * 65, ""],
)
def test_pinned_generation_rejects_noncanonical_ids(
    tmp_path: Path, bad_id: str
) -> None:
    with pytest.raises(SnapshotValidationError, match="64 lowercase hex"):
        load_snapshot_versioned(tmp_path, generation_id=bad_id)


@pytest.mark.parametrize("raw", ["../escape\n", "/tmp/escape\n", "a" * 64, "a\n\n"])
def test_current_rejects_traversal_absolute_and_noncanonical_content(
    tmp_path: Path, raw: str
) -> None:
    (tmp_path / CURRENT_FILENAME).write_text(raw, encoding="utf-8")

    with pytest.raises(SnapshotValidationError):
        load_snapshot_versioned(tmp_path)


def test_current_rejects_dangling_symlink_and_invalid_utf8(tmp_path: Path) -> None:
    dangling_root = tmp_path / "dangling"
    dangling_root.mkdir()
    (dangling_root / CURRENT_FILENAME).symlink_to(tmp_path / "missing-current")
    with pytest.raises(SnapshotValidationError, match="regular file"):
        load_snapshot_versioned(dangling_root)

    invalid_utf8_root = tmp_path / "invalid-utf8"
    invalid_utf8_root.mkdir()
    (invalid_utf8_root / CURRENT_FILENAME).write_bytes(b"\xff\n")
    with pytest.raises(SnapshotValidationError, match="cannot read CURRENT"):
        load_snapshot_versioned(invalid_utf8_root)


def test_generations_root_symlink_is_rejected(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    (tmp_path / GENERATIONS_DIRECTORY).symlink_to(external, target_is_directory=True)
    generation_id = "a" * 64

    with pytest.raises(SnapshotValidationError, match="cannot be a symlink"):
        load_snapshot_versioned(tmp_path, generation_id=generation_id)


def test_generation_directory_symlink_is_rejected(tmp_path: Path) -> None:
    generation_id = save_snapshot_v2(_snapshot(), tmp_path)
    target = _generation_directory(tmp_path)
    external = tmp_path / "external-generation"
    target.rename(external)
    target.symlink_to(external, target_is_directory=True)

    with pytest.raises(SnapshotValidationError, match="cannot be a symlink"):
        load_snapshot_versioned(tmp_path, generation_id=generation_id)


def test_generation_file_symlink_is_rejected(tmp_path: Path) -> None:
    save_snapshot_v2(_snapshot(), tmp_path)
    generation = _generation_directory(tmp_path)
    funding = generation / FUNDING_FILENAME
    external = tmp_path / "external-funding.csv"
    funding.rename(external)
    funding.symlink_to(external)

    with pytest.raises(SnapshotValidationError, match="regular files"):
        load_snapshot_versioned(tmp_path)


@pytest.mark.parametrize("extra", ["extra.csv", ".hidden"])
def test_generation_rejects_unknown_files(tmp_path: Path, extra: str) -> None:
    save_snapshot_v2(_snapshot(), tmp_path)
    (_generation_directory(tmp_path) / extra).write_text("unexpected")

    with pytest.raises(SnapshotValidationError, match="allowlist"):
        load_snapshot_versioned(tmp_path)


@pytest.mark.parametrize("missing", sorted(GENERATION_FILENAMES))
def test_generation_rejects_every_missing_file(tmp_path: Path, missing: str) -> None:
    save_snapshot_v2(_snapshot(), tmp_path)
    (_generation_directory(tmp_path) / missing).unlink()

    with pytest.raises(SnapshotValidationError, match="allowlist"):
        load_snapshot_versioned(tmp_path)


def test_data_hash_corruption_is_rejected(tmp_path: Path) -> None:
    save_snapshot_v2(_snapshot(), tmp_path)
    funding = _generation_directory(tmp_path) / FUNDING_FILENAME
    funding.write_text(funding.read_text() + "\n", encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="byte-size mismatch"):
        load_snapshot_versioned(tmp_path)


def test_manifest_byte_size_mismatch_is_rejected(tmp_path: Path) -> None:
    save_snapshot_v2(_snapshot(), tmp_path)
    manifest_path = _generation_directory(tmp_path) / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][FUNDING_FILENAME]["byte_size"] += 1
    manifest_path.write_text(_canonical_json(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="byte-size mismatch"):
        load_snapshot_versioned(tmp_path)


def test_manifest_row_count_mismatch_is_rejected(tmp_path: Path) -> None:
    save_snapshot_v2(_snapshot(), tmp_path)
    manifest_path = _generation_directory(tmp_path) / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][FUNDING_FILENAME]["row_count"] += 1
    manifest_path.write_text(_canonical_json(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="row-count mismatch"):
        load_snapshot_versioned(tmp_path)


def test_manifest_unknown_file_key_is_rejected(tmp_path: Path) -> None:
    save_snapshot_v2(_snapshot(), tmp_path)
    manifest_path = _generation_directory(tmp_path) / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["secret.json"] = manifest["files"][METADATA_FILENAME]
    manifest_path.write_text(_canonical_json(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="manifest.json"):
        load_snapshot_versioned(tmp_path)


def test_noncanonical_manifest_is_rejected(tmp_path: Path) -> None:
    save_snapshot_v2(_snapshot(), tmp_path)
    manifest_path = _generation_directory(tmp_path) / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text())
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="not canonical"):
        load_snapshot_versioned(tmp_path)


def test_noncanonical_metadata_is_rejected_with_coherent_identity(
    tmp_path: Path,
) -> None:
    save_snapshot_v2(_snapshot(), tmp_path)
    metadata_path = _generation_directory(tmp_path) / METADATA_FILENAME
    metadata = json.loads(metadata_path.read_text())
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    _rewrite_identity(tmp_path)

    with pytest.raises(SnapshotValidationError, match="metadata.json is not canonical"):
        load_snapshot_versioned(tmp_path)


def test_noncanonical_csv_is_rejected_with_coherent_identity(tmp_path: Path) -> None:
    save_snapshot_v2(_snapshot(), tmp_path)
    funding_path = _generation_directory(tmp_path) / FUNDING_FILENAME
    funding_path.write_bytes(funding_path.read_bytes().replace(b"\n", b"\r\n"))
    _rewrite_identity(tmp_path)

    with pytest.raises(SnapshotValidationError, match="funding.csv is not canonical"):
        load_snapshot_versioned(tmp_path)


def test_manifest_metadata_provenance_mismatch_is_rejected(tmp_path: Path) -> None:
    save_snapshot_v2(_snapshot(), tmp_path)
    manifest_path = _generation_directory(tmp_path) / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text())
    manifest["source"] = "wrong-source"
    manifest_path.write_text(_canonical_json(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="provenance mismatch"):
        load_snapshot_versioned(tmp_path)


def test_integrity_coherent_funding_gap_is_rejected_by_bundle_validation(
    tmp_path: Path,
) -> None:
    save_snapshot_v2(_snapshot(), tmp_path)
    funding_path = _generation_directory(tmp_path) / FUNDING_FILENAME
    lines = funding_path.read_text().splitlines()
    fields = lines[2].split(",")
    fields[0] = (START + timedelta(hours=16)).isoformat()
    lines[2] = ",".join(fields)
    funding_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _rewrite_identity(tmp_path)

    with pytest.raises(SnapshotValidationError, match="bundle failed validation"):
        load_snapshot_versioned(tmp_path)


def test_metadata_schema_version_mismatch_is_rejected_with_coherent_identity(
    tmp_path: Path,
) -> None:
    save_snapshot_v2(_snapshot(), tmp_path)
    metadata_path = _generation_directory(tmp_path) / METADATA_FILENAME
    metadata = json.loads(metadata_path.read_text())
    metadata["schema_version"] = 1
    metadata_path.write_text(_canonical_json(metadata), encoding="utf-8")
    _rewrite_identity(tmp_path)

    with pytest.raises(SnapshotValidationError, match="metadata.json failed"):
        load_snapshot_versioned(tmp_path)


def test_manifest_models_reject_allowlist_and_row_count_contracts() -> None:
    entry = SnapshotManifestFile(sha256="a" * 64, byte_size=1, row_count=1)
    with pytest.raises(ValidationError, match="allowlist"):
        SnapshotV2Manifest(
            generation_id="b" * 64,
            created_at=CREATED_AT,
            source="binance",
            symbol="BTC/USDT",
            timeframe="1h",
            files={OHLCV_FILENAME: entry},
        )


def test_series_metadata_rejects_bad_range_and_false_retention() -> None:
    with pytest.raises(ValidationError, match="requested_until"):
        SnapshotSeriesMetadata(
            fetched_at=CREATED_AT,
            requested_since=START + timedelta(hours=1),
            requested_until=START,
            granularity="1h",
            point_count=0,
        )
    with pytest.raises(ValidationError, match="shortened prefix"):
        SnapshotSeriesMetadata(
            fetched_at=CREATED_AT,
            requested_since=START,
            actual_since=START,
            actual_until=START,
            granularity="1h",
            point_count=1,
            truncated_at_venue_retention=True,
        )


def test_snapshot_rejects_symbol_count_grid_and_future_mismatches() -> None:
    with pytest.raises(ValidationError, match="funding symbols"):
        _snapshot(funding=_funding(symbol="ETH/USDT"))

    gap_funding = (_funding(1)[0], _funding(3)[2])
    with pytest.raises(ValidationError, match="funding timestamps"):
        _snapshot(funding=gap_funding)

    funding = _funding(2)
    with pytest.raises(ValidationError, match="contiguous and unique"):
        _snapshot(funding=(funding[0], funding[0]))
    ordered = _snapshot(funding=funding)
    with pytest.raises(ValidationError, match="contiguous and unique"):
        SnapshotV2(
            metadata=ordered.metadata,
            ohlcv=ordered.ohlcv,
            funding=tuple(reversed(funding)),
            open_interest=ordered.open_interest,
        )

    with pytest.raises(ValidationError, match="OHLCV timestamps"):
        _snapshot(ohlcv=_ohlcv(start=START + timedelta(minutes=5)))
    with pytest.raises(ValidationError, match="funding timestamps"):
        _snapshot(funding=_funding(1, start=START + timedelta(hours=4)))
    with pytest.raises(ValidationError, match="open interest timestamps"):
        _snapshot(open_interest=_open_interest(start=START + timedelta(minutes=30)))

    with pytest.raises(ValidationError, match="future points"):
        _snapshot(created_at=START + timedelta(hours=1))

    points = _ohlcv()
    bad_metadata = SnapshotV2Metadata(
        source="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        created_at=CREATED_AT,
        ohlcv=SnapshotSeriesMetadata(
            fetched_at=CREATED_AT,
            actual_since=points[0].timestamp,
            actual_until=points[-1].timestamp,
            granularity="1h",
            point_count=999,
        ),
        funding=_series_metadata(tuple(p.timestamp for p in _funding()), "8h"),
        open_interest=_series_metadata(
            tuple(p.timestamp for p in _open_interest().points), "1h"
        ),
    )
    with pytest.raises(ValidationError, match="point_count"):
        SnapshotV2(
            metadata=bad_metadata,
            ohlcv=points,
            funding=_funding(),
            open_interest=_open_interest(),
        )


@pytest.mark.parametrize(
    "phase",
    [
        "input_validated",
        "storage_ready",
        "staging_created",
        "data_files_written",
        "manifest_written",
        "staged_validated",
        "generation_finalized",
        "generation_validated",
    ],
)
def test_every_pre_pointer_phase_failure_preserves_prior_current(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    first = _snapshot()
    first_id = save_snapshot_v2(first, tmp_path)

    def fail_at_phase(actual: str) -> None:
        if actual == phase:
            raise RuntimeError(f"injected {phase}")

    monkeypatch.setattr(snapshot_v2_module, "_after_publish_phase", fail_at_phase)

    with pytest.raises(RuntimeError, match=phase):
        save_snapshot_v2(_snapshot(source=f"refresh-{phase}"), tmp_path)

    assert _current_id(tmp_path) == first_id
    loaded = load_snapshot_versioned(tmp_path)
    assert loaded.snapshot_v2 == first


def test_current_write_failure_preserves_prior_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _snapshot()
    first_id = save_snapshot_v2(first, tmp_path)
    real_atomic_write = snapshot_v2_module.atomic_write_text

    def fail_current(path: Path, content: str, *args: object, **kwargs: object) -> None:
        if path.name == CURRENT_FILENAME:
            raise OSError("injected pointer failure")
        real_atomic_write(path, content, *args, **kwargs)

    monkeypatch.setattr(snapshot_v2_module, "atomic_write_text", fail_current)

    with pytest.raises(OSError, match="pointer failure"):
        save_snapshot_v2(_snapshot(source="refresh-pointer"), tmp_path)

    assert _current_id(tmp_path) == first_id
    assert load_snapshot_versioned(tmp_path).snapshot_v2 == first


def test_unreferenced_staging_and_generation_are_ignored(tmp_path: Path) -> None:
    first = _snapshot()
    first_id = save_snapshot_v2(first, tmp_path)
    generations = tmp_path / GENERATIONS_DIRECTORY
    (generations / ".staging-deadbeef").mkdir()
    (generations / ("f" * 64)).mkdir()

    loaded = load_snapshot_versioned(tmp_path)

    assert loaded.generation_id == first_id
    assert loaded.snapshot_v2 == first


def test_existing_same_id_corruption_is_not_silently_reused(tmp_path: Path) -> None:
    snapshot = _snapshot()
    save_snapshot_v2(snapshot, tmp_path)
    funding = _generation_directory(tmp_path) / FUNDING_FILENAME
    funding.write_text("corrupt", encoding="utf-8")

    with pytest.raises(SnapshotValidationError):
        save_snapshot_v2(snapshot, tmp_path)


def test_concurrent_same_id_commit_is_validated_and_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_rename = Path.rename

    def commit_before_rename(source: Path, target: Path) -> Path:
        if source.name.startswith(".staging-"):
            target.mkdir()
            for source_file in source.iterdir():
                (target / source_file.name).write_bytes(source_file.read_bytes())
            raise FileExistsError("injected same-id concurrent commit")
        return real_rename(source, target)

    monkeypatch.setattr(Path, "rename", commit_before_rename)

    generation_id = save_snapshot_v2(_snapshot(), tmp_path)

    assert _current_id(tmp_path) == generation_id
    assert load_snapshot_versioned(tmp_path).snapshot_v2 == _snapshot()


def test_writer_rejects_current_and_generations_symlinks(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    generations_root = tmp_path / "with-generations-symlink"
    generations_root.mkdir()
    (generations_root / GENERATIONS_DIRECTORY).symlink_to(
        external, target_is_directory=True
    )
    with pytest.raises(SnapshotValidationError, match="generations directory"):
        save_snapshot_v2(_snapshot(), generations_root)

    current_root = tmp_path / "with-current-symlink"
    first_id = save_snapshot_v2(_snapshot(), current_root)
    current = current_root / CURRENT_FILENAME
    current.unlink()
    external_current = tmp_path / "external-current"
    external_current.write_text(f"{first_id}\n")
    current.symlink_to(external_current)
    with pytest.raises(SnapshotValidationError, match="CURRENT"):
        save_snapshot_v2(_snapshot(source="refresh"), current_root)

    target_root = tmp_path / "with-target-symlink"
    (target_root / GENERATIONS_DIRECTORY).mkdir(parents=True)
    reference_root = tmp_path / "reference"
    generation_id = save_snapshot_v2(_snapshot(), reference_root)
    (target_root / GENERATIONS_DIRECTORY / generation_id).symlink_to(
        tmp_path / "missing-generation",
        target_is_directory=True,
    )
    with pytest.raises(SnapshotValidationError, match="generation directory"):
        save_snapshot_v2(_snapshot(), target_root)

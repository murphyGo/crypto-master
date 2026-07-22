"""Immutable schema-v2 snapshots for Funding/OI deterministic replay.

Schema v1 remains owned by :mod:`src.backtest.snapshot`.  This module adds a
copy-on-write generation store below the same symbol/timeframe directory:

``CURRENT`` points at one validated immutable generation.  Readers never scan
for a latest directory, and writers change visibility only after the staged
generation has passed the production reader.

Related requirements: FR-046, NFR-006, DD-NFR-008, DD-NFR-009,
DD-NFR-011, DD-NFR-012.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self

from src.backtest.snapshot import (
    OHLCV_HEADER,
    Snapshot,
    SnapshotValidationError,
    load_snapshot,
)
from src.exchange.derivatives import (
    FundingRate,
    OpenInterestHistory,
    OpenInterestPoint,
)
from src.models import OHLCV
from src.utils.io import atomic_write_text

SCHEMA_VERSION_V2: Literal[2] = 2
CURRENT_FILENAME = "CURRENT"
GENERATIONS_DIRECTORY = "generations"
MANIFEST_FILENAME = "manifest.json"
METADATA_FILENAME = "metadata.json"
OHLCV_FILENAME = "ohlcv.csv"
FUNDING_FILENAME = "funding.csv"
OPEN_INTEREST_FILENAME = "open_interest.csv"

FUNDING_HEADER: tuple[str, str] = ("timestamp", "rate")
OPEN_INTEREST_HEADER: tuple[str, str, str] = (
    "timestamp",
    "open_interest",
    "open_interest_value",
)

MANIFEST_DATA_FILENAMES: tuple[str, str, str, str] = (
    OHLCV_FILENAME,
    FUNDING_FILENAME,
    OPEN_INTEREST_FILENAME,
    METADATA_FILENAME,
)
GENERATION_FILENAMES = frozenset((*MANIFEST_DATA_FILENAMES, MANIFEST_FILENAME))

_GENERATION_ID_RE = re.compile(r"^[0-9a-f]{64}$")
_TIMEFRAME_SECONDS = {"15m": 15 * 60, "1h": 60 * 60, "4h": 4 * 60 * 60}
_GRID_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


# Package-private fault-injection seam. Production behavior is a no-op; tests
# monkeypatch it to prove every pre-pointer failure preserves the old CURRENT.
def _after_publish_phase(_phase: str) -> None:
    pass


def _strict_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _validate_generation_id(value: str) -> str:
    if not _GENERATION_ID_RE.fullmatch(value):
        raise SnapshotValidationError(
            "snapshot generation id must be exactly 64 lowercase hex characters"
        )
    return value


class SnapshotSeriesMetadata(BaseModel):
    """Coverage and provenance for one normalized snapshot series."""

    fetched_at: datetime
    requested_since: datetime | None = None
    requested_until: datetime | None = None
    actual_since: datetime | None = None
    actual_until: datetime | None = None
    granularity: str = Field(min_length=1)
    point_count: int = Field(ge=0)
    truncated_at_venue_retention: bool = False

    model_config = ConfigDict(frozen=True)

    @field_validator(
        "fetched_at",
        "requested_since",
        "requested_until",
        "actual_since",
        "actual_until",
    )
    @classmethod
    def _timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _strict_utc(value)

    @model_validator(mode="after")
    def _validate_ranges(self) -> Self:
        if (
            self.requested_since is not None
            and self.requested_until is not None
            and self.requested_until < self.requested_since
        ):
            raise ValueError("requested_until must be on or after requested_since")

        if self.point_count == 0:
            if self.actual_since is not None or self.actual_until is not None:
                raise ValueError("empty series cannot declare actual bounds")
        elif self.actual_since is None or self.actual_until is None:
            raise ValueError("non-empty series requires both actual bounds")

        if (
            self.actual_since is not None
            and self.actual_until is not None
            and self.actual_until < self.actual_since
        ):
            raise ValueError("actual_until must be on or after actual_since")
        if (
            self.actual_since is not None
            and self.requested_since is not None
            and self.actual_since < self.requested_since
        ):
            raise ValueError("actual series cannot begin before requested_since")
        if (
            self.actual_until is not None
            and self.requested_until is not None
            and self.actual_until > self.requested_until
        ):
            raise ValueError("actual series cannot end after requested_until")

        if self.truncated_at_venue_retention:
            if self.requested_since is None or self.actual_since is None:
                raise ValueError(
                    "retention truncation requires requested and actual starts"
                )
            if self.actual_since <= self.requested_since:
                raise ValueError("retention truncation requires a shortened prefix")
        return self


class SnapshotV2Metadata(BaseModel):
    """Canonical schema-v2 sidecar."""

    schema_version: Literal[2] = SCHEMA_VERSION_V2
    source: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    timeframe: Literal["15m", "1h", "4h"]
    created_at: datetime
    ohlcv: SnapshotSeriesMetadata
    funding: SnapshotSeriesMetadata
    open_interest: SnapshotSeriesMetadata

    model_config = ConfigDict(frozen=True)

    @field_validator("source", "symbol")
    @classmethod
    def _text_is_canonical(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("text fields must not contain surrounding whitespace")
        return value

    @field_validator("created_at")
    @classmethod
    def _created_at_is_utc(cls, value: datetime) -> datetime:
        return _strict_utc(value)

    @model_validator(mode="after")
    def _validate_series_contract(self) -> Self:
        if self.ohlcv.granularity != self.timeframe:
            raise ValueError("OHLCV granularity must equal snapshot timeframe")
        if self.funding.granularity != "8h":
            raise ValueError("funding granularity must be 8h")
        if self.open_interest.granularity != "1h":
            raise ValueError("open-interest granularity must be 1h")
        if self.ohlcv.truncated_at_venue_retention:
            raise ValueError("OHLCV cannot use derivatives retention metadata")
        if self.funding.truncated_at_venue_retention:
            raise ValueError("funding cannot use OI retention metadata")
        for series in (self.ohlcv, self.funding, self.open_interest):
            if series.fetched_at > self.created_at:
                raise ValueError("series fetched_at cannot be after created_at")
        return self


class SnapshotManifestFile(BaseModel):
    """Integrity record for one allowlisted generation data file."""

    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(ge=0)
    row_count: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(frozen=True)


class SnapshotV2Manifest(BaseModel):
    """Canonical manifest for one immutable generation."""

    schema_version: Literal[2] = SCHEMA_VERSION_V2
    generation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    source: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    timeframe: Literal["15m", "1h", "4h"]
    files: dict[str, SnapshotManifestFile]

    model_config = ConfigDict(frozen=True)

    @field_validator("created_at")
    @classmethod
    def _created_at_is_utc(cls, value: datetime) -> datetime:
        return _strict_utc(value)

    @model_validator(mode="after")
    def _validate_file_allowlist(self) -> Self:
        if set(self.files) != set(MANIFEST_DATA_FILENAMES):
            raise ValueError(
                "manifest files must exactly match the snapshot-v2 allowlist"
            )
        for name in (OHLCV_FILENAME, FUNDING_FILENAME, OPEN_INTEREST_FILENAME):
            if self.files[name].row_count is None:
                raise ValueError(f"manifest {name} requires row_count")
        if self.files[METADATA_FILENAME].row_count is not None:
            raise ValueError("manifest metadata.json row_count must be null")
        return self


def _validate_grid(
    timestamps: Sequence[datetime],
    *,
    seconds: int,
    label: str,
) -> None:
    for timestamp in timestamps:
        normalized = _strict_utc(timestamp)
        offset = normalized - _GRID_EPOCH
        offset_microseconds = (
            offset.days * 24 * 60 * 60 + offset.seconds
        ) * 1_000_000 + offset.microseconds
        if offset_microseconds % (seconds * 1_000_000) != 0:
            raise ValueError(f"{label} timestamps must align to the time grid")
    for previous, current in zip(timestamps, timestamps[1:], strict=False):
        if current - previous != timedelta(seconds=seconds):
            raise ValueError(f"{label} timestamps must be contiguous and unique")


def _validate_bounds(
    series: SnapshotSeriesMetadata,
    timestamps: Sequence[datetime],
    *,
    created_at: datetime,
    label: str,
) -> None:
    if series.point_count != len(timestamps):
        raise ValueError(f"{label} point_count does not match series length")
    if timestamps:
        if series.actual_since != timestamps[0]:
            raise ValueError(f"{label} actual_since does not match first point")
        if series.actual_until != timestamps[-1]:
            raise ValueError(f"{label} actual_until does not match last point")
        if timestamps[-1] > created_at:
            raise ValueError(f"{label} cannot contain future points")


class SnapshotV2(BaseModel):
    """Validated in-memory schema-v2 snapshot bundle."""

    metadata: SnapshotV2Metadata
    ohlcv: tuple[OHLCV, ...] = ()
    funding: tuple[FundingRate, ...] = ()
    open_interest: OpenInterestHistory

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _validate_bundle(self) -> Self:
        metadata = self.metadata
        if any(point.symbol != metadata.symbol for point in self.funding):
            raise ValueError("funding symbols must match snapshot symbol")
        if self.open_interest.symbol != metadata.symbol:
            raise ValueError("open-interest history symbol must match snapshot symbol")

        ohlcv_times = tuple(point.timestamp for point in self.ohlcv)
        funding_times = tuple(point.timestamp for point in self.funding)
        oi_times = tuple(point.timestamp for point in self.open_interest.points)

        _validate_grid(
            ohlcv_times,
            seconds=_TIMEFRAME_SECONDS[metadata.timeframe],
            label="OHLCV",
        )
        _validate_grid(funding_times, seconds=8 * 60 * 60, label="funding")
        _validate_grid(oi_times, seconds=60 * 60, label="open interest")

        _validate_bounds(
            metadata.ohlcv,
            ohlcv_times,
            created_at=metadata.created_at,
            label="OHLCV",
        )
        _validate_bounds(
            metadata.funding,
            funding_times,
            created_at=metadata.created_at,
            label="funding",
        )
        _validate_bounds(
            metadata.open_interest,
            oi_times,
            created_at=metadata.created_at,
            label="open interest",
        )

        oi_meta = metadata.open_interest
        history = self.open_interest
        if oi_meta.requested_since != history.requested_since:
            raise ValueError("OI requested_since metadata mismatch")
        if oi_meta.requested_until != history.requested_until:
            raise ValueError("OI requested_until metadata mismatch")
        if oi_meta.actual_since != history.actual_since:
            raise ValueError("OI actual_since metadata mismatch")
        if oi_meta.actual_until != history.actual_until:
            raise ValueError("OI actual_until metadata mismatch")
        if oi_meta.truncated_at_venue_retention != history.truncated_at_venue_retention:
            raise ValueError("OI retention metadata mismatch")
        return self


class VersionedSnapshot(BaseModel):
    """Version-negotiated snapshot view with explicit v1 unavailability."""

    schema_version: Literal[1, 2]
    generation_id: str | None = None
    legacy_snapshot: Snapshot | None = None
    snapshot_v2: SnapshotV2 | None = None

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _validate_version_shape(self) -> Self:
        if self.schema_version == 1:
            if self.generation_id is not None or self.snapshot_v2 is not None:
                raise ValueError("schema v1 cannot declare a v2 generation")
            if self.legacy_snapshot is None:
                raise ValueError("schema v1 requires a legacy snapshot")
        else:
            if self.generation_id is None or self.snapshot_v2 is None:
                raise ValueError("schema v2 requires generation id and bundle")
            if self.legacy_snapshot is not None:
                raise ValueError("schema v2 cannot contain a legacy snapshot")
            _validate_generation_id(self.generation_id)
        return self

    @property
    def derivatives_available(self) -> bool:
        """Whether a derivatives-aware schema is present."""
        return self.schema_version == 2

    @property
    def ohlcv(self) -> tuple[OHLCV, ...]:
        if self.snapshot_v2 is not None:
            return self.snapshot_v2.ohlcv
        assert self.legacy_snapshot is not None
        return tuple(self.legacy_snapshot.ohlcv)


def _iso_utc(value: datetime) -> str:
    return _strict_utc(value).isoformat()


def _canonical_json_bytes(model: BaseModel) -> bytes:
    payload = model.model_dump(mode="json")
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _format_csv(header: Sequence[str], rows: Sequence[Sequence[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _snapshot_data_bytes(snapshot: SnapshotV2) -> dict[str, bytes]:
    ohlcv = _format_csv(
        OHLCV_HEADER,
        [
            (
                _iso_utc(point.timestamp),
                str(point.open),
                str(point.high),
                str(point.low),
                str(point.close),
                str(point.volume),
            )
            for point in snapshot.ohlcv
        ],
    )
    funding = _format_csv(
        FUNDING_HEADER,
        [(_iso_utc(point.timestamp), str(point.rate)) for point in snapshot.funding],
    )
    open_interest = _format_csv(
        OPEN_INTEREST_HEADER,
        [
            (
                _iso_utc(point.timestamp),
                str(point.open_interest),
                (
                    ""
                    if point.open_interest_value is None
                    else str(point.open_interest_value)
                ),
            )
            for point in snapshot.open_interest.points
        ],
    )
    return {
        OHLCV_FILENAME: ohlcv,
        FUNDING_FILENAME: funding,
        OPEN_INTEREST_FILENAME: open_interest,
        METADATA_FILENAME: _canonical_json_bytes(snapshot.metadata),
    }


def _generation_id(data_files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in MANIFEST_DATA_FILENAMES:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data_files[name])
        digest.update(b"\0")
    return digest.hexdigest()


def _manifest_for(
    snapshot: SnapshotV2,
    data_files: dict[str, bytes],
    generation_id: str,
) -> SnapshotV2Manifest:
    row_counts = {
        OHLCV_FILENAME: len(snapshot.ohlcv),
        FUNDING_FILENAME: len(snapshot.funding),
        OPEN_INTEREST_FILENAME: len(snapshot.open_interest.points),
        METADATA_FILENAME: None,
    }
    entries = {
        name: SnapshotManifestFile(
            sha256=hashlib.sha256(content).hexdigest(),
            byte_size=len(content),
            row_count=row_counts[name],
        )
        for name, content in data_files.items()
    }
    return SnapshotV2Manifest(
        generation_id=generation_id,
        created_at=snapshot.metadata.created_at,
        source=snapshot.metadata.source,
        symbol=snapshot.metadata.symbol,
        timeframe=snapshot.metadata.timeframe,
        files=entries,
    )


def _parse_decimal(raw: str, *, field: str, row_number: int) -> Decimal:
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise SnapshotValidationError(
            f"row {row_number}: invalid {field} decimal"
        ) from exc
    if not value.is_finite():
        raise SnapshotValidationError(f"row {row_number}: {field} must be finite")
    return value


def _parse_timestamp(raw: str, *, row_number: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw)
        return _strict_utc(parsed)
    except ValueError as exc:
        raise SnapshotValidationError(
            f"row {row_number}: invalid UTC timestamp"
        ) from exc


def _read_csv(
    raw: bytes, expected_header: Sequence[str], *, name: str
) -> list[list[str]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SnapshotValidationError(f"{name} is not valid UTF-8") from exc
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise SnapshotValidationError(f"{name} is empty") from exc
    if tuple(header) != tuple(expected_header):
        raise SnapshotValidationError(f"{name} header mismatch")
    rows: list[list[str]] = []
    for row_number, row in enumerate(reader, start=2):
        if len(row) != len(expected_header):
            raise SnapshotValidationError(
                f"{name} row {row_number}: expected {len(expected_header)} columns"
            )
        rows.append(row)
    return rows


def _parse_ohlcv(raw: bytes) -> tuple[OHLCV, ...]:
    points: list[OHLCV] = []
    for row_number, row in enumerate(
        _read_csv(raw, OHLCV_HEADER, name=OHLCV_FILENAME), start=2
    ):
        timestamp, open_, high, low, close, volume = row
        try:
            points.append(
                OHLCV(
                    timestamp=_parse_timestamp(timestamp, row_number=row_number),
                    open=_parse_decimal(open_, field="open", row_number=row_number),
                    high=_parse_decimal(high, field="high", row_number=row_number),
                    low=_parse_decimal(low, field="low", row_number=row_number),
                    close=_parse_decimal(close, field="close", row_number=row_number),
                    volume=_parse_decimal(
                        volume, field="volume", row_number=row_number
                    ),
                )
            )
        except Exception as exc:
            if isinstance(exc, SnapshotValidationError):
                raise
            raise SnapshotValidationError(
                f"{OHLCV_FILENAME} row {row_number} failed validation"
            ) from exc
    return tuple(points)


def _parse_funding(raw: bytes, symbol: str) -> tuple[FundingRate, ...]:
    points: list[FundingRate] = []
    for row_number, row in enumerate(
        _read_csv(raw, FUNDING_HEADER, name=FUNDING_FILENAME), start=2
    ):
        timestamp, rate = row
        try:
            points.append(
                FundingRate(
                    symbol=symbol,
                    timestamp=_parse_timestamp(timestamp, row_number=row_number),
                    rate=_parse_decimal(rate, field="rate", row_number=row_number),
                )
            )
        except Exception as exc:
            if isinstance(exc, SnapshotValidationError):
                raise
            raise SnapshotValidationError(
                f"{FUNDING_FILENAME} row {row_number} failed validation"
            ) from exc
    return tuple(points)


def _parse_open_interest(
    raw: bytes,
    metadata: SnapshotV2Metadata,
) -> OpenInterestHistory:
    points: list[OpenInterestPoint] = []
    for row_number, row in enumerate(
        _read_csv(raw, OPEN_INTEREST_HEADER, name=OPEN_INTEREST_FILENAME), start=2
    ):
        timestamp, amount, value = row
        try:
            points.append(
                OpenInterestPoint(
                    symbol=metadata.symbol,
                    timestamp=_parse_timestamp(timestamp, row_number=row_number),
                    open_interest=_parse_decimal(
                        amount, field="open_interest", row_number=row_number
                    ),
                    open_interest_value=(
                        None
                        if value == ""
                        else _parse_decimal(
                            value,
                            field="open_interest_value",
                            row_number=row_number,
                        )
                    ),
                )
            )
        except Exception as exc:
            if isinstance(exc, SnapshotValidationError):
                raise
            raise SnapshotValidationError(
                f"{OPEN_INTEREST_FILENAME} row {row_number} failed validation"
            ) from exc

    series = metadata.open_interest
    try:
        return OpenInterestHistory(
            symbol=metadata.symbol,
            requested_since=series.requested_since,
            requested_until=series.requested_until,
            actual_since=series.actual_since,
            actual_until=series.actual_until,
            truncated_at_venue_retention=series.truncated_at_venue_retention,
            points=tuple(points),
        )
    except Exception as exc:
        raise SnapshotValidationError(
            "open_interest.csv coverage metadata failed validation"
        ) from exc


def _resolve_generation_directory(directory: Path, generation_id: str) -> Path:
    generation_id = _validate_generation_id(generation_id)
    generations = directory / GENERATIONS_DIRECTORY
    if generations.is_symlink():
        raise SnapshotValidationError("generations directory cannot be a symlink")
    try:
        generations_root = generations.resolve(strict=True)
    except OSError as exc:
        raise SnapshotValidationError("missing generations directory") from exc

    candidate = generations / generation_id
    if candidate.is_symlink():
        raise SnapshotValidationError("generation directory cannot be a symlink")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise SnapshotValidationError(
            f"snapshot generation {generation_id} does not exist"
        ) from exc
    if not resolved.is_relative_to(generations_root):
        raise SnapshotValidationError("snapshot generation escapes generations root")
    if not resolved.is_dir():
        raise SnapshotValidationError("snapshot generation is not a directory")
    return resolved


def _load_generation_directory(
    generation_directory: Path,
    *,
    expected_generation_id: str,
) -> SnapshotV2:
    expected_generation_id = _validate_generation_id(expected_generation_id)
    try:
        entries = list(generation_directory.iterdir())
    except OSError as exc:
        raise SnapshotValidationError("cannot inspect snapshot generation") from exc
    names = {entry.name for entry in entries}
    if names != GENERATION_FILENAMES:
        raise SnapshotValidationError(
            "generation files must exactly match the snapshot-v2 allowlist"
        )
    if any(entry.is_symlink() or not entry.is_file() for entry in entries):
        raise SnapshotValidationError("generation files must be regular files")

    manifest_path = generation_directory / MANIFEST_FILENAME
    try:
        manifest_raw = manifest_path.read_bytes()
        manifest = SnapshotV2Manifest.model_validate_json(manifest_raw)
    except Exception as exc:
        raise SnapshotValidationError("manifest.json failed schema validation") from exc
    if _canonical_json_bytes(manifest) != manifest_raw:
        raise SnapshotValidationError("manifest.json is not canonical")
    if manifest.generation_id != expected_generation_id:
        raise SnapshotValidationError("manifest generation id mismatch")

    data_files: dict[str, bytes] = {}
    for name in MANIFEST_DATA_FILENAMES:
        try:
            raw = (generation_directory / name).read_bytes()
        except OSError as exc:
            raise SnapshotValidationError(
                f"cannot read generation file {name}"
            ) from exc
        expected = manifest.files[name]
        if len(raw) != expected.byte_size:
            raise SnapshotValidationError(f"{name} byte-size mismatch")
        if hashlib.sha256(raw).hexdigest() != expected.sha256:
            raise SnapshotValidationError(f"{name} hash mismatch")
        data_files[name] = raw

    if _generation_id(data_files) != expected_generation_id:
        raise SnapshotValidationError("generation content identity mismatch")

    try:
        metadata_raw = data_files[METADATA_FILENAME]
        metadata = SnapshotV2Metadata.model_validate_json(metadata_raw)
    except Exception as exc:
        raise SnapshotValidationError("metadata.json failed schema validation") from exc
    if _canonical_json_bytes(metadata) != metadata_raw:
        raise SnapshotValidationError("metadata.json is not canonical")
    if (
        manifest.created_at != metadata.created_at
        or manifest.source != metadata.source
        or manifest.symbol != metadata.symbol
        or manifest.timeframe != metadata.timeframe
    ):
        raise SnapshotValidationError("manifest and metadata provenance mismatch")

    ohlcv = _parse_ohlcv(data_files[OHLCV_FILENAME])
    funding = _parse_funding(data_files[FUNDING_FILENAME], metadata.symbol)
    open_interest = _parse_open_interest(data_files[OPEN_INTEREST_FILENAME], metadata)
    row_counts = {
        OHLCV_FILENAME: len(ohlcv),
        FUNDING_FILENAME: len(funding),
        OPEN_INTEREST_FILENAME: len(open_interest.points),
    }
    for name, actual_count in row_counts.items():
        if manifest.files[name].row_count != actual_count:
            raise SnapshotValidationError(f"{name} row-count mismatch")

    try:
        snapshot = SnapshotV2(
            metadata=metadata,
            ohlcv=ohlcv,
            funding=funding,
            open_interest=open_interest,
        )
    except Exception as exc:
        raise SnapshotValidationError("snapshot-v2 bundle failed validation") from exc

    canonical_data = _snapshot_data_bytes(snapshot)
    for name in (OHLCV_FILENAME, FUNDING_FILENAME, OPEN_INTEREST_FILENAME):
        if canonical_data[name] != data_files[name]:
            raise SnapshotValidationError(f"{name} is not canonical")
    return snapshot


def _write_data_files(staging: Path, data_files: dict[str, bytes]) -> None:
    for name in MANIFEST_DATA_FILENAMES:
        atomic_write_text(staging / name, data_files[name].decode("utf-8"))


def save_snapshot_v2(snapshot: SnapshotV2, directory: Path) -> str:
    """Publish a validated immutable generation and atomically select it.

    A failure before the final ``CURRENT`` replacement may leave an
    unreferenced staging/finalized generation, but the previous visible
    generation remains readable. Readers ignore every directory not selected by
    ``CURRENT`` or an explicit pinned generation id.
    """

    # Revalidation protects the boundary even when callers pass a subclass.
    try:
        normalized = SnapshotV2.model_validate(snapshot.model_dump())
    except Exception as exc:
        raise SnapshotValidationError("snapshot-v2 input failed validation") from exc
    _after_publish_phase("input_validated")

    data_files = _snapshot_data_bytes(normalized)
    generation_id = _generation_id(data_files)
    manifest = _manifest_for(normalized, data_files, generation_id)
    manifest_bytes = _canonical_json_bytes(manifest)

    directory.mkdir(parents=True, exist_ok=True)
    generations = directory / GENERATIONS_DIRECTORY
    if generations.is_symlink():
        raise SnapshotValidationError("generations directory cannot be a symlink")
    generations.mkdir(exist_ok=True)
    _after_publish_phase("storage_ready")

    target = generations / generation_id
    if target.is_symlink():
        raise SnapshotValidationError("generation directory cannot be a symlink")
    if target.exists():
        _load_generation_directory(target, expected_generation_id=generation_id)
    else:
        staging = generations / f".staging-{uuid.uuid4().hex}"
        staging.mkdir()
        _after_publish_phase("staging_created")

        _write_data_files(staging, data_files)
        _after_publish_phase("data_files_written")
        atomic_write_text(staging / MANIFEST_FILENAME, manifest_bytes.decode("utf-8"))
        _after_publish_phase("manifest_written")

        _load_generation_directory(staging, expected_generation_id=generation_id)
        _after_publish_phase("staged_validated")
        try:
            staging.rename(target)
        except OSError:
            # A concurrent writer may have committed the same content-derived
            # id after our existence check. Reuse only its fully valid bundle;
            # otherwise preserve the original rename/validation failure.
            if target.is_symlink() or not target.exists():
                raise
            _load_generation_directory(target, expected_generation_id=generation_id)
        _after_publish_phase("generation_finalized")
        _load_generation_directory(target, expected_generation_id=generation_id)
        _after_publish_phase("generation_validated")

    current = directory / CURRENT_FILENAME
    if current.is_symlink():
        raise SnapshotValidationError("CURRENT cannot be a symlink")
    atomic_write_text(current, f"{generation_id}\n")
    return generation_id


def _read_current(directory: Path) -> str | None:
    current = directory / CURRENT_FILENAME
    if current.is_symlink():
        raise SnapshotValidationError("CURRENT must be a regular file")
    if not current.exists():
        return None
    if not current.is_file():
        raise SnapshotValidationError("CURRENT must be a regular file")
    try:
        raw = current.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SnapshotValidationError("cannot read CURRENT") from exc
    generation_id = raw.removesuffix("\n")
    if raw != f"{generation_id}\n":
        raise SnapshotValidationError(
            "CURRENT must contain one generation id followed by LF"
        )
    return _validate_generation_id(generation_id)


def load_snapshot_versioned(
    directory: Path,
    *,
    generation_id: str | None = None,
) -> VersionedSnapshot:
    """Load a pinned/current schema-v2 generation or fall back to schema v1.

    Passing ``generation_id`` always selects that exact immutable generation.
    Without it, ``CURRENT`` is read once. Only when ``CURRENT`` is absent does
    the loader delegate to the unchanged Phase 25 schema-v1 reader.
    """

    selected = (
        _validate_generation_id(generation_id)
        if generation_id is not None
        else _read_current(directory)
    )
    if selected is None:
        return VersionedSnapshot(
            schema_version=1,
            legacy_snapshot=load_snapshot(directory),
        )

    generation_directory = _resolve_generation_directory(directory, selected)
    snapshot = _load_generation_directory(
        generation_directory,
        expected_generation_id=selected,
    )
    return VersionedSnapshot(
        schema_version=2,
        generation_id=selected,
        snapshot_v2=snapshot,
    )


__all__ = [
    "CURRENT_FILENAME",
    "FUNDING_FILENAME",
    "FUNDING_HEADER",
    "GENERATION_FILENAMES",
    "GENERATIONS_DIRECTORY",
    "MANIFEST_DATA_FILENAMES",
    "MANIFEST_FILENAME",
    "METADATA_FILENAME",
    "OHLCV_FILENAME",
    "OPEN_INTEREST_FILENAME",
    "OPEN_INTEREST_HEADER",
    "SCHEMA_VERSION_V2",
    "SnapshotManifestFile",
    "SnapshotSeriesMetadata",
    "SnapshotV2",
    "SnapshotV2Manifest",
    "SnapshotV2Metadata",
    "VersionedSnapshot",
    "load_snapshot_versioned",
    "save_snapshot_v2",
]

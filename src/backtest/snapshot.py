"""Snapshot dataset format + loader for reproducible baselines (Phase 25.1 / DEBT-043).

``scripts/backtest_baselines.py`` calls Binance mainnet on every run,
so re-runs drift day-to-day with whatever the live OHLCV looks like.
That is not suitable for reproducible operator artefacts or autonomous
cycles. Phase 25 replaces the live dependence with a snapshot-pinned
dataset committed to the repo: every (symbol, timeframe) pair has a
fixed CSV of OHLCV rows plus a metadata sidecar describing when and
where it was fetched. Re-runs hit the snapshot, not the network.

This module is the format spec + loader for that dataset. Phase 25.2
wires the ``--snapshot`` CLI flag and the ``--refresh-snapshot``
operator gate; Phase 25.3 populates the first baseline directories
and ``docs/baselines.md``. 25.1 stays narrow to format + tests so the
schema is settled before any production code starts depending on it.

**Format chosen: CSV + JSON sidecar.**
The snapshot files MUST be committed (the whole point is
reproducibility — they travel with the repo). Three options were on
the table:

- **CSV** — human-readable, version-control-friendly diff (line-level
  in ``git diff``), no extra deps. A typical 90-day 1h baseline is
  ~2160 rows; even multi-symbol coverage is well under the size where
  CSV becomes a problem. Pandas (already a project dep) handles
  read/write trivially.
- **Parquet** — columnar, smaller, but binary (``git diff`` shows
  "binary files differ" and the operator can't review row drift in a
  PR) and adds the ``pyarrow`` dependency.
- **JSONL** — line-oriented and schema-flexible but ~2x verbose
  vs CSV for the same row, and the row schema is fully fixed
  (timestamp + 5 floats), so the flexibility is unused.

CSV wins on the "must be diffable in PR review" axis. The OHLCV row
schema is hard-locked in this module so the diffability holds across
refreshes.

**Directory layout** (per spec, Phase 25 plan §25.1):

::

    data/backtest/snapshots/
    └── baselines/
        └── <SYMBOL>__<timeframe>/      # e.g. BTCUSDT__1h
            ├── ohlcv.csv               # header + one row per candle
            └── metadata.json           # fetch sidecar

The symbol uses the no-slash filesystem-safe spelling (``BTCUSDT``,
not ``BTC/USDT``); the in-memory model carries the canonical
``BTC/USDT`` form, so the metadata sidecar pins both spellings.

**OHLCV row schema** (``ohlcv.csv``):

::

    timestamp,open,high,low,close,volume

- ``timestamp`` — ISO-8601 UTC string (``2026-01-01T00:00:00+00:00``).
  Phase 21.1 contract: every persisted timestamp is UTC-aware. The
  loader uses :func:`src.utils.time.ensure_utc` at the read boundary
  to guard against legacy naive values.
- ``open``/``high``/``low``/``close``/``volume`` — decimal strings.
  We use ``Decimal`` end-to-end (project-wide money-math contract);
  CSV stores the string repr to avoid float-truncation artefacts on
  re-read.

Header order is part of the contract: ``load_snapshot`` rejects any
file whose header does not match exactly. This keeps the on-disk
shape pinned across refreshes so a row-level ``git diff`` is
meaningful.

**Metadata sidecar** (``metadata.json``):

::

    {
      "symbol": "BTC/USDT",
      "timeframe": "1h",
      "source": "binance",
      "fetched_at": "2026-05-01T00:00:00+00:00",
      "candle_count": 2160,
      "first_timestamp": "2026-02-01T00:00:00+00:00",
      "last_timestamp": "2026-04-30T23:00:00+00:00",
      "fetcher_version": "phase-25.1"
    }

``candle_count`` is cross-checked against the actual CSV row count on
load; a mismatch raises :class:`SnapshotValidationError` so a corrupted
or partially-written snapshot fails loud rather than silently feeding
a baseline run.

**Freshness policy.** Default ``max_age_days=90``: any snapshot whose
``fetched_at`` is older than 90 days is stale and must be refreshed.
Refresh is operator-gated (Phase 25.2 will wire ``--refresh-snapshot``);
this module only exposes the policy check. The 90-day window matches
the typical baseline horizon — rolling a snapshot more often than the
data it covers buys nothing for reproducibility.

Related Requirements:
- FR-020: Historical Chart Data Query — OHLCV originates from
  exchange API; snapshot persistence preserves the same shape.
- FR-025: Backtesting Execution — reproducibility prerequisite.
- NFR-006: Backtesting Result Storage (JSON format).
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.models import OHLCV
from src.utils.io import atomic_write_text
from src.utils.time import ensure_utc, now_utc

__all__ = [
    "OHLCV_HEADER",
    "DEFAULT_MAX_AGE_DAYS",
    "FETCHER_VERSION",
    "Snapshot",
    "SnapshotExchange",
    "SnapshotMetadata",
    "SnapshotValidationError",
    "baseline_directory",
    "is_snapshot_fresh",
    "load_snapshot",
    "save_snapshot",
]


# Header is part of the on-disk contract — load_snapshot rejects any
# file whose first row does not match exactly. Editing this tuple is
# a breaking format change and requires a snapshot regeneration.
OHLCV_HEADER: tuple[str, str, str, str, str, str] = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
)

# Default freshness window; a snapshot older than this is stale and
# must be refreshed (Phase 25.2 will wire the operator-gated refresh).
DEFAULT_MAX_AGE_DAYS: int = 90

# Pinned in the metadata sidecar so we can detect format-skew across
# format generations. Bump when OHLCV_HEADER or the metadata schema
# changes in a non-backward-compatible way.
FETCHER_VERSION: str = "phase-25.1"


class SnapshotValidationError(Exception):
    """Raised when a snapshot on disk does not match the format spec.

    The loader fails loud rather than silently feeding a corrupted or
    partially-written snapshot into a baseline run. Callers should
    treat this as a hard error and surface it to the operator.
    """


class SnapshotMetadata(BaseModel):
    """Fetch sidecar describing when and where a snapshot was captured.

    All datetimes are UTC-aware (Phase 21 contract). The
    ``field_validator(mode="after")`` hook coerces naive on-disk
    values via :func:`src.utils.time.ensure_utc` at the read boundary
    so any subsequent comparison (sort, freshness check, ``min``/
    ``max``) is always aware-vs-aware.
    """

    symbol: str = Field(min_length=1)
    timeframe: Literal["15m", "1h", "4h"]
    source: str = Field(min_length=1)
    fetched_at: datetime
    candle_count: int = Field(ge=0)
    first_timestamp: datetime
    last_timestamp: datetime
    fetcher_version: str = Field(min_length=1)

    model_config = {"frozen": True}

    @field_validator("fetched_at", "first_timestamp", "last_timestamp", mode="after")
    @classmethod
    def _coerce_to_utc(cls, value: datetime) -> datetime:
        """UTC-coerce metadata timestamps at the read boundary.

        Phase 21.2 read-boundary convention: any persisted datetime
        loaded back from disk flows through ``ensure_utc`` so naive
        legacy values gain ``tzinfo=UTC`` rather than tripping a later
        aware-vs-naive comparison.
        """
        return ensure_utc(value)


class Snapshot(BaseModel):
    """In-memory bundle of metadata + OHLCV rows for one baseline.

    Built either by :func:`load_snapshot` (read path) or directly by
    the Phase 25.2 refresh path before :func:`save_snapshot`.
    """

    metadata: SnapshotMetadata
    ohlcv: list[OHLCV]

    model_config = {"frozen": True}


def _symbol_to_dirname(symbol: str) -> str:
    """Filesystem-safe spelling of a trading pair (``BTC/USDT`` →
    ``BTCUSDT``)."""
    return symbol.replace("/", "")


def baseline_directory(root: Path, symbol: str, timeframe: str) -> Path:
    """Conventional snapshot directory for a (symbol, timeframe) pair.

    Layout: ``<root>/baselines/<SYMBOL>__<timeframe>/``.
    """
    return root / "baselines" / f"{_symbol_to_dirname(symbol)}__{timeframe}"


def _parse_decimal(field_name: str, raw: str, row_num: int) -> Decimal:
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise SnapshotValidationError(
            f"row {row_num}: cannot parse {field_name}={raw!r} as Decimal"
        ) from exc


def _parse_timestamp(raw: str, row_num: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise SnapshotValidationError(
            f"row {row_num}: cannot parse timestamp={raw!r} as ISO-8601"
        ) from exc
    return ensure_utc(parsed)


def _read_ohlcv_csv(csv_path: Path) -> list[OHLCV]:
    """Read ``ohlcv.csv`` and return the parsed rows.

    Raises :class:`SnapshotValidationError` on any schema breach
    (header mismatch, unparseable cell, wrong column count). The
    error message identifies the row number so the operator can fix
    the file directly.
    """
    if not csv_path.exists():
        raise SnapshotValidationError(f"missing ohlcv.csv at {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise SnapshotValidationError(f"empty ohlcv.csv at {csv_path}") from exc

        if tuple(header) != OHLCV_HEADER:
            raise SnapshotValidationError(
                f"ohlcv.csv header mismatch: expected {OHLCV_HEADER}, "
                f"got {tuple(header)}"
            )

        rows: list[OHLCV] = []
        # row_num counts from 2 because the header is row 1; this
        # matches what the operator sees in their editor.
        for row_num, raw_row in enumerate(reader, start=2):
            if len(raw_row) != len(OHLCV_HEADER):
                raise SnapshotValidationError(
                    f"row {row_num}: expected {len(OHLCV_HEADER)} columns, "
                    f"got {len(raw_row)}"
                )
            ts_raw, o_raw, h_raw, l_raw, c_raw, v_raw = raw_row
            rows.append(
                OHLCV(
                    timestamp=_parse_timestamp(ts_raw, row_num),
                    open=_parse_decimal("open", o_raw, row_num),
                    high=_parse_decimal("high", h_raw, row_num),
                    low=_parse_decimal("low", l_raw, row_num),
                    close=_parse_decimal("close", c_raw, row_num),
                    volume=_parse_decimal("volume", v_raw, row_num),
                )
            )

    return rows


def _read_metadata(metadata_path: Path) -> SnapshotMetadata:
    if not metadata_path.exists():
        raise SnapshotValidationError(f"missing metadata.json at {metadata_path}")

    try:
        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SnapshotValidationError(
            f"metadata.json at {metadata_path} is not valid JSON: {exc}"
        ) from exc

    try:
        return SnapshotMetadata.model_validate(raw)
    except Exception as exc:
        # Pydantic raises ValidationError, but we wrap it so callers
        # have one exception type to catch for "snapshot is broken".
        raise SnapshotValidationError(
            f"metadata.json at {metadata_path} failed schema validation: {exc}"
        ) from exc


def load_snapshot(directory: Path) -> Snapshot:
    """Load a snapshot from a (symbol, timeframe) subdirectory.

    Reads ``ohlcv.csv`` and ``metadata.json`` and validates the full
    schema:

    - CSV header matches :data:`OHLCV_HEADER` exactly.
    - Each CSV row has the right column count and parseable values.
    - Metadata JSON validates against :class:`SnapshotMetadata`.
    - ``metadata.candle_count`` matches the actual CSV row count.

    Args:
        directory: Path to a ``<SYMBOL>__<timeframe>`` directory under
            ``data/backtest/snapshots/baselines/``.

    Returns:
        Validated :class:`Snapshot` with UTC-aware timestamps.

    Raises:
        SnapshotValidationError: On any schema breach. The message
            identifies the offending file and (for CSV errors) the
            row number.
    """
    metadata = _read_metadata(directory / "metadata.json")
    rows = _read_ohlcv_csv(directory / "ohlcv.csv")

    if metadata.candle_count != len(rows):
        raise SnapshotValidationError(
            f"candle_count mismatch in {directory}: metadata says "
            f"{metadata.candle_count}, ohlcv.csv has {len(rows)} rows"
        )

    return Snapshot(metadata=metadata, ohlcv=rows)


def _format_ohlcv_csv(rows: list[OHLCV]) -> str:
    """Serialise OHLCV rows to the fixed CSV format.

    Uses the ``Decimal`` ``str()`` repr to avoid float-truncation on
    re-read. ``timestamp.isoformat()`` produces the ISO-8601 UTC
    string the loader expects (Phase 21 contract: rows are UTC-aware
    by construction here, so the offset is always ``+00:00``).
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(OHLCV_HEADER)
    for row in rows:
        writer.writerow(
            [
                row.timestamp.isoformat(),
                str(row.open),
                str(row.high),
                str(row.low),
                str(row.close),
                str(row.volume),
            ]
        )
    return buf.getvalue()


def save_snapshot(snapshot: Snapshot, directory: Path) -> None:
    """Persist a snapshot to disk atomically.

    Writes ``ohlcv.csv`` and ``metadata.json`` via
    :func:`src.utils.io.atomic_write_text` (Phase 22.1) so a crash
    mid-write leaves the destination either at its previous contents
    or at the new contents — never half-written. Concurrent writers
    on the same directory resolve last-writer-wins, which is fine
    for the Phase 25.2 ``--refresh-snapshot`` operator path (single
    operator, one refresh at a time).

    The directory is created if it doesn't exist; parents included.
    Operator-only path: 25.2 will be the only production caller.

    Args:
        snapshot: Validated :class:`Snapshot` to persist.
        directory: Destination ``<SYMBOL>__<timeframe>`` directory.
            Will be created (with parents) if missing.
    """
    directory.mkdir(parents=True, exist_ok=True)

    csv_text = _format_ohlcv_csv(snapshot.ohlcv)
    # ``model_dump_json`` emits ISO-8601 strings for the datetime
    # fields, which is exactly what _read_metadata round-trips back
    # in via ``ensure_utc``. ``indent=2`` keeps the file diffable.
    metadata_text = snapshot.metadata.model_dump_json(indent=2)

    atomic_write_text(directory / "ohlcv.csv", csv_text)
    atomic_write_text(directory / "metadata.json", metadata_text)


def is_snapshot_fresh(
    metadata: SnapshotMetadata,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    *,
    now: datetime | None = None,
) -> bool:
    """Return ``True`` iff the snapshot's ``fetched_at`` is within the policy.

    Default policy: 90 days. Refresh is operator-gated (Phase 25.2
    will wire ``--refresh-snapshot``); this function is the read-side
    check used by the baseline script before consuming the snapshot.

    Args:
        metadata: Snapshot metadata sidecar.
        max_age_days: Freshness window in days. Defaults to
            :data:`DEFAULT_MAX_AGE_DAYS` (90).
        now: Override the wall clock for tests. Defaults to
            :func:`src.utils.time.now_utc`.

    Returns:
        ``True`` if ``now - fetched_at <= max_age_days``;
        ``False`` otherwise.
    """
    current = now if now is not None else now_utc()
    # Defensive UTC-coerce: a test passing a naive ``now`` would
    # crash the subtraction below. Better to coerce than to surface
    # a confusing TypeError.
    current = ensure_utc(current)
    age = current - metadata.fetched_at
    return age <= timedelta(days=max_age_days)


class SnapshotExchange:
    """Snapshot-backed read-only stand-in for :class:`BinanceExchange`.

    Phase 25.2 adapter. Wraps a collection of preloaded
    :class:`Snapshot` objects keyed by ``(symbol, timeframe)`` and
    exposes the narrow exchange surface that
    ``scripts/backtest_baselines.py`` actually consumes:
    :meth:`connect`, :meth:`disconnect`, :meth:`get_ohlcv`. Every
    other ``BaseExchange`` method is intentionally absent — the
    baseline regenerator never touches them, and the snapshot
    dataset has no notion of live tickers, balances, or orders.

    **Slice-bounds enforcement** (quant carry-over from 25.1):

    * ``limit`` is clamped to ``len(ohlcv)`` so a caller asking for
      more bars than the snapshot holds gets the whole snapshot
      rather than an out-of-range slice.
    * ``since`` past ``last_timestamp`` returns an empty list — the
      snapshot CANNOT extrapolate past the data it captured. Callers
      that paginate forward will see the empty page and stop.
    * Pagination semantics match the Phase 10.3 fake exchange: with
      no ``since`` we return the most-recent ``limit`` rows; with a
      ``since`` cursor we return up to ``limit`` rows starting at the
      first row with ``timestamp >= since``.

    Use the ``exchange=`` injection point on
    :func:`scripts.backtest_baselines.run_all` to swap this in for
    the live ``BinanceExchange``.
    """

    name: str = "snapshot"

    def __init__(self, snapshots: dict[tuple[str, str], Snapshot]) -> None:
        """Build the adapter from a preloaded snapshot map.

        Args:
            snapshots: Mapping ``(symbol, timeframe) -> Snapshot``.
                Symbols use the canonical slash form (``BTC/USDT``),
                matching :attr:`SnapshotMetadata.symbol`.
        """
        self._snapshots = dict(snapshots)
        self.connected = False

    @classmethod
    def from_directory(
        cls,
        root: Path,
        pairs: list[tuple[str, str]],
    ) -> SnapshotExchange:
        """Build an adapter by loading every requested snapshot off disk.

        Args:
            root: Snapshot root directory (typically
                ``data/backtest/snapshots``). The conventional
                ``baselines/<SYMBOL>__<timeframe>/`` layout from
                :func:`baseline_directory` is resolved underneath.
            pairs: ``(symbol, timeframe)`` pairs to load. Each must
                map to an existing snapshot directory; otherwise
                :class:`SnapshotValidationError` propagates from
                :func:`load_snapshot` and the operator gets a
                descriptive failure naming the missing path.

        Returns:
            Fully-loaded :class:`SnapshotExchange`. Connect/disconnect
            are no-ops for parity with the live exchange contract.
        """
        loaded: dict[tuple[str, str], Snapshot] = {}
        for symbol, timeframe in pairs:
            directory = baseline_directory(root, symbol, timeframe)
            loaded[(symbol, timeframe)] = load_snapshot(directory)
        return cls(loaded)

    async def connect(self) -> None:
        """No-op for parity with :class:`BaseExchange`."""
        self.connected = True

    async def disconnect(self) -> None:
        """No-op for parity with :class:`BaseExchange`."""
        self.connected = False

    def loaded_metadata(self) -> dict[tuple[str, str], SnapshotMetadata]:
        """Return the metadata sidecar for every loaded snapshot.

        Useful for the operator-level freshness check in
        ``scripts/backtest_baselines.py``: the script iterates every
        ``(symbol, timeframe) -> SnapshotMetadata`` pair to enforce
        its tighter active-use window without poking at private
        state. The returned dict is a fresh copy; mutating it does
        not affect the adapter.
        """
        return {key: snap.metadata for key, snap in self._snapshots.items()}

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        since: int | None = None,
    ) -> list[OHLCV]:
        """Return snapshot rows for ``(symbol, timeframe)``.

        Mirrors :meth:`BinanceExchange.get_ohlcv` semantics for the
        two access patterns the baseline script uses:

        * No ``since``: return the most recent ``limit`` rows.
        * With ``since``: return up to ``limit`` rows whose
          ``timestamp`` is at or after the given UTC millisecond
          cursor.

        Slice bounds are clamped (quant carry-over from 25.1):
        ``limit`` cannot exceed ``len(ohlcv)``, and a ``since`` past
        ``last_timestamp`` yields an empty list — the snapshot
        refuses to extrapolate beyond the data it captured.

        Args:
            symbol: Trading pair in canonical slash form
                (``BTC/USDT``).
            timeframe: Candle timeframe label.
            limit: Maximum bars to return; clamped to the snapshot's
                row count.
            since: Optional UTC milliseconds cursor; rows with
                ``timestamp.timestamp() * 1000 >= since`` are returned.

        Returns:
            Matching OHLCV rows, ascending by timestamp. Empty when
            ``since`` is past ``last_timestamp``.

        Raises:
            KeyError: If no snapshot is loaded for the requested
                ``(symbol, timeframe)`` pair. The script's
                ``run_baseline`` surfaces this directly so the
                operator sees which snapshot is missing.
        """
        key = (symbol, timeframe)
        if key not in self._snapshots:
            raise KeyError(
                f"no snapshot loaded for ({symbol!r}, {timeframe!r}); "
                f"available: {sorted(self._snapshots.keys())}"
            )
        rows = self._snapshots[key].ohlcv
        if not rows:
            return []

        # Quant carry-over: clamp ``limit`` to the snapshot's actual
        # length so a caller asking for more bars than we hold gets
        # the whole snapshot rather than a confusing partial slice.
        clamped_limit = min(limit, len(rows))

        if since is None:
            # Most-recent page (matches BinanceExchange default shape).
            return list(rows[-clamped_limit:])

        # Quant carry-over: a ``since`` cursor past ``last_timestamp``
        # is an extrapolation request — return empty rather than the
        # tail page so paginators stop instead of looping forever.
        last_ts_ms = int(rows[-1].timestamp.timestamp() * 1000)
        if since > last_ts_ms:
            return []

        for i, candle in enumerate(rows):
            ts_ms = int(candle.timestamp.timestamp() * 1000)
            if ts_ms >= since:
                return list(rows[i : i + clamped_limit])
        return []

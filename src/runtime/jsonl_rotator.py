"""Time-based monthly rotation for append-only JSONL logs (Phase 10.4).

The audit log and the runtime activity log both grow unbounded — each
event is one line, low-volume today but a few MB/day at production
cadence. Phase 5 / 7 / 8 risk lists all flagged this. This module
introduces a small wrapper that keeps writes in a per-month file and
gives readers a merged, retention-bounded view.

Layout::

    <base>.YYYY-MM.jsonl    # one file per calendar month
    <base>.YYYY-MM.jsonl
    ...

Where ``<base>`` is a path *without* extension (e.g.
``data/runtime/activity``). Callers pass the base path; the rotator
derives the active month from ``datetime.now()`` on every append, so a
process that runs across a month boundary correctly switches files
without restart.

Reads merge the active month plus the most-recent ``retention_months``
archives (oldest → newest by month token, then by record timestamp).
Anything older than the retention window is silently ignored — the
files stay on disk so operators can still grep them, but they don't
flow back into the application.

Legacy un-rotated ``<base>.jsonl`` files (created before this change
landed) are read as if they were the oldest available archive. We
chose the **read-as-legacy** strategy over migrating to a dated archive
on first read because:

* migration is destructive — a botched rename would lose history;
* the legacy file's records carry their own ``timestamp`` field, so
  merging by timestamp produces correct ordering anyway;
* operators can rename the file by hand once they confirm the new
  rotated files are accumulating.

Related Requirements:
- NFR-008: mode-separated storage extends to retention.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.logger import get_logger

logger = get_logger("crypto_master.runtime.jsonl_rotator")


# ``YYYY-MM`` token embedded in the rotated filename (e.g. ``2026-04``).
_MONTH_TOKEN_RE = re.compile(r"^(\d{4})-(\d{2})$")


class JsonlRotator:
    """Append-only JSONL writer with monthly rotation + retention-bounded reads.

    Stateless apart from the base path: every ``append`` is an
    independent open / write / close so concurrent dashboard reads
    don't race with engine writes (same property as the un-rotated
    predecessors in :mod:`src.feedback.audit` and
    :mod:`src.runtime.activity_log`).

    Usage::

        rotator = JsonlRotator(Path("data/runtime/activity"))
        rotator.append({"timestamp": "...", "event_type": "..."})
        for record in rotator.read_all():
            ...
    """

    def __init__(self, base_path: Path, retention_months: int = 12) -> None:
        """Initialize the rotator.

        Args:
            base_path: Path *without* extension. The active file lives
                at ``<base>.YYYY-MM.jsonl``; archives at the same shape
                with older month tokens.
            retention_months: How many months of archives to merge into
                ``read_all`` (in addition to the active month). Older
                archives are still on disk but ignored. Defaults to 12.
        """
        if retention_months < 1:
            raise ValueError(f"retention_months must be >= 1, got {retention_months}")
        self.base_path = base_path
        self.retention_months = retention_months

    # =========================================================================
    # Path derivation
    # =========================================================================

    def _active_path(self) -> Path:
        """Return ``<base>.YYYY-MM.jsonl`` for the current calendar month.

        Recomputed on every call so a long-running process correctly
        switches files when the wall clock crosses a month boundary.
        """
        now = datetime.now()
        token = now.strftime("%Y-%m")
        return self._path_for_token(token)

    def _path_for_token(self, token: str) -> Path:
        """Build the rotated path for a given ``YYYY-MM`` token."""
        return self.base_path.with_name(f"{self.base_path.name}.{token}.jsonl")

    def _legacy_path(self) -> Path:
        """Return the path of the un-rotated legacy file, if present."""
        return self.base_path.with_name(f"{self.base_path.name}.jsonl")

    def _all_rotated_paths(self) -> list[Path]:
        """Return every ``<base>.YYYY-MM.jsonl`` on disk, sorted by token.

        Sorting by ``YYYY-MM`` is identical to chronological order
        because the token uses zero-padded month numbers and a
        four-digit year.
        """
        parent = self.base_path.parent
        if not parent.exists():
            return []
        prefix = f"{self.base_path.name}."
        suffix = ".jsonl"
        candidates: list[tuple[str, Path]] = []
        for p in parent.glob(f"{self.base_path.name}.*.jsonl"):
            stem = p.name[len(prefix) : -len(suffix)]
            if _MONTH_TOKEN_RE.match(stem):
                candidates.append((stem, p))
        candidates.sort(key=lambda pair: pair[0])
        return [p for _token, p in candidates]

    def _archive_paths(self) -> list[Path]:
        """Return the most-recent ``retention_months`` archive paths.

        "Archive" here means *every rotated file* — the active month is
        included if it exists. ``read_all`` uses this list verbatim.

        The legacy un-rotated file is treated as the oldest entry when
        present, but only counts toward the retention window once, not
        as a special category. Returned in chronological order
        (oldest → newest) so callers can iterate forward.
        """
        rotated = self._all_rotated_paths()
        legacy = self._legacy_path()

        # Cap at retention_months. Keep the newest N rotated files; the
        # legacy file (if any) is only included when there's room left
        # in the window so brand-new deployments with N+1 monthly files
        # don't drag in a zero-record legacy stub.
        kept_rotated = rotated[-self.retention_months :]

        if legacy.exists() and legacy.is_file():
            # Legacy file is conceptually the oldest. Slot it in front.
            return [legacy, *kept_rotated]
        return kept_rotated

    # =========================================================================
    # Write
    # =========================================================================

    def append(self, record: dict[str, Any]) -> None:
        """Append one record (already a JSON-serializable dict).

        The active month is recomputed every call from
        ``datetime.now()``, so a process running across a month
        boundary writes to the new file on its next append without
        restart. The parent directory is created lazily on first
        write — callers don't have to pre-create it.

        Args:
            record: A JSON-serializable dict. Caller is responsible
                for serialization shape (e.g. ``model_dump`` mode);
                this method just dumps with ``json.dumps``.
        """
        path = self._active_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, default=str)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    # =========================================================================
    # Read
    # =========================================================================

    def read_all(self) -> Iterator[dict[str, Any]]:
        """Yield every record across the active month + retained archives.

        Records are yielded in **timestamp order** when the records
        carry a ``timestamp`` field (the convention for both
        ``ActivityEvent`` and ``AuditEvent``). When timestamps are
        missing or unparseable, those records sort to the end in
        file-encounter order.

        Malformed lines are skipped with a warning rather than crashing
        the read — the same policy as the un-rotated predecessors.
        """
        merged: list[tuple[datetime | None, int, dict[str, Any]]] = []
        seq = 0  # tiebreaker for stable ordering of equal timestamps
        for path in self._archive_paths():
            for record in self._read_file(path):
                ts = _coerce_timestamp(record.get("timestamp"))
                merged.append((ts, seq, record))
                seq += 1
        # Records with no parseable timestamp sort to the end.
        # DEBT-025: ``_coerce_timestamp`` returns UTC-aware values, so
        # the fallback used when ``triple[0] is None`` must also be
        # UTC-aware to avoid aware-vs-naive comparison errors.
        _SENTINEL_MAX = datetime.max.replace(tzinfo=timezone.utc)
        merged.sort(
            key=lambda triple: (
                triple[0] is None,
                triple[0] or _SENTINEL_MAX,
                triple[1],
            )
        )
        for _ts, _i, record in merged:
            yield record

    def _read_file(self, path: Path) -> Iterator[dict[str, Any]]:
        """Yield records from one file, skipping malformed lines."""
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    yield json.loads(stripped)
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping malformed line {lineno} in {path}: {e}")


def _coerce_timestamp(value: Any) -> datetime | None:
    """Best-effort timestamp parser for record sorting.

    Pydantic's ``model_dump_json`` emits ISO-8601 strings; ``json.dumps``
    with ``default=str`` does the same for ``datetime``. Both shapes
    are handled. Anything else returns ``None`` so the record falls to
    the end of the merged stream.

    DEBT-025 (Phase 21.1): always returns a UTC-aware ``datetime`` so
    the sort key in ``read_all`` doesn't mix aware-vs-naive values
    (which raises ``TypeError`` in Python). Naive inputs (legacy
    records, ``date`` objects) are interpreted as UTC — which matches
    the project convention that all persisted timestamps originate
    from UTC-aware sources.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


__all__ = ["JsonlRotator"]

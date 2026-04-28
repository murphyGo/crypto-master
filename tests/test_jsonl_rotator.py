"""Tests for the JSONL monthly rotator (Phase 10.4)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.runtime import jsonl_rotator
from src.runtime.jsonl_rotator import JsonlRotator


class _ClockStub:
    """Mutable replacement for ``datetime.now`` inside the rotator module.

    Unlike ``freezegun`` (which the project doesn't currently depend on),
    this is a simple monkeypatch target — the test sets ``.now`` to the
    desired wall clock and the rotator uses it for its next append.
    """

    def __init__(self, fixed: datetime) -> None:
        self.fixed = fixed

    # ``datetime.now`` is called as an unbound method in the module, so
    # we replace the whole class with a small shim that exposes ``now``.
    def now(self) -> datetime:  # noqa: D401 - simple stub
        return self.fixed


@pytest.fixture
def base(tmp_path: Path) -> Path:
    """Base path (no extension) for the rotator under test."""
    return tmp_path / "events"


def _set_clock(monkeypatch: pytest.MonkeyPatch, when: datetime) -> None:
    """Pin ``datetime.now()`` inside the rotator module."""

    class _DT(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:  # type: ignore[override]
            return when

    monkeypatch.setattr(jsonl_rotator, "datetime", _DT)


# =============================================================================
# Construction
# =============================================================================


def test_retention_months_must_be_positive(base: Path) -> None:
    with pytest.raises(ValueError, match="retention_months"):
        JsonlRotator(base, retention_months=0)


# =============================================================================
# Active path + month-boundary rotation
# =============================================================================


def test_active_path_uses_current_month(
    base: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_clock(monkeypatch, datetime(2026, 4, 15, 12, 0, 0))
    rotator = JsonlRotator(base)

    rotator.append({"timestamp": "2026-04-15T12:00:00", "msg": "hello"})

    expected = base.with_name("events.2026-04.jsonl")
    assert expected.exists()


def test_append_rotates_at_month_boundary(
    base: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two appends across a month boundary land in two different files."""
    _set_clock(monkeypatch, datetime(2026, 4, 30, 23, 59, 59))
    rotator = JsonlRotator(base)
    rotator.append({"timestamp": "2026-04-30T23:59:59", "n": 1})

    _set_clock(monkeypatch, datetime(2026, 5, 1, 0, 0, 1))
    rotator.append({"timestamp": "2026-05-01T00:00:01", "n": 2})

    april = base.with_name("events.2026-04.jsonl")
    may = base.with_name("events.2026-05.jsonl")
    assert april.exists()
    assert may.exists()
    assert april.read_text(encoding="utf-8").count("\n") == 1
    assert may.read_text(encoding="utf-8").count("\n") == 1


def test_append_creates_parent_directory_lazily(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nested = tmp_path / "deeply" / "nested" / "events"
    _set_clock(monkeypatch, datetime(2026, 4, 1, 0, 0, 0))
    rotator = JsonlRotator(nested)

    rotator.append({"timestamp": "2026-04-01T00:00:00", "x": 1})

    assert nested.parent.is_dir()
    assert nested.with_name("events.2026-04.jsonl").exists()


# =============================================================================
# read_all merges across months in timestamp order
# =============================================================================


def test_read_all_merges_across_months_in_timestamp_order(
    base: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reads merge the active month + archives, sorted by timestamp."""
    _set_clock(monkeypatch, datetime(2026, 3, 10, 9, 0, 0))
    rotator = JsonlRotator(base)
    rotator.append({"timestamp": "2026-03-10T09:00:00", "n": 1})

    _set_clock(monkeypatch, datetime(2026, 4, 5, 14, 0, 0))
    rotator.append({"timestamp": "2026-04-05T14:00:00", "n": 2})
    rotator.append({"timestamp": "2026-04-05T14:30:00", "n": 3})

    _set_clock(monkeypatch, datetime(2026, 5, 1, 8, 0, 0))
    rotator.append({"timestamp": "2026-05-01T08:00:00", "n": 4})

    records = list(rotator.read_all())

    assert [r["n"] for r in records] == [1, 2, 3, 4]


def test_read_all_returns_empty_when_no_files(base: Path) -> None:
    rotator = JsonlRotator(base)

    assert list(rotator.read_all()) == []


# =============================================================================
# Retention cap
# =============================================================================


def test_archives_beyond_retention_are_excluded(
    base: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With retention=2, only the 2 most-recent rotated files are read."""
    months = [
        (datetime(2026, 1, 1), "2026-01"),
        (datetime(2026, 2, 1), "2026-02"),
        (datetime(2026, 3, 1), "2026-03"),
        (datetime(2026, 4, 1), "2026-04"),
    ]
    rotator = JsonlRotator(base, retention_months=2)
    for when, token in months:
        _set_clock(monkeypatch, when)
        rotator.append({"timestamp": when.isoformat(), "token": token})

    records = list(rotator.read_all())

    # Only the two newest months survive the cap.
    assert [r["token"] for r in records] == ["2026-03", "2026-04"]


def test_writes_unaffected_by_archive_cap(
    base: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rotator with a small retention still writes to the active month.

    Old archives outside the retention window remain on disk untouched
    — they are simply not surfaced via ``read_all``.
    """
    rotator = JsonlRotator(base, retention_months=1)
    _set_clock(monkeypatch, datetime(2026, 1, 1))
    rotator.append({"timestamp": "2026-01-01T00:00:00", "n": 1})
    _set_clock(monkeypatch, datetime(2026, 4, 1))
    rotator.append({"timestamp": "2026-04-01T00:00:00", "n": 2})

    # The January file still exists (untouched on disk)…
    assert base.with_name("events.2026-01.jsonl").exists()
    # …but it doesn't appear in read_all because retention=1.
    records = list(rotator.read_all())
    assert [r["n"] for r in records] == [2]


# =============================================================================
# Robustness: malformed lines
# =============================================================================


def test_corrupt_archive_lines_are_skipped(
    base: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A garbage line in an archive must not abort the read."""
    _set_clock(monkeypatch, datetime(2026, 4, 1, 0, 0, 0))
    rotator = JsonlRotator(base)
    rotator.append({"timestamp": "2026-04-01T00:00:00", "n": 1})

    # Inject a malformed line at the end of the active file.
    active = base.with_name("events.2026-04.jsonl")
    with active.open("a", encoding="utf-8") as fh:
        fh.write("{not-json\n")

    rotator.append({"timestamp": "2026-04-02T00:00:00", "n": 2})

    records = list(rotator.read_all())

    assert [r["n"] for r in records] == [1, 2]


def test_records_without_timestamp_sort_to_end(
    base: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing-timestamp records still surface but trail the rest."""
    _set_clock(monkeypatch, datetime(2026, 4, 1, 0, 0, 0))
    rotator = JsonlRotator(base)
    rotator.append({"msg": "no timestamp"})
    rotator.append({"timestamp": "2026-04-01T01:00:00", "n": 1})

    records = list(rotator.read_all())

    # Timestamped record first; un-timestamped trails.
    assert records[0].get("n") == 1
    assert records[1]["msg"] == "no timestamp"


# =============================================================================
# Legacy un-rotated file
# =============================================================================


def test_legacy_unrotated_file_is_read(
    base: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pre-rotation ``<base>.jsonl`` file is read as the oldest archive."""
    legacy = base.with_name("events.jsonl")
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        '{"timestamp": "2026-02-15T12:00:00", "n": 0}\n',
        encoding="utf-8",
    )

    _set_clock(monkeypatch, datetime(2026, 4, 1, 0, 0, 0))
    rotator = JsonlRotator(base)
    rotator.append({"timestamp": "2026-04-01T00:00:00", "n": 1})

    records = list(rotator.read_all())

    # Legacy record sorts ahead of April record by timestamp.
    assert [r["n"] for r in records] == [0, 1]
    # And new writes still go to the rotated file, not the legacy one.
    legacy_lines = legacy.read_text(encoding="utf-8").count("\n")
    assert legacy_lines == 1


def test_legacy_file_is_not_overwritten_by_writes(
    base: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy = base.with_name("events.jsonl")
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        '{"timestamp": "2026-02-15T12:00:00", "old": true}\n',
        encoding="utf-8",
    )
    legacy_before = legacy.read_text(encoding="utf-8")

    _set_clock(monkeypatch, datetime(2026, 4, 1, 0, 0, 0))
    rotator = JsonlRotator(base)
    rotator.append({"timestamp": "2026-04-01T00:00:00", "new": True})

    assert legacy.read_text(encoding="utf-8") == legacy_before


# =============================================================================
# Path glob ignores unrelated files
# =============================================================================


def test_unrelated_files_in_directory_are_ignored(
    base: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Files that don't match the ``YYYY-MM`` token pattern are skipped."""
    base.parent.mkdir(parents=True, exist_ok=True)
    # A debug file someone left in the directory.
    (base.parent / "events.debug.jsonl").write_text(
        '{"junk": true}\n', encoding="utf-8"
    )
    # A totally unrelated jsonl.
    (base.parent / "other.jsonl").write_text(
        '{"junk": true}\n', encoding="utf-8"
    )

    _set_clock(monkeypatch, datetime(2026, 4, 1, 0, 0, 0))
    rotator = JsonlRotator(base)
    rotator.append({"timestamp": "2026-04-01T00:00:00", "n": 1})

    records = list(rotator.read_all())

    assert [r["n"] for r in records] == [1]

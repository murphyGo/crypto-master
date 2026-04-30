"""Tests for the JSONL monthly rotator (Phase 10.4 / 21.2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.runtime import jsonl_rotator
from src.runtime.jsonl_rotator import JsonlRotator


@pytest.fixture
def base(tmp_path: Path) -> Path:
    """Base path (no extension) for the rotator under test."""
    return tmp_path / "events"


def _set_clock(monkeypatch: pytest.MonkeyPatch, when: datetime) -> None:
    """Pin ``now_utc()`` inside the rotator module.

    Phase 21.2: the rotator imports :func:`src.utils.time.now_utc` and
    calls it for the active-month token. Tests patch the import-bound
    name so naive test inputs (treated as UTC) drive the rotation
    independently of the host clock or the host TZ.
    """

    fixed = when if when.tzinfo is not None else when.replace(tzinfo=timezone.utc)
    monkeypatch.setattr(jsonl_rotator, "now_utc", lambda: fixed)


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
    (base.parent / "other.jsonl").write_text('{"junk": true}\n', encoding="utf-8")

    _set_clock(monkeypatch, datetime(2026, 4, 1, 0, 0, 0))
    rotator = JsonlRotator(base)
    rotator.append({"timestamp": "2026-04-01T00:00:00", "n": 1})

    records = list(rotator.read_all())

    assert [r["n"] for r in records] == [1]


# =============================================================================
# Phase 21.2: UTC month boundary on a non-UTC host
# =============================================================================


def test_active_path_is_utc_month_not_local_month(
    base: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Active-month token tracks UTC, not local.

    DEBT-025 / Phase 21.2: with the host clock at ``2026-04-30
    23:30 +09:00`` (Asia/Tokyo / KST), local-month says ``2026-04``
    but UTC-month is also ``2026-04`` (UTC = 2026-04-30 14:30). The
    interesting case is ``2026-05-01 00:30 +09:00`` (UTC =
    2026-04-30 15:30): local rolled to May, UTC is still April. The
    rotator must follow UTC.
    """
    # Local 2026-05-01 00:30 KST == UTC 2026-04-30 15:30. The real
    # ``now_utc`` always returns the UTC-aware instant — for this
    # wall-clock moment, that's April 30 in UTC. We feed the patched
    # rotator the UTC-aware equivalent of the KST wall clock so the
    # ``strftime("%Y-%m")`` on the result yields the UTC month.
    kst = timezone(timedelta(hours=9))
    kst_local = datetime(2026, 5, 1, 0, 30, 0, tzinfo=kst)
    utc_instant = kst_local.astimezone(timezone.utc)
    assert utc_instant.month == 4  # sanity: same instant, UTC-month is April
    _set_clock(monkeypatch, utc_instant)

    rotator = JsonlRotator(base)
    rotator.append({"timestamp": utc_instant.isoformat(), "n": 1})

    april = base.with_name("events.2026-04.jsonl")
    may = base.with_name("events.2026-05.jsonl")
    assert (
        april.exists()
    ), "Active month should be UTC-April even when local clock is May"
    assert (
        not may.exists()
    ), "Local-month rotation would have written to May; UTC must not"


def test_active_path_uses_utc_aware_now(
    base: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rotator's ``_active_path`` consumes a UTC-aware ``now_utc``.

    Pin the clock to a known UTC instant and assert the active path
    reflects the UTC year-month token, regardless of any host TZ
    arithmetic that ``datetime.strftime`` might apply.
    """
    fixed = datetime(2026, 4, 30, 23, 59, 59, tzinfo=timezone.utc)
    _set_clock(monkeypatch, fixed)

    rotator = JsonlRotator(base)
    active = rotator._active_path()

    assert active.name == "events.2026-04.jsonl"


def test_read_with_legacy_naive_timestamp_is_tolerant(
    base: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy records with naive ISO timestamps still load.

    Records persisted before Phase 21.2 carry naive ISO-8601 strings.
    ``read_all`` must coerce them to UTC at the comparison boundary
    so the merged sort doesn't raise ``TypeError`` when an aware
    record arrives in the same stream.
    """
    _set_clock(monkeypatch, datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc))
    rotator = JsonlRotator(base)

    # Naive (legacy) timestamp.
    rotator.append({"timestamp": "2026-03-15T10:00:00", "n": 1})
    # Aware (post-21.2) timestamp.
    rotator.append({"timestamp": "2026-04-01T08:00:00+00:00", "n": 2})

    records = list(rotator.read_all())

    # Both records load and sort by timestamp without raising.
    assert [r["n"] for r in records] == [1, 2]

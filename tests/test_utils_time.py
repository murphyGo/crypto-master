"""Tests for ``src.utils.time`` (Phase 21.1).

These tests pin the contract: every helper returns a UTC-aware
``datetime`` regardless of the host's local timezone. The
non-UTC-host simulation uses ``time.tzset`` rather than a third-
party freeze library because the project does not currently depend
on ``time_machine`` or ``freezegun``.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone

import pytest

from src.utils.time import from_unix_ms, now_utc

# ``time.tzset`` is POSIX-only; on Windows it doesn't exist, in which
# case the TZ-shift assertion can't run. Skip the host-shift variant
# but still assert tzinfo on the value itself.
_HAS_TZSET = hasattr(time, "tzset") and sys.platform != "win32"


@pytest.fixture
def kst_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a non-UTC host (KST = UTC+9) for the test.

    Sets the ``TZ`` env var and calls ``time.tzset()`` so the
    process-wide ``localtime`` interpretation shifts. ``monkeypatch``
    restores ``TZ`` automatically; we re-run ``tzset()`` on teardown
    to restore the original interpretation.
    """
    if not _HAS_TZSET:
        pytest.skip("time.tzset() not available on this platform")
    original_tz = os.environ.get("TZ")
    monkeypatch.setenv("TZ", "Asia/Seoul")
    time.tzset()
    yield
    # monkeypatch restores TZ; re-run tzset so subsequent tests see
    # the restored value.
    if original_tz is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original_tz
    time.tzset()


# =============================================================================
# from_unix_ms
# =============================================================================


class TestFromUnixMs:
    """Contract: returns UTC-aware datetime, host TZ-independent."""

    def test_returns_utc_aware_datetime(self) -> None:
        """Returned datetime carries ``tzinfo=timezone.utc``."""
        result = from_unix_ms(1704067200000)
        assert result.tzinfo is timezone.utc

    def test_known_epoch_jan_1_2024(self) -> None:
        """1704067200000 ms == 2024-01-01 00:00:00 UTC."""
        result = from_unix_ms(1704067200000)
        assert result == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_unix_epoch_zero(self) -> None:
        """0 ms == 1970-01-01 00:00:00 UTC."""
        result = from_unix_ms(0)
        assert result == datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_accepts_float_input(self) -> None:
        """Float input is accepted and yields the same wall-clock UTC."""
        result = from_unix_ms(1704067200000.0)
        assert result == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_sub_second_precision_preserved(self) -> None:
        """Millisecond precision survives the conversion."""
        # 1704067200500 ms == 2024-01-01 00:00:00.500 UTC
        result = from_unix_ms(1704067200500)
        assert result == datetime(2024, 1, 1, 0, 0, 0, 500_000, tzinfo=timezone.utc)

    def test_value_unchanged_on_non_utc_host(self, kst_host: None) -> None:
        """The whole point of Phase 21.1: the wall-clock UTC value is
        identical on a UTC host vs a UTC+9 host."""
        result = from_unix_ms(1704067200000)
        # Same UTC instant regardless of TZ env.
        assert result == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert result.tzinfo is timezone.utc

    def test_naive_fromtimestamp_would_drift_on_non_utc_host(
        self, kst_host: None
    ) -> None:
        """Sanity check that the bug actually existed.

        With the old (naive) call, the same input ms decodes to a
        different wall-clock value on a non-UTC host. We assert that
        the *aware* path does **not** drift.
        """
        naive = datetime.fromtimestamp(1704067200000 / 1000)  # buggy form
        aware = from_unix_ms(1704067200000)
        # The naive decode picks up the host's UTC+9 offset, so its
        # wall-clock hour is 9 hours ahead of the aware value's hour.
        assert naive.hour == 9
        assert aware.hour == 0
        # And the aware value carries tzinfo while the naive one does not.
        assert naive.tzinfo is None
        assert aware.tzinfo is timezone.utc


# =============================================================================
# now_utc
# =============================================================================


class TestNowUtc:
    """Contract: ``datetime.now`` wrapped with ``tz=UTC``."""

    def test_returns_utc_aware_datetime(self) -> None:
        """Returned datetime carries ``tzinfo=timezone.utc``."""
        result = now_utc()
        assert result.tzinfo is timezone.utc

    def test_close_to_real_now(self) -> None:
        """Sanity: ``now_utc()`` is within a few seconds of the real clock."""
        before = datetime.now(tz=timezone.utc)
        result = now_utc()
        after = datetime.now(tz=timezone.utc)
        assert before <= result <= after

    def test_aware_on_non_utc_host(self, kst_host: None) -> None:
        """tzinfo is UTC even on a non-UTC host."""
        result = now_utc()
        assert result.tzinfo is timezone.utc

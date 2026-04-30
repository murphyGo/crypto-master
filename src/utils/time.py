"""UTC-aware timestamp helpers (Phase 21.1).

The audit (DEBT-025) found exchange adapters constructing OHLCV /
ticker / order timestamps via ``datetime.fromtimestamp(ms / 1000)``
with **no ``tz=`` argument**. Without ``tz=``, Python interprets
the Unix timestamp in the host's local timezone, so on a non-UTC
host (e.g. KST = UTC+9) every adapter timestamp is silently shifted
by 9 hours. Production on Fly (UTC) hides the bug; a future region
change (e.g. ``fly regions add nrt``) silently activates it.

This module is the single source of truth for converting Unix
millisecond timestamps to ``datetime`` and for getting the current
wall clock — both always UTC-aware.

**Project convention**: any timestamp originating from an external
system (exchange API, on-disk record, JSONL log) **must** flow
through one of these helpers. Internal datetimes that are naive by
contract (e.g. fixture-pinned literals in tests) are exempt, but
the moment they cross a boundary into adapter / persistence /
comparison code they get normalised here.

Related Requirements:
- FR-020: Historical Chart Data Query — correctness boundary on
  the OHLCV timestamp returned to callers.
- NFR-007: Trading History Storage — timestamps in the trade
  ledger must be UTC.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = ["from_unix_ms", "now_utc"]


def from_unix_ms(ms: int | float) -> datetime:
    """Convert a Unix millisecond timestamp to a UTC-aware ``datetime``.

    Accepts ``int`` or ``float`` because ccxt and most exchange APIs
    return ``int`` but defensive callers occasionally hand us a
    ``float`` (e.g. after JSON round-tripping).

    Args:
        ms: Unix timestamp in milliseconds since epoch (UTC).

    Returns:
        ``datetime`` with ``tzinfo=timezone.utc``. The wall-clock
        value matches the input exactly regardless of the host's
        local timezone.
    """
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def now_utc() -> datetime:
    """Return the current wall clock as a UTC-aware ``datetime``.

    Wraps ``datetime.now(tz=timezone.utc)`` so callers don't need
    to import ``timezone`` at every site, and so that any future
    change to "current time" semantics (test clock injection,
    monotonic offset, etc.) has one place to live.

    Returns:
        ``datetime`` with ``tzinfo=timezone.utc``.
    """
    return datetime.now(tz=timezone.utc)

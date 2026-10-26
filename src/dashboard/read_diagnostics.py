"""Sanitized, process-bounded diagnostics without runtime-data file writes."""

from __future__ import annotations

import json
import logging
import math
import queue
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from typing import Any

_KINDS = frozenset(
    {"activity", "ledger", "snapshots", "candidates", "proposals", "audit", "promotion"}
)
_STATUSES = frozenset({"pending", "stale", "unavailable"})
_REASONS = frozenset(
    {
        "rebuild_pending",
        "queue_full",
        "service_closed",
        "root_budget_exhausted",
        "cache_budget_exhausted",
        "empty_projection",
        "result_budget_exhausted",
        "account_budget_exhausted",
        "evaluation_clock_reversed",
        "identity_budget_exhausted",
        "invalid_record",
        "missing_timestamp",
        "source_changed",
        "state_budget_exhausted",
        "strategy_budget_exhausted",
        "window_evaluation_budget_exhausted",
        "manifest_budget_exhausted",
        "unknown_query",
        "malformed_json",
        "malformed_json_array",
        "partial_record",
        "record_too_large",
        "read_failed",
    }
)
_STAGES = frozenset(
    {
        "admission",
        "error_cache",
        "foreground_wait",
        "projection",
        "encoding",
        "cache_publication",
    }
)

# Standalone stdlib logger: no project get_logger(), ancestor handlers, files or
# directories. A failing console sink must never affect a read/future outcome.
_console = logging.Logger("dashboard_read_diagnostics", level=logging.INFO)
_console.propagate = False
_handler = logging.StreamHandler()
_formatter = logging.Formatter("%(asctime)s %(message)s")
_formatter.converter = time.gmtime
_handler.setFormatter(_formatter)
_console.addHandler(_handler)

Diagnostic = dict[str, str | int | float | None]


def _emit(record: Diagnostic) -> None:
    _console.info(json.dumps(record, sort_keys=True, separators=(",", ":")))


def _label(value: Any, allowed: frozenset[str]) -> str:
    return value if type(value) is str and value in allowed else "unknown"


class _DiagnosticDrain:
    """One process daemon; a blocked console never blocks read callers.

    No replacement thread is started if a sink stalls. At most 64 pending
    records and one active record survive; subsequent delivery is dropped.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[Callable[[Diagnostic], None], Diagnostic]] = (
            queue.Queue(maxsize=64)
        )
        self._lock = threading.Lock()
        self._dropped = 0
        self._failed = 0
        self._thread = threading.Thread(
            target=self._drain, name="dashboard-read-diagnostics", daemon=True
        )
        self._thread.start()

    def submit(self, emit: Callable[[Diagnostic], None], record: Diagnostic) -> None:
        try:
            self._queue.put_nowait((emit, record))
        except queue.Full:
            with self._lock:
                self._dropped = min(self._dropped + 1, 2**63 - 1)

    def _drain(self) -> None:
        while True:
            emit, record = self._queue.get()
            try:
                emit(record)
            except Exception:
                with self._lock:
                    self._failed = min(self._failed + 1, 2**63 - 1)
            finally:
                self._queue.task_done()
                # An idle drain must not retain a prior caller/sink graph.
                del emit, record

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "queued": self._queue.qsize(),
                "dropped": self._dropped,
                "failed": self._failed,
                "workers": int(self._thread.is_alive()),
            }


_delivery = _DiagnosticDrain()


class ReadDiagnostics:
    """At most 64 records/rate keys, burst 8 and refill 2 console events/sec.

    Repeated identical classifications emit at most once per five seconds.
    Only allowlisted labels form rate keys; roots, query ids and measured ages
    cannot create new cardinality. Numeric fields do not retain input objects.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        emit: Callable[[Diagnostic], None] = _emit,
    ) -> None:
        self._clock = clock
        self._emit = emit
        self._lock = threading.Lock()
        self._records: deque[Diagnostic] = deque(maxlen=64)
        self._last: OrderedDict[tuple[str, ...], float] = OrderedDict()
        self._tokens = 8.0
        self._refilled = clock()

    def record(
        self,
        *,
        kind: str,
        status: str,
        reason: str,
        stage: str,
        cache_age_seconds: float | None,
        admitted: int,
    ) -> None:
        key = (
            _label(kind, _KINDS),
            _label(status, _STATUSES),
            _label(reason, _REASONS),
            _label(stage, _STAGES),
        )
        age = (
            round(max(0.0, cache_age_seconds), 3)
            if isinstance(cache_age_seconds, (int, float))
            and type(cache_age_seconds) in (int, float)
            and math.isfinite(cache_age_seconds)
            else None
        )
        record: Diagnostic = {
            "event": "dashboard_read_incomplete",
            "kind": key[0],
            "status": key[1],
            "reason": key[2],
            "stage": key[3],
            "cache_age_seconds": age,
            "admitted": (
                admitted if type(admitted) is int and 0 <= admitted <= 4 else None
            ),
        }
        with self._lock:
            now = self._clock()
            self._tokens = min(8.0, self._tokens + max(0.0, now - self._refilled) * 2)
            self._refilled = max(now, self._refilled)
            if self._tokens < 1 or now - self._last.get(key, -math.inf) < 5:
                return
            self._tokens -= 1
            self._last[key] = now
            self._last.move_to_end(key)
            while len(self._last) > 64:
                self._last.popitem(last=False)
            self._records.append(record)
        _delivery.submit(self._emit, dict(record))

    def snapshot(self) -> tuple[Diagnostic, ...]:
        with self._lock:
            return tuple(dict(record) for record in self._records)


shared_read_diagnostics = ReadDiagnostics()

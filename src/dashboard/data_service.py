"""One bounded read worker shared by all dashboard sessions.

No Streamlit calls happen in this module or its worker. The foreground wait
includes admission and queue time. Timed-out calls reuse the admitted work;
they never create replacement threads for slow or blocked filesystem IO.
"""

from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Generator
from concurrent.futures import Future
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.dashboard.read_models import Limits, Query, ReadResult, utc_now
from src.utils.bounded_read import ReadFailure

Builder = Callable[[Query, Limits], Generator[dict[str, Any] | None, None, None]]


@dataclass
class CacheEntry:
    result: ReadResult
    evaluated: float
    charge: int


class DashboardDataService:
    def __init__(self, *, limits: Limits | None = None, builder: Builder | None = None):
        self.limits = limits or Limits()
        self._builder = builder or self._build_cached
        self._condition = threading.Condition()
        self._cache: OrderedDict[Query, CacheEntry] = OrderedDict()
        self._cache_bytes = 0
        self._jobs: OrderedDict[Query, Future[ReadResult]] = OrderedDict()
        self._errors: dict[Query, tuple[float, str]] = {}
        self._closed = False
        self._active: Query | None = None
        self._thread = threading.Thread(
            target=self._work, name="dashboard-reader", daemon=True
        )
        self._thread.start()

    def request(self, query: Query, *, wait: float | None = None) -> ReadResult:
        deadline = time.monotonic() + min(
            self.limits.wait_seconds,
            self.limits.wait_seconds if wait is None else max(0, wait),
        )
        query = query.normalized()
        with self._condition:
            if self._closed:
                return ReadResult("unavailable", reason="service_closed")
            now = time.monotonic()
            entry = self._cache.get(query)
            if entry and now - entry.evaluated <= self.limits.fresh_seconds:
                self._cache.move_to_end(query)
                return entry.result
            error = self._errors.get(query)
            if error and now - error[0] < self.limits.fresh_seconds:
                return self._fallback(query, error[1])
            future = self._jobs.get(query)
            if future is None:
                active_roots = {key.root for key in self._jobs}
                for key, cached in list(self._cache.items()):
                    if (
                        key.root not in active_roots
                        and now - cached.evaluated > self.limits.stale_seconds
                    ):
                        self._cache.pop(key)
                        self._cache_bytes -= cached.charge
                roots = {key.root for key in (*self._cache, *self._jobs)}
                if query.root not in roots and len(roots) >= self.limits.roots:
                    return ReadResult("unavailable", reason="root_budget_exhausted")
                if len(self._jobs) >= self.limits.admitted:
                    return self._fallback(query, "queue_full")
                future = Future()
                self._jobs[query] = future
                self._condition.notify()
        try:
            return future.result(timeout=max(0, deadline - time.monotonic()))
        except TimeoutError:
            with self._condition:
                return self._fallback(query, "rebuild_pending")

    def _build_cached(
        self, query: Query, limits: Limits
    ) -> Generator[dict[str, Any] | None, None, None]:
        from src.dashboard.projections import build_projection

        with self._condition:
            entry = self._cache.get(query)
            previous = entry.result.payload if entry else None
        yield from build_projection(query, limits, previous=previous)

    def _fallback(self, query: Query, reason: str) -> ReadResult:
        entry = self._cache.get(query)
        if entry and time.monotonic() - entry.evaluated <= self.limits.stale_seconds:
            return ReadResult(
                "stale",
                entry.result.payload,
                entry.result.evaluated_at,
                reason,
                entry.evaluated,
            )
        return ReadResult(
            "pending" if reason == "rebuild_pending" else "unavailable", reason=reason
        )

    def request_many(self, queries: list[Query]) -> dict[str, ReadResult]:
        """Share one foreground deadline across independent page sections."""
        deadline = time.monotonic() + self.limits.wait_seconds
        results: dict[str, ReadResult] = {}
        while True:
            for query in queries:
                previous = results.get(query.kind)
                if (
                    previous is None
                    or not previous.complete
                    or time.monotonic() - previous.verified_monotonic
                    > self.limits.fresh_seconds
                ):
                    results[query.kind] = self.request(query, wait=0)
            if all(result.complete for result in results.values()):
                return results
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return results
            with self._condition:
                self._condition.wait(timeout=min(remaining, 0.05))

    def _work(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._closed or bool(self._jobs))
                if self._closed:
                    return
                query, future = next(iter(self._jobs.items()))
                self._active = query
            iterator = None
            evaluated_at = query.at or utc_now()
            try:
                iterator = self._builder(query, self.limits)
                data = None
                quantum = time.monotonic()
                checkpoints = 0
                for item in iterator:
                    if self._closed:
                        raise ReadFailure("service_closed")
                    if item is not None:
                        data = item
                    checkpoints += 1
                    if (
                        time.monotonic() - quantum >= self.limits.wait_seconds
                        or checkpoints * 65536 >= self.limits.quantum_bytes
                    ):
                        # Retain compact reducer/parser checkpoint only. One
                        # active builder owns the global state/manifest budget.
                        time.sleep(0)
                        quantum = time.monotonic()
                        checkpoints = 0
                if data is None:
                    raise ReadFailure("empty_projection")
                # Bound incremental encoding before joining the payload.
                buffer = bytearray()
                size = 0
                for chunk in json.JSONEncoder(separators=(",", ":")).iterencode(data):
                    encoded = chunk.encode("utf-8")
                    size += len(encoded)
                    if size > self.limits.result_bytes:
                        raise ReadFailure("result_budget_exhausted")
                    buffer.extend(encoded)
                payload = bytes(buffer)
                evaluated_at = (
                    datetime.fromisoformat(data["evaluated_at"])
                    if "evaluated_at" in data
                    else evaluated_at
                )
                evaluated = time.monotonic()
                result = ReadResult(
                    "complete", payload, evaluated_at, verified_monotonic=evaluated
                )
                with self._condition:
                    # Reducers re-evaluate time windows at publication after
                    # verifying the captured sources. Source timestamps remain
                    # separate from this evaluation age.
                    charge = len(payload) + 4096 + len(repr(query).encode())
                    previous = self._cache.pop(query, None)
                    if previous:
                        self._cache_bytes -= previous.charge
                    while self._cache and (
                        self._cache_bytes + charge > self.limits.cache_bytes
                        or len(self._cache) >= self.limits.cache_entries
                    ):
                        _, removed = self._cache.popitem(last=False)
                        self._cache_bytes -= removed.charge
                    if charge > self.limits.cache_bytes:
                        raise ReadFailure("cache_budget_exhausted")
                    self._cache[query] = CacheEntry(result, evaluated, charge)
                    self._cache_bytes += charge
                    self._errors.pop(query, None)
            except Exception as exc:
                reason = exc.reason if isinstance(exc, ReadFailure) else "read_failed"
                with self._condition:
                    self._errors[query] = (time.monotonic(), reason)
                    # Bounded failure metadata; it cannot grow with every key.
                    while len(self._errors) > self.limits.cache_entries:
                        self._errors.pop(next(iter(self._errors)))
                    result = self._fallback(query, reason)
            finally:
                if iterator is not None:
                    iterator.close()
            with self._condition:
                self._jobs.pop(query, None)
                self._active = None
                future.set_result(result)
                self._condition.notify_all()

    def close(self, *, timeout: float = 1.0) -> None:
        with self._condition:
            self._closed = True
            for query, future in list(self._jobs.items()):
                if query != self._active:
                    future.set_result(
                        ReadResult("unavailable", reason="service_closed")
                    )
                    self._jobs.pop(query)
            self._condition.notify_all()
        self._thread.join(timeout)

    def stats(self) -> dict[str, int]:
        with self._condition:
            return {
                "cache_bytes": self._cache_bytes,
                "entries": len(self._cache),
                "admitted": len(self._jobs),
                "workers": int(self._thread.is_alive()),
            }


def _build(
    query: Query, limits: Limits
) -> Generator[dict[str, Any] | None, None, None]:
    from src.dashboard.projections import build_projection

    yield from build_projection(query, limits)


_singleton_lock = threading.Lock()
_singleton: DashboardDataService | None = None


def get_data_service() -> DashboardDataService:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = DashboardDataService()
        return _singleton

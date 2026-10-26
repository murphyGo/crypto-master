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
from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING, Any

from src.dashboard.read_diagnostics import ReadDiagnostics, shared_read_diagnostics
from src.dashboard.read_models import Limits, Query, ReadResult, utc_now
from src.utils.bounded_read import ReadFailure

if TYPE_CHECKING:
    from src.dashboard.checkpoint_store import CheckpointStore

Builder = Callable[[Query, Limits], Generator[dict[str, Any] | None, None, None]]


@dataclass
class CacheEntry:
    result: ReadResult
    evaluated: float
    charge: int
    threshold: ReadResult | None = None


class DashboardDataService:
    def __init__(
        self,
        *,
        limits: Limits | None = None,
        builder: Builder | None = None,
        checkpoint_store: CheckpointStore | None = None,
        diagnostics: ReadDiagnostics | None = None,
    ):
        self.limits = limits or Limits()
        self.checkpoint_store = checkpoint_store
        self._diagnostics = (
            diagnostics if diagnostics is not None else shared_read_diagnostics
        )
        self._index_reservation = (
            min(4 * 1024 * 1024, self.limits.cache_bytes // 4)
            if checkpoint_store is not None
            else 0
        )
        if checkpoint_store is not None:
            checkpoint_store.index_reservation = min(
                checkpoint_store.index_reservation, self._index_reservation
            )
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
        return self._request_normalized(query.normalized(), deadline)

    def _request_normalized(self, query: Query, deadline: float) -> ReadResult:
        with self._condition:
            if self._closed:
                return self._fallback(
                    query, "service_closed", stage="admission", allow_stale=False
                )
            now = time.monotonic()
            entry = self._cache.get(query)
            if entry and now - entry.evaluated <= self.limits.fresh_seconds:
                self._cache.move_to_end(query)
                return entry.result
            if query.kind == "proposals" and query.window == "threshold":
                # The threshold is lifetime/global in every complete proposal
                # projection, including Home's 24h funnel. Borrow only that
                # scalar and its original age/coverage, not windowed counts.
                for key, cached in reversed(self._cache.items()):
                    if (
                        key.kind == "proposals"
                        and key.root == query.root
                        and cached.threshold is not None
                        and now - cached.evaluated <= self.limits.fresh_seconds
                        and replace(key, window="threshold") == query
                    ):
                        return cached.threshold
            error = self._errors.get(query)
            if error and now - error[0] < self.limits.fresh_seconds:
                return self._fallback(query, error[1], stage="error_cache")
            future = self._jobs.get(query)
            if future is None:
                active_roots = {key.root for key in self._jobs}
                # A display deadline does not expire the compact projection
                # needed to verify/reuse this root after a slow batch. Retire
                # other inactive roots; byte/entry limits still bound retention.
                for key, cached in list(self._cache.items()):
                    if (
                        key.root != query.root
                        and key.root not in active_roots
                        and now - cached.evaluated > self.limits.stale_seconds
                    ):
                        self._cache.pop(key)
                        self._cache_bytes -= cached.charge
                roots = {key.root for key in (*self._cache, *self._jobs)}
                if query.root not in roots and len(roots) >= self.limits.roots:
                    return self._fallback(
                        query, "root_budget_exhausted", stage="admission"
                    )
                if len(self._jobs) >= self.limits.admitted:
                    return self._fallback(query, "queue_full", stage="admission")
                future = Future()
                self._jobs[query] = future
                self._condition.notify()
        try:
            return future.result(timeout=max(0, deadline - time.monotonic()))
        except TimeoutError:
            with self._condition:
                return self._fallback(query, "rebuild_pending", stage="foreground_wait")

    def _build_cached(
        self, query: Query, limits: Limits
    ) -> Generator[dict[str, Any] | None, None, None]:
        from src.dashboard.projections import build_projection

        with self._condition:
            entry = self._cache.get(query)
            previous = entry.result.payload if entry else None
        yield from build_projection(
            query, limits, previous=previous, checkpoint_store=self.checkpoint_store
        )

    def _fallback(
        self, query: Query, reason: str, *, stage: str, allow_stale: bool = True
    ) -> ReadResult:
        entry = self._cache.get(query)
        age = time.monotonic() - entry.evaluated if entry else None
        error = self._errors.get(query)
        retry = None
        if (
            error is not None
            and error[1] == reason
            and reason not in {"rebuild_pending", "queue_full"}
        ):

            def retry() -> None:
                with self._condition:
                    # A stale page callback cannot erase a later failure. Only
                    # explicit retry clears this error generation; valid cache
                    # contents/age and any active job remain untouched.
                    if self._errors.get(query) is error:
                        self._errors.pop(query)

        if (
            allow_stale
            and entry
            and age is not None
            and age <= self.limits.stale_seconds
        ):
            result = ReadResult(
                "stale",
                entry.result.payload,
                entry.result.evaluated_at,
                reason,
                entry.evaluated,
                retry=retry,
            )
        else:
            result = ReadResult(
                "pending" if reason == "rebuild_pending" else "unavailable",
                reason=reason,
                retry=retry,
            )
        try:
            self._diagnostics.record(
                kind=query.kind,
                status=result.status,
                reason=reason,
                stage=stage,
                cache_age_seconds=age,
                admitted=len(self._jobs),
            )
        except Exception:
            # Only telemetry failure is suppressed. The original verified or
            # incomplete outcome, worker and waiting future remain unchanged.
            pass
        return result

    def request_many(self, queries: list[Query]) -> dict[str, ReadResult]:
        """Share one foreground deadline across independent page sections."""
        deadline = time.monotonic() + self.limits.wait_seconds
        # Resolve each path once for this page request. Polling pending work
        # must not repeat filesystem canonicalization or switch root aliases.
        queries = [query.normalized() for query in queries]
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
                    results[query.kind] = self._request_normalized(
                        query, time.monotonic()
                    )
            if all(result.complete for result in results.values()):
                return results
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return results
            with self._condition:
                if not self._jobs and all(
                    result.status != "pending"
                    and result.reason not in {"rebuild_pending", "queue_full"}
                    for result in results.values()
                ):
                    # Known read failures cannot improve while idle inside
                    # this request. Return verified siblings immediately and
                    # let the explicit refresh retry, without another 4s wait.
                    return results
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
            stage = "projection"
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
                stage = "encoding"
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
                threshold = None
                if (
                    query.kind == "proposals"
                    and query.window != "threshold"
                    and "threshold" in data
                ):
                    compact = {
                        key: data[key]
                        for key in (
                            "threshold",
                            "evaluated_at",
                            "_source_digest",
                            "source_coverage",
                        )
                        if key in data
                    }
                    threshold_payload = json.dumps(
                        compact, separators=(",", ":")
                    ).encode()
                    if (
                        len(payload) + len(threshold_payload)
                        <= self.limits.result_bytes
                    ):
                        threshold = ReadResult(
                            "complete",
                            threshold_payload,
                            evaluated_at,
                            verified_monotonic=evaluated,
                        )
                with self._condition:
                    stage = "cache_publication"
                    # Reducers re-evaluate time windows at publication after
                    # verifying the captured sources. Source timestamps remain
                    # separate from this evaluation age.
                    charge = (
                        len(payload)
                        + (
                            len(threshold.payload)
                            if threshold and threshold.payload
                            else 0
                        )
                        + 4096
                        + len(repr(query).encode())
                    )
                    previous = self._cache.pop(query, None)
                    if previous:
                        self._cache_bytes -= previous.charge
                    while self._cache and (
                        self._cache_bytes + charge
                        > self.limits.cache_bytes - self._index_reservation
                        or len(self._cache) >= self.limits.cache_entries
                    ):
                        _, removed = self._cache.popitem(last=False)
                        self._cache_bytes -= removed.charge
                    if charge > self.limits.cache_bytes - self._index_reservation:
                        raise ReadFailure("cache_budget_exhausted")
                    self._cache[query] = CacheEntry(
                        result, evaluated, charge, threshold
                    )
                    self._cache_bytes += charge
                    self._errors.pop(query, None)
            except Exception as exc:
                reason = exc.reason if isinstance(exc, ReadFailure) else "read_failed"
                with self._condition:
                    self._errors[query] = (time.monotonic(), reason)
                    # Bounded failure metadata; it cannot grow with every key.
                    while len(self._errors) > self.limits.cache_entries:
                        self._errors.pop(next(iter(self._errors)))
                    result = self._fallback(query, reason, stage=stage)
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
                "cache_bytes": self._cache_bytes + self._index_reservation,
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
            import os

            from src.config import get_settings
            from src.dashboard.checkpoint_store import CheckpointStore

            store = (
                CheckpointStore(get_settings().data_dir)
                if os.environ.get("DASHBOARD_CHECKPOINTS_ENABLED", "1") != "0"
                else None
            )
            _singleton = DashboardDataService(checkpoint_store=store)
        return _singleton

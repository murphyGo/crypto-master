"""One bounded read worker shared by all dashboard sessions.

No Streamlit calls happen in this module or its worker. The foreground wait
includes admission and queue time. Timed-out calls reuse the admitted work;
they never create replacement threads for slow or blocked filesystem IO.
"""

from __future__ import annotations

import json
import threading
import time
import weakref
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
_RECOVERY_SECONDS = 30.0
_RETRY_DELAYS = (0.25, 0.5)


@dataclass
class CacheEntry:
    result: ReadResult
    evaluated: float
    charge: int
    threshold: ReadResult | None = None


@dataclass(slots=True)
class Recovery:
    deadline: float
    ready_at: float
    attempts: int = 0
    recovering: bool = False
    stage: str = "projection"


@dataclass(frozen=True, slots=True)
class ErrorToken:
    reason: str
    retry_at: float


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
        # A page may retain this tiny generation signal, never the Future or
        # its completed payload. At most one signal per admitted job (four).
        self._job_progress: dict[Query, threading.Event] = {}
        self._recovery: dict[Query, Recovery] = {}
        self._errors: dict[Query, ErrorToken] = {}
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
            fresh = self._fresh_result(query, now, touch=True)
            if fresh is not None:
                return fresh
            error = self._errors.get(query)
            if error and now < error.retry_at:
                return self._fallback(query, error.reason, stage="error_cache")
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
                    return self._fallback(
                        query,
                        "queue_full",
                        stage="admission",
                        progress=self._admission_progress(query),
                    )
                if not self._reserve_terminal_slot(query):
                    return self._fallback(
                        query, "recovery_budget_exhausted", stage="admission"
                    )
                future = Future()
                self._jobs[query] = future
                self._job_progress[query] = threading.Event()
                self._recovery[query] = Recovery(now + _RECOVERY_SECONDS, now)
                self._condition.notify()
            # Bind before waiting. Settlement and a new same-query job may
            # race with TimeoutError; the original generation must still wake
            # this page without inspecting or retaining the newer Future.
            progress = self._job_progress[query].is_set
        try:
            return future.result(timeout=max(0, deadline - time.monotonic()))
        except TimeoutError:
            with self._condition:
                return self._fallback(
                    query, "rebuild_pending", stage="foreground_wait", progress=progress
                )

    def _reserve_terminal_slot(self, query: Query) -> bool:
        """Reserve bounded metadata without evading source-error cooldowns.

        The caller holds the condition. An admitted job reserves one slot so
        it can always record failure later, even if all other clients fail.
        Ordinary errors and expired source tokens are evictable. Unexpired
        source tokens remain protected across scope churn and new callers.
        """
        self._errors.pop(query, None)  # The same query's cooldown has expired.
        now = time.monotonic()
        while len(self._errors) + len(self._jobs) >= self.limits.cache_entries:
            evictable = next(
                (
                    key
                    for key, error in self._errors.items()
                    if error.reason != "source_changed" or now >= error.retry_at
                ),
                None,
            )
            if evictable is None:
                return False
            self._errors.pop(evictable)
        return True

    def _fresh_result(
        self, query: Query, now: float, *, touch: bool = False
    ) -> ReadResult | None:
        """The caller holds the condition; progress polling never touches LRU."""
        entry = self._cache.get(query)
        if entry and now - entry.evaluated <= self.limits.fresh_seconds:
            if touch:
                self._cache.move_to_end(query)
            return entry.result
        if query.kind == "proposals" and query.window == "threshold":
            # Borrow only a compatible fresh scalar and its original age.
            for key, cached in reversed(self._cache.items()):
                if (
                    key.kind == "proposals"
                    and key.root == query.root
                    and cached.threshold is not None
                    and now - cached.evaluated <= self.limits.fresh_seconds
                    and replace(key, window="threshold") == query
                ):
                    return cached.threshold
        return None

    def _admission_progress(self, query: Query) -> Callable[[], bool]:
        service_ref = weakref.ref(self)

        def ready() -> bool:
            service = service_ref()
            if service is None:
                return True
            with service._condition:
                if service._closed or query in service._jobs:
                    return True
                now = time.monotonic()
                if service._fresh_result(query, now) is not None:
                    return True
                error = service._errors.get(query)
                if error and now < error.retry_at:
                    return True
                active_roots = {key.root for key in service._jobs}
                # Model request-time retirement without evicting anything.
                roots = active_roots | {
                    key.root
                    for key, cached in service._cache.items()
                    if not (
                        key.root != query.root
                        and key.root not in active_roots
                        and now - cached.evaluated > service.limits.stale_seconds
                    )
                }
                if query.root not in roots and len(roots) >= service.limits.roots:
                    return False
                return len(service._jobs) < service.limits.admitted

        return ready

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
        self,
        query: Query,
        reason: str,
        *,
        stage: str,
        allow_stale: bool = True,
        progress: Callable[[], bool] | None = None,
    ) -> ReadResult:
        entry = self._cache.get(query)
        age = time.monotonic() - entry.evaluated if entry else None
        error = self._errors.get(query)
        retry = None
        if (
            error is not None
            and error.reason == reason
            and reason not in {"rebuild_pending", "queue_full"}
        ):

            def retry() -> None:
                with self._condition:
                    # A stale page callback cannot erase a later failure. Only
                    # explicit retry can bypass this token's cooldown; valid cache
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
                progress=progress,
            )
        else:
            result = ReadResult(
                "pending" if reason == "rebuild_pending" else "unavailable",
                reason=reason,
                retry=retry,
                progress=progress,
            )
        self._record(query, result.status, reason, stage, age)
        return result

    def _record(
        self, query: Query, status: str, reason: str, stage: str, age: float | None
    ) -> None:
        try:
            self._diagnostics.record(
                kind=query.kind,
                status=status,
                reason=reason,
                stage=stage,
                cache_age_seconds=age,
                admitted=len(self._jobs),
            )
        except Exception:
            # Telemetry cannot alter or strand a verified/incomplete outcome.
            pass

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
        try:
            self._run_jobs()
        except BaseException:
            # A thread-level exit must not leave admitted Futures pending.
            # Quarantine this service; never start a replacement IO worker.
            self._shutdown("read_failed")
        finally:
            self._shutdown("service_closed")

    def _next_job(self) -> tuple[Query, Future[ReadResult], Recovery] | None:
        with self._condition:
            while not self._closed:
                now = time.monotonic()
                for query, future in self._jobs.items():
                    recovery = self._recovery[query]
                    if now >= recovery.ready_at or (
                        recovery.recovering and now >= recovery.deadline
                    ):
                        self._active = query
                        return query, future, recovery
                wake_at = min(
                    (
                        (
                            min(state.ready_at, state.deadline)
                            if state.recovering
                            else state.ready_at
                        )
                        for state in self._recovery.values()
                    ),
                    default=None,
                )
                self._condition.wait(
                    timeout=None if wake_at is None else max(0, wake_at - now)
                )
        return None

    def _check_attempt(self, recovery: Recovery) -> None:
        if self._closed:
            raise ReadFailure("service_closed")
        if recovery.recovering and time.monotonic() >= recovery.deadline:
            raise ReadFailure("source_changed")

    def _run_jobs(self) -> None:
        while (job := self._next_job()) is not None:
            query, future, recovery = job
            recovery.stage = "projection"
            try:
                self._check_attempt(recovery)
                recovery.attempts += 1
                entry = self._attempt(query, recovery)
                with self._condition:
                    recovery.stage = "cache_publication"
                    self._check_attempt(recovery)
                    if self._jobs.get(query) is not future:
                        continue
                    previous = self._cache.pop(query, None)
                    if previous:
                        self._cache_bytes -= previous.charge
                    while self._cache and (
                        self._cache_bytes + entry.charge
                        > self.limits.cache_bytes - self._index_reservation
                        or len(self._cache) >= self.limits.cache_entries
                    ):
                        _, removed = self._cache.popitem(last=False)
                        self._cache_bytes -= removed.charge
                    if entry.charge > self.limits.cache_bytes - self._index_reservation:
                        raise ReadFailure("cache_budget_exhausted")
                    self._cache[query] = entry
                    self._cache_bytes += entry.charge
                    self._errors.pop(query, None)
                    result = entry.result
            except Exception as exc:
                reason = exc.reason if isinstance(exc, ReadFailure) else "read_failed"
                with self._condition:
                    if self._jobs.get(query) is not future:
                        continue
                    now = time.monotonic()
                    delay_index = recovery.attempts - 1
                    if (
                        reason == "source_changed"
                        and not self._closed
                        and 0 <= delay_index < len(_RETRY_DELAYS)
                        and now + _RETRY_DELAYS[delay_index] < recovery.deadline
                    ):
                        recovery.recovering = True
                        recovery.ready_at = now + _RETRY_DELAYS[delay_index]
                        self._jobs.move_to_end(query)
                        self._active = None
                        cached = self._cache.get(query)
                        age = now - cached.evaluated if cached else None
                        self._record(
                            query,
                            (
                                "stale"
                                if age is not None and age <= self.limits.stale_seconds
                                else "pending"
                            ),
                            reason,
                            "retry_scheduled",
                            age,
                        )
                        self._condition.notify_all()
                        continue
                    # Settle this finite job. A later ordinary request can
                    # begin a new episode only after its original window and
                    # the minimum error cooldown; idle pages spawn no work.
                    retry_at = now + self.limits.fresh_seconds
                    if reason == "source_changed":
                        retry_at = max(retry_at, recovery.deadline)
                    self._errors[query] = ErrorToken(reason, retry_at)
                    result = self._fallback(
                        query,
                        reason,
                        stage=(
                            "retry_exhausted"
                            if reason == "source_changed"
                            else recovery.stage
                        ),
                        allow_stale=reason != "service_closed",
                    )
                    self._settle(query, future, result)
                    continue
            with self._condition:
                self._settle(query, future, result)

    def _settle(
        self, query: Query, future: Future[ReadResult], result: ReadResult
    ) -> None:
        # Called under the condition; converting a reservation to a terminal
        # token and settling its Future is one observable transition.
        if self._jobs.get(query) is future:
            self._jobs.pop(query)
            self._recovery.pop(query)
            progress = self._job_progress.pop(query)
            self._active = None
            try:
                future.set_result(result)
            finally:
                progress.set()
                self._condition.notify_all()

    def _attempt(self, query: Query, recovery: Recovery) -> CacheEntry:
        """A failed iterator and its partial state die before any reschedule."""
        iterator = None
        evaluated_at = query.at or utc_now()
        try:
            iterator = self._builder(query, self.limits)
            data = None
            quantum = time.monotonic()
            checkpoints = 0
            for item in iterator:
                self._check_attempt(recovery)
                if item is not None:
                    data = item
                checkpoints += 1
                if (
                    time.monotonic() - quantum >= self.limits.wait_seconds
                    or checkpoints * 65536 >= self.limits.quantum_bytes
                ):
                    time.sleep(0)
                    quantum = time.monotonic()
                    checkpoints = 0
            self._check_attempt(recovery)
            if data is None:
                raise ReadFailure("empty_projection")
            recovery.stage = "encoding"
            buffer = bytearray()
            size = 0
            for chunk in json.JSONEncoder(separators=(",", ":")).iterencode(data):
                if recovery.recovering:
                    self._check_attempt(recovery)
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
                threshold_payload = json.dumps(compact, separators=(",", ":")).encode()
                if len(payload) + len(threshold_payload) <= self.limits.result_bytes:
                    threshold = ReadResult(
                        "complete",
                        threshold_payload,
                        evaluated_at,
                        verified_monotonic=evaluated,
                    )
            charge = (
                len(payload)
                + (len(threshold.payload) if threshold and threshold.payload else 0)
                + 4096
                + len(repr(query).encode())
            )
            return CacheEntry(result, evaluated, charge, threshold)
        finally:
            if iterator is not None:
                try:
                    iterator.close()
                except Exception as exc:
                    # Cleanup is not a recoverable source mutation, including
                    # a cleanup hook which itself raises source_changed.
                    raise ReadFailure("read_failed") from exc

    def _shutdown(self, reason: str) -> None:
        with self._condition:
            self._closed = True
            for progress in self._job_progress.values():
                progress.set()
            for future in self._jobs.values():
                if not future.done():
                    future.set_result(ReadResult("unavailable", reason=reason))
            self._jobs.clear()
            self._job_progress.clear()
            self._recovery.clear()
            self._errors.clear()
            self._active = None
            self._condition.notify_all()

    def close(self, *, timeout: float = 1.0) -> None:
        self._shutdown("service_closed")
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

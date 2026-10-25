"""Bounded, process-owned reads for the runtime's safety decision.

This deliberately retains the runtime's legacy JSON/model skip policy. It does
not change the dashboard's strict readers or chronological ``read_all`` API.
Disk IO belongs to one lazy daemon thread; timed-out work keeps its slot until
it has actually unwound, and cannot publish a late score.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import heapq
import json
import math
import os
import re
import stat
import sys
import threading
import time
from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.logger import get_logger
from src.runtime.activity_events import ActivityEvent, ActivityEventType
from src.runtime.activity_log import ActivityLog
from src.runtime.gate_reason import GateReason
from src.runtime.safety_score import (
    RuntimeSafetyScore,
    SafetyAccumulator,
    SafetyAggregationError,
    compute_runtime_safety_score,
)
from src.utils.time import ensure_utc, now_utc

logger = get_logger("crypto_master.runtime.safety_inputs")
_MONTH = re.compile(r"^\d{4}-\d{2}$")
_LINE_END = re.compile(rb"[\r\n]")
MiB = 1024 * 1024
_FAILURE_REASONS = frozenset(
    {
        "safety_cycle_budget_exhausted",
        "safety_read_budget_exhausted",
        "safety_reader_closed",
        "safety_reader_busy",
        "safety_read_cancelled",
        "safety_read_timeout",
        "safety_read_byte_limit",
        "safety_read_failed",
        "safety_evaluation_expired",
        "safety_source_config",
        "safety_source_changed",
        "safety_source_unreadable",
        "safety_manifest_limit",
        "safety_row_limit",
        "safety_nonobject_row",
        "safety_invalid_utf8",
        "safety_extra_limit",
        "safety_extra_unsupported",
        "safety_key_unsupported",
        "safety_key_limit",
        "safety_state_limit",
        "safety_state_unsupported",
    }
)


@dataclass(frozen=True)
class SafetyReadLimits:
    block_bytes: int = 64 * 1024
    row_bytes: int = MiB
    state_bytes: int = 16 * MiB
    manifest_bytes: int = 4 * MiB
    extra_count: int = 4096
    extra_bytes: int = 2 * MiB
    distinct_keys: int = 50_000

    def __post_init__(self) -> None:
        maxima = (64 * 1024, MiB, 16 * MiB, 4 * MiB, 4096, 2 * MiB, 50_000)
        for name, maximum in zip(self.__dataclass_fields__, maxima, strict=True):
            value = getattr(self, name)
            if type(value) is not int or not 0 < value <= maximum:
                raise ValueError(f"invalid safety read limit: {name}")


class SafetyReadUnavailable(Exception):
    """Stable failure metadata, without source data or a worker traceback."""

    def __init__(
        self, reason: str, *, elapsed_seconds: float = 0.0, bytes_read: int = 0
    ) -> None:
        self.reason = (
            reason
            if type(reason) is str and reason in _FAILURE_REASONS
            else "safety_read_failed"
        )
        self.elapsed_seconds = elapsed_seconds
        self.bytes_read = bytes_read
        super().__init__(self.reason)


@dataclass(frozen=True)
class SafetyReadResult:
    score: RuntimeSafetyScore
    evaluated_at: datetime
    elapsed_seconds: float
    bytes_read: int
    diagnostics: dict[str, int | float | str]


class _SourceFailure(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass
class _Budget:
    started: float
    deadline: float
    max_bytes: int
    cancelled: threading.Event
    clock: Callable[[], float]
    bytes_read: int = 0

    def check(self) -> None:
        if self.cancelled.is_set():
            raise _SourceFailure("safety_read_cancelled")
        if self.clock() >= self.deadline:
            raise _SourceFailure("safety_read_timeout")

    def read_size(self, desired: int) -> int:
        self.check()
        if self.bytes_read + desired > self.max_bytes:
            raise _SourceFailure("safety_read_byte_limit")
        return desired


@dataclass(frozen=True)
class _Version:
    device: int
    inode: int
    size: int
    mtime_ns: int
    ctime_ns: int
    mode: int

    @classmethod
    def of(cls, value: os.stat_result) -> _Version:
        return cls(
            value.st_dev,
            value.st_ino,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
            value.st_mode,
        )


@dataclass(frozen=True)
class _File:
    path: Path
    version: _Version
    link_version: _Version


@dataclass(frozen=True)
class _Manifest:
    files: tuple[_File, ...]
    directory: _Version | None
    charged_bytes: int


def _discover(base: Path, retention: int, budget: _Budget, limit: int) -> _Manifest:
    """Select legacy plus newest N files without materializing the directory.

    Reserve two manifests up front: the final proof must coexist with the first.
    All path/heap/version bookkeeping is conservatively included in the charge.
    """
    budget.check()
    if limit < 1024:
        raise _SourceFailure("safety_manifest_limit")
    if retention < 1:
        raise _SourceFailure("safety_source_config")
    directory = base.parent
    try:
        before = _Version.of(directory.stat())
    except FileNotFoundError:
        return _Manifest((), None, 1024)
    prefix, suffix = f"{base.name}.", ".jsonl"
    legacy_name = f"{base.name}.jsonl"
    kept: list[tuple[str, str, int]] = []
    legacy: str | None = None
    charged = 512
    with os.scandir(directory) as entries:
        for entry in entries:
            budget.check()
            name = entry.name
            cost = 1024 + 8 * (len(str(directory)) + len(name))
            if name == legacy_name:
                if entry.is_file():
                    if 2 * (charged + cost) > limit:
                        raise _SourceFailure("safety_manifest_limit")
                    legacy = name
                    charged += cost
                continue
            if not name.startswith(prefix) or not name.endswith(suffix):
                continue
            token = name[len(prefix) : -len(suffix)]
            if not _MONTH.match(token):
                continue
            if len(kept) >= retention and token <= kept[0][0]:
                continue
            if len(kept) >= retention:
                charged -= heapq.heappop(kept)[2]
            if 2 * (charged + cost) > limit:
                raise _SourceFailure("safety_manifest_limit")
            heapq.heappush(kept, (token, name, cost))
            charged += cost
    if _Version.of(directory.stat()) != before:
        raise _SourceFailure("safety_source_changed")
    kept.sort()
    names = ([legacy] if legacy is not None else []) + [row[1] for row in kept]
    files: list[_File] = []
    for name in names:
        budget.check()
        path = directory / name
        version = _Version.of(path.stat())
        if not stat.S_ISREG(version.mode):
            raise _SourceFailure("safety_source_unreadable")
        files.append(_File(path, version, _Version.of(path.lstat())))
    if _Version.of(directory.stat()) != before:
        raise _SourceFailure("safety_source_changed")
    return _Manifest(tuple(files), before, 2 * charged)


def _check_file(source: _File) -> None:
    if (
        _Version.of(source.path.stat()) != source.version
        or _Version.of(source.path.lstat()) != source.link_version
    ):
        raise _SourceFailure("safety_source_changed")


def _raw_rows(
    source: _File, budget: _Budget, limits: SafetyReadLimits
) -> Generator[bytes, None, None]:
    """Bounded universal LF/CRLF/CR rows, including an unterminated final row."""
    pending = bytearray()
    after_cr = False
    with source.path.open("rb") as handle:
        if _Version.of(os.fstat(handle.fileno())) != source.version:
            raise _SourceFailure("safety_source_changed")
        remaining = source.version.size
        while remaining:
            length = budget.read_size(min(limits.block_bytes, remaining))
            block = handle.read(length)
            budget.bytes_read += len(block)
            budget.check()
            if len(block) != length:
                raise _SourceFailure("safety_source_changed")
            remaining -= length
            start = 0
            if after_cr:
                start = int(block.startswith(b"\n"))
                after_cr = False
            for match in _LINE_END.finditer(block, start):
                end = match.start()
                if end < start:
                    continue
                if len(pending) + end - start > limits.row_bytes:
                    raise _SourceFailure("safety_row_limit")
                pending.extend(block[start:end])
                raw = bytes(pending)
                pending.clear()
                yield raw
                del raw
                start = end + 1
                if block[end] == 13:
                    if start < len(block) and block[start] == 10:
                        start += 1
                    elif start == len(block):
                        after_cr = True
            if len(pending) + len(block) - start > limits.row_bytes:
                raise _SourceFailure("safety_row_limit")
            pending.extend(block[start:])
        if pending:
            yield bytes(pending)
        if _Version.of(os.fstat(handle.fileno())) != source.version:
            raise _SourceFailure("safety_source_changed")
    _check_file(source)


def _activity_events(
    manifest: _Manifest,
    budget: _Budget,
    limits: SafetyReadLimits,
    diagnostics: dict[str, int | float | str],
) -> Generator[ActivityEvent, None, None]:
    rows_seen = 0
    for source in manifest.files:
        rows = _raw_rows(source, budget, limits)
        try:
            for raw in rows:
                rows_seen += 1
                if rows_seen % 256 == 0:
                    budget.check()
                # Decode text first: bytes json.loads would accept UTF-16/BOM.
                stripped = raw.decode("utf-8").strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except ValueError:
                    diagnostics["json_skips"] += 1  # type: ignore[operator]
                    logger.warning("Skipping malformed runtime activity row")
                    continue
                if not isinstance(payload, dict):
                    raise _SourceFailure("safety_nonobject_row")
                try:
                    event = ActivityEvent(**payload)
                except ValueError:
                    diagnostics["model_skips"] += 1  # type: ignore[operator]
                    logger.warning("Skipping unparseable runtime activity record")
                    continue
                del payload, stripped, raw
                diagnostics["rows_decoded"] += 1  # type: ignore[operator]
                yield event
                del event
        finally:
            rows.close()
        diagnostics["files_read"] += 1  # type: ignore[operator]


def _extra_charge(events: Sequence[ActivityEvent], limit: int) -> int:
    """Charge bounded owned references/structures without coercing scalar keys."""
    total = sys.getsizeof(()) + 8 * len(events)
    if total > limit:
        raise _SourceFailure("safety_extra_limit")
    active: set[int] = set()

    def charge(value: Any, depth: int = 0) -> None:
        nonlocal total
        if depth > 64:
            raise _SourceFailure("safety_extra_unsupported")
        kind = type(value)
        if kind not in (
            type(None),
            bool,
            int,
            float,
            str,
            bytes,
            list,
            tuple,
            dict,
            datetime,
            date,
            Decimal,
            ActivityEvent,
            GateReason,
            ActivityEventType,
        ):
            raise _SourceFailure("safety_extra_unsupported")
        total += sys.getsizeof(value) + 32
        if total > limit:
            raise _SourceFailure("safety_extra_limit")
        if kind in (list, tuple, dict, ActivityEvent):
            identity = id(value)
            if identity in active:
                raise _SourceFailure("safety_extra_unsupported")
            active.add(identity)
            try:
                if kind is ActivityEvent:
                    # Account for Pydantic's dictionaries/field-set scaffolding.
                    total += 1024
                    if total > limit:
                        raise _SourceFailure("safety_extra_limit")
                    for name in ActivityEvent.model_fields:
                        charge(getattr(value, name), depth + 1)
                elif kind is dict:
                    for key, item in value.items():
                        charge(key, depth + 1)
                        charge(item, depth + 1)
                else:
                    for item in value:
                        charge(item, depth + 1)
            finally:
                active.remove(identity)

    for event in events:
        if type(event) is not ActivityEvent:
            raise _SourceFailure("safety_extra_unsupported")
        charge(event)
    return total


@dataclass
class _Job:
    base: Path
    retention: int
    extras: tuple[ActivityEvent, ...]
    extra_bytes: int
    evaluated_at: datetime
    lookback_hours: int | None
    budget: _Budget
    future: concurrent.futures.Future[_Outcome] = field(
        default_factory=concurrent.futures.Future
    )
    discarded: bool = False


@dataclass(frozen=True)
class _Outcome:
    result: SafetyReadResult | None = None
    reason: str | None = None
    elapsed_seconds: float = 0.0
    bytes_read: int = 0


class SafetyReadService:
    """One active/zero queued reads; shutdown never waits for blocked disk IO."""

    def __init__(
        self,
        *,
        limits: SafetyReadLimits | None = None,
        clock: Callable[[], float] = time.monotonic,
        utc_clock: Callable[[], datetime] = now_utc,
    ) -> None:
        self.limits = limits or SafetyReadLimits()
        self._clock = clock
        self._utc_clock = utc_clock
        self._condition = threading.Condition()
        self._job: _Job | None = None
        self._thread: threading.Thread | None = None
        self._closed = False

    async def evaluate(
        self,
        activity_log: ActivityLog,
        extra_events: Sequence[ActivityEvent] | None = None,
        *,
        now: datetime,
        max_seconds: float = 30.0,
        max_bytes: int = 2 * 1024 * MiB,
        lookback_hours: int | None = 24,
    ) -> SafetyReadResult:
        """Evaluate with a frozen time and an owned, bounded extra container.

        Extra models belong to the caller and must not be mutated while this
        coroutine is pending. Retain their raw scalar identities, including
        shared NaNs, instead of deep copying or serializing their details.
        """
        started = self._clock()
        if not math.isfinite(max_seconds) or max_seconds <= 0 or max_bytes <= 0:
            raise SafetyReadUnavailable("safety_read_budget_exhausted")
        max_seconds = min(max_seconds, 30.0)
        max_bytes = min(max_bytes, 2 * 1024 * MiB)
        reason: str | None
        with self._condition:
            if self._closed:
                raise SafetyReadUnavailable("safety_reader_closed")
            if self._job is not None:
                raise SafetyReadUnavailable("safety_reader_busy")
            try:
                extras = () if extra_events is None else extra_events
                if type(extras) not in (list, tuple):
                    raise _SourceFailure("safety_extra_unsupported")
                if len(extras) > self.limits.extra_count:
                    raise _SourceFailure("safety_extra_limit")
                extra_bytes = _extra_charge(extras, self.limits.extra_bytes)
                job = _Job(
                    base=activity_log._rotator.base_path,
                    retention=activity_log._rotator.retention_months,
                    extras=tuple(extras),
                    extra_bytes=extra_bytes,
                    evaluated_at=ensure_utc(now),
                    lookback_hours=lookback_hours,
                    budget=_Budget(
                        started,
                        started + max_seconds,
                        max_bytes,
                        threading.Event(),
                        self._clock,
                    ),
                )
                job.budget.check()
            except _SourceFailure as failure:
                reason = failure.reason
                # Raise outside the exception context: no original cause retained.
                job = None
            else:
                reason = None
            if job is not None:
                self._job = job
                if self._thread is None:
                    self._thread = threading.Thread(
                        target=self._work, name="runtime-safety-reader", daemon=True
                    )
                    self._thread.start()
                self._condition.notify()
        if reason is not None or job is None:
            raise SafetyReadUnavailable(
                reason or "safety_read_failed",
                elapsed_seconds=self._clock() - started,
            )

        try:
            future = asyncio.wrap_future(job.future)
            outcome = await asyncio.wait_for(
                asyncio.shield(future), max(0.0, job.budget.deadline - self._clock())
            )
        except asyncio.TimeoutError:
            self._discard(job)
            # Quarantined IO can still consume its allowed bytes; reserve the
            # full cap so an engine cycle cannot undercharge that later work.
            raise SafetyReadUnavailable(
                "safety_read_timeout",
                elapsed_seconds=self._clock() - started,
                bytes_read=max_bytes,
            ) from None
        except asyncio.CancelledError:
            self._discard(job)
            raise
        if outcome.reason is not None:
            raise SafetyReadUnavailable(
                outcome.reason,
                elapsed_seconds=outcome.elapsed_seconds,
                bytes_read=outcome.bytes_read,
            )
        result = outcome.result
        age = (ensure_utc(self._utc_clock()) - job.evaluated_at).total_seconds()
        if age < 0 or age > max_seconds or self._clock() >= job.budget.deadline:
            raise SafetyReadUnavailable(
                "safety_evaluation_expired",
                elapsed_seconds=self._clock() - started,
                bytes_read=outcome.bytes_read,
            )
        if result is None:
            raise SafetyReadUnavailable("safety_read_failed")
        return SafetyReadResult(
            result.score,
            result.evaluated_at,
            self._clock() - started,
            result.bytes_read,
            result.diagnostics,
        )

    def _discard(self, job: _Job) -> None:
        with self._condition:
            job.discarded = True
            job.budget.cancelled.set()

    def shutdown(self) -> None:
        """Disallow admission and request cooperative cancellation; never join."""
        with self._condition:
            self._closed = True
            if self._job is not None:
                self._job.discarded = True
                self._job.budget.cancelled.set()
            self._condition.notify()

    def close(self) -> None:
        """Nonblocking lifecycle alias for owners of an injected service."""
        self.shutdown()

    def _work(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._job is not None or self._closed)
                job = self._job
                if job is None:
                    return
            try:
                result = self._read(job)
                outcome = _Outcome(
                    result=result,
                    elapsed_seconds=self._clock() - job.budget.started,
                    bytes_read=job.budget.bytes_read,
                )
            except (_SourceFailure, SafetyAggregationError) as failure:
                outcome = _Outcome(
                    reason=failure.reason,
                    elapsed_seconds=self._clock() - job.budget.started,
                    bytes_read=job.budget.bytes_read,
                )
            except UnicodeError:
                outcome = _Outcome(
                    reason="safety_invalid_utf8",
                    elapsed_seconds=self._clock() - job.budget.started,
                    bytes_read=job.budget.bytes_read,
                )
            except OSError:
                outcome = _Outcome(
                    reason="safety_source_unreadable",
                    elapsed_seconds=self._clock() - job.budget.started,
                    bytes_read=job.budget.bytes_read,
                )
            except Exception:
                outcome = _Outcome(
                    reason="safety_read_failed",
                    elapsed_seconds=self._clock() - job.budget.started,
                    bytes_read=job.budget.bytes_read,
                )
            with self._condition:
                if job.discarded:
                    outcome = _Outcome(
                        reason="safety_read_cancelled",
                        elapsed_seconds=self._clock() - job.budget.started,
                        bytes_read=job.budget.bytes_read,
                    )
                self._job = None
                job.future.set_result(outcome)
            # The waiting daemon must not retain the previous job's extras.
            del job, outcome
            if "result" in locals():
                del result

    def _read(self, job: _Job) -> SafetyReadResult:
        budget = job.budget
        manifest = _discover(
            job.base, job.retention, budget, self.limits.manifest_bytes
        )
        diagnostics: dict[str, int | float | str] = {
            "rows_decoded": 0,
            "json_skips": 0,
            "model_skips": 0,
            "files_read": 0,
            "manifest_bytes": manifest.charged_bytes,
        }
        accumulator = SafetyAccumulator(
            lookback_hours=job.lookback_hours,
            now=job.evaluated_at,
            max_state_bytes=self.limits.state_bytes,
            max_distinct_keys=self.limits.distinct_keys,
            reserved_extra_bytes=job.extra_bytes,
        )
        events = _activity_events(manifest, budget, self.limits, diagnostics)
        try:
            for event in events:
                accumulator.add(event)
                del event
        finally:
            events.close()
        for i, event in enumerate(job.extras):
            if i % 256 == 0:
                budget.check()
            accumulator.add(event)
        proof = _discover(job.base, job.retention, budget, self.limits.manifest_bytes)
        if proof != manifest:
            raise _SourceFailure("safety_source_changed")
        for source in manifest.files:
            budget.check()
            # Opening even an empty file proves readability at publication.
            with source.path.open("rb") as handle:
                if _Version.of(os.fstat(handle.fileno())) != source.version:
                    raise _SourceFailure("safety_source_changed")
            _check_file(source)
        budget.check()
        diagnostics["state_bytes"] = accumulator.state_bytes
        diagnostics["distinct_keys"] = accumulator.distinct_keys
        score = compute_runtime_safety_score(accumulator.finish())
        return SafetyReadResult(
            score,
            job.evaluated_at,
            self._clock() - budget.started,
            budget.bytes_read,
            diagnostics,
        )


_shared_lock = threading.Lock()
_shared_service: SafetyReadService | None = None
_shared_closed = False


def get_safety_read_service() -> SafetyReadService:
    global _shared_service
    with _shared_lock:
        if _shared_service is None:
            _shared_service = SafetyReadService()
            if _shared_closed:
                _shared_service.shutdown()
        return _shared_service


def shutdown_shared_safety_read_service() -> None:
    """Process teardown only; a closed singleton is never replaced."""
    global _shared_closed
    with _shared_lock:
        _shared_closed = True
        if _shared_service is not None:
            _shared_service.shutdown()

"""Bounded, process-owned canonical activity input for pre-order safety checks.

No exchange/notification work lives here. A timed-out worker retains its slot
until it actually unwinds; failed/late reads never become a healthy score.
"""

from __future__ import annotations

import asyncio
import atexit
import heapq
import json
import os
import queue
import re
import sys
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.logger import get_logger
from src.runtime.activity_events import ActivityEvent
from src.runtime.safety_score import (
    RuntimeSafetyScore,
    SafetyAccumulator,
    compute_runtime_safety_score,
)
from src.utils.bounded_read import Generation, ReadFailure, legacy_text_rows
from src.utils.time import ensure_utc, now_utc

logger = get_logger("crypto_master.runtime.safety_reader")
_MONTH = re.compile(r"^\d{4}-\d{2}$")
_MIB = 1024 * 1024


class SafetyReadUnavailable(Exception):
    """Allowlisted stable failure; never holds a worker's traceback/payload."""


@dataclass(frozen=True)
class SafetyReadLimits:
    state_bytes: int = 16 * _MIB
    manifest_bytes: int = 4 * _MIB
    summary_bytes: int = 2 * _MIB
    conditions: int = 50_000
    extra_count: int = 4096
    extra_bytes: int = 2 * _MIB
    row_bytes: int = _MIB
    read_bytes: int = 2 * 1024 * _MIB
    read_seconds: float = 30.0
    cycle_bytes: int = 4 * 1024 * _MIB
    cycle_seconds: float = 60.0


@dataclass
class SafetyCycleBudget:
    seconds: float = 0.0
    bytes: int = 0


def structural_size(value: Any, limit: int) -> int:
    """Conservative bounded traversal; shared objects are charged repeatedly."""
    total = 0
    stack = [iter((value,))]
    while stack:
        try:
            item = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue
        total += sys.getsizeof(item) + 32
        if total > limit or len(stack) > 128:
            raise SafetyReadUnavailable("state_limit")
        if isinstance(item, ActivityEvent):
            stack.append(iter((item.__dict__,)))
        elif isinstance(item, dict):
            stack.append(iter(item.items()))
        elif isinstance(item, (list, tuple, set, frozenset)):
            stack.append(iter(item))
        elif not isinstance(item, (str, bytes, int, float, bool, type(None), datetime)):
            raise SafetyReadUnavailable("unsupported_state")
    return total


@dataclass(frozen=True)
class Source:
    path: Path
    generation: Generation
    ctime_ns: int
    mode: int

    @classmethod
    def capture(cls, path: Path) -> Source:
        stat = path.stat()
        return cls(
            path,
            Generation(stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns),
            stat.st_ctime_ns,
            stat.st_mode,
        )

    def verify(self) -> None:
        # Open even a summary-cache hit, so lost readability cannot be hidden.
        with self.path.open("rb") as handle:
            stat = os.fstat(handle.fileno())
            proof = Source(
                self.path,
                Generation(stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns),
                stat.st_ctime_ns,
                stat.st_mode,
            )
        if proof != self or Source.capture(self.path) != self:
            raise SafetyReadUnavailable("source_changed")


@dataclass
class ReadControl:
    limits: SafetyReadLimits
    cycle: SafetyCycleBudget
    started: float
    deadline: float
    cancelled: threading.Event = field(default_factory=threading.Event)
    bytes: int = 0
    state: int = 0

    def check(self) -> None:
        if self.cancelled.is_set():
            raise SafetyReadUnavailable("cancelled")
        if time.monotonic() >= self.deadline:
            raise SafetyReadUnavailable("deadline")

    def read(self, length: int) -> None:
        self.check()
        if (
            self.bytes + length > self.limits.read_bytes
            or self.cycle.bytes + length > self.limits.cycle_bytes
        ):
            raise SafetyReadUnavailable("read_limit")
        self.bytes += length
        self.cycle.bytes += length

    def reserve(self, value: Any) -> None:
        charge = structural_size(value, self.limits.state_bytes - self.state) + 128
        if self.state + charge > self.limits.state_bytes:
            raise SafetyReadUnavailable("state_limit")
        self.state += charge


def capture_sources(
    base: Path, retention: int, control: ReadControl
) -> tuple[Source, ...]:
    # Half the manifest cap permits final re-discovery while the original lives.
    cap = control.limits.manifest_bytes // 2
    selected: list[tuple[str, str]] = []
    charged = 0
    parent = base.parent
    if not parent.exists():
        control.check()
        return ()
    prefix = base.name + "."
    with os.scandir(parent) as entries:
        for entry in entries:
            control.check()
            name = entry.name
            if not name.startswith(prefix) or not name.endswith(".jsonl"):
                continue
            token = name[len(prefix) : -6]
            if not _MONTH.fullmatch(token):
                continue
            charge = len(name.encode("utf-8")) * 4 + 1024
            if len(selected) < retention:
                if charged + charge > cap:
                    raise SafetyReadUnavailable("manifest_limit")
                heapq.heappush(selected, (token, name))
                charged += charge
            elif selected and token > selected[0][0]:
                old = selected[0][1]
                delta = charge - (len(old.encode("utf-8")) * 4 + 1024)
                if charged + delta > cap:
                    raise SafetyReadUnavailable("manifest_limit")
                heapq.heapreplace(selected, (token, name))
                charged += delta
    legacy = base.with_name(base.name + ".jsonl")
    paths = [parent / name for _, name in sorted(selected)]
    if legacy.exists() and legacy.is_file():
        paths.insert(0, legacy)
    if sum(len(str(p).encode("utf-8")) * 4 + 1024 for p in paths) > cap:
        raise SafetyReadUnavailable("manifest_limit")
    return tuple(Source.capture(path) for path in paths)


@dataclass(frozen=True)
class ValidationSummary:
    maximum: datetime | None
    dynamic: bool
    skipped: int
    charge: int


class CanonicalSafetyReader:
    """Worker-only bounded source reduction; summary cache contains no events."""

    def __init__(self) -> None:
        self.summaries: OrderedDict[Source, ValidationSummary] = OrderedDict()
        self.summary_bytes = 0
        self.roots: list[Path] = []

    def evaluate(
        self,
        base: Path,
        retention: int,
        extras: tuple[ActivityEvent, ...],
        at: datetime,
        control: ReadControl,
    ) -> RuntimeSafetyScore:
        cutoff = at - timedelta(hours=24)
        if base not in self.roots:
            if len(self.roots) >= 2:
                self.summaries.clear()
                self.summary_bytes = 0
                self.roots.clear()
            self.roots.append(base)
        sources = capture_sources(base, retention, control)
        accumulator = SafetyAccumulator(
            max_conditions=control.limits.conditions, reserve=control.reserve
        )
        for source in sources:
            control.check()
            source.verify()
            cached = self.summaries.get(source)
            if (
                cached is not None
                and not cached.dynamic
                and (cached.maximum is None or cached.maximum < cutoff)
            ):
                if cached.skipped:
                    logger.warning(
                        "Safety archive retains %s legacy skipped rows", cached.skipped
                    )
                self.summaries.move_to_end(source)
                continue
            maximum = None
            dynamic = False
            skipped = 0
            rows = 0
            with closing(
                legacy_text_rows(
                    source.path,
                    source.generation,
                    record_bytes=control.limits.row_bytes,
                    before_read=control.read,
                )
            ) as iterator:
                for raw in iterator:
                    if raw is None:
                        control.check()
                        continue
                    rows += 1
                    if rows % 256 == 0:
                        control.check()
                    if not raw:
                        continue
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        skipped += 1
                        continue
                    if not isinstance(payload, dict):
                        raise SafetyReadUnavailable("invalid_record")
                    try:
                        event = ActivityEvent(**payload)
                    except ValueError:
                        skipped += 1
                        continue
                    dynamic |= "timestamp" not in payload
                    timestamp = ensure_utc(event.timestamp)
                    maximum = timestamp if maximum is None else max(maximum, timestamp)
                    if timestamp >= cutoff:
                        accumulator.add(event)
                    del event, payload
            source.verify()
            if skipped:
                logger.warning("Safety archive retains %s legacy skipped rows", skipped)
            charge = len(str(source.path).encode("utf-8")) * 4 + 1024
            previous = self.summaries.pop(source, None)
            if previous is not None:
                self.summary_bytes -= previous.charge
            while self.summaries and (
                len(self.summaries) >= 64
                or self.summary_bytes + charge > control.limits.summary_bytes
            ):
                _, removed = self.summaries.popitem(last=False)
                self.summary_bytes -= removed.charge
            if charge <= control.limits.summary_bytes:
                self.summaries[source] = ValidationSummary(
                    maximum, dynamic, skipped, charge
                )
                self.summary_bytes += charge
        for event in extras:
            control.check()
            if ensure_utc(event.timestamp) >= cutoff:
                accumulator.add(event)
        if capture_sources(base, retention, control) != sources:
            raise SafetyReadUnavailable("source_changed")
        for source in sources:
            source.verify()
        control.check()
        age = (ensure_utc(now_utc()) - at).total_seconds()
        if age < 0 or age > control.limits.read_seconds:
            raise SafetyReadUnavailable("clock_age")
        return compute_runtime_safety_score(accumulator.inputs)


@dataclass
class Job:
    base: Path
    retention: int
    extras: tuple[ActivityEvent, ...]
    at: datetime
    control: ReadControl
    future: Future[tuple[RuntimeSafetyScore | None, str | None]]


class SafetyReadService:
    """One daemon, one occupied slot, no queued evaluations."""

    def __init__(self, limits: SafetyReadLimits | None = None) -> None:
        self.limits = limits or SafetyReadLimits()
        self._lock = threading.Lock()
        self._busy = False
        self._closed = False
        self._queue: queue.Queue[Job | None] = queue.Queue(maxsize=1)
        self._thread: threading.Thread | None = None
        self._reader = CanonicalSafetyReader()
        self._control: ReadControl | None = None

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            if job is None:
                return
            outcome: tuple[RuntimeSafetyScore | None, str | None]
            try:
                score = self._reader.evaluate(
                    job.base, job.retention, job.extras, job.at, job.control
                )
                outcome = (score, None)
            except (SafetyReadUnavailable, ReadFailure) as error:
                outcome = (None, str(error))
            except Exception:
                # Do not transfer exceptions/tracebacks/source state to the loop.
                outcome = (None, "input_unavailable")
            finally:
                job.control.cycle.seconds += time.monotonic() - job.control.started
            with self._lock:
                self._busy = False
                self._control = None
            if not job.future.cancelled():
                job.future.set_result(outcome)
            del job, outcome
            if self._closed:
                return

    async def score(
        self,
        base: Path,
        retention: int,
        extra_events: list[ActivityEvent] | None,
        cycle: SafetyCycleBudget,
    ) -> RuntimeSafetyScore:
        started = time.monotonic()
        at = ensure_utc(now_utc())
        remaining = min(
            self.limits.read_seconds, self.limits.cycle_seconds - cycle.seconds
        )
        if remaining <= 0 or cycle.bytes >= self.limits.cycle_bytes:
            raise SafetyReadUnavailable("cycle_limit")
        extras = extra_events if extra_events is not None else []
        if len(extras) > self.limits.extra_count:
            raise SafetyReadUnavailable("extra_limit")
        extra_charge = structural_size(extras, self.limits.extra_bytes)
        control = ReadControl(
            self.limits, cycle, started, started + remaining, state=extra_charge
        )
        if control.state > self.limits.state_bytes:
            raise SafetyReadUnavailable("state_limit")
        future: Future[tuple[RuntimeSafetyScore | None, str | None]] = Future()
        with self._lock:
            if self._closed or self._busy:
                raise SafetyReadUnavailable("reader_busy")
            self._busy = True
            self._control = control
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self._run, name="runtime-safety-reader", daemon=True
                )
                self._thread.start()
            self._queue.put_nowait(
                Job(base, retention, tuple(extras), at, control, future)
            )
        try:
            outcome = await asyncio.wait_for(
                asyncio.shield(asyncio.wrap_future(future)),
                max(0.0, control.deadline - time.monotonic()),
            )
        except (TimeoutError, asyncio.CancelledError) as error:
            control.cancelled.set()
            if isinstance(error, asyncio.CancelledError):
                raise
            raise SafetyReadUnavailable("deadline") from None
        score, reason = outcome
        control.check()
        if reason is not None or score is None:
            raise SafetyReadUnavailable(reason or "input_unavailable")
        age = (ensure_utc(now_utc()) - at).total_seconds()
        if age < 0 or age > remaining:
            raise SafetyReadUnavailable("clock_age")
        return score

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._control is not None:
                self._control.cancelled.set()
            if not self._busy and self._thread is not None:
                self._queue.put_nowait(None)


_SERVICE: SafetyReadService | None = None
_SERVICE_LOCK = threading.Lock()


def safety_read_service() -> SafetyReadService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = SafetyReadService()
            atexit.register(_SERVICE.close)
        return _SERVICE

"""Append-only activity log for the trading engine (Phase 8.1).

Every meaningful step the engine takes — cycle started, proposal
generated, auto-decision, position opened/closed, monitor pass,
sleep, shutdown — is recorded as one JSON line. The dashboard reads
this file to surface what the engine is doing in real time.

The format mirrors :mod:`src.feedback.audit` (``AuditLog``): one JSON
object per line, independent open/append/close per write so concurrent
readers and writers don't corrupt earlier events. The append-only
shape means a crash leaves at most one partially-written final line —
which ``read_all`` skips with a warning.

Related Requirements:
- FR-009 / FR-010: Live + paper trading mode (production wiring)
- FR-026: Automated Feedback Loop (visibility into the loop)
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.logger import get_logger

logger = get_logger("crypto_master.runtime.activity_log")


DEFAULT_ACTIVITY_PATH = Path("data/runtime/activity.jsonl")


class ActivityEventType(str, Enum):
    """Lifecycle events the engine emits.

    Values are stable strings — the dashboard filters on them and
    they are written as-is into the JSONL log.
    """

    # Process lifecycle
    STARTUP = "startup"
    SHUTDOWN = "shutdown"

    # Cycle lifecycle
    CYCLE_STARTED = "cycle_started"
    CYCLE_COMPLETED = "cycle_completed"
    CYCLE_ERRORED = "cycle_errored"
    SLEEPING = "sleeping"

    # Scan + propose
    SCAN_ERRORED = "scan_errored"
    PROPOSAL_GENERATED = "proposal_generated"
    PROPOSAL_ACCEPTED = "proposal_accepted"
    PROPOSAL_REJECTED = "proposal_rejected"

    # Execution
    POSITION_OPENED = "position_opened"
    POSITION_OPEN_ERRORED = "position_open_errored"

    # Monitoring
    MONITOR_PASS = "monitor_pass"
    POSITION_CLOSED = "position_closed"
    MONITOR_ERRORED = "monitor_errored"


class ActivityEvent(BaseModel):
    """A single activity log entry.

    Attributes:
        timestamp: When the event happened (UTC-naive ``datetime.now``
            to match the rest of this codebase).
        event_type: One of :class:`ActivityEventType`.
        message: Short human-readable summary — what shows up in the
            dashboard's activity timeline.
        details: Free-form JSON-serializable payload. Conventional keys:
            ``proposal_id``, ``trade_id``, ``symbol``, ``score``, ``pnl``,
            ``error``. Engine appends whatever is useful per event.
        cycle_id: UUID linking events from the same cycle so the
            dashboard can group them. ``None`` for process-level events
            (startup, shutdown).
    """

    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: ActivityEventType
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    cycle_id: str | None = None

    model_config = {"use_enum_values": True}


class ActivityLog:
    """Append-only JSONL activity log for the runtime engine.

    Stateless apart from the file path: every ``append`` is an
    independent open/write/close so concurrent dashboard reads don't
    race with engine writes.

    Usage::

        log = ActivityLog()
        log.append(
            ActivityEventType.CYCLE_STARTED,
            "Cycle 14 begin",
            details={"cycle_index": 14},
            cycle_id="abc-123",
        )
        events = log.tail(50)
    """

    def __init__(self, path: Path | None = None) -> None:
        """Initialize the log.

        Args:
            path: Where to read from / append to. Defaults to
                ``data/runtime/activity.jsonl``. Tests should pass
                ``tmp_path / "activity.jsonl"``.
        """
        self.path = path or DEFAULT_ACTIVITY_PATH

    def append(
        self,
        event_type: ActivityEventType,
        message: str = "",
        *,
        details: dict[str, Any] | None = None,
        cycle_id: str | None = None,
    ) -> ActivityEvent:
        """Append one event to the log and return it for chaining."""
        event = ActivityEvent(
            event_type=event_type,
            message=message,
            details=details or {},
            cycle_id=cycle_id,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = event.model_dump_json()
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        logger.debug(
            f"Activity: {event.event_type} {event.message} " f"cycle={event.cycle_id}"
        )
        return event

    def read_all(self) -> list[ActivityEvent]:
        """Load every event from the log.

        Skips malformed trailing lines (the only kind a crash can
        produce) with a warning. Empty / missing files return an
        empty list.
        """
        if not self.path.exists():
            return []
        events: list[ActivityEvent] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                    events.append(ActivityEvent(**payload))
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(
                        f"Skipping malformed activity line {lineno} in "
                        f"{self.path}: {e}"
                    )
        return events

    def tail(self, n: int = 100) -> list[ActivityEvent]:
        """Return the most recent ``n`` events in append order.

        The dashboard's timeline shows these top-to-bottom as oldest →
        newest within the slice. ``n`` ≤ 0 returns an empty list.
        """
        if n <= 0:
            return []
        events = self.read_all()
        return events[-n:] if len(events) > n else events

    def filter(
        self,
        *,
        cycle_id: str | None = None,
        event_type: ActivityEventType | str | None = None,
    ) -> list[ActivityEvent]:
        """Return events matching all supplied predicates.

        Args:
            cycle_id: Keep only events with this cycle id.
            event_type: Keep only events of this type. Accepts the
                enum or its raw string value.
        """
        events = self.read_all()
        if cycle_id is not None:
            events = [e for e in events if e.cycle_id == cycle_id]
        if event_type is not None:
            wanted = (
                event_type.value
                if isinstance(event_type, ActivityEventType)
                else event_type
            )
            events = [e for e in events if e.event_type == wanted]
        return events


__all__ = [
    "DEFAULT_ACTIVITY_PATH",
    "ActivityEvent",
    "ActivityEventType",
    "ActivityLog",
]

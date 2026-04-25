"""Append-only audit log for the feedback loop.

Every promote / demote / discard / approve / reject event in the
feedback loop is recorded here. The format is JSON Lines (one event
per line) so the file is:

* **Append-only** — concurrent writers can't corrupt earlier events,
  and a partially-written final line is the only thing a crash can
  leave behind.
* **Human-greppable** — operators can inspect the trail without code.
* **Cheaply replayable** — ``read_all()`` reconstructs full state by
  iterating the file.

The audit log is the source of truth for "what happened to which
candidate." ``CandidateRecord`` JSON files capture the latest snapshot;
this log captures the full history.

Related Requirements:
- FR-026: Automated Feedback Loop
- FR-027: Technique Adoption (traceability)
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.logger import get_logger

logger = get_logger("crypto_master.feedback.audit")


DEFAULT_AUDIT_PATH = Path("data/audit/feedback.jsonl")


class AuditEventType(str, Enum):
    """Lifecycle events recorded in the audit log."""

    GENERATED = "generated"
    BACKTESTED = "backtested"
    GATE_PASSED = "gate_passed"
    GATE_FAILED = "gate_failed"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROMOTED = "promoted"
    DISCARDED = "discarded"
    ERRORED = "errored"


class AuditEvent(BaseModel):
    """A single audit log entry.

    Attributes:
        timestamp: When the event happened (UTC-naive ``datetime.now``
            to match the rest of this codebase).
        event_type: One of ``AuditEventType``.
        candidate_id: UUID of the candidate this event belongs to.
        technique_name: Technique name at the time of the event.
        technique_version: Technique version at the time of the event.
        actor: ``"system"`` for automated events; the approver's name
            for ``APPROVED`` / ``REJECTED``.
        details: Free-form JSON-serializable diagnostics. The loop
            populates this with gate verdicts, error messages, file
            paths, etc.
    """

    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: AuditEventType
    candidate_id: str
    technique_name: str
    technique_version: str
    actor: str = "system"
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}


class AuditLog:
    """Append-only JSONL audit log writer + reader.

    Stateless apart from the file path; every ``append`` is an
    independent open/write/close so concurrent writers do not need
    coordination beyond the OS-level append guarantee.

    Usage::

        log = AuditLog()
        log.append(AuditEvent(
            event_type=AuditEventType.GENERATED,
            candidate_id="abc",
            technique_name="my_strat",
            technique_version="0.1.0",
        ))
        history = log.read_all()
    """

    def __init__(self, path: Path | None = None) -> None:
        """Initialize the audit log.

        Args:
            path: Where to read from / append to. Defaults to
                ``data/audit/feedback.jsonl``. Tests should supply
                ``tmp_path / "audit.jsonl"`` to avoid touching the
                real data directory.
        """
        self.path = path or DEFAULT_AUDIT_PATH

    def append(self, event: AuditEvent) -> None:
        """Append one event to the log.

        Creates the parent directory on first write so callers don't
        have to pre-create ``data/audit/``.

        Args:
            event: The event to record.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Pydantic's ``model_dump_json`` produces a single-line JSON
        # object — exactly what JSONL wants.
        line = event.model_dump_json()
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        logger.debug(
            f"Audit: {event.event_type} candidate={event.candidate_id} "
            f"technique={event.technique_name}"
        )

    def read_all(self) -> list[AuditEvent]:
        """Load every event from the log.

        Skips malformed trailing lines (the only kind a crash can
        produce) with a warning. Empty / missing files return an empty
        list.

        Returns:
            All successfully-parsed events, in append order.
        """
        if not self.path.exists():
            return []
        events: list[AuditEvent] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                    events.append(AuditEvent(**payload))
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(
                        f"Skipping malformed audit line {lineno} in "
                        f"{self.path}: {e}"
                    )
        return events

    def filter(
        self,
        candidate_id: str | None = None,
        event_type: AuditEventType | None = None,
    ) -> list[AuditEvent]:
        """Return events matching all supplied predicates.

        Args:
            candidate_id: If set, keep only events for this candidate.
            event_type: If set, keep only events of this type.

        Returns:
            Matching events in append order.
        """
        events = self.read_all()
        if candidate_id is not None:
            events = [e for e in events if e.candidate_id == candidate_id]
        if event_type is not None:
            wanted = (
                event_type.value
                if isinstance(event_type, AuditEventType)
                else event_type
            )
            events = [e for e in events if e.event_type == wanted]
        return events


__all__ = [
    "AuditEvent",
    "AuditEventType",
    "AuditLog",
    "DEFAULT_AUDIT_PATH",
]

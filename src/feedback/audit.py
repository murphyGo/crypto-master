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

Phase 10.4 routes the file through :class:`JsonlRotator` so writes
land in monthly files (``feedback.YYYY-MM.jsonl``) and reads merge the
active month + the most-recent ``Settings.log_retention_months``
archives.

Related Requirements:
- FR-026: Automated Feedback Loop
- FR-027: Technique Adoption (traceability)
- NFR-008: log retention (Phase 10.4).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.config import get_settings
from src.logger import get_logger
from src.runtime.jsonl_rotator import JsonlRotator
from src.utils.time import ensure_utc, now_utc

logger = get_logger("crypto_master.feedback.audit")


# Relative path used as a fallback marker; the real default is computed
# from ``Settings.data_dir`` at construction time so the audit trail
# survives container recycles on managed hosts (Phase 10.5).
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
        timestamp: When the event happened (UTC-aware ``now_utc()``
            per Phase 21.2). Legacy on-disk records may carry naive
            timestamps; readers that compare timestamps must coerce
            to UTC at the read boundary.
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

    timestamp: datetime = Field(default_factory=now_utc)
    event_type: AuditEventType
    candidate_id: str
    technique_name: str
    technique_version: str
    actor: str = "system"
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}

    @field_validator("timestamp", mode="after")
    @classmethod
    def _coerce_timestamp_to_utc(cls, value: datetime) -> datetime:
        """Coerce naive on-disk timestamps to UTC (DEBT-025 / Phase 21.2).

        Audit events written before the 21.2 sweep persist naive
        timestamps; mixing them with new aware timestamps in
        dashboard sorts raises ``TypeError``. ``ensure_utc`` makes
        every loaded ``AuditEvent`` UTC-aware regardless of the
        on-disk shape.
        """
        return ensure_utc(value)


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

    def __init__(
        self,
        path: Path | None = None,
        *,
        data_dir: Path | None = None,
    ) -> None:
        """Initialize the audit log.

        Args:
            path: Where to read from / append to. When supplied, this
                explicit path wins (tests should supply
                ``tmp_path / "audit.jsonl"`` to avoid touching the
                real data directory). A trailing ``.jsonl`` suffix is
                stripped to derive the rotator base so existing test
                fixtures keep working.
            data_dir: Optional override for the audit data root.
                When ``path`` is not given, the audit log defaults to
                ``<data_dir>/audit/feedback`` (no extension — it is
                the rotator base; the actual files are
                ``feedback.YYYY-MM.jsonl``). ``data_dir`` itself
                defaults to ``Settings().data_dir`` so the trail lands
                on the persistent volume (Phase 10.5).
        """
        if path is not None:
            self.path = path
            base = path.with_suffix("") if path.suffix == ".jsonl" else path
        else:
            root = data_dir if data_dir is not None else get_settings().data_dir
            base = root / "audit" / "feedback"
            self.path = base.with_name("feedback.jsonl")

        retention = get_settings().log_retention_months
        self._rotator = JsonlRotator(base, retention_months=retention)

    def append(self, event: AuditEvent) -> None:
        """Append one event to the log.

        Routes through :class:`JsonlRotator` so the active calendar
        month determines the destination file (``feedback.YYYY-MM.jsonl``).
        Creates the parent directory on first write so callers don't
        have to pre-create ``data/audit/``.

        Args:
            event: The event to record.
        """
        record = event.model_dump(mode="json")
        self._rotator.append(record)
        logger.debug(
            f"Audit: {event.event_type} candidate={event.candidate_id} "
            f"technique={event.technique_name}"
        )

    def read_all(self) -> list[AuditEvent]:
        """Load every event across the active month + retained archives.

        Skips malformed trailing lines (the only kind a crash can
        produce) with a warning. Empty / missing files return an empty
        list.

        Returns:
            All successfully-parsed events, in timestamp order.
        """
        events: list[AuditEvent] = []
        for payload in self._rotator.read_all():
            try:
                events.append(AuditEvent(**payload))
            except ValueError as e:
                logger.warning(f"Skipping unparseable audit record: {e}")
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

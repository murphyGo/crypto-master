"""Automated feedback loop for analysis-technique evolution.

The feedback loop wires together the building blocks produced in
Phases 5.1–5.4 — the Claude-driven improver, the backtester, and the
robustness gate — into a single orchestrator that takes a technique
candidate from generation through validation and (with explicit user
approval) into the active strategy set.

Related Requirements:
- FR-026: Automated Feedback Loop
- FR-027: Technique Adoption (user approval required)
- FR-034: Robustness Validation Gate
- CON-003: User Approval Required
"""

from src.feedback.audit import AuditEvent, AuditEventType, AuditLog
from src.feedback.loop import (
    CandidateRecord,
    FeedbackLoop,
    FeedbackLoopError,
    LoopStatus,
)

__all__ = [
    "AuditEvent",
    "AuditEventType",
    "AuditLog",
    "CandidateRecord",
    "FeedbackLoop",
    "FeedbackLoopError",
    "LoopStatus",
]

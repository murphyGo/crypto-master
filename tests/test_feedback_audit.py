"""Tests for the feedback-loop audit log."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.feedback.audit import AuditEvent, AuditEventType, AuditLog


def make_event(
    event_type: AuditEventType = AuditEventType.GENERATED,
    candidate_id: str = "cand-1",
    technique_name: str = "tech_a",
    technique_version: str = "0.1.0",
    actor: str = "system",
    details: dict | None = None,
) -> AuditEvent:
    return AuditEvent(
        event_type=event_type,
        candidate_id=candidate_id,
        technique_name=technique_name,
        technique_version=technique_version,
        actor=actor,
        details=details or {},
    )


def test_append_and_read_round_trip(tmp_path: Path) -> None:
    log = AuditLog(path=tmp_path / "audit.jsonl")
    e1 = make_event(event_type=AuditEventType.GENERATED)
    e2 = make_event(event_type=AuditEventType.BACKTESTED)
    log.append(e1)
    log.append(e2)

    history = log.read_all()
    assert len(history) == 2
    assert history[0].event_type == AuditEventType.GENERATED.value
    assert history[1].event_type == AuditEventType.BACKTESTED.value


def test_append_creates_parent_dir(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "nested" / "audit.jsonl"
    log = AuditLog(path=nested)
    log.append(make_event())
    assert nested.exists()
    assert nested.parent.is_dir()


def test_jsonl_format(tmp_path: Path) -> None:
    """Each appended event is one self-contained JSON line."""
    log = AuditLog(path=tmp_path / "audit.jsonl")
    log.append(make_event(event_type=AuditEventType.GENERATED))
    log.append(make_event(event_type=AuditEventType.PROMOTED))

    raw = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    lines = [line for line in raw.split("\n") if line]
    assert len(lines) == 2
    for line in lines:
        payload = json.loads(line)  # each line must parse independently
        assert "event_type" in payload
        assert "candidate_id" in payload


def test_malformed_trailing_line_is_skipped(tmp_path: Path) -> None:
    """A crash mid-write can leave a partial last line. Don't crash."""
    log = AuditLog(path=tmp_path / "audit.jsonl")
    log.append(make_event())
    # Simulate a half-written line.
    with (tmp_path / "audit.jsonl").open("a", encoding="utf-8") as fh:
        fh.write('{"timestamp": "2026-')

    history = log.read_all()
    assert len(history) == 1  # only the well-formed event survives


def test_read_returns_empty_for_missing_file(tmp_path: Path) -> None:
    log = AuditLog(path=tmp_path / "does-not-exist.jsonl")
    assert log.read_all() == []


def test_filter_by_candidate_and_event_type(tmp_path: Path) -> None:
    log = AuditLog(path=tmp_path / "audit.jsonl")
    log.append(make_event(candidate_id="A", event_type=AuditEventType.GENERATED))
    log.append(make_event(candidate_id="A", event_type=AuditEventType.BACKTESTED))
    log.append(make_event(candidate_id="B", event_type=AuditEventType.GENERATED))

    only_a = log.filter(candidate_id="A")
    assert len(only_a) == 2
    assert {e.event_type for e in only_a} == {
        AuditEventType.GENERATED.value,
        AuditEventType.BACKTESTED.value,
    }

    only_generated = log.filter(event_type=AuditEventType.GENERATED)
    assert len(only_generated) == 2
    assert {e.candidate_id for e in only_generated} == {"A", "B"}

    a_and_generated = log.filter(candidate_id="A", event_type=AuditEventType.GENERATED)
    assert len(a_and_generated) == 1


def test_event_type_serializes_as_string(tmp_path: Path) -> None:
    """JSONL must contain string event types, not enum reprs."""
    log = AuditLog(path=tmp_path / "audit.jsonl")
    log.append(make_event(event_type=AuditEventType.GATE_PASSED))

    raw = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    payload = json.loads(raw.strip())
    assert payload["event_type"] == "gate_passed"


def test_default_timestamp_is_set(tmp_path: Path) -> None:
    log = AuditLog(path=tmp_path / "audit.jsonl")
    before = datetime.now()
    log.append(make_event())
    history = log.read_all()
    assert before <= history[0].timestamp

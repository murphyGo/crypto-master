"""Tests for the feedback-loop audit log."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.config import reload_settings
from src.feedback import audit as audit_module
from src.feedback.audit import AuditEvent, AuditEventType, AuditLog
from src.runtime import jsonl_rotator


def _set_clock(monkeypatch: pytest.MonkeyPatch, when: datetime) -> None:
    """Pin ``now_utc()`` for both the rotator and the audit-event model.

    Phase 21.2: write-time wall-clock comes from ``now_utc()`` in two
    spots — the rotator's active-month token and ``AuditEvent``'s
    default ``timestamp`` factory. Patching both keeps tests
    deterministic across the boundary.
    """
    fixed = when if when.tzinfo is not None else when.replace(tzinfo=timezone.utc)
    monkeypatch.setattr(jsonl_rotator, "now_utc", lambda: fixed)
    monkeypatch.setattr(audit_module, "now_utc", lambda: fixed)


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


def test_constructor_respects_settings_data_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default audit path is rooted under Settings.data_dir (Phase 10.5)."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    reload_settings()
    try:
        log = AuditLog()
    finally:
        monkeypatch.delenv("DATA_DIR", raising=False)
        reload_settings()

    assert log.path == tmp_path / "audit" / "feedback.jsonl"
    assert tmp_path in log.path.parents


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
    # Phase 10.4 routes writes through the monthly rotator. The
    # parent must exist; the actual file lives next to ``log.path``
    # with a ``YYYY-MM`` token.
    assert nested.parent.is_dir()
    rotated = list(nested.parent.glob("audit.*.jsonl"))
    assert len(rotated) == 1


def test_jsonl_format(tmp_path: Path) -> None:
    """Each appended event is one self-contained JSON line."""
    log = AuditLog(path=tmp_path / "audit.jsonl")
    log.append(make_event(event_type=AuditEventType.GENERATED))
    log.append(make_event(event_type=AuditEventType.PROMOTED))

    rotated = next(tmp_path.glob("audit.*.jsonl"))
    raw = rotated.read_text(encoding="utf-8")
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
    # Simulate a half-written line on the rotator's active file.
    rotated = next(tmp_path.glob("audit.*.jsonl"))
    with rotated.open("a", encoding="utf-8") as fh:
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

    rotated = next(tmp_path.glob("audit.*.jsonl"))
    raw = rotated.read_text(encoding="utf-8")
    payload = json.loads(raw.strip())
    assert payload["event_type"] == "gate_passed"


# =============================================================================
# Phase 10.4 — monthly rotation + retention
# =============================================================================


def test_rotator_integration_merges_across_months(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit events split into per-month files and merge on read."""
    log = AuditLog(path=tmp_path / "audit.jsonl")

    _set_clock(monkeypatch, datetime(2026, 3, 15, 9, 0, 0))
    log.append(make_event(candidate_id="march-cand"))

    _set_clock(monkeypatch, datetime(2026, 4, 1, 0, 0, 1))
    log.append(make_event(candidate_id="april-cand"))

    rotated = sorted(tmp_path.glob("audit.*.jsonl"))
    assert [p.name for p in rotated] == [
        "audit.2026-03.jsonl",
        "audit.2026-04.jsonl",
    ]

    history = log.read_all()
    assert [e.candidate_id for e in history] == ["march-cand", "april-cand"]


def test_default_timestamp_is_set(tmp_path: Path) -> None:
    log = AuditLog(path=tmp_path / "audit.jsonl")
    before = datetime.now(tz=timezone.utc)
    log.append(make_event())
    history = log.read_all()
    # Phase 21.2: AuditEvent.timestamp is UTC-aware via ``now_utc``;
    # after a JSONL round-trip Pydantic returns its own zero-offset
    # tzinfo (not the ``timezone.utc`` singleton), so assert equality
    # via ``utcoffset`` rather than identity.
    ts = history[0].timestamp
    assert ts.tzinfo is not None
    assert ts.utcoffset() == timezone.utc.utcoffset(None)
    assert before <= ts

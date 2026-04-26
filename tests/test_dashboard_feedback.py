"""Tests for the Feedback Loop status page (Phase 7.4)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.dashboard.pages.feedback import (
    build_audit_timeline_dataframe,
    build_candidates_dataframe,
    build_summary_metrics,
    load_candidate_records,
)
from src.feedback.audit import AuditEvent, AuditEventType, AuditLog
from src.feedback.loop import CandidateRecord, LoopStatus

# =============================================================================
# Helpers
# =============================================================================


def make_record(
    *,
    candidate_id: str = "cand-12345678",
    kind: str = "improvement",
    technique_name: str = "tech_a",
    technique_version: str = "1.0.0",
    source_path: str = "strategies/experimental/tech_a.md",
    status: LoopStatus = LoopStatus.AWAITING_APPROVAL,
    backtest_run_id: str | None = "run-1",
    robustness_passed: bool | None = True,
    robustness_summary: str | None = "All gates passed.",
    failed_gates: list[str] | None = None,
    decision_reason: str = "",
    parent_technique: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> CandidateRecord:
    return CandidateRecord(
        candidate_id=candidate_id,
        kind=kind,  # type: ignore[arg-type]
        parent_technique=parent_technique,
        technique_name=technique_name,
        technique_version=technique_version,
        source_path=Path(source_path),
        status=status,
        backtest_run_id=backtest_run_id,
        robustness_passed=robustness_passed,
        robustness_summary=robustness_summary,
        failed_gates=failed_gates or [],
        decision_reason=decision_reason,
        created_at=created_at or datetime(2026, 1, 1, 0, 0, 0),
        updated_at=updated_at or datetime(2026, 1, 2, 0, 0, 0),
    )


def write_record(state_dir: Path, record: CandidateRecord) -> Path:
    """Persist a CandidateRecord to a state dir for loader tests."""
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / f"{record.candidate_id}.json"
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return path


# =============================================================================
# load_candidate_records
# =============================================================================


def test_load_candidate_records_empty_dir(tmp_path: Path) -> None:
    """Missing dir → empty list, not an exception."""
    records = load_candidate_records(tmp_path / "never_created")

    assert records == []


def test_load_candidate_records_returns_all(tmp_path: Path) -> None:
    write_record(tmp_path, make_record(candidate_id="a"))
    write_record(tmp_path, make_record(candidate_id="b"))

    records = load_candidate_records(tmp_path)

    assert {r.candidate_id for r in records} == {"a", "b"}


def test_load_candidate_records_sorts_newest_first(tmp_path: Path) -> None:
    write_record(
        tmp_path,
        make_record(candidate_id="old", updated_at=datetime(2026, 1, 1)),
    )
    write_record(
        tmp_path,
        make_record(candidate_id="new", updated_at=datetime(2026, 4, 1)),
    )

    records = load_candidate_records(tmp_path)

    assert [r.candidate_id for r in records] == ["new", "old"]


def test_load_candidate_records_skips_malformed(tmp_path: Path) -> None:
    write_record(tmp_path, make_record(candidate_id="good"))
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    records = load_candidate_records(tmp_path)

    assert [r.candidate_id for r in records] == ["good"]


# =============================================================================
# build_candidates_dataframe
# =============================================================================


def test_candidates_dataframe_empty_returns_columns_only() -> None:
    df = build_candidates_dataframe([])

    assert df.empty
    assert "Candidate ID" in df.columns
    assert "Status" in df.columns
    assert "Robustness" in df.columns


def test_candidates_dataframe_one_row_per_record() -> None:
    records = [
        make_record(candidate_id="cand-aaaaaa11"),
        make_record(candidate_id="cand-bbbbbb22"),
    ]

    df = build_candidates_dataframe(records)

    assert len(df) == 2
    # Truncated id (first 8 chars).
    assert set(df["Candidate ID"]) == {"cand-aaa", "cand-bbb"}


def test_candidates_dataframe_robustness_label() -> None:
    pass_rec = make_record(candidate_id="pass-1", robustness_passed=True)
    fail_rec = make_record(candidate_id="fail-1", robustness_passed=False)
    none_rec = make_record(candidate_id="none-1", robustness_passed=None)

    df = build_candidates_dataframe([pass_rec, fail_rec, none_rec])

    by_id = {row["Candidate ID"]: row["Robustness"] for _, row in df.iterrows()}
    assert by_id["pass-1"[:8]] == "PASS"
    assert by_id["fail-1"[:8]] == "FAIL"
    assert by_id["none-1"[:8]] == "—"


# =============================================================================
# build_summary_metrics
# =============================================================================


def test_summary_metrics_empty() -> None:
    metrics = build_summary_metrics([])

    assert metrics["total"] == 0
    assert metrics[LoopStatus.AWAITING_APPROVAL.value] == 0
    assert metrics[LoopStatus.PROMOTED.value] == 0
    assert metrics[LoopStatus.DISCARDED.value] == 0


def test_summary_metrics_counts_by_status() -> None:
    records = [
        make_record(candidate_id="a", status=LoopStatus.AWAITING_APPROVAL),
        make_record(candidate_id="b", status=LoopStatus.AWAITING_APPROVAL),
        make_record(candidate_id="c", status=LoopStatus.PROMOTED),
        make_record(candidate_id="d", status=LoopStatus.DISCARDED),
        make_record(candidate_id="e", status=LoopStatus.ERRORED),
    ]

    metrics = build_summary_metrics(records)

    assert metrics["total"] == 5
    assert metrics[LoopStatus.AWAITING_APPROVAL.value] == 2
    assert metrics[LoopStatus.PROMOTED.value] == 1
    assert metrics[LoopStatus.DISCARDED.value] == 1
    assert metrics[LoopStatus.ERRORED.value] == 1


# =============================================================================
# build_audit_timeline_dataframe
# =============================================================================


def test_audit_timeline_empty_returns_columns_only() -> None:
    df = build_audit_timeline_dataframe([])

    assert df.empty
    assert list(df.columns) == ["Timestamp", "Event", "Actor", "Details"]


def test_audit_timeline_sorts_oldest_first() -> None:
    earlier = AuditEvent(
        timestamp=datetime(2026, 1, 1),
        event_type=AuditEventType.GENERATED,
        candidate_id="a",
        technique_name="t",
        technique_version="1",
    )
    later = AuditEvent(
        timestamp=datetime(2026, 1, 5),
        event_type=AuditEventType.PROMOTED,
        candidate_id="a",
        technique_name="t",
        technique_version="1",
    )

    df = build_audit_timeline_dataframe([later, earlier])

    assert list(df["Event"]) == [
        AuditEventType.GENERATED.value,
        AuditEventType.PROMOTED.value,
    ]


def test_audit_timeline_serializes_details() -> None:
    event = AuditEvent(
        event_type=AuditEventType.GATE_FAILED,
        candidate_id="a",
        technique_name="t",
        technique_version="1",
        details={"failed_gates": ["oos", "walk_forward"]},
    )

    df = build_audit_timeline_dataframe([event])

    details_str = df.iloc[0]["Details"]
    assert "failed_gates" in details_str
    assert "oos" in details_str


# =============================================================================
# AppTest smoke
# =============================================================================


def test_feedback_page_renders_empty_state(tmp_path: Path) -> None:
    """Page must not crash when no candidates are recorded."""
    from streamlit.testing.v1 import AppTest

    script = f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})
from pathlib import Path
from src.dashboard.pages.feedback import render
from src.feedback.audit import AuditLog

render(
    state_dir=Path({str(tmp_path / "state")!r}),
    audit_log=AuditLog(path=Path({str(tmp_path / "audit.jsonl")!r})),
)
"""
    at = AppTest.from_string(script).run(timeout=10)

    assert not at.exception, [str(e) for e in at.exception]
    info_text = " ".join(i.value for i in at.info)
    assert "No candidates recorded" in info_text


def test_feedback_page_renders_populated(tmp_path: Path) -> None:
    """End-to-end: a saved candidate + audit event renders detail + timeline."""
    from streamlit.testing.v1 import AppTest

    state_dir = tmp_path / "state"
    audit_path = tmp_path / "audit.jsonl"

    record = make_record(
        candidate_id="abc12345-promoted",
        status=LoopStatus.PROMOTED,
        robustness_passed=True,
        robustness_summary="OOS PASS, walk-forward PASS, regime PASS",
    )
    write_record(state_dir, record)

    audit = AuditLog(path=audit_path)
    audit.append(
        AuditEvent(
            event_type=AuditEventType.GENERATED,
            candidate_id=record.candidate_id,
            technique_name=record.technique_name,
            technique_version=record.technique_version,
        )
    )
    audit.append(
        AuditEvent(
            event_type=AuditEventType.PROMOTED,
            candidate_id=record.candidate_id,
            technique_name=record.technique_name,
            technique_version=record.technique_version,
            actor="alice",
        )
    )

    script = f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})
from pathlib import Path
from src.dashboard.pages.feedback import render
from src.feedback.audit import AuditLog

render(
    state_dir=Path({str(state_dir)!r}),
    audit_log=AuditLog(path=Path({str(audit_path)!r})),
)
"""
    at = AppTest.from_string(script).run(timeout=15)

    assert not at.exception, [str(e) for e in at.exception]
    titles = [t.value for t in at.title]
    assert any("Feedback Loop" in t for t in titles), titles


# =============================================================================
# JSON-on-disk shape sanity (no leftover state from a prior bug)
# =============================================================================


def test_loaded_record_round_trips_path(tmp_path: Path) -> None:
    """Path objects must round-trip via JSON without becoming odd strings."""
    rec = make_record(source_path="strategies/experimental/foo.md")
    path = write_record(tmp_path, rec)
    raw = json.loads(path.read_text(encoding="utf-8"))

    # Path is serialized as a string by pydantic.
    assert raw["source_path"] == "strategies/experimental/foo.md"

    loaded = load_candidate_records(tmp_path)
    assert loaded[0].source_path == Path("strategies/experimental/foo.md")

"""Feedback Loop status page (Phase 7.4).

Surfaces the state of the technique-evolution pipeline:

* Summary cards — totals by ``LoopStatus`` (awaiting approval, promoted,
  discarded, etc.).
* Candidates table — every persisted ``CandidateRecord`` snapshot under
  the state directory, sorted newest first.
* Per-candidate detail — full record fields plus an audit-log timeline
  filtered to the selected candidate.

The page is read-only. Approving / rejecting a candidate stays a
``FeedbackLoop`` API concern (CON-003 — user approval is enforced
there, not in the dashboard) so promotion can't accidentally happen
mid-render.

Related Requirements:
- FR-030: Technique Generation Status
- FR-026: Automated Feedback Loop (consumed)
- FR-027: Technique Adoption (consumed)
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import Enum
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import get_settings
from src.dashboard.query_params import query_param_first as _query_param_first
from src.feedback.audit import DEFAULT_AUDIT_PATH, AuditEvent, AuditLog
from src.feedback.loop import (
    CandidateRecord,
    FeedbackLoop,
    LoopStatus,
)
from src.feedback.promotion_lab import PromotionObservation
from src.logger import get_logger

logger = get_logger("crypto_master.dashboard.feedback")


class CandidateDecisionAction(str, Enum):
    """Operator action available from the promotion lab UI."""

    PROMOTE = "promote"
    REJECT = "reject"


def default_candidate_state_dir() -> Path:
    """Return the runtime feedback candidate-state directory."""
    return get_settings().data_dir / "feedback" / "state"


def default_promotion_state_dir() -> Path:
    """Return the runtime promotion-lab observation directory."""
    return get_settings().data_dir / "feedback" / "promotion_lab"


# =============================================================================
# Pure helpers (importable + testable without Streamlit runtime)
# =============================================================================


def load_candidate_records(state_dir: Path) -> list[CandidateRecord]:
    """Load every persisted ``CandidateRecord`` snapshot.

    Same shape as ``FeedbackLoop.list_pending`` but without the
    pending-only filter and without requiring a fully-constructed
    loop. Malformed files are skipped with a warning so one bad file
    doesn't blank the dashboard.

    Args:
        state_dir: Directory holding ``<candidate_id>.json`` files.

    Returns:
        Records sorted by ``updated_at`` descending. Empty list if the
        directory is missing.
    """
    if not state_dir.exists():
        return []

    records: list[CandidateRecord] = []
    for path in sorted(state_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append(CandidateRecord(**payload))
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Skipping unreadable candidate file {path}: {e}")
    records.sort(key=lambda r: r.updated_at, reverse=True)
    return records


def load_promotion_observations(state_dir: Path) -> dict[str, PromotionObservation]:
    """Load promotion-lab observations keyed by candidate ID."""
    if not state_dir.exists():
        return {}

    observations: dict[str, PromotionObservation] = {}
    for path in sorted(state_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            observation = PromotionObservation(**payload)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Skipping unreadable promotion observation {path}: {e}")
            continue
        observations[observation.candidate_id] = observation
    return observations


def build_candidates_dataframe(
    records: list[CandidateRecord],
    observations: Mapping[str, PromotionObservation] | None = None,
) -> pd.DataFrame:
    """Build the all-candidates table.

    Records are already sorted by the loader; we keep that order and
    drop only the noisy fields (full source paths, long summaries) to
    a per-candidate detail view downstream.

    Returns:
        DataFrame with one row per candidate. Empty DataFrame keeps
        the declared columns so the empty-state render is clean.
    """
    columns = [
        "Candidate ID",
        "Kind",
        "Technique",
        "Version",
        "Status",
        "Robustness",
        "Promotion",
        "Score",
        "Updated",
    ]
    if not records:
        return pd.DataFrame(columns=columns)

    observations = observations or {}
    rows = []
    for r in records:
        if r.robustness_passed is None:
            robustness = "—"
        else:
            robustness = "PASS" if r.robustness_passed else "FAIL"
        observation = observations.get(r.candidate_id)
        rows.append(
            {
                "Candidate ID": r.candidate_id[:8],
                "Kind": r.kind,
                "Technique": r.technique_name,
                "Version": r.technique_version,
                "Status": r.status,
                "Robustness": robustness,
                "Promotion": observation.decision.value if observation else "—",
                "Score": observation.score if observation else "—",
                "Updated": r.updated_at,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def build_summary_metrics(records: list[CandidateRecord]) -> dict[str, int]:
    """Count candidates per ``LoopStatus``.

    Returns:
        Dict with keys ``total`` plus one entry per ``LoopStatus``
        value. Counts are zero when no candidates match — the
        dashboard's metric cards still render zero (more honest than
        hiding the metric).
    """
    counts: dict[str, int] = {"total": len(records)}
    for status in LoopStatus:
        counts[status.value] = 0
    for r in records:
        # ``use_enum_values=True`` means r.status is the string value.
        status_value = r.status if isinstance(r.status, str) else r.status.value
        counts[status_value] = counts.get(status_value, 0) + 1
    return counts


def build_audit_timeline_dataframe(events: list[AuditEvent]) -> pd.DataFrame:
    """Build the audit-log timeline table for one candidate.

    Args:
        events: ``AuditEvent`` list (typically pre-filtered to a
            single candidate via ``AuditLog.filter``).

    Returns:
        DataFrame with one row per event sorted ascending by
        timestamp (oldest first → reads top-to-bottom as a story).
    """
    columns = ["Timestamp", "Event", "Actor", "Details"]
    if not events:
        return pd.DataFrame(columns=columns)

    rows = []
    for e in sorted(events, key=lambda ev: ev.timestamp):
        details_str = (
            json.dumps(e.details, default=str, sort_keys=True) if e.details else ""
        )
        rows.append(
            {
                "Timestamp": e.timestamp,
                "Event": (
                    e.event_type
                    if isinstance(e.event_type, str)
                    else e.event_type.value
                ),
                "Actor": e.actor,
                "Details": details_str,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def apply_candidate_decision(
    feedback_loop: FeedbackLoop,
    *,
    candidate_id: str,
    action: CandidateDecisionAction,
    approver: str,
    reason: str = "",
) -> CandidateRecord:
    """Apply an explicit operator decision through ``FeedbackLoop`` APIs."""
    approver = approver.strip()
    if not approver:
        raise ValueError("approver is required")

    if action == CandidateDecisionAction.PROMOTE:
        return feedback_loop.approve(candidate_id, approver=approver)

    reason = reason.strip()
    if not reason:
        raise ValueError("rejection reason is required")
    return feedback_loop.reject(candidate_id, approver=approver, reason=reason)


# =============================================================================
# Streamlit render
# =============================================================================


def render(
    state_dir: Path | None = None,
    promotion_state_dir: Path | None = None,
    audit_log: AuditLog | None = None,
    feedback_loop: FeedbackLoop | None = None,
) -> None:
    """Render the Feedback Loop page.

    Args:
        state_dir: Override the candidate-state directory. Defaults to
            ``<DATA_DIR>/feedback/state``.
        promotion_state_dir: Override the promotion observation directory.
            Defaults to ``<DATA_DIR>/feedback/promotion_lab``.
        audit_log: Override the audit log. Defaults to
            ``AuditLog()`` reading from ``data/audit/feedback.jsonl``.
        feedback_loop: Optional operational loop. When supplied, awaiting
            candidates get explicit promote/reject actions.
    """
    st.title("🔁 Feedback Loop")
    st.caption(
        "Experimental candidates and the audit trail of the "
        "improvement → backtest → robustness gate → decision pipeline."
    )

    state_dir = state_dir or default_candidate_state_dir()
    promotion_state_dir = promotion_state_dir or default_promotion_state_dir()
    audit = audit_log or AuditLog()

    records = load_candidate_records(state_dir)
    observations = load_promotion_observations(promotion_state_dir)
    metrics = build_summary_metrics(records)

    # ---- Summary cards ----
    st.subheader("Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total", metrics["total"])
    c2.metric("Awaiting Approval", metrics[LoopStatus.AWAITING_APPROVAL.value])
    c3.metric("Promoted", metrics[LoopStatus.PROMOTED.value])
    c4.metric("Discarded", metrics[LoopStatus.DISCARDED.value])
    c5.metric("Errored", metrics[LoopStatus.ERRORED.value])

    if not records:
        st.info(
            f"No candidates recorded yet. State directory: `{state_dir}`. "
            "Run `FeedbackLoop.improve_existing` / `propose_new` / "
            "`from_user_idea` to start populating it."
        )
        return

    # ---- All candidates table ----
    st.subheader("Candidates")
    candidates_df = build_candidates_dataframe(records, observations)
    st.dataframe(candidates_df, hide_index=True, use_container_width=True)

    # ---- Per-candidate detail ----
    st.subheader("Candidate Detail")
    options = [r.candidate_id for r in records]
    selected_index = _selected_candidate_index(records, options)
    selected_id = st.selectbox(
        "Candidate",
        options=options,
        index=selected_index,
        format_func=lambda cid: (
            f"{cid[:8]}  ({_record_for(records, cid).technique_name} "
            f"v{_record_for(records, cid).technique_version})"
        ),
    )
    if not selected_id:
        return

    record = _record_for(records, selected_id)
    _render_record_detail(record, observations.get(selected_id))
    if (
        feedback_loop is not None
        and record.status == LoopStatus.AWAITING_APPROVAL.value
    ):
        _render_operator_actions(feedback_loop, record)

    # ---- Audit timeline for this candidate ----
    st.markdown("**Audit timeline**")
    events = audit.filter(candidate_id=selected_id)
    timeline_df = build_audit_timeline_dataframe(events)
    if timeline_df.empty:
        st.info("No audit events recorded for this candidate.")
    else:
        st.dataframe(timeline_df, hide_index=True, use_container_width=True)


def _record_for(records: list[CandidateRecord], candidate_id: str) -> CandidateRecord:
    """Internal: find the record by id (caller guarantees existence)."""
    for r in records:
        if r.candidate_id == candidate_id:
            return r
    raise KeyError(f"Candidate {candidate_id} not in records")


def _selected_candidate_index(
    records: list[CandidateRecord],
    options: list[str],
) -> int:
    """Pick the candidate requested by Home drill-through query params."""
    requested_id = _query_param_first("candidate_id")
    if requested_id in options:
        return options.index(requested_id)

    requested_status = _query_param_first("status")
    if requested_status:
        for index, record in enumerate(records):
            if str(record.status) == requested_status:
                return index
    return 0


def _render_record_detail(
    record: CandidateRecord,
    observation: PromotionObservation | None = None,
) -> None:
    """Render the per-candidate detail block."""
    col1, col2 = st.columns(2)
    col1.markdown(f"**Candidate ID:** `{record.candidate_id}`")
    col1.markdown(f"**Kind:** {record.kind}")
    col1.markdown(f"**Technique:** {record.technique_name} v{record.technique_version}")
    col1.markdown(f"**Status:** {record.status}")
    col2.markdown(f"**Source:** `{record.source_path}`")
    col2.markdown(f"**Backtest run:** {record.backtest_run_id or '—'}")
    if record.parent_technique:
        col2.markdown(f"**Parent technique:** {record.parent_technique}")
    col2.markdown(f"**Updated:** {record.updated_at.isoformat(timespec='seconds')}")

    if record.robustness_summary:
        st.markdown("**Robustness summary**")
        st.code(record.robustness_summary, language="text")
    if record.failed_gates:
        st.markdown(f"**Failed gates:** {', '.join(record.failed_gates)}")
    if record.decision_reason:
        st.markdown(f"**Decision reason:** {record.decision_reason}")
    if observation:
        st.markdown("**Promotion lab recommendation**")
        st.markdown(
            f"`{observation.decision.value}` with score "
            f"`{observation.score}` after "
            f"`{observation.evaluations_count}` evaluation(s)."
        )
        if observation.factors:
            st.markdown(f"**Promotion factors:** {'; '.join(observation.factors)}")
        if observation.blocking_reasons:
            st.markdown(
                f"**Promotion blockers:** {'; '.join(observation.blocking_reasons)}"
            )


def _render_operator_actions(
    feedback_loop: FeedbackLoop,
    record: CandidateRecord,
) -> None:
    """Render explicit promotion/rejection controls for awaiting candidates."""
    st.markdown("**Operator actions**")
    approver = st.text_input(
        "Approver",
        value="dashboard",
        key=f"promotion-approver-{record.candidate_id}",
    )
    reject_reason = st.text_input(
        "Reject reason",
        value="Rejected from promotion lab",
        key=f"promotion-reject-reason-{record.candidate_id}",
    )
    promote_col, reject_col = st.columns(2)
    if promote_col.button("Promote", key=f"promote-{record.candidate_id}"):
        updated = apply_candidate_decision(
            feedback_loop,
            candidate_id=record.candidate_id,
            action=CandidateDecisionAction.PROMOTE,
            approver=approver,
        )
        st.success(f"Promoted candidate {updated.candidate_id}.")
        st.rerun()
    if reject_col.button("Reject", key=f"reject-{record.candidate_id}"):
        updated = apply_candidate_decision(
            feedback_loop,
            candidate_id=record.candidate_id,
            action=CandidateDecisionAction.REJECT,
            approver=approver,
            reason=reject_reason,
        )
        st.success(f"Rejected candidate {updated.candidate_id}.")
        st.rerun()


__all__ = [
    "CandidateDecisionAction",
    "DEFAULT_AUDIT_PATH",
    "apply_candidate_decision",
    "build_audit_timeline_dataframe",
    "build_candidates_dataframe",
    "build_summary_metrics",
    "default_candidate_state_dir",
    "default_promotion_state_dir",
    "load_promotion_observations",
    "load_candidate_records",
    "render",
]

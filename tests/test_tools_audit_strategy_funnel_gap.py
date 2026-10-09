"""Tests for ``src.tools.audit_strategy_funnel_gap`` (DEBT-074)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.proposal.engine import Proposal, ProposalScore
from src.proposal.interaction import (
    ProposalDecision,
    ProposalFinalState,
    ProposalHistory,
    ProposalRecord,
)
from src.tools.audit_strategy_funnel_gap import audit_strategy_funnel_gap, main


def _write_fail_closed(
    data_dir: Path,
    *,
    sub_account_id: str,
    technique_name: str,
    emitted: int,
    fail_closed: int,
    **stages: int,
) -> None:
    path = (
        data_dir / "performance" / sub_account_id / technique_name / "fail_closed.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "sub_account_id": sub_account_id,
                "technique_name": technique_name,
                "technique_version": "1.0.0",
                "proposals_emitted": emitted,
                "proposals_fail_closed": fail_closed,
                **stages,
                "last_updated": "2026-06-30T00:00:00+00:00",
            }
        )
    )


def _proposal(
    *,
    sub_account_id: str,
    technique_name: str,
) -> Proposal:
    return Proposal(
        symbol="BTC/USDT",
        timeframe="1h",
        technique_name=technique_name,
        technique_version="1.0.0",
        sub_account_id=sub_account_id,
        signal="long",
        entry_price=Decimal("50000"),
        stop_loss=Decimal("49000"),
        take_profit=Decimal("52000"),
        quantity=Decimal("0.1"),
        leverage=1,
        risk_reward_ratio=2.0,
        score=ProposalScore(
            confidence=0.8,
            win_rate=0.6,
            risk_reward=2.0,
            expected_value=1.0,
            sample_size=10,
            sample_factor=1.0,
            edge_factor=1.1,
            composite=0.88,
        ),
    )


def test_audit_classifies_vcp_shaped_pre_funnel_gap(tmp_path: Path) -> None:
    """Emitted with no fail-closed/proposal/trade is a pre-funnel gap."""
    _write_fail_closed(
        tmp_path,
        sub_account_id="vcp_lab",
        technique_name="vcp_breakout",
        emitted=6428,
        fail_closed=0,
    )

    audit = audit_strategy_funnel_gap(
        tmp_path,
        "vcp_breakout",
        sub_account="vcp_lab",
    )

    assert audit.proposals_emitted == 6428
    assert audit.proposals_fail_closed == 0
    assert audit.proposal_records == 0
    assert audit.opened_or_linked == 0
    assert audit.conclusion == "pre_funnel_no_signal_or_selection_or_history_gap"
    assert "candidate-level deselection" in audit.suggested_follow_up


def test_audit_counts_opened_proposal_records(tmp_path: Path) -> None:
    """A selected proposal with a trade link is classified as opened."""
    _write_fail_closed(
        tmp_path,
        sub_account_id="vcp_lab",
        technique_name="vcp_breakout",
        emitted=3,
        fail_closed=0,
    )
    history = ProposalHistory(data_dir=tmp_path / "proposals")
    record = ProposalRecord(
        proposal=_proposal(
            sub_account_id="vcp_lab",
            technique_name="vcp_breakout",
        ),
        decision=ProposalDecision.ACCEPTED,
        final_state=ProposalFinalState.TRADE_OPENED,
        trade_id="trade-1",
    )
    history.save(record)

    audit = audit_strategy_funnel_gap(
        tmp_path,
        "vcp_breakout",
        sub_account="vcp_lab",
    )

    assert audit.proposal_records == 1
    assert audit.opened_or_linked == 1
    assert audit.linked_trades == 1
    assert audit.conclusion == "opened"


def test_audit_cli_returns_success(tmp_path: Path, monkeypatch) -> None:
    """CLI wrapper is read-only and exits successfully."""
    _write_fail_closed(
        tmp_path,
        sub_account_id="vcp_lab",
        technique_name="vcp_breakout",
        emitted=1,
        fail_closed=0,
    )
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    assert main(["vcp_breakout", "--sub-account", "vcp_lab"]) == 0


@pytest.mark.parametrize(
    "observed,neutral,non_neutral,built,selected,failures,expected",
    [
        (3, 3, 0, 0, 0, 0, "neutral_only"),
        (1, 1, 0, 0, 0, 0, "pre_funnel_no_signal_or_selection_or_history_gap"),
        (3, 2, 1, 1, 0, 0, "pre_funnel_no_signal_or_selection_or_history_gap"),
        (3, 0, 3, 0, 0, 3, "pre_funnel_fail_closed"),
        (3, 0, 0, 0, 0, 3, "pre_funnel_fail_closed"),
        (3, 3, 0, 0, 1, 0, "pre_funnel_no_signal_or_selection_or_history_gap"),
    ],
)
def test_audit_signal_coverage_never_guesses_missing_history(
    tmp_path, observed, neutral, non_neutral, built, selected, failures, expected
):
    _write_fail_closed(
        tmp_path,
        sub_account_id="lab",
        technique_name="test",
        emitted=3,
        fail_closed=failures,
        analysis_attempts_observed=observed,
        neutral_results=neutral,
        non_neutral_results=non_neutral,
        candidates_built=built,
        candidates_selected=selected,
    )
    path = tmp_path / "performance" / "lab" / "test" / "fail_closed.json"
    before = path.read_bytes()
    audit = audit_strategy_funnel_gap(tmp_path, "test", sub_account="lab")
    assert audit.conclusion == expected
    assert audit.neutral_results == neutral
    assert audit.candidates_selected == selected
    assert path.read_bytes() == before


def test_legacy_gap_explicitly_allows_no_signal(tmp_path):
    _write_fail_closed(
        tmp_path,
        sub_account_id="lab",
        technique_name="test",
        emitted=25383,
        fail_closed=0,
    )
    audit = audit_strategy_funnel_gap(tmp_path, "test", sub_account="lab")
    assert "no_signal" in audit.conclusion
    assert "Legacy or incomplete coverage" in audit.suggested_follow_up
    assert audit.analysis_attempts_observed == 0


def test_partial_stage_write_is_not_reported_as_no_activity(tmp_path):
    _write_fail_closed(
        tmp_path,
        sub_account_id="lab",
        technique_name="test",
        emitted=0,
        fail_closed=0,
        neutral_results=1,
    )
    assert (
        audit_strategy_funnel_gap(tmp_path, "test", sub_account="lab").conclusion
        == "mixed"
    )

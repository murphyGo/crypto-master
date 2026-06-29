"""Tests for ``src.tools.audit_strategy_funnel_gap`` (DEBT-074)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

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
    assert audit.conclusion == "pre_funnel_candidate_selection_or_history_gap"
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

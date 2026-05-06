"""Tests for proposal replay input models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from src.models import OHLCV
from src.proposal.engine import Proposal, ProposalScore
from src.proposal.interaction import ProposalDecision, ProposalHistory, ProposalRecord
from src.proposal.replay import (
    ProposalReplayInput,
    ProposalReplayInputError,
)


def make_score() -> ProposalScore:
    return ProposalScore(
        confidence=0.8,
        win_rate=0.6,
        sample_size=25,
        expected_value=2.0,
        sample_factor=1.0,
        edge_factor=2.0,
        composite=1.6,
    )


def make_proposal(
    proposal_id: str,
    created_at: datetime,
    *,
    sub_account_id: str = "default",
) -> Proposal:
    return Proposal(
        proposal_id=proposal_id,
        created_at=created_at,
        symbol="BTC/USDT",
        timeframe="1h",
        signal="long",
        technique_name="tech_a",
        technique_version="1.0.0",
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        quantity=Decimal("0.1"),
        leverage=1,
        risk_reward_ratio=2.0,
        score=make_score(),
        reasoning="Replay fixture.",
        sub_account_id=sub_account_id,
    )


def make_record(
    proposal_id: str,
    created_at: datetime,
    *,
    decision: ProposalDecision = ProposalDecision.ACCEPTED,
) -> ProposalRecord:
    return ProposalRecord(
        proposal=make_proposal(proposal_id, created_at),
        sub_account_id="default",
        decision=decision,
        decision_at=created_at + timedelta(minutes=1),
        actor="test",
    )


def candle(timestamp: datetime, close: str = "100") -> OHLCV:
    price = Decimal(close)
    return OHLCV(
        timestamp=timestamp,
        open=price,
        high=price + Decimal("2"),
        low=price - Decimal("2"),
        close=price,
        volume=Decimal("10"),
    )


def test_replay_input_pairs_records_with_candle_windows_in_time_order() -> None:
    base = datetime(2026, 5, 7, tzinfo=timezone.utc)
    later = make_record("p2", base + timedelta(hours=2))
    earlier = make_record("p1", base + timedelta(hours=1))

    replay_input = ProposalReplayInput.from_records(
        [later, earlier],
        {
            "p1": [candle(base + timedelta(hours=1))],
            "p2": [candle(base + timedelta(hours=2))],
        },
    )

    assert [case.proposal_id for case in replay_input.cases] == ["p1", "p2"]
    assert replay_input.case_for("p2").record == later


def test_replay_input_requires_candle_window_for_each_proposal() -> None:
    base = datetime(2026, 5, 7, tzinfo=timezone.utc)
    record = make_record("missing", base)

    with pytest.raises(ProposalReplayInputError, match="missing candle window"):
        ProposalReplayInput.from_records([record], {})


def test_replay_input_rejects_unsorted_candle_windows() -> None:
    base = datetime(2026, 5, 7, tzinfo=timezone.utc)
    record = make_record("p1", base)

    with pytest.raises(ProposalReplayInputError, match="sorted"):
        ProposalReplayInput.from_records(
            [record],
            {"p1": [candle(base + timedelta(hours=1)), candle(base)]},
        )


def test_replay_input_requires_window_at_or_after_proposal_time() -> None:
    base = datetime(2026, 5, 7, tzinfo=timezone.utc)
    record = make_record("p1", base)

    with pytest.raises(ProposalReplayInputError, match="at or after proposal time"):
        ProposalReplayInput.from_records(
            [record],
            {"p1": [candle(base - timedelta(hours=2))]},
        )


def test_replay_input_can_load_filtered_history(tmp_path: Path) -> None:
    base = datetime(2026, 5, 7, tzinfo=timezone.utc)
    accepted = make_record("accepted", base, decision=ProposalDecision.ACCEPTED)
    rejected = make_record(
        "rejected",
        base + timedelta(hours=1),
        decision=ProposalDecision.REJECTED,
    )
    history = ProposalHistory(data_dir=tmp_path)
    history.save(accepted)
    history.save(rejected)

    replay_input = ProposalReplayInput.from_history(
        history,
        {
            "accepted": [candle(base)],
            "rejected": [candle(base + timedelta(hours=1))],
        },
        decision=ProposalDecision.ACCEPTED,
    )

    assert [case.proposal_id for case in replay_input.cases] == ["accepted"]

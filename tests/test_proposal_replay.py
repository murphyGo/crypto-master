"""Tests for proposal replay input models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest

from src.models import OHLCV
from src.proposal.engine import Proposal, ProposalScore
from src.proposal.interaction import ProposalDecision, ProposalHistory, ProposalRecord
from src.proposal.replay import (
    ProposalReplayExitAssumption,
    ProposalReplayInput,
    ProposalReplayInputError,
    ProposalReplayScenario,
    compare_replay_scenarios,
    render_replay_report,
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
    signal: Literal["long", "short"] = "long",
    entry_price: str = "100",
    stop_loss: str = "95",
    take_profit: str = "110",
    quantity: str = "0.1",
) -> Proposal:
    return Proposal(
        proposal_id=proposal_id,
        created_at=created_at,
        symbol="BTC/USDT",
        timeframe="1h",
        signal=signal,
        technique_name="tech_a",
        technique_version="1.0.0",
        entry_price=Decimal(entry_price),
        stop_loss=Decimal(stop_loss),
        take_profit=Decimal(take_profit),
        quantity=Decimal(quantity),
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
    signal: Literal["long", "short"] = "long",
    entry_price: str = "100",
    stop_loss: str = "95",
    take_profit: str = "110",
) -> ProposalRecord:
    return ProposalRecord(
        proposal=make_proposal(
            proposal_id,
            created_at,
            signal=signal,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        ),
        sub_account_id="default",
        decision=decision,
        decision_at=created_at + timedelta(minutes=1),
        actor="test",
    )


def candle(
    timestamp: datetime,
    close: str = "100",
    *,
    high: str | None = None,
    low: str | None = None,
) -> OHLCV:
    price = Decimal(close)
    return OHLCV(
        timestamp=timestamp,
        open=price,
        high=Decimal(high) if high is not None else price + Decimal("2"),
        low=Decimal(low) if low is not None else price - Decimal("2"),
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


def test_compare_replay_scenarios_filters_below_threshold() -> None:
    base = datetime(2026, 5, 7, tzinfo=timezone.utc)
    record = make_record("p1", base)
    replay_input = ProposalReplayInput.from_records(
        [record],
        {"p1": [candle(base, high="112", low="99")]},
    )

    result = compare_replay_scenarios(
        replay_input,
        [ProposalReplayScenario(min_score=2.0)],
    )[0]

    assert result.approved_count == 0
    assert result.outcomes[0].approved is False
    assert result.outcomes[0].exit_reason == "filtered"


def test_compare_replay_scenarios_resolves_same_candle_stop_first() -> None:
    base = datetime(2026, 5, 7, tzinfo=timezone.utc)
    record = make_record("p1", base)
    replay_input = ProposalReplayInput.from_records(
        [record],
        {"p1": [candle(base, high="112", low="94")]},
    )

    result = compare_replay_scenarios(
        replay_input,
        [
            ProposalReplayScenario(
                exit_assumption=ProposalReplayExitAssumption.STOP_FIRST,
            )
        ],
    )[0]

    outcome = result.outcomes[0]
    assert outcome.exit_reason == "stop_loss"
    assert outcome.exit_price == Decimal("95")
    assert outcome.gross_pnl == Decimal("-0.5")
    assert outcome.pnl_percent == Decimal("-5.00")


def test_compare_replay_scenarios_resolves_same_candle_take_profit_first() -> None:
    base = datetime(2026, 5, 7, tzinfo=timezone.utc)
    record = make_record("p1", base)
    replay_input = ProposalReplayInput.from_records(
        [record],
        {"p1": [candle(base, high="112", low="94")]},
    )

    result = compare_replay_scenarios(
        replay_input,
        [
            ProposalReplayScenario(
                exit_assumption=ProposalReplayExitAssumption.TAKE_PROFIT_FIRST,
            )
        ],
    )[0]

    outcome = result.outcomes[0]
    assert outcome.exit_reason == "take_profit"
    assert outcome.exit_price == Decimal("110")
    assert outcome.gross_pnl == Decimal("1.0")
    assert outcome.pnl_percent == Decimal("10.0")


def test_compare_replay_scenarios_uses_end_of_data_close() -> None:
    base = datetime(2026, 5, 7, tzinfo=timezone.utc)
    record = make_record("p1", base)
    replay_input = ProposalReplayInput.from_records(
        [record],
        {"p1": [candle(base, close="103", high="104", low="99")]},
    )

    result = compare_replay_scenarios(
        replay_input,
        [ProposalReplayScenario()],
    )[0]

    outcome = result.outcomes[0]
    assert outcome.exit_reason == "end_of_data"
    assert outcome.exit_price == Decimal("103")
    assert outcome.gross_pnl == Decimal("0.3")
    assert result.approved_count == 1
    assert result.average_pnl_percent == Decimal("3.00")


def test_compare_replay_scenarios_handles_short_take_profit() -> None:
    base = datetime(2026, 5, 7, tzinfo=timezone.utc)
    record = make_record(
        "short",
        base,
        signal="short",
        entry_price="100",
        stop_loss="105",
        take_profit="90",
    )
    replay_input = ProposalReplayInput.from_records(
        [record],
        {"short": [candle(base, close="92", high="101", low="89")]},
    )

    result = compare_replay_scenarios(
        replay_input,
        [ProposalReplayScenario()],
    )[0]

    outcome = result.outcomes[0]
    assert outcome.exit_reason == "take_profit"
    assert outcome.exit_price == Decimal("90")
    assert outcome.gross_pnl == Decimal("1.0")
    assert outcome.pnl_percent == Decimal("10.0")


def test_render_replay_report_ranks_and_details_scenarios() -> None:
    base = datetime(2026, 5, 7, tzinfo=timezone.utc)
    record = make_record("p1", base)
    replay_input = ProposalReplayInput.from_records(
        [record],
        {"p1": [candle(base, high="112", low="94")]},
    )
    results = compare_replay_scenarios(
        replay_input,
        [
            ProposalReplayScenario(
                exit_assumption=ProposalReplayExitAssumption.STOP_FIRST,
            ),
            ProposalReplayScenario(
                exit_assumption=ProposalReplayExitAssumption.TAKE_PROFIT_FIRST,
            ),
        ],
    )

    report = render_replay_report(results)

    assert report.startswith("# Proposal Replay Report")
    assert "## Recommended Scenario" in report
    assert "`score>=0.0000:take_profit_first`" in report
    assert "| score>=0.0000:take_profit_first | 1 | 1.00 | 10.00 |" in report
    assert (
        "| score>=0.0000:stop_first | p1 | approved | stop_loss | -0.50 | -5.00 |"
        in report
    )

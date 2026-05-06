"""Tests for the proposal replay CLI."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path

from src.models import OHLCV
from src.proposal.engine import Proposal, ProposalScore
from src.proposal.interaction import ProposalDecision, ProposalRecord
from src.proposal.replay import ProposalReplayCase, ProposalReplayInput
from src.tools.proposal_replay import build_scenarios, main


def _score() -> ProposalScore:
    return ProposalScore(
        confidence=0.8,
        win_rate=0.6,
        sample_size=25,
        expected_value=2.0,
        sample_factor=1.0,
        edge_factor=2.0,
        composite=1.6,
    )


def _replay_input() -> ProposalReplayInput:
    ts = datetime(2026, 5, 7, tzinfo=timezone.utc)
    proposal = Proposal(
        proposal_id="p1",
        created_at=ts,
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
        score=_score(),
        reasoning="Replay fixture.",
    )
    record = ProposalRecord(
        proposal=proposal,
        decision=ProposalDecision.ACCEPTED,
        decision_at=ts,
    )
    candle = OHLCV(
        timestamp=ts,
        open=Decimal("100"),
        high=Decimal("112"),
        low=Decimal("94"),
        close=Decimal("100"),
        volume=Decimal("10"),
    )
    return ProposalReplayInput(
        cases=[ProposalReplayCase(record=record, candles=[candle])]
    )


def test_build_scenarios_defaults_to_stop_first() -> None:
    scenarios = build_scenarios(min_scores=[], exit_assumptions=[])

    assert len(scenarios) == 1
    assert scenarios[0].scenario_id == "score>=0.0000:stop_first"


def test_build_scenarios_cross_product() -> None:
    scenarios = build_scenarios(
        min_scores=[0.0, 2.0],
        exit_assumptions=["stop_first", "take_profit_first"],
    )

    assert [scenario.scenario_id for scenario in scenarios] == [
        "score>=0.0000:stop_first",
        "score>=0.0000:take_profit_first",
        "score>=2.0000:stop_first",
        "score>=2.0000:take_profit_first",
    ]


def test_main_writes_report_to_stdout(tmp_path: Path) -> None:
    input_path = tmp_path / "replay.json"
    input_path.write_text(_replay_input().model_dump_json(), encoding="utf-8")
    stdout = StringIO()

    rc = main(
        [
            "--input",
            str(input_path),
            "--exit-assumption",
            "take_profit_first",
        ],
        stdout=stdout,
    )

    assert rc == 0
    assert "# Proposal Replay Report" in stdout.getvalue()
    assert "`score>=0.0000:take_profit_first`" in stdout.getvalue()


def test_main_writes_report_to_file(tmp_path: Path) -> None:
    input_path = tmp_path / "replay.json"
    output_path = tmp_path / "reports" / "replay.md"
    input_path.write_text(_replay_input().model_dump_json(), encoding="utf-8")
    stdout = StringIO()

    rc = main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--min-score",
            "2.0",
        ],
        stdout=stdout,
    )

    assert rc == 0
    assert stdout.getvalue() == ""
    assert output_path.read_text(encoding="utf-8").startswith(
        "# Proposal Replay Report"
    )
    assert "score>=2.0000:stop_first" in output_path.read_text(encoding="utf-8")

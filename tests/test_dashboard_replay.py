"""Tests for the proposal replay dashboard page."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.dashboard.pages.replay import parse_min_scores, render_report_from_path
from src.models import OHLCV
from src.proposal.engine import Proposal, ProposalScore
from src.proposal.interaction import ProposalDecision, ProposalRecord
from src.proposal.replay import (
    ProposalReplayCase,
    ProposalReplayInput,
    ProposalReplayInputError,
)

APP_PATH = str(Path(__file__).resolve().parents[1] / "src" / "dashboard" / "app.py")


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
    timestamp = datetime(2026, 5, 7, tzinfo=timezone.utc)
    proposal = Proposal(
        proposal_id="p1",
        created_at=timestamp,
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
        decision_at=timestamp,
    )
    candle = OHLCV(
        timestamp=timestamp,
        open=Decimal("100"),
        high=Decimal("112"),
        low=Decimal("94"),
        close=Decimal("100"),
        volume=Decimal("10"),
    )
    return ProposalReplayInput(
        cases=[ProposalReplayCase(record=record, candles=[candle])]
    )


def test_parse_min_scores_accepts_comma_separated_values() -> None:
    assert parse_min_scores("0, 1.0,2.5") == [0.0, 1.0, 2.5]


def test_parse_min_scores_rejects_negative_values() -> None:
    with pytest.raises(ProposalReplayInputError, match="nonnegative"):
        parse_min_scores("-1")


def test_render_report_from_path_renders_markdown(tmp_path: Path) -> None:
    input_path = tmp_path / "replay.json"
    input_path.write_text(_replay_input().model_dump_json(), encoding="utf-8")

    report = render_report_from_path(
        input_path=input_path,
        min_score_text="0.0, 2.0",
        exit_assumptions=["stop_first"],
    )

    assert report.startswith("# Proposal Replay Report")
    assert "score>=0.0000:stop_first" in report
    assert "score>=2.0000:stop_first" in report


def test_app_navigation_includes_replay_page() -> None:
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    assert not at.exception, [str(e) for e in at.exception]
    sidebar_text = " ".join(m.value for m in at.sidebar.markdown)
    assert "Crypto Master" in sidebar_text

"""Tests for the user-interaction layer (Phase 6.2)."""

from __future__ import annotations

import builtins
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.proposal.engine import Proposal, ProposalScore
from src.proposal.interaction import (
    ProposalDecision,
    ProposalDecisionInput,
    ProposalHistory,
    ProposalHistoryError,
    ProposalInteraction,
    ProposalRecord,
    default_decision_prompt,
    format_proposal,
)

# =============================================================================
# Helpers
# =============================================================================


def make_score(
    *,
    composite: float = 1.6,
    confidence: float = 0.8,
    sample_size: int = 25,
    win_rate: float = 0.6,
    expected_value: float = 2.0,
    sample_factor: float = 1.0,
    edge_factor: float = 2.0,
) -> ProposalScore:
    return ProposalScore(
        confidence=confidence,
        win_rate=win_rate,
        sample_size=sample_size,
        expected_value=expected_value,
        sample_factor=sample_factor,
        edge_factor=edge_factor,
        composite=composite,
    )


def make_proposal(
    *,
    proposal_id: str | None = None,
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    signal: str = "long",
    technique_name: str = "tech_a",
    technique_version: str = "1.0.0",
    profile_name: str | None = None,
    entry: str = "50000",
    sl: str = "49500",
    tp: str = "51500",
    quantity: str = "0.1",
    leverage: int = 1,
    rr: float = 3.0,
    score: ProposalScore | None = None,
    reasoning: str = "Bullish breakout, high volume confirmation.",
    created_at: datetime | None = None,
) -> Proposal:
    kwargs: dict[str, object] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "signal": signal,
        "technique_name": technique_name,
        "technique_version": technique_version,
        "profile_name": profile_name,
        "entry_price": Decimal(entry),
        "stop_loss": Decimal(sl),
        "take_profit": Decimal(tp),
        "quantity": Decimal(quantity),
        "leverage": leverage,
        "risk_reward_ratio": rr,
        "score": score or make_score(),
        "reasoning": reasoning,
    }
    if proposal_id is not None:
        kwargs["proposal_id"] = proposal_id
    if created_at is not None:
        kwargs["created_at"] = created_at
    return Proposal(**kwargs)


class FakeInputs:
    """Patch ``builtins.input`` to feed scripted answers."""

    def __init__(self, answers: list[str]) -> None:
        self._answers: Iterator[str] = iter(answers)

    def __call__(self, prompt: str = "") -> str:
        try:
            return next(self._answers)
        except StopIteration as e:
            raise AssertionError(f"Unexpected extra input prompt: {prompt!r}") from e


# =============================================================================
# format_proposal
# =============================================================================


def test_format_proposal_includes_core_fields() -> None:
    proposal = make_proposal(
        proposal_id="abc-123",
        symbol="BTC/USDT",
        signal="long",
        entry="50000",
        sl="49500",
        tp="51500",
        rr=3.0,
        score=make_score(composite=1.6, sample_size=25, win_rate=0.6),
    )

    rendered = format_proposal(proposal)

    assert "abc-123" in rendered
    assert "BTC/USDT" in rendered
    assert "LONG" in rendered
    assert "50000" in rendered
    assert "49500" in rendered
    assert "51500" in rendered
    assert "1x" in rendered  # leverage
    assert "3.00" in rendered  # R/R
    assert "1.6" in rendered  # composite
    assert "25" in rendered  # sample size
    assert "60.00%" in rendered  # win rate
    assert "Bullish breakout" in rendered


def test_format_proposal_renders_no_history_score() -> None:
    """A score with no history (sample=0, edge=0) must still render cleanly."""
    proposal = make_proposal(
        score=make_score(
            composite=0.4,
            sample_size=0,
            win_rate=0.0,
            expected_value=0.0,
            sample_factor=0.0,
            edge_factor=0.0,
        ),
    )

    rendered = format_proposal(proposal)

    assert "Sample size:  0" in rendered
    assert "0.00%" in rendered
    assert "0.00" in rendered  # expected value


def test_format_proposal_truncates_long_reasoning() -> None:
    long_reason = "x" * 1000
    proposal = make_proposal(reasoning=long_reason)

    rendered = format_proposal(proposal)

    # Truncated and ellipsised, not the full 1000 characters.
    assert "..." in rendered
    assert "x" * 1000 not in rendered


def test_format_proposal_handles_empty_reasoning() -> None:
    proposal = make_proposal(reasoning="")

    rendered = format_proposal(proposal)

    assert "(no reasoning provided)" in rendered


def test_format_proposal_includes_profile_when_set() -> None:
    proposal = make_proposal(profile_name="conservative")

    rendered = format_proposal(proposal)

    assert "Profile:" in rendered
    assert "conservative" in rendered


# =============================================================================
# default_decision_prompt
# =============================================================================


async def test_default_decision_prompt_accepts_yes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(builtins, "input", FakeInputs(["yes"]))
    proposal = make_proposal()

    result = await default_decision_prompt(proposal)

    assert result.accepted is True
    assert result.reason is None
    captured = capsys.readouterr().out
    assert "TRADING PROPOSAL" in captured


async def test_default_decision_prompt_accepts_y_case_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(builtins, "input", FakeInputs(["Y"]))

    result = await default_decision_prompt(make_proposal())

    assert result.accepted is True


async def test_default_decision_prompt_rejects_with_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        builtins, "input", FakeInputs(["no", "low confidence on the trend"])
    )

    result = await default_decision_prompt(make_proposal())

    assert result.accepted is False
    assert result.reason == "low confidence on the trend"


async def test_default_decision_prompt_rejects_without_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(builtins, "input", FakeInputs(["no", ""]))

    result = await default_decision_prompt(make_proposal())

    assert result.accepted is False
    assert result.reason is None


# =============================================================================
# ProposalHistory
# =============================================================================


def test_history_save_load_round_trip(tmp_path: Path) -> None:
    history = ProposalHistory(data_dir=tmp_path)
    proposal = make_proposal()
    record = ProposalRecord(
        proposal=proposal,
        decision=ProposalDecision.ACCEPTED,
        decision_at=datetime(2026, 4, 26, 12, 0, 0),
        actor="user",
    )

    history.save(record)
    loaded = history.load(proposal.proposal_id)

    assert loaded.proposal.proposal_id == proposal.proposal_id
    assert loaded.proposal.entry_price == proposal.entry_price
    assert loaded.proposal.score.composite == proposal.score.composite
    assert loaded.decision == ProposalDecision.ACCEPTED.value
    assert loaded.decision_at == datetime(2026, 4, 26, 12, 0, 0)
    assert loaded.actor == "user"


def test_history_save_creates_directory_lazily(tmp_path: Path) -> None:
    """Caller doesn't have to pre-create data/proposals/."""
    target = tmp_path / "nested" / "proposals"
    history = ProposalHistory(data_dir=target)
    record = ProposalRecord(proposal=make_proposal())

    history.save(record)

    assert target.is_dir()
    assert (target / f"{record.proposal.proposal_id}.json").exists()


def test_history_load_unknown_id_raises(tmp_path: Path) -> None:
    history = ProposalHistory(data_dir=tmp_path)

    with pytest.raises(ProposalHistoryError, match="No proposal record"):
        history.load("does-not-exist")


def test_history_list_all_returns_chronological(tmp_path: Path) -> None:
    history = ProposalHistory(data_dir=tmp_path)
    p_old = make_proposal(proposal_id="old", created_at=datetime(2026, 1, 1, 0, 0, 0))
    p_new = make_proposal(proposal_id="new", created_at=datetime(2026, 4, 1, 0, 0, 0))
    # Save newer first to prove ordering isn't insertion order.
    history.save(ProposalRecord(proposal=p_new))
    history.save(ProposalRecord(proposal=p_old))

    records = history.list_all()

    assert [r.proposal.proposal_id for r in records] == ["old", "new"]


def test_history_list_all_filters_by_decision(tmp_path: Path) -> None:
    history = ProposalHistory(data_dir=tmp_path)
    accepted = ProposalRecord(
        proposal=make_proposal(proposal_id="a"),
        decision=ProposalDecision.ACCEPTED,
    )
    rejected = ProposalRecord(
        proposal=make_proposal(proposal_id="b"),
        decision=ProposalDecision.REJECTED,
    )
    pending = ProposalRecord(proposal=make_proposal(proposal_id="c"))
    history.save(accepted)
    history.save(rejected)
    history.save(pending)

    only_rejected = history.list_all(decision=ProposalDecision.REJECTED)

    assert len(only_rejected) == 1
    assert only_rejected[0].proposal.proposal_id == "b"


def test_history_list_all_returns_empty_when_dir_missing(tmp_path: Path) -> None:
    history = ProposalHistory(data_dir=tmp_path / "never_created")

    assert history.list_all() == []


def test_history_list_all_skips_malformed_files(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    history = ProposalHistory(data_dir=tmp_path)
    history.save(ProposalRecord(proposal=make_proposal(proposal_id="good")))
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    records = history.list_all()

    assert [r.proposal.proposal_id for r in records] == ["good"]


def test_history_attach_outcome_updates_record(tmp_path: Path) -> None:
    history = ProposalHistory(data_dir=tmp_path)
    proposal = make_proposal()
    history.save(
        ProposalRecord(
            proposal=proposal,
            decision=ProposalDecision.ACCEPTED,
            decision_at=datetime(2026, 4, 26, 12, 0, 0),
        )
    )

    updated = history.attach_outcome(
        proposal.proposal_id, trade_id="trade-99", pnl_percent=1.85
    )

    assert updated.trade_id == "trade-99"
    assert updated.outcome_pnl_percent == pytest.approx(1.85)
    assert updated.outcome_recorded_at is not None
    # Persisted, not just in memory.
    reloaded = history.load(proposal.proposal_id)
    assert reloaded.trade_id == "trade-99"
    assert reloaded.outcome_pnl_percent == pytest.approx(1.85)


def test_history_attach_outcome_unknown_id_raises(tmp_path: Path) -> None:
    history = ProposalHistory(data_dir=tmp_path)

    with pytest.raises(ProposalHistoryError):
        history.attach_outcome("nope", trade_id="t1", pnl_percent=0.0)


# =============================================================================
# ProposalInteraction
# =============================================================================


async def test_present_persists_accepted_record(tmp_path: Path) -> None:
    history = ProposalHistory(data_dir=tmp_path)

    async def accept(_: Proposal) -> ProposalDecisionInput:
        return ProposalDecisionInput(accepted=True)

    interaction = ProposalInteraction(history=history, decision_callback=accept)
    proposal = make_proposal()

    record = await interaction.present(proposal, actor="alice")

    assert record.decision == ProposalDecision.ACCEPTED.value
    assert record.actor == "alice"
    assert record.decision_at is not None
    assert record.rejection_reason is None
    # Persisted.
    reloaded = history.load(proposal.proposal_id)
    assert reloaded.decision == ProposalDecision.ACCEPTED.value


async def test_present_persists_rejected_record_with_reason(
    tmp_path: Path,
) -> None:
    history = ProposalHistory(data_dir=tmp_path)

    async def reject(_: Proposal) -> ProposalDecisionInput:
        return ProposalDecisionInput(accepted=False, reason="too risky")

    interaction = ProposalInteraction(history=history, decision_callback=reject)
    proposal = make_proposal()

    record = await interaction.present(proposal)

    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason == "too risky"
    reloaded = history.load(proposal.proposal_id)
    assert reloaded.rejection_reason == "too risky"


async def test_present_propagates_callback_exception_without_saving(
    tmp_path: Path,
) -> None:
    history = ProposalHistory(data_dir=tmp_path)

    async def boom(_: Proposal) -> ProposalDecisionInput:
        raise RuntimeError("interrupted")

    interaction = ProposalInteraction(history=history, decision_callback=boom)
    proposal = make_proposal()

    with pytest.raises(RuntimeError, match="interrupted"):
        await interaction.present(proposal)

    # Nothing saved.
    assert history.list_all() == []


async def test_present_batch_returns_one_record_per_proposal(
    tmp_path: Path,
) -> None:
    history = ProposalHistory(data_dir=tmp_path)
    decisions = iter(
        [
            ProposalDecisionInput(accepted=True),
            ProposalDecisionInput(accepted=False, reason="meh"),
            ProposalDecisionInput(accepted=True),
        ]
    )

    async def scripted(_: Proposal) -> ProposalDecisionInput:
        return next(decisions)

    interaction = ProposalInteraction(history=history, decision_callback=scripted)
    proposals = [
        make_proposal(proposal_id="p1", symbol="BTC/USDT"),
        make_proposal(proposal_id="p2", symbol="ETH/USDT"),
        make_proposal(proposal_id="p3", symbol="SOL/USDT"),
    ]

    records = await interaction.present_batch(proposals, actor="bob")

    assert [r.proposal.proposal_id for r in records] == ["p1", "p2", "p3"]
    assert records[0].decision == ProposalDecision.ACCEPTED.value
    assert records[1].decision == ProposalDecision.REJECTED.value
    assert records[1].rejection_reason == "meh"
    assert records[2].decision == ProposalDecision.ACCEPTED.value
    assert all(r.actor == "bob" for r in records)
    assert len(history.list_all()) == 3

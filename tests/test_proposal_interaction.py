"""Tests for the user-interaction layer (Phase 6.2)."""

from __future__ import annotations

import builtins
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from src.config import reload_settings
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


def test_history_constructor_respects_settings_data_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default history dir is rooted under Settings.data_dir (Phase 10.5)."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    reload_settings()
    try:
        history = ProposalHistory()
    finally:
        monkeypatch.delenv("DATA_DIR", raising=False)
        reload_settings()

    assert history.data_dir == tmp_path / "proposals"
    assert tmp_path in history.data_dir.parents


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
    assert (target / "default" / f"{record.proposal.proposal_id}.json").exists()


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
# Phase 10.4 — purge_old (age-based archive)
# =============================================================================


def test_purge_old_moves_aged_records_to_archive(tmp_path: Path) -> None:
    """Records older than retention move to ``archive/<YYYY-MM>/``."""
    history = ProposalHistory(data_dir=tmp_path)
    old = ProposalRecord(
        proposal=make_proposal(
            proposal_id="old",
            created_at=datetime(2024, 1, 15, 10, 0, 0),
        )
    )
    fresh = ProposalRecord(
        proposal=make_proposal(
            proposal_id="fresh",
            created_at=datetime(2026, 4, 1, 10, 0, 0),
        )
    )
    history.save(old)
    history.save(fresh)

    archived = history.purge_old(
        now=datetime(2026, 4, 28, 0, 0, 0), retention_months=12
    )

    assert len(archived) == 1
    # Old record moved into archive/2024-01/old.json
    archived_path = tmp_path / "default" / "archive" / "2024-01" / "old.json"
    assert archived_path.exists()
    assert archived[0] == archived_path
    # Fresh record left in place.
    assert (tmp_path / "default" / "fresh.json").exists()
    # Old record no longer at top level.
    assert not (tmp_path / "default" / "old.json").exists()


def test_purge_old_respects_retention_window(tmp_path: Path) -> None:
    """A record exactly at the cutoff stays; older records archive."""
    history = ProposalHistory(data_dir=tmp_path)
    boundary = datetime(2026, 1, 1, 0, 0, 0)
    just_inside = ProposalRecord(
        proposal=make_proposal(
            proposal_id="just-inside",
            # 11 months back — inside the 12-month window.
            created_at=boundary,
        )
    )
    just_outside = ProposalRecord(
        proposal=make_proposal(
            proposal_id="just-outside",
            # 13 months back — outside the 12-month window.
            created_at=datetime(2024, 12, 1, 0, 0, 0),
        )
    )
    history.save(just_inside)
    history.save(just_outside)

    archived = history.purge_old(
        now=datetime(2026, 12, 1, 0, 0, 0), retention_months=12
    )

    assert len(archived) == 1
    assert archived[0].name == "just-outside.json"
    assert (tmp_path / "default" / "just-inside.json").exists()


def test_purge_old_is_idempotent(tmp_path: Path) -> None:
    """Re-running with the same retention archives nothing the second time."""
    history = ProposalHistory(data_dir=tmp_path)
    history.save(
        ProposalRecord(
            proposal=make_proposal(
                proposal_id="ancient",
                created_at=datetime(2024, 1, 1, 0, 0, 0),
            )
        )
    )

    first = history.purge_old(now=datetime(2026, 4, 28, 0, 0, 0), retention_months=12)
    second = history.purge_old(now=datetime(2026, 4, 28, 0, 0, 0), retention_months=12)

    assert len(first) == 1
    assert second == []


def test_purge_old_uses_settings_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without explicit ``retention_months``, falls back to Settings."""
    monkeypatch.setenv("LOG_RETENTION_MONTHS", "1")
    reload_settings()
    try:
        history = ProposalHistory(data_dir=tmp_path)
        history.save(
            ProposalRecord(
                proposal=make_proposal(
                    proposal_id="month-old",
                    created_at=datetime(2026, 1, 1, 0, 0, 0),
                )
            )
        )

        archived = history.purge_old(now=datetime(2026, 4, 28, 0, 0, 0))
    finally:
        monkeypatch.delenv("LOG_RETENTION_MONTHS", raising=False)
        reload_settings()

    assert len(archived) == 1
    assert archived[0].parent.name == "2026-01"


def test_purge_old_uses_calendar_months_not_30_day_approximation(
    tmp_path: Path,
) -> None:
    """DEBT-036 / Phase 26.2: cutoff is true calendar months, not days * 30.

    For ``retention_months=12`` from ``2026-01-15``, the cutoff must
    land on ``2025-01-15`` (calendar-correct), not ``2025-01-20`` (the
    legacy ``timedelta(days=30 * 12) = 360 days`` buggy drift).

    Pin: a proposal at ``2025-01-17`` (3 days inside the legacy buggy
    cutoff but 2 days *outside* the true calendar cutoff) must
    archive under the corrected math.
    """
    history = ProposalHistory(data_dir=tmp_path)
    history.save(
        ProposalRecord(
            proposal=make_proposal(
                proposal_id="calendar-edge",
                created_at=datetime(2025, 1, 17, 0, 0, 0),
            )
        )
    )

    archived = history.purge_old(
        now=datetime(2026, 1, 15, 0, 0, 0), retention_months=12
    )

    # True calendar cutoff = 2025-01-15. The 2025-01-17 record is two
    # days *after* the cutoff → INSIDE the window → not archived.
    # Under the buggy 360-day cutoff (2025-01-20), it would have been
    # archived. The fact that this assertion passes pins the fix.
    assert archived == []
    assert (tmp_path / "default" / "calendar-edge.json").exists()


def test_purge_old_calendar_cutoff_archives_record_just_outside(
    tmp_path: Path,
) -> None:
    """DEBT-036 / Phase 26.2: the symmetric case — a record older than
    the true calendar cutoff is archived.

    From ``now=2026-01-15``, ``retention_months=12`` → cutoff
    ``2025-01-15``. A record at ``2025-01-14`` is one day older than
    the cutoff → archives.
    """
    history = ProposalHistory(data_dir=tmp_path)
    history.save(
        ProposalRecord(
            proposal=make_proposal(
                proposal_id="just-outside-cal",
                created_at=datetime(2025, 1, 14, 0, 0, 0),
            )
        )
    )

    archived = history.purge_old(
        now=datetime(2026, 1, 15, 0, 0, 0), retention_months=12
    )

    assert len(archived) == 1
    assert archived[0].name == "just-outside-cal.json"


def test_purge_old_does_not_revisit_archive_subdir(tmp_path: Path) -> None:
    """``list_all`` and ``purge_old`` ignore the ``archive/`` subdir."""
    history = ProposalHistory(data_dir=tmp_path)
    history.save(
        ProposalRecord(
            proposal=make_proposal(
                proposal_id="ancient",
                created_at=datetime(2024, 1, 1, 0, 0, 0),
            )
        )
    )
    history.purge_old(now=datetime(2026, 4, 28, 0, 0, 0), retention_months=12)

    # Top-level listing must not surface the archived file.
    assert history.list_all() == []


def test_purge_old_handles_missing_data_dir(tmp_path: Path) -> None:
    history = ProposalHistory(data_dir=tmp_path / "never_created")

    assert (
        history.purge_old(now=datetime(2026, 4, 28, 0, 0, 0), retention_months=12) == []
    )


def test_purge_old_skips_unreadable_files(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Corrupt JSON in the proposals dir doesn't crash the purge."""
    history = ProposalHistory(data_dir=tmp_path)
    history.save(
        ProposalRecord(
            proposal=make_proposal(
                proposal_id="ancient",
                created_at=datetime(2024, 1, 1, 0, 0, 0),
            )
        )
    )
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    archived = history.purge_old(
        now=datetime(2026, 4, 28, 0, 0, 0), retention_months=12
    )

    # The well-formed old record was archived; the corrupt file was skipped.
    assert len(archived) == 1
    assert archived[0].name == "ancient.json"
    # The broken file is left where it was.
    assert (tmp_path / "broken.json").exists()


# =============================================================================
# ProposalInteraction
# =============================================================================


async def test_set_decision_callback_swaps_callback_used_by_present(
    tmp_path: Path,
) -> None:
    """DEBT-041 / Phase 26.2: ``set_decision_callback`` swaps the
    callback in place and the next ``present`` call uses the new one.

    Pin: the public setter replaces the constructor-injected callback
    so callers (notably ``RuntimeEngine``) can drop the legacy
    ``self._decision_callback = ...`` private-attribute access.
    """
    history = ProposalHistory(data_dir=tmp_path)

    async def reject(_: Proposal) -> ProposalDecisionInput:
        return ProposalDecisionInput(accepted=False, reason="initial-cb")

    async def accept(_: Proposal) -> ProposalDecisionInput:
        return ProposalDecisionInput(accepted=True)

    interaction = ProposalInteraction(history=history, decision_callback=reject)
    interaction.set_decision_callback(accept)

    record = await interaction.present(make_proposal(), actor="alice")
    assert record.decision == ProposalDecision.ACCEPTED.value


async def test_set_decision_callback_is_idempotent_with_default_constructor(
    tmp_path: Path,
) -> None:
    """``set_decision_callback`` works when no callback was passed to
    the constructor — it overwrites the default stdin prompt.
    """
    history = ProposalHistory(data_dir=tmp_path)

    async def reject(_: Proposal) -> ProposalDecisionInput:
        return ProposalDecisionInput(accepted=False, reason="auto-no")

    interaction = ProposalInteraction(history=history)
    interaction.set_decision_callback(reject)

    record = await interaction.present(make_proposal())
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason == "auto-no"


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


# =============================================================================
# Phase 21.2 — UTC-aware write-side + legacy-tolerance at read boundary
# =============================================================================


async def test_present_writes_utc_aware_decision_at(tmp_path: Path) -> None:
    """Phase 21.2: ``decision_at`` is UTC-aware on a fresh write."""
    history = ProposalHistory(data_dir=tmp_path)

    async def accept(_: Proposal) -> ProposalDecisionInput:
        return ProposalDecisionInput(accepted=True)

    interaction = ProposalInteraction(history=history, decision_callback=accept)
    record = await interaction.present(make_proposal(proposal_id="utc-1"))

    assert record.decision_at is not None
    assert record.decision_at.tzinfo is not None
    assert record.decision_at.utcoffset() == timezone.utc.utcoffset(None)


def test_attach_outcome_writes_utc_aware_outcome_recorded_at(
    tmp_path: Path,
) -> None:
    """Phase 21.2: ``outcome_recorded_at`` is UTC-aware on a fresh write."""
    history = ProposalHistory(data_dir=tmp_path)
    record = ProposalRecord(
        proposal=make_proposal(proposal_id="utc-2"),
        decision=ProposalDecision.ACCEPTED,
    )
    history.save(record)

    updated = history.attach_outcome(
        proposal_id="utc-2",
        trade_id="trade-1",
        pnl_percent=1.5,
    )

    assert updated.outcome_recorded_at is not None
    assert updated.outcome_recorded_at.tzinfo is not None


def test_list_all_tolerates_legacy_naive_created_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy proposals on disk with naive ``created_at`` still load + sort.

    Phase 21.2: the sort key in :meth:`ProposalHistory.list_all` coerces
    naive timestamps to UTC at the comparison boundary so a partial
    rollout (some files naive, some aware) doesn't raise ``TypeError``.
    """
    history = ProposalHistory(data_dir=tmp_path)

    # Hand-craft a legacy proposal JSON with a naive ``created_at``.
    proposal = make_proposal(proposal_id="legacy-1")
    legacy_record = ProposalRecord(
        proposal=proposal,
        decision=ProposalDecision.PENDING,
    )
    legacy_payload = legacy_record.model_dump(mode="json")
    # Strip the timezone suffix from the ISO-8601 string so the on-disk
    # shape mimics a pre-21.2 record.
    legacy_payload["proposal"]["created_at"] = "2026-01-01T00:00:00"
    (tmp_path / "legacy-1.json").write_text(
        __import__("json").dumps(legacy_payload),
        encoding="utf-8",
    )

    # Save a fresh (aware) proposal alongside it.
    fresh = make_proposal(proposal_id="fresh-1")
    history.save(ProposalRecord(proposal=fresh, decision=ProposalDecision.PENDING))

    # ``list_all`` must not raise; the legacy record loads (its
    # ``created_at`` is treated as UTC) and sorts ahead of fresh.
    records = history.list_all()
    ids = [r.proposal.proposal_id for r in records]
    assert "legacy-1" in ids
    assert "fresh-1" in ids


def test_purge_old_tolerates_naive_now_argument(tmp_path: Path) -> None:
    """``purge_old`` coerces naive ``now`` arguments to UTC (Phase 21.2)."""
    history = ProposalHistory(data_dir=tmp_path)
    fresh = make_proposal(proposal_id="fresh-1")
    history.save(ProposalRecord(proposal=fresh, decision=ProposalDecision.PENDING))

    # Pass a naive ``now`` far in the future so retention shouldn't
    # apply (everything is younger than 30*N days from this far-future
    # cutoff). The point is that the comparison must not raise.
    naive_now = datetime(2027, 1, 1, 12, 0, 0)
    archived = history.purge_old(now=naive_now, retention_months=120)
    # 120 months is huge — nothing should be archived. Either way, no
    # ``TypeError`` from naive-vs-aware comparison.
    assert isinstance(archived, list)


# =============================================================================
# Phase 22.1 / DEBT-028 — atomic write regression
# =============================================================================


def test_proposal_history_save_crash_preserves_prior_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crash mid-save leaves the previous record JSON intact.

    Pins the DEBT-028 fix at ``ProposalHistory.save``. The engine's
    stale-quote rejection path runs ``load → model_copy → save``
    against the same file in the same cycle that
    ``ProposalInteraction.present`` first wrote it; the crash here
    must not corrupt the canonical record on disk.
    """
    history = ProposalHistory(data_dir=tmp_path)
    proposal = make_proposal(proposal_id="prop-22-1")
    record = ProposalRecord(
        proposal=proposal,
        decision=ProposalDecision.ACCEPTED,
        decision_at=datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc),
        actor="user",
    )
    history.save(record)

    # Now patch the helper and try to overwrite with a REJECTED
    # decision. The crash must not truncate the on-disk file.
    def boom(path: Path, text: str, **kwargs: object) -> None:
        raise OSError("simulated mid-write crash")

    monkeypatch.setattr("src.proposal.interaction.atomic_write_text", boom)

    rejected = record.model_copy(update={"decision": ProposalDecision.REJECTED.value})
    with pytest.raises(OSError, match="simulated mid-write crash"):
        history.save(rejected)

    # The original ACCEPTED record is still readable verbatim.
    loaded = history.load("prop-22-1")
    assert loaded.decision == ProposalDecision.ACCEPTED.value

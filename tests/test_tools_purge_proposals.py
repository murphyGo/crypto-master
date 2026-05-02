"""Tests for the operator CLI ``src.tools.purge_proposals`` (Phase 11.4)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import reload_settings
from src.proposal.engine import Proposal, ProposalScore
from src.proposal.interaction import ProposalHistory, ProposalRecord
from src.tools.purge_proposals import main

# =============================================================================
# Helpers
# =============================================================================


def _make_record(proposal_id: str, created_at: datetime) -> ProposalRecord:
    """Build a minimal ``ProposalRecord`` for purge fixtures.

    Mirrors the helpers in ``tests/test_proposal_interaction.py`` —
    only the fields ``Proposal`` requires are populated.
    """
    score = ProposalScore(
        confidence=0.8,
        win_rate=0.6,
        sample_size=25,
        expected_value=2.0,
        sample_factor=1.0,
        edge_factor=2.0,
        composite=1.6,
    )
    proposal = Proposal(
        proposal_id=proposal_id,
        symbol="BTC/USDT",
        timeframe="1h",
        signal="long",
        technique_name="tech_a",
        technique_version="1.0.0",
        entry_price=Decimal("50000"),
        stop_loss=Decimal("49500"),
        take_profit=Decimal("51500"),
        quantity=Decimal("0.1"),
        leverage=1,
        risk_reward_ratio=3.0,
        score=score,
        reasoning="Bullish breakout, high volume confirmation.",
        created_at=created_at,
    )
    return ProposalRecord(proposal=proposal)


# =============================================================================
# Tests
# =============================================================================


def test_main_calls_purge_old_with_settings_retention(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without ``--retention-months``, the CLI reads the value from
    :class:`Settings` and forwards it to
    :meth:`ProposalHistory.purge_old`."""
    with (
        patch("src.tools.purge_proposals.ProposalHistory") as history_cls,
        patch("src.tools.purge_proposals.get_settings") as get_settings,
    ):
        get_settings.return_value.log_retention_months = 9
        history_cls.return_value.purge_old.return_value = []

        rc = main([])

        assert rc == 0
        history_cls.return_value.purge_old.assert_called_once_with(retention_months=9)

    captured = capsys.readouterr()
    assert "9 months" in captured.out
    assert "nothing to purge" in captured.out


def test_main_explicit_retention_flag_overrides_settings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--retention-months`` wins over Settings."""
    with (
        patch("src.tools.purge_proposals.ProposalHistory") as history_cls,
        patch("src.tools.purge_proposals.get_settings") as get_settings,
    ):
        get_settings.return_value.log_retention_months = 12
        history_cls.return_value.purge_old.return_value = [
            Path("a.json"),
            Path("b.json"),
        ]

        rc = main(["--retention-months", "6"])

        assert rc == 0
        history_cls.return_value.purge_old.assert_called_once_with(retention_months=6)

    captured = capsys.readouterr()
    assert "Purged 2 proposal record(s)" in captured.out
    assert "6 months" in captured.out


def test_main_archives_old_records_against_real_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """End-to-end: with ``DATA_DIR`` pointing at ``tmp_path``, an old
    record on disk moves into
    ``proposals/default/archive/<YYYY-MM>/`` and the fresh one stays
    in the default sub-account directory."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_RETENTION_MONTHS", "1")
    reload_settings()
    try:
        proposals_dir = tmp_path / "proposals"
        history = ProposalHistory(data_dir=proposals_dir)
        history.save(_make_record("old", datetime(2024, 1, 15, 10, 0, 0)))
        history.save(_make_record("fresh", datetime.now()))

        rc = main(["--retention-months", "1"])
        assert rc == 0

        # Old record archived under its own creation month.
        archived = proposals_dir / "default" / "archive" / "2024-01" / "old.json"
        assert archived.exists()
        assert not (proposals_dir / "default" / "old.json").exists()
        # Fresh record stays in the default sub-account directory.
        assert (proposals_dir / "default" / "fresh.json").exists()

        captured = capsys.readouterr()
        assert "Purged 1 proposal record" in captured.out
        assert "1 months" in captured.out
    finally:
        monkeypatch.delenv("DATA_DIR", raising=False)
        monkeypatch.delenv("LOG_RETENTION_MONTHS", raising=False)
        reload_settings()


def test_main_prints_nothing_purged_when_empty(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI's empty-result print is informative, not blank."""
    with (
        patch("src.tools.purge_proposals.ProposalHistory") as history_cls,
        patch("src.tools.purge_proposals.get_settings") as get_settings,
    ):
        get_settings.return_value.log_retention_months = 12
        history_cls.return_value.purge_old.return_value = []

        rc = main([])

        assert rc == 0

    captured = capsys.readouterr()
    assert "No proposal records older than 12 months" in captured.out
    assert "nothing to purge" in captured.out

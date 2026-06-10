"""Tests for proposal-linked paper trade bounds repair."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from src.proposal.engine import Proposal, ProposalScore
from src.proposal.interaction import (
    ProposalDecision,
    ProposalFinalState,
    ProposalRecord,
)
from src.runtime.activity_log import ActivityEventType, ActivityLog
from src.strategy.performance import TradeHistory, TradeHistoryTracker
from src.tools.repair_paper_trade_bounds_from_proposals import (
    ProposalBoundsRepairSummary,
    _TradeBoundsPatch,
    _write_trade_bounds_patches,
    main,
    repair_paper_trade_bounds_from_proposals,
)


def _proposal(
    *,
    proposal_id: str = "proposal-1",
    sub_account_id: str = "default",
    technique_name: str = "ma_crossover",
    stop_loss: Decimal = Decimal("49500"),
    take_profit: Decimal = Decimal("51500"),
) -> Proposal:
    return Proposal(
        proposal_id=proposal_id,
        symbol="BTC/USDT",
        timeframe="1h",
        technique_name=technique_name,
        technique_version="1.0.0",
        sub_account_id=sub_account_id,
        signal="long",
        entry_price=Decimal("50000"),
        stop_loss=stop_loss,
        take_profit=take_profit,
        quantity=Decimal("0.1"),
        leverage=1,
        risk_reward_ratio=1.0,
        score=ProposalScore(
            confidence=0.8,
            win_rate=0.0,
            sample_size=0,
            expected_value=0.0,
            sample_factor=0.0,
            edge_factor=1.0,
            composite=0.8,
        ),
        reasoning="test",
    )


def _seed_proposal_record(
    data_dir: Path,
    *,
    trade_id: str,
    sub_account_id: str = "default",
    proposal_id: str = "proposal-1",
    stop_loss: Decimal = Decimal("49500"),
    take_profit: Decimal = Decimal("51500"),
) -> ProposalRecord:
    record = ProposalRecord(
        proposal=_proposal(
            proposal_id=proposal_id,
            sub_account_id=sub_account_id,
            stop_loss=stop_loss,
            take_profit=take_profit,
        ),
        sub_account_id=sub_account_id,
        decision=ProposalDecision.ACCEPTED,
        trade_id=trade_id,
        final_state=ProposalFinalState.TRADE_OPENED,
    )
    path = data_dir / "proposals" / sub_account_id / f"{proposal_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2))
    return record


def _seed_paper_trade(
    data_dir: Path,
    sub_account_id: str = "default",
    *,
    stop_loss: Decimal | None = None,
    take_profit: Decimal | None = None,
    status: str = "open",
) -> TradeHistory:
    tracker = TradeHistoryTracker(
        data_dir=data_dir / "trades",
        sub_account_id=sub_account_id,
    )
    trade = tracker.open_trade(
        symbol="BTC/USDT",
        side="long",
        entry_price=Decimal("50000"),
        entry_quantity=Decimal("0.1"),
        mode="paper",
        leverage=1,
        sub_account_id=sub_account_id,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )
    if status != "open":
        path = data_dir / "trades" / "paper" / sub_account_id / "trades.json"
        rows = json.loads(path.read_text())
        for row in rows:
            if row["id"] == trade.id:
                row["status"] = status
        path.write_text(json.dumps(rows, indent=2))
    return trade


def _read_trade_row(data_dir: Path, sub_account_id: str, trade_id: str) -> dict:
    path = data_dir / "trades" / "paper" / sub_account_id / "trades.json"
    for row in json.loads(path.read_text()):
        if row["id"] == trade_id:
            return row
    raise AssertionError(f"trade {trade_id} not found")


def test_repair_populates_open_trade_bounds_from_linked_proposal(
    tmp_path: Path,
) -> None:
    trade = _seed_paper_trade(tmp_path)
    _seed_proposal_record(tmp_path, trade_id=trade.id)

    summary = repair_paper_trade_bounds_from_proposals(tmp_path)

    assert summary == ProposalBoundsRepairSummary(examined=1, repaired=1)
    row = _read_trade_row(tmp_path, "default", trade.id)
    assert row["stop_loss"] == "49500"
    assert row["take_profit"] == "51500"
    assert row["performance_record_id"] is None


def test_repair_is_dry_run_only(tmp_path: Path) -> None:
    trade = _seed_paper_trade(tmp_path)
    _seed_proposal_record(tmp_path, trade_id=trade.id)

    summary = repair_paper_trade_bounds_from_proposals(tmp_path, dry_run=True)

    assert summary.repaired == 1
    row = _read_trade_row(tmp_path, "default", trade.id)
    assert row["stop_loss"] is None
    assert row["take_profit"] is None


def test_repair_skips_already_set(tmp_path: Path) -> None:
    trade = _seed_paper_trade(
        tmp_path,
        stop_loss=Decimal("49000"),
        take_profit=Decimal("52000"),
    )
    _seed_proposal_record(tmp_path, trade_id=trade.id)

    summary = repair_paper_trade_bounds_from_proposals(tmp_path)

    assert summary.already_set == 1
    assert summary.repaired == 0
    row = _read_trade_row(tmp_path, "default", trade.id)
    assert row["stop_loss"] == "49000"
    assert row["take_profit"] == "52000"


def test_repair_skips_open_trade_without_proposal(tmp_path: Path) -> None:
    _seed_paper_trade(tmp_path)

    summary = repair_paper_trade_bounds_from_proposals(tmp_path)

    assert summary.skipped_no_proposal == 1
    assert summary.repaired == 0


def test_repair_respects_sub_account_filter(tmp_path: Path) -> None:
    alpha = _seed_paper_trade(tmp_path, "alpha")
    beta = _seed_paper_trade(tmp_path, "beta")
    _seed_proposal_record(tmp_path, trade_id=alpha.id, sub_account_id="alpha")
    _seed_proposal_record(
        tmp_path,
        trade_id=beta.id,
        sub_account_id="beta",
        proposal_id="proposal-2",
    )

    summary = repair_paper_trade_bounds_from_proposals(
        tmp_path,
        sub_account="beta",
    )

    assert summary.examined == 1
    assert summary.repaired == 1
    assert _read_trade_row(tmp_path, "alpha", alpha.id)["stop_loss"] is None
    assert _read_trade_row(tmp_path, "beta", beta.id)["stop_loss"] == "49500"


def test_repair_skips_cross_account_proposal_match(tmp_path: Path) -> None:
    trade = _seed_paper_trade(tmp_path, "beta")
    _seed_proposal_record(tmp_path, trade_id=trade.id, sub_account_id="alpha")

    summary = repair_paper_trade_bounds_from_proposals(tmp_path)

    assert summary.repaired == 0
    assert summary.skipped_account_mismatch == 1
    row = _read_trade_row(tmp_path, "beta", trade.id)
    assert row["stop_loss"] is None
    assert row["take_profit"] is None


def test_patch_write_merges_into_latest_trade_snapshot(tmp_path: Path) -> None:
    trades_path = tmp_path / "trades" / "paper" / "default" / "trades.json"
    trades_path.parent.mkdir(parents=True)
    trades_path.write_text(
        json.dumps(
            [
                {
                    "id": "target",
                    "status": "open",
                    "stop_loss": None,
                    "take_profit": None,
                },
                {
                    "id": "concurrent",
                    "status": "open",
                    "stop_loss": "10",
                    "take_profit": "20",
                },
            ],
            indent=2,
        )
    )

    assert _write_trade_bounds_patches(
        trades_path,
        {"target": _TradeBoundsPatch(stop_loss="49500", take_profit="51500")},
    )

    rows = json.loads(trades_path.read_text())
    assert rows == [
        {
            "id": "target",
            "status": "open",
            "stop_loss": "49500",
            "take_profit": "51500",
        },
        {
            "id": "concurrent",
            "status": "open",
            "stop_loss": "10",
            "take_profit": "20",
        },
    ]


def test_live_repair_emits_activity_event(tmp_path: Path) -> None:
    trade = _seed_paper_trade(tmp_path)
    _seed_proposal_record(tmp_path, trade_id=trade.id)
    activity_log = ActivityLog(data_dir=tmp_path)

    repair_paper_trade_bounds_from_proposals(
        tmp_path,
        activity_log=activity_log,
    )

    events = activity_log.filter(
        event_type=ActivityEventType.RECONCILIATION_REPAIRED_PAPER_BOUNDS
    )
    assert len(events) == 1
    assert events[0].details["repaired"] == 1
    assert events[0].details["examined"] == 1


def test_dry_run_does_not_emit_activity_event(tmp_path: Path) -> None:
    trade = _seed_paper_trade(tmp_path)
    _seed_proposal_record(tmp_path, trade_id=trade.id)
    activity_log = ActivityLog(data_dir=tmp_path)

    repair_paper_trade_bounds_from_proposals(
        tmp_path,
        dry_run=True,
        activity_log=activity_log,
    )

    assert (
        activity_log.filter(
            event_type=ActivityEventType.RECONCILIATION_REPAIRED_PAPER_BOUNDS
        )
        == []
    )


def test_main_uses_settings_data_dir(tmp_path: Path) -> None:
    trade = _seed_paper_trade(tmp_path)
    _seed_proposal_record(tmp_path, trade_id=trade.id)

    with patch(
        "src.tools.repair_paper_trade_bounds_from_proposals.get_settings"
    ) as get_settings:
        get_settings.return_value.data_dir = tmp_path
        assert main([]) == 0

    assert _read_trade_row(tmp_path, "default", trade.id)["stop_loss"] == "49500"


def test_main_returns_nonzero_for_malformed_trade_file(tmp_path: Path) -> None:
    trades_path = tmp_path / "trades" / "paper" / "default" / "trades.json"
    trades_path.parent.mkdir(parents=True)
    trades_path.write_text("{not-json")

    with patch(
        "src.tools.repair_paper_trade_bounds_from_proposals.get_settings"
    ) as get_settings:
        get_settings.return_value.data_dir = tmp_path
        assert main([]) == 1

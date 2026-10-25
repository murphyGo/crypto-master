"""DEBT-087: persisted account outcomes reach proposal selection and scoring."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.exchange.base import BaseExchange
from src.main import build_engine
from src.models import OHLCV
from src.proposal.engine import Proposal, ProposalEngine, ProposalEngineConfig
from src.proposal.interaction import ProposalHistory, ProposalRecord
from src.runtime.activity_log import ActivityLog
from src.runtime.engine import EngineConfig
from src.runtime.snapshot_recorder import SnapshotRecorder
from src.strategy.performance import PerformanceRecord, PerformanceTracker
from src.strategy.trade_history import TradeHistoryTracker
from src.trading.base import Trader
from src.trading.sub_account_registry import SubAccountRegistry
from tests.test_proposal_engine import make_info, make_ohlcv, make_strategy


def _persist_history(
    root: Path,
    account: str,
    technique: str,
    *,
    count: int = 3,
    pnl: float = 4.0,
    version: str = "1.0.0",
    synthetic: bool = False,
    pending: bool = False,
) -> None:
    tracker = PerformanceTracker(data_dir=root, sub_account_id=account)
    entry = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(count):
        exit_price = Decimal("50000") * (1 + Decimal(str(pnl)) / 100)
        tracker.save_record(
            PerformanceRecord(
                technique_name=technique,
                technique_version=version,
                sub_account_id=account,
                symbol="BTC/USDT",
                timeframe="1h",
                signal="long",
                entry_price=Decimal("50000"),
                stop_loss=Decimal("49500"),
                take_profit=Decimal("52000"),
                confidence=0.8,
                analysis_timestamp=entry + timedelta(days=i),
                outcome="pending" if pending else "win" if pnl > 0 else "loss",
                exit_timestamp=None if pending else entry + timedelta(days=i, hours=1),
                exit_price=None if pending else exit_price,
                pnl_percent=None if pending else pnl,
                quantity=Decimal("0.02"),
                mode="paper",
                synthetic=synthetic,
            )
        )


def _engine(
    root: Path,
    *,
    multi: bool = True,
    live: bool = False,
    names: tuple[str, ...] = ("a_trend", "b_reversion"),
) -> ProposalEngine:
    exchange = AsyncMock(spec=BaseExchange)
    exchange.get_ohlcv.return_value = make_ohlcv(n=200)
    return ProposalEngine(
        exchange=exchange,
        strategies={
            name: make_strategy(make_info(name, symbols=[], technique_type="code"))
            for name in names
        },
        performance_tracker=PerformanceTracker(data_dir=root),
        config=ProposalEngineConfig(
            multi_technique_per_symbol=multi,
            mode="live" if live else "paper",
            min_closed_trades_for_live_promotion=5,
        ),
    )


async def _propose(engine: ProposalEngine, route: str, account: str) -> Proposal | None:
    if route == "bitcoin":
        return await engine.propose_bitcoin(sub_account_id=account)
    rows = await engine.propose_altcoins(
        symbols=["ETH/USDT", "BNB/USDT"], top_k=1, sub_account_id=account
    )
    return rows[0] if rows else None


@pytest.mark.parametrize("multi", [False, True])
@pytest.mark.parametrize("route", ["bitcoin", "altcoins"])
async def test_public_proposals_use_opposing_account_histories(
    tmp_path: Path, multi: bool, route: str
) -> None:
    """The same techniques select differently using each account's real files."""
    root = tmp_path / "injected-performance"
    for account, winning in [("alpha", "a_trend"), ("beta", "b_reversion")]:
        for name in ["a_trend", "b_reversion"]:
            _persist_history(root, account, name, pnl=4 if name == winning else -4)
    # A plausible default history must not contaminate either lab.
    _persist_history(root, "default", "a_trend", count=9, pnl=8)
    engine = _engine(root, multi=multi)

    for account, expected in [("alpha", "a_trend"), ("beta", "b_reversion")]:
        proposal = await _propose(engine, route, account)
        assert proposal is not None
        assert proposal.sub_account_id == account
        assert proposal.technique_name == expected
        assert proposal.score.sample_size == 3
        assert proposal.score.expected_value == pytest.approx(4)
        assert proposal.score.win_rate == 1
    assert engine.performance_tracker.data_dir == root
    assert engine.performance_tracker.sub_account_id == "default"


@pytest.mark.parametrize("multi", [False, True])
@pytest.mark.parametrize("route", ["bitcoin", "altcoins"])
async def test_live_gate_uses_closed_real_current_version_in_requested_account(
    tmp_path: Path, multi: bool, route: str
) -> None:
    root = tmp_path / "performance"
    _persist_history(root, "default", "a_trend", count=12)
    _persist_history(root, "thin", "a_trend", count=3)
    _persist_history(root, "thin", "a_trend", count=5, version="0.9.0")
    _persist_history(root, "thin", "a_trend", count=5, synthetic=True)
    _persist_history(root, "thin", "a_trend", count=5, pending=True)
    _persist_history(root, "ready", "a_trend", count=5)
    engine = _engine(root, multi=multi, live=True, names=("a_trend",))
    log = ActivityLog(path=tmp_path / "activity.jsonl")
    engine.activity_log = log

    assert await _propose(engine, route, "thin") is None
    blocked = log.read_all()[0]
    assert blocked.event_type == "cold_start_blocked"
    assert blocked.details["sub_account_id"] == "thin"
    assert blocked.details["max_trades_observed"] == 3

    proposal = await _propose(engine, route, "ready")
    assert proposal is not None
    assert proposal.score.sample_size == 5
    # A missing lab cannot borrow the mature default account's history.
    assert await _propose(engine, route, "missing") is None


async def test_paper_score_excludes_pending_synthetic_and_other_versions(
    tmp_path: Path,
) -> None:
    root = tmp_path / "performance"
    _persist_history(root, "beta", "a_trend", count=3, pnl=-2)
    _persist_history(root, "beta", "a_trend", count=5, version="0.9.0", pnl=90)
    _persist_history(root, "beta", "a_trend", count=5, synthetic=True, pnl=90)
    _persist_history(root, "beta", "a_trend", count=5, pending=True)
    engine = _engine(root, names=("a_trend",))

    proposal = await engine.propose_bitcoin(sub_account_id="beta")
    assert proposal is not None
    assert proposal.score.sample_size == 3
    assert proposal.score.expected_value == pytest.approx(-2)
    assert proposal.score.win_rate == 0
    assert proposal.score.sample_factor == pytest.approx(3 / 20)


async def test_default_account_and_injected_reader_behavior_remain_supported(
    tmp_path: Path,
) -> None:
    root = tmp_path / "custom-root"
    _persist_history(root, "default", "a_trend", count=2, pnl=3)
    _persist_history(root, "beta", "a_trend", count=4, pnl=-3)
    engine = _engine(root, names=("a_trend",))
    tracker = engine.performance_tracker
    with patch.object(tracker, "load_records", wraps=tracker.load_records) as read:
        proposal = await engine.propose_bitcoin()
        assert proposal is not None
        assert proposal.sub_account_id == "default"
        assert proposal.score.sample_size == 2
        read.assert_called_once_with("a_trend", "1.0.0")
    assert tracker.get_performance("a_trend").closed_real_trade_count == 2
    assert (
        tracker.get_performance(
            "a_trend", sub_account_id="beta"
        ).closed_real_trade_count
        == 4
    )
    assert tracker.sub_account_id == "default"


async def test_interleaved_requests_do_not_swap_shared_account_scope(
    tmp_path: Path,
) -> None:
    root = tmp_path / "performance"
    _persist_history(root, "alpha", "a_trend", count=2, pnl=4)
    _persist_history(root, "beta", "a_trend", count=5, pnl=-4)
    engine = _engine(root, names=("a_trend",))

    async def candles(**kwargs: object) -> list[OHLCV]:
        await asyncio.sleep(0)
        return make_ohlcv(n=200)

    engine.exchange.get_ohlcv.side_effect = candles
    alpha, beta = await asyncio.gather(
        engine.propose_bitcoin(sub_account_id="alpha"),
        engine.propose_bitcoin(sub_account_id="beta"),
    )
    assert alpha is not None and beta is not None
    assert (alpha.score.sample_size, alpha.score.expected_value) == (2, 4)
    assert (beta.score.sample_size, beta.score.expected_value) == (5, -4)
    assert engine.performance_tracker.sub_account_id == "default"


async def test_production_composition_reads_account_history_from_settings_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise main.build_engine's real tracker injection, not a test factory."""
    data_root = tmp_path / "mounted-data"
    settings = Settings(_env_file=None, data_dir=data_root, trading_mode="paper")
    monkeypatch.setattr("src.config._settings", settings)
    _persist_history(data_root / "performance", "beta", "a_trend", count=3, pnl=4)
    _persist_history(data_root / "performance", "default", "a_trend", count=7, pnl=-6)
    strategy = make_strategy(make_info("a_trend", technique_type="code"))
    monkeypatch.setattr("src.main.load_all_strategies", lambda: {"a_trend": strategy})
    exchange = AsyncMock(spec=BaseExchange)
    exchange.name = "stub"
    exchange.get_ohlcv.return_value = make_ohlcv(n=200)
    registry = MagicMock(spec=SubAccountRegistry)
    registry.list_active.return_value = []
    built = build_engine(
        settings,
        exchange,
        config=EngineConfig(),
        registry=registry,
        trader=MagicMock(spec=Trader),
        activity_log=ActivityLog(path=data_root / "runtime" / "activity.jsonl"),
    )

    tracker = built.proposal_engine.performance_tracker
    assert type(tracker) is PerformanceTracker
    assert tracker.data_dir == data_root / "performance"
    beta = await built.proposal_engine.propose_bitcoin(sub_account_id="beta")
    default = await built.proposal_engine.propose_bitcoin()
    assert beta is not None and default is not None
    assert (beta.score.sample_size, beta.score.expected_value) == (3, 4)
    assert (default.score.sample_size, default.score.expected_value) == (7, -6)
    assert tracker.sub_account_id == "default"


@pytest.mark.parametrize("multi", [False, True])
async def test_closed_trade_writer_feeds_next_proposal_in_same_account(
    tmp_path: Path, multi: bool
) -> None:
    """Reproduce production's default reader plus account-scoped close writer."""
    root = tmp_path / "performance"
    engine = _engine(root, multi=multi, names=("a_trend",))
    first = await engine.propose_bitcoin(sub_account_id="beta")
    assert first is not None and first.score.sample_size == 0
    trades = TradeHistoryTracker(tmp_path / "trades", sub_account_id="beta")
    opened = trades.open_trade(
        symbol=first.symbol,
        side=first.signal,
        entry_price=first.entry_price,
        entry_quantity=first.quantity,
        mode="paper",
        stop_loss=first.stop_loss,
        take_profit=first.take_profit,
    )
    history = ProposalHistory(data_dir=tmp_path / "proposals")
    history.save(
        ProposalRecord(
            proposal=first,
            sub_account_id="beta",
            decision="accepted",
            trade_id=opened.id,
            final_state="trade_opened",
        )
    )
    closed = trades.close_trade(
        opened.id, exit_price=first.take_profit, close_reason="take_profit"
    )
    assert closed is not None
    recorder = SnapshotRecorder(
        proposal_history=history,
        activity_log=ActivityLog(path=tmp_path / "activity.jsonl"),
        proposal_engine=engine,
        portfolio_tracker=None,
        default_exchange=engine.exchange,
        remember_mark_price=lambda *_: None,
    )
    recorder.record_closed_trade(closed, "take_profit", "close-cycle")

    assert (root / "beta" / "a_trend" / "records.json").exists()
    assert not (root / "default").exists()
    second = await engine.propose_bitcoin(sub_account_id="beta")
    assert second is not None
    assert second.score.sample_size == 1
    assert second.score.win_rate == 1
    assert second.score.expected_value == pytest.approx(closed.pnl_percent)
    assert second.score.composite > first.score.composite
    other = await engine.propose_bitcoin(sub_account_id="other")
    assert other is not None and other.score.sample_size == 0
    assert engine.performance_tracker.sub_account_id == "default"

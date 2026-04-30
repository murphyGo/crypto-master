"""Tests for the trading engine runtime (Phase 8.1)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exchange.base import BaseExchange, ExchangeAPIError
from src.models import Ticker
from src.proposal.engine import Proposal, ProposalEngine, ProposalScore
from src.proposal.interaction import (
    ProposalDecision,
    ProposalHistory,
    ProposalInteraction,
)
from src.proposal.notification import NotificationDispatcher
from src.runtime.activity_log import ActivityEventType, ActivityLog
from src.runtime.engine import (
    EngineConfig,
    TradingEngine,
)
from src.strategy.performance import TradeHistory

# =============================================================================
# Helpers
# =============================================================================


def make_score(composite: float = 1.6) -> ProposalScore:
    return ProposalScore(
        confidence=0.8,
        win_rate=0.6,
        sample_size=25,
        expected_value=2.0,
        sample_factor=1.0,
        edge_factor=2.0,
        composite=composite,
    )


def make_proposal(
    *,
    proposal_id: str | None = None,
    composite: float = 1.6,
    symbol: str = "BTC/USDT",
    signal: str = "long",
    entry: str = "50000",
    sl: str = "49500",
    tp: str = "51500",
    quantity: str = "0.1",
) -> Proposal:
    kwargs: dict[str, object] = {
        "symbol": symbol,
        "timeframe": "1h",
        "signal": signal,
        "technique_name": "tech_a",
        "technique_version": "1.0.0",
        "entry_price": Decimal(entry),
        "stop_loss": Decimal(sl),
        "take_profit": Decimal(tp),
        "quantity": Decimal(quantity),
        "leverage": 1,
        "risk_reward_ratio": 3.0,
        "score": make_score(composite=composite),
        "reasoning": "test",
    }
    if proposal_id is not None:
        kwargs["proposal_id"] = proposal_id
    return Proposal(**kwargs)


def make_trade(
    *,
    trade_id: str = "trade-1",
    symbol: str = "BTC/USDT",
    side: str = "long",
    entry: str = "50000",
    quantity: str = "0.1",
    exit_price: str | None = None,
    pnl_percent: float | None = None,
    status: str = "open",
) -> TradeHistory:
    return TradeHistory(
        id=trade_id,
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        mode="paper",
        entry_price=Decimal(entry),
        entry_quantity=Decimal(quantity),
        entry_time=datetime(2026, 4, 27, 12, 0, 0),
        exit_price=Decimal(exit_price) if exit_price is not None else None,
        exit_quantity=Decimal(quantity) if exit_price is not None else None,
        pnl_percent=pnl_percent,
        status=status,  # type: ignore[arg-type]
    )


def build_engine(
    *,
    tmp_path: Path,
    btc_proposal: Proposal | Exception | None = None,
    altcoin_proposals: list[Proposal] | Exception | None = None,
    config: EngineConfig | None = None,
    open_trades: list[TradeHistory] | None = None,
    ticker_price: Decimal = Decimal("50000"),
    ticker_error: Exception | None = None,
) -> tuple[TradingEngine, dict[str, MagicMock]]:
    """Build a TradingEngine with mock dependencies wired together."""
    exchange = AsyncMock(spec=BaseExchange)
    if ticker_error is not None:
        exchange.get_ticker.side_effect = ticker_error
    else:
        exchange.get_ticker.return_value = Ticker(
            symbol="BTC/USDT",
            price=ticker_price,
            timestamp=datetime(2026, 4, 27, 12, 5, 0),
        )

    proposal_engine = MagicMock(spec=ProposalEngine)
    if isinstance(btc_proposal, Exception):
        proposal_engine.propose_bitcoin = AsyncMock(side_effect=btc_proposal)
    else:
        proposal_engine.propose_bitcoin = AsyncMock(return_value=btc_proposal)
    if isinstance(altcoin_proposals, Exception):
        proposal_engine.propose_altcoins = AsyncMock(side_effect=altcoin_proposals)
    else:
        proposal_engine.propose_altcoins = AsyncMock(
            return_value=altcoin_proposals or []
        )

    history = ProposalHistory(data_dir=tmp_path / "proposals")
    interaction = ProposalInteraction(history=history)

    trader = MagicMock()
    trader.get_open_trades.return_value = open_trades or []
    # ``open_position`` and ``close_position`` are async on the
    # Trader protocol — Phase 10.1.
    trader.open_position = AsyncMock(
        side_effect=lambda position, **kwargs: make_trade(
            trade_id=f"t-{position.symbol}-{position.side}",
            symbol=position.symbol,
            side=position.side,
            entry=str(position.entry_price),
            quantity=str(position.quantity),
        )
    )
    trader.close_position = AsyncMock(return_value=None)
    # Default: no SL/TP exits.
    trader.check_exit_conditions.return_value = (False, None)

    notification_dispatcher = MagicMock(spec=NotificationDispatcher)
    notification_dispatcher.notify_proposal = AsyncMock(return_value=None)

    activity_log = ActivityLog(path=tmp_path / "activity.jsonl")

    engine = TradingEngine(
        exchange=exchange,
        proposal_engine=proposal_engine,
        proposal_interaction=interaction,
        proposal_history=history,
        trader=trader,
        notification_dispatcher=notification_dispatcher,
        activity_log=activity_log,
        config=config or EngineConfig(auto_approve_threshold=1.0),
    )
    return engine, {
        "exchange": exchange,
        "proposal_engine": proposal_engine,
        "history": history,
        "interaction": interaction,
        "trader": trader,
        "notification_dispatcher": notification_dispatcher,
        "activity_log": activity_log,
    }


# =============================================================================
# _auto_decide
# =============================================================================


async def test_auto_decide_accepts_above_threshold(tmp_path: Path) -> None:
    engine, _ = build_engine(
        tmp_path=tmp_path,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    proposal = make_proposal(composite=1.5)

    decision = await engine._auto_decide(proposal)

    assert decision.accepted is True
    assert decision.reason is None


async def test_auto_decide_accepts_at_threshold(tmp_path: Path) -> None:
    engine, _ = build_engine(
        tmp_path=tmp_path,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    proposal = make_proposal(composite=1.0)

    decision = await engine._auto_decide(proposal)

    assert decision.accepted is True


async def test_auto_decide_rejects_below_threshold(tmp_path: Path) -> None:
    engine, _ = build_engine(
        tmp_path=tmp_path,
        config=EngineConfig(auto_approve_threshold=1.5),
    )
    proposal = make_proposal(composite=0.4)

    decision = await engine._auto_decide(proposal)

    assert decision.accepted is False
    assert "0.4" in (decision.reason or "")
    assert "1.5" in (decision.reason or "")


# =============================================================================
# run_cycle: happy path
# =============================================================================


async def test_run_cycle_opens_position_for_accepted_proposal(
    tmp_path: Path,
) -> None:
    btc = make_proposal(proposal_id="btc-1", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=btc,
        config=EngineConfig(auto_approve_threshold=1.0),
    )

    result = await engine.run_cycle()

    assert result.proposals_generated == 1
    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 0
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_called_once()
    # Proposal record persisted with ACCEPTED + trade_id linked.
    record = mocks["history"].load("btc-1")
    assert record.decision == ProposalDecision.ACCEPTED.value
    assert record.trade_id == "t-BTC/USDT-long"


async def test_run_cycle_rejects_low_score_proposal(tmp_path: Path) -> None:
    btc = make_proposal(proposal_id="btc-low", composite=0.2)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=btc,
        config=EngineConfig(auto_approve_threshold=1.0),
    )

    result = await engine.run_cycle()

    assert result.proposals_rejected == 1
    assert result.positions_opened == 0
    mocks["trader"].open_position.assert_not_called()
    record = mocks["history"].load("btc-low")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason is not None


async def test_run_cycle_handles_no_proposals(tmp_path: Path) -> None:
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=None,
        altcoin_proposals=[],
    )

    result = await engine.run_cycle()

    assert result.proposals_generated == 0
    assert result.positions_opened == 0
    # Cycle still completes — there should be a CYCLE_COMPLETED event.
    completed = mocks["activity_log"].filter(
        event_type=ActivityEventType.CYCLE_COMPLETED
    )
    assert len(completed) == 1


# =============================================================================
# run_cycle: scan errors
# =============================================================================


async def test_run_cycle_btc_scan_error_does_not_block_altcoins(
    tmp_path: Path,
) -> None:
    alt = make_proposal(proposal_id="alt-1", symbol="ETH/USDT", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=ExchangeAPIError("rate limited"),
        altcoin_proposals=[alt],
    )

    result = await engine.run_cycle()

    assert result.proposals_generated == 1
    assert result.proposals_accepted == 1
    # SCAN_ERRORED was logged.
    errors = mocks["activity_log"].filter(event_type=ActivityEventType.SCAN_ERRORED)
    assert len(errors) == 1


async def test_run_cycle_altcoin_scan_error_logged(tmp_path: Path) -> None:
    btc = make_proposal(proposal_id="btc-1", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=btc,
        altcoin_proposals=ExchangeAPIError("alt down"),
    )

    result = await engine.run_cycle()

    assert result.proposals_generated == 1  # only BTC
    errors = mocks["activity_log"].filter(event_type=ActivityEventType.SCAN_ERRORED)
    assert len(errors) == 1


# =============================================================================
# Monitor pass
# =============================================================================


async def test_monitor_pass_closes_position_on_sl_hit(tmp_path: Path) -> None:
    """SL hit: paper_trader closes, attach_outcome writes realized P&L."""
    open_trade = make_trade(trade_id="t-existing")
    closed_trade = make_trade(
        trade_id="t-existing",
        exit_price="49500",
        pnl_percent=-1.0,
        status="closed",
    )

    # Pre-existing proposal record linked to this trade so the engine's
    # _find_proposal_for_trade lookup returns a hit.
    pre_proposal = make_proposal(proposal_id="p-existing")
    engine, mocks = build_engine(tmp_path=tmp_path, open_trades=[open_trade])
    mocks["history"].save_record_for_test = lambda *a, **kw: None  # safe noop
    # Save a record + link trade to it
    from src.proposal.interaction import ProposalRecord

    mocks["history"].save(
        ProposalRecord(proposal=pre_proposal, decision=ProposalDecision.ACCEPTED)
    )
    mocks["history"].attach_trade("p-existing", trade_id="t-existing")

    # Configure the trader: SL hit, close returns the closed trade.
    mocks["trader"].check_exit_conditions.return_value = (
        True,
        "stop_loss",
    )
    mocks["trader"].close_position.return_value = closed_trade

    result = await engine.run_cycle()

    assert result.positions_closed == 1
    mocks["trader"].close_position.assert_called_once()
    # Proposal record now has the realized outcome.
    record = mocks["history"].load("p-existing")
    assert record.outcome_pnl_percent == pytest.approx(-1.0)
    assert record.outcome_recorded_at is not None
    # POSITION_CLOSED event was logged.
    closed = mocks["activity_log"].filter(event_type=ActivityEventType.POSITION_CLOSED)
    assert len(closed) == 1


async def test_monitor_pass_skips_when_ticker_fails(tmp_path: Path) -> None:
    open_trade = make_trade(trade_id="t-1")
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        open_trades=[open_trade],
        ticker_error=ExchangeAPIError("ticker down"),
    )

    result = await engine.run_cycle()

    assert result.positions_closed == 0
    mocks["trader"].close_position.assert_not_called()
    monitor_errors = mocks["activity_log"].filter(
        event_type=ActivityEventType.MONITOR_ERRORED
    )
    assert len(monitor_errors) == 1


async def test_monitor_pass_no_open_trades(tmp_path: Path) -> None:
    engine, mocks = build_engine(tmp_path=tmp_path, open_trades=[])

    result = await engine.run_cycle()

    assert result.positions_closed == 0
    # MONITOR_PASS event still recorded with open_count=0.
    passes = mocks["activity_log"].filter(event_type=ActivityEventType.MONITOR_PASS)
    assert len(passes) == 1
    assert passes[0].details["open_count"] == 0


# =============================================================================
# run_forever + stop
# =============================================================================


async def test_run_forever_exits_when_stop_called(tmp_path: Path) -> None:
    """stop() interrupts the sleep and the loop exits cleanly."""
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        config=EngineConfig(
            cycle_interval_seconds=10,
            auto_approve_threshold=1.0,
        ),
    )

    async def stop_after_first_cycle() -> None:
        # Wait for the first SLEEPING event, then signal stop.
        for _ in range(50):
            sleep_events = mocks["activity_log"].filter(
                event_type=ActivityEventType.SLEEPING
            )
            if sleep_events:
                await engine.stop()
                return
            await asyncio.sleep(0.05)
        await engine.stop()  # safety net

    await asyncio.gather(engine.run_forever(), stop_after_first_cycle())

    # Engine exited; SHUTDOWN was logged.
    shutdowns = mocks["activity_log"].filter(event_type=ActivityEventType.SHUTDOWN)
    assert len(shutdowns) == 1


# =============================================================================
# Phase 12.1: Cross-Cycle Position Cap
# =============================================================================


def test_cap_default_is_one() -> None:
    """EngineConfig defaults to a per-symbol cap of 1."""
    config = EngineConfig()

    assert config.max_open_positions_per_symbol == 1


def test_cap_respects_env_via_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """ENGINE_MAX_OPEN_POSITIONS_PER_SYMBOL flows into build_engine's config."""
    monkeypatch.setenv("ENGINE_MAX_OPEN_POSITIONS_PER_SYMBOL", "3")

    from src.config import reload_settings
    from src.main import build_engine

    settings = reload_settings()
    assert settings.engine_max_open_positions_per_symbol == 3

    # ``build_engine`` constructs an exchange-dependent stack; we only
    # care that the cap field is wired through, so stub out the heavy
    # downstream constructors.
    fake_exchange = MagicMock(spec=BaseExchange)
    fake_exchange.name = "fake"
    fake_exchange.testnet = True
    with (
        patch("src.main.load_all_strategies", return_value=[]),
        patch("src.main.build_trader", return_value=MagicMock()),
    ):
        engine = build_engine(settings, fake_exchange)

    assert engine.config.max_open_positions_per_symbol == 3
    # Restore the singleton to defaults so other tests don't see the env value.
    monkeypatch.delenv("ENGINE_MAX_OPEN_POSITIONS_PER_SYMBOL", raising=False)
    reload_settings()


async def test_proposal_rejected_when_symbol_cap_reached(tmp_path: Path) -> None:
    """Cap reached across cycles: accepted proposal is blocked at the gate."""
    # Trader already holds an open BNB short from a prior cycle.
    existing_trade = make_trade(
        trade_id="t-bnb-existing",
        symbol="BNB/USDT",
        side="short",
    )
    proposal = make_proposal(
        proposal_id="bnb-2",
        symbol="BNB/USDT",
        signal="short",
        composite=2.0,
    )

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=1,
        ),
        open_trades=[existing_trade],
    )

    result = await engine.run_cycle()

    # Composite gate accepted; cap layer rejected.
    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 1
    assert result.positions_opened == 0
    mocks["trader"].open_position.assert_not_called()

    # Activity log carries a PROPOSAL_REJECTED event with the cap reason.
    rejections = mocks["activity_log"].filter(
        event_type=ActivityEventType.PROPOSAL_REJECTED
    )
    assert len(rejections) == 1
    rejection = rejections[0]
    reason = rejection.details["reason"]
    assert "BNB/USDT" in reason
    assert "cap 1 reached" in reason
    assert rejection.details["open_count"] == 1
    assert rejection.details["cap"] == 1


async def test_proposal_executes_when_cap_not_reached(tmp_path: Path) -> None:
    """No existing open trade on the symbol: proposal executes normally."""
    # SL above entry for a coherent short proposal (the Phase 18.1
    # stale-quote gate dispatches off ``proposal.signal``; an inverted
    # SL would trip the past-SL check in this test's default ticker
    # state).
    proposal = make_proposal(
        proposal_id="bnb-1",
        symbol="BNB/USDT",
        signal="short",
        composite=2.0,
        entry="50000",
        sl="50500",
        tp="48500",
    )

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=1,
        ),
        open_trades=[],
    )

    result = await engine.run_cycle()

    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 0
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_called_once()
    # No PROPOSAL_REJECTED in the log for this cycle.
    rejections = mocks["activity_log"].filter(
        event_type=ActivityEventType.PROPOSAL_REJECTED
    )
    assert len(rejections) == 0


async def test_cap_counts_only_matching_symbol(tmp_path: Path) -> None:
    """Open trades on other symbols don't count against this symbol's cap."""
    other_trade = make_trade(
        trade_id="t-eth-existing",
        symbol="ETH/USDT",
        side="long",
    )
    # SL above entry for a coherent short proposal (Phase 18.1).
    proposal = make_proposal(
        proposal_id="bnb-1",
        symbol="BNB/USDT",
        signal="short",
        composite=2.0,
        entry="50000",
        sl="50500",
        tp="48500",
    )

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=1,
        ),
        open_trades=[other_trade],
    )

    result = await engine.run_cycle()

    # ETH open trade does NOT block a BNB proposal.
    assert result.proposals_accepted == 1
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_called_once()


async def test_cap_blocks_opposite_side_same_symbol(tmp_path: Path) -> None:
    """Cap counts trades regardless of side: long blocks a same-symbol short.

    DEBT-010 (Phase 13.1): an existing BNB long must block a BNB short
    proposal at cap=1. This prevents synthetic hedges (long + short on
    one symbol slipping past the per-symbol cap on side mismatch).
    """
    existing_long = make_trade(
        trade_id="t-bnb-long",
        symbol="BNB/USDT",
        side="long",
    )
    short_proposal = make_proposal(
        proposal_id="bnb-short-1",
        symbol="BNB/USDT",
        signal="short",
        composite=2.0,
    )

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=short_proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=1,
        ),
        open_trades=[existing_long],
    )

    result = await engine.run_cycle()

    # Composite gate accepted; cap layer rejected the opposite-side trade.
    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 1
    assert result.positions_opened == 0
    mocks["trader"].open_position.assert_not_called()

    # Activity log carries a PROPOSAL_REJECTED with the cap reason for BNB.
    rejections = mocks["activity_log"].filter(
        event_type=ActivityEventType.PROPOSAL_REJECTED
    )
    assert len(rejections) == 1
    rejection = rejections[0]
    reason = rejection.details["reason"]
    assert "BNB/USDT" in reason
    assert "cap 1 reached" in reason
    assert rejection.details["open_count"] == 1
    assert rejection.details["cap"] == 1


async def test_interruptible_sleep_wakes_on_stop(tmp_path: Path) -> None:
    """Direct test of the sleep helper: stop() shortcuts a long sleep."""
    engine, _ = build_engine(tmp_path=tmp_path)

    async def signal_stop_soon() -> None:
        await asyncio.sleep(0.05)
        await engine.stop()

    sleep_task = asyncio.create_task(engine._interruptible_sleep(60))
    stop_task = asyncio.create_task(signal_stop_soon())

    await asyncio.wait_for(asyncio.gather(sleep_task, stop_task), timeout=2.0)


# =============================================================================
# Portfolio snapshot recording (Phase 17.2)
# =============================================================================


async def test_portfolio_snapshot_recorded_each_cycle(tmp_path: Path) -> None:
    """Engine writes an AssetSnapshot at the end of every cycle when wired."""
    from src.trading.portfolio import PortfolioTracker

    engine, mocks = build_engine(tmp_path=tmp_path)

    portfolio_tracker = PortfolioTracker(data_dir=tmp_path / "portfolio")
    engine.portfolio_tracker = portfolio_tracker
    engine.mode = "paper"
    engine.quote_currency = "USDT"

    mocks["trader"].get_balances = AsyncMock(return_value={"USDT": Decimal("9876.54")})

    await engine.run_cycle()

    snapshots = portfolio_tracker.load_snapshots("paper")
    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap.balances["USDT"] == Decimal("9876.54")
    assert snap.quote_currency == "USDT"


async def test_portfolio_snapshot_skipped_when_tracker_absent(
    tmp_path: Path,
) -> None:
    """No tracker wired -> no balance fetch attempted -> cycle still completes."""
    engine, mocks = build_engine(tmp_path=tmp_path)
    # No portfolio_tracker assignment — defaults to None.
    mocks["trader"].get_balances = AsyncMock()

    await engine.run_cycle()

    mocks["trader"].get_balances.assert_not_called()


async def test_close_writes_performance_record_for_dashboard(
    tmp_path: Path,
) -> None:
    """When a position closes, a PerformanceRecord lands in data/performance/.

    The Analysis Techniques dashboard reads from this directory to
    aggregate per-technique win rate / total P&L; without this wiring
    the page shows zeros for every metric.
    """
    from src.proposal.interaction import ProposalRecord
    from src.strategy.performance import (
        PerformanceTracker,
        TradeOutcome,
    )

    tracker = PerformanceTracker(data_dir=tmp_path / "performance")

    # Open trade primed with TP-hit prices so monitor closes it.
    open_trade = make_trade(
        trade_id="t-close-1",
        entry="50000",
        exit_price="50000",
        pnl_percent=2.0,
        status="open",
    )

    pre_proposal = make_proposal(proposal_id="p-close-1", composite=1.6)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        open_trades=[open_trade],
        ticker_price=Decimal("51500"),  # at the TP
    )
    # Inject the same tracker the proposal engine should be using for
    # the dashboard read path.
    mocks["proposal_engine"].performance_tracker = tracker

    mocks["history"].save(
        ProposalRecord(
            proposal=pre_proposal,
            decision=ProposalDecision.ACCEPTED,
            trade_id="t-close-1",
        )
    )

    # Close path: stub so check_exit_conditions reports TP, close returns
    # a populated TradeHistory.
    closed_trade = make_trade(
        trade_id="t-close-1",
        entry="50000",
        exit_price="51500",
        pnl_percent=3.0,
        status="closed",
    )
    closed_trade.close_reason = "take_profit"
    closed_trade.exit_time = datetime(2026, 4, 27, 13, 0, 0)
    mocks["trader"].check_exit_conditions.return_value = (True, "take_profit")
    mocks["trader"].close_position.return_value = closed_trade

    await engine.run_cycle()

    records = tracker.load_records(pre_proposal.technique_name)
    assert len(records) == 1
    rec = records[0]
    assert rec.trade_id == "t-close-1"
    assert rec.outcome == TradeOutcome.WIN
    assert rec.pnl_percent == 3.0
    assert rec.symbol == pre_proposal.symbol
    assert rec.signal == pre_proposal.signal


# =============================================================================
# Phase 18.1: Stale-Quote Sanity Gate at Proposal Fill
# =============================================================================


async def test_stale_quote_gate_rejects_when_live_past_sl(
    tmp_path: Path,
) -> None:
    """Live has crossed the proposal's SL → reject fill, no open_position."""
    # Long proposal: entry=50000, SL=49500. Live=49400 has crossed SL.
    proposal = make_proposal(proposal_id="stale-1", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        ticker_price=Decimal("49400"),
    )

    result = await engine.run_cycle()

    # open_position must NOT be called.
    mocks["trader"].open_position.assert_not_called()
    assert result.positions_opened == 0
    assert result.proposals_rejected == 1

    # Proposal record overwritten as REJECTED with the stale-quote reason.
    record = mocks["history"].load("stale-1")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason == "stale_quote_past_sl"
    # Phase 21.2: decision_at on the overwritten record is UTC-aware.
    assert record.decision_at is not None
    assert record.decision_at.tzinfo is not None

    # Activity event with structured payload.
    rejections = mocks["activity_log"].filter(
        event_type=ActivityEventType.PROPOSAL_REJECTED
    )
    assert len(rejections) == 1
    details = rejections[0].details
    assert details["reason"] == "stale_quote_past_sl"
    assert details["proposal_entry"] == "50000"
    assert details["proposal_stop_loss"] == "49500"
    assert details["live_price"] == "49400"
    # drift_bps = |49400 - 50000| / 50000 * 10_000 = 120
    assert details["drift_bps"] == pytest.approx(120.0)


async def test_stale_quote_gate_rejects_when_live_past_sl_short(
    tmp_path: Path,
) -> None:
    """Short side: live >= SL is the stale-quote condition."""
    # Short proposal: entry=50000, SL=50500. Live=50600 has crossed SL upward.
    proposal = make_proposal(
        proposal_id="stale-short-1",
        composite=2.0,
        signal="short",
        entry="50000",
        sl="50500",
        tp="48500",
    )
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        ticker_price=Decimal("50600"),
    )

    result = await engine.run_cycle()

    mocks["trader"].open_position.assert_not_called()
    assert result.positions_opened == 0
    record = mocks["history"].load("stale-short-1")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason == "stale_quote_past_sl"


async def test_stale_quote_gate_fills_when_within_tolerance(
    tmp_path: Path,
) -> None:
    """Live within slippage tolerance → fill at proposal.entry_price.

    Regression guard for the no-silent-switch contract: even when the
    live price differs from the proposal's entry, the gate must NOT
    mutate the entry. The proposal's R/R math is predicated on
    ``entry_price``.
    """
    # Long proposal: entry=50000, SL=49500. Live=50100 → drift 20 bps,
    # well below the 50 bps default tolerance, and not past SL.
    proposal = make_proposal(proposal_id="ok-1", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        ticker_price=Decimal("50100"),
    )

    result = await engine.run_cycle()

    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_called_once()
    # The Position handed to the trader carries the *proposal* entry,
    # not the live price.
    call_position = mocks["trader"].open_position.call_args.args[0]
    assert call_position.entry_price == Decimal("50000")

    # Proposal record stays ACCEPTED.
    record = mocks["history"].load("ok-1")
    assert record.decision == ProposalDecision.ACCEPTED.value
    # No PROPOSAL_REJECTED activity for this cycle.
    rejections = mocks["activity_log"].filter(
        event_type=ActivityEventType.PROPOSAL_REJECTED
    )
    assert len(rejections) == 0


async def test_stale_quote_gate_rejects_when_drift_exceeds_tolerance(
    tmp_path: Path,
) -> None:
    """Live drift beyond fill_slippage_tolerance → reject."""
    # Long proposal: entry=50000, SL=49500. Live=50500 → drift 100 bps,
    # which exceeds the 50 bps default. SL not crossed (50500 > 49500).
    proposal = make_proposal(proposal_id="drift-1", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        ticker_price=Decimal("50500"),
    )

    result = await engine.run_cycle()

    mocks["trader"].open_position.assert_not_called()
    assert result.positions_opened == 0
    assert result.proposals_rejected == 1

    record = mocks["history"].load("drift-1")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason == "slippage_exceeds_tolerance"

    rejections = mocks["activity_log"].filter(
        event_type=ActivityEventType.PROPOSAL_REJECTED
    )
    assert len(rejections) == 1
    details = rejections[0].details
    assert details["reason"] == "slippage_exceeds_tolerance"
    assert details["live_price"] == "50500"
    # drift_bps = |50500 - 50000| / 50000 * 10_000 = 100
    assert details["drift_bps"] == pytest.approx(100.0)


async def test_stale_quote_gate_falls_through_on_ticker_failure(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """exchange.get_ticker raising → fill proceeds, WARN logged.

    Transient exchange errors must not silently disable trading. The
    operator's signal is the WARN log emitted with the
    ``stale_quote_check_failed`` marker.
    """
    proposal = make_proposal(proposal_id="fallback-1", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        ticker_error=ExchangeAPIError("ticker down"),
    )

    import logging

    # ``get_logger`` disables propagation so caplog's root handler
    # misses these records — wire caplog onto the named logger for
    # the duration of the assertion (same pattern as test_main_dispatch).
    target_logger = logging.getLogger("crypto_master.runtime.engine")
    target_logger.addHandler(caplog.handler)
    previous_level = target_logger.level
    target_logger.setLevel(logging.WARNING)
    try:
        result = await engine.run_cycle()
    finally:
        target_logger.removeHandler(caplog.handler)
        target_logger.setLevel(previous_level)

    # Fill proceeded.
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_called_once()
    record = mocks["history"].load("fallback-1")
    assert record.decision == ProposalDecision.ACCEPTED.value

    # WARN log carries the marker + the symbol + proposal id.
    warn_messages = [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and "stale_quote_check_failed" in r.getMessage()
    ]
    assert len(warn_messages) == 1
    msg = warn_messages[0]
    assert "BTC/USDT" in msg
    assert "fallback-1" in msg


async def test_portfolio_snapshot_balance_failure_does_not_break_cycle(
    tmp_path: Path,
) -> None:
    """A flaky balance fetch is logged and swallowed."""
    from src.trading.portfolio import PortfolioTracker

    engine, mocks = build_engine(tmp_path=tmp_path)
    portfolio_tracker = PortfolioTracker(data_dir=tmp_path / "portfolio")
    engine.portfolio_tracker = portfolio_tracker

    mocks["trader"].get_balances = AsyncMock(
        side_effect=ExchangeAPIError("rate limited")
    )

    # Cycle must complete even though the snapshot couldn't be recorded.
    result = await engine.run_cycle()

    assert result is not None
    assert portfolio_tracker.load_snapshots("paper") == []

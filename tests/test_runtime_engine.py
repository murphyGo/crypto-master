"""Tests for the trading engine runtime (Phase 8.1)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

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

    paper_trader = MagicMock()
    paper_trader.get_open_trades.return_value = open_trades or []
    # Default: open_position returns a fresh trade with the new id.
    paper_trader.open_position.side_effect = lambda position, **kwargs: make_trade(
        trade_id=f"t-{position.symbol}-{position.side}",
        symbol=position.symbol,
        side=position.side,
        entry=str(position.entry_price),
        quantity=str(position.quantity),
    )
    # Default: no SL/TP exits.
    paper_trader.check_exit_conditions.return_value = (False, None)

    notification_dispatcher = MagicMock(spec=NotificationDispatcher)
    notification_dispatcher.notify_proposal = AsyncMock(return_value=None)

    activity_log = ActivityLog(path=tmp_path / "activity.jsonl")

    engine = TradingEngine(
        exchange=exchange,
        proposal_engine=proposal_engine,
        proposal_interaction=interaction,
        proposal_history=history,
        paper_trader=paper_trader,
        notification_dispatcher=notification_dispatcher,
        activity_log=activity_log,
        config=config or EngineConfig(auto_approve_threshold=1.0),
    )
    return engine, {
        "exchange": exchange,
        "proposal_engine": proposal_engine,
        "history": history,
        "interaction": interaction,
        "paper_trader": paper_trader,
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
    mocks["paper_trader"].open_position.assert_called_once()
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
    mocks["paper_trader"].open_position.assert_not_called()
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
    mocks["paper_trader"].check_exit_conditions.return_value = (
        True,
        "stop_loss",
    )
    mocks["paper_trader"].close_position.return_value = closed_trade

    result = await engine.run_cycle()

    assert result.positions_closed == 1
    mocks["paper_trader"].close_position.assert_called_once()
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
    mocks["paper_trader"].close_position.assert_not_called()
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


async def test_interruptible_sleep_wakes_on_stop(tmp_path: Path) -> None:
    """Direct test of the sleep helper: stop() shortcuts a long sleep."""
    engine, _ = build_engine(tmp_path=tmp_path)

    async def signal_stop_soon() -> None:
        await asyncio.sleep(0.05)
        await engine.stop()

    sleep_task = asyncio.create_task(engine._interruptible_sleep(60))
    stop_task = asyncio.create_task(signal_stop_soon())

    await asyncio.wait_for(asyncio.gather(sleep_task, stop_task), timeout=2.0)

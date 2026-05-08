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
    ProposalRecord,
)
from src.proposal.notification import (
    Notification,
    NotificationDispatcher,
    NotificationLevel,
)
from src.runtime.activity_log import ActivityEventType, ActivityLog
from src.runtime.engine import (
    EngineConfig,
    TradingEngine,
)
from src.strategy.performance import PerformanceTracker, TradeHistory
from src.trading.sub_account import (
    CapitalPolicy,
    ExecutionPolicy,
    ProposalPolicy,
    RiskOverrides,
    RiskPolicy,
    StrategyPolicy,
    SubAccount,
)
from src.utils.time import now_utc

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
    performance_record_id: str | None = None,
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
        performance_record_id=performance_record_id,
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
    ticker_timestamp: datetime | None = None,
) -> tuple[TradingEngine, dict[str, MagicMock]]:
    """Build a TradingEngine with mock dependencies wired together."""
    exchange = AsyncMock(spec=BaseExchange)
    if ticker_error is not None:
        exchange.get_ticker.side_effect = ticker_error
    else:
        # Phase 24.1 / DEBT-033: ticker timestamp must be fresh
        # relative to ``now_utc()`` so the freshness gate falls
        # through to the stale-quote sanity checks. Tests that
        # exercise the freshness gate itself override this via
        # ``ticker_timestamp``.
        ts = ticker_timestamp if ticker_timestamp is not None else now_utc()
        exchange.get_ticker.return_value = Ticker(
            symbol="BTC/USDT",
            price=ticker_price,
            timestamp=ts,
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


class FakeSubAccountRegistry:
    def __init__(self, sub_accounts: list[SubAccount], traders: dict[str, MagicMock]):
        self.sub_accounts = sub_accounts
        self.traders = traders
        self.filter_calls: list[tuple[str, list[object]]] = []

    def list_active(self) -> list[SubAccount]:
        return self.sub_accounts

    def get_trader(self, id: str) -> MagicMock:
        return self.traders[id]

    def get(self, id: str) -> SubAccount:
        for sub_account in self.sub_accounts:
            if sub_account.id == id:
                return sub_account
        raise KeyError(id)

    def filter_strategies(self, id: str, available: list[object]) -> list[object]:
        self.filter_calls.append((id, available))
        sub_account = self.get(id)
        strategy_filter = sub_account.effective_strategy_filter()
        if strategy_filter is None:
            return available
        allowed = set(strategy_filter)
        return [
            s
            for s in available
            if getattr(getattr(s, "info", None), "name", None) in allowed
        ]


def make_mock_trader() -> MagicMock:
    trader = MagicMock()
    trader.get_open_trades.return_value = []
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
    trader.check_exit_conditions.return_value = (False, None)
    trader.get_balances = AsyncMock(return_value={"USDT": Decimal("10000")})
    return trader


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


async def test_auto_decide_uses_sub_account_threshold_override(
    tmp_path: Path,
) -> None:
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    sub = SubAccount(
        id="experimental",
        name="Experimental",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
        risk_overrides=RiskOverrides(auto_approve_threshold=2.0),
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"experimental": mocks["trader"]},
    )
    proposal = make_proposal(composite=1.5).model_copy(
        update={"sub_account_id": "experimental"}
    )

    decision = await engine._auto_decide(proposal)

    assert decision.accepted is False
    assert "2.0000" in (decision.reason or "")


async def test_auto_decide_uses_proposal_policy_threshold(
    tmp_path: Path,
) -> None:
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        config=EngineConfig(auto_approve_threshold=2.0),
    )
    sub = SubAccount(
        id="paper_lab",
        name="Paper Lab",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
        proposal_policy=ProposalPolicy(auto_approve_threshold=0.0),
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"paper_lab": mocks["trader"]},
    )
    proposal = make_proposal(composite=0.1).model_copy(
        update={"sub_account_id": "paper_lab"}
    )

    decision = await engine._auto_decide(proposal)

    assert decision.accepted is True


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


async def test_run_cycle_runtime_safety_pause_blocks_accepted_fill(
    tmp_path: Path,
) -> None:
    btc = make_proposal(proposal_id="btc-safety", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=btc,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            runtime_safety_pause_min_score=90,
        ),
    )
    mocks["activity_log"].append(
        ActivityEventType.CYCLE_ERRORED,
        "prior cycle failed",
        cycle_id="prior-cycle",
    )

    result = await engine.run_cycle()

    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 1
    assert result.positions_opened == 0
    mocks["trader"].open_position.assert_not_called()
    record = mocks["history"].load("btc-safety")
    assert record.decision == ProposalDecision.REJECTED.value
    assert "runtime safety score" in (record.rejection_reason or "")
    rejected = mocks["activity_log"].filter(
        event_type=ActivityEventType.PROPOSAL_REJECTED
    )
    assert any(
        event.details.get("runtime_safety_pause_min_score") == 90 for event in rejected
    )


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


async def test_run_cycle_fans_out_per_active_sub_account(tmp_path: Path) -> None:
    """Phase 19.2: each active sub-account gets its own scan and trader."""
    exchange = AsyncMock(spec=BaseExchange)
    exchange.get_ticker.return_value = Ticker(
        symbol="BTC/USDT",
        price=Decimal("50000"),
        timestamp=now_utc(),
    )

    proposal_engine = MagicMock(spec=ProposalEngine)
    proposal_engine.strategies = {}

    async def propose_bitcoin(**kwargs: object) -> Proposal:
        return make_proposal(proposal_id=f"p-{kwargs['sub_account_id']}").model_copy(
            update={"sub_account_id": kwargs["sub_account_id"]}
        )

    proposal_engine.propose_bitcoin = AsyncMock(side_effect=propose_bitcoin)
    proposal_engine.propose_altcoins = AsyncMock(return_value=[])

    history = ProposalHistory(data_dir=tmp_path / "proposals")
    interaction = ProposalInteraction(history=history)
    trader_a = make_mock_trader()
    trader_b = make_mock_trader()
    registry = FakeSubAccountRegistry(
        [
            SubAccount(
                id="alpha",
                name="Alpha",
                mode="paper",
                exchange_ref="default",
                initial_balance={"USDT": Decimal("10000")},
            ),
            SubAccount(
                id="beta",
                name="Beta",
                mode="paper",
                exchange_ref="default",
                initial_balance={"USDT": Decimal("10000")},
            ),
        ],
        {"alpha": trader_a, "beta": trader_b},
    )
    notification_dispatcher = MagicMock(spec=NotificationDispatcher)
    notification_dispatcher.notify_proposal = AsyncMock(return_value=None)

    engine = TradingEngine(
        exchange=exchange,
        proposal_engine=proposal_engine,
        proposal_interaction=interaction,
        proposal_history=history,
        trader=trader_a,
        registry=registry,  # type: ignore[arg-type]
        notification_dispatcher=notification_dispatcher,
        activity_log=ActivityLog(path=tmp_path / "activity.jsonl"),
        config=EngineConfig(auto_approve_threshold=1.0),
    )

    result = await engine.run_cycle()

    assert result.proposals_generated == 2
    assert trader_a.open_position.await_count == 1
    assert trader_b.open_position.await_count == 1
    assert proposal_engine.propose_bitcoin.await_count == 2
    assert {
        c.kwargs["sub_account_id"]
        for c in proposal_engine.propose_bitcoin.await_args_list
    } == {"alpha", "beta"}
    assert {r.sub_account_id for r in history.list_all()} == {"alpha", "beta"}


def test_engine_rejects_non_default_exchange_ref_until_router_exists(
    tmp_path: Path,
) -> None:
    engine, mocks = build_engine(tmp_path=tmp_path)
    sub = SubAccount(
        id="alt",
        name="Alt",
        mode="paper",
        exchange_ref="bybit_alt",
        initial_balance={"USDT": Decimal("10000")},
    )
    registry = FakeSubAccountRegistry([sub], {"alt": mocks["trader"]})

    with pytest.raises(RuntimeError, match="exchange refs"):
        TradingEngine(
            exchange=mocks["exchange"],
            proposal_engine=mocks["proposal_engine"],
            proposal_interaction=mocks["interaction"],
            proposal_history=mocks["history"],
            trader=mocks["trader"],
            registry=registry,  # type: ignore[arg-type]
            notification_dispatcher=mocks["notification_dispatcher"],
            activity_log=mocks["activity_log"],
            config=EngineConfig(auto_approve_threshold=1.0),
        )


async def test_run_cycle_threads_sub_account_risk_override(tmp_path: Path) -> None:
    """Risk override is passed to ProposalEngine per sub-account."""
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=make_proposal(proposal_id="alpha-proposal"),
    )
    sub = SubAccount(
        id="alpha",
        name="Alpha",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
        risk_overrides=RiskOverrides(risk_percent=Decimal("0.25"), leverage_cap=2),
    )
    registry = FakeSubAccountRegistry([sub], {"alpha": mocks["trader"]})
    engine.sub_account_registry = registry  # type: ignore[assignment]
    mocks["proposal_engine"].strategies = {}
    mocks["proposal_engine"].config = MagicMock(leverage=5)

    async def propose_bitcoin(**kwargs: object) -> Proposal:
        return make_proposal(proposal_id="alpha-proposal").model_copy(
            update={"sub_account_id": kwargs["sub_account_id"]}
        )

    mocks["proposal_engine"].propose_bitcoin.side_effect = propose_bitcoin

    await engine.run_cycle()

    call = mocks["proposal_engine"].propose_bitcoin.await_args
    assert call.kwargs["sub_account_id"] == "alpha"
    assert call.kwargs["risk_percent"] == 0.25
    assert call.kwargs["leverage"] == 2


async def test_run_cycle_threads_sub_account_strategy_filter(tmp_path: Path) -> None:
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=make_proposal(proposal_id="alpha-proposal"),
    )
    sub = SubAccount(
        id="alpha",
        name="Alpha",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
        strategy_filter=["alpha_only"],
    )
    registry = FakeSubAccountRegistry([sub], {"alpha": mocks["trader"]})
    engine.sub_account_registry = registry  # type: ignore[assignment]
    alpha_strategy = MagicMock()
    alpha_strategy.info.name = "alpha_only"
    beta_strategy = MagicMock()
    beta_strategy.info.name = "beta_only"
    mocks["proposal_engine"].strategies = {
        "alpha_only": alpha_strategy,
        "beta_only": beta_strategy,
    }

    await engine.run_cycle()

    btc_call = mocks["proposal_engine"].propose_bitcoin.await_args
    alt_call = mocks["proposal_engine"].propose_altcoins.await_args
    assert btc_call.kwargs["strategies"] == [alpha_strategy]
    assert alt_call.kwargs["strategies"] == [alpha_strategy]


async def test_run_cycle_threads_account_policy_scan_scope(
    tmp_path: Path,
) -> None:
    """Account policy can override scan symbols, top-k, sizing balance, and risk."""
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=make_proposal(proposal_id="alpha-btc"),
        altcoin_proposals=[],
        config=EngineConfig(
            bitcoin_symbol="BTC/USDT",
            altcoin_symbols=["ETH/USDT"],
            altcoin_top_k=1,
            balance=Decimal("10000"),
        ),
    )
    sub = SubAccount(
        id="alpha",
        name="Alpha",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
        capital_policy=CapitalPolicy(sizing_balance=Decimal("2500")),
        strategy_policy=StrategyPolicy(
            bitcoin_symbol="SOL/USDT",
            symbols=["XRP/USDT", "DOGE/USDT"],
            top_k=2,
        ),
        risk_policy=RiskPolicy(risk_percent=Decimal("0.5")),
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"alpha": mocks["trader"]},
    )
    mocks["proposal_engine"].strategies = {}

    async def propose_bitcoin(**kwargs: object) -> Proposal:
        return make_proposal(
            proposal_id="alpha-btc",
            symbol=str(kwargs["symbol"]),
        ).model_copy(update={"sub_account_id": kwargs["sub_account_id"]})

    mocks["proposal_engine"].propose_bitcoin.side_effect = propose_bitcoin

    await engine.run_cycle()

    btc_call = mocks["proposal_engine"].propose_bitcoin.await_args
    alt_call = mocks["proposal_engine"].propose_altcoins.await_args
    assert btc_call.kwargs["symbol"] == "SOL/USDT"
    assert btc_call.kwargs["balance"] == Decimal("2500")
    assert btc_call.kwargs["risk_percent"] == 0.5
    assert alt_call.kwargs["symbols"] == ["XRP/USDT", "DOGE/USDT"]
    assert alt_call.kwargs["balance"] == Decimal("2500")
    assert alt_call.kwargs["top_k"] == 2


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


async def test_monitor_pass_uses_sub_account_trader_for_exit_check(
    tmp_path: Path,
) -> None:
    """Non-default accounts must evaluate exits against their own trader state."""
    open_trade = make_trade(trade_id="beta-open")
    closed_trade = make_trade(
        trade_id="beta-open",
        exit_price="51500",
        pnl_percent=3.0,
        status="closed",
    )
    default_trader = make_mock_trader()
    beta_trader = make_mock_trader()
    beta_trader.get_open_trades.return_value = [open_trade]
    default_trader.check_exit_conditions.return_value = (False, None)
    beta_trader.check_exit_conditions.return_value = (True, "take_profit")
    beta_trader.close_position.return_value = closed_trade

    sub = SubAccount(
        id="beta",
        name="Beta",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
    )
    registry = FakeSubAccountRegistry([sub], {"beta": beta_trader})
    engine, mocks = build_engine(tmp_path=tmp_path, open_trades=[])
    mocks["proposal_engine"].strategies = {}
    engine.sub_account_registry = registry  # type: ignore[assignment]
    engine.trader = default_trader

    result = await engine.run_cycle()

    assert result.positions_closed == 1
    default_trader.check_exit_conditions.assert_not_called()
    beta_trader.check_exit_conditions.assert_called_once_with(
        "beta-open",
        Decimal("50000"),
    )
    beta_trader.close_position.assert_awaited_once_with(
        "beta-open",
        Decimal("50000"),
        reason="take_profit",
    )
    closed = mocks["activity_log"].filter(event_type=ActivityEventType.POSITION_CLOSED)
    assert len(closed) == 1


async def test_monitor_pass_surfaces_orphan_open_trade_state(
    tmp_path: Path,
) -> None:
    open_trade = make_trade(trade_id="orphan")
    engine, mocks = build_engine(tmp_path=tmp_path, open_trades=[open_trade])
    mocks["trader"].get_open_position.return_value = None

    result = await engine.run_cycle()

    assert result.positions_closed == 0
    assert result.errors == ["orphan_open_trade:orphan"]
    mocks["exchange"].get_ticker.assert_not_awaited()
    errors = mocks["activity_log"].filter(event_type=ActivityEventType.MONITOR_ERRORED)
    assert len(errors) == 1
    assert errors[0].details["trade_id"] == "orphan"


def test_closed_trade_performance_record_uses_trade_sub_account_path(
    tmp_path: Path,
) -> None:
    engine, mocks = build_engine(tmp_path=tmp_path)
    tracker = PerformanceTracker(data_dir=tmp_path / "performance")
    mocks["proposal_engine"].performance_tracker = tracker
    proposal = make_proposal(proposal_id="p-beta").model_copy(
        update={"sub_account_id": "beta"}
    )
    record = ProposalRecord(proposal=proposal, decision=ProposalDecision.ACCEPTED)
    closed_trade = make_trade(
        trade_id="beta-closed",
        exit_price="51500",
        pnl_percent=3.0,
        status="closed",
    ).model_copy(update={"sub_account_id": "beta"})

    engine._save_performance_record(record, closed_trade, "take_profit")

    assert (
        tmp_path / "performance" / "beta" / proposal.technique_name / "records.json"
    ).exists()
    assert not (
        tmp_path / "performance" / "default" / proposal.technique_name / "records.json"
    ).exists()


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

    record = mocks["history"].load("bnb-2")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason is not None
    assert "cap 1 reached" in record.rejection_reason

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


async def test_notification_receives_runtime_safety_score(tmp_path: Path) -> None:
    proposal = make_proposal(proposal_id="safety-notify", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )

    await engine.run_cycle()

    kwargs = mocks["notification_dispatcher"].notify_proposal.await_args.kwargs
    assert kwargs["safety_score"].score <= 100


async def test_correlation_warning_is_advisory_by_default(tmp_path: Path) -> None:
    existing_trade = make_trade(
        trade_id="t-btc-existing",
        symbol="BTC/USDT",
        side="long",
    ).model_copy(update={"sub_account_id": "alpha"})
    proposal = make_proposal(proposal_id="btc-dup", composite=2.0).model_copy(
        update={"sub_account_id": "beta"}
    )
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=None,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=2,
        ),
    )
    alpha = SubAccount(
        id="alpha",
        name="Alpha",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
    )
    beta = SubAccount(
        id="beta",
        name="Beta",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
    )
    alpha_trader = make_mock_trader()
    beta_trader = make_mock_trader()
    alpha_trader.get_open_trades.return_value = [existing_trade]
    engine.sub_account_registry = FakeSubAccountRegistry(
        [alpha, beta],
        {"alpha": alpha_trader, "beta": beta_trader},
    )  # type: ignore[assignment]
    mocks["proposal_engine"].strategies = {}

    async def propose_bitcoin(**kwargs: object) -> Proposal | None:
        if kwargs["sub_account_id"] == "alpha":
            return None
        return proposal

    mocks["proposal_engine"].propose_bitcoin.side_effect = propose_bitcoin

    result = await engine.run_cycle()

    assert result.positions_opened == 1
    beta_trader.open_position.assert_awaited_once()
    warnings = mocks["activity_log"].filter(
        event_type=ActivityEventType.CORRELATION_WARNING
    )
    assert len(warnings) == 1
    assert warnings[0].details["gate_enabled"] is False


async def test_correlation_gate_rejects_when_enabled(tmp_path: Path) -> None:
    existing_trade = make_trade(
        trade_id="t-btc-existing",
        symbol="BTC/USDT",
        side="long",
    ).model_copy(update={"sub_account_id": "alpha"})
    proposal = make_proposal(
        proposal_id="btc-corr-reject",
        composite=2.0,
    ).model_copy(update={"sub_account_id": "beta"})
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=None,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=2,
            correlation_gate_enabled=True,
        ),
    )
    alpha = SubAccount(
        id="alpha",
        name="Alpha",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
    )
    beta = SubAccount(
        id="beta",
        name="Beta",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
    )
    alpha_trader = make_mock_trader()
    beta_trader = make_mock_trader()
    alpha_trader.get_open_trades.return_value = [existing_trade]
    engine.sub_account_registry = FakeSubAccountRegistry(
        [alpha, beta],
        {"alpha": alpha_trader, "beta": beta_trader},
    )  # type: ignore[assignment]
    mocks["proposal_engine"].strategies = {}

    async def propose_bitcoin(**kwargs: object) -> Proposal | None:
        if kwargs["sub_account_id"] == "alpha":
            return None
        return proposal

    mocks["proposal_engine"].propose_bitcoin.side_effect = propose_bitcoin

    result = await engine.run_cycle()

    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 1
    assert result.positions_opened == 0
    beta_trader.open_position.assert_not_called()
    record = mocks["history"].load("btc-corr-reject")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason == (
        "correlation gate rejected excessive duplicate exposure"
    )


async def test_correlation_gate_uses_proposal_history_strategy_lookup(
    tmp_path: Path,
) -> None:
    existing_trade = make_trade(
        trade_id="t-btc-existing",
        symbol="BTC/USDT",
        side="long",
    ).model_copy(update={"sub_account_id": "alpha"})
    existing_proposal = make_proposal(
        proposal_id="btc-existing-proposal",
        composite=2.0,
    ).model_copy(update={"sub_account_id": "alpha"})
    proposal = make_proposal(
        proposal_id="btc-strategy-reject",
        composite=2.0,
    ).model_copy(update={"sub_account_id": "beta"})
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=None,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=2,
            correlation_gate_enabled=True,
            correlation_max_sub_accounts_per_symbol_side=2,
            correlation_max_sub_accounts_per_strategy_symbol_side=1,
        ),
    )
    mocks["history"].save(
        ProposalRecord(
            proposal=existing_proposal,
            decision=ProposalDecision.ACCEPTED,
            trade_id=existing_trade.id,
        )
    )
    alpha = SubAccount(
        id="alpha",
        name="Alpha",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
    )
    beta = SubAccount(
        id="beta",
        name="Beta",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
    )
    alpha_trader = make_mock_trader()
    beta_trader = make_mock_trader()
    alpha_trader.get_open_trades.return_value = [existing_trade]
    engine.sub_account_registry = FakeSubAccountRegistry(
        [alpha, beta],
        {"alpha": alpha_trader, "beta": beta_trader},
    )  # type: ignore[assignment]
    mocks["proposal_engine"].strategies = {}

    async def propose_bitcoin(**kwargs: object) -> Proposal | None:
        if kwargs["sub_account_id"] == "alpha":
            return None
        return proposal

    mocks["proposal_engine"].propose_bitcoin.side_effect = propose_bitcoin

    result = await engine.run_cycle()

    assert result.proposals_rejected == 1
    beta_trader.open_position.assert_not_called()
    warning = mocks["activity_log"].filter(
        event_type=ActivityEventType.CORRELATION_WARNING
    )[0]
    assert warning.details["warnings"][0]["warning_type"] == (
        "duplicate_strategy_symbol_side"
    )
    assert warning.details["warnings"][0]["strategy_id"] == "tech_a"


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

    record = mocks["history"].load("bnb-short-1")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason is not None
    assert "cap 1 reached" in record.rejection_reason

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
    assert result.proposals_accepted == 1
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
    assert details["entry_price"] == "50000"
    assert "proposal_entry" not in details
    assert details["proposal_stop_loss"] == "49500"
    assert details["live_price"] == "49400"
    # drift_bps = |49400 - 50000| / 50000 * 10_000 = 120
    assert details["drift_bps"] == pytest.approx(120.0)


async def test_stale_quote_gate_uses_account_execution_policy(
    tmp_path: Path,
) -> None:
    """Account execution policy can opt a paper lab out of past-SL rejection."""
    proposal = make_proposal(
        proposal_id="paper-lab-stale",
        composite=2.0,
    ).model_copy(update={"sub_account_id": "paper_lab"})
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            reject_if_past_stop_loss=True,
        ),
        ticker_price=Decimal("49400"),
    )
    sub = SubAccount(
        id="paper_lab",
        name="Paper Lab",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
        execution_policy=ExecutionPolicy(
            reject_if_past_stop_loss=False,
            fill_slippage_tolerance=Decimal("1"),
        ),
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"paper_lab": mocks["trader"]},
    )
    mocks["proposal_engine"].strategies = {}

    result = await engine.run_cycle()

    assert result.positions_opened == 1
    assert result.proposals_rejected == 0
    mocks["trader"].open_position.assert_awaited_once()


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
    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 1
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
    assert result.proposals_accepted == 1
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
    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 0
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


# =============================================================================
# Phase 24.1 / DEBT-033: ticker freshness threshold
# =============================================================================


async def test_stale_quote_gate_falls_through_when_ticker_age_exceeds_threshold(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Phase 24.1 / DEBT-033: ticker older than ``max_ticker_age_seconds``
    triggers the same WARN-and-fall-through path as a ticker-fetch
    exception.

    A successfully-fetched but stale ticker is no better than a failed
    fetch for the slippage / past-SL checks: silently using one would
    defeat the gate's purpose. The fix surfaces the staleness via the
    ``stale_quote_check_failed`` marker so the operator can see the
    gate was effectively a no-op for that proposal.

    The test puts the ticker at a clearly-stale timestamp (one hour
    ago) and a price that WOULD have rejected the proposal (past-SL on
    a long: live=49000, SL=49500). The gate must NOT consult that
    price; the fill must proceed.
    """
    import logging
    from datetime import timedelta

    proposal = make_proposal(proposal_id="stale-ticker-1", composite=2.0)
    # One hour old > default max_ticker_age_seconds=10.0.
    stale_ts = now_utc() - timedelta(hours=1)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        # Live below SL would normally reject, but we should never
        # reach the price-comparison branch on a stale ticker.
        ticker_price=Decimal("49000"),
        ticker_timestamp=stale_ts,
    )

    target_logger = logging.getLogger("crypto_master.runtime.engine")
    target_logger.addHandler(caplog.handler)
    previous_level = target_logger.level
    target_logger.setLevel(logging.WARNING)
    try:
        result = await engine.run_cycle()
    finally:
        target_logger.removeHandler(caplog.handler)
        target_logger.setLevel(previous_level)

    # Fall-through behavior: fill proceeded, no rejection.
    assert result.positions_opened == 1
    assert result.proposals_rejected == 0
    mocks["trader"].open_position.assert_called_once()
    record = mocks["history"].load("stale-ticker-1")
    assert record.decision == ProposalDecision.ACCEPTED.value

    # WARN log carries the marker + the stale-ticker error_type tag.
    warn_messages = [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and "stale_quote_check_failed" in r.getMessage()
    ]
    assert len(warn_messages) == 1
    msg = warn_messages[0]
    assert "BTC/USDT" in msg
    assert "stale-ticker-1" in msg
    assert "stale_ticker" in msg


async def test_stale_quote_gate_uses_fresh_ticker_when_within_threshold(
    tmp_path: Path,
) -> None:
    """Phase 24.1 / DEBT-033: a ticker within
    ``max_ticker_age_seconds`` is considered fresh; the gate's
    slippage / past-SL checks run normally.

    Pinned regression: a ticker timestamped two seconds ago (well
    inside the 10-second default) must NOT short-circuit the gate.
    Past-SL ticker → past-SL rejection.
    """
    from datetime import timedelta

    proposal = make_proposal(proposal_id="fresh-ticker-1", composite=2.0)
    fresh_ts = now_utc() - timedelta(seconds=2)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        ticker_price=Decimal("49000"),  # past SL=49500 on a long
        ticker_timestamp=fresh_ts,
    )

    result = await engine.run_cycle()

    # Fresh ticker → past-SL rejection fires, fill blocked.
    assert result.positions_opened == 0
    assert result.proposals_rejected == 1
    mocks["trader"].open_position.assert_not_called()
    record = mocks["history"].load("fresh-ticker-1")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason == "stale_quote_past_sl"


# =============================================================================
# Phase 24.2 / DEBT-033 follow-up: opt-in reject_if_stale_quote
# =============================================================================


async def test_reject_if_stale_quote_true_blocks_fill_on_stale_ticker(
    tmp_path: Path,
) -> None:
    """When ``reject_if_stale_quote=True``, a stale ticker triggers a
    hard rejection with reason ``stale_quote_no_live_data`` instead of
    falling through to the fill.

    The audit's original concern: fall-through fills proceed at
    ``proposal.entry_price`` with no live cross-check. The opt-in
    reject path closes that hole for live mode without changing the
    default (paper-mode-friendly) behaviour.
    """
    from datetime import timedelta

    proposal = make_proposal(proposal_id="reject-stale-1", composite=2.0)
    # One hour old > default max_ticker_age_seconds=10.0.
    stale_ts = now_utc() - timedelta(hours=1)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            reject_if_stale_quote=True,
        ),
        # Live below SL would normally reject via past-SL gate, but
        # the freshness check fires first on a stale ticker.
        ticker_price=Decimal("49000"),
        ticker_timestamp=stale_ts,
    )

    result = await engine.run_cycle()

    # Hard rejection: no fill, reason is the new no-live-data marker.
    assert result.positions_opened == 0
    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 1
    mocks["trader"].open_position.assert_not_called()
    record = mocks["history"].load("reject-stale-1")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason == "stale_quote_no_live_data"


async def test_reject_if_stale_quote_false_preserves_fall_through_warn(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When ``reject_if_stale_quote=False`` (default), the existing
    WARN-and-fall-through behaviour is preserved on a stale ticker.

    Pin the back-compat path. The fix must not silently break paper-
    mode deployments that rely on fall-through to keep trading during
    transient ticker staleness.
    """
    import logging
    from datetime import timedelta

    proposal = make_proposal(proposal_id="fall-through-1", composite=2.0)
    stale_ts = now_utc() - timedelta(hours=1)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        # Default reject_if_stale_quote=False; stated explicitly to
        # make the contract obvious to readers.
        config=EngineConfig(
            auto_approve_threshold=1.0,
            reject_if_stale_quote=False,
        ),
        ticker_price=Decimal("49000"),
        ticker_timestamp=stale_ts,
    )

    target_logger = logging.getLogger("crypto_master.runtime.engine")
    target_logger.addHandler(caplog.handler)
    previous_level = target_logger.level
    target_logger.setLevel(logging.WARNING)
    try:
        result = await engine.run_cycle()
    finally:
        target_logger.removeHandler(caplog.handler)
        target_logger.setLevel(previous_level)

    # Fall-through: fill proceeded at proposal.entry_price.
    assert result.positions_opened == 1
    assert result.proposals_rejected == 0
    mocks["trader"].open_position.assert_called_once()
    record = mocks["history"].load("fall-through-1")
    assert record.decision == ProposalDecision.ACCEPTED.value

    # WARN log carries the stale-ticker marker so operators can see
    # the gate was effectively a no-op for that proposal.
    warn_messages = [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and "stale_quote_check_failed" in r.getMessage()
    ]
    assert len(warn_messages) == 1
    assert "stale_ticker" in warn_messages[0]


async def test_reject_if_stale_quote_true_blocks_fill_on_ticker_fetch_error(
    tmp_path: Path,
) -> None:
    """When ``reject_if_stale_quote=True``, a ticker fetch failure also
    triggers the hard rejection (no live data ≡ stale quote for the
    purpose of the cross-check).

    The two paths share the same opt-in safety: if the gate cannot
    consult a live tape, the fill is blocked rather than falling
    through to ``proposal.entry_price``.
    """
    proposal = make_proposal(proposal_id="reject-fetch-fail-1", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            reject_if_stale_quote=True,
        ),
        ticker_error=ExchangeAPIError("transient outage"),
    )

    result = await engine.run_cycle()

    assert result.positions_opened == 0
    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 1
    mocks["trader"].open_position.assert_not_called()
    record = mocks["history"].load("reject-fetch-fail-1")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason == "stale_quote_no_live_data"


# =============================================================================
# Phase 21.3: Stale-Quote Payload Timestamp Coherence (DEBT-025)
# =============================================================================
#
# These tests pin the contract documented on
# ``TradingEngine._record_stale_quote_rejection``: every ``datetime`` that
# participates in the rejection payload is UTC-aware.
#
# Sources verified:
#   * ``ProposalRecord.decision_at``  → ``now_utc()`` (engine.py)
#   * ``ProposalRecord.proposal.created_at`` → ``Proposal`` validator
#   * ``ActivityEvent.timestamp``     → ``now_utc()`` + validator
#   * ``ticker.timestamp``            → adapter ``from_unix_ms`` (Phase 21.1)


async def test_stale_quote_rejection_payload_timestamps_are_utc_aware(
    tmp_path: Path,
) -> None:
    """Every datetime in the persisted rejection record is UTC-aware.

    Coherence test for Phase 21.3 / DEBT-025: assert ``decision_at`` and
    ``proposal.created_at`` on the overwritten ``ProposalRecord`` carry
    ``tzinfo == timezone.utc``, and the ``PROPOSAL_REJECTED``
    ``ActivityEvent.timestamp`` does too.
    """
    from datetime import timezone

    proposal = make_proposal(proposal_id="utc-coherence-1", composite=2.0)
    # Sanity: the proposal's own ``created_at`` is UTC-aware out of the
    # box (default_factory=now_utc + _coerce_created_at_to_utc validator).
    assert proposal.created_at.tzinfo == timezone.utc

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        ticker_price=Decimal("49400"),  # past SL → stale-quote rejection
    )

    await engine.run_cycle()

    # ProposalRecord fields are aware.
    record = mocks["history"].load("utc-coherence-1")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.decision_at is not None
    assert record.decision_at.tzinfo == timezone.utc
    assert record.proposal.created_at.tzinfo == timezone.utc

    # The PROPOSAL_REJECTED ActivityEvent timestamp is aware too.
    rejections = mocks["activity_log"].filter(
        event_type=ActivityEventType.PROPOSAL_REJECTED
    )
    assert len(rejections) == 1
    assert rejections[0].timestamp.tzinfo == timezone.utc


async def test_stale_quote_rejection_decision_at_minus_candle_ts_is_aware_math(
    tmp_path: Path,
) -> None:
    """``decision_at`` (engine) and ``ticker.timestamp`` (adapter) are
    aware-comparable.

    Cross-source test for Phase 21.3: confirm the engine-side clock and
    the adapter-side candle clock are both UTC-aware so timedelta math
    between them does not raise ``TypeError``. This is the regression
    surface that catches a future regression of either side back to
    naive datetimes.
    """
    from datetime import timezone

    from src.utils.time import from_unix_ms

    proposal = make_proposal(proposal_id="utc-cross-1", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        ticker_price=Decimal("49400"),
    )

    # Override the default fixture ticker with an adapter-shaped one
    # (``from_unix_ms`` is the canonical Phase 21.1 UTC-aware source).
    # Phase 24.1 / DEBT-033: timestamp must stay within
    # ``max_ticker_age_seconds`` so the freshness gate passes and the
    # past-SL rejection is the path under test. Using a millisecond
    # epoch derived from ``now_utc()`` keeps the cross-source
    # aware-comparability assertion that this test cares about.
    now = now_utc()
    aware_ts = from_unix_ms(int(now.timestamp() * 1000))
    assert aware_ts.tzinfo == timezone.utc
    mocks["exchange"].get_ticker.return_value = Ticker(
        symbol="BTC/USDT",
        price=Decimal("49400"),
        timestamp=aware_ts,
    )

    await engine.run_cycle()

    record = mocks["history"].load("utc-cross-1")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.decision_at is not None
    assert record.decision_at.tzinfo == timezone.utc

    # Aware-vs-aware subtraction works (regression: a naive value on
    # either side would raise ``TypeError: can't subtract offset-naive
    # and offset-aware datetimes``).
    delta = record.decision_at - aware_ts
    assert delta.total_seconds() >= 0  # decision happened after the quote


async def test_stale_quote_rejection_tolerates_legacy_naive_record_on_disk(
    tmp_path: Path,
) -> None:
    """Pre-21.1 records with naive ``created_at`` don't crash the rewrite.

    Legacy-tolerance test for Phase 21.3: a proposal record persisted
    before the 21.x sweep carries a naive ``created_at`` on disk. When
    the stale-quote gate overwrites that record with REJECTED, the
    ``Proposal._coerce_created_at_to_utc`` validator must coerce the
    naive value to UTC at the read boundary so ``decision_at - created_at``
    style comparisons (engine-side or downstream) stay aware-vs-aware.
    """
    import json
    from datetime import timezone

    proposal = make_proposal(proposal_id="legacy-1", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        ticker_price=Decimal("49400"),
    )

    # Pre-seed a legacy ProposalRecord on disk with a NAIVE created_at,
    # mirroring what a pre-Phase-21.1 deployment would have written. We
    # bypass ``ProposalHistory.save`` (which round-trips through Pydantic
    # and would coerce on construction) and write the raw JSON directly.
    history = mocks["history"]
    history.data_dir.mkdir(parents=True, exist_ok=True)
    legacy_path = history.data_dir / "legacy-1.json"
    legacy_payload = {
        "proposal": {
            "proposal_id": "legacy-1",
            # Naive timestamp string — no offset suffix, mimics legacy
            # data on disk before Phase 21.2's UTC coercion landed.
            "created_at": "2026-04-01T00:00:00",
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "technique_name": "tech_a",
            "technique_version": "1.0.0",
            "profile_name": None,
            "signal": "long",
            "entry_price": "50000",
            "stop_loss": "49500",
            "take_profit": "51500",
            "quantity": "0.1",
            "leverage": 1,
            "risk_reward_ratio": 3.0,
            "score": {
                "confidence": 0.8,
                "win_rate": 0.6,
                "sample_size": 25,
                "expected_value": 2.0,
                "sample_factor": 1.0,
                "edge_factor": 2.0,
                "composite": 2.0,
            },
            "reasoning": "legacy",
        },
        "decision": "accepted",
        # Naive decision_at on the legacy record too.
        "decision_at": "2026-04-01T00:00:01",
        "actor": "auto",
        "rejection_reason": None,
        "trade_id": None,
        "outcome_pnl_percent": None,
        "outcome_recorded_at": None,
    }
    legacy_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    # The cycle must complete without raising — the gate's overwrite
    # path loads the legacy record, applies model_copy, and saves. With
    # a naive ``created_at`` on disk, a future regression of the
    # validator would either persist naive or raise on aware-vs-naive
    # comparison downstream.
    await engine.run_cycle()

    # The record was overwritten as REJECTED, and the validator coerced
    # the naive ``created_at`` to UTC on read.
    rewritten = history.load("legacy-1")
    assert rewritten.decision == ProposalDecision.REJECTED.value
    assert rewritten.rejection_reason == "stale_quote_past_sl"
    assert rewritten.proposal.created_at.tzinfo == timezone.utc
    assert rewritten.decision_at is not None
    assert rewritten.decision_at.tzinfo == timezone.utc


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


# =============================================================================
# Phase 26.3 / DEBT-038: notifier failure visibility
# =============================================================================


async def test_notifier_failure_emits_notification_failed_event(
    tmp_path: Path,
) -> None:
    """When the dispatcher call raises, the engine emits NOTIFICATION_FAILED
    with the structured payload and continues the cycle (emit-then-swallow).

    Pins the Phase 26.3 / DEBT-038 contract: the dispatcher already
    isolates per-notifier failures internally, but if the dispatcher
    call itself raises we surface a single ``NOTIFICATION_FAILED``
    activity event so operators see the failure in the dashboard.
    """
    btc = make_proposal(proposal_id="btc-notify-fail", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=btc,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    # Dispatcher itself raises (not a per-notifier failure — that's
    # already isolated inside NotificationDispatcher).
    mocks["notification_dispatcher"].notify_proposal = AsyncMock(
        side_effect=RuntimeError("dispatcher exploded")
    )

    result = await engine.run_cycle()

    # Cycle still completes; the proposal still moves through the
    # accept + open path (emit-then-swallow policy preserves existing
    # behaviour).
    assert result.proposals_generated == 1
    assert result.proposals_accepted == 1
    assert result.positions_opened == 1

    failed = mocks["activity_log"].filter(
        event_type=ActivityEventType.NOTIFICATION_FAILED
    )
    assert len(failed) == 1
    event = failed[0]
    assert event.cycle_id == result.cycle_id
    # Structured payload contract — pinned per the Phase 26.3 docstring.
    assert event.details["proposal_id"] == "btc-notify-fail"
    assert event.details["symbol"] == "BTC/USDT"
    assert event.details["dispatcher_name"] == "MagicMock"
    assert event.details["error_type"] == "RuntimeError"
    assert event.details["error_message"] == "dispatcher exploded"


# =============================================================================
# CH-03: per-sub-account cycle isolation + per-notifier failure visibility
# =============================================================================


async def test_cycle_continues_after_one_sub_account_raises(
    tmp_path: Path,
) -> None:
    """One sub-account exception must not skip scan/monitor for later accounts (CH-03).

    Before this slice, ``run_cycle`` had no per-account guard; an
    exception inside any sub-account block (registry mismatch, trader
    bug, snapshot crash) propagated up and skipped scan, monitor, and
    snapshot for every later sub-account. The outer guard at
    ``_run_one_cycle_with_guard`` only catches at cycle granularity.
    """
    exchange = AsyncMock(spec=BaseExchange)
    exchange.get_ticker.return_value = Ticker(
        symbol="BTC/USDT", price=Decimal("50000"), timestamp=now_utc()
    )
    proposal_engine = MagicMock(spec=ProposalEngine)
    proposal_engine.strategies = {}
    proposal_engine.propose_altcoins = AsyncMock(return_value=[])

    boom = RuntimeError("alpha trader exploded")
    call_log: list[str] = []

    async def propose_bitcoin(**kwargs: object) -> Proposal:
        sub_id = str(kwargs.get("sub_account_id"))
        call_log.append(sub_id)
        if sub_id == "alpha":
            raise boom
        return make_proposal(proposal_id=f"btc-iso-{sub_id}", composite=2.0).model_copy(
            update={"sub_account_id": sub_id}
        )

    proposal_engine.propose_bitcoin = AsyncMock(side_effect=propose_bitcoin)

    history = ProposalHistory(data_dir=tmp_path / "proposals")
    interaction = ProposalInteraction(history=history)
    trader_alpha = make_mock_trader()
    trader_beta = make_mock_trader()
    registry = FakeSubAccountRegistry(
        [
            SubAccount(
                id="alpha",
                name="Alpha",
                mode="paper",
                exchange_ref="default",
                initial_balance={"USDT": Decimal("10000")},
            ),
            SubAccount(
                id="beta",
                name="Beta",
                mode="paper",
                exchange_ref="default",
                initial_balance={"USDT": Decimal("10000")},
            ),
        ],
        {"alpha": trader_alpha, "beta": trader_beta},
    )
    notification_dispatcher = MagicMock(spec=NotificationDispatcher)
    notification_dispatcher.notify_proposal = AsyncMock(return_value=None)
    activity_log = ActivityLog(path=tmp_path / "activity.jsonl")

    engine = TradingEngine(
        exchange=exchange,
        proposal_engine=proposal_engine,
        proposal_interaction=interaction,
        proposal_history=history,
        trader=trader_alpha,
        registry=registry,  # type: ignore[arg-type]
        notification_dispatcher=notification_dispatcher,
        activity_log=activity_log,
        config=EngineConfig(auto_approve_threshold=1.0),
    )

    result = await engine.run_cycle()

    # Both accounts attempted scan.
    assert "alpha" in call_log and "beta" in call_log
    # Beta still proposed + opened despite alpha raising.
    assert trader_beta.open_position.await_count == 1
    assert trader_alpha.open_position.await_count == 0
    # Errors recorded against the cycle result.
    assert any("sub_account[alpha]" in err for err in result.errors)
    # Activity event emitted with the failing sub-account tagged.
    cycle_errored = activity_log.filter(event_type=ActivityEventType.CYCLE_ERRORED)
    assert any(
        event.details.get("sub_account_id") == "alpha"
        and event.details.get("error_type") == "RuntimeError"
        for event in cycle_errored
    )


async def test_engine_wires_per_notifier_failure_callback(tmp_path: Path) -> None:
    """Engine attaches its callback to the dispatcher (CH-03).

    The dispatcher already has per-backend failure isolation, but
    without a callback those failures are only ``logger.warning``-d.
    The engine wires a callback at construction time so per-backend
    failures emit NOTIFICATION_FAILED activity events tagged with
    the notifier class name and feed ``recent_notification_failures``
    in the runtime safety score.
    """
    activity_log = ActivityLog(path=tmp_path / "activity.jsonl")
    real_dispatcher = NotificationDispatcher(notifiers=[])
    assert real_dispatcher._on_notifier_failure is None

    history = ProposalHistory(data_dir=tmp_path / "proposals")
    interaction = ProposalInteraction(history=history)
    trader = make_mock_trader()

    engine = TradingEngine(
        exchange=AsyncMock(spec=BaseExchange),
        proposal_engine=MagicMock(spec=ProposalEngine),
        proposal_interaction=interaction,
        proposal_history=history,
        trader=trader,
        notification_dispatcher=real_dispatcher,
        activity_log=activity_log,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    del engine  # construction is what wires the callback

    assert real_dispatcher._on_notifier_failure is not None

    # Invoke the callback as the dispatcher would on a per-notifier
    # failure and assert the activity event lands with the structured
    # payload that consumers (safety score, dashboard) expect.
    proposal = make_proposal(proposal_id="btc-notif", composite=2.0)
    notification = Notification(
        level=NotificationLevel.GOOD_OPPORTUNITY,
        proposal=proposal,
        message="boom",
        safety_score=None,
    )
    real_dispatcher._on_notifier_failure(
        "SlackNotifier", notification, RuntimeError("slack 503")
    )
    failed = activity_log.filter(event_type=ActivityEventType.NOTIFICATION_FAILED)
    assert len(failed) == 1
    event = failed[0]
    assert event.details["notifier_name"] == "SlackNotifier"
    assert event.details["proposal_id"] == "btc-notif"
    assert event.details["symbol"] == "BTC/USDT"
    assert event.details["error_type"] == "RuntimeError"
    assert event.details["error_message"] == "slack 503"

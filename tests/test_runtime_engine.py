"""Tests for the trading engine runtime (Phase 8.1)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exchange.base import BaseExchange, ExchangeAPIError
from src.models import OHLCV, AnalysisResult, Ticker
from src.proposal.engine import Proposal, ProposalEngine, ProposalScore
from src.proposal.interaction import (
    ProposalDecision,
    ProposalFinalState,
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
    ORPHAN_AUTO_CLOSE_THRESHOLD,
    EngineConfig,
    EngineError,
    ErrorCategory,
    GateDecision,
    PolicyResolver,
    TradingEngine,
)
from src.runtime.reconciliation import OpenTradeState
from src.strategy.base import BaseStrategy, TechniqueInfo
from src.strategy.performance import (
    PerformanceTracker,
    TradeHistory,
    TradeHistoryTracker,
)
from src.strategy.tuning import (
    StrategyAction,
    StrategyOverride,
    StrategyTuningPolicy,
)
from src.trading.sub_account import (
    CapitalPolicy,
    ExecutionPolicy,
    GlobalRiskPolicy,
    MarketRegimePolicy,
    ProposalPolicy,
    RiskPolicy,
    StrategyPolicy,
    SubAccount,
)
from src.trading.sub_account_registry import DEFAULT_SUB_ACCOUNT_ID
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
    mode: str = "paper",
    exit_time: datetime | None = None,
    pnl: str | None = None,
) -> TradeHistory:
    return TradeHistory(
        id=trade_id,
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        mode=mode,  # type: ignore[arg-type]
        entry_price=Decimal(entry),
        entry_quantity=Decimal(quantity),
        entry_time=datetime(2026, 4, 27, 12, 0, 0),
        exit_price=Decimal(exit_price) if exit_price is not None else None,
        exit_quantity=Decimal(quantity) if exit_price is not None else None,
        exit_time=exit_time,
        pnl=Decimal(pnl) if pnl is not None else None,
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
    ticker_timestamp_none: bool = False,
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
        #
        # CAH-01 [BUGFIX]: ``ticker_timestamp_none=True`` produces a
        # ``Ticker.timestamp=None`` (the adapter's missing-timestamp
        # output) so the None-branch of the stale-quote gate can be
        # exercised. It is a distinct flag from ``ticker_timestamp``
        # because ``None`` is already the "use now_utc()" sentinel.
        ts = None if ticker_timestamp_none else (ticker_timestamp or now_utc())
        exchange.get_ticker.return_value = Ticker(
            symbol="BTC/USDT",
            price=ticker_price,
            timestamp=ts,
        )

    proposal_engine = MagicMock(spec=ProposalEngine)
    # Default to an empty strategy registry so the HTF trend filter
    # gate (which looks up ``proposal.technique_name`` in
    # ``proposal_engine.strategies``) treats every test proposal as
    # "unknown strategy → fail open". Tests that exercise the gate
    # itself overwrite this with a real ``{name: BaseStrategy}`` dict.
    proposal_engine.strategies = {}
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
    trader.get_balances = AsyncMock(return_value={"USDT": Decimal("10000")})

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
    def __init__(
        self,
        sub_accounts: list[SubAccount],
        traders: dict[str, MagicMock],
        global_policy: GlobalRiskPolicy | None = None,
    ):
        self.sub_accounts = sub_accounts
        self.traders = traders
        self.filter_calls: list[tuple[str, list[object]]] = []
        self._global_policy = global_policy or GlobalRiskPolicy()

    def list_active(self) -> list[SubAccount]:
        return self.sub_accounts

    def global_risk_policy(self) -> GlobalRiskPolicy:
        return self._global_policy

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


class _FakeTradeTracker:
    """Minimal stand-in for ``TradeHistoryTracker`` used by the daily-loss

    kill-switch tests. The engine accesses closed trades via
    ``trader._trade_tracker.load_trades(self.mode)``; this fake returns the
    configured records regardless of mode, mirroring the per-account /
    mode-scoped tracker's list API without touching disk.
    """

    def __init__(self, trades: list[TradeHistory]):
        self._trades = trades

    def load_trades(self, mode: str | None = None) -> list[TradeHistory]:
        return list(self._trades)


def _attach_closed_trades(trader: MagicMock, trades: list[TradeHistory]) -> None:
    """Wire a fake trade tracker onto a mock trader for daily-loss tests.

    Without this, ``getattr(trader, "_trade_tracker", None)`` on a bare
    ``MagicMock`` returns an auto-child mock whose ``load_trades`` is not
    iterable. Setting an explicit tracker makes ``_realized_pnl_today``
    see the configured closed trades.
    """
    trader._trade_tracker = _FakeTradeTracker(trades)


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
        capital_policy=CapitalPolicy(initial_balance={"USDT": Decimal("10000")}),
        proposal_policy=ProposalPolicy(auto_approve_threshold=2.0),
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


async def test_engine_routes_non_default_exchange_ref_to_account_exchange(
    tmp_path: Path,
) -> None:
    engine, mocks = build_engine(tmp_path=tmp_path)
    account_exchange = AsyncMock(spec=BaseExchange)
    account_exchange.get_ticker.return_value = Ticker(
        symbol="BTC/USDT",
        price=Decimal("50000"),
        timestamp=now_utc(),
    )
    account_trader = make_mock_trader()
    account_trader.exchange = account_exchange
    sub = SubAccount(
        id="alt",
        name="Alt",
        mode="paper",
        exchange_ref="bybit_alt",
        initial_balance={"USDT": Decimal("10000")},
    )
    registry = FakeSubAccountRegistry([sub], {"alt": account_trader})
    engine.sub_account_registry = registry  # type: ignore[assignment]
    mocks["proposal_engine"].strategies = {}
    mocks["proposal_engine"].exchange = mocks["exchange"]

    async def propose_bitcoin(**kwargs: object) -> Proposal:
        assert mocks["proposal_engine"].exchange is account_exchange
        return make_proposal(proposal_id="alt-proposal").model_copy(
            update={"sub_account_id": kwargs["sub_account_id"]}
        )

    mocks["proposal_engine"].propose_bitcoin.side_effect = propose_bitcoin

    result = await engine.run_cycle()

    assert result.proposals_generated == 1
    assert account_trader.open_position.await_count == 1
    account_exchange.get_ticker.assert_awaited()
    mocks["exchange"].get_ticker.assert_not_awaited()
    assert mocks["proposal_engine"].exchange is mocks["exchange"]


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
        capital_policy=CapitalPolicy(initial_balance={"USDT": Decimal("10000")}),
        risk_policy=RiskPolicy(risk_percent=Decimal("0.25"), leverage_cap=2),
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
    assert result.errors == [
        EngineError(
            category=ErrorCategory.POSITION_STATE,
            symbol="BTC/USDT",
            detail="orphan_open_trade:orphan",
        )
    ]
    assert all(isinstance(error, EngineError) for error in result.errors)
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
# Orphan auto-close watchdog (DEBT-058 follow-up)
# =============================================================================


class TestOrphanAutoClose:
    """Watchdog that force-closes a perpetually orphaned trade.

    The runtime's existing orphan branch fires
    ``MONITOR_ERRORED:orphan_open_trade`` whenever a trade is open in
    the persisted ledger but missing from the trader's in-memory
    ``_open_positions`` map. Without this watchdog the same trade can
    drift indefinitely (the Fly 260h BNB short is the canonical
    case). After ``ORPHAN_AUTO_CLOSE_THRESHOLD`` consecutive strikes
    on the same trade id, the engine force-closes via
    ``Trader.force_close_orphan`` and emits a
    ``POSITION_ORPHAN_FORCE_CLOSED`` activity event.
    """

    async def test_first_orphan_increment_does_not_close(self, tmp_path: Path) -> None:
        """One orphan strike must not trigger force_close_orphan."""
        open_trade = make_trade(trade_id="orphan")
        engine, mocks = build_engine(tmp_path=tmp_path, open_trades=[open_trade])
        mocks["trader"].get_open_position.return_value = None
        mocks["trader"].force_close_orphan = AsyncMock()

        await engine.run_cycle()

        assert engine._orphan_strike_counts == {"orphan": 1}
        mocks["trader"].force_close_orphan.assert_not_awaited()
        force_closed = mocks["activity_log"].filter(
            event_type=ActivityEventType.POSITION_ORPHAN_FORCE_CLOSED
        )
        assert force_closed == []

    async def test_strike_below_threshold_continues(self, tmp_path: Path) -> None:
        """Cycles 1..K-1 increment but never call force_close_orphan."""
        open_trade = make_trade(trade_id="orphan")
        engine, mocks = build_engine(tmp_path=tmp_path, open_trades=[open_trade])
        mocks["trader"].get_open_position.return_value = None
        mocks["trader"].force_close_orphan = AsyncMock()

        for _ in range(ORPHAN_AUTO_CLOSE_THRESHOLD - 1):
            await engine.run_cycle()

        assert engine._orphan_strike_counts == {
            "orphan": ORPHAN_AUTO_CLOSE_THRESHOLD - 1
        }
        mocks["trader"].force_close_orphan.assert_not_awaited()
        # Each cycle still recorded the MONITOR_ERRORED event.
        errors = mocks["activity_log"].filter(
            event_type=ActivityEventType.MONITOR_ERRORED
        )
        assert len(errors) == ORPHAN_AUTO_CLOSE_THRESHOLD - 1

    async def test_strike_threshold_triggers_force_close(self, tmp_path: Path) -> None:
        """Cycle K → force_close_orphan called, event emitted, counter pruned."""
        open_trade = make_trade(trade_id="orphan", side="short", entry="50000")
        engine, mocks = build_engine(
            tmp_path=tmp_path,
            open_trades=[open_trade],
            ticker_price=Decimal("48500"),
        )
        mocks["trader"].get_open_position.return_value = None
        closed = make_trade(
            trade_id="orphan",
            side="short",
            entry="50000",
            exit_price="48500",
            pnl_percent=3.0,
            status="closed",
        )
        mocks["trader"].force_close_orphan = AsyncMock(return_value=closed)

        for _ in range(ORPHAN_AUTO_CLOSE_THRESHOLD):
            await engine.run_cycle()

        mocks["trader"].force_close_orphan.assert_awaited_once_with(
            "orphan", Decimal("48500")
        )
        # Strike count dropped after the watchdog fired.
        assert "orphan" not in engine._orphan_strike_counts

        events = mocks["activity_log"].filter(
            event_type=ActivityEventType.POSITION_ORPHAN_FORCE_CLOSED
        )
        assert len(events) == 1
        details = events[0].details
        assert details["trade_id"] == "orphan"
        assert details["symbol"] == "BTC/USDT"
        assert details["side"] == "short"
        assert details["entry_price"] == "50000"
        assert details["exit_price"] == "48500"
        assert details["pnl_percent"] == 3.0
        assert details["strikes"] == ORPHAN_AUTO_CLOSE_THRESHOLD
        assert details["threshold"] == ORPHAN_AUTO_CLOSE_THRESHOLD

    async def test_strike_count_resets_when_trade_closes(self, tmp_path: Path) -> None:
        """Trade no longer in ``open_trades`` → counter pruned."""
        open_trade = make_trade(trade_id="orphan")
        engine, mocks = build_engine(tmp_path=tmp_path, open_trades=[open_trade])
        mocks["trader"].get_open_position.return_value = None
        mocks["trader"].force_close_orphan = AsyncMock()

        await engine.run_cycle()
        await engine.run_cycle()
        assert engine._orphan_strike_counts == {"orphan": 2}

        # Subsequent monitor pass returns no open trades — the prune
        # step at the top of ``_monitor`` should drop the stale entry.
        mocks["trader"].get_open_trades.return_value = []
        await engine.run_cycle()

        assert engine._orphan_strike_counts == {}

    async def test_strike_count_resets_when_state_recovered(
        self, tmp_path: Path
    ) -> None:
        """Rehydration on a later cycle drops the strike count."""
        open_trade = make_trade(trade_id="orphan")
        engine, mocks = build_engine(tmp_path=tmp_path, open_trades=[open_trade])
        mocks["trader"].get_open_position.return_value = None
        mocks["trader"].force_close_orphan = AsyncMock()

        await engine.run_cycle()
        assert engine._orphan_strike_counts == {"orphan": 1}

        # Simulate rehydration: ``_missing_position_state`` now returns
        # False (the in-memory map carries the position again).
        mocks["trader"].get_open_position.return_value = MagicMock()

        await engine.run_cycle()

        assert engine._orphan_strike_counts == {}
        mocks["trader"].force_close_orphan.assert_not_awaited()

    async def test_orphan_event_details_include_strike_metadata(
        self, tmp_path: Path
    ) -> None:
        """``MONITOR_ERRORED`` payload exposes ``strike_count`` + ``threshold``."""
        open_trade = make_trade(trade_id="orphan")
        engine, mocks = build_engine(tmp_path=tmp_path, open_trades=[open_trade])
        mocks["trader"].get_open_position.return_value = None
        mocks["trader"].force_close_orphan = AsyncMock()

        await engine.run_cycle()

        errors = mocks["activity_log"].filter(
            event_type=ActivityEventType.MONITOR_ERRORED
        )
        assert len(errors) == 1
        details = errors[0].details
        assert details["strike_count"] == 1
        assert details["threshold"] == ORPHAN_AUTO_CLOSE_THRESHOLD
        assert details["trade_id"] == "orphan"

    async def test_force_close_skipped_when_ticker_fetch_fails(
        self, tmp_path: Path
    ) -> None:
        """Threshold reached but ticker fetch fails → strike count survives."""
        open_trade = make_trade(trade_id="orphan")
        engine, mocks = build_engine(
            tmp_path=tmp_path,
            open_trades=[open_trade],
        )
        mocks["trader"].get_open_position.return_value = None
        mocks["trader"].force_close_orphan = AsyncMock()

        # Drive the strike count up to the threshold.
        for _ in range(ORPHAN_AUTO_CLOSE_THRESHOLD - 1):
            await engine.run_cycle()

        # On the threshold cycle, the ticker fetch fails.
        mocks["exchange"].get_ticker.side_effect = ExchangeAPIError("ticker down")
        await engine.run_cycle()

        mocks["trader"].force_close_orphan.assert_not_awaited()
        # Strike count must remain at the threshold so the next cycle
        # retries — the watchdog should not silently drop the trade.
        assert engine._orphan_strike_counts["orphan"] == ORPHAN_AUTO_CLOSE_THRESHOLD
        # A dedicated MONITOR_ERRORED event named the failure phase.
        errors = mocks["activity_log"].filter(
            event_type=ActivityEventType.MONITOR_ERRORED
        )
        ticker_failures = [
            e for e in errors if e.details.get("phase") == "orphan_ticker_fetch_failed"
        ]
        assert len(ticker_failures) == 1


# =============================================================================
# Time-stop gate (per-strategy ``max_bars_held``)
# =============================================================================


class _StubStrategy(BaseStrategy):
    """Minimal BaseStrategy concretion for time-stop tests.

    The runtime only reads ``self.info`` for the time-stop window —
    ``analyze`` is never called from the monitor path — but
    BaseStrategy is abstract, so we satisfy the contract with a
    no-op coroutine.
    """

    async def analyze(  # type: ignore[override]
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
        current_price: Decimal | None = None,
    ) -> AnalysisResult:
        raise AssertionError("Stub strategy must not be invoked from monitor tests")


def _wire_time_stop_proposal(
    history: ProposalHistory,
    *,
    proposal_id: str,
    trade_id: str,
    technique_name: str,
) -> None:
    """Persist a proposal record + link to a trade so the time-stop
    helper's ``_find_proposal_record_for_trade`` returns a hit.
    """
    proposal = make_proposal(proposal_id=proposal_id).model_copy(
        update={"technique_name": technique_name}
    )
    history.save(ProposalRecord(proposal=proposal, decision=ProposalDecision.ACCEPTED))
    history.attach_trade(proposal_id, trade_id=trade_id)


def _make_aged_trade(
    *,
    trade_id: str,
    age_seconds: float,
    technique_name: str = "tech_a",
) -> TradeHistory:
    """Build an open ``TradeHistory`` whose ``entry_time`` is offset.

    ``now_utc()`` minus ``age_seconds`` keeps the trade naturally
    "aged" against the runtime helper's ``now_utc() - trade.entry_time``
    arithmetic without needing to monkeypatch the clock.
    """
    from datetime import timedelta

    return TradeHistory(
        id=trade_id,
        symbol="BTC/USDT",
        side="long",
        mode="paper",
        entry_price=Decimal("50000"),
        entry_quantity=Decimal("0.1"),
        entry_time=now_utc() - timedelta(seconds=age_seconds),
        status="open",
    )


class TestTimeStopGate:
    """Per-strategy time-stop fallback in ``_monitor`` (P0 trading-correctness)."""

    async def test_time_stop_closes_aged_trade_with_default(
        self, tmp_path: Path
    ) -> None:
        """Aged trade with no per-strategy override hits the timeframe default."""
        from src.strategy.base import default_max_bars_held

        # 1h default = 48 bars * 3600s = 172800s; nudge past it.
        age = default_max_bars_held("1h") * 3600 + 60
        open_trade = _make_aged_trade(trade_id="t-aged", age_seconds=age)
        closed_trade = open_trade.model_copy(
            update={
                "status": "closed",
                "exit_price": Decimal("50000"),
                "exit_quantity": Decimal("0.1"),
                "close_reason": "time_stop",
                "pnl_percent": 0.0,
            }
        )

        engine, mocks = build_engine(tmp_path=tmp_path, open_trades=[open_trade])
        # No proposal record + no strategy → falls back to 1h default.
        mocks["proposal_engine"].strategies = {}
        mocks["trader"].close_position.return_value = closed_trade

        result = await engine.run_cycle()

        assert result.positions_closed == 1
        mocks["trader"].close_position.assert_awaited_once_with(
            "t-aged", Decimal("50000"), reason="time_stop"
        )

    async def test_time_stop_uses_per_strategy_override(self, tmp_path: Path) -> None:
        """``max_bars_held=8`` on 1h → close past 8h, keep before."""
        info = TechniqueInfo(
            name="rsi_universal",
            version="1.0.0",
            description="rsi",
            technique_type="code",
            timeframes=["1h"],
            max_bars_held=8,
        )
        strategy = _StubStrategy(info=info)

        # Past the 8h window → must close.
        aged_trade = _make_aged_trade(
            trade_id="t-past-8h",
            age_seconds=8 * 3600 + 120,
            technique_name="rsi_universal",
        )
        closed_trade = aged_trade.model_copy(
            update={
                "status": "closed",
                "exit_price": Decimal("50000"),
                "exit_quantity": Decimal("0.1"),
                "close_reason": "time_stop",
                "pnl_percent": 0.0,
            }
        )

        engine, mocks = build_engine(tmp_path=tmp_path, open_trades=[aged_trade])
        mocks["proposal_engine"].strategies = {"rsi_universal": strategy}
        _wire_time_stop_proposal(
            mocks["history"],
            proposal_id="p-rsi-1",
            trade_id="t-past-8h",
            technique_name="rsi_universal",
        )
        mocks["trader"].close_position.return_value = closed_trade

        result = await engine.run_cycle()

        assert result.positions_closed == 1
        mocks["trader"].close_position.assert_awaited_once_with(
            "t-past-8h", Decimal("50000"), reason="time_stop"
        )

        # Now: 7h-old trade with the same override → must NOT close.
        young_trade = _make_aged_trade(
            trade_id="t-young-7h",
            age_seconds=7 * 3600,
            technique_name="rsi_universal",
        )
        engine2, mocks2 = build_engine(tmp_path=tmp_path, open_trades=[young_trade])
        mocks2["proposal_engine"].strategies = {"rsi_universal": strategy}
        _wire_time_stop_proposal(
            mocks2["history"],
            proposal_id="p-rsi-2",
            trade_id="t-young-7h",
            technique_name="rsi_universal",
        )

        result2 = await engine2.run_cycle()

        assert result2.positions_closed == 0
        mocks2["trader"].close_position.assert_not_called()

    async def test_time_stop_respects_higher_priority_sl(self, tmp_path: Path) -> None:
        """SL fires on the same monitor pass → close reason is ``stop_loss``."""
        # Trade is well past the time-stop window AND the SL hits.
        aged_trade = _make_aged_trade(trade_id="t-sl", age_seconds=1_000_000)
        sl_closed = aged_trade.model_copy(
            update={
                "status": "closed",
                "exit_price": Decimal("49500"),
                "exit_quantity": Decimal("0.1"),
                "close_reason": "stop_loss",
                "pnl_percent": -1.0,
            }
        )
        engine, mocks = build_engine(tmp_path=tmp_path, open_trades=[aged_trade])
        mocks["proposal_engine"].strategies = {}
        mocks["trader"].check_exit_conditions.return_value = (True, "stop_loss")
        mocks["trader"].close_position.return_value = sl_closed

        result = await engine.run_cycle()

        assert result.positions_closed == 1
        mocks["trader"].close_position.assert_awaited_once_with(
            "t-sl", Decimal("50000"), reason="stop_loss"
        )
        # No POSITION_TIME_STOPPED event — SL won the race.
        time_stops = mocks["activity_log"].filter(
            event_type=ActivityEventType.POSITION_TIME_STOPPED
        )
        assert time_stops == []

    async def test_time_stop_emits_activity_event(self, tmp_path: Path) -> None:
        """The time-stop close emits POSITION_TIME_STOPPED with the contract payload."""
        info = TechniqueInfo(
            name="tech_with_stop",
            version="1.0.0",
            description="x",
            technique_type="code",
            timeframes=["1h"],
            max_bars_held=4,
        )
        strategy = _StubStrategy(info=info)
        aged_trade = _make_aged_trade(
            trade_id="t-event",
            age_seconds=4 * 3600 + 60,
            technique_name="tech_with_stop",
        )
        closed_trade = aged_trade.model_copy(
            update={
                "status": "closed",
                "exit_price": Decimal("50000"),
                "exit_quantity": Decimal("0.1"),
                "close_reason": "time_stop",
                "pnl_percent": 0.0,
            }
        )

        engine, mocks = build_engine(tmp_path=tmp_path, open_trades=[aged_trade])
        mocks["proposal_engine"].strategies = {"tech_with_stop": strategy}
        _wire_time_stop_proposal(
            mocks["history"],
            proposal_id="p-event",
            trade_id="t-event",
            technique_name="tech_with_stop",
        )
        mocks["trader"].close_position.return_value = closed_trade

        await engine.run_cycle()

        events = mocks["activity_log"].filter(
            event_type=ActivityEventType.POSITION_TIME_STOPPED
        )
        assert len(events) == 1
        details = events[0].details
        assert details["trade_id"] == "t-event"
        assert details["symbol"] == "BTC/USDT"
        assert details["max_bars"] == 4
        assert details["timeframe"] == "1h"
        assert details["technique_name"] == "tech_with_stop"
        assert isinstance(details["age_hours"], float)
        assert details["age_hours"] >= 4.0

    async def test_time_stop_uses_default_when_strategy_missing(
        self, tmp_path: Path
    ) -> None:
        """Trade with no proposal/strategy → defaults to the 1h fallback."""
        from src.strategy.base import default_max_bars_held

        age = default_max_bars_held("1h") * 3600 + 30
        aged_trade = _make_aged_trade(trade_id="t-orphan", age_seconds=age)
        closed_trade = aged_trade.model_copy(
            update={
                "status": "closed",
                "exit_price": Decimal("50000"),
                "exit_quantity": Decimal("0.1"),
                "close_reason": "time_stop",
                "pnl_percent": 0.0,
            }
        )

        engine, mocks = build_engine(tmp_path=tmp_path, open_trades=[aged_trade])
        # No strategies registered + no proposal linkage.
        mocks["proposal_engine"].strategies = {}
        mocks["trader"].close_position.return_value = closed_trade

        result = await engine.run_cycle()

        assert result.positions_closed == 1
        events = mocks["activity_log"].filter(
            event_type=ActivityEventType.POSITION_TIME_STOPPED
        )
        assert len(events) == 1
        assert events[0].details["timeframe"] == "1h"
        assert events[0].details["max_bars"] == default_max_bars_held("1h")
        assert events[0].details["technique_name"] is None


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


def test_policy_resolver_field_precedence_matrix() -> None:
    """Each policy field resolves sub-account overrides before engine defaults."""
    config = EngineConfig(
        auto_approve_threshold=1.0,
        bitcoin_symbol="BTC/USDT",
        altcoin_symbols=["ETH/USDT"],
        altcoin_top_k=1,
        balance=Decimal("10000"),
        max_open_positions_per_symbol=1,
        runtime_safety_pause_min_score=80,
        fill_slippage_tolerance=Decimal("0.005"),
        reject_if_past_stop_loss=True,
        reject_if_stale_quote=False,
        max_ticker_age_seconds=10.0,
        correlation_gate_enabled=False,
        correlation_max_sub_accounts_per_symbol_side=1,
        correlation_max_sub_accounts_per_strategy_symbol_side=1,
    )
    sub_account = SubAccount(
        id="alpha",
        name="Alpha",
        mode="paper",
        exchange_ref="default",
        capital_policy=CapitalPolicy(sizing_balance=Decimal("2500")),
        strategy_policy=StrategyPolicy(
            bitcoin_symbol="BTC-PERP/USDT",
            symbols=["SOL/USDT", "BNB/USDT"],
            top_k=2,
        ),
        proposal_policy=ProposalPolicy(auto_approve_threshold=1.5),
        risk_policy=RiskPolicy(
            risk_percent=Decimal("0.25"),
            max_open_positions_total=5,
            max_open_positions_per_symbol=3,
            leverage_cap=4,
        ),
        execution_policy=ExecutionPolicy(
            runtime_safety_pause_min_score=70,
            fill_slippage_tolerance=Decimal("0.01"),
            reject_if_past_stop_loss=False,
            reject_if_stale_quote=True,
            max_ticker_age_seconds=3.0,
            correlation_gate_enabled=True,
            correlation_max_sub_accounts_per_symbol_side=2,
            correlation_max_sub_accounts_per_strategy_symbol_side=4,
        ),
    )

    resolved = PolicyResolver(
        config=config,
        sub_account=sub_account,
        default_leverage=10,
    ).resolve()

    assert resolved.bitcoin_symbol == "BTC-PERP/USDT"
    assert resolved.altcoin_symbols == ["SOL/USDT", "BNB/USDT"]
    assert resolved.altcoin_top_k == 2
    assert resolved.sizing_balance == Decimal("2500")
    assert resolved.risk_percent == Decimal("0.25")
    assert resolved.leverage == 4
    assert resolved.auto_approve_threshold == 1.5
    assert resolved.max_open_positions_total == 5
    assert resolved.max_open_positions_per_symbol == 3
    assert resolved.runtime_safety_pause_min_score == 70
    assert resolved.fill_slippage_tolerance == Decimal("0.01")
    assert resolved.reject_if_past_stop_loss is False
    assert resolved.reject_if_stale_quote is True
    assert resolved.max_ticker_age_seconds == 3.0
    assert resolved.correlation_gate_enabled is True
    assert resolved.correlation_max_sub_accounts_per_symbol_side == 2
    assert resolved.correlation_max_sub_accounts_per_strategy_symbol_side == 4

    defaulted = PolicyResolver(
        config=config,
        sub_account=None,
        default_leverage=10,
    ).resolve()
    assert defaulted.bitcoin_symbol == "BTC/USDT"
    assert defaulted.altcoin_symbols == ["ETH/USDT"]
    assert defaulted.altcoin_top_k == 1
    assert defaulted.sizing_balance == Decimal("10000")
    assert defaulted.risk_percent is None
    assert defaulted.leverage == 10
    assert defaulted.auto_approve_threshold == 1.0
    assert defaulted.max_open_positions_total is None
    assert defaulted.max_open_positions_per_symbol == 1
    assert defaulted.runtime_safety_pause_min_score == 80
    assert defaulted.fill_slippage_tolerance == Decimal("0.005")
    assert defaulted.reject_if_past_stop_loss is True
    assert defaulted.reject_if_stale_quote is False
    assert defaulted.max_ticker_age_seconds == 10.0
    assert defaulted.correlation_gate_enabled is False
    assert defaulted.correlation_max_sub_accounts_per_symbol_side == 1
    assert defaulted.correlation_max_sub_accounts_per_strategy_symbol_side == 1


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


async def test_gate_envelope_saves_final_cap_rejection_once(
    tmp_path: Path,
) -> None:
    """Post-decision gates persist only the final record, not torn ACCEPTED state."""
    existing_trade = make_trade(
        trade_id="t-bnb-existing",
        symbol="BNB/USDT",
        side="short",
    )
    proposal = make_proposal(
        proposal_id="bnb-envelope",
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
    saved_decisions: list[str] = []
    original_save = mocks["history"].save

    def counted_save(record: ProposalRecord) -> None:
        saved_decisions.append(str(record.decision))
        original_save(record)

    mocks["history"].save = counted_save

    result = await engine.run_cycle()

    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 1
    assert saved_decisions == [ProposalDecision.REJECTED.value]
    record = mocks["history"].load("bnb-envelope")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason is not None
    assert "cap 1 reached" in record.rejection_reason


# =============================================================================
# CAH-05: _finalize_rejection / cap-gate extraction event-count invariants.
#
# The refactor routes every gate rejection through ``_finalize_rejection``.
# The replay-event list shape is asymmetric (Shape A iterates the running
# ``events`` list; Shape B iterates ``events + gate.events``). These tests
# guard against the double/under-count hazard by asserting the EXACT count
# and ordered identity of emitted activity events at a representative Shape A
# site (total-cap) and a Shape B site (market-regime), plus that
# ``proposals_rejected`` increments exactly once.
# =============================================================================


# Activity events emitted per-proposal inside ``_handle_proposal`` (the
# cycle-level CYCLE_STARTED / CYCLE_COMPLETED / MONITOR_PASS markers are
# emitted elsewhere and are not what this refactor touches).
_PROPOSAL_LIFECYCLE_EVENTS = frozenset(
    {
        ActivityEventType.PROPOSAL_GENERATED,
        ActivityEventType.PROPOSAL_ACCEPTED,
        ActivityEventType.PROPOSAL_REJECTED,
        ActivityEventType.MARKET_REGIME_BLOCKED,
    }
)


async def test_total_cap_rejection_event_count_shape_a(tmp_path: Path) -> None:
    """Shape A (total-cap): GENERATED + ACCEPTED + REJECTED, exactly once each."""
    existing_trade = make_trade(
        trade_id="t-eth-existing",
        symbol="ETH/USDT",
        side="long",
    ).model_copy(update={"sub_account_id": "cap_acct"})
    proposal = make_proposal(
        proposal_id="btc-total-cap",
        symbol="BTC/USDT",
        signal="long",
        composite=2.0,
    ).model_copy(update={"sub_account_id": "cap_acct"})
    engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=proposal)
    cap_account = SubAccount(
        id="cap_acct",
        name="Cap Test",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
        risk_policy=RiskPolicy(
            max_open_positions_total=1,
            max_open_positions_per_symbol=5,
        ),
    )
    mocks["trader"].get_open_trades.return_value = [existing_trade]
    engine.sub_account_registry = FakeSubAccountRegistry(
        [cap_account], {"cap_acct": mocks["trader"]}
    )  # type: ignore[assignment]
    engine._runtime_policy_cache = {}

    result = await engine.run_cycle()

    # Total-cap is a Shape A site: the rejection event is concatenated onto
    # the running ``events`` list and replayed verbatim. Exactly one
    # increment, no double-count.
    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 1
    assert result.positions_opened == 0

    emitted = [
        event
        for event in mocks["activity_log"].read_all()
        if event.event_type in _PROPOSAL_LIFECYCLE_EVENTS
    ]
    types = [event.event_type for event in emitted]
    # GENERATED → ACCEPTED → REJECTED, no duplicates / drops.
    assert types == [
        ActivityEventType.PROPOSAL_GENERATED,
        ActivityEventType.PROPOSAL_ACCEPTED,
        ActivityEventType.PROPOSAL_REJECTED,
    ]
    rejections = mocks["activity_log"].filter(
        event_type=ActivityEventType.PROPOSAL_REJECTED
    )
    assert len(rejections) == 1
    assert rejections[0].details["gate_reason"] == "total_cap"
    assert rejections[0].details["cap"] == 1


async def test_regime_rejection_event_count_shape_b(tmp_path: Path) -> None:
    """Shape B (regime): GENERATED + ACCEPTED + REGIME_BLOCKED, exactly once each."""
    proposal = make_proposal(
        proposal_id="btc-regime-count",
        composite=2.0,
    ).model_copy(update={"sub_account_id": "regime_acct"})
    engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=proposal)
    _attach_regime_account(
        engine,
        mocks["trader"],
        enabled=True,
        allowed_regimes=["sideways"],
    )
    mocks["exchange"].get_ohlcv = AsyncMock(
        return_value=_make_regime_ohlcv([100.0] * 198 + [97.0, 97.0]),
    )

    result = await engine.run_cycle()

    # Regime is a Shape B site: the gate's own event is concatenated with
    # the running ``events`` list at the call site (``events + gate.events``)
    # and replayed verbatim. Exactly one increment.
    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 1
    assert result.positions_opened == 0

    emitted = [
        event
        for event in mocks["activity_log"].read_all()
        if event.event_type in _PROPOSAL_LIFECYCLE_EVENTS
    ]
    types = [event.event_type for event in emitted]
    assert types == [
        ActivityEventType.PROPOSAL_GENERATED,
        ActivityEventType.PROPOSAL_ACCEPTED,
        ActivityEventType.MARKET_REGIME_BLOCKED,
    ]
    blocked = mocks["activity_log"].filter(
        event_type=ActivityEventType.MARKET_REGIME_BLOCKED
    )
    assert len(blocked) == 1


async def test_gate_activity_crash_leaves_final_record_not_torn(
    tmp_path: Path,
) -> None:
    """If the ordered activity batch fails, disk already has the final verdict."""
    existing_trade = make_trade(
        trade_id="t-bnb-existing",
        symbol="BNB/USDT",
        side="short",
    )
    proposal = make_proposal(
        proposal_id="bnb-envelope-crash",
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
    original_append = mocks["activity_log"].append

    def crash_on_accepted_event(
        event_type: ActivityEventType,
        message: str = "",
        *,
        details: dict[str, object] | None = None,
        cycle_id: str | None = None,
    ) -> object:
        if event_type == ActivityEventType.PROPOSAL_ACCEPTED:
            raise RuntimeError("crash between gate batch events")
        return original_append(
            event_type,
            message,
            details=details,
            cycle_id=cycle_id,
        )

    mocks["activity_log"].append = crash_on_accepted_event

    result = await engine.run_cycle()

    assert result.errors
    record = mocks["history"].load("bnb-envelope-crash")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason is not None
    assert "cap 1 reached" in record.rejection_reason


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


async def test_notification_failure_updates_safety_pause_before_fill(
    tmp_path: Path,
) -> None:
    proposal = make_proposal(proposal_id="notify-pause", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            runtime_safety_pause_min_score=95,
        ),
    )
    mocks["notification_dispatcher"].notify_proposal.side_effect = RuntimeError(
        "slack down"
    )

    result = await engine.run_cycle()

    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 1
    assert result.positions_opened == 0
    mocks["trader"].open_position.assert_not_called()
    record = mocks["history"].load("notify-pause")
    assert record.decision == ProposalDecision.REJECTED.value
    assert "runtime safety score" in (record.rejection_reason or "")
    rejected = mocks["activity_log"].filter(
        event_type=ActivityEventType.PROPOSAL_REJECTED
    )
    safety_rejections = [
        event
        for event in rejected
        if event.details.get("runtime_safety_pause_min_score") == 95
    ]
    assert safety_rejections
    assert safety_rejections[-1].details["runtime_safety_score"] == 90


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


def test_strategy_lookup_for_open_trades_is_cached_per_cycle(tmp_path: Path) -> None:
    trade = make_trade(trade_id="cached-trade", symbol="BTC/USDT", side="long")
    proposal = make_proposal(proposal_id="cached-proposal", composite=2.0)
    engine, mocks = build_engine(tmp_path=tmp_path)
    mocks["history"].save(
        ProposalRecord(
            proposal=proposal,
            decision=ProposalDecision.ACCEPTED,
            trade_id=trade.id,
        )
    )
    calls = 0
    original = mocks["history"].list_all

    def counted_list_all(*args: object, **kwargs: object) -> list[ProposalRecord]:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    mocks["history"].list_all = counted_list_all

    assert engine._strategy_lookup_for_open_trades() == {trade.id: "tech_a"}
    assert engine._strategy_lookup_for_open_trades() == {trade.id: "tech_a"}

    assert calls == 1


def test_runtime_policy_for_id_is_cached_per_cycle(tmp_path: Path) -> None:
    engine, _ = build_engine(tmp_path=tmp_path)
    calls = 0
    original = engine._runtime_policy_for

    def counted_policy(sub_account: SubAccount | None) -> object:
        nonlocal calls
        calls += 1
        return original(sub_account)

    engine._runtime_policy_for = counted_policy  # type: ignore[method-assign]

    first = engine._runtime_policy_for_id("default")
    second = engine._runtime_policy_for_id("default")

    assert first is second
    assert calls == 1


def test_runtime_safety_score_is_cached_per_cycle(tmp_path: Path) -> None:
    engine, mocks = build_engine(tmp_path=tmp_path)
    calls = 0
    original = mocks["activity_log"].read_all

    def counted_read_all() -> list[object]:
        nonlocal calls
        calls += 1
        return original()

    mocks["activity_log"].read_all = counted_read_all

    first = engine._current_runtime_safety_score()
    second = engine._current_runtime_safety_score()

    assert first is second
    assert calls == 1


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
# CAH-01 [BUGFIX]: None ticker timestamp == unverifiable freshness
# =============================================================================
#
# A ccxt None ticker timestamp must NOT be laundered into "0 seconds old"
# (the prior now_utc() fallback defeated the DEBT-033 freshness gate). The
# adapters now pass ``Ticker.timestamp=None`` through; the gate mirrors the
# over-age branch: WARN + fall through normally, HARD-REJECT when
# ``reject_if_stale_quote`` is True.


async def test_reject_if_stale_quote_true_blocks_fill_on_none_ticker_timestamp(
    tmp_path: Path,
) -> None:
    """When ``reject_if_stale_quote=True``, a None ticker timestamp triggers
    the same hard rejection as a stale/over-age ticker.

    CAH-01: unverifiable freshness is fail-closed under the operator's
    opt-in switch. The reason matches the over-age branch
    (``stale_quote_no_live_data``) so the rejection-distribution audit
    treats them as one bucket; the ``detail`` distinguishes them
    (``ticker_timestamp_missing``).
    """
    proposal = make_proposal(proposal_id="reject-none-ts-1", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            reject_if_stale_quote=True,
        ),
        # Live below SL would normally reject via past-SL gate, but the
        # missing-timestamp check fires first.
        ticker_price=Decimal("49000"),
        ticker_timestamp_none=True,
    )

    result = await engine.run_cycle()

    # Hard rejection: no fill, reason is the shared no-live-data marker.
    assert result.positions_opened == 0
    assert result.proposals_accepted == 1
    assert result.proposals_rejected == 1
    mocks["trader"].open_position.assert_not_called()
    record = mocks["history"].load("reject-none-ts-1")
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason == "stale_quote_no_live_data"


async def test_reject_if_stale_quote_false_falls_through_on_none_ticker_timestamp(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When ``reject_if_stale_quote=False`` (default), a None ticker
    timestamp WARNs and falls through, mirroring the over-age branch.

    CAH-01: the fix must not block paper-mode fills on a venue that
    happens to omit ticker timestamps; it only refuses to *fabricate*
    freshness. The price-comparison branches are skipped (no verifiable
    quote age), so a past-SL ticker price must NOT cause a rejection.
    """
    import logging

    proposal = make_proposal(proposal_id="none-ts-fall-through-1", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            reject_if_stale_quote=False,
        ),
        ticker_price=Decimal("49000"),  # past SL=49500 on a long
        ticker_timestamp_none=True,
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
    record = mocks["history"].load("none-ts-fall-through-1")
    assert record.decision == ProposalDecision.ACCEPTED.value

    # WARN log carries the stale-ticker marker so operators can see the
    # gate was effectively a no-op for that proposal.
    warn_messages = [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and "stale_quote_check_failed" in r.getMessage()
    ]
    assert len(warn_messages) == 1
    msg = warn_messages[0]
    assert "stale_ticker" in msg
    assert "timestamp missing" in msg


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
    assert any(
        err.category == ErrorCategory.SUB_ACCOUNT and "sub_account[alpha]" in err.detail
        for err in result.errors
    )
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


# =============================================================================
# _trend_filter_gate (HTF SMA200 trend filter for counter-trend strategies)
# =============================================================================


class _StubStrategy(BaseStrategy):
    """Minimal BaseStrategy stand-in for trend-filter tests.

    We only need ``info.counter_trend`` to be readable by the gate;
    ``analyze`` is never invoked in these tests because the gate runs
    after the proposal already exists.
    """

    async def analyze(  # type: ignore[override]
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
        current_price: Decimal | None = None,
    ) -> AnalysisResult:
        raise NotImplementedError


def _make_stub_strategy(name: str, *, counter_trend: bool) -> BaseStrategy:
    info = TechniqueInfo(
        name=name,
        version="1.0.0",
        description="stub",
        technique_type="code",
        counter_trend=counter_trend,
    )
    return _StubStrategy(info)


def _make_daily_ohlcv(closes: list[float]) -> list[OHLCV]:
    """Build a list of OHLCV daily candles with the given close prices.

    The other fields are filled with the same value because the trend
    filter only consumes ``close``.
    """
    base_ts = datetime(2026, 1, 1, 0, 0, 0)
    bars: list[OHLCV] = []
    for index, close in enumerate(closes):
        price = Decimal(str(close))
        bars.append(
            OHLCV(
                timestamp=base_ts.replace(day=((index % 28) + 1)),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=Decimal("1"),
            )
        )
    return bars


class TestTrendFilterGate:
    """HTF 1D SMA200 trend filter for counter_trend strategies."""

    async def test_short_in_uptrend_rejected(self, tmp_path: Path) -> None:
        # 200 candles all at 100 → SMA200 = 100; final close at 200 →
        # uptrend. A counter-trend short must be rejected.
        closes = [100.0] * 199 + [200.0]
        proposal = make_proposal(
            proposal_id="ct-short-up", composite=2.0, signal="short"
        )
        engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=proposal)
        mocks["proposal_engine"].strategies = {
            proposal.technique_name: _make_stub_strategy(
                proposal.technique_name, counter_trend=True
            )
        }
        mocks["exchange"].get_ohlcv = AsyncMock(return_value=_make_daily_ohlcv(closes))

        result = await engine.run_cycle()

        assert result.proposals_accepted == 1
        assert result.proposals_rejected == 1
        assert result.positions_opened == 0
        mocks["trader"].open_position.assert_not_called()
        record = mocks["history"].load("ct-short-up")
        assert record.decision == ProposalDecision.REJECTED.value
        assert record.rejection_reason == "counter_trend_short_in_uptrend"
        rejected = mocks["activity_log"].filter(
            event_type=ActivityEventType.PROPOSAL_REJECTED
        )
        assert any(
            "counter_trend" in (event.details.get("reason") or "") for event in rejected
        )

    async def test_long_in_downtrend_rejected(self, tmp_path: Path) -> None:
        # 200 candles all at 200 → SMA200 = 200; final close at 100 →
        # downtrend. A counter-trend long must be rejected.
        closes = [200.0] * 199 + [100.0]
        proposal = make_proposal(
            proposal_id="ct-long-down",
            composite=2.0,
            signal="long",
            entry="100",
            sl="98",
            tp="106",
        )
        engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=proposal)
        mocks["proposal_engine"].strategies = {
            proposal.technique_name: _make_stub_strategy(
                proposal.technique_name, counter_trend=True
            )
        }
        mocks["exchange"].get_ohlcv = AsyncMock(return_value=_make_daily_ohlcv(closes))

        result = await engine.run_cycle()

        assert result.proposals_rejected == 1
        assert result.positions_opened == 0
        record = mocks["history"].load("ct-long-down")
        assert record.rejection_reason == "counter_trend_long_in_downtrend"

    async def test_short_in_downtrend_passes(self, tmp_path: Path) -> None:
        # SMA200 = 200, last close = 100 → downtrend. A counter-trend
        # short *with* the trend should NOT be blocked by this gate.
        closes = [200.0] * 199 + [100.0]
        proposal = make_proposal(
            proposal_id="ct-short-down",
            composite=2.0,
            signal="short",
            entry="100",
            sl="102",
            tp="94",
        )
        engine, mocks = build_engine(
            tmp_path=tmp_path,
            btc_proposal=proposal,
            ticker_price=Decimal("100"),
        )
        mocks["proposal_engine"].strategies = {
            proposal.technique_name: _make_stub_strategy(
                proposal.technique_name, counter_trend=True
            )
        }
        mocks["exchange"].get_ohlcv = AsyncMock(return_value=_make_daily_ohlcv(closes))

        result = await engine.run_cycle()

        assert result.proposals_accepted == 1
        assert result.positions_opened == 1
        # No trend-filter rejection on the record.
        record = mocks["history"].load("ct-short-down")
        assert record.decision == ProposalDecision.ACCEPTED.value

    async def test_long_in_uptrend_passes(self, tmp_path: Path) -> None:
        closes = [100.0] * 199 + [200.0]
        proposal = make_proposal(
            proposal_id="ct-long-up",
            composite=2.0,
            signal="long",
            entry="200",
            sl="196",
            tp="212",
        )
        engine, mocks = build_engine(
            tmp_path=tmp_path,
            btc_proposal=proposal,
            ticker_price=Decimal("200"),
        )
        mocks["proposal_engine"].strategies = {
            proposal.technique_name: _make_stub_strategy(
                proposal.technique_name, counter_trend=True
            )
        }
        mocks["exchange"].get_ohlcv = AsyncMock(return_value=_make_daily_ohlcv(closes))

        result = await engine.run_cycle()

        assert result.proposals_accepted == 1
        assert result.positions_opened == 1
        record = mocks["history"].load("ct-long-up")
        assert record.decision == ProposalDecision.ACCEPTED.value

    async def test_non_counter_trend_strategy_skipped(self, tmp_path: Path) -> None:
        # A trend-following strategy: even with a clearly counter-trend
        # short in an uptrend, the gate must not fetch HTF data and
        # must not block the fill.
        proposal = make_proposal(
            proposal_id="tf-short-up",
            composite=2.0,
            signal="short",
            entry="50000",
            sl="50500",
            tp="48500",
        )
        engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=proposal)
        mocks["proposal_engine"].strategies = {
            proposal.technique_name: _make_stub_strategy(
                proposal.technique_name, counter_trend=False
            )
        }
        get_ohlcv = AsyncMock(return_value=[])
        mocks["exchange"].get_ohlcv = get_ohlcv

        result = await engine.run_cycle()

        assert result.positions_opened == 1
        get_ohlcv.assert_not_called()

    async def test_insufficient_history_passes(self, tmp_path: Path) -> None:
        # Only 50 daily candles — gate must fail open rather than
        # silently disable trading on fresh listings.
        closes = [100.0] * 49 + [200.0]
        proposal = make_proposal(
            proposal_id="ct-shorthist",
            composite=2.0,
            signal="short",
            entry="50000",
            sl="50500",
            tp="48500",
        )
        engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=proposal)
        mocks["proposal_engine"].strategies = {
            proposal.technique_name: _make_stub_strategy(
                proposal.technique_name, counter_trend=True
            )
        }
        mocks["exchange"].get_ohlcv = AsyncMock(return_value=_make_daily_ohlcv(closes))

        result = await engine.run_cycle()

        assert result.positions_opened == 1
        record = mocks["history"].load("ct-shorthist")
        assert record.decision == ProposalDecision.ACCEPTED.value

    async def test_cache_used_within_cycle(self, tmp_path: Path) -> None:
        # Two proposals on the same symbol in the same cycle should
        # share the cached HTF sample → ``get_ohlcv`` called once.
        closes = [100.0] * 199 + [200.0]  # uptrend → both shorts rejected
        btc_short = make_proposal(
            proposal_id="ct-cache-1",
            composite=2.0,
            signal="short",
            symbol="BTC/USDT",
        )
        eth_short = make_proposal(
            proposal_id="ct-cache-2",
            composite=2.0,
            signal="short",
            symbol="BTC/USDT",  # same symbol on purpose to hit cache
        )
        engine, mocks = build_engine(
            tmp_path=tmp_path,
            btc_proposal=btc_short,
            altcoin_proposals=[eth_short],
        )
        mocks["proposal_engine"].strategies = {
            btc_short.technique_name: _make_stub_strategy(
                btc_short.technique_name, counter_trend=True
            )
        }
        get_ohlcv = AsyncMock(return_value=_make_daily_ohlcv(closes))
        mocks["exchange"].get_ohlcv = get_ohlcv

        result = await engine.run_cycle()

        # Both proposals were rejected by the trend filter and
        # ``get_ohlcv`` was invoked exactly once thanks to the cache.
        assert result.proposals_rejected == 2
        assert result.positions_opened == 0
        assert get_ohlcv.call_count == 1


def _make_family_stub_strategy(
    name: str, *, strategy_family: str | None
) -> BaseStrategy:
    """Build a stub strategy parameterised on ``strategy_family``.

    Counter-trend defaults to False so the trend-filter gate is a
    no-op and the sibling-family gate is the only thing under test
    in the table-style cases below.
    """
    info = TechniqueInfo(
        name=name,
        version="1.0.0",
        description="stub",
        technique_type="code",
        counter_trend=False,
        strategy_family=strategy_family,
    )
    return _StubStrategy(info)


class TestSiblingFamilyGate:
    """P0-E sibling-strategy de-duplication.

    Two strategies sharing a non-None ``strategy_family`` that fire
    the same ``(symbol, signal-side)`` in the same cycle: only the
    first wins; the rest are rejected with reason
    ``sibling_strategy_dedup:<family>``.
    """

    async def test_first_sibling_proposal_passes_subsequent_blocked(
        self, tmp_path: Path
    ) -> None:
        proposal_a = make_proposal(
            proposal_id="sib-a",
            composite=2.0,
            signal="short",
            symbol="AVAX/USDT",
            entry="9.77",
            sl="9.97",
            tp="9.37",
        ).model_copy(update={"technique_name": "rsi_4h"})
        proposal_b = make_proposal(
            proposal_id="sib-b",
            composite=2.0,
            signal="short",
            symbol="AVAX/USDT",
            entry="9.77",
            sl="9.97",
            tp="9.37",
        ).model_copy(update={"technique_name": "rsi_15m"})
        engine, mocks = build_engine(
            tmp_path=tmp_path,
            btc_proposal=proposal_a,
            altcoin_proposals=[proposal_b],
            ticker_price=Decimal("9.77"),
        )
        mocks["proposal_engine"].strategies = {
            "rsi_4h": _make_family_stub_strategy(
                "rsi_4h", strategy_family="rsi_mean_reversion"
            ),
            "rsi_15m": _make_family_stub_strategy(
                "rsi_15m", strategy_family="rsi_mean_reversion"
            ),
        }

        result = await engine.run_cycle()

        # First sibling fills; second sibling is rejected by the gate
        # (composite gate accepted both, so accepted = 2).
        assert result.proposals_accepted == 2
        assert result.proposals_rejected == 1
        assert result.positions_opened == 1
        record_a = mocks["history"].load("sib-a")
        record_b = mocks["history"].load("sib-b")
        assert record_a.decision == ProposalDecision.ACCEPTED.value
        assert record_b.decision == ProposalDecision.REJECTED.value
        assert "sibling_strategy_dedup" in (record_b.rejection_reason or "")
        assert "rsi_mean_reversion" in (record_b.rejection_reason or "")

    async def test_different_signal_passes(self, tmp_path: Path) -> None:
        # Same family + same symbol + opposite side → both pass the
        # gate. Long and short on the same symbol are distinct theses.
        proposal_long = make_proposal(
            proposal_id="sib-long",
            composite=2.0,
            signal="long",
            symbol="AVAX/USDT",
            entry="9.77",
            sl="9.57",
            tp="10.17",
        ).model_copy(update={"technique_name": "rsi_4h"})
        proposal_short = make_proposal(
            proposal_id="sib-short",
            composite=2.0,
            signal="short",
            symbol="AVAX/USDT",
            entry="9.77",
            sl="9.97",
            tp="9.37",
        ).model_copy(update={"technique_name": "rsi_15m"})
        engine, mocks = build_engine(
            tmp_path=tmp_path,
            btc_proposal=proposal_long,
            altcoin_proposals=[proposal_short],
            ticker_price=Decimal("9.77"),
        )
        mocks["proposal_engine"].strategies = {
            "rsi_4h": _make_family_stub_strategy(
                "rsi_4h", strategy_family="rsi_mean_reversion"
            ),
            "rsi_15m": _make_family_stub_strategy(
                "rsi_15m", strategy_family="rsi_mean_reversion"
            ),
        }

        result = await engine.run_cycle()

        assert result.proposals_accepted == 2
        assert result.positions_opened == 2
        assert mocks["history"].load("sib-long").decision == (
            ProposalDecision.ACCEPTED.value
        )
        assert mocks["history"].load("sib-short").decision == (
            ProposalDecision.ACCEPTED.value
        )

    async def test_different_symbol_passes(self, tmp_path: Path) -> None:
        # Same family + same side + different symbol → both pass.
        proposal_avax = make_proposal(
            proposal_id="sib-avax",
            composite=2.0,
            signal="short",
            symbol="AVAX/USDT",
            entry="9.77",
            sl="9.97",
            tp="9.37",
        ).model_copy(update={"technique_name": "rsi_4h"})
        proposal_sol = make_proposal(
            proposal_id="sib-sol",
            composite=2.0,
            signal="short",
            symbol="SOL/USDT",
            entry="90.15",
            sl="92.0",
            tp="86.5",
        ).model_copy(update={"technique_name": "rsi_15m"})
        engine, mocks = build_engine(
            tmp_path=tmp_path,
            btc_proposal=proposal_avax,
            altcoin_proposals=[proposal_sol],
            ticker_price=Decimal("9.77"),
        )
        # Per-symbol ticker so the slippage gate matches each
        # proposal's entry price exactly. ``build_engine`` defaults to
        # a single fixed ticker, which would reject SOL because the
        # AVAX-priced ticker drifts well past tolerance.
        symbol_to_price = {
            "AVAX/USDT": Decimal("9.77"),
            "SOL/USDT": Decimal("90.15"),
        }

        async def fake_get_ticker(symbol: str) -> Ticker:
            return Ticker(
                symbol=symbol,
                price=symbol_to_price[symbol],
                timestamp=now_utc(),
            )

        mocks["exchange"].get_ticker = AsyncMock(side_effect=fake_get_ticker)
        mocks["proposal_engine"].strategies = {
            "rsi_4h": _make_family_stub_strategy(
                "rsi_4h", strategy_family="rsi_mean_reversion"
            ),
            "rsi_15m": _make_family_stub_strategy(
                "rsi_15m", strategy_family="rsi_mean_reversion"
            ),
        }

        result = await engine.run_cycle()

        assert result.proposals_accepted == 2
        assert result.positions_opened == 2

    async def test_different_family_passes(self, tmp_path: Path) -> None:
        # Different family + same symbol + same side → both pass.
        proposal_a = make_proposal(
            proposal_id="sib-fam-a",
            composite=2.0,
            signal="short",
            symbol="AVAX/USDT",
            entry="9.77",
            sl="9.97",
            tp="9.37",
        ).model_copy(update={"technique_name": "rsi_4h"})
        proposal_b = make_proposal(
            proposal_id="sib-fam-b",
            composite=2.0,
            signal="short",
            symbol="AVAX/USDT",
            entry="9.77",
            sl="9.97",
            tp="9.37",
        ).model_copy(update={"technique_name": "ict_smc"})
        engine, mocks = build_engine(
            tmp_path=tmp_path,
            btc_proposal=proposal_a,
            altcoin_proposals=[proposal_b],
            ticker_price=Decimal("9.77"),
        )
        mocks["proposal_engine"].strategies = {
            "rsi_4h": _make_family_stub_strategy(
                "rsi_4h", strategy_family="rsi_mean_reversion"
            ),
            "ict_smc": _make_family_stub_strategy(
                "ict_smc", strategy_family="ict_smc_setups"
            ),
        }

        result = await engine.run_cycle()

        assert result.proposals_accepted == 2
        assert result.positions_opened == 2

    async def test_no_family_never_deduped(self, tmp_path: Path) -> None:
        # Both strategies have ``strategy_family=None`` → both pass
        # even though every other axis (symbol, side) matches the
        # dedup case. This preserves the historical behaviour for
        # every existing single-cadence strategy.
        proposal_a = make_proposal(
            proposal_id="sib-none-a",
            composite=2.0,
            signal="short",
            symbol="AVAX/USDT",
            entry="9.77",
            sl="9.97",
            tp="9.37",
        ).model_copy(update={"technique_name": "ema_cross"})
        proposal_b = make_proposal(
            proposal_id="sib-none-b",
            composite=2.0,
            signal="short",
            symbol="AVAX/USDT",
            entry="9.77",
            sl="9.97",
            tp="9.37",
        ).model_copy(update={"technique_name": "macd_div"})
        engine, mocks = build_engine(
            tmp_path=tmp_path,
            btc_proposal=proposal_a,
            altcoin_proposals=[proposal_b],
            ticker_price=Decimal("9.77"),
        )
        mocks["proposal_engine"].strategies = {
            "ema_cross": _make_family_stub_strategy("ema_cross", strategy_family=None),
            "macd_div": _make_family_stub_strategy("macd_div", strategy_family=None),
        }

        result = await engine.run_cycle()

        assert result.proposals_accepted == 2
        assert result.positions_opened == 2

    async def test_cache_cleared_between_cycles(self, tmp_path: Path) -> None:
        # Same family + same (symbol, side) across two distinct cycles
        # → both pass. The dedup cache must reset at the start of
        # every ``run_cycle`` so a winning sibling in cycle N does not
        # silently block its identical-family sibling in cycle N+1.
        proposal = make_proposal(
            proposal_id="sib-cycle-1",
            composite=2.0,
            signal="short",
            symbol="AVAX/USDT",
            entry="9.77",
            sl="9.97",
            tp="9.37",
        ).model_copy(update={"technique_name": "rsi_4h"})
        engine, mocks = build_engine(
            tmp_path=tmp_path,
            btc_proposal=proposal,
            ticker_price=Decimal("9.77"),
        )
        mocks["proposal_engine"].strategies = {
            "rsi_4h": _make_family_stub_strategy(
                "rsi_4h", strategy_family="rsi_mean_reversion"
            ),
        }

        # Cycle 1.
        result1 = await engine.run_cycle()
        assert result1.proposals_accepted == 1
        assert result1.positions_opened == 1

        # Cycle 2: identical proposal (different id) — must pass.
        proposal2 = make_proposal(
            proposal_id="sib-cycle-2",
            composite=2.0,
            signal="short",
            symbol="AVAX/USDT",
            entry="9.77",
            sl="9.97",
            tp="9.37",
        ).model_copy(update={"technique_name": "rsi_4h"})
        mocks["proposal_engine"].propose_bitcoin = AsyncMock(return_value=proposal2)

        result2 = await engine.run_cycle()
        assert result2.proposals_accepted == 1
        assert result2.proposals_rejected == 0
        assert result2.positions_opened == 1
        assert mocks["history"].load("sib-cycle-2").decision == (
            ProposalDecision.ACCEPTED.value
        )

    async def test_first_winner_logged_in_event(self, tmp_path: Path) -> None:
        # The PROPOSAL_REJECTED event for a sibling-dedup miss must
        # name the technique that won the gate first, so operators can
        # tell which cadence "stole" the slot from the duplicate.
        proposal_first = make_proposal(
            proposal_id="sib-first",
            composite=2.0,
            signal="short",
            symbol="AVAX/USDT",
            entry="9.77",
            sl="9.97",
            tp="9.37",
        ).model_copy(update={"technique_name": "rsi_4h"})
        proposal_loser = make_proposal(
            proposal_id="sib-loser",
            composite=2.0,
            signal="short",
            symbol="AVAX/USDT",
            entry="9.77",
            sl="9.97",
            tp="9.37",
        ).model_copy(update={"technique_name": "rsi_15m"})
        engine, mocks = build_engine(
            tmp_path=tmp_path,
            btc_proposal=proposal_first,
            altcoin_proposals=[proposal_loser],
            ticker_price=Decimal("9.77"),
        )
        mocks["proposal_engine"].strategies = {
            "rsi_4h": _make_family_stub_strategy(
                "rsi_4h", strategy_family="rsi_mean_reversion"
            ),
            "rsi_15m": _make_family_stub_strategy(
                "rsi_15m", strategy_family="rsi_mean_reversion"
            ),
        }

        await engine.run_cycle()

        rejected = mocks["activity_log"].filter(
            event_type=ActivityEventType.PROPOSAL_REJECTED
        )
        sibling_events = [
            event
            for event in rejected
            if "sibling_strategy_dedup" in (event.details.get("reason") or "")
        ]
        assert len(sibling_events) == 1
        details = sibling_events[0].details
        assert details["family"] == "rsi_mean_reversion"
        assert details["symbol"] == "AVAX/USDT"
        assert details["signal"] == "short"
        assert details["first_winner_technique"] == "rsi_4h"


# =============================================================================
# _market_regime_gate (per-sub-account regime gating)
# =============================================================================


def _attach_regime_account(
    engine: TradingEngine,
    trader: MagicMock,
    *,
    enabled: bool,
    allowed_regimes: list[str],
    reference_symbol: str = "BTC/USDT",
    timeframe: str = "4h",
    sub_account_id: str = "regime_acct",
) -> SubAccount:
    """Attach a single-account registry with a configured regime policy.

    The default ``build_engine`` path runs without a registry so
    ``_handle_proposal`` sees ``sub_account=None`` — the regime gate
    intentionally treats that as a back-compat no-op. These tests
    swap in a registry whose single account carries the configured
    ``MarketRegimePolicy`` so the gate has a policy to evaluate.
    """
    sub_account = SubAccount(
        id=sub_account_id,
        name="Regime Test",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
        market_regime=MarketRegimePolicy(
            enabled=enabled,
            reference_symbol=reference_symbol,
            timeframe=timeframe,
            allowed_regimes=allowed_regimes,
        ),
    )
    registry = FakeSubAccountRegistry([sub_account], {sub_account_id: trader})
    engine.sub_account_registry = registry  # type: ignore[assignment]
    engine._runtime_policy_cache = {}
    return sub_account


def _make_regime_ohlcv(
    closes: list[float],
    *,
    timeframe_seconds: int = 4 * 60 * 60,
) -> list[OHLCV]:
    """OHLCV series ending just before ``now_utc()``.

    Matches the runtime classifier's freshness rule (last candle within
    ``2 × timeframe`` of wall clock) so the classifier returns the
    intended label rather than ``unknown`` for staleness.
    """
    last_ts = now_utc()
    candles: list[OHLCV] = []
    n = len(closes)
    for index, close in enumerate(closes):
        ts = last_ts.replace(microsecond=0) - timedelta(
            seconds=timeframe_seconds * (n - 1 - index)
        )
        price = Decimal(str(close))
        candles.append(
            OHLCV(
                timestamp=ts,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=Decimal("1"),
            )
        )
    return candles


class TestMarketRegimeGate:
    """Per-sub-account regime gating wired into the proposal pipeline."""

    async def test_gate_disabled_passes_through(self, tmp_path: Path) -> None:
        # ``enabled=False`` is the back-compat default: even with a
        # deeply bearish reference series, the proposal must fill and
        # no MARKET_REGIME_BLOCKED event may be emitted.
        proposal = make_proposal(
            proposal_id="gate-off",
            composite=2.0,
        ).model_copy(update={"sub_account_id": "regime_acct"})
        engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=proposal)
        _attach_regime_account(
            engine,
            mocks["trader"],
            enabled=False,
            allowed_regimes=["bull"],
        )
        mocks["exchange"].get_ohlcv = AsyncMock(
            return_value=_make_regime_ohlcv([200.0] * 199 + [100.0]),
        )

        result = await engine.run_cycle()

        assert result.positions_opened == 1
        mocks["exchange"].get_ohlcv.assert_not_called()
        blocked = mocks["activity_log"].filter(
            event_type=ActivityEventType.MARKET_REGIME_BLOCKED
        )
        assert blocked == []

    async def test_gate_allowed_regime_passes_through(self, tmp_path: Path) -> None:
        # 198 candles at 100 + last 2 closes at 103 → classifier returns
        # ``bull`` (DEBT-063: two-bar confirmation); account allows
        # ``bull`` → proposal fills.
        proposal = make_proposal(
            proposal_id="gate-bull-ok",
            composite=2.0,
        ).model_copy(update={"sub_account_id": "regime_acct"})
        engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=proposal)
        _attach_regime_account(
            engine,
            mocks["trader"],
            enabled=True,
            allowed_regimes=["bull"],
        )
        mocks["exchange"].get_ohlcv = AsyncMock(
            return_value=_make_regime_ohlcv([100.0] * 198 + [103.0, 103.0]),
        )

        result = await engine.run_cycle()

        assert result.positions_opened == 1
        blocked = mocks["activity_log"].filter(
            event_type=ActivityEventType.MARKET_REGIME_BLOCKED
        )
        assert blocked == []

    async def test_gate_disallowed_regime_blocks_and_emits_event(
        self, tmp_path: Path
    ) -> None:
        # 198 candles at 100 + last 2 closes at 97 → classifier returns
        # ``bear`` (DEBT-063: two-bar confirmation); account allows only
        # ``sideways`` → proposal blocked AND a MARKET_REGIME_BLOCKED
        # event must carry the spec §4 payload shape.
        proposal = make_proposal(
            proposal_id="gate-bear-blocked",
            composite=2.0,
        ).model_copy(update={"sub_account_id": "regime_acct"})
        engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=proposal)
        _attach_regime_account(
            engine,
            mocks["trader"],
            enabled=True,
            allowed_regimes=["sideways"],
        )
        mocks["exchange"].get_ohlcv = AsyncMock(
            return_value=_make_regime_ohlcv([100.0] * 198 + [97.0, 97.0]),
        )

        result = await engine.run_cycle()

        assert result.proposals_accepted == 1
        assert result.proposals_rejected == 1
        assert result.positions_opened == 0
        mocks["trader"].open_position.assert_not_called()
        record = mocks["history"].load("gate-bear-blocked")
        assert record.decision == ProposalDecision.REJECTED.value
        assert record.rejection_reason == "market_regime_blocked_bear"

        blocked = mocks["activity_log"].filter(
            event_type=ActivityEventType.MARKET_REGIME_BLOCKED
        )
        assert len(blocked) == 1
        details = blocked[0].details
        # Spec §4 payload contract.
        assert details["symbol"] == "BTC/USDT"
        assert details["timeframe"] == "4h"
        assert details["regime"] == "bear"
        assert details["baseline"] is not None
        assert Decimal(details["close"]) == Decimal("97")
        assert details["policy_decision"] == "block"
        assert details["sub_account_id"] == "regime_acct"
        assert details["reason"] == "market_regime_blocked_bear"

    async def test_unknown_regime_blocks_by_default(self, tmp_path: Path) -> None:
        # < 200 candles → classifier returns ``unknown``; account does
        # NOT list ``unknown`` in allowed_regimes → proposal blocked.
        # Spec §3 third bullet: "unknown should block by default when
        # gating is enabled unless the account explicitly allows it".
        proposal = make_proposal(
            proposal_id="gate-unknown-blocked",
            composite=2.0,
        ).model_copy(update={"sub_account_id": "regime_acct"})
        engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=proposal)
        _attach_regime_account(
            engine,
            mocks["trader"],
            enabled=True,
            allowed_regimes=["bull", "bear", "sideways"],
        )
        mocks["exchange"].get_ohlcv = AsyncMock(
            return_value=_make_regime_ohlcv([100.0] * 50),
        )

        result = await engine.run_cycle()

        assert result.proposals_rejected == 1
        assert result.positions_opened == 0
        record = mocks["history"].load("gate-unknown-blocked")
        assert record.rejection_reason == "market_regime_blocked_unknown"
        blocked = mocks["activity_log"].filter(
            event_type=ActivityEventType.MARKET_REGIME_BLOCKED
        )
        assert len(blocked) == 1
        assert blocked[0].details["regime"] == "unknown"
        # Insufficient-data classifications carry the classifier reason
        # so post-mortems can distinguish "no data yet" from "feed went
        # quiet" without re-running the classifier.
        assert blocked[0].details["classifier_reason"] == "insufficient_data"

    async def test_unknown_regime_passes_when_explicitly_allowed(
        self, tmp_path: Path
    ) -> None:
        # Same insufficient-data scenario, but the account explicitly
        # lists ``unknown`` → proposal must pass.
        proposal = make_proposal(
            proposal_id="gate-unknown-ok",
            composite=2.0,
        ).model_copy(update={"sub_account_id": "regime_acct"})
        engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=proposal)
        _attach_regime_account(
            engine,
            mocks["trader"],
            enabled=True,
            allowed_regimes=["bull", "bear", "sideways", "unknown"],
        )
        mocks["exchange"].get_ohlcv = AsyncMock(
            return_value=_make_regime_ohlcv([100.0] * 50),
        )

        result = await engine.run_cycle()

        assert result.positions_opened == 1
        blocked = mocks["activity_log"].filter(
            event_type=ActivityEventType.MARKET_REGIME_BLOCKED
        )
        assert blocked == []

    async def test_ohlcv_fetch_failure_falls_open(self, tmp_path: Path) -> None:
        # Transient OHLCV fetch failures must not silently disable
        # trading — same fail-open contract as ``_trend_filter_gate``.
        # The fail-open path must NOT emit a MARKET_REGIME_BLOCKED
        # event (the proposal is not blocked); the dedicated degraded
        # event is asserted by
        # ``test_ohlcv_fetch_failure_falls_open_and_emits_degraded_event``.
        proposal = make_proposal(
            proposal_id="gate-fetch-fail",
            composite=2.0,
        ).model_copy(update={"sub_account_id": "regime_acct"})
        engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=proposal)
        _attach_regime_account(
            engine,
            mocks["trader"],
            enabled=True,
            allowed_regimes=["bull"],
        )
        mocks["exchange"].get_ohlcv = AsyncMock(
            side_effect=RuntimeError("exchange down"),
        )

        result = await engine.run_cycle()

        assert result.positions_opened == 1
        blocked = mocks["activity_log"].filter(
            event_type=ActivityEventType.MARKET_REGIME_BLOCKED
        )
        assert blocked == []

    async def test_ohlcv_fetch_failure_falls_open_and_emits_degraded_event(
        self, tmp_path: Path
    ) -> None:
        # Quant-trader audit follow-up: fail-open is still the right
        # default for transient fetch errors, but the silent gate
        # disablement must surface to the operator. Pin the payload
        # contract here so a future refactor cannot regress to the
        # silent-disable shape (DEBT-061 anti-pattern).
        proposal = make_proposal(
            proposal_id="gate-fetch-degraded",
            composite=2.0,
        ).model_copy(update={"sub_account_id": "regime_acct"})
        engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=proposal)
        _attach_regime_account(
            engine,
            mocks["trader"],
            enabled=True,
            allowed_regimes=["bull"],
            reference_symbol="BTC/USDT",
            timeframe="4h",
            sub_account_id="regime_acct",
        )
        mocks["exchange"].get_ohlcv = AsyncMock(
            side_effect=RuntimeError("exchange down"),
        )

        result = await engine.run_cycle()

        # Fail-open semantics: proposal still fills.
        assert result.positions_opened == 1
        # No MARKET_REGIME_BLOCKED event on the fail-open path.
        blocked = mocks["activity_log"].filter(
            event_type=ActivityEventType.MARKET_REGIME_BLOCKED
        )
        assert blocked == []
        # Exactly one MARKET_REGIME_DEGRADED event with the pinned
        # payload contract.
        degraded = mocks["activity_log"].filter(
            event_type=ActivityEventType.MARKET_REGIME_DEGRADED
        )
        assert len(degraded) == 1
        event = degraded[0]
        assert event.cycle_id is not None
        details = event.details
        assert details["symbol"] == "BTC/USDT"
        assert details["timeframe"] == "4h"
        assert details["error_type"] == "RuntimeError"
        assert details["sub_account_id"] == "regime_acct"
        assert details["policy_decision"] == "pass_through_degraded"

    @pytest.mark.parametrize(
        ("closes_tail", "expected_regime", "expected_blocked"),
        [
            # bull: last 2 bars at 103 (DEBT-063 two-bar confirmation)
            # vs 100-anchored SMA both exceed the +2% band.
            ([100.0] * 198 + [103.0, 103.0], "bull", False),
            # bear: last 2 bars at 97 both cross the -2% band.
            ([100.0] * 198 + [97.0, 97.0], "bear", True),
            # sideways: 101 sits inside the ±2% neutral band.
            ([100.0] * 199 + [101.0], "sideways", True),
            # unknown: < 200 candles → classifier returns "unknown".
            # The policy lists only "bull", so unknown blocks per spec
            # §3 — third bullet on `unknown`.
            ([100.0] * 50, "unknown", True),
        ],
    )
    async def test_end_to_end_bull_bear_sideways_unknown_policy_override(
        self,
        tmp_path: Path,
        closes_tail: list[float],
        expected_regime: str,
        expected_blocked: bool,
    ) -> None:
        """End-to-end integration: configure a sub-account with
        ``allowed_regimes=["bull"]``, feed each classifier scenario,
        and assert exactly the expected accept/block outcome + the
        right MARKET_REGIME_BLOCKED event for every non-bull regime.
        Covers Step 5 of the market-regime code-generation plan."""
        proposal = make_proposal(
            proposal_id=f"e2e-{expected_regime}",
            composite=2.0,
        ).model_copy(update={"sub_account_id": "regime_acct"})
        engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=proposal)
        _attach_regime_account(
            engine,
            mocks["trader"],
            enabled=True,
            allowed_regimes=["bull"],
        )
        mocks["exchange"].get_ohlcv = AsyncMock(
            return_value=_make_regime_ohlcv(closes_tail),
        )

        result = await engine.run_cycle()

        blocked = mocks["activity_log"].filter(
            event_type=ActivityEventType.MARKET_REGIME_BLOCKED
        )
        if expected_blocked:
            assert result.proposals_rejected == 1
            assert result.positions_opened == 0
            mocks["trader"].open_position.assert_not_called()
            assert len(blocked) == 1
            assert blocked[0].details["regime"] == expected_regime
            assert blocked[0].details["policy_decision"] == "block"
            assert blocked[0].details["sub_account_id"] == "regime_acct"
            record = mocks["history"].load(f"e2e-{expected_regime}")
            assert record.rejection_reason == f"market_regime_blocked_{expected_regime}"
        else:
            assert result.positions_opened == 1
            assert blocked == []

    async def test_regime_classification_cached_per_cycle(self, tmp_path: Path) -> None:
        # Two proposals in one cycle, same reference symbol/timeframe →
        # the OHLCV fetch should happen exactly once. This pins the
        # cache invariant the runtime relies on so a fan-out scan does
        # not multiply the exchange round-trip count by proposal count.
        proposal_btc = make_proposal(
            proposal_id="cache-btc",
            symbol="BTC/USDT",
            composite=2.0,
        ).model_copy(update={"sub_account_id": "regime_acct"})
        proposal_eth = make_proposal(
            proposal_id="cache-eth",
            symbol="ETH/USDT",
            composite=2.0,
        ).model_copy(update={"sub_account_id": "regime_acct"})
        engine, mocks = build_engine(
            tmp_path=tmp_path,
            btc_proposal=proposal_btc,
            altcoin_proposals=[proposal_eth],
        )
        _attach_regime_account(
            engine,
            mocks["trader"],
            enabled=True,
            allowed_regimes=["bull"],
        )
        mocks["exchange"].get_ohlcv = AsyncMock(
            return_value=_make_regime_ohlcv([100.0] * 198 + [103.0, 103.0]),
        )

        await engine.run_cycle()

        assert mocks["exchange"].get_ohlcv.await_count == 1

    async def test_correlation_gate_runs_before_regime_gate(
        self, tmp_path: Path
    ) -> None:
        # DEBT-062: when BOTH the correlation gate AND the regime gate
        # would reject, the directly-actionable correlation rejection
        # must surface to the operator — not the non-actionable regime
        # rejection. Pin the new gate order by setting up a proposal
        # that would fail BOTH gates and asserting the correlation-
        # rejected terminal state + no MARKET_REGIME_BLOCKED event.
        existing_trade = make_trade(
            trade_id="t-btc-existing",
            symbol="BTC/USDT",
            side="long",
        ).model_copy(update={"sub_account_id": "alpha"})
        proposal = make_proposal(
            proposal_id="ordering-corr-vs-regime",
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
        # Beta carries a regime policy that would ALSO block: it requires
        # ``bull`` but the fixture is bear (two confirming bars at 97).
        beta = SubAccount(
            id="beta",
            name="Beta",
            mode="paper",
            exchange_ref="default",
            initial_balance={"USDT": Decimal("10000")},
            market_regime=MarketRegimePolicy(
                enabled=True,
                reference_symbol="BTC/USDT",
                timeframe="4h",
                allowed_regimes=["bull"],
            ),
        )
        alpha_trader = make_mock_trader()
        beta_trader = make_mock_trader()
        alpha_trader.get_open_trades.return_value = [existing_trade]
        engine.sub_account_registry = FakeSubAccountRegistry(
            [alpha, beta],
            {"alpha": alpha_trader, "beta": beta_trader},
        )  # type: ignore[assignment]
        engine._runtime_policy_cache = {}
        mocks["proposal_engine"].strategies = {}
        mocks["exchange"].get_ohlcv = AsyncMock(
            return_value=_make_regime_ohlcv([100.0] * 198 + [97.0, 97.0]),
        )

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

        # Correlation rejection wins: the persisted record carries the
        # correlation final-state, not the regime final-state.
        record = mocks["history"].load("ordering-corr-vs-regime")
        assert record.decision == ProposalDecision.REJECTED.value
        assert record.final_state == ProposalFinalState.GATE_REJECTED_CORRELATION.value
        assert record.rejection_reason == (
            "correlation gate rejected excessive duplicate exposure"
        )

        # No MARKET_REGIME_BLOCKED event is emitted — the regime gate
        # is short-circuited by the earlier correlation rejection.
        regime_blocked = mocks["activity_log"].filter(
            event_type=ActivityEventType.MARKET_REGIME_BLOCKED
        )
        assert regime_blocked == []


# =============================================================================
# Startup reconciliation health check (runtime-reconciliation §3)
# =============================================================================


def _seed_paper_trade_row(
    tmp_path: Path,
    sub_account_id: str,
    *,
    trade_id: str = "trade-1",
    symbol: str | None = "BTC/USDT",
    side: str | None = "long",
    entry_price: str | None = "50000",
    entry_quantity: str | None = "0.1",
    stop_loss: str | None = "49500",
    take_profit: str | None = "51500",
    leverage: int = 10,
    performance_record_id: str | None = None,
    status: str = "open",
) -> None:
    """Write a single open paper-trade row into the ledger directly.

    Bypasses ``TradeHistoryTracker.open_trade`` so tests can construct
    rows with deliberately missing fields (the strict pydantic model
    rejects ``None`` symbol/price; the on-disk JSON is more
    permissive and that's exactly the failure mode the reconciliation
    classifier surfaces).
    """
    import json as _json

    path = tmp_path / "trades" / "paper" / sub_account_id / "trades.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    if path.exists():
        rows = _json.loads(path.read_text())
    rows.append(
        {
            "id": trade_id,
            "sub_account_id": sub_account_id,
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "entry_quantity": entry_quantity,
            "leverage": leverage,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "performance_record_id": performance_record_id,
            "status": status,
            "mode": "paper",
        }
    )
    path.write_text(_json.dumps(rows, indent=2))


def _drive_run_forever_once(engine: TradingEngine) -> None:
    """Trip ``run_forever`` so the startup health check fires, then stop.

    The engine is signalled to stop *before* ``run_forever`` is called
    so the loop guard exits immediately after the STARTUP + health
    check pass. This keeps the test deterministic — we don't depend
    on the cycle body or any of its mocks for the health-check
    coverage.
    """
    engine._stop_event.set()
    asyncio.run(engine.run_forever())


def test_startup_emits_reconciliation_health_report(tmp_path: Path) -> None:
    """One ``RECONCILIATION_HEALTH_REPORT`` event per startup, never blocks."""
    engine, mocks = build_engine(tmp_path=tmp_path)
    # Make the trader's tracker data_dir resolve to ``tmp_path/trades``
    # so the health-check helper picks ``tmp_path`` as the data root
    # rather than ``Settings().data_dir``.
    tracker = MagicMock()
    tracker.data_dir = tmp_path / "trades"
    mocks["trader"]._trade_tracker = tracker

    _seed_paper_trade_row(
        tmp_path,
        "default",
        trade_id="bad",
        symbol=None,  # unrecoverable
        performance_record_id=None,
    )

    _drive_run_forever_once(engine)

    events = mocks["activity_log"].filter(
        event_type=ActivityEventType.RECONCILIATION_HEALTH_REPORT
    )
    assert len(events) == 1
    event = events[0]
    totals = event.details["totals"]
    assert totals["open_trade_count"] == 1
    assert totals["state_counts"]["unrecoverable"] == 1


def test_startup_emits_locked_inconsistent_event_when_drift_detected(
    tmp_path: Path,
) -> None:
    """A locked-margin drift produces a separate ``RECONCILIATION_LOCKED_INCONSISTENT`` event."""
    import json as _json

    engine, mocks = build_engine(tmp_path=tmp_path)
    tracker = MagicMock()
    tracker.data_dir = tmp_path / "trades"
    mocks["trader"]._trade_tracker = tracker

    # One open row → locked_sum = 50000 * 0.1 / 10 = 500.
    _seed_paper_trade_row(tmp_path, "default", trade_id="ok")
    # Snapshot reports a different locked amount → drift > epsilon.
    balances_path = tmp_path / "trades" / "paper" / "default" / "balances.json"
    balances_path.write_text(
        _json.dumps(
            {
                "USDT": {
                    "currency": "USDT",
                    "free": "9000",
                    "locked": "999",
                }
            }
        )
    )

    _drive_run_forever_once(engine)

    inconsistent = mocks["activity_log"].filter(
        event_type=ActivityEventType.RECONCILIATION_LOCKED_INCONSISTENT
    )
    assert len(inconsistent) == 1
    sub_accounts = inconsistent[0].details["sub_accounts"]
    assert sub_accounts[0]["sub_account_id"] == "default"


def test_startup_health_check_swallows_internal_errors(tmp_path: Path) -> None:
    """A crash inside ``compute_health_report`` must not block startup.

    Paper-mode resolution 2026-05-13: never fail-startup. Verified by
    patching the helper to raise; ``run_forever`` must still emit the
    STARTUP event and reach SHUTDOWN cleanly. The success-event
    (``RECONCILIATION_HEALTH_REPORT``) must NOT be emitted — Q4
    follow-up routes the failure through
    ``RECONCILIATION_HEALTH_CHECK_FAILED`` instead.
    """
    engine, mocks = build_engine(tmp_path=tmp_path)

    with patch(
        "src.runtime.engine.compute_health_report",
        side_effect=RuntimeError("boom"),
    ):
        _drive_run_forever_once(engine)

    events = mocks["activity_log"].read_all()
    event_types = {e.event_type for e in events}
    assert ActivityEventType.STARTUP.value in event_types
    assert ActivityEventType.SHUTDOWN.value in event_types
    assert ActivityEventType.RECONCILIATION_HEALTH_REPORT.value not in event_types


def test_startup_emits_health_check_failed_event(tmp_path: Path) -> None:
    """Q4 follow-up: a ``compute_health_report`` crash emits a meta-event.

    Without this event the dashboard cannot distinguish "fresh deploy
    that hasn't booted yet" from "health check has been crashing on
    every boot for 9 days" — the DEBT-061 silent-disable anti-pattern.
    Payload contract pinned: ``error_type`` / ``message`` /
    ``sub_account_id`` keys are stable for the dashboard banner.
    """
    engine, mocks = build_engine(tmp_path=tmp_path)

    with patch(
        "src.runtime.engine.compute_health_report",
        side_effect=RuntimeError("boom"),
    ):
        _drive_run_forever_once(engine)

    failed = mocks["activity_log"].filter(
        event_type=ActivityEventType.RECONCILIATION_HEALTH_CHECK_FAILED
    )
    assert len(failed) == 1
    payload = failed[0].details
    assert payload["error_type"] == "RuntimeError"
    assert payload["message"] == "boom"
    assert payload["sub_account_id"] is None
    # Startup still proceeded to the cycle loop — STARTUP and SHUTDOWN
    # bracket the run as in the success path.
    event_types = {e.event_type for e in mocks["activity_log"].read_all()}
    assert ActivityEventType.STARTUP.value in event_types
    assert ActivityEventType.SHUTDOWN.value in event_types


# =============================================================================
# proposal-funnel-audit — final_state transitions + record_id join key
# =============================================================================


async def test_score_rejected_proposal_carries_score_rejected_final_state(
    tmp_path: Path,
) -> None:
    """Below-threshold proposals end in ``final_state=score_rejected``."""
    proposal = make_proposal(proposal_id="ff_score_rej", composite=0.1)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=2.0),
    )
    await engine.run_cycle()
    record = mocks["history"].load("ff_score_rej")
    assert record.final_state == ProposalFinalState.SCORE_REJECTED.value


async def test_build_cap_blocker_payload_shape(tmp_path: Path) -> None:
    """The cap-blocker helper produces the spec §3 shape per open trade.

    The blocker entry must carry: ``trade_id``, ``symbol``, ``side``,
    ``entry_price``, ``entry_time`` (isoformat string), ``age_seconds``,
    ``monitorable``, ``cap_value``, ``current_open_count`` and the
    optional ``unrealized_pnl_percent`` / ``technique_name`` /
    ``proposal_record_id`` fields.

    DEBT-066 update: cap-rejection is a hot path; the helper must never
    fetch a ticker (``get_ticker.assert_not_awaited()``) and the
    ``unrealized_pnl_percent`` field is now sourced from the in-memory
    mark-price cache when available. Pre-seed the cache here so the
    cache-based pricing path is exercised end-to-end.
    """
    proposal = make_proposal(proposal_id="ff_cap_helper", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    open_trade = make_trade(
        trade_id="t-helper",
        symbol="BNB/USDT",
        side="short",
        performance_record_id="perf-1",
    )
    # DEBT-066: prime the cache so cache-based pricing is consulted.
    # The default entry is at 50000; a mark of 49000 on the SHORT side
    # is +2% in the position's favor (entry - mark)/entry × 100.
    engine._remember_mark_price("BNB/USDT", Decimal("49000"))
    payload = await engine._build_cap_blocker_payload(
        open_trades=[open_trade],
        cap=5,
        reason="symbol_cap",
    )
    assert len(payload) == 1
    entry = payload[0]
    for required in (
        "trade_id",
        "symbol",
        "side",
        "entry_price",
        "entry_time",
        "age_seconds",
        "monitorable",
        "unrealized_pnl_percent",
        "technique_name",
        "proposal_record_id",
        "cap_value",
        "current_open_count",
        "reason",
    ):
        assert required in entry, f"missing {required} from cap blocker entry"
    assert entry["trade_id"] == "t-helper"
    assert entry["cap_value"] == 5
    assert entry["current_open_count"] == 1
    # Cap rejection is a hot-path; the helper must not call the
    # exchange (no ticker fetch per blocker).
    mocks["exchange"].get_ticker.assert_not_awaited()
    # DEBT-066: cache-based pricing path is exercised — the seeded
    # mark feeds a populated ``unrealized_pnl_percent``.
    assert entry["unrealized_pnl_percent"] is not None
    assert entry["unrealized_pnl_percent"] == pytest.approx(2.0, rel=1e-9)


async def test_build_cap_blocker_payload_falls_back_to_none_when_cache_miss(
    tmp_path: Path,
) -> None:
    """DEBT-066: ``unrealized_pnl_percent`` falls back to ``None`` on cache miss.

    Pins the regression contract for the pre-DEBT-066 behaviour: when
    the in-memory mark cache has no entry for the blocker's symbol, the
    diagnostic field carries ``None`` rather than triggering a fresh
    ticker fetch (which would re-introduce the hot-path latency tax the
    DEBT entry exists to prevent).
    """
    proposal = make_proposal(proposal_id="ff_cap_none_pnl", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    open_trade = make_trade(
        trade_id="t-no-mark",
        symbol="ETH/USDT",
        side="long",
        performance_record_id="perf-no-mark",
    )
    # Cache deliberately empty for this symbol — the helper must not
    # spin up a ticker fetch to fill the gap.
    assert engine._get_cached_mark_price("ETH/USDT") is None
    payload = await engine._build_cap_blocker_payload(
        open_trades=[open_trade],
        cap=3,
        reason="total_cap",
    )
    assert len(payload) == 1
    assert payload[0]["unrealized_pnl_percent"] is None
    mocks["exchange"].get_ticker.assert_not_awaited()


# =============================================================================
# DEBT-066: in-memory mark-price cache
# =============================================================================


async def test_mark_price_cache_populated_from_asset_snapshot(tmp_path: Path) -> None:
    """``_record_portfolio_snapshot`` writes every per-trade mark into the cache.

    The snapshot path already fetches a ticker per open trade for the
    AssetSnapshot's ``current_prices`` map. DEBT-066 piggybacks on the
    same fetch — no new exchange calls — to populate the in-memory
    cache the cap-blocker helper consumes.
    """
    from src.trading.portfolio import PortfolioTracker

    proposal = make_proposal(proposal_id="ff_mark_snapshot", composite=2.0)
    open_trade_a = make_trade(trade_id="t-eth", symbol="ETH/USDT", side="long")
    open_trade_b = make_trade(trade_id="t-bnb", symbol="BNB/USDT", side="short")
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[open_trade_a, open_trade_b],
    )
    # Wire a portfolio tracker so the snapshot path is exercised
    # end-to-end.
    engine.portfolio_tracker = PortfolioTracker(data_dir=tmp_path / "portfolio")

    # Per-symbol ticker prices via ``side_effect`` — the default mock
    # returns the same 50000 ticker for every call.
    async def _ticker_by_symbol(symbol: str) -> Ticker:
        prices = {"ETH/USDT": Decimal("2500"), "BNB/USDT": Decimal("700")}
        return Ticker(symbol=symbol, price=prices[symbol], timestamp=now_utc())

    mocks["exchange"].get_ticker.side_effect = _ticker_by_symbol
    mocks["trader"].get_balances = AsyncMock(return_value={})

    await engine._record_portfolio_snapshot(
        cycle_id="cycle-mark",
        sub_account=None,
        trader=mocks["trader"],
    )

    assert engine._get_cached_mark_price("ETH/USDT") == Decimal("2500")
    assert engine._get_cached_mark_price("BNB/USDT") == Decimal("700")


async def test_get_cached_mark_price_returns_value_when_fresh(
    tmp_path: Path,
) -> None:
    """A cache entry within ``max_age_seconds`` is returned verbatim."""
    proposal = make_proposal(proposal_id="ff_mark_fresh", composite=2.0)
    engine, _ = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    engine._remember_mark_price("ETH/USDT", Decimal("2500"))
    # Default max_age_seconds = 300; the entry is microseconds old.
    assert engine._get_cached_mark_price("ETH/USDT") == Decimal("2500")


async def test_get_cached_mark_price_returns_none_when_stale(
    tmp_path: Path,
) -> None:
    """An entry older than ``max_age_seconds`` is rejected as stale.

    The cache itself keeps the stale entry; the read-side helper is the
    freshness gate. A subsequent write overwrites the timestamp on the
    next monitor pass.
    """
    from src.runtime.engine import MarkPriceEntry

    proposal = make_proposal(proposal_id="ff_mark_stale", composite=2.0)
    engine, _ = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    # Inject an entry observed 10 minutes ago — older than the 300s
    # default freshness window.
    stale_observed_at = now_utc() - timedelta(minutes=10)
    engine._mark_price_cache["ETH/USDT"] = MarkPriceEntry(
        price=Decimal("2500"),
        observed_at=stale_observed_at,
    )
    assert engine._get_cached_mark_price("ETH/USDT") is None
    # Pin the cache entry is still there — only the read enforces freshness.
    assert "ETH/USDT" in engine._mark_price_cache


async def test_get_cached_mark_price_respects_custom_max_age(
    tmp_path: Path,
) -> None:
    """An explicit ``max_age_seconds`` overrides the 300s default.

    Pins the API contract so the consumer at ``_build_cap_blocker_payload``
    can dial freshness independently of the cycle interval.
    """
    from src.runtime.engine import MarkPriceEntry

    proposal = make_proposal(proposal_id="ff_mark_custom_age", composite=2.0)
    engine, _ = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    # Inject an entry 60 seconds old.
    engine._mark_price_cache["ETH/USDT"] = MarkPriceEntry(
        price=Decimal("2500"),
        observed_at=now_utc() - timedelta(seconds=60),
    )
    # Permissive window — entry passes.
    assert engine._get_cached_mark_price("ETH/USDT", max_age_seconds=120) == Decimal(
        "2500"
    )
    # Restrictive window — entry fails.
    assert engine._get_cached_mark_price("ETH/USDT", max_age_seconds=30) is None


async def test_build_cap_blocker_payload_consumes_mark_cache(
    tmp_path: Path,
) -> None:
    """A primed mark cache feeds the cap-blocker ``unrealized_pnl_percent``.

    Long-side math: ``(mark - entry)/entry × 100``. Entry 50000, mark
    52500 → +5.0% unrealized.
    """
    proposal = make_proposal(proposal_id="ff_cap_consumes_cache", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    open_trade = make_trade(
        trade_id="t-cache",
        symbol="ETH/USDT",
        side="long",
        entry="50000",
    )
    engine._remember_mark_price("ETH/USDT", Decimal("52500"))
    payload = await engine._build_cap_blocker_payload(
        open_trades=[open_trade],
        cap=2,
        reason="total_cap",
    )
    assert len(payload) == 1
    assert payload[0]["unrealized_pnl_percent"] == pytest.approx(5.0, rel=1e-9)
    # Still zero exchange calls — the cache is the source.
    mocks["exchange"].get_ticker.assert_not_awaited()


async def test_build_cap_blocker_payload_short_side_uses_inverse_pnl_sign(
    tmp_path: Path,
) -> None:
    """Short-side math: ``(entry - mark)/entry × 100`` (mirrors ``pnl_for_trade``).

    Entry 50000, mark 49000 → +2.0% for a short. The sign convention
    must match the autopsy / backtest engines so dashboards rendering
    blocker PnL line up with closed-trade PnL.
    """
    proposal = make_proposal(proposal_id="ff_cap_short_sign", composite=2.0)
    engine, _ = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    open_trade = make_trade(
        trade_id="t-short",
        symbol="BNB/USDT",
        side="short",
        entry="50000",
    )
    engine._remember_mark_price("BNB/USDT", Decimal("49000"))
    payload = await engine._build_cap_blocker_payload(
        open_trades=[open_trade],
        cap=2,
        reason="symbol_cap",
    )
    assert payload[0]["unrealized_pnl_percent"] == pytest.approx(2.0, rel=1e-9)


async def test_symbol_cap_rejection_carries_symbol_cap_final_state(
    tmp_path: Path,
) -> None:
    """Per-symbol cap rejection promotes the record to
    ``gate_rejected_symbol_cap`` and only lists same-symbol blockers."""
    existing = make_trade(
        trade_id="t-bnb-existing",
        symbol="BNB/USDT",
        side="short",
    )
    proposal = make_proposal(
        proposal_id="ff_sym_cap",
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
        open_trades=[existing],
    )
    await engine.run_cycle()
    record = mocks["history"].load("ff_sym_cap")
    assert record.final_state == ProposalFinalState.GATE_REJECTED_SYMBOL_CAP.value

    rejections = mocks["activity_log"].filter(
        event_type=ActivityEventType.PROPOSAL_REJECTED
    )
    cap_rejection = next(
        e for e in rejections if e.details.get("gate_reason") == "symbol_cap"
    )
    assert cap_rejection.details["record_id"] == "ff_sym_cap"
    blockers = cap_rejection.details["blocking_trades"]
    assert len(blockers) == 1
    assert blockers[0]["trade_id"] == "t-bnb-existing"
    assert blockers[0]["symbol"] == "BNB/USDT"


async def test_accepted_proposal_advances_to_trade_opened_final_state(
    tmp_path: Path,
) -> None:
    """A proposal that clears every gate and fills lands in
    ``final_state=trade_opened``."""
    proposal = make_proposal(proposal_id="ff_opened", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    await engine.run_cycle()
    record = mocks["history"].load("ff_opened")
    assert record.final_state == ProposalFinalState.TRADE_OPENED.value

    # POSITION_OPENED event carries the record_id join key.
    opened_events = mocks["activity_log"].filter(
        event_type=ActivityEventType.POSITION_OPENED
    )
    assert len(opened_events) == 1
    assert opened_events[0].details["record_id"] == "ff_opened"


async def test_position_closed_event_carries_record_id(tmp_path: Path) -> None:
    """When a trade closes, the POSITION_CLOSED event carries the
    record_id join key and the record advances to ``outcome_linked``."""
    proposal = make_proposal(proposal_id="ff_closed", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    # Run the cycle that opens the trade.
    await engine.run_cycle()

    # Now configure trader to report an SL exit on the next monitor pass.
    trader = mocks["trader"]
    # Capture the trade just opened to feed the SL exit branch.
    captured_trade = make_trade(
        trade_id="t-BTC/USDT-long",
        symbol="BTC/USDT",
        side="long",
        entry="50000",
        quantity="0.1",
        status="open",
    )
    trader.get_open_trades.return_value = [captured_trade]
    closed_trade = make_trade(
        trade_id="t-BTC/USDT-long",
        symbol="BTC/USDT",
        side="long",
        entry="50000",
        quantity="0.1",
        exit_price="49500",
        pnl_percent=-1.0,
        status="closed",
    )
    trader.check_exit_conditions.return_value = (True, "stop_loss")
    trader.close_position = AsyncMock(return_value=closed_trade)

    # Trigger a monitor-only cycle: no new proposals.
    mocks["proposal_engine"].propose_bitcoin = AsyncMock(return_value=None)
    mocks["proposal_engine"].propose_altcoins = AsyncMock(return_value=[])
    await engine.run_cycle()

    closed_events = mocks["activity_log"].filter(
        event_type=ActivityEventType.POSITION_CLOSED
    )
    assert len(closed_events) >= 1
    last_close = closed_events[-1]
    assert last_close.details["record_id"] == "ff_closed"
    assert last_close.details["proposal_id"] == "ff_closed"

    record = mocks["history"].load("ff_closed")
    assert record.final_state == ProposalFinalState.OUTCOME_LINKED.value


# =============================================================================
# cross-account-risk-policy: per-account aggregate cap gate
# =============================================================================


def _make_risk_sub(
    *,
    id: str = "rsi_lab",
    sizing_mode: str = "fixed_notional",
    risk_budget_pct: Decimal | None = None,
    sizing_balance: Decimal | None = None,
    min_notional_per_trade: Decimal | None = None,
    max_gross_notional: Decimal | None = None,
    max_notional_per_trade: Decimal | None = None,
    min_stop_distance_bps: int | None = None,
    max_open_stop_risk: Decimal | None = None,
    max_time_in_position_hours: int | None = None,
    stale_position_action: str | None = None,
    open_unrealized_drawdown_limit_pct: Decimal | None = None,
    open_stop_risk_limit_pct: Decimal | None = None,
    daily_loss_limit_pct: Decimal | None = None,
    quote_currency: str = "USDT",
) -> SubAccount:
    """SubAccount factory for the risk-policy gate tests."""
    return SubAccount(
        id=id,
        name=id,
        mode="paper",
        exchange_ref="default",
        capital_policy=CapitalPolicy(
            initial_balance={quote_currency: Decimal("10000")},
            sizing_balance=sizing_balance,
            quote_currency=quote_currency,
        ),
        risk_policy=RiskPolicy(
            sizing_mode=sizing_mode,  # type: ignore[arg-type]
            risk_budget_pct=risk_budget_pct,
            min_notional_per_trade=min_notional_per_trade,
            max_gross_notional=max_gross_notional,
            max_notional_per_trade=max_notional_per_trade,
            min_stop_distance_bps=min_stop_distance_bps,
            max_open_stop_risk=max_open_stop_risk,
            max_time_in_position_hours=max_time_in_position_hours,
            stale_position_action=stale_position_action,  # type: ignore[arg-type]
            open_unrealized_drawdown_limit_pct=open_unrealized_drawdown_limit_pct,
            open_stop_risk_limit_pct=open_stop_risk_limit_pct,
            daily_loss_limit_pct=daily_loss_limit_pct,
        ),
    )


async def test_risk_budget_sizing_resizes_before_account_aggregate_cap(
    tmp_path: Path,
) -> None:
    """DEBT-068(a): risk-budget mode replaces the strategy's raw quantity.

    The raw strategy quantity would breach the account aggregate notional cap,
    but the risk-budget-sized quantity fits and proceeds to execution.
    """
    proposal = make_proposal(
        proposal_id="risk-sized",
        symbol="BTC/USDT",
        composite=2.0,
        entry="50000",
        sl="49000",
        quantity="0.2",  # raw notional = 10,000; risk-budget qty = 0.05.
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    sub = _make_risk_sub(
        sizing_mode="risk_budget",
        risk_budget_pct=Decimal("0.005"),
        max_gross_notional=Decimal("3000"),
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()

    assert result.positions_opened == 1
    opened_position = mocks["trader"].open_position.await_args.args[0]
    assert opened_position.quantity == Decimal("0.05")
    record = mocks["history"].load("risk-sized")
    assert record.final_state == ProposalFinalState.TRADE_OPENED.value


async def test_risk_budget_sizing_rejects_stop_too_tight(
    tmp_path: Path,
) -> None:
    """Risk-budget sizing rejects proposals below the stop-distance floor."""
    proposal = make_proposal(
        proposal_id="risk-tight-stop",
        symbol="BTC/USDT",
        composite=2.0,
        entry="50000",
        sl="49999",
        quantity="0.2",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    sub = _make_risk_sub(
        sizing_mode="risk_budget",
        risk_budget_pct=Decimal("0.005"),
        min_stop_distance_bps=25,
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()

    assert result.proposals_rejected == 1
    mocks["trader"].open_position.assert_not_called()
    record = mocks["history"].load("risk-tight-stop")
    assert record.final_state == ProposalFinalState.GATE_REJECTED_RISK_SIZING.value
    assert "stop distance" in (record.rejection_reason or "")
    event = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.PROPOSAL_REJECTED
        )
        if e.details.get("gate_reason") == "risk_sizing"
    ][0]
    assert event.details["risk_sizing_reason"] == "stop_too_tight"


async def test_risk_budget_sizing_falls_back_to_explicit_sizing_balance(
    tmp_path: Path,
) -> None:
    """Missing live balance uses explicit ``CapitalPolicy.sizing_balance``."""
    proposal = make_proposal(
        proposal_id="risk-sized-fallback",
        symbol="BTC/USDT",
        composite=2.0,
        entry="50000",
        sl="49000",
        quantity="0.2",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    mocks["trader"].get_balances = AsyncMock(return_value={})
    sub = _make_risk_sub(
        sizing_mode="risk_budget",
        risk_budget_pct=Decimal("0.005"),
        sizing_balance=Decimal("8000"),
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()

    assert result.positions_opened == 1
    opened_position = mocks["trader"].open_position.await_args.args[0]
    assert opened_position.quantity == Decimal("0.04")


async def test_account_aggregate_cap_gate_live_rejects_over_notional(
    tmp_path: Path,
) -> None:
    """Live mode + ``max_gross_notional`` breached → hard-block rejection."""
    existing = make_trade(
        trade_id="t-existing",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="2",  # notional = 4000
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    proposal = make_proposal(
        proposal_id="rsi-1",
        symbol="BTC/USDT",
        composite=2.0,
        entry="50000",
        quantity="0.05",  # notional = 2500
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[existing],
    )
    engine.mode = "live"
    sub = _make_risk_sub(max_gross_notional=Decimal("5000"))
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.proposals_rejected == 1
    mocks["trader"].open_position.assert_not_called()

    record = mocks["history"].load("rsi-1")
    assert (
        record.final_state
        == ProposalFinalState.GATE_REJECTED_ACCOUNT_AGGREGATE_CAP.value
    )
    assert "gross_notional" in (record.rejection_reason or "")


async def test_account_aggregate_cap_gate_paper_emits_advisory_but_continues(
    tmp_path: Path,
) -> None:
    """Paper mode: cap breach is advisory-with-event; proposal still executes.

    Pins the resolved 2026-05-13 Open Decision: paper-first means caps
    are advisory in paper, hard-blocking in live. The proposal record
    must NOT carry the ``gate_rejected_account_aggregate_cap`` terminal
    when the engine is in paper mode — the advisory event lives in the
    activity log only.
    """
    existing = make_trade(
        trade_id="t-existing",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="2",
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    proposal = make_proposal(
        proposal_id="rsi-paper",
        symbol="BTC/USDT",
        composite=2.0,
        entry="50000",
        quantity="0.05",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[existing],
    )
    engine.mode = "paper"  # explicit
    sub = _make_risk_sub(max_gross_notional=Decimal("5000"))
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    # Proposal executes; cap is advisory only.
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_awaited_once()

    # Advisory event present in activity log (DEBT-068(g): dedicated
    # RISK_CAP_ADVISORY event type, advisory=True kept as discriminator).
    advisories = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.RISK_CAP_ADVISORY
        )
        if e.details.get("gate_reason") == "account_aggregate_cap"
    ]
    assert len(advisories) == 1
    assert advisories[0].details["advisory"] is True
    assert advisories[0].details["mode"] == "paper"


async def test_account_aggregate_cap_gate_open_stop_risk_breach_live(
    tmp_path: Path,
) -> None:
    """``max_open_stop_risk`` independently triggers rejection in live mode.

    Two-cap branch coverage: notional is well within bounds, but the
    aggregated worst-case stop risk would exceed the cap.
    """
    existing = make_trade(
        trade_id="t-existing-stop",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="0.5",  # notional = 1000
    ).model_copy(
        update={
            "sub_account_id": "rsi_lab",
            "stop_loss": Decimal("1800"),  # stop_risk = 200 * 0.5 = 100
        }
    )
    proposal = make_proposal(
        proposal_id="rsi-stop",
        symbol="BTC/USDT",
        composite=2.0,
        entry="50000",
        sl="49000",  # stop distance = 1000
        quantity="0.02",  # contribution = 1000 * 0.02 = 20
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[existing],
    )
    engine.mode = "live"
    sub = _make_risk_sub(max_open_stop_risk=Decimal("50"))  # 100 alone > 50
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.proposals_rejected == 1
    record = mocks["history"].load("rsi-stop")
    assert (
        record.final_state
        == ProposalFinalState.GATE_REJECTED_ACCOUNT_AGGREGATE_CAP.value
    )
    assert "open_stop_risk" in (record.rejection_reason or "")


async def test_account_aggregate_cap_gate_under_caps_passes(tmp_path: Path) -> None:
    """When the post-fill totals stay under both caps, the proposal continues."""
    existing = make_trade(
        trade_id="t-small",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="0.1",  # notional = 200
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    proposal = make_proposal(
        proposal_id="rsi-ok",
        symbol="BTC/USDT",
        composite=2.0,
        entry="50000",
        quantity="0.01",  # notional = 500
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[existing],
    )
    engine.mode = "live"
    sub = _make_risk_sub(max_gross_notional=Decimal("10000"))
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_awaited_once()


async def test_account_aggregate_cap_gate_no_caps_configured_is_noop(
    tmp_path: Path,
) -> None:
    """Sub-account with no aggregate caps falls through cleanly."""
    proposal = make_proposal(proposal_id="rsi-none", composite=2.0).model_copy(
        update={"sub_account_id": "rsi_lab"}
    )
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    engine.mode = "live"
    sub = _make_risk_sub()
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1


# =============================================================================
# cross-account-risk-policy: stale-position block gate
# =============================================================================


async def test_stale_position_block_gate_live_rejects_when_stale_trade_open(
    tmp_path: Path,
) -> None:
    """Live mode + open trade > ``max_time_in_position_hours`` → reject new entries."""
    # Trade opened 100 hours ago; cap at 24h.
    stale_trade = make_trade(
        trade_id="t-stale",
        symbol="ETH/USDT",
        side="long",
    ).model_copy(
        update={
            "sub_account_id": "rsi_lab",
            "entry_time": now_utc() - timedelta(hours=100),
        }
    )
    proposal = make_proposal(proposal_id="rsi-blocked", composite=2.0).model_copy(
        update={"sub_account_id": "rsi_lab"}
    )

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[stale_trade],
    )
    engine.mode = "live"
    sub = _make_risk_sub(
        max_time_in_position_hours=24,
        stale_position_action="block_new_entries",
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.proposals_rejected == 1
    mocks["trader"].open_position.assert_not_called()

    record = mocks["history"].load("rsi-blocked")
    assert (
        record.final_state
        == ProposalFinalState.GATE_REJECTED_STALE_POSITION_BLOCK.value
    )
    assert "stale_position_block" in (record.rejection_reason or "")


async def test_stale_position_block_gate_paper_advisory_only(tmp_path: Path) -> None:
    """Paper mode: stale-position block is advisory-with-event; proposal continues."""
    stale_trade = make_trade(
        trade_id="t-stale-paper",
        symbol="ETH/USDT",
        side="long",
    ).model_copy(
        update={
            "sub_account_id": "rsi_lab",
            "entry_time": now_utc() - timedelta(hours=100),
        }
    )
    proposal = make_proposal(proposal_id="rsi-paper-stale", composite=2.0).model_copy(
        update={"sub_account_id": "rsi_lab"}
    )

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[stale_trade],
    )
    engine.mode = "paper"
    sub = _make_risk_sub(
        max_time_in_position_hours=24,
        stale_position_action="block_new_entries",
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1

    advisories = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.PROPOSAL_REJECTED
        )
        if e.details.get("gate_reason") == "stale_position_block"
    ]
    assert len(advisories) == 1
    assert advisories[0].details["advisory"] is True


async def test_stale_position_block_gate_no_action_configured_is_noop(
    tmp_path: Path,
) -> None:
    """Cap configured but action != block_new_entries → gate is a no-op."""
    stale_trade = make_trade(
        trade_id="t-stale-noaction",
        symbol="ETH/USDT",
        side="long",
    ).model_copy(
        update={
            "sub_account_id": "rsi_lab",
            "entry_time": now_utc() - timedelta(hours=100),
        }
    )
    proposal = make_proposal(proposal_id="rsi-stale-alert", composite=2.0).model_copy(
        update={"sub_account_id": "rsi_lab"}
    )

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[stale_trade],
    )
    engine.mode = "live"
    # ``alert_only`` is handled elsewhere; this gate must NOT reject.
    sub = _make_risk_sub(
        max_time_in_position_hours=24,
        stale_position_action="alert_only",
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1


async def test_stale_position_block_gate_fresh_trade_passes(tmp_path: Path) -> None:
    """A fresh open trade (under cap) does not block new entries."""
    fresh_trade = make_trade(
        trade_id="t-fresh",
        symbol="ETH/USDT",
        side="long",
    ).model_copy(
        update={
            "sub_account_id": "rsi_lab",
            "entry_time": now_utc() - timedelta(hours=1),
        }
    )
    proposal = make_proposal(proposal_id="rsi-fresh", composite=2.0).model_copy(
        update={"sub_account_id": "rsi_lab"}
    )

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[fresh_trade],
    )
    engine.mode = "live"
    sub = _make_risk_sub(
        max_time_in_position_hours=24,
        stale_position_action="block_new_entries",
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1


async def test_stale_position_block_gate_handles_naive_entry_time_defensively(
    tmp_path: Path,
) -> None:
    """Naive ``entry_time`` is treated as UTC instead of crashing.

    Other call sites in ``engine.py`` (line ~2374) and
    ``correlation_governor.py`` (lines 76 / 106) defensively wrap
    ``trade.entry_time`` in ``ensure_utc()`` before doing tz-aware
    arithmetic. Slice 1 of cross-account-risk-policy missed this site;
    a naive datetime here would raise
    ``TypeError: can't subtract offset-naive and offset-aware datetimes``
    inside the stale-position block gate.

    Pin the defense: with a naive ``entry_time`` 100h in the past and a
    24h cap, the gate must compute age correctly (treating the naive
    timestamp as UTC) and reject the proposal in live mode.
    """
    # Naive datetime (no tzinfo) — 100 hours before now_utc().
    naive_entry = (now_utc() - timedelta(hours=100)).replace(tzinfo=None)
    assert naive_entry.tzinfo is None  # sanity-check the construction

    stale_trade = make_trade(
        trade_id="t-stale-naive",
        symbol="ETH/USDT",
        side="long",
    ).model_copy(
        update={
            "sub_account_id": "rsi_lab",
            "entry_time": naive_entry,
        }
    )
    proposal = make_proposal(
        proposal_id="rsi-naive-blocked",
        composite=2.0,
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[stale_trade],
    )
    engine.mode = "live"
    sub = _make_risk_sub(
        max_time_in_position_hours=24,
        stale_position_action="block_new_entries",
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    # Must not raise TypeError on naive-vs-aware datetime subtraction.
    result = await engine.run_cycle()

    # Naive 100h-ago entry should be treated as UTC and exceed the 24h cap.
    assert result.proposals_rejected == 1
    mocks["trader"].open_position.assert_not_called()

    record = mocks["history"].load("rsi-naive-blocked")
    assert (
        record.final_state
        == ProposalFinalState.GATE_REJECTED_STALE_POSITION_BLOCK.value
    )
    assert "stale_position_block" in (record.rejection_reason or "")


# =============================================================================
# cross-account-risk-policy: stale-position MONITOR actions (DEBT-068(e))
# =============================================================================


def _make_recoverable_stale_trade(
    *,
    trade_id: str,
    hours_old: float,
    sub_account_id: str = "rsi_lab",
) -> TradeHistory:
    """An open trade old enough to be stale with a CLEAN reconciliation row.

    Both SL and TP plus a ``performance_record_id`` are set so
    ``classify_open_trade`` returns ``MONITORABLE`` — the only state that
    reaches the ``auto_close`` enforcement path. ``entry_time`` is
    ``hours_old`` in the past so the monitor's age computation trips
    against ``now_utc()`` without monkeypatching the clock.
    """
    return make_trade(
        trade_id=trade_id,
        symbol="ETH/USDT",
        side="long",
        performance_record_id="perf-1",
    ).model_copy(
        update={
            "sub_account_id": sub_account_id,
            "entry_time": now_utc() - timedelta(hours=hours_old),
            "stop_loss": Decimal("48000"),
            "take_profit": Decimal("55000"),
        }
    )


async def test_stale_auto_close_closes_recon_ok_position(tmp_path: Path) -> None:
    """auto_close + stale + reconciliation OK → close at market with
    ``reason="stale_age_cap"`` and emit STALE_POSITION_AUTO_CLOSED."""
    stale_trade = _make_recoverable_stale_trade(trade_id="t-stale-ac", hours_old=30)
    closed = stale_trade.model_copy(
        update={
            "status": "closed",
            "exit_price": Decimal("50000"),
            "exit_quantity": Decimal("0.1"),
            "close_reason": "stale_age_cap",
            "pnl_percent": 0.0,
        }
    )

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        open_trades=[stale_trade],
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    mocks["trader"].close_position.return_value = closed
    sub = _make_risk_sub(
        max_time_in_position_hours=24,
        stale_position_action="auto_close",
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()

    assert result.positions_closed == 1
    mocks["trader"].close_position.assert_awaited_once_with(
        "t-stale-ac", Decimal("50000"), reason="stale_age_cap"
    )

    auto_closed = mocks["activity_log"].filter(
        event_type=ActivityEventType.STALE_POSITION_AUTO_CLOSED
    )
    assert len(auto_closed) == 1
    details = auto_closed[0].details
    assert details["trade_id"] == "t-stale-ac"
    assert details["reconciliation_state"] == OpenTradeState.MONITORABLE.value
    assert details["exit_price"] == "50000"

    # The canonical POSITION_CLOSED carries reason=stale_age_cap.
    closes = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.POSITION_CLOSED
        )
        if e.details.get("trade_id") == "t-stale-ac"
    ]
    assert len(closes) == 1
    assert closes[0].details["reason"] == "stale_age_cap"


async def test_stale_auto_close_leaves_fresh_position_open(tmp_path: Path) -> None:
    """auto_close + fresh position (age < cap) → not closed, no events."""
    fresh_trade = _make_recoverable_stale_trade(trade_id="t-fresh-ac", hours_old=1)

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        open_trades=[fresh_trade],
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    sub = _make_risk_sub(
        max_time_in_position_hours=24,
        stale_position_action="auto_close",
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()

    assert result.positions_closed == 0
    mocks["trader"].close_position.assert_not_called()
    assert (
        mocks["activity_log"].filter(
            event_type=ActivityEventType.STALE_POSITION_AUTO_CLOSED
        )
        == []
    )
    assert (
        mocks["activity_log"].filter(
            event_type=ActivityEventType.STALE_POSITION_DETECTED
        )
        == []
    )


async def test_stale_auto_close_degraded_downgrades_to_block(tmp_path: Path) -> None:
    """auto_close + stale + reconciliation ``degraded`` → NOT closed,
    downgrade-to-block operator event emitted."""
    # No SL/TP on the row → classify_open_trade returns DEGRADED.
    stale_trade = make_trade(
        trade_id="t-stale-degraded",
        symbol="ETH/USDT",
        side="long",
        performance_record_id="perf-1",
    ).model_copy(
        update={
            "sub_account_id": "rsi_lab",
            "entry_time": now_utc() - timedelta(hours=30),
        }
    )

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        open_trades=[stale_trade],
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    sub = _make_risk_sub(
        max_time_in_position_hours=24,
        stale_position_action="auto_close",
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()

    assert result.positions_closed == 0
    mocks["trader"].close_position.assert_not_called()
    assert (
        mocks["activity_log"].filter(
            event_type=ActivityEventType.STALE_POSITION_AUTO_CLOSED
        )
        == []
    )

    detected = mocks["activity_log"].filter(
        event_type=ActivityEventType.STALE_POSITION_DETECTED
    )
    assert len(detected) == 1
    details = detected[0].details
    assert details["reconciliation_state"] == OpenTradeState.DEGRADED.value
    assert details["resolution"] == "degraded_block_new_entries"
    assert details["priority"] == "high"


async def test_stale_auto_close_unrecoverable_alerts_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """auto_close + stale + reconciliation ``unrecoverable`` → NEVER closed,
    high-priority alert emitted."""
    stale_trade = _make_recoverable_stale_trade(trade_id="t-stale-unrec", hours_old=30)

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        open_trades=[stale_trade],
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    sub = _make_risk_sub(
        max_time_in_position_hours=24,
        stale_position_action="auto_close",
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    # A valid TradeHistory cannot omit its core fields (entry_price/size/
    # symbol/side are all required by the model), so the unrecoverable
    # state is forced at the classifier boundary.
    # CAH-15 Slice 2: ``_classify_trade_reconciliation`` moved to PositionMonitor.
    monkeypatch.setattr(
        engine._position_monitor,
        "_classify_trade_reconciliation",
        lambda trade: OpenTradeState.UNRECOVERABLE,
    )

    result = await engine.run_cycle()

    assert result.positions_closed == 0
    mocks["trader"].close_position.assert_not_called()
    assert (
        mocks["activity_log"].filter(
            event_type=ActivityEventType.STALE_POSITION_AUTO_CLOSED
        )
        == []
    )

    detected = mocks["activity_log"].filter(
        event_type=ActivityEventType.STALE_POSITION_DETECTED
    )
    assert len(detected) == 1
    details = detected[0].details
    assert details["reconciliation_state"] == OpenTradeState.UNRECOVERABLE.value
    assert details["resolution"] == "unrecoverable_operator_only"
    assert details["priority"] == "high"


async def test_monitor_multi_rung_single_pass_closes_each_exactly_once(
    tmp_path: Path,
) -> None:
    """CAH-15 Slice 2 ADR CHANGE A: SL/TP + time-stop + stale-age + orphan
    force-close all in ONE monitor pass close exactly four distinct trades,
    once each — no double-count, no double-close, no fall-through.

    The four close rungs are mutually exclusive via ``continue`` and feed a
    single ``closed_count`` that is written once to ``result.positions_closed``.
    This is the regression most likely to break under the PositionMonitor
    extraction, so it is asserted explicitly across all four rungs at once.
    """
    # A: SL/TP hit (check_exit_conditions returns an exit before time-stop).
    trade_sl = make_trade(trade_id="A-sl", symbol="BTC/USDT", side="long")
    # B: aged far beyond its default 1h/48-bar time-stop window (make_trade's
    # default entry_time is weeks old) and NOT orphaned -> time-stop.
    trade_ts = make_trade(trade_id="B-ts", symbol="SOL/USDT", side="long")
    # C: 30h old -> past the 24h stale cap but inside the 48h time-stop window,
    # reconciliation MONITORABLE -> stale auto_close.
    trade_stale = _make_recoverable_stale_trade(trade_id="C-stale", hours_old=30)
    # D: missing in-memory position state -> orphan watchdog; pre-seeded to one
    # strike below the threshold so THIS pass force-closes it.
    trade_orphan = make_trade(trade_id="D-orphan", symbol="XRP/USDT", side="short")

    open_trades = [trade_sl, trade_ts, trade_stale, trade_orphan]
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        open_trades=open_trades,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    trader = mocks["trader"]

    def _closed(trade: TradeHistory, price: Decimal, pnl: float) -> TradeHistory:
        return trade.model_copy(
            update={
                "status": "closed",
                "exit_price": price,
                "exit_quantity": trade.entry_quantity,
                "pnl_percent": pnl,
            }
        )

    by_id = {t.id: t for t in open_trades}

    trader.get_open_position = MagicMock(
        side_effect=lambda trade_id: None if trade_id == "D-orphan" else object()
    )
    trader.check_exit_conditions = MagicMock(
        side_effect=lambda trade_id, price: (
            (True, "stop_loss") if trade_id == "A-sl" else (False, None)
        )
    )

    async def _close(trade_id: str, price: Decimal, *, reason: str) -> TradeHistory:
        return _closed(by_id[trade_id], price, 0.0)

    trader.close_position = AsyncMock(side_effect=_close)

    async def _force_close(trade_id: str, price: Decimal) -> TradeHistory:
        return _closed(by_id[trade_id], price, 1.0)

    trader.force_close_orphan = AsyncMock(side_effect=_force_close)

    sub = _make_risk_sub(
        max_time_in_position_hours=24,
        stale_position_action="auto_close",
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": trader},
    )  # type: ignore[assignment]

    # One strike below threshold -> this pass is the force-close strike.
    engine._position_monitor._orphan_strike_counts["D-orphan"] = (
        ORPHAN_AUTO_CLOSE_THRESHOLD - 1
    )

    result = await engine.run_cycle()

    # CHANGE A: exactly four closes, one per rung, single accumulation.
    assert result.positions_closed == 4

    # No double-close: each market close fired once with its own reason, and the
    # orphan path force-closed exactly once.
    close_reasons = sorted(
        call.kwargs["reason"] for call in trader.close_position.await_args_list
    )
    assert close_reasons == ["stale_age_cap", "stop_loss", "time_stop"]
    closed_ids = {call.args[0] for call in trader.close_position.await_args_list}
    assert closed_ids == {"A-sl", "B-ts", "C-stale"}
    trader.force_close_orphan.assert_awaited_once()
    assert trader.force_close_orphan.await_args.args[0] == "D-orphan"

    # Each rung emitted its canonical event exactly once.
    log = mocks["activity_log"]
    assert len(log.filter(event_type=ActivityEventType.POSITION_TIME_STOPPED)) == 1
    assert len(log.filter(event_type=ActivityEventType.STALE_POSITION_AUTO_CLOSED)) == 1
    assert (
        len(log.filter(event_type=ActivityEventType.POSITION_ORPHAN_FORCE_CLOSED)) == 1
    )
    # The orphan counter was pruned after the force-close.
    assert "D-orphan" not in engine._orphan_strike_counts


async def test_stale_alert_only_emits_event_without_closing(tmp_path: Path) -> None:
    """alert_only + stale → STALE_POSITION_DETECTED, position NOT closed."""
    stale_trade = _make_recoverable_stale_trade(trade_id="t-stale-alert", hours_old=30)

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        open_trades=[stale_trade],
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    sub = _make_risk_sub(
        max_time_in_position_hours=24,
        stale_position_action="alert_only",
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()

    assert result.positions_closed == 0
    mocks["trader"].close_position.assert_not_called()

    detected = mocks["activity_log"].filter(
        event_type=ActivityEventType.STALE_POSITION_DETECTED
    )
    assert len(detected) == 1
    assert detected[0].details["resolution"] == "alert_only"
    # No high-priority flag and no auto-close event on the alert-only path.
    assert "priority" not in detected[0].details


async def test_stale_block_new_entries_emits_detected_event_from_monitor(
    tmp_path: Path,
) -> None:
    """block_new_entries + stale → monitor emits STALE_POSITION_DETECTED
    (operator visibility) without closing; enforcement stays in the gate."""
    stale_trade = _make_recoverable_stale_trade(trade_id="t-stale-block", hours_old=30)

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        open_trades=[stale_trade],
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    sub = _make_risk_sub(
        max_time_in_position_hours=24,
        stale_position_action="block_new_entries",
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()

    assert result.positions_closed == 0
    mocks["trader"].close_position.assert_not_called()

    detected = mocks["activity_log"].filter(
        event_type=ActivityEventType.STALE_POSITION_DETECTED
    )
    # Exactly one per monitor pass — no double-emit.
    assert len(detected) == 1
    assert detected[0].details["resolution"] == "block_new_entries"


async def test_stale_no_action_configured_is_monitor_noop(tmp_path: Path) -> None:
    """No ``stale_position_action`` → monitor does nothing stale-related."""
    stale_trade = _make_recoverable_stale_trade(trade_id="t-stale-none", hours_old=30)

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        open_trades=[stale_trade],
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    # Cap set but no action → existing behavior unchanged (no enforcement).
    sub = _make_risk_sub(
        max_time_in_position_hours=24,
        stale_position_action=None,
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()

    assert result.positions_closed == 0
    mocks["trader"].close_position.assert_not_called()
    assert (
        mocks["activity_log"].filter(
            event_type=ActivityEventType.STALE_POSITION_DETECTED
        )
        == []
    )
    assert (
        mocks["activity_log"].filter(
            event_type=ActivityEventType.STALE_POSITION_AUTO_CLOSED
        )
        == []
    )


async def test_stale_auto_close_does_not_double_close_after_sl(
    tmp_path: Path,
) -> None:
    """SL/TP precedence: a stale auto_close trade that ALSO hits SL this
    pass is closed via SL, not double-closed by the stale path."""
    stale_trade = _make_recoverable_stale_trade(trade_id="t-stale-sl", hours_old=30)
    sl_closed = stale_trade.model_copy(
        update={
            "status": "closed",
            "exit_price": Decimal("48000"),
            "exit_quantity": Decimal("0.1"),
            "close_reason": "stop_loss",
            "pnl_percent": -4.0,
        }
    )

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        open_trades=[stale_trade],
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    mocks["trader"].check_exit_conditions.return_value = (True, "stop_loss")
    mocks["trader"].close_position.return_value = sl_closed
    sub = _make_risk_sub(
        max_time_in_position_hours=24,
        stale_position_action="auto_close",
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()

    # Closed exactly once, by SL — not double-counted by the stale path.
    assert result.positions_closed == 1
    mocks["trader"].close_position.assert_awaited_once_with(
        "t-stale-sl", Decimal("50000"), reason="stop_loss"
    )
    assert (
        mocks["activity_log"].filter(
            event_type=ActivityEventType.STALE_POSITION_AUTO_CLOSED
        )
        == []
    )
    assert (
        mocks["activity_log"].filter(
            event_type=ActivityEventType.STALE_POSITION_DETECTED
        )
        == []
    )


# =============================================================================
# cross-account-risk-policy: global aggregate cap gate (DEBT-068(b))
# =============================================================================


async def test_global_cap_gate_disabled_is_noop_even_when_breached(
    tmp_path: Path,
) -> None:
    """``GlobalRiskPolicy.enabled=False`` (default) → gate never fires.

    Even when the cross-account totals would breach every cap, an absent
    / disabled global policy must leave the proposal untouched and emit
    no advisory event — the "no global gate" default behaviour.
    """
    existing = make_trade(
        trade_id="t-eth-1",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="5",  # notional = 10000
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    proposal = make_proposal(
        proposal_id="rsi-global-disabled",
        symbol="ETH/USDT",
        signal="long",
        composite=2.0,
        entry="2000",
        sl="1950",
        tp="2100",
        quantity="5",  # notional = 10000
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=10,
        ),
        open_trades=[existing],
        ticker_price=Decimal("2000"),
    )
    engine.mode = "live"
    sub = _make_risk_sub()
    # No global_policy → defaults to a disabled GlobalRiskPolicy().
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_awaited_once()

    advisories = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.RISK_CAP_ADVISORY
        )
        if e.details.get("gate_reason") == "global_cap"
    ]
    assert advisories == []


async def test_global_cap_gate_paper_emits_advisory_but_continues(
    tmp_path: Path,
) -> None:
    """Paper mode + enabled global cap breach → advisory-with-event, no block.

    Per spec §"Global Symbol/Side Caps", paper mode is advisory-only in
    v1 so strategy-isolated paper measurements are not contaminated by
    portfolio-level throttling. The proposal still executes; an advisory
    event with ``advisory=True`` lands in the activity log.
    """
    existing = make_trade(
        trade_id="t-eth-long",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="2",  # notional = 4000
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    proposal = make_proposal(
        proposal_id="rsi-global-paper",
        symbol="ETH/USDT",
        signal="long",
        composite=2.0,
        entry="2000",
        sl="1950",
        tp="2100",
        quantity="2",  # notional = 4000; symbol_side total = 8000 > 5000
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=10,
        ),
        open_trades=[existing],
        ticker_price=Decimal("2000"),
    )
    engine.mode = "paper"
    sub = _make_risk_sub()
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
        global_policy=GlobalRiskPolicy(
            enabled=True,
            max_gross_notional_per_symbol_side=Decimal("5000"),
        ),
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    # Proposal executes; the global cap is advisory only in paper.
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_awaited_once()

    advisories = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.RISK_CAP_ADVISORY
        )
        if e.details.get("gate_reason") == "global_cap"
    ]
    assert len(advisories) == 1
    assert advisories[0].details["advisory"] is True
    assert advisories[0].details["mode"] == "paper"

    # Record was NOT downgraded — it lands in proposal_opened / trade_opened.
    record = mocks["history"].load("rsi-global-paper")
    assert record.final_state != ProposalFinalState.GATE_REJECTED_GLOBAL_CAP.value


async def test_global_cap_gate_live_rejects_on_open_positions_count(
    tmp_path: Path,
) -> None:
    """Live mode: ``max_open_positions_per_symbol_side`` breach hard-blocks."""
    open_trades = [
        make_trade(
            trade_id="t-eth-1",
            symbol="ETH/USDT",
            side="long",
            entry="2000",
            quantity="0.1",
        ).model_copy(update={"sub_account_id": "rsi_lab"}),
        make_trade(
            trade_id="t-eth-2",
            symbol="ETH/USDT",
            side="long",
            entry="2000",
            quantity="0.1",
        ).model_copy(update={"sub_account_id": "rsi_lab"}),
    ]
    proposal = make_proposal(
        proposal_id="rsi-global-count",
        symbol="ETH/USDT",
        signal="long",
        composite=2.0,
        entry="2000",
        sl="1950",
        tp="2100",
        quantity="0.1",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=10,
        ),
        open_trades=open_trades,
        ticker_price=Decimal("2000"),
    )
    engine.mode = "live"
    sub = _make_risk_sub()
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
        global_policy=GlobalRiskPolicy(
            enabled=True,
            # 2 open + 1 new = 3 > cap of 2.
            max_open_positions_per_symbol_side=2,
        ),
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.proposals_rejected == 1
    mocks["trader"].open_position.assert_not_called()

    record = mocks["history"].load("rsi-global-count")
    assert record.final_state == ProposalFinalState.GATE_REJECTED_GLOBAL_CAP.value
    assert "open_positions_per_symbol_side" in (record.rejection_reason or "")


async def test_global_cap_gate_live_rejects_on_symbol_side_notional(
    tmp_path: Path,
) -> None:
    """Live mode: ``max_gross_notional_per_symbol_side`` breach hard-blocks."""
    existing = make_trade(
        trade_id="t-eth-long",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="2",  # notional = 4000
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    proposal = make_proposal(
        proposal_id="rsi-global-ssn",
        symbol="ETH/USDT",
        signal="long",
        composite=2.0,
        entry="2000",
        sl="1950",
        tp="2100",
        quantity="2",  # +4000; total 8000 > 5000
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=10,
        ),
        open_trades=[existing],
        ticker_price=Decimal("2000"),
    )
    engine.mode = "live"
    sub = _make_risk_sub()
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
        global_policy=GlobalRiskPolicy(
            enabled=True,
            max_gross_notional_per_symbol_side=Decimal("5000"),
        ),
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.proposals_rejected == 1
    record = mocks["history"].load("rsi-global-ssn")
    assert record.final_state == ProposalFinalState.GATE_REJECTED_GLOBAL_CAP.value
    assert "gross_notional_per_symbol_side" in (record.rejection_reason or "")


async def test_global_cap_gate_live_rejects_on_symbol_notional_both_sides(
    tmp_path: Path,
) -> None:
    """Live: ``max_gross_notional_per_symbol`` sums BOTH sides on the symbol.

    A delta-balanced book (long + short) stays under each per-side cap
    but still trips the symbol-level concentration cap.
    """
    open_trades = [
        make_trade(
            trade_id="t-eth-long",
            symbol="ETH/USDT",
            side="long",
            entry="2000",
            quantity="1",  # notional = 2000
        ).model_copy(update={"sub_account_id": "rsi_lab"}),
        make_trade(
            trade_id="t-eth-short",
            symbol="ETH/USDT",
            side="short",
            entry="2000",
            quantity="1.5",  # notional = 3000
        ).model_copy(update={"sub_account_id": "rsi_lab"}),
    ]
    proposal = make_proposal(
        proposal_id="rsi-global-sym",
        symbol="ETH/USDT",
        signal="long",
        composite=2.0,
        entry="2000",
        sl="1950",
        tp="2100",
        quantity="1.5",  # +3000; symbol total = 2000+3000+3000 = 8000 > 7000
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=10,
        ),
        open_trades=open_trades,
        ticker_price=Decimal("2000"),
    )
    engine.mode = "live"
    sub = _make_risk_sub()
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
        global_policy=GlobalRiskPolicy(
            enabled=True,
            # Per-side long total = 2000+3000 = 5000 (under per-side cap),
            # but symbol total = 8000 > 7000.
            max_gross_notional_per_symbol_side=Decimal("6000"),
            max_gross_notional_per_symbol=Decimal("7000"),
        ),
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.proposals_rejected == 1
    record = mocks["history"].load("rsi-global-sym")
    assert record.final_state == ProposalFinalState.GATE_REJECTED_GLOBAL_CAP.value
    assert "gross_notional_per_symbol" in (record.rejection_reason or "")


async def test_global_cap_gate_enabled_but_under_caps_passes(
    tmp_path: Path,
) -> None:
    """Enabled global caps with totals within bounds → no-op, proposal opens."""
    existing = make_trade(
        trade_id="t-eth-long",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="0.5",  # notional = 1000
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    proposal = make_proposal(
        proposal_id="rsi-global-ok",
        symbol="ETH/USDT",
        signal="long",
        composite=2.0,
        entry="2000",
        sl="1950",
        tp="2100",
        quantity="0.5",  # +1000; total 2000, count 2 — all under caps
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=10,
        ),
        open_trades=[existing],
        ticker_price=Decimal("2000"),
    )
    engine.mode = "live"
    sub = _make_risk_sub()
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
        global_policy=GlobalRiskPolicy(
            enabled=True,
            max_open_positions_per_symbol_side=5,
            max_gross_notional_per_symbol_side=Decimal("10000"),
            max_gross_notional_per_symbol=Decimal("10000"),
        ),
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_awaited_once()


async def test_global_cap_gate_enabled_with_all_caps_unset_is_noop(
    tmp_path: Path,
) -> None:
    """``enabled=True`` but every cap field None → gate stays inert."""
    existing = make_trade(
        trade_id="t-eth-long",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="5",  # large notional, but no caps configured
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    proposal = make_proposal(
        proposal_id="rsi-global-nocaps",
        symbol="ETH/USDT",
        signal="long",
        composite=2.0,
        entry="2000",
        sl="1950",
        tp="2100",
        quantity="5",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=10,
        ),
        open_trades=[existing],
        ticker_price=Decimal("2000"),
    )
    engine.mode = "live"
    sub = _make_risk_sub()
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
        global_policy=GlobalRiskPolicy(enabled=True),
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_awaited_once()


# =============================================================================
# cross-account-risk-policy: DEBT-068(c) lowest_priority_loses arbitration
# =============================================================================


def _arb_holder_trade(
    *, trade_id: str, sub_account_id: str, side: str = "long", quantity: str
) -> TradeHistory:
    """ETH/USDT open trade attributed to ``sub_account_id`` for arbitration."""
    return make_trade(
        trade_id=trade_id,
        symbol="ETH/USDT",
        side=side,
        entry="2000",
        quantity=quantity,
    ).model_copy(update={"sub_account_id": sub_account_id})


def _build_arb_engine(
    *,
    tmp_path: Path,
    proposer_id: str,
    open_trades: list[TradeHistory],
    policy: GlobalRiskPolicy,
    mode: str = "live",
    proposal_quantity: str = "2",
) -> tuple[TradingEngine, dict[str, MagicMock], Proposal, SubAccount | None]:
    """Wire an engine for a direct ``_global_aggregate_cap_gate`` arb call.

    Returns the proposal and proposer ``SubAccount`` (or ``None`` when
    ``proposer_id`` is empty) so the test can call the gate directly.
    """
    proposal = make_proposal(
        proposal_id="arb-prop",
        symbol="ETH/USDT",
        signal="long",
        composite=2.0,
        entry="2000",
        sl="1950",
        tp="2100",
        quantity=proposal_quantity,
    ).model_copy(update={"sub_account_id": proposer_id or DEFAULT_SUB_ACCOUNT_ID})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=10,
        ),
        open_trades=open_trades,
        ticker_price=Decimal("2000"),
    )
    engine.mode = mode

    holder_ids = {t.sub_account_id for t in open_trades}
    all_ids = holder_ids | ({proposer_id} if proposer_id else set())
    subs = [_make_risk_sub(id=acct) for acct in sorted(all_ids)]
    shared = mocks["trader"]
    engine.sub_account_registry = FakeSubAccountRegistry(
        subs,
        dict.fromkeys(sorted(all_ids), shared),
        global_policy=policy,
    )  # type: ignore[assignment]

    proposer_sub: SubAccount | None = None
    if proposer_id:
        for sub in subs:
            if sub.id == proposer_id:
                proposer_sub = sub
                break
    return engine, mocks, proposal, proposer_sub


async def _run_arb_gate(
    engine: TradingEngine, proposal: Proposal, sub_account: SubAccount | None
) -> object:
    record = await engine.proposal_interaction.decide(proposal, actor="test")
    return engine._global_aggregate_cap_gate(proposal, record, sub_account, "cyc")


async def test_arb_fcfs_regression_blocks_breach(tmp_path: Path) -> None:
    """1. FCFS (default): a breach hard-blocks live with arbitration n/a."""
    holder = _arb_holder_trade(trade_id="h-rank2", sub_account_id="lab_c", quantity="2")
    # proposer outranks lab_c, but FCFS ignores priority.
    engine, _mocks, proposal, sub = _build_arb_engine(
        tmp_path=tmp_path,
        proposer_id="lab_a",
        open_trades=[holder],
        policy=GlobalRiskPolicy(
            enabled=True,
            max_gross_notional_per_symbol_side=Decimal("5000"),
            cap_resolution="first_come_first_serve",
            account_priority=["lab_a", "lab_b", "lab_c"],
        ),
    )
    outcome = await _run_arb_gate(engine, proposal, sub)
    assert outcome is not None
    assert outcome.decision == GateDecision.REJECTED
    assert outcome.events[0].details["arbitration_outcome"] == "n/a"
    assert outcome.events[0].details["cap_resolution"] == "first_come_first_serve"


async def test_arb_high_priority_proposer_admitted(tmp_path: Path) -> None:
    """2. Proposer rank 0, key held only by rank-2 holder → ADMIT (live)."""
    holder = _arb_holder_trade(trade_id="h-rank2", sub_account_id="lab_c", quantity="2")
    engine, mocks, proposal, sub = _build_arb_engine(
        tmp_path=tmp_path,
        proposer_id="lab_a",  # rank 0
        open_trades=[holder],
        policy=GlobalRiskPolicy(
            enabled=True,
            max_gross_notional_per_symbol_side=Decimal("5000"),
            cap_resolution="lowest_priority_loses",
            account_priority=["lab_a", "lab_b", "lab_c"],
        ),
    )
    outcome = await _run_arb_gate(engine, proposal, sub)
    assert outcome is None  # admitted

    advisories = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.RISK_CAP_ADVISORY
        )
        if e.details.get("gate_reason") == "global_cap"
    ]
    assert len(advisories) == 1
    assert advisories[0].details["advisory"] is False
    assert advisories[0].details["arbitration_outcome"] == "admitted"
    assert "cap_overshoot" in advisories[0].details


async def test_arb_lowest_priority_proposer_blocked(tmp_path: Path) -> None:
    """3. Proposer rank 2 (lowest listed), key held only by rank-0 → BLOCK."""
    holder = _arb_holder_trade(trade_id="h-rank0", sub_account_id="lab_a", quantity="2")
    engine, _mocks, proposal, sub = _build_arb_engine(
        tmp_path=tmp_path,
        proposer_id="lab_c",  # rank 2
        open_trades=[holder],
        policy=GlobalRiskPolicy(
            enabled=True,
            max_gross_notional_per_symbol_side=Decimal("5000"),
            cap_resolution="lowest_priority_loses",
            account_priority=["lab_a", "lab_b", "lab_c"],
        ),
    )
    outcome = await _run_arb_gate(engine, proposal, sub)
    assert outcome is not None
    assert outcome.decision == GateDecision.REJECTED
    assert outcome.events[0].details["arbitration_outcome"] == "blocked"


async def test_arb_middle_priority_outranks_lower_holder_admitted(
    tmp_path: Path,
) -> None:
    """4. Proposer rank 1, holders at ranks 0 and 2 → ADMIT (outranks 2)."""
    holders = [
        _arb_holder_trade(trade_id="h0", sub_account_id="lab_a", quantity="1"),
        _arb_holder_trade(trade_id="h2", sub_account_id="lab_c", quantity="1"),
    ]
    engine, _mocks, proposal, sub = _build_arb_engine(
        tmp_path=tmp_path,
        proposer_id="lab_b",  # rank 1
        open_trades=holders,
        policy=GlobalRiskPolicy(
            enabled=True,
            max_gross_notional_per_symbol_side=Decimal("5000"),
            cap_resolution="lowest_priority_loses",
            account_priority=["lab_a", "lab_b", "lab_c"],
        ),
    )
    outcome = await _run_arb_gate(engine, proposal, sub)
    assert outcome is None  # admitted: outranks lab_c (rank 2)


async def test_arb_no_holders_alone_exceeds_cap_blocks(tmp_path: Path) -> None:
    """5. No existing holders; proposal alone exceeds cap → BLOCK."""
    engine, _mocks, proposal, sub = _build_arb_engine(
        tmp_path=tmp_path,
        proposer_id="lab_a",  # rank 0, but no other holders to outrank
        open_trades=[],
        proposal_quantity="3",  # 6000 > 5000
        policy=GlobalRiskPolicy(
            enabled=True,
            max_gross_notional_per_symbol_side=Decimal("5000"),
            cap_resolution="lowest_priority_loses",
            account_priority=["lab_a", "lab_b", "lab_c"],
        ),
    )
    outcome = await _run_arb_gate(engine, proposal, sub)
    assert outcome is not None
    assert outcome.decision == GateDecision.REJECTED
    assert outcome.events[0].details["arbitration_outcome"] == "blocked"


async def test_arb_unlisted_proposer_blocks(tmp_path: Path) -> None:
    """6. Proposer not in account_priority, listed holders → BLOCK (rank inf)."""
    holder = _arb_holder_trade(trade_id="h-rank0", sub_account_id="lab_a", quantity="2")
    engine, _mocks, proposal, sub = _build_arb_engine(
        tmp_path=tmp_path,
        proposer_id="lab_x",  # not in account_priority
        open_trades=[holder],
        policy=GlobalRiskPolicy(
            enabled=True,
            max_gross_notional_per_symbol_side=Decimal("5000"),
            cap_resolution="lowest_priority_loses",
            account_priority=["lab_a", "lab_b", "lab_c"],
        ),
    )
    outcome = await _run_arb_gate(engine, proposal, sub)
    assert outcome is not None
    assert outcome.decision == GateDecision.REJECTED
    details = outcome.events[0].details
    assert details["proposer_listed"] is False
    assert details["proposer_rank"] is None


async def test_arb_empty_priority_blocks_both_modes(tmp_path: Path) -> None:
    """7. Empty account_priority → block every breach (FCFS-equivalent)."""
    for resolution in ("first_come_first_serve", "lowest_priority_loses"):
        holder = _arb_holder_trade(trade_id="h", sub_account_id="lab_a", quantity="2")
        engine, _mocks, proposal, sub = _build_arb_engine(
            tmp_path=tmp_path,
            proposer_id="lab_b",
            open_trades=[holder],
            policy=GlobalRiskPolicy(
                enabled=True,
                max_gross_notional_per_symbol_side=Decimal("5000"),
                cap_resolution=resolution,  # type: ignore[arg-type]
                account_priority=[],
            ),
        )
        outcome = await _run_arb_gate(engine, proposal, sub)
        assert outcome is not None, resolution
        assert outcome.decision == GateDecision.REJECTED


async def test_arb_self_only_holder_excluded_blocks(tmp_path: Path) -> None:
    """8. Proposer already holds AND is sole holder → self-excluded → BLOCK."""
    holder = _arb_holder_trade(trade_id="h-self", sub_account_id="lab_a", quantity="2")
    engine, _mocks, proposal, sub = _build_arb_engine(
        tmp_path=tmp_path,
        proposer_id="lab_a",  # rank 0 but only holder is itself
        open_trades=[holder],
        policy=GlobalRiskPolicy(
            enabled=True,
            max_gross_notional_per_symbol_side=Decimal("5000"),
            cap_resolution="lowest_priority_loses",
            account_priority=["lab_a", "lab_b", "lab_c"],
        ),
    )
    outcome = await _run_arb_gate(engine, proposal, sub)
    assert outcome is not None
    assert outcome.decision == GateDecision.REJECTED
    assert outcome.events[0].details["existing_holders"] == []


async def test_arb_self_plus_lower_other_holder_admitted(tmp_path: Path) -> None:
    """9. Proposer holds, but a lower-priority OTHER account also holds → ADMIT."""
    holders = [
        _arb_holder_trade(trade_id="h-self", sub_account_id="lab_a", quantity="1"),
        _arb_holder_trade(trade_id="h-other", sub_account_id="lab_c", quantity="1"),
    ]
    engine, _mocks, proposal, sub = _build_arb_engine(
        tmp_path=tmp_path,
        proposer_id="lab_a",  # rank 0, outranks lab_c (rank 2)
        open_trades=holders,
        policy=GlobalRiskPolicy(
            enabled=True,
            max_gross_notional_per_symbol_side=Decimal("5000"),
            cap_resolution="lowest_priority_loses",
            account_priority=["lab_a", "lab_b", "lab_c"],
        ),
    )
    outcome = await _run_arb_gate(engine, proposal, sub)
    assert outcome is None  # admitted


async def test_arb_two_caps_one_blocks_blocks_overall(tmp_path: Path) -> None:
    """10. Two caps breach; admits one, blocks other → BLOCK (AND-conservative).

    The per-symbol cap key (both sides) includes a lower-priority short
    holder the proposer outranks → that cap admits. The per-symbol-SIDE
    (long) cap key holds ONLY a higher-priority long holder the proposer
    cannot outrank → that cap blocks → overall block.
    """
    holders = [
        # long side: higher-priority holder (only on the per-symbol-side key)
        _arb_holder_trade(
            trade_id="h-long", sub_account_id="lab_a", side="long", quantity="1"
        ),
        # short side: lower-priority holder (only on the per-symbol key)
        _arb_holder_trade(
            trade_id="h-short", sub_account_id="lab_c", side="short", quantity="2"
        ),
    ]
    engine, _mocks, proposal, sub = _build_arb_engine(
        tmp_path=tmp_path,
        proposer_id="lab_b",  # rank 1
        open_trades=holders,
        proposal_quantity="2",  # +4000 long
        policy=GlobalRiskPolicy(
            enabled=True,
            # long side total: 2000 (lab_a) + 4000 = 6000 > 5000. Holders {lab_a}
            # rank 0 — proposer (rank 1) does NOT outrank → this cap BLOCKS.
            max_gross_notional_per_symbol_side=Decimal("5000"),
            # symbol total: 2000 + 4000 (long) + 4000 (short lab_c) = 10000 > 7000.
            # Holders {lab_a, lab_c}; proposer outranks lab_c → this cap ADMITS.
            max_gross_notional_per_symbol=Decimal("7000"),
            cap_resolution="lowest_priority_loses",
            account_priority=["lab_a", "lab_b", "lab_c"],
        ),
    )
    outcome = await _run_arb_gate(engine, proposal, sub)
    assert outcome is not None
    assert outcome.decision == GateDecision.REJECTED
    by_cap = outcome.events[0].details["arbitration_by_cap"]
    assert by_cap["gross_notional_per_symbol_side"]["admitted"] is False
    assert by_cap["gross_notional_per_symbol"]["admitted"] is True


async def test_arb_two_caps_both_admit_admits_overall(tmp_path: Path) -> None:
    """11. Two caps breach; arbitration admits both → ADMIT."""
    holders = [
        _arb_holder_trade(
            trade_id="h-long", sub_account_id="lab_c", side="long", quantity="2"
        ),
        _arb_holder_trade(
            trade_id="h-short", sub_account_id="lab_c", side="short", quantity="1"
        ),
    ]
    engine, _mocks, proposal, sub = _build_arb_engine(
        tmp_path=tmp_path,
        proposer_id="lab_a",  # rank 0, outranks lab_c (rank 2) on both keys
        open_trades=holders,
        proposal_quantity="2",  # +4000
        policy=GlobalRiskPolicy(
            enabled=True,
            # long side: 4000 + 4000 = 8000 > 5000
            max_gross_notional_per_symbol_side=Decimal("5000"),
            # symbol: 4000 + 2000 + 4000 = 10000 > 7000
            max_gross_notional_per_symbol=Decimal("7000"),
            cap_resolution="lowest_priority_loses",
            account_priority=["lab_a", "lab_b", "lab_c"],
        ),
    )
    outcome = await _run_arb_gate(engine, proposal, sub)
    assert outcome is None  # admitted on both caps


async def test_arb_block_details_populated_paper_and_live(tmp_path: Path) -> None:
    """12. Block outcome: details fields populated in both paper and live."""
    for mode in ("live", "paper"):
        holder = _arb_holder_trade(
            trade_id="h-rank0", sub_account_id="lab_a", quantity="2"
        )
        engine, mocks, proposal, sub = _build_arb_engine(
            tmp_path=tmp_path,
            proposer_id="lab_c",  # rank 2 → blocked
            open_trades=[holder],
            mode=mode,
            policy=GlobalRiskPolicy(
                enabled=True,
                max_gross_notional_per_symbol_side=Decimal("5000"),
                cap_resolution="lowest_priority_loses",
                account_priority=["lab_a", "lab_b", "lab_c"],
            ),
        )
        outcome = await _run_arb_gate(engine, proposal, sub)
        if mode == "live":
            assert outcome is not None
            details = outcome.events[0].details
        else:
            # paper: block_overall True falls into advisory branch, returns None
            assert outcome is None
            advisories = [
                e
                for e in mocks["activity_log"].filter(
                    event_type=ActivityEventType.RISK_CAP_ADVISORY
                )
                if e.details.get("gate_reason") == "global_cap"
            ]
            assert len(advisories) == 1
            details = advisories[0].details
            assert details["advisory"] is True
        assert details["cap_resolution"] == "lowest_priority_loses"
        assert details["arbitration_outcome"] == "blocked"
        assert details["proposer_rank"] == 2
        assert details["existing_holders"] == ["lab_a"]


async def test_arb_admitted_live_breach_emits_informational_event(
    tmp_path: Path,
) -> None:
    """13. Admitted live breach → informational RISK_CAP_ADVISORY (advisory=False)."""
    holder = _arb_holder_trade(trade_id="h-rank2", sub_account_id="lab_c", quantity="2")
    engine, mocks, proposal, sub = _build_arb_engine(
        tmp_path=tmp_path,
        proposer_id="lab_a",
        open_trades=[holder],
        policy=GlobalRiskPolicy(
            enabled=True,
            max_gross_notional_per_symbol_side=Decimal("5000"),
            cap_resolution="lowest_priority_loses",
            account_priority=["lab_a", "lab_b", "lab_c"],
        ),
    )
    outcome = await _run_arb_gate(engine, proposal, sub)
    assert outcome is None

    advisories = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.RISK_CAP_ADVISORY
        )
        if e.details.get("gate_reason") == "global_cap"
    ]
    assert len(advisories) == 1
    details = advisories[0].details
    assert details["advisory"] is False
    assert details["arbitration_outcome"] == "admitted"
    assert details["cap_overshoot"]["max"] == "3000"


async def test_arb_sub_account_none_is_fcfs_equivalent(tmp_path: Path) -> None:
    """14. sub_account None → proposer DEFAULT, FCFS-equivalent (block on breach).

    With a single default account, holders self-exclude to empty, so even
    ``lowest_priority_loses`` blocks any breach.
    """
    holder = make_trade(
        trade_id="h-default",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="2",
    )  # default sub_account_id
    proposal = make_proposal(
        proposal_id="arb-none",
        symbol="ETH/USDT",
        signal="long",
        composite=2.0,
        entry="2000",
        sl="1950",
        tp="2100",
        quantity="2",
    )

    engine, _mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0, max_open_positions_per_symbol=10
        ),
        open_trades=[holder],
        ticker_price=Decimal("2000"),
    )
    engine.mode = "live"
    engine.sub_account_registry = FakeSubAccountRegistry(
        [_make_risk_sub(id=DEFAULT_SUB_ACCOUNT_ID)],
        {DEFAULT_SUB_ACCOUNT_ID: _mocks["trader"]},
        global_policy=GlobalRiskPolicy(
            enabled=True,
            max_gross_notional_per_symbol_side=Decimal("5000"),
            cap_resolution="lowest_priority_loses",
            account_priority=["lab_a", "lab_b"],
        ),
    )  # type: ignore[assignment]

    outcome = await _run_arb_gate(engine, proposal, None)
    assert outcome is not None
    assert outcome.decision == GateDecision.REJECTED


# =============================================================================
# cross-account-risk-policy: stateless kill-switch gates (DEBT-068(c-1))
# =============================================================================


async def test_open_drawdown_kill_switch_not_tripped_under_limit(
    tmp_path: Path,
) -> None:
    """Open unrealized loss within the drawdown limit → proposal proceeds."""
    existing = make_trade(
        trade_id="t-dd",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="1",  # notional 2000
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    proposal = make_proposal(
        proposal_id="dd-ok",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[existing],
    )
    engine.mode = "live"
    # equity 10000, limit 5% → threshold -500. Mark 1950 → -50 loss.
    engine._remember_mark_price("ETH/USDT", Decimal("1950"))
    sub = _make_risk_sub(open_unrealized_drawdown_limit_pct=Decimal("0.05"))
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_awaited_once()


async def test_open_drawdown_kill_switch_tripped_live_hard_blocks(
    tmp_path: Path,
) -> None:
    """Open unrealized loss worse than ``-pct * equity`` hard-blocks in live."""
    existing = make_trade(
        trade_id="t-dd-big",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="1",  # notional 2000
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    proposal = make_proposal(
        proposal_id="dd-trip",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[existing],
    )
    engine.mode = "live"
    # equity 10000, limit 5% → threshold -500. Mark 1400 → -600 loss < -500.
    engine._remember_mark_price("ETH/USDT", Decimal("1400"))
    sub = _make_risk_sub(open_unrealized_drawdown_limit_pct=Decimal("0.05"))
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.proposals_rejected == 1
    mocks["trader"].open_position.assert_not_called()
    record = mocks["history"].load("dd-trip")
    assert (
        record.final_state
        == ProposalFinalState.GATE_REJECTED_OPEN_DRAWDOWN_KILL_SWITCH.value
    )
    assert "open_drawdown_kill_switch" in (record.rejection_reason or "")


async def test_open_drawdown_kill_switch_paper_advisory_proceeds(
    tmp_path: Path,
) -> None:
    """Paper mode: drawdown trip is advisory-with-event; proposal executes."""
    existing = make_trade(
        trade_id="t-dd-paper",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="1",
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    proposal = make_proposal(
        proposal_id="dd-paper",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[existing],
    )
    engine.mode = "paper"
    engine._remember_mark_price("ETH/USDT", Decimal("1400"))  # -600 < -500
    sub = _make_risk_sub(open_unrealized_drawdown_limit_pct=Decimal("0.05"))
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_awaited_once()

    advisories = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.RISK_KILL_SWITCH_TRIPPED
        )
        if e.details.get("gate_reason") == "open_drawdown_kill_switch"
    ]
    assert len(advisories) == 1
    assert advisories[0].details["advisory"] is True
    assert advisories[0].details["mode"] == "paper"


async def test_open_drawdown_kill_switch_stale_mark_excluded_no_false_trip(
    tmp_path: Path,
) -> None:
    """A position with no fresh mark is excluded → no false drawdown trip."""
    # Big notional that WOULD breach if marked at a large loss, but no
    # cached mark exists → excluded → unrealized 0 → no trip.
    existing = make_trade(
        trade_id="t-dd-stale",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="5",
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    proposal = make_proposal(
        proposal_id="dd-stale",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[existing],
    )
    engine.mode = "live"
    # No _remember_mark_price for ETH/USDT → stale/missing → excluded.
    sub = _make_risk_sub(open_unrealized_drawdown_limit_pct=Decimal("0.05"))
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_awaited_once()


async def test_open_stop_risk_kill_switch_tripped_live_distinct_from_cap_gate(
    tmp_path: Path,
) -> None:
    """Open-stop-risk kill switch trips FIRST, with a gate_reason distinct
    from the aggregate-cap gate, short-circuiting before the cap gate runs.
    """
    existing = make_trade(
        trade_id="t-sr",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="1",
    ).model_copy(
        update={
            "sub_account_id": "rsi_lab",
            "stop_loss": Decimal("1000"),  # stop_risk = 1000 * 1 = 1000
        }
    )
    proposal = make_proposal(
        proposal_id="sr-trip",
        symbol="BTC/USDT",
        composite=2.0,
        entry="50000",
        sl="49000",
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[existing],
    )
    engine.mode = "live"
    # equity 10000, limit 5% → threshold 500. Existing stop-risk 1000 > 500.
    # ALSO configure max_open_stop_risk so the aggregate-cap gate WOULD fire
    # if reached — proving the kill switch short-circuits before it.
    sub = _make_risk_sub(
        open_stop_risk_limit_pct=Decimal("0.05"),
        max_open_stop_risk=Decimal("1"),
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.proposals_rejected == 1
    mocks["trader"].open_position.assert_not_called()

    record = mocks["history"].load("sr-trip")
    assert (
        record.final_state
        == ProposalFinalState.GATE_REJECTED_OPEN_STOP_RISK_KILL_SWITCH.value
    )

    # DEBT-068(g): live kill-switch trips emit RISK_KILL_SWITCH_TRIPPED
    # (the record final_state / funnel stays the kill-switch terminal).
    rejections = mocks["activity_log"].filter(
        event_type=ActivityEventType.RISK_KILL_SWITCH_TRIPPED
    )
    gate_reasons = {e.details.get("gate_reason") for e in rejections}
    # Kill switch fired; the aggregate-cap gate never ran (no double event).
    assert "open_stop_risk_kill_switch" in gate_reasons
    assert "account_aggregate_cap" not in gate_reasons


async def test_account_kill_switch_inert_when_pct_fields_none(
    tmp_path: Path,
) -> None:
    """Both ``_pct`` kill-switch fields None → gate is a no-op."""
    existing = make_trade(
        trade_id="t-inert",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="5",
    ).model_copy(update={"sub_account_id": "rsi_lab", "stop_loss": Decimal("1000")})
    proposal = make_proposal(
        proposal_id="inert",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[existing],
    )
    engine.mode = "live"
    engine._remember_mark_price("ETH/USDT", Decimal("100"))  # huge loss, but inert
    sub = _make_risk_sub()  # no kill-switch pct fields
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1


async def test_account_kill_switch_equity_unavailable_returns_none_no_event(
    tmp_path: Path,
) -> None:
    """No live balance and no sizing_balance → gate skipped, no event."""
    existing = make_trade(
        trade_id="t-noeq",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="1",
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    proposal = make_proposal(
        proposal_id="noeq",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[existing],
    )
    engine.mode = "live"
    mocks["trader"].get_balances = AsyncMock(return_value={})
    engine._remember_mark_price("ETH/USDT", Decimal("1000"))  # large loss
    # sizing_balance left None → no equity reference at all.
    sub = _make_risk_sub(open_unrealized_drawdown_limit_pct=Decimal("0.05"))
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    # Fail-open: proposal proceeds, no kill-switch event.
    assert result.positions_opened == 1
    kill_events = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.RISK_KILL_SWITCH_TRIPPED
        )
        if e.details.get("gate_reason")
        in {"open_drawdown_kill_switch", "open_stop_risk_kill_switch"}
    ]
    assert kill_events == []


async def test_global_kill_switch_summed_portfolio_drawdown_blocks_live(
    tmp_path: Path,
) -> None:
    """Portfolio open-drawdown summed over all open trades hard-blocks in live.

    Uses the single-active-account fixture (mirrors the global-cap gate
    tests) so the proposal is generated once and the cross-account open
    trades come through ``_open_trades_for_correlation``. The portfolio
    equity sum and the unrealized-PnL sum are still exercised end-to-end.
    """
    # Two losing ETH longs on the active account; mark 1900 → -1000 total.
    open_trades = [
        make_trade(
            trade_id="t-eth-1",
            symbol="ETH/USDT",
            side="long",
            entry="2000",
            quantity="5",
        ).model_copy(update={"sub_account_id": "rsi_lab"}),
        make_trade(
            trade_id="t-eth-2",
            symbol="ETH/USDT",
            side="long",
            entry="2000",
            quantity="5",
        ).model_copy(update={"sub_account_id": "rsi_lab"}),
    ]
    proposal = make_proposal(
        proposal_id="global-dd",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            max_open_positions_per_symbol=10,
        ),
        open_trades=open_trades,
    )
    engine.mode = "live"
    engine._remember_mark_price("ETH/USDT", Decimal("1900"))  # total -1000

    sub = _make_risk_sub()
    # Portfolio equity 10000; limit 2% → threshold -200. -1000 < -200 → trip.
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
        global_policy=GlobalRiskPolicy(
            enabled=True,
            portfolio_unrealized_drawdown_limit_pct=Decimal("0.02"),
        ),
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.proposals_rejected == 1
    mocks["trader"].open_position.assert_not_called()
    record = mocks["history"].load("global-dd")
    assert (
        record.final_state
        == ProposalFinalState.GATE_REJECTED_PORTFOLIO_KILL_SWITCH.value
    )
    assert "portfolio_kill_switch" in (record.rejection_reason or "")
    # Event details prove the portfolio equity is the SUM across the
    # registry's enabled accounts (here one account → 10000).
    event = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.RISK_KILL_SWITCH_TRIPPED
        )
        if e.details.get("gate_reason") == "portfolio_kill_switch"
    ][0]
    assert event.details["portfolio_equity"] == "10000"
    assert event.details["portfolio_unrealized_pnl"] == "-1000"


async def test_global_kill_switch_equity_sums_multiple_accounts(
    tmp_path: Path,
) -> None:
    """Portfolio equity is the sum of equity across all enabled sub-accounts.

    Direct gate call (avoids the test proposal-engine mock re-emitting the
    same proposal once per active account in ``run_cycle``). Verifies the
    cross-account equity summation that the live-path test cannot isolate.
    """
    a_trade = make_trade(
        trade_id="t-a",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="5",
    ).model_copy(update={"sub_account_id": "lab_a"})
    b_trade = make_trade(
        trade_id="t-b",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="5",
    ).model_copy(update={"sub_account_id": "lab_b"})
    proposal = make_proposal(
        proposal_id="global-eq",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "lab_c"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    engine.mode = "live"
    shared = mocks["trader"]
    shared.get_open_trades.return_value = [a_trade, b_trade]
    shared.get_balances = AsyncMock(return_value={"USDT": Decimal("10000")})
    engine._remember_mark_price("ETH/USDT", Decimal("1900"))  # total -1000

    sub_a = _make_risk_sub(id="lab_a")
    sub_b = _make_risk_sub(id="lab_b")
    sub_c = _make_risk_sub(id="lab_c")
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub_a, sub_b, sub_c],
        {"lab_a": shared, "lab_b": shared, "lab_c": shared},
        global_policy=GlobalRiskPolicy(
            enabled=True,
            # 3 * 10000 = 30000; limit 2% → threshold -600. -1000 < -600.
            portfolio_unrealized_drawdown_limit_pct=Decimal("0.02"),
        ),
    )  # type: ignore[assignment]

    record = await engine.proposal_interaction.decide(proposal, actor="test")
    outcome = await engine._global_kill_switch_gate(proposal, record, "cyc")

    assert outcome is not None
    assert outcome.decision == GateDecision.REJECTED
    assert (
        outcome.final_record.final_state
        == ProposalFinalState.GATE_REJECTED_PORTFOLIO_KILL_SWITCH.value
    )
    assert outcome.events[0].details["portfolio_equity"] == "30000"


async def test_global_kill_switch_inert_when_policy_disabled(
    tmp_path: Path,
) -> None:
    """``GlobalRiskPolicy.enabled=False`` → portfolio kill switch is inert."""
    a_trade = make_trade(
        trade_id="t-a",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="5",
    ).model_copy(update={"sub_account_id": "lab_a"})
    proposal = make_proposal(
        proposal_id="global-off",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "lab_a"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[a_trade],
    )
    engine.mode = "live"
    engine._remember_mark_price("ETH/USDT", Decimal("1000"))  # huge loss
    sub_a = _make_risk_sub(id="lab_a")
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub_a],
        {"lab_a": mocks["trader"]},
        global_policy=GlobalRiskPolicy(
            enabled=False,
            portfolio_unrealized_drawdown_limit_pct=Decimal("0.02"),
        ),
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1


# =============================================================================
# cross-account-risk-policy: stateful daily-loss kill switches (DEBT-068(c-2))
# =============================================================================


def _closed_loss_trade(
    *,
    trade_id: str,
    sub_account_id: str = "rsi_lab",
    pnl: str,
    exit_time: datetime,
    symbol: str = "ETH/USDT",
) -> TradeHistory:
    """A CLOSED trade with a realized (signed, net) ``pnl`` and ``exit_time``."""
    return make_trade(
        trade_id=trade_id,
        symbol=symbol,
        side="long",
        entry="2000",
        quantity="1",
        exit_price="1900",
        status="closed",
        pnl=pnl,
        exit_time=exit_time,
    ).model_copy(update={"sub_account_id": sub_account_id})


async def test_daily_loss_kill_switch_not_tripped_within_limit(
    tmp_path: Path,
) -> None:
    """Today's realized loss within the limit → proposal proceeds."""
    # equity 10000, realized today -100 → starting_equity 10100,
    # limit 3% → threshold -303. -100 >= -303 → no trip.
    closed = _closed_loss_trade(
        trade_id="dl-ok",
        pnl="-100",
        exit_time=now_utc(),
    )
    proposal = make_proposal(
        proposal_id="dl-within",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    engine.mode = "live"
    _attach_closed_trades(mocks["trader"], [closed])
    sub = _make_risk_sub(daily_loss_limit_pct=Decimal("0.03"))
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_awaited_once()


async def test_daily_loss_kill_switch_tripped_live_hard_blocks(
    tmp_path: Path,
) -> None:
    """Realized loss worse than the limit hard-blocks in live mode."""
    # equity 10000, realized today -500 → starting_equity 10500,
    # limit 3% → threshold -315. -500 < -315 → trip.
    closed = _closed_loss_trade(
        trade_id="dl-big",
        pnl="-500",
        exit_time=now_utc(),
    )
    proposal = make_proposal(
        proposal_id="dl-trip",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    engine.mode = "live"
    _attach_closed_trades(mocks["trader"], [closed])
    sub = _make_risk_sub(daily_loss_limit_pct=Decimal("0.03"))
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.proposals_rejected == 1
    mocks["trader"].open_position.assert_not_called()
    record = mocks["history"].load("dl-trip")
    assert (
        record.final_state
        == ProposalFinalState.GATE_REJECTED_DAILY_LOSS_KILL_SWITCH.value
    )
    assert "daily_loss_kill_switch" in (record.rejection_reason or "")
    event = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.RISK_KILL_SWITCH_TRIPPED
        )
        if e.details.get("gate_reason") == "daily_loss_kill_switch"
    ][0]
    assert event.details["realized_pnl_today"] == "-500"
    assert event.details["starting_equity_today"] == "10500"


async def test_daily_loss_kill_switch_paper_advisory_proceeds(
    tmp_path: Path,
) -> None:
    """Paper mode: daily-loss trip is advisory-with-event; proposal executes."""
    closed = _closed_loss_trade(
        trade_id="dl-paper",
        pnl="-500",
        exit_time=now_utc(),
    )
    proposal = make_proposal(
        proposal_id="dl-paper",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    engine.mode = "paper"
    _attach_closed_trades(mocks["trader"], [closed])
    sub = _make_risk_sub(daily_loss_limit_pct=Decimal("0.03"))
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_awaited_once()

    advisories = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.RISK_KILL_SWITCH_TRIPPED
        )
        if e.details.get("gate_reason") == "daily_loss_kill_switch"
    ]
    assert len(advisories) == 1
    assert advisories[0].details["advisory"] is True
    assert advisories[0].details["mode"] == "paper"


async def test_daily_loss_kill_switch_utc_midnight_window_boundary(
    tmp_path: Path,
) -> None:
    """Trades exiting BEFORE UTC midnight are excluded; one AFTER trips.

    Proves the daily-loss window is bounded at today's UTC midnight on the
    EXIT timestamp. A large loss closed just before midnight is in the
    prior day (excluded → no trip); the same loss closed just after
    midnight is in today's window (included → trip).
    """
    midnight = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    before = midnight - timedelta(seconds=1)  # prior UTC day
    after = midnight + timedelta(seconds=1)  # today

    # --- BEFORE midnight: excluded → realized today 0 → no trip. ---
    closed_before = _closed_loss_trade(
        trade_id="dl-before",
        pnl="-500",
        exit_time=before,
    )
    proposal_b = make_proposal(
        proposal_id="dl-boundary-before",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    engine_b, mocks_b = build_engine(
        tmp_path=tmp_path / "before",
        btc_proposal=proposal_b,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    engine_b.mode = "live"
    _attach_closed_trades(mocks_b["trader"], [closed_before])
    engine_b.sub_account_registry = FakeSubAccountRegistry(
        [_make_risk_sub(daily_loss_limit_pct=Decimal("0.03"))],
        {"rsi_lab": mocks_b["trader"]},
    )  # type: ignore[assignment]
    result_b = await engine_b.run_cycle()
    assert result_b.positions_opened == 1

    # --- AFTER midnight: included → realized today -500 → trip. ---
    closed_after = _closed_loss_trade(
        trade_id="dl-after",
        pnl="-500",
        exit_time=after,
    )
    proposal_a = make_proposal(
        proposal_id="dl-boundary-after",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    engine_a, mocks_a = build_engine(
        tmp_path=tmp_path / "after",
        btc_proposal=proposal_a,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    engine_a.mode = "live"
    _attach_closed_trades(mocks_a["trader"], [closed_after])
    engine_a.sub_account_registry = FakeSubAccountRegistry(
        [_make_risk_sub(daily_loss_limit_pct=Decimal("0.03"))],
        {"rsi_lab": mocks_a["trader"]},
    )  # type: ignore[assignment]
    result_a = await engine_a.run_cycle()
    assert result_a.proposals_rejected == 1
    mocks_a["trader"].open_position.assert_not_called()


async def test_daily_loss_kill_switch_survives_restart_no_state_file(
    tmp_path: Path,
) -> None:
    """Realized-today is recomputed from disk → restart cannot escape the limit.

    Persist a losing closed trade to a real ``TradeHistoryTracker`` on
    disk, then build a FRESH tracker from the same ``data_dir`` (simulating
    a process restart with no separate state file) and confirm the engine
    recomputes the same realized_today and still trips.
    """
    data_dir = tmp_path / "trades"
    # Persist a losing closed trade for today via the production tracker.
    writer = TradeHistoryTracker(data_dir=data_dir, sub_account_id="rsi_lab")
    losing = _closed_loss_trade(
        trade_id="dl-persist",
        pnl="-500",
        exit_time=now_utc(),
    ).model_copy(update={"mode": "live"})
    writer.save_trade(losing)

    # Simulate restart: a brand-new tracker reading the same files.
    reloaded = TradeHistoryTracker(data_dir=data_dir, sub_account_id="rsi_lab")

    proposal = make_proposal(
        proposal_id="dl-restart",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    engine.mode = "live"
    # Wire the reloaded on-disk tracker onto the trader.
    mocks["trader"]._trade_tracker = reloaded
    sub = _make_risk_sub(daily_loss_limit_pct=Decimal("0.03"))
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    # Sanity: the helper recomputes the persisted realized loss from disk.
    assert engine._realized_pnl_today(mocks["trader"], "rsi_lab") == Decimal("-500")

    result = await engine.run_cycle()
    assert result.proposals_rejected == 1
    record = mocks["history"].load("dl-restart")
    assert (
        record.final_state
        == ProposalFinalState.GATE_REJECTED_DAILY_LOSS_KILL_SWITCH.value
    )


async def test_daily_loss_kill_switch_equity_unavailable_skips_no_event(
    tmp_path: Path,
) -> None:
    """No equity reference → daily-loss gate skipped, no event (fail-open)."""
    closed = _closed_loss_trade(
        trade_id="dl-noeq",
        pnl="-500",
        exit_time=now_utc(),
    )
    proposal = make_proposal(
        proposal_id="dl-noeq",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    engine.mode = "live"
    mocks["trader"].get_balances = AsyncMock(return_value={})
    _attach_closed_trades(mocks["trader"], [closed])
    # sizing_balance left None → no equity reference at all.
    sub = _make_risk_sub(daily_loss_limit_pct=Decimal("0.03"))
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1
    kill_events = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.RISK_KILL_SWITCH_TRIPPED
        )
        if e.details.get("gate_reason") == "daily_loss_kill_switch"
    ]
    assert kill_events == []


async def test_daily_loss_runs_before_open_drawdown_kill_switch(
    tmp_path: Path,
) -> None:
    """A proposal breaching BOTH daily-loss and open-drawdown rejects with
    the DAILY-LOSS reason (spec §"Runtime Behavior": daily-loss runs first).
    """
    # Daily-loss trip: realized today -500 → threshold ~-315 → trip.
    closed = _closed_loss_trade(
        trade_id="dl-both",
        pnl="-500",
        exit_time=now_utc(),
    )
    # Open-drawdown trip: open ETH long marked at a big loss.
    open_trade = make_trade(
        trade_id="dd-both-open",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="1",
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    proposal = make_proposal(
        proposal_id="dl-and-dd",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
        open_trades=[open_trade],
    )
    engine.mode = "live"
    _attach_closed_trades(mocks["trader"], [closed])
    engine._remember_mark_price("ETH/USDT", Decimal("1400"))  # -600 < -500
    sub = _make_risk_sub(
        daily_loss_limit_pct=Decimal("0.03"),
        open_unrealized_drawdown_limit_pct=Decimal("0.05"),
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.proposals_rejected == 1
    record = mocks["history"].load("dl-and-dd")
    assert (
        record.final_state
        == ProposalFinalState.GATE_REJECTED_DAILY_LOSS_KILL_SWITCH.value
    )
    rejections = mocks["activity_log"].filter(
        event_type=ActivityEventType.RISK_KILL_SWITCH_TRIPPED
    )
    gate_reasons = {e.details.get("gate_reason") for e in rejections}
    assert "daily_loss_kill_switch" in gate_reasons
    # Daily-loss short-circuited before the drawdown check fired.
    assert "open_drawdown_kill_switch" not in gate_reasons


async def test_daily_loss_kill_switch_inert_when_pct_none(
    tmp_path: Path,
) -> None:
    """``daily_loss_limit_pct=None`` → daily-loss check is inert."""
    closed = _closed_loss_trade(
        trade_id="dl-inert",
        pnl="-9000",  # catastrophic, but no limit configured
        exit_time=now_utc(),
    )
    proposal = make_proposal(
        proposal_id="dl-inert",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    engine.mode = "live"
    _attach_closed_trades(mocks["trader"], [closed])
    sub = _make_risk_sub()  # no daily_loss_limit_pct
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1


async def test_portfolio_daily_loss_kill_switch_summed_blocks_live(
    tmp_path: Path,
) -> None:
    """Portfolio daily-loss summed across two accounts blocks a third's

    proposal. Direct gate call (the multi-account ``run_cycle`` mock
    re-emits one proposal per active account, so cross-account assertions
    use the gate method directly, as the c-1 global tests do).
    """
    # Two accounts each realized -400 today → portfolio_realized -800.
    # lab_a / lab_b: equity 10000, realized -400 → starting 10400 each.
    # lab_c: equity 10000, realized 0 → starting 10000.
    # portfolio_starting_equity 30800; limit 2% → threshold -616.
    # -800 < -616 → trip.
    closed_a = _closed_loss_trade(
        trade_id="pdl-a",
        sub_account_id="lab_a",
        pnl="-400",
        exit_time=now_utc(),
    )
    closed_b = _closed_loss_trade(
        trade_id="pdl-b",
        sub_account_id="lab_b",
        pnl="-400",
        exit_time=now_utc(),
    )
    proposal = make_proposal(
        proposal_id="pdl-trip",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "lab_c"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    engine.mode = "live"
    trader_a = make_mock_trader()
    trader_b = make_mock_trader()
    trader_c = make_mock_trader()
    _attach_closed_trades(trader_a, [closed_a])
    _attach_closed_trades(trader_b, [closed_b])
    _attach_closed_trades(trader_c, [])  # lab_c has no realized loss today

    sub_a = _make_risk_sub(id="lab_a")
    sub_b = _make_risk_sub(id="lab_b")
    sub_c = _make_risk_sub(id="lab_c")
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub_a, sub_b, sub_c],
        {"lab_a": trader_a, "lab_b": trader_b, "lab_c": trader_c},
        global_policy=GlobalRiskPolicy(
            enabled=True,
            portfolio_daily_loss_limit_pct=Decimal("0.02"),
        ),
    )  # type: ignore[assignment]

    record = await engine.proposal_interaction.decide(proposal, actor="test")
    outcome = await engine._global_kill_switch_gate(proposal, record, "cyc")

    assert outcome is not None
    assert outcome.decision == GateDecision.REJECTED
    assert (
        outcome.final_record.final_state
        == ProposalFinalState.GATE_REJECTED_PORTFOLIO_DAILY_LOSS_KILL_SWITCH.value
    )
    # DEBT-068(g): live kill-switch trips emit the dedicated event type.
    assert outcome.events[0].event_type == ActivityEventType.RISK_KILL_SWITCH_TRIPPED
    details = outcome.events[0].details
    assert details["gate_reason"] == "portfolio_daily_loss_kill_switch"
    assert details["portfolio_realized_pnl_today"] == "-800"
    assert details["portfolio_starting_equity_today"] == "30800"


async def test_portfolio_daily_loss_kill_switch_inert_when_disabled(
    tmp_path: Path,
) -> None:
    """``GlobalRiskPolicy.enabled=False`` → portfolio daily-loss is inert."""
    closed_a = _closed_loss_trade(
        trade_id="pdl-off",
        sub_account_id="lab_a",
        pnl="-9000",
        exit_time=now_utc(),
    )
    proposal = make_proposal(
        proposal_id="pdl-off",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "lab_a"})
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(auto_approve_threshold=1.0),
    )
    engine.mode = "live"
    _attach_closed_trades(mocks["trader"], [closed_a])
    sub_a = _make_risk_sub(id="lab_a")
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub_a],
        {"lab_a": mocks["trader"]},
        global_policy=GlobalRiskPolicy(
            enabled=False,
            portfolio_daily_loss_limit_pct=Decimal("0.02"),
        ),
    )  # type: ignore[assignment]

    result = await engine.run_cycle()
    assert result.positions_opened == 1


# =============================================================================
# strategy-tuning: _strategy_action_gate (Slice 1)
# =============================================================================


def _make_sub_account_with_action(
    *,
    action: StrategyAction,
    technique_name: str = "tech_a",
    scout_size_factor: Decimal | None = None,
    enabled: bool = True,
) -> SubAccount:
    """Build a sub-account whose strategy_tuning policy has the given action."""
    override_kwargs: dict[str, object] = {"applied": action}
    if scout_size_factor is not None:
        override_kwargs["scout_size_factor"] = scout_size_factor
    policy = StrategyTuningPolicy(
        enabled=enabled,
        strategy_overrides={
            technique_name: StrategyOverride(**override_kwargs),
        },
    )
    return SubAccount(
        id="tuning_test",
        name="Tuning Test",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
        strategy_tuning=policy,
    )


def test_strategy_action_gate_keep_is_no_op(tmp_path: Path) -> None:
    """``keep`` returns the inputs unchanged and emits no outcome."""
    engine, _ = build_engine(tmp_path=tmp_path)
    proposal = make_proposal(proposal_id="keep-test")
    record = ProposalRecord(proposal=proposal)
    sub = _make_sub_account_with_action(action=StrategyAction.KEEP)

    new_proposal, new_record, outcome = engine._strategy_action_gate(
        proposal, record, sub, cycle_id="cy1"
    )

    assert new_proposal is proposal
    assert new_record is record
    assert outcome is None


def test_strategy_action_gate_promote_is_no_op(tmp_path: Path) -> None:
    """``promote`` is recommendation-only; runtime behaviour is keep-like."""
    engine, _ = build_engine(tmp_path=tmp_path)
    proposal = make_proposal(proposal_id="promote-test")
    record = ProposalRecord(proposal=proposal)
    sub = _make_sub_account_with_action(action=StrategyAction.PROMOTE)

    new_proposal, new_record, outcome = engine._strategy_action_gate(
        proposal, record, sub, cycle_id="cy1"
    )

    assert outcome is None
    assert new_proposal is proposal
    assert new_record is record


def test_strategy_action_gate_retune_passes_through_and_emits_advisory(
    tmp_path: Path,
) -> None:
    """``retune`` flows through but emits a ``RETUNE_FLAGGED`` advisory event."""
    engine, mocks = build_engine(tmp_path=tmp_path)
    proposal = make_proposal(proposal_id="retune-test")
    record = ProposalRecord(proposal=proposal)
    sub = _make_sub_account_with_action(action=StrategyAction.RETUNE)

    new_proposal, new_record, outcome = engine._strategy_action_gate(
        proposal, record, sub, cycle_id="cy1"
    )

    assert outcome is None
    assert new_proposal is proposal
    flagged = mocks["activity_log"].filter(event_type=ActivityEventType.RETUNE_FLAGGED)
    assert len(flagged) == 1
    assert flagged[0].details["technique_name"] == proposal.technique_name


def test_strategy_action_gate_scout_scales_quantity(tmp_path: Path) -> None:
    """``scout`` rewrites ``proposal.quantity`` by ``scout_size_factor``."""
    engine, _ = build_engine(tmp_path=tmp_path)
    proposal = make_proposal(proposal_id="scout-test", quantity="0.4")
    record = ProposalRecord(proposal=proposal)
    sub = _make_sub_account_with_action(
        action=StrategyAction.SCOUT,
        scout_size_factor=Decimal("0.25"),
    )

    new_proposal, new_record, outcome = engine._strategy_action_gate(
        proposal, record, sub, cycle_id="cy1"
    )

    assert outcome is None
    assert new_proposal.quantity == Decimal("0.4") * Decimal("0.25")
    # Other fields untouched.
    assert new_proposal.entry_price == proposal.entry_price
    assert new_record is record


def test_strategy_action_gate_shadow_persists_with_shadow_marker(
    tmp_path: Path,
) -> None:
    """``shadow`` returns a rejected outcome with ``shadow=True`` on the record."""
    engine, _ = build_engine(tmp_path=tmp_path)
    proposal = make_proposal(proposal_id="shadow-test")
    record = ProposalRecord(proposal=proposal)
    sub = _make_sub_account_with_action(action=StrategyAction.SHADOW)

    new_proposal, new_record, outcome = engine._strategy_action_gate(
        proposal, record, sub, cycle_id="cy1"
    )

    assert outcome is not None
    assert new_record.shadow is True
    assert new_record.final_state == ProposalFinalState.SHADOW_RECORDED.value
    assert outcome.final_record is new_record
    # Event payload carries the shadow marker for dashboards.
    assert outcome.events[0].details["shadow"] is True


def test_strategy_action_gate_pause_rejects_with_dedicated_terminal(
    tmp_path: Path,
) -> None:
    """``pause`` rejects with the ``GATE_REJECTED_STRATEGY_ACTION_PAUSE`` terminal."""
    engine, _ = build_engine(tmp_path=tmp_path)
    proposal = make_proposal(proposal_id="pause-test")
    record = ProposalRecord(proposal=proposal)
    sub = _make_sub_account_with_action(action=StrategyAction.PAUSE)

    new_proposal, new_record, outcome = engine._strategy_action_gate(
        proposal, record, sub, cycle_id="cy1"
    )

    assert outcome is not None
    assert new_record.decision == ProposalDecision.REJECTED.value
    assert (
        new_record.final_state
        == ProposalFinalState.GATE_REJECTED_STRATEGY_ACTION_PAUSE.value
    )
    assert new_record.rejection_reason == "strategy_action_pause"
    assert outcome.events[0].details["gate_reason"] == "strategy_action_pause"
    # DEBT-069(f): the pause event carries the config-vs-evidence discriminator.
    # The gate fires on the applied action, so it is always "gate_config"; the
    # corroboration upgrade is computed dashboard-side. Observability-only — the
    # rejection terminal / gate_reason are unchanged above.
    assert outcome.events[0].details["pause_reason"] == "gate_config"


def test_strategy_action_gate_disabled_policy_is_no_op(tmp_path: Path) -> None:
    """``strategy_tuning.enabled=False`` keeps the gate a complete no-op."""
    engine, _ = build_engine(tmp_path=tmp_path)
    proposal = make_proposal(proposal_id="disabled-test")
    record = ProposalRecord(proposal=proposal)
    # Even with PAUSE in the overrides, disabled means the gate never fires.
    sub = _make_sub_account_with_action(
        action=StrategyAction.PAUSE,
        enabled=False,
    )

    new_proposal, new_record, outcome = engine._strategy_action_gate(
        proposal, record, sub, cycle_id="cy1"
    )

    assert outcome is None
    assert new_proposal is proposal
    assert new_record is record


def test_strategy_action_gate_unknown_strategy_defaults_to_keep(
    tmp_path: Path,
) -> None:
    """Strategies without an explicit override default to ``keep``."""
    engine, _ = build_engine(tmp_path=tmp_path)
    proposal = make_proposal(proposal_id="default-keep")
    record = ProposalRecord(proposal=proposal)
    # Policy enabled but no override for ``tech_a``.
    sub = SubAccount(
        id="default_keep",
        name="Default Keep",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
        strategy_tuning=StrategyTuningPolicy(enabled=True),
    )

    new_proposal, new_record, outcome = engine._strategy_action_gate(
        proposal, record, sub, cycle_id="cy1"
    )

    assert outcome is None
    assert new_proposal is proposal


def test_strategy_action_gate_no_sub_account_is_no_op(tmp_path: Path) -> None:
    """Legacy path without a sub-account never gates."""
    engine, _ = build_engine(tmp_path=tmp_path)
    proposal = make_proposal(proposal_id="no-sub")
    record = ProposalRecord(proposal=proposal)

    new_proposal, new_record, outcome = engine._strategy_action_gate(
        proposal, record, None, cycle_id="cy1"
    )

    assert outcome is None
    assert new_proposal is proposal
    assert new_record is record


# =============================================================================
# cross-account-risk-policy DEBT-068(d): operator manual freeze
# =============================================================================


def _write_freeze_flag(path: Path, *, frozen: bool) -> None:
    """Write a ``config/runtime_flags.yaml``-shaped file at ``path``."""
    path.write_text(
        f"runtime_flags:\n  trading_freeze: {str(frozen).lower()}\n",
        encoding="utf-8",
    )


async def test_operator_freeze_absent_file_trades_normally(tmp_path: Path) -> None:
    """No flag file ⇒ not frozen ⇒ proposal proceeds to execution."""
    proposal = make_proposal(proposal_id="no-freeze", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            runtime_flags_path=tmp_path / "runtime_flags.yaml",  # absent
        ),
    )

    result = await engine.run_cycle()

    assert engine._operator_freeze_active is False
    assert result.positions_opened == 1
    assert result.proposals_rejected == 0
    mocks["trader"].open_position.assert_called_once()
    freeze_events = mocks["activity_log"].filter(
        event_type=ActivityEventType.OPERATOR_FREEZE_ENGAGED
    )
    assert freeze_events == []


@pytest.mark.parametrize("mode", ["paper", "live"])
async def test_operator_freeze_rejects_in_both_modes(tmp_path: Path, mode: str) -> None:
    """``trading_freeze: true`` hard-blocks every proposal in paper AND live.

    Unlike caps / kill-switches there is no paper-advisory carve-out: the
    operator pulled the lever, so no position opens in either mode.
    """
    flag_path = tmp_path / "runtime_flags.yaml"
    _write_freeze_flag(flag_path, frozen=True)
    proposal = make_proposal(proposal_id="frozen", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            runtime_flags_path=flag_path,
        ),
    )
    engine.mode = mode  # type: ignore[assignment]

    result = await engine.run_cycle()

    assert engine._operator_freeze_active is True
    assert result.proposals_rejected == 1
    assert result.positions_opened == 0
    mocks["trader"].open_position.assert_not_called()

    record = mocks["history"].load("frozen")
    assert record.final_state == ProposalFinalState.GATE_REJECTED_OPERATOR_FREEZE.value
    assert record.decision == ProposalDecision.REJECTED.value
    assert record.rejection_reason == "operator_freeze"

    freeze_events = mocks["activity_log"].filter(
        event_type=ActivityEventType.OPERATOR_FREEZE_ENGAGED
    )
    assert len(freeze_events) == 1
    assert freeze_events[0].details.get("reason") == "operator_freeze"
    assert freeze_events[0].details.get("proposal_id") == "frozen"


async def test_operator_freeze_rejects_before_other_gates(tmp_path: Path) -> None:
    """Freeze is the earliest reject — it wins over a would-be kill-switch.

    The proposal's account is configured with a tripped open-drawdown kill
    switch; without the freeze it would be rejected with
    ``open_drawdown_kill_switch``. With the freeze on, the operator-freeze
    terminal fires instead and the kill-switch gate never runs.
    """
    flag_path = tmp_path / "runtime_flags.yaml"
    _write_freeze_flag(flag_path, frozen=True)

    existing = make_trade(
        trade_id="t-dd",
        symbol="ETH/USDT",
        side="long",
        entry="2000",
        quantity="5",
    ).model_copy(update={"sub_account_id": "rsi_lab", "stop_loss": Decimal("1000")})
    proposal = make_proposal(
        proposal_id="freeze-precedence",
        symbol="BTC/USDT",
        composite=2.0,
        quantity="0.01",
    ).model_copy(update={"sub_account_id": "rsi_lab"})

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            runtime_flags_path=flag_path,
        ),
        open_trades=[existing],
    )
    engine.mode = "live"
    # Drive the open position deep underwater so the kill switch *would*
    # trip if it were reached.
    engine._remember_mark_price("ETH/USDT", Decimal("100"))
    sub = _make_risk_sub(open_unrealized_drawdown_limit_pct=Decimal("0.05"))
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub],
        {"rsi_lab": mocks["trader"]},
    )  # type: ignore[assignment]

    result = await engine.run_cycle()

    assert result.proposals_rejected == 1
    assert result.positions_opened == 0
    record = mocks["history"].load("freeze-precedence")
    # Operator freeze wins; the kill-switch terminal never fires.
    assert record.final_state == ProposalFinalState.GATE_REJECTED_OPERATOR_FREEZE.value
    # No kill-switch advisory / rejection event was emitted. DEBT-068(g):
    # kill-switch trips emit RISK_KILL_SWITCH_TRIPPED (not PROPOSAL_REJECTED),
    # so assert that type is absent for this freeze-precedence cycle.
    kill_events = [
        e
        for e in mocks["activity_log"].filter(
            event_type=ActivityEventType.RISK_KILL_SWITCH_TRIPPED
        )
        if e.details.get("gate_reason")
    ]
    assert kill_events == []
    assert (
        len(
            mocks["activity_log"].filter(
                event_type=ActivityEventType.OPERATOR_FREEZE_ENGAGED
            )
        )
        == 1
    )


async def test_operator_freeze_malformed_file_does_not_freeze(
    tmp_path: Path,
) -> None:
    """Malformed flag file ⇒ treated as not-frozen; cycle does not crash."""
    flag_path = tmp_path / "runtime_flags.yaml"
    flag_path.write_text("runtime_flags: [oops\n", encoding="utf-8")  # bad YAML
    proposal = make_proposal(proposal_id="malformed", composite=2.0)
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        config=EngineConfig(
            auto_approve_threshold=1.0,
            runtime_flags_path=flag_path,
        ),
    )

    result = await engine.run_cycle()

    assert engine._operator_freeze_active is False
    assert result.positions_opened == 1
    mocks["trader"].open_position.assert_called_once()


async def test_operator_freeze_reloaded_per_cycle(tmp_path: Path) -> None:
    """Flipping the flag file between cycles changes the next cycle's behavior.

    Cycle 1 runs unfrozen (file absent), opens a position. The operator
    then writes ``trading_freeze: true``; cycle 2 picks it up at the top of
    the cycle and rejects.
    """
    flag_path = tmp_path / "runtime_flags.yaml"
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=make_proposal(proposal_id="cycle1", composite=2.0),
        config=EngineConfig(
            auto_approve_threshold=1.0,
            runtime_flags_path=flag_path,
        ),
    )

    # Cycle 1: no flag file → not frozen → opens.
    result1 = await engine.run_cycle()
    assert engine._operator_freeze_active is False
    assert result1.positions_opened == 1

    # Operator freezes a RUNNING engine; swap the per-cycle proposal too.
    _write_freeze_flag(flag_path, frozen=True)
    mocks["proposal_engine"].propose_bitcoin = AsyncMock(
        return_value=make_proposal(proposal_id="cycle2", composite=2.0)
    )

    # Cycle 2: flag re-read at cycle top → frozen → rejects.
    result2 = await engine.run_cycle()
    assert engine._operator_freeze_active is True
    assert result2.proposals_rejected == 1
    assert result2.positions_opened == 0
    record = mocks["history"].load("cycle2")
    assert record.final_state == ProposalFinalState.GATE_REJECTED_OPERATOR_FREEZE.value
    # open_position was called exactly once across both cycles (cycle 1 only).
    mocks["trader"].open_position.assert_called_once()


# =============================================================================
# strategy-tuning DEBT-069(d): STRATEGY_ACTION_APPLIED emission
# =============================================================================


def _tuning_sub_account(
    overrides: dict[str, StrategyOverride],
) -> SubAccount:
    return SubAccount(
        id="lab",
        name="Lab",
        mode="paper",
        exchange_ref="default",
        capital_policy=CapitalPolicy(initial_balance={"USDT": Decimal("10000")}),
        strategy_tuning=StrategyTuningPolicy(
            enabled=True,
            strategy_overrides=overrides,
        ),
    )


def _strategy_applied_events(activity_log: ActivityLog) -> list[dict]:
    return [
        e.details or {}
        for e in activity_log.read_all()
        if e.event_type == ActivityEventType.STRATEGY_ACTION_APPLIED.value
    ]


@pytest.mark.asyncio
async def test_strategy_action_first_run_seeds_silently(tmp_path: Path) -> None:
    """No prior snapshot ⇒ seed the snapshot, emit zero events."""
    snapshot_path = tmp_path / "snap.json"
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        config=EngineConfig(strategy_action_snapshot_path=snapshot_path),
    )
    sub = _tuning_sub_account(
        {"rsi_universal": StrategyOverride(applied=StrategyAction.SCOUT)}
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub], {"lab": mocks["trader"]}
    )

    await engine.run_cycle()

    assert _strategy_applied_events(mocks["activity_log"]) == []
    assert snapshot_path.exists()


@pytest.mark.asyncio
async def test_strategy_action_changed_emits_one_event_per_change(
    tmp_path: Path,
) -> None:
    """A changed applied action across runs emits one event with full details."""
    snapshot_path = tmp_path / "snap.json"
    # First process: seed scout/pause.
    engine1, mocks1 = build_engine(
        tmp_path=tmp_path / "run1",
        config=EngineConfig(strategy_action_snapshot_path=snapshot_path),
    )
    sub1 = _tuning_sub_account(
        {
            "rsi_universal": StrategyOverride(applied=StrategyAction.SCOUT),
            "momentum_pinball_orb": StrategyOverride(applied=StrategyAction.PAUSE),
        }
    )
    engine1.sub_account_registry = FakeSubAccountRegistry(
        [sub1], {"lab": mocks1["trader"]}
    )
    await engine1.run_cycle()
    assert _strategy_applied_events(mocks1["activity_log"]) == []

    # Second process: rsi_universal flipped scout -> keep, orb unchanged.
    engine2, mocks2 = build_engine(
        tmp_path=tmp_path / "run2",
        config=EngineConfig(strategy_action_snapshot_path=snapshot_path),
    )
    sub2 = _tuning_sub_account(
        {
            "rsi_universal": StrategyOverride(applied=StrategyAction.KEEP),
            "momentum_pinball_orb": StrategyOverride(applied=StrategyAction.PAUSE),
        }
    )
    engine2.sub_account_registry = FakeSubAccountRegistry(
        [sub2], {"lab": mocks2["trader"]}
    )
    await engine2.run_cycle()

    events = _strategy_applied_events(mocks2["activity_log"])
    assert len(events) == 1
    assert events[0] == {
        "sub_account": "lab",
        "strategy": "rsi_universal",
        "prior_action": "scout",
        "new_action": "keep",
    }


@pytest.mark.asyncio
async def test_strategy_action_unchanged_emits_nothing(tmp_path: Path) -> None:
    """Identical applied state across runs ⇒ no events on the second run."""
    snapshot_path = tmp_path / "snap.json"
    engine1, mocks1 = build_engine(
        tmp_path=tmp_path / "run1",
        config=EngineConfig(strategy_action_snapshot_path=snapshot_path),
    )
    sub1 = _tuning_sub_account(
        {"rsi_universal": StrategyOverride(applied=StrategyAction.SCOUT)}
    )
    engine1.sub_account_registry = FakeSubAccountRegistry(
        [sub1], {"lab": mocks1["trader"]}
    )
    await engine1.run_cycle()

    engine2, mocks2 = build_engine(
        tmp_path=tmp_path / "run2",
        config=EngineConfig(strategy_action_snapshot_path=snapshot_path),
    )
    sub2 = _tuning_sub_account(
        {"rsi_universal": StrategyOverride(applied=StrategyAction.SCOUT)}
    )
    engine2.sub_account_registry = FakeSubAccountRegistry(
        [sub2], {"lab": mocks2["trader"]}
    )
    await engine2.run_cycle()

    assert _strategy_applied_events(mocks2["activity_log"]) == []


@pytest.mark.asyncio
async def test_strategy_action_diff_runs_once_per_process(tmp_path: Path) -> None:
    """The diff emitter is guarded so a second cycle does not re-emit."""
    snapshot_path = tmp_path / "snap.json"
    # Seed a prior snapshot so the first cycle below would emit if the guard
    # were absent on a subsequent cycle.
    from src.runtime.strategy_action_snapshot import save_snapshot

    save_snapshot({"lab": {"rsi_universal": "pause"}}, snapshot_path)

    engine, mocks = build_engine(
        tmp_path=tmp_path,
        config=EngineConfig(strategy_action_snapshot_path=snapshot_path),
    )
    sub = _tuning_sub_account(
        {"rsi_universal": StrategyOverride(applied=StrategyAction.SCOUT)}
    )
    engine.sub_account_registry = FakeSubAccountRegistry(
        [sub], {"lab": mocks["trader"]}
    )

    await engine.run_cycle()
    await engine.run_cycle()

    # pause -> scout transition emitted exactly once across both cycles.
    events = _strategy_applied_events(mocks["activity_log"])
    assert len(events) == 1
    assert events[0]["prior_action"] == "pause"
    assert events[0]["new_action"] == "scout"

"""Normal aged entries and real bound recovery have distinct close labels."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.exchange.base import BaseExchange
from src.models import Order, OrderStatus, Position, Ticker
from src.runtime.activity_log import ActivityLog
from src.runtime.engine import CycleResult
from src.runtime.position_monitor import PositionMonitor
from src.strategy.trade_history import TradeHistoryTracker
from src.trading.live import LiveTrader
from src.trading.paper import ZERO_FEE_CONFIG, PaperTrader
from src.utils.time import now_utc


def position():
    return Position(
        symbol="BTC/USDT",
        side="long",
        entry_price=Decimal("50000"),
        quantity=Decimal("0.1"),
        leverage=10,
        stop_loss=Decimal("49000"),
        take_profit=Decimal("52000"),
    )


def exchange_at(price):
    exchange = MagicMock(spec=BaseExchange)
    exchange.testnet = False
    exchange.name = "mock"
    exchange.get_ticker = AsyncMock(
        return_value=Ticker(symbol="BTC/USDT", price=price, timestamp=now_utc())
    )
    exchange.create_order = AsyncMock(
        side_effect=[
            Order(
                id=str(i),
                symbol="BTC/USDT",
                side=side,
                type="market",
                quantity=Decimal("0.1"),
                filled_quantity=Decimal("0.1"),
                average_price=fill,
                fee=Decimal("0"),
                fee_currency="USDT",
                status=OrderStatus.FILLED,
                created_at=now_utc(),
            )
            for i, side, fill in [(0, "buy", Decimal("50000")), (1, "sell", price)]
        ]
    )
    return exchange


def monitor(tmp_path, exchange):
    engine = PositionMonitor(
        activity_log=ActivityLog(path=tmp_path / "activity.jsonl"),
        proposal_engine=MagicMock(),
        default_exchange=exchange,
        remember_mark_price=MagicMock(),
        record_closed_trade=MagicMock(),
        find_proposal_record_for_trade=lambda _: None,
    )
    # The tests exercise the bound rung; existing engine tests cover lower rungs.
    engine._maybe_time_stop = AsyncMock(return_value=False)
    engine._maybe_stale_age_action = AsyncMock(return_value=False)
    return engine


@pytest.mark.parametrize("mode", ["paper", "live"])
@pytest.mark.parametrize(
    "reason,price", [("stop_loss", Decimal("48000")), ("take_profit", Decimal("53000"))]
)
async def test_real_normal_open_26h_null_reverse_link_preserves_trigger(
    tmp_path, mode, reason, price
):
    exchange = exchange_at(price)
    if mode == "paper":
        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path / "trades",
            fee_config=ZERO_FEE_CONFIG,
        )
    else:
        trader = LiveTrader(
            exchange=exchange,
            data_dir=tmp_path / "trades",
            confirmation_callback=AsyncMock(return_value=True),
        )
    opened = await trader.open_position(position())
    assert opened.performance_record_id is None
    opened.entry_time = now_utc() - timedelta(hours=26)
    TradeHistoryTracker(data_dir=tmp_path / "trades")._update_trade(opened)
    result = CycleResult(cycle_id="normal")
    await monitor(tmp_path, exchange).monitor("normal", result, None, trader)
    closed = trader.get_trade(opened.id)
    assert result.positions_closed == 1
    assert closed.close_reason == reason
    assert closed.pnl == (price - Decimal("50000")) * Decimal("0.1") - closed.fees
    if mode == "live":
        assert exchange.create_order.await_count == 2


async def recovered(tmp_path):
    trader = PaperTrader(
        initial_balance={"USDT": Decimal("10000")},
        data_dir=tmp_path / "trades",
        fee_config=ZERO_FEE_CONFIG,
    )
    trade = await trader.open_position(position())
    trade.entry_time = now_utc() - timedelta(hours=26)
    trade.stop_loss = trade.take_profit = None
    tracker = TradeHistoryTracker(data_dir=tmp_path / "trades")
    tracker._update_trade(trade)
    tracker.recover_trade_bounds(trade.id, Decimal("49000"), Decimal("52000"))
    return trader, trade.id


async def test_recovered_first_breach_is_conservative(tmp_path):
    trader, trade_id = await recovered(tmp_path)
    assert trader.get_trade(trade_id).bounds_recovery_pending
    result = CycleResult(cycle_id="recovered")
    await monitor(tmp_path, exchange_at(Decimal("53000"))).monitor(
        "recovered", result, None, trader
    )
    closed = trader.get_trade(trade_id)
    assert closed.close_reason == "orphan_force_close"
    assert closed.pnl == Decimal("300")


async def test_healthy_observation_survives_restart_and_later_bound_hit(tmp_path):
    trader, trade_id = await recovered(tmp_path)
    result = CycleResult(cycle_id="healthy")
    await monitor(tmp_path, exchange_at(Decimal("50000"))).monitor(
        "healthy", result, None, trader
    )
    assert result.positions_closed == 0
    assert not trader.get_trade(trade_id).bounds_recovery_pending
    restarted = PaperTrader(
        initial_balance={"USDT": Decimal("10000")},
        data_dir=tmp_path / "trades",
        fee_config=ZERO_FEE_CONFIG,
    )
    result = CycleResult(cycle_id="later")
    await monitor(tmp_path, exchange_at(Decimal("53000"))).monitor(
        "later", result, None, restarted
    )
    assert restarted.get_trade(trade_id).close_reason == "take_profit"


async def test_failed_acknowledgement_keeps_conservative_state_without_stopping_monitor(
    tmp_path, monkeypatch
):
    trader, trade_id = await recovered(tmp_path)
    monkeypatch.setattr(
        trader,
        "acknowledge_bounds_recovery",
        MagicMock(side_effect=OSError("disk unavailable")),
    )
    result = CycleResult(cycle_id="io-failure")
    await monitor(tmp_path, exchange_at(Decimal("50000"))).monitor(
        "io-failure", result, None, trader
    )
    assert result.positions_closed == 0
    assert trader.get_trade(trade_id).bounds_recovery_pending


async def test_young_repair_and_legacy_default(tmp_path):
    trader, trade_id = await recovered(tmp_path)
    trade = trader.get_trade(trade_id)
    trade.entry_time = now_utc() - timedelta(hours=1)
    assert (
        PositionMonitor._close_reason_for_bound_exit(trade, "take_profit")
        == "take_profit"
    )
    assert (
        PositionMonitor._close_reason_for_bound_exit(trade, "time_stop") == "time_stop"
    )


def test_failed_recovery_persistence_keeps_in_memory_bounds(tmp_path, monkeypatch):
    from src.strategy.performance import PerformanceRecord, PerformanceTracker

    perf = PerformanceRecord(
        technique_name="test",
        technique_version="1",
        symbol="BTC/USDT",
        timeframe="1h",
        signal="long",
        entry_price=Decimal("50000"),
        stop_loss=Decimal("49000"),
        take_profit=Decimal("52000"),
        confidence=0.8,
    )
    PerformanceTracker(data_dir=tmp_path / "performance").save_record(perf)
    tracker = TradeHistoryTracker(data_dir=tmp_path / "trades")
    trade = tracker.open_trade(
        symbol="BTC/USDT",
        side="long",
        entry_price=Decimal("50000"),
        entry_quantity=Decimal("0.1"),
        mode="paper",
        performance_record_id=perf.id,
    )
    monkeypatch.setattr(
        TradeHistoryTracker,
        "recover_trade_bounds",
        MagicMock(side_effect=OSError("disk unavailable")),
    )
    restarted = PaperTrader(
        initial_balance={"USDT": Decimal("10000")}, data_dir=tmp_path / "trades"
    )
    assert restarted.get_open_position(trade.id).position.stop_loss == Decimal("49000")
    assert restarted.get_trade(trade.id).stop_loss is None


def test_legacy_trade_defaults_to_no_recovery():
    from src.strategy.trade_history import TradeHistory

    trade = TradeHistory(
        symbol="BTC/USDT",
        side="long",
        mode="paper",
        entry_price=Decimal("50000"),
        entry_quantity=Decimal("0.1"),
    )
    payload = trade.model_dump(exclude={"bounds_recovery_pending"})
    assert not TradeHistory.model_validate(payload).bounds_recovery_pending

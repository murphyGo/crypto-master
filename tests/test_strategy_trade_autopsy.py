"""Tests for closed-trade autopsy evidence models."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.backtest.engine import BacktestTrade
from src.strategy.performance import TradeHistory
from src.strategy.trade_autopsy import (
    TradeAutopsy,
    TradeAutopsyError,
    TradeAutopsyOutcome,
)


def _dt(hour: int) -> datetime:
    return datetime(2026, 5, 7, hour, tzinfo=timezone.utc)


def test_trade_autopsy_from_closed_trade_history() -> None:
    trade = TradeHistory(
        id="trade-1",
        sub_account_id="lab",
        symbol="BTC/USDT",
        side="long",
        mode="paper",
        entry_price=Decimal("100"),
        entry_quantity=Decimal("2"),
        entry_time=_dt(1),
        exit_price=Decimal("110"),
        exit_quantity=Decimal("2"),
        exit_time=_dt(3),
        leverage=1,
        fees=Decimal("1"),
        pnl=Decimal("19"),
        pnl_percent=10.0,
        status="closed",
        close_reason="take_profit",
    )

    autopsy = TradeAutopsy.from_trade_history(trade)

    assert autopsy.trade_id == "trade-1"
    assert autopsy.sub_account_id == "lab"
    assert autopsy.mode == "paper"
    assert autopsy.outcome == TradeAutopsyOutcome.WIN
    assert autopsy.holding_seconds == 7200
    assert "closed by take_profit" in autopsy.evidence


def test_trade_autopsy_rejects_open_trade_history() -> None:
    trade = TradeHistory(
        id="trade-1",
        symbol="BTC/USDT",
        side="long",
        mode="paper",
        entry_price=Decimal("100"),
        entry_quantity=Decimal("2"),
        status="open",
    )

    with pytest.raises(TradeAutopsyError, match="not closed"):
        TradeAutopsy.from_trade_history(trade)


def test_trade_autopsy_from_backtest_trade() -> None:
    trade = BacktestTrade(
        trade_id="bt-1",
        symbol="ETH/USDT",
        side="short",
        entry_time=_dt(1),
        exit_time=_dt(2),
        entry_price=Decimal("100"),
        exit_price=Decimal("90"),
        quantity=Decimal("3"),
        leverage=1,
        stop_loss=Decimal("105"),
        take_profit=Decimal("90"),
        entry_fee=Decimal("0.5"),
        exit_fee=Decimal("0.5"),
        pnl=Decimal("29"),
        close_reason="take_profit",
        sub_account_id="lab",
        technique_name="short_lab",
    )

    autopsy = TradeAutopsy.from_backtest_trade(trade)

    assert autopsy.trade_id == "bt-1"
    assert autopsy.mode == "backtest"
    assert autopsy.sub_account_id == "lab"
    assert autopsy.fees == Decimal("1.0")
    assert autopsy.outcome == TradeAutopsyOutcome.WIN
    assert autopsy.pnl_percent == pytest.approx(9.6666666667)


def test_trade_autopsy_zero_pnl_is_breakeven() -> None:
    trade = BacktestTrade(
        trade_id="bt-1",
        symbol="ETH/USDT",
        side="long",
        entry_time=_dt(1),
        exit_time=_dt(1),
        entry_price=Decimal("100"),
        exit_price=Decimal("100"),
        quantity=Decimal("1"),
        leverage=1,
        stop_loss=Decimal("95"),
        take_profit=Decimal("105"),
        entry_fee=Decimal("0"),
        exit_fee=Decimal("0"),
        pnl=Decimal("0"),
        close_reason="end_of_data",
    )

    autopsy = TradeAutopsy.from_backtest_trade(trade)

    assert autopsy.outcome == TradeAutopsyOutcome.BREAKEVEN
    assert autopsy.holding_seconds == 0

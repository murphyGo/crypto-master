"""Tests for closed-trade autopsy evidence models."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.backtest.engine import BacktestTrade
from src.models import OHLCV
from src.strategy.performance import TradeHistory
from src.strategy.trade_autopsy import (
    TradeAutopsy,
    TradeAutopsyError,
    TradeAutopsyOutcome,
)


def _dt(hour: int) -> datetime:
    return datetime(2026, 5, 7, hour, tzinfo=timezone.utc)


def _candle(
    hour: int,
    *,
    high: str,
    low: str,
) -> OHLCV:
    return OHLCV(
        timestamp=_dt(hour),
        open=Decimal("100"),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal("100"),
        volume=Decimal("1"),
    )


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


def test_trade_autopsy_candle_metrics_for_long_trade() -> None:
    autopsy = TradeAutopsy(
        trade_id="trade-1",
        symbol="BTC/USDT",
        side="long",
        mode="backtest",
        entry_time=_dt(1),
        exit_time=_dt(3),
        entry_price=Decimal("100"),
        exit_price=Decimal("103"),
        quantity=Decimal("1"),
        leverage=1,
        pnl=Decimal("3"),
        close_reason="end_of_data",
        holding_seconds=7200,
        outcome=TradeAutopsyOutcome.WIN,
    )

    enriched = autopsy.with_candle_window(
        [
            _candle(0, high="200", low="1"),
            _candle(1, high="104", low="98"),
            _candle(2, high="110", low="95"),
            _candle(3, high="106", low="99"),
            _candle(4, high="300", low="1"),
        ]
    )

    assert enriched.max_favorable_excursion_percent == pytest.approx(10.0)
    assert enriched.max_adverse_excursion_percent == pytest.approx(5.0)
    assert enriched.drawdown_before_exit_percent == pytest.approx(5.0)
    assert "candle_window=3" in enriched.evidence


def test_trade_autopsy_candle_metrics_for_short_trade() -> None:
    autopsy = TradeAutopsy(
        trade_id="trade-1",
        symbol="BTC/USDT",
        side="short",
        mode="backtest",
        entry_time=_dt(1),
        exit_time=_dt(3),
        entry_price=Decimal("100"),
        exit_price=Decimal("95"),
        quantity=Decimal("1"),
        leverage=1,
        pnl=Decimal("5"),
        close_reason="take_profit",
        holding_seconds=7200,
        outcome=TradeAutopsyOutcome.WIN,
    )

    enriched = autopsy.with_candle_window(
        [
            _candle(1, high="103", low="94"),
            _candle(2, high="108", low="90"),
            _candle(3, high="101", low="96"),
        ]
    )

    assert enriched.max_favorable_excursion_percent == pytest.approx(10.0)
    assert enriched.max_adverse_excursion_percent == pytest.approx(8.0)
    assert enriched.drawdown_before_exit_percent == pytest.approx(8.0)


def test_trade_autopsy_candle_metrics_require_overlap() -> None:
    autopsy = TradeAutopsy(
        trade_id="trade-1",
        symbol="BTC/USDT",
        side="long",
        mode="backtest",
        entry_time=_dt(1),
        exit_time=_dt(2),
        entry_price=Decimal("100"),
        exit_price=Decimal("100"),
        quantity=Decimal("1"),
        leverage=1,
        pnl=Decimal("0"),
        close_reason="end_of_data",
        holding_seconds=3600,
        outcome=TradeAutopsyOutcome.BREAKEVEN,
    )

    with pytest.raises(TradeAutopsyError, match="no candles overlap"):
        autopsy.with_candle_window([_candle(3, high="101", low="99")])

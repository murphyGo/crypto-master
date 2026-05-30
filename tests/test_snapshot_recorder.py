"""Unit tests for :class:`SnapshotRecorder` (CAH-15 Slice 1, ADR 0001).

These exercise the recorder in isolation from ``TradingEngine``. The
end-to-end behaviour-preservation proof lives in ``test_runtime_engine.py``
(the snapshot / closed-trade / mark-price-cache suites pass unchanged through
the engine's delegating wrappers); here we pin the extracted collaborator's
own contract — most importantly the ADR CHANGE-B mark-price write-through
firing through the **injected** callback, never a chained one.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models import Ticker
from src.runtime.activity_log import ActivityEventType, ActivityLog
from src.runtime.snapshot_recorder import SnapshotRecorder
from src.strategy.performance import PerformanceTracker, TradeHistory, TradeOutcome
from src.trading.portfolio import PortfolioTracker
from src.utils.time import now_utc


def _trade(
    *,
    trade_id: str = "t-1",
    symbol: str = "BTC/USDT",
    side: str = "long",
    status: str = "open",
    exit_price: str | None = None,
    pnl_percent: float | None = None,
    sub_account_id: str = "default",
) -> TradeHistory:
    return TradeHistory(
        id=trade_id,
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        mode="paper",
        entry_price=Decimal("50000"),
        entry_quantity=Decimal("0.1"),
        entry_time=datetime(2026, 4, 27, 12, 0, 0),
        exit_price=Decimal(exit_price) if exit_price is not None else None,
        exit_quantity=Decimal("0.1") if exit_price is not None else None,
        exit_time=now_utc() if exit_price is not None else None,
        pnl=None,
        pnl_percent=pnl_percent,
        status=status,  # type: ignore[arg-type]
        sub_account_id=sub_account_id,
    )


def _build_recorder(
    tmp_path: Path,
    *,
    portfolio_tracker: PortfolioTracker | None = None,
    proposal_history: MagicMock | None = None,
    remember_calls: list[tuple[str, Decimal]] | None = None,
    default_exchange: MagicMock | None = None,
) -> SnapshotRecorder:
    def _remember(symbol: str, price: Decimal) -> None:
        if remember_calls is not None:
            remember_calls.append((symbol, price))

    return SnapshotRecorder(
        proposal_history=proposal_history or MagicMock(),
        activity_log=ActivityLog(path=tmp_path / "activity.jsonl"),
        proposal_engine=MagicMock(performance_tracker=None),
        portfolio_tracker=portfolio_tracker,
        default_exchange=default_exchange or MagicMock(),
        remember_mark_price=_remember,
        mode="paper",
        quote_currency="USDT",
    )


async def test_snapshot_skipped_when_tracker_absent(tmp_path: Path) -> None:
    """No portfolio tracker -> early return, no balance fetch attempted."""
    trader = MagicMock()
    trader.get_balances = AsyncMock()
    recorder = _build_recorder(tmp_path, portfolio_tracker=None)

    await recorder.record_portfolio_snapshot("cyc", None, trader)

    trader.get_balances.assert_not_called()


async def test_snapshot_write_through_fires_injected_callback(tmp_path: Path) -> None:
    """ADR CHANGE B: every per-trade ticker read writes through the callback.

    The recorder must populate the engine-owned mark cache via the
    *injected* ``remember_mark_price`` — one call per open trade, with the
    same (symbol, price) the AssetSnapshot's ``current_prices`` records.
    """
    remember_calls: list[tuple[str, Decimal]] = []
    tracker = PortfolioTracker(data_dir=tmp_path / "portfolio")

    trader = MagicMock()
    trader.get_balances = AsyncMock(return_value={"USDT": Decimal("1000")})
    trader.get_open_trades = MagicMock(
        return_value=[
            _trade(trade_id="t-eth", symbol="ETH/USDT"),
            _trade(trade_id="t-bnb", symbol="BNB/USDT", side="short"),
        ]
    )

    prices = {"ETH/USDT": Decimal("2500"), "BNB/USDT": Decimal("700")}
    exchange = MagicMock()
    exchange.get_ticker = AsyncMock(
        side_effect=lambda symbol: Ticker(
            symbol=symbol, price=prices[symbol], timestamp=now_utc()
        )
    )

    recorder = _build_recorder(
        tmp_path,
        portfolio_tracker=tracker,
        remember_calls=remember_calls,
        default_exchange=exchange,
    )

    await recorder.record_portfolio_snapshot("cyc", None, trader)

    assert remember_calls == [
        ("ETH/USDT", Decimal("2500")),
        ("BNB/USDT", Decimal("700")),
    ]
    snaps = tracker.load_snapshots("paper")
    assert len(snaps) == 1
    assert snaps[0].current_prices == prices


async def test_snapshot_uses_default_exchange_when_none_passed(tmp_path: Path) -> None:
    """``exchange=None`` falls back to the injected default exchange."""
    tracker = PortfolioTracker(data_dir=tmp_path / "portfolio")
    trader = MagicMock()
    trader.get_balances = AsyncMock(return_value={})
    trader.get_open_trades = MagicMock(return_value=[_trade(symbol="SOL/USDT")])
    default_exchange = MagicMock()
    default_exchange.get_ticker = AsyncMock(
        return_value=Ticker(
            symbol="SOL/USDT", price=Decimal("150"), timestamp=now_utc()
        )
    )
    recorder = _build_recorder(
        tmp_path, portfolio_tracker=tracker, default_exchange=default_exchange
    )

    await recorder.record_portfolio_snapshot("cyc", None, trader)

    default_exchange.get_ticker.assert_awaited_once_with("SOL/USDT")


async def test_record_closed_trade_emits_position_closed_and_attaches_outcome(
    tmp_path: Path,
) -> None:
    """Closed trade -> POSITION_CLOSED event + outcome attached to its proposal."""
    history = MagicMock()
    record = MagicMock()
    record.proposal.proposal_id = "p-1"
    record.proposal.technique_name = "rsi_universal"
    record.trade_id = "t-close"
    history.list_all = MagicMock(return_value=[record])
    history.attach_outcome = MagicMock()

    recorder = _build_recorder(tmp_path, proposal_history=history)
    trade = _trade(
        trade_id="t-close", status="closed", exit_price="51000", pnl_percent=2.0
    )

    recorder.record_closed_trade(trade, "take_profit", "cyc")

    history.attach_outcome.assert_called_once_with(
        "p-1", trade_id="t-close", pnl_percent=2.0
    )
    closed = [
        e
        for e in recorder.activity_log.read_all()
        if e.event_type == ActivityEventType.POSITION_CLOSED
    ]
    assert len(closed) == 1
    assert closed[0].details["reason"] == "take_profit"
    assert closed[0].details["technique_name"] == "rsi_universal"


async def test_record_closed_trade_handles_unknown_proposal(tmp_path: Path) -> None:
    """A trade with no matching proposal still logs, with null ids/technique."""
    history = MagicMock()
    history.list_all = MagicMock(return_value=[])
    history.attach_outcome = MagicMock()
    recorder = _build_recorder(tmp_path, proposal_history=history)
    trade = _trade(trade_id="orphan", status="closed", exit_price="49000")

    recorder.record_closed_trade(trade, "stop_loss", "cyc")

    history.attach_outcome.assert_not_called()
    closed = [
        e
        for e in recorder.activity_log.read_all()
        if e.event_type == ActivityEventType.POSITION_CLOSED
    ]
    assert len(closed) == 1
    assert closed[0].details["proposal_id"] is None
    assert closed[0].details["technique_name"] is None


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("take_profit", TradeOutcome.WIN),
        ("stop_loss", TradeOutcome.LOSS),
        ("time_stop", TradeOutcome.BREAKEVEN),
        ("orphan_force_close", TradeOutcome.BREAKEVEN),
    ],
)
def test_classify_close_reason(reason: str, expected: TradeOutcome) -> None:
    assert SnapshotRecorder._classify_close_reason(reason) is expected


def test_find_proposal_record_for_trade_matches_then_misses(tmp_path: Path) -> None:
    history = MagicMock()
    match = MagicMock()
    match.trade_id = "t-hit"
    other = MagicMock()
    other.trade_id = "t-other"
    history.list_all = MagicMock(return_value=[other, match])
    recorder = _build_recorder(tmp_path, proposal_history=history)

    assert recorder.find_proposal_record_for_trade("t-hit") is match
    assert recorder.find_proposal_record_for_trade("t-missing") is None


def test_save_performance_record_routes_to_trade_sub_account(tmp_path: Path) -> None:
    """The perf row lands under the *trade's* sub-account path, not default."""
    tracker = PerformanceTracker(data_dir=tmp_path / "performance")
    proposal = MagicMock()
    proposal.technique_name = "vcp_breakout"
    proposal.technique_version = "1"
    proposal.symbol = "BTC/USDT"
    proposal.timeframe = "4h"
    proposal.signal = "long"
    proposal.entry_price = Decimal("50000")
    proposal.stop_loss = Decimal("49000")
    proposal.take_profit = Decimal("52000")
    proposal.score.confidence = 0.8
    proposal.created_at = now_utc()
    proposal.profile_name = None
    record = MagicMock()
    record.proposal = proposal

    recorder = _build_recorder(tmp_path)
    recorder.proposal_engine = MagicMock(performance_tracker=tracker)
    trade = _trade(
        trade_id="beta-closed",
        status="closed",
        exit_price="52000",
        pnl_percent=4.0,
        sub_account_id="beta",
    )

    recorder._save_performance_record(record, trade, "take_profit")

    assert (
        tmp_path / "performance" / "beta" / "vcp_breakout" / "records.json"
    ).exists()
    assert not (tmp_path / "performance" / "default").exists()

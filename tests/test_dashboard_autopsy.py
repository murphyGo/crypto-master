"""Tests for the trade autopsy dashboard page."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.dashboard.pages.autopsy import build_autopsy_dataframe, build_trade_autopsies
from src.strategy.performance import TradeHistory

APP_PATH = str(Path(__file__).resolve().parents[1] / "src" / "dashboard" / "app.py")


def _trade(
    *,
    trade_id: str,
    status: str = "closed",
    pnl: Decimal | None = Decimal("10"),
) -> TradeHistory:
    entry_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return TradeHistory(
        id=trade_id,
        symbol="BTC/USDT",
        side="long",  # type: ignore[arg-type]
        mode="paper",
        entry_price=Decimal("100"),
        entry_quantity=Decimal("1"),
        entry_time=entry_time,
        exit_price=Decimal("110") if status == "closed" else None,
        exit_quantity=Decimal("1") if status == "closed" else None,
        exit_time=entry_time + timedelta(hours=1) if status == "closed" else None,
        pnl=pnl,
        pnl_percent=10.0 if pnl is not None else None,
        status=status,  # type: ignore[arg-type]
        close_reason="take_profit" if status == "closed" else None,
        sub_account_id="lab",
    )


def test_build_trade_autopsies_uses_closed_complete_trades_only() -> None:
    autopsies = build_trade_autopsies(
        [
            _trade(trade_id="closed-1"),
            _trade(trade_id="open-1", status="open"),
            _trade(trade_id="missing-pnl", pnl=None),
        ]
    )

    assert [autopsy.trade_id for autopsy in autopsies] == ["closed-1"]
    assert autopsies[0].outcome.value == "win"
    assert "closed by take_profit" in autopsies[0].evidence


def test_build_autopsy_dataframe_empty_has_operator_columns() -> None:
    df = build_autopsy_dataframe([])

    assert df.empty
    assert "MFE %" in df.columns
    assert "MAE %" in df.columns


def test_build_autopsy_dataframe_renders_summary_fields() -> None:
    autopsies = build_trade_autopsies([_trade(trade_id="closed-1")])

    df = build_autopsy_dataframe(autopsies)

    assert df.iloc[0]["Trade ID"] == "closed-1"
    assert df.iloc[0]["Outcome"] == "win"
    assert df.iloc[0]["Sub-account"] == "lab"


def test_app_runs_with_autopsy_page_registered() -> None:
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    assert not at.exception, [str(e) for e in at.exception]

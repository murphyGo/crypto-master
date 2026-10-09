"""Default page routes cannot return to the incident's full-history path."""

from datetime import datetime, timezone

import pytest
from streamlit.testing.v1 import AppTest

from src.config import Settings
from src.dashboard.data_service import DashboardDataService
from src.dashboard.pages import feedback, home, ops, trading
from src.runtime.activity_log import ActivityLog
from src.strategy.trade_history import TradeHistoryTracker
from src.trading.portfolio import PortfolioTracker
from tests.test_dashboard_trading import make_snapshot, make_trade


@pytest.fixture
def bounded_pages(tmp_path, monkeypatch):
    from src.dashboard import data_service
    from src.feedback import audit
    from src.proposal import interaction
    from src.runtime import activity_log

    settings = Settings(data_dir=tmp_path)
    for module in (trading, home, ops, feedback, interaction, activity_log, audit):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(trading, "discover_configured_sub_account_ids", lambda *_: [])
    service = DashboardDataService()
    monkeypatch.setattr(data_service, "get_data_service", lambda: service)

    def forbidden(*args, **kwargs):
        pytest.fail("default page called a full-history materializer")

    monkeypatch.setattr(ActivityLog, "read_all", forbidden)
    monkeypatch.setattr(interaction.ProposalHistory, "list_all", forbidden)
    monkeypatch.setattr(TradeHistoryTracker, "load_trades", forbidden)
    monkeypatch.setattr(PortfolioTracker, "load_snapshots", forbidden)
    monkeypatch.setattr(feedback, "load_candidate_records", forbidden)
    directory = tmp_path / "trades" / "paper" / "default"
    directory.mkdir(parents=True)
    directory.joinpath("trades.json").write_text(
        "[" + make_trade().model_dump_json() + "]"
    )
    portfolio = tmp_path / "portfolio" / "paper" / "default"
    portfolio.mkdir(parents=True)
    portfolio.joinpath("snapshots.json").write_text(
        "["
        + make_snapshot(
            timestamp=datetime.now(timezone.utc), quote_balance="100"
        ).model_dump_json()
        + "]"
    )
    yield tmp_path
    service.close()


@pytest.mark.parametrize(
    "page,entry",
    [
        ("trading", "render"),
        ("home", "render_home"),
        ("engine", "render"),
        ("ops", "render"),
        ("proposals", "render"),
        ("feedback", "render"),
    ],
)
def test_default_pages_render_without_full_history_materializers(
    bounded_pages, page, entry
):
    at = AppTest.from_string(
        f"from src.dashboard.pages.{page} import {entry}\n{entry}()"
    ).run(timeout=10)
    assert not at.exception
    assert at.title


def test_trading_bad_activity_retains_verified_ledger_and_no_healthy_banner(
    bounded_pages,
):
    runtime = bounded_pages / "runtime"
    runtime.mkdir()
    runtime.joinpath("activity.jsonl").write_text("broken\n")
    at = AppTest.from_string(
        "from src.dashboard.pages.trading import render\nrender()"
    ).run(timeout=10)
    assert not at.exception
    assert any("Runtime reconciliation" in row.value for row in at.warning)
    assert not at.success
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics["Open Positions"] == "1"
    assert metrics["Current Equity"] == "100.00 USDT"
    assert not any("No open positions" in message.value for message in at.info)

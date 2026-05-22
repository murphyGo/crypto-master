"""Tests for the Trading status page (Phase 7.3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from src.dashboard.pages.trading import (
    DEFAULT_HISTORY_LIMIT,
    build_comparative_equity_dataframe,
    build_equity_curve_dataframe,
    build_open_positions_dataframe,
    build_summary_metrics,
    build_trade_history_dataframe,
    discover_configured_sub_account_ids,
    discover_sub_account_ids,
    latest_snapshot_current_prices,
    merge_sub_account_ids,
)
from src.proposal.engine import Proposal, ProposalScore
from src.proposal.interaction import (
    ProposalDecision,
    ProposalHistory,
    ProposalRecord,
)
from src.strategy.performance import TradeHistory
from src.trading.portfolio import AssetSnapshot

# =============================================================================
# Helpers
# =============================================================================


def make_trade(
    *,
    trade_id: str = "trade-id-12345678",
    symbol: str = "BTC/USDT",
    side: str = "long",
    mode: str = "paper",
    entry_price: str = "50000",
    entry_quantity: str = "0.1",
    entry_time: datetime | None = None,
    exit_price: str | None = None,
    exit_quantity: str | None = None,
    exit_time: datetime | None = None,
    leverage: int = 1,
    pnl: str | None = None,
    pnl_percent: float | None = None,
    status: str = "open",
    close_reason: str | None = None,
) -> TradeHistory:
    return TradeHistory(
        id=trade_id,
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        mode=mode,  # type: ignore[arg-type]
        entry_price=Decimal(entry_price),
        entry_quantity=Decimal(entry_quantity),
        entry_time=entry_time or datetime(2026, 1, 1, 12, 0, 0),
        exit_price=Decimal(exit_price) if exit_price is not None else None,
        exit_quantity=Decimal(exit_quantity) if exit_quantity is not None else None,
        exit_time=exit_time,
        leverage=leverage,
        pnl=Decimal(pnl) if pnl is not None else None,
        pnl_percent=pnl_percent,
        status=status,  # type: ignore[arg-type]
        close_reason=close_reason,
    )


def make_snapshot(
    *,
    timestamp: datetime,
    quote_currency: str = "USDT",
    quote_balance: str = "10000",
    realized_pnl: str = "0",
    unrealized_pnl: str = "0",
    current_prices: dict[str, Decimal] | None = None,
) -> AssetSnapshot:
    return AssetSnapshot(
        timestamp=timestamp,
        mode="paper",
        quote_currency=quote_currency,
        balances={quote_currency: Decimal(quote_balance)},
        realized_pnl=Decimal(realized_pnl),
        unrealized_pnl=Decimal(unrealized_pnl),
        current_prices=current_prices or {},
    )


def _make_proposal(proposal_id: str) -> Proposal:
    """Build a minimal valid Proposal for ProposalHistory fixtures."""
    return Proposal(
        proposal_id=proposal_id,
        symbol="BTC/USDT",
        timeframe="1h",
        technique_name="tech_a",
        technique_version="1.0.0",
        signal="long",
        entry_price=Decimal("50000"),
        stop_loss=Decimal("49500"),
        take_profit=Decimal("51500"),
        quantity=Decimal("0.1"),
        leverage=1,
        risk_reward_ratio=3.0,
        score=ProposalScore(
            confidence=0.8,
            win_rate=0.6,
            sample_size=25,
            expected_value=2.0,
            sample_factor=1.0,
            edge_factor=2.0,
            composite=0.45,
        ),
        reasoning="test",
    )


# =============================================================================
# build_open_positions_dataframe
# =============================================================================


def test_open_positions_includes_only_open_trades() -> None:
    open_trade = make_trade(trade_id="open-1", status="open")
    closed_trade = make_trade(
        trade_id="closed-1",
        status="closed",
        exit_price="51000",
        exit_quantity="0.1",
        exit_time=datetime(2026, 1, 2),
    )

    df = build_open_positions_dataframe([open_trade, closed_trade])

    assert len(df) == 1
    assert df.iloc[0]["Trade ID"] == "open-1"[:8]


def test_open_positions_sorts_newest_first() -> None:
    older = make_trade(
        trade_id="older-1",
        entry_time=datetime(2026, 1, 1),
    )
    newer = make_trade(
        trade_id="newer-1",
        entry_time=datetime(2026, 1, 5),
    )

    df = build_open_positions_dataframe([older, newer])

    assert df.iloc[0]["Trade ID"] == "newer-1"[:8]


def test_open_positions_empty_returns_empty_frame_with_columns() -> None:
    df = build_open_positions_dataframe([])

    assert df.empty
    assert "Symbol" in df.columns
    assert "Side" in df.columns


def test_open_positions_uppercase_side() -> None:
    long_trade = make_trade(trade_id="long-1", side="long")
    short_trade = make_trade(trade_id="short-1", side="short")

    df = build_open_positions_dataframe([long_trade, short_trade])

    sides = set(df["Side"])
    assert sides == {"LONG", "SHORT"}


def test_open_positions_includes_current_pnl_when_price_available() -> None:
    long_trade = make_trade(
        trade_id="long-1",
        side="long",
        entry_price="50000",
        entry_quantity="0.1",
    )
    short_trade = make_trade(
        trade_id="short-1",
        symbol="ETH/USDT",
        side="short",
        entry_price="3000",
        entry_quantity="2",
    )

    df = build_open_positions_dataframe(
        [long_trade, short_trade],
        current_prices={
            "BTC/USDT": Decimal("51000"),
            "ETH/USDT": Decimal("2900"),
        },
    )

    by_symbol = {row["Symbol"]: row for row in df.to_dict("records")}
    assert by_symbol["BTC/USDT"]["Current Price"] == 51000.0
    assert by_symbol["BTC/USDT"]["Current P&L"] == pytest.approx(100.0)
    assert by_symbol["BTC/USDT"]["Current P&L %"] == pytest.approx(2.0)
    assert by_symbol["ETH/USDT"]["Current P&L"] == pytest.approx(200.0)
    assert by_symbol["ETH/USDT"]["Current P&L %"] == pytest.approx(3.33)


def test_open_positions_leaves_current_pnl_blank_without_price() -> None:
    trade = make_trade(symbol="BTC/USDT")

    df = build_open_positions_dataframe([trade], current_prices={})

    row = df.iloc[0]
    assert row["Current Price"] is None
    assert row["Current P&L"] is None
    assert row["Current P&L %"] is None


# =============================================================================
# build_trade_history_dataframe
# =============================================================================


def test_trade_history_sorts_by_when_descending() -> None:
    closed_old = make_trade(
        trade_id="cl-old",
        status="closed",
        entry_time=datetime(2026, 1, 1),
        exit_time=datetime(2026, 1, 2),
        exit_price="51000",
        exit_quantity="0.1",
        pnl="100",
        pnl_percent=2.0,
    )
    closed_new = make_trade(
        trade_id="cl-new",
        status="closed",
        entry_time=datetime(2026, 1, 5),
        exit_time=datetime(2026, 1, 6),
        exit_price="49000",
        exit_quantity="0.1",
        pnl="-100",
        pnl_percent=-2.0,
    )
    open_recent = make_trade(
        trade_id="op-rec",
        status="open",
        entry_time=datetime(2026, 1, 7),
    )

    df = build_trade_history_dataframe([closed_old, closed_new, open_recent])

    assert list(df["Trade ID"]) == ["op-rec"[:8], "cl-new"[:8], "cl-old"[:8]]


def test_trade_history_truncates_to_limit() -> None:
    trades = [
        make_trade(
            trade_id=f"trade-{i}",
            status="closed",
            entry_time=datetime(2026, 1, 1) + timedelta(hours=i),
            exit_time=datetime(2026, 1, 1) + timedelta(hours=i + 1),
            exit_price="51000",
            exit_quantity="0.1",
            pnl="10",
            pnl_percent=0.5,
        )
        for i in range(50)
    ]

    df = build_trade_history_dataframe(trades, limit=5)

    assert len(df) == 5


def test_trade_history_default_limit_constant() -> None:
    """Sanity: the default limit is reasonable (visual table size)."""
    assert 10 <= DEFAULT_HISTORY_LIMIT <= 100


def test_trade_history_renders_open_with_none_exit_fields() -> None:
    open_trade = make_trade(trade_id="open-1", status="open")

    df = build_trade_history_dataframe([open_trade])

    row = df.iloc[0]
    assert row["Status"] == "open"
    assert row["Exit Price"] is None
    assert row["P&L %"] is None
    assert row["Close Reason"] == "—"


def test_trade_history_empty_returns_empty_frame_with_columns() -> None:
    df = build_trade_history_dataframe([])

    assert df.empty
    assert "Trade ID" in df.columns
    assert "P&L %" in df.columns


# =============================================================================
# build_equity_curve_dataframe
# =============================================================================


def test_equity_curve_sorts_by_timestamp() -> None:
    t0 = datetime(2026, 1, 1)
    curve = [
        (t0 + timedelta(days=2), Decimal("11000")),
        (t0, Decimal("10000")),
        (t0 + timedelta(days=1), Decimal("10500")),
    ]

    df = build_equity_curve_dataframe(curve)

    assert list(df["equity"]) == [10000.0, 10500.0, 11000.0]


def test_equity_curve_empty_returns_empty_frame_with_columns() -> None:
    df = build_equity_curve_dataframe([])

    assert df.empty
    assert list(df.columns) == ["timestamp", "equity"]


def test_comparative_equity_curve_uses_one_column_per_sub_account() -> None:
    t0 = datetime(2026, 1, 1)
    df = build_comparative_equity_dataframe(
        {
            "default": [(t0, Decimal("10000"))],
            "experimental": [(t0, Decimal("2500"))],
        }
    )

    assert list(df.columns) == ["default", "experimental"]
    assert df.loc[t0, "default"] == 10000.0
    assert df.loc[t0, "experimental"] == 2500.0


def test_discover_sub_account_ids_default_first(tmp_path: Path) -> None:
    (tmp_path / "trades" / "paper" / "experimental").mkdir(parents=True)
    (tmp_path / "portfolio" / "paper" / "default").mkdir(parents=True)
    (tmp_path / "portfolio" / "paper" / "btc_only").mkdir(parents=True)

    assert discover_sub_account_ids(tmp_path, "paper") == [
        "default",
        "btc_only",
        "experimental",
    ]


def test_discover_configured_sub_account_ids_reads_enabled_mode(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "sub_accounts.yaml"
    config_path.write_text(
        """
sub_accounts:
  - id: default
    mode: paper
    enabled: false
  - id: rsi_4h
    mode: paper
    enabled: true
  - id: live_only
    mode: live
    enabled: true
  - id: ma_crossover
    mode: paper
""",
        encoding="utf-8",
    )

    assert discover_configured_sub_account_ids(config_path, "paper") == [
        "rsi_4h",
        "ma_crossover",
    ]
    assert discover_configured_sub_account_ids(config_path, "live") == ["live_only"]


def test_merge_sub_account_ids_prefers_config_order_then_persisted() -> None:
    assert merge_sub_account_ids(
        ["rsi_4h", "ma_crossover"],
        ["default", "rsi_4h", "vcp_breakout"],
    ) == ["rsi_4h", "ma_crossover", "default", "vcp_breakout"]


# =============================================================================
# build_summary_metrics
# =============================================================================


def test_summary_metrics_empty_inputs(tmp_path: Path) -> None:
    metrics = build_summary_metrics([], [], ProposalHistory(data_dir=tmp_path))

    assert metrics["open_positions"] == 0
    assert metrics["closed_trades"] == 0
    assert metrics["win_rate"] == 0.0
    assert metrics["realized_pnl"] == 0.0
    assert metrics["unrealized_pnl"] == 0.0
    assert metrics["latest_equity"] == 0.0
    assert metrics["latest_snapshot_at"] is None
    assert metrics["proposals_rejected_threshold_count"] == 0


def test_summary_metrics_counts_open_and_closed() -> None:
    trades = [
        make_trade(trade_id="o1", status="open"),
        make_trade(trade_id="o2", status="open"),
        make_trade(
            trade_id="c1",
            status="closed",
            exit_price="51000",
            exit_quantity="0.1",
            exit_time=datetime(2026, 1, 2),
            pnl="100",
            pnl_percent=2.0,
        ),
    ]

    metrics = build_summary_metrics(trades, [])

    assert metrics["open_positions"] == 2
    assert metrics["closed_trades"] == 1


def test_summary_metrics_win_rate() -> None:
    """Win == take-profit close (matches PerformanceSummary).

    Two of four closed trades hit take-profit → 0.5. A positive-P&L
    manual close is *not* a win, and opens are excluded.
    """
    trades = [
        make_trade(
            trade_id=f"c{i}",
            status="closed",
            exit_price="50000",
            exit_quantity="0.1",
            exit_time=datetime(2026, 1, 2),
            pnl="0",
            pnl_percent=pnl,
            close_reason=reason,
        )
        for i, (pnl, reason) in enumerate(
            [
                (3.0, "take_profit"),
                (-1.0, "stop_loss"),
                (2.0, "take_profit"),
                (1.5, "manual"),
            ]
        )
    ]
    trades.append(make_trade(trade_id="open-x", status="open"))

    metrics = build_summary_metrics(trades, [])

    assert metrics["win_rate"] == pytest.approx(0.5)


def test_summary_metrics_realized_pnl_sums_closed_only() -> None:
    closed = [
        make_trade(
            trade_id=f"c{i}",
            status="closed",
            exit_price="50000",
            exit_quantity="0.1",
            exit_time=datetime(2026, 1, 2),
            pnl=pnl_str,
            pnl_percent=0.0,
        )
        for i, pnl_str in enumerate(["100", "-50", "25"])
    ]
    open_t = make_trade(trade_id="open-1", status="open")

    metrics = build_summary_metrics([*closed, open_t], [])

    assert metrics["realized_pnl"] == pytest.approx(75.0)


def test_summary_metrics_counts_threshold_rejections(tmp_path: Path) -> None:
    """Phase 15.1: only the threshold-gate rejection pattern is counted.

    Cap-rejected proposals (Phase 12.1, reason starts ``"symbol "``)
    must not be counted, and accepted/pending records contribute zero.
    """
    history = ProposalHistory(data_dir=tmp_path)

    accepted = ProposalRecord(
        proposal=_make_proposal("p-accepted"),
        decision=ProposalDecision.ACCEPTED,
        decision_at=datetime(2026, 1, 1, 10, 0, 0),
    )
    threshold_rejected = ProposalRecord(
        proposal=_make_proposal("p-threshold"),
        decision=ProposalDecision.REJECTED,
        decision_at=datetime(2026, 1, 1, 11, 0, 0),
        rejection_reason="composite 0.4500 below threshold 1.0000",
    )
    cap_rejected = ProposalRecord(
        proposal=_make_proposal("p-cap"),
        decision=ProposalDecision.REJECTED,
        decision_at=datetime(2026, 1, 1, 12, 0, 0),
        rejection_reason="symbol BTC/USDT cap 1 reached (1 open)",
    )
    no_reason = ProposalRecord(
        proposal=_make_proposal("p-no-reason"),
        decision=ProposalDecision.REJECTED,
        decision_at=datetime(2026, 1, 1, 13, 0, 0),
        rejection_reason=None,
    )
    for record in (accepted, threshold_rejected, cap_rejected, no_reason):
        history.save(record)

    metrics = build_summary_metrics([], [], history)

    assert metrics["proposals_rejected_threshold_count"] == 1


def test_summary_metrics_handles_empty_proposal_history(tmp_path: Path) -> None:
    """Backward-compat: empty proposals dir → count 0, no exception."""
    history = ProposalHistory(data_dir=tmp_path / "never_created")

    metrics = build_summary_metrics([], [], history)

    assert metrics["proposals_rejected_threshold_count"] == 0
    # Existing fields still computed correctly.
    assert metrics["open_positions"] == 0
    assert metrics["closed_trades"] == 0


def test_summary_metrics_uses_latest_snapshot() -> None:
    snapshots = [
        make_snapshot(
            timestamp=datetime(2026, 1, 1),
            quote_balance="10000",
            unrealized_pnl="50",
        ),
        make_snapshot(
            timestamp=datetime(2026, 1, 5),
            quote_balance="11000",
            unrealized_pnl="200",
        ),
        make_snapshot(
            timestamp=datetime(2026, 1, 3),
            quote_balance="10500",
            unrealized_pnl="100",
        ),
    ]

    metrics = build_summary_metrics([], snapshots)

    # Latest snapshot is 2026-01-05 even though it's not last in the list.
    # Phase 21.2: AssetSnapshot.timestamp is UTC-aware via the validator,
    # so the latest_snapshot_at metric is also aware.
    assert metrics["latest_snapshot_at"] == datetime(2026, 1, 5, tzinfo=timezone.utc)
    assert metrics["latest_equity"] == pytest.approx(11200.0)  # 11000 + 200
    assert metrics["unrealized_pnl"] == pytest.approx(200.0)


def test_latest_snapshot_current_prices_uses_newest_snapshot() -> None:
    snapshots = [
        make_snapshot(
            timestamp=datetime(2026, 1, 1),
            current_prices={"BTC/USDT": Decimal("50000")},
        ),
        make_snapshot(
            timestamp=datetime(2026, 1, 2),
            current_prices={"BTC/USDT": Decimal("51000")},
        ),
    ]

    assert latest_snapshot_current_prices(snapshots) == {"BTC/USDT": Decimal("51000")}


# =============================================================================
# AppTest smoke
# =============================================================================


def test_trading_page_renders_empty_state(tmp_path: Path) -> None:
    """Page must not crash when no trades or snapshots exist."""
    from streamlit.testing.v1 import AppTest

    script = f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})
from pathlib import Path
from src.dashboard.pages.trading import render
from src.proposal.interaction import ProposalHistory
from src.strategy.performance import TradeHistoryTracker
from src.trading.portfolio import PortfolioTracker

tt = TradeHistoryTracker(data_dir=Path({str(tmp_path / "trades")!r}))
pt = PortfolioTracker(
    data_dir=Path({str(tmp_path / "portfolio")!r}),
    trade_tracker=tt,
)
ph = ProposalHistory(data_dir=Path({str(tmp_path / "proposals")!r}))

render(trade_tracker=tt, portfolio_tracker=pt, proposal_history=ph)
"""
    at = AppTest.from_string(script).run(timeout=10)

    assert not at.exception, [str(e) for e in at.exception]
    info_text = " ".join(i.value for i in at.info)
    assert "No open positions" in info_text
    assert "No trade history" in info_text
    assert "No equity history" in info_text
    # Phase 15.1: the threshold-rejection metric card must render.
    metric_labels = [m.label for m in at.metric]
    assert "Proposals rejected (threshold)" in metric_labels
    rej_metric = next(
        m for m in at.metric if m.label == "Proposals rejected (threshold)"
    )
    assert rej_metric.value == "0"


def test_trading_page_renders_summary_with_data(tmp_path: Path) -> None:
    """End-to-end: a paper-mode trade + snapshot makes the summary populate."""
    from streamlit.testing.v1 import AppTest

    # Pre-populate trade + snapshot via the real trackers, then render.
    script = f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from src.dashboard.pages.trading import render
from src.proposal.interaction import ProposalHistory
from src.strategy.performance import TradeHistoryTracker, TradeHistory
from src.trading.portfolio import PortfolioTracker, AssetSnapshot

tt = TradeHistoryTracker(data_dir=Path({str(tmp_path / "trades")!r}))
trade = TradeHistory(
    symbol="BTC/USDT",
    side="long",
    mode="paper",
    entry_price=Decimal("50000"),
    entry_quantity=Decimal("0.1"),
    entry_time=datetime(2026, 1, 1, 12, 0, 0),
    exit_price=Decimal("51000"),
    exit_quantity=Decimal("0.1"),
    exit_time=datetime(2026, 1, 1, 14, 0, 0),
    pnl=Decimal("100"),
    pnl_percent=2.0,
    status="closed",
    close_reason="take_profit",
)
tt.save_trade(trade)

pt = PortfolioTracker(
    data_dir=Path({str(tmp_path / "portfolio")!r}),
    trade_tracker=tt,
)
snap = AssetSnapshot(
    timestamp=datetime(2026, 1, 2, 0, 0, 0),
    mode="paper",
    quote_currency="USDT",
    balances={{"USDT": Decimal("10100")}},
    realized_pnl=Decimal("100"),
    unrealized_pnl=Decimal("0"),
)
# Use the public save path used elsewhere in the codebase.
pt._save_snapshots("paper", [snap])

ph = ProposalHistory(data_dir=Path({str(tmp_path / "proposals")!r}))
render(trade_tracker=tt, portfolio_tracker=pt, proposal_history=ph)
"""
    at = AppTest.from_string(script).run(timeout=15)

    assert not at.exception, [str(e) for e in at.exception]
    titles = [t.value for t in at.title]
    assert any("Trading" in t for t in titles), titles
    metric_blob = " ".join(
        f"{m.label} {m.value}" for m in at.metric  # type: ignore[attr-defined]
    )
    assert "Current Equity" in metric_blob, metric_blob
    assert "10100" in metric_blob, metric_blob


# =============================================================================
# Cash-only suppression rule (runtime-reconciliation §4)
# =============================================================================


def test_cash_only_suppressed_when_ledger_has_open_trades(tmp_path: Path) -> None:
    """The Trading page must not render "no open positions" when the
    reconciliation banner reports a non-zero open-trade count.

    This pins the exact Fly 2026-05-13 failure mode: 49 open ledger
    rows but the portfolio snapshot reports zero positions. The
    page-level guard is the explicit warning that fires whenever
    the banner's ``open_trade_count > 0`` *and* the open-positions
    DataFrame is empty. We exercise both halves via a focused
    AppTest harness — no real trades or snapshots are seeded so the
    DataFrame is genuinely empty.
    """
    from streamlit.testing.v1 import AppTest

    # Pre-seed an activity log with a RECONCILIATION_HEALTH_REPORT
    # event that reports a non-zero open-trade count.
    from src.runtime.activity_log import ActivityEventType, ActivityLog

    log = ActivityLog(path=tmp_path / "activity.jsonl")
    log.append(
        ActivityEventType.RECONCILIATION_HEALTH_REPORT,
        "snapshot",
        details={
            "report": {
                "default": {
                    "open_trade_count": 3,
                    "state_counts": {
                        "monitorable": 3,
                        "degraded": 0,
                        "unrecoverable": 0,
                        "legacy_no_perf_link": 0,
                    },
                    "locked_sum": "0",
                    "balance_snapshot_present": True,
                    "balance_locked": "0",
                    "locked_consistent": True,
                    "perf_links_resolved": 3,
                    "perf_links_missing": 0,
                    "classifications": [],
                }
            },
            "totals": {
                "open_trade_count": 3,
                "state_counts": {
                    "monitorable": 3,
                    "degraded": 0,
                    "unrecoverable": 0,
                    "legacy_no_perf_link": 0,
                },
                "locked_sum": "0",
                "perf_links_resolved": 3,
                "perf_links_missing": 0,
                "any_locked_inconsistent": False,
                "classifications": [],
            },
        },
    )

    script = f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})
from pathlib import Path
from src.dashboard.pages.trading import render
from src.proposal.interaction import ProposalHistory
from src.runtime.activity_log import ActivityLog
from src.strategy.performance import TradeHistoryTracker
from src.trading.portfolio import PortfolioTracker

tt = TradeHistoryTracker(data_dir=Path({str(tmp_path / "trades")!r}))
pt = PortfolioTracker(
    data_dir=Path({str(tmp_path / "portfolio")!r}),
    trade_tracker=tt,
)
ph = ProposalHistory(data_dir=Path({str(tmp_path / "proposals")!r}))
log = ActivityLog(path=Path({str(tmp_path / "activity.jsonl")!r}))

render(trade_tracker=tt, portfolio_tracker=pt, proposal_history=ph, activity_log=log)
"""
    at = AppTest.from_string(script).run(timeout=15)

    assert not at.exception, [str(e) for e in at.exception]
    warning_text = " ".join(w.value for w in at.warning)
    # The cash-only suppression rule replaces "No open positions" with
    # an explicit ledger-vs-snapshot mismatch warning carrying the
    # ledger open-trade count.
    assert "ledger has 3 open trade(s)" in warning_text, warning_text
    info_text = " ".join(i.value for i in at.info)
    assert "No open positions" not in info_text


def test_no_cash_only_suppression_when_ledger_is_empty(tmp_path: Path) -> None:
    """Reverse case: zero open trades on the ledger → "No open positions" is fine.

    Pins that the suppression rule is gated specifically on the
    banner's ``open_trade_count`` and doesn't accidentally fire for
    every render.
    """
    from streamlit.testing.v1 import AppTest

    # No activity log → no reconciliation event → banner reports 0
    # open trades. The default "No open positions" info message is
    # the expected render.
    script = f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})
from pathlib import Path
from src.dashboard.pages.trading import render
from src.proposal.interaction import ProposalHistory
from src.runtime.activity_log import ActivityLog
from src.strategy.performance import TradeHistoryTracker
from src.trading.portfolio import PortfolioTracker

tt = TradeHistoryTracker(data_dir=Path({str(tmp_path / "trades")!r}))
pt = PortfolioTracker(
    data_dir=Path({str(tmp_path / "portfolio")!r}),
    trade_tracker=tt,
)
ph = ProposalHistory(data_dir=Path({str(tmp_path / "proposals")!r}))
log = ActivityLog(path=Path({str(tmp_path / "activity.jsonl")!r}))

render(trade_tracker=tt, portfolio_tracker=pt, proposal_history=ph, activity_log=log)
"""
    at = AppTest.from_string(script).run(timeout=15)

    assert not at.exception, [str(e) for e in at.exception]
    info_text = " ".join(i.value for i in at.info)
    assert "No open positions" in info_text

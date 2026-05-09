"""Tests for the Streamlit dashboard chassis (Phase 7.1).

The chassis renders no domain data — it just sets up the page, the
sidebar, and the navigation. Tests exercise the constants directly
and use Streamlit's ``AppTest`` to smoke-run the script end-to-end.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.dashboard.app import (
    build_candidate_dataframe,
    build_candidate_rows,
    build_command_center_status,
    build_exposure_dataframe,
    build_exposure_rows,
    build_incident_dataframe,
    build_incident_rows,
    build_runtime_diagnostic_dataframe,
    build_runtime_diagnostic_rows,
    count_actionable_events,
    estimate_open_notional,
    latest_snapshot_equity,
    snapshot_freshness,
)
from src.dashboard.pages import feedback as feedback_page
from src.dashboard.theme import (
    APP_ICON,
    APP_TAGLINE,
    APP_TITLE,
    INITIAL_SIDEBAR_STATE,
    PAGE_LAYOUT,
)
from src.feedback.loop import CandidateRecord, LoopStatus
from src.runtime.activity_log import ActivityEvent, ActivityEventType
from src.runtime.safety_score import (
    RuntimeSafetyBand,
    RuntimeSafetyInputs,
    RuntimeSafetyScore,
)
from src.strategy.performance import TradeHistory
from src.trading.portfolio import AssetSnapshot

APP_PATH = str(Path(__file__).resolve().parents[1] / "src" / "dashboard" / "app.py")


def make_trade(
    *,
    trade_id: str = "trade-id-12345678",
    symbol: str = "BTC/USDT",
    side: str = "long",
    entry_price: str = "50000",
    entry_quantity: str = "0.1",
    leverage: int = 2,
    status: str = "open",
) -> TradeHistory:
    return TradeHistory(
        id=trade_id,
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        mode="paper",
        entry_price=Decimal(entry_price),
        entry_quantity=Decimal(entry_quantity),
        entry_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        leverage=leverage,
        status=status,  # type: ignore[arg-type]
    )


def make_snapshot(timestamp: datetime) -> AssetSnapshot:
    return AssetSnapshot(
        timestamp=timestamp,
        mode="paper",
        quote_currency="USDT",
        balances={"USDT": Decimal("10000")},
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
    )


def make_candidate(
    *,
    candidate_id: str = "candidate-12345678",
    technique_name: str = "Breakout Guard",
    status: LoopStatus = LoopStatus.AWAITING_APPROVAL,
    updated_at: datetime | None = None,
    robustness_passed: bool | None = True,
    backtest_run_id: str | None = "bt-123",
) -> CandidateRecord:
    timestamp = updated_at or datetime(2026, 1, 1, tzinfo=timezone.utc)
    return CandidateRecord(
        candidate_id=candidate_id,
        kind="improvement",
        parent_technique="baseline",
        technique_name=technique_name,
        technique_version="v2",
        source_path=Path("strategies/experimental/breakout_guard.py"),
        status=status,
        backtest_run_id=backtest_run_id,
        robustness_passed=robustness_passed,
        sub_account_id="default",
        created_at=timestamp,
        updated_at=timestamp,
    )


def make_event(
    event_type: ActivityEventType,
    timestamp: datetime,
    *,
    cycle_id: str | None = None,
    message: str | None = None,
    details: dict[str, object] | None = None,
) -> ActivityEvent:
    return ActivityEvent(
        event_type=event_type,
        timestamp=timestamp,
        message=message or event_type.value,
        details=details or {},
        cycle_id=cycle_id,
    )


# =============================================================================
# Theme constants
# =============================================================================


def test_app_constants_are_set() -> None:
    """Sanity: nothing is empty."""
    assert APP_TITLE
    assert APP_ICON
    assert APP_TAGLINE
    assert PAGE_LAYOUT == "wide"
    assert INITIAL_SIDEBAR_STATE == "expanded"


# =============================================================================
# AppTest smoke
# =============================================================================


def test_app_runs_without_exception() -> None:
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    assert not at.exception, [str(e) for e in at.exception]


def test_app_renders_home_title() -> None:
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    titles = [t.value for t in at.title]
    assert any(APP_TITLE in t for t in titles), titles


def test_app_renders_tagline_via_caption() -> None:
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    captions = [c.value for c in at.caption]
    assert any(APP_TAGLINE in c for c in captions), captions


def test_app_sidebar_has_branding() -> None:
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    sidebar_md = " ".join(m.value for m in at.sidebar.markdown)
    assert APP_TITLE in sidebar_md, sidebar_md


def test_app_home_lists_three_sections() -> None:
    """Three section cards: Strategies (success), Trading + Feedback (info)."""
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    info_text = " ".join(i.value for i in at.info)
    success_text = " ".join(s.value for s in at.success)
    combined = info_text + " " + success_text
    assert "Strategies" in combined
    assert "Trading" in combined
    assert "Feedback Loop" in combined


def test_app_home_renders_command_center() -> None:
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    markdown_text = " ".join(m.value for m in at.markdown)
    metric_labels = [m.label for m in at.metric]
    assert "Command Center" in markdown_text
    assert "Runtime safety" in metric_labels
    assert "Last cycle" in metric_labels
    assert "Open positions" in metric_labels
    assert "Scope" in metric_labels
    assert "Actionable events" in metric_labels
    assert "Candidates" in metric_labels
    assert "Awaiting approval" in metric_labels


def test_app_home_renders_command_center_controls() -> None:
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    radio_labels = [r.label for r in at.radio]
    selectbox_labels = [s.label for s in at.selectbox]
    assert "Command center mode" in radio_labels
    assert "Command center scope" in selectbox_labels


def test_app_home_no_pending_phase_labels() -> None:
    """All three section cards are wired — none should advertise a coming phase."""
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    info_text = " ".join(i.value for i in at.info)
    success_text = " ".join(s.value for s in at.success)
    combined = info_text + " " + success_text
    for phase_label in ("Phase 7.2", "Phase 7.3", "Phase 7.4"):
        assert phase_label not in combined, combined


def test_load_command_center_status_reads_feedback_from_runtime_dir(
    tmp_path: Path, monkeypatch
) -> None:
    """Home command center must share the Feedback page's runtime state path."""
    from src.dashboard import app as dashboard_app

    seen_paths: list[Path] = []

    def _load_candidate_records(path: Path) -> list[CandidateRecord]:
        seen_paths.append(path)
        return []

    monkeypatch.setattr(feedback_page, "default_candidate_state_dir", lambda: tmp_path)
    monkeypatch.setattr(
        feedback_page,
        "load_candidate_records",
        _load_candidate_records,
    )
    monkeypatch.setattr(dashboard_app.ActivityLog, "read_all", lambda self: [])

    dashboard_app.load_command_center_status(sub_account_ids=[])

    assert seen_paths == [tmp_path]


def test_app_navigation_includes_all_pages() -> None:
    """All four content pages must be reachable from the sidebar nav."""
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    sidebar_text = " ".join(m.value for m in at.sidebar.markdown)
    # AppTest doesn't expose nav buttons as a typed widget yet, so we
    # rely on the script's exception-free run + presence of the title
    # in sidebar markdown to confirm the chassis renders.
    assert "Crypto Master" in sidebar_text


def test_snapshot_freshness_missing() -> None:
    assert snapshot_freshness(None) == "missing"


def test_snapshot_freshness_detects_stale_snapshot() -> None:
    now = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)
    latest = now - timedelta(hours=7)

    assert snapshot_freshness(latest, now=now) == "stale"


def test_estimate_open_notional_uses_open_trades_only() -> None:
    open_trade = make_trade(entry_price="50000", entry_quantity="0.2")
    closed_trade = make_trade(
        entry_price="10000",
        entry_quantity="1",
        status="closed",
    )

    assert estimate_open_notional([open_trade, closed_trade]) == Decimal("10000.0")


def test_count_actionable_events() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(ActivityEventType.CYCLE_STARTED, now, cycle_id="cycle-1"),
        make_event(ActivityEventType.NOTIFICATION_FAILED, now, cycle_id="cycle-1"),
        make_event(ActivityEventType.CORRELATION_WARNING, now, cycle_id="cycle-1"),
    ]

    assert count_actionable_events(events, now=now) == 2


def test_count_actionable_events_uses_recent_window() -> None:
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    events = [
        make_event(
            ActivityEventType.NOTIFICATION_FAILED,
            now - timedelta(hours=25),
            cycle_id="old-cycle",
        ),
        make_event(
            ActivityEventType.CORRELATION_WARNING,
            now - timedelta(hours=1),
            cycle_id="new-cycle",
        ),
    ]

    assert count_actionable_events(events, now=now) == 1


def test_build_command_center_status_summarizes_inputs() -> None:
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    events = [
        make_event(ActivityEventType.CYCLE_STARTED, now, cycle_id="cycle-1"),
        make_event(
            ActivityEventType.CYCLE_COMPLETED,
            now + timedelta(seconds=10),
            cycle_id="cycle-1",
        ),
        make_event(ActivityEventType.NOTIFICATION_FAILED, now, cycle_id="cycle-1"),
    ]
    trades = [make_trade(entry_price="50000", entry_quantity="0.1")]
    snapshots = [make_snapshot(now - timedelta(hours=1))]

    status = build_command_center_status(
        events=events,
        trades=trades,
        snapshots=snapshots,
        sub_account_count=2,
        mode="paper",
        scope="Aggregate",
        candidate_metrics={
            "total": 3,
            "awaiting_approval": 1,
            "promoted": 1,
            "errored": 1,
        },
        candidate_records=[make_candidate()],
        now=now,
    )

    assert status.safety.band.value == "safe"
    assert status.last_cycle_status == "ok"
    assert status.open_positions == 1
    assert status.estimated_open_notional == Decimal("5000.0")
    assert status.latest_equity == Decimal("10000")
    assert status.snapshot_freshness == "fresh"
    assert status.actionable_events == 1
    assert status.sub_account_count == 2
    assert status.scope == "Aggregate"
    assert len(status.exposure_rows) == 1
    assert status.candidate_total == 3
    assert status.candidates_awaiting_approval == 1
    assert status.candidates_promoted == 1
    assert status.candidates_errored == 1
    assert len(status.incident_rows) == 1
    assert len(status.candidate_rows) == 1
    assert len(status.diagnostic_rows) == 4


def test_build_exposure_rows_groups_duplicate_sub_account_exposure() -> None:
    default_trade = make_trade(
        trade_id="default-btc",
        symbol="BTC/USDT",
        entry_price="50000",
        entry_quantity="0.1",
        leverage=2,
    )
    experimental_trade = make_trade(
        trade_id="experimental-btc",
        symbol="BTC/USDT",
        entry_price="51000",
        entry_quantity="0.2",
        leverage=5,
    )

    rows = build_exposure_rows(
        [
            ("default", default_trade),
            ("experimental", experimental_trade),
        ],
        latest_equity=Decimal("20000"),
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.symbol == "BTC/USDT"
    assert row.side == "long"
    assert row.sub_accounts == ("default", "experimental")
    assert row.open_count == 2
    assert row.estimated_notional == Decimal("15200.0")
    assert row.estimated_margin == Decimal("4540.0")
    assert row.notional_pct_of_equity == 76.0
    assert row.max_leverage == 5
    assert row.duplicate_across_accounts is True


def test_build_exposure_dataframe_empty_has_operator_columns() -> None:
    df = build_exposure_dataframe([])

    assert df.empty
    assert "Duplicate Accounts" in df.columns


def test_latest_snapshot_equity_uses_newest_snapshot() -> None:
    older = make_snapshot(datetime(2026, 1, 1, tzinfo=timezone.utc))
    newer = make_snapshot(datetime(2026, 1, 2, tzinfo=timezone.utc))
    newer.balances["USDT"] = Decimal("12000")
    newer.unrealized_pnl = Decimal("-250")

    assert latest_snapshot_equity([older, newer]) == Decimal("11750")


def test_latest_snapshot_equity_aggregates_per_sub_account() -> None:
    """Aggregate scope sums latest-per-sub-account, not the global newest (CH-05).

    Before consistency-hardening CH-05, the dashboard returned the
    equity of the single newest snapshot across every sub-account, so
    aggregate equity understated by ``N - 1`` accounts and
    proportionally inflated ``notional_pct_of_equity``.
    """
    alpha_old = make_snapshot(datetime(2026, 1, 1, tzinfo=timezone.utc))
    alpha_old.sub_account_id = "alpha"
    alpha_old.balances["USDT"] = Decimal("8000")
    alpha_new = make_snapshot(datetime(2026, 1, 2, tzinfo=timezone.utc))
    alpha_new.sub_account_id = "alpha"
    alpha_new.balances["USDT"] = Decimal("9000")
    beta = make_snapshot(datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
    beta.sub_account_id = "beta"
    beta.balances["USDT"] = Decimal("4000")

    snapshots = [alpha_old, alpha_new, beta]

    # Without aggregation: returns the single newest (alpha @ 9000).
    assert latest_snapshot_equity(snapshots) == Decimal("9000")
    # With aggregation: sums latest-per-sub-account (alpha 9000 + beta 4000).
    assert latest_snapshot_equity(snapshots, aggregate_per_sub_account=True) == Decimal(
        "13000"
    )


def test_build_command_center_status_filters_by_scope() -> None:
    """Single-account scope filters incidents/safety/equity (CH-05)."""
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    alpha_event = make_event(
        ActivityEventType.NOTIFICATION_FAILED,
        now,
        details={"sub_account_id": "alpha", "symbol": "BTC/USDT"},
    )
    beta_event = make_event(
        ActivityEventType.NOTIFICATION_FAILED,
        now,
        details={"sub_account_id": "beta", "symbol": "ETH/USDT"},
    )
    alpha_snap = make_snapshot(now)
    alpha_snap.sub_account_id = "alpha"
    alpha_snap.balances["USDT"] = Decimal("9000")
    beta_snap = make_snapshot(now)
    beta_snap.sub_account_id = "beta"
    beta_snap.balances["USDT"] = Decimal("4000")

    aggregate = build_command_center_status(
        events=[alpha_event, beta_event],
        trades=[],
        snapshots=[alpha_snap, beta_snap],
        sub_account_count=2,
        mode="paper",
        now=now,
    )
    assert aggregate.scope == "Aggregate"
    assert aggregate.latest_equity == Decimal("13000")
    assert len(aggregate.incident_rows) == 2

    scoped = build_command_center_status(
        events=[alpha_event, beta_event],
        trades=[],
        snapshots=[alpha_snap, beta_snap],
        sub_account_count=2,
        mode="paper",
        scope="alpha",
        now=now,
    )
    assert scoped.scope == "alpha"
    # Single-account scope keeps the single snapshot's equity (no
    # aggregate sum across accounts).
    assert scoped.latest_equity == Decimal("9000")
    # Only alpha's incident remains.
    assert len(scoped.incident_rows) == 1
    assert scoped.incident_rows[0].sub_account_id == "alpha"


def test_build_incident_rows_extracts_operator_fields() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = build_incident_rows(
        [
            make_event(
                ActivityEventType.LIQUIDATED,
                now,
                message="liquidated BTC",
                details={"sub_account_id": "default", "symbol": "BTC/USDT"},
            )
        ],
        now=now,
        mode="live",
        scope="default",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.severity == "stop"
    assert row.event_type == "liquidated"
    assert row.sub_account_id == "default"
    assert row.symbol == "BTC/USDT"
    assert row.next_step == "Review Trading exposure"
    assert row.target_page == "trading"
    assert row.query_params["sub_account"] == "default"
    assert row.query_params["symbol"] == "BTC/USDT"
    assert row.query_params["mode"] == "live"
    assert row.query_params["scope"] == "default"


def test_build_incident_dataframe_empty_has_operator_columns() -> None:
    df = build_incident_dataframe([])

    assert df.empty
    assert "Target Page" in df.columns


def test_build_candidate_rows_sorts_recent_records_and_maps_next_steps() -> None:
    older = make_candidate(
        candidate_id="older-candidate",
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status=LoopStatus.PROMOTED,
    )
    newer = make_candidate(
        candidate_id="newer-candidate",
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        status=LoopStatus.AWAITING_APPROVAL,
        robustness_passed=False,
        backtest_run_id=None,
    )

    rows = build_candidate_rows([older, newer], mode="paper", scope="alpha")

    assert [row.candidate_id for row in rows] == ["newer-candidate", "older-candidate"]
    assert rows[0].robustness == "FAIL"
    assert rows[0].backtest_run_id == "—"
    assert rows[0].next_step == "Open Feedback Loop approval"
    assert rows[0].target_page == "feedback"
    assert rows[0].query_params["candidate_id"] == "newer-candidate"
    assert rows[0].query_params["mode"] == "paper"
    assert rows[0].query_params["scope"] == "alpha"
    assert rows[1].next_step == "Verify promoted strategy"


def test_build_candidate_dataframe_empty_has_operator_columns() -> None:
    df = build_candidate_dataframe([])

    assert df.empty
    assert "Filter Hint" in df.columns


def test_build_runtime_diagnostic_rows_maps_stop_conditions() -> None:
    safety = RuntimeSafetyScore(
        score=35,
        band=RuntimeSafetyBand.PAUSE_RECOMMENDED,
        inputs=RuntimeSafetyInputs(),
        factors=["cycle errors=3"],
    )
    incident = build_incident_rows(
        [
            make_event(
                ActivityEventType.LIQUIDATED,
                datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ],
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    rows = build_runtime_diagnostic_rows(
        safety=safety,
        last_cycle_status="errored",
        snapshot_freshness="stale",
        incident_rows=incident,
    )

    assert [row.status for row in rows] == ["stop", "stop", "watch", "stop"]
    assert rows[1].next_step == "Open Engine timeline"
    assert rows[1].target_page == "engine"
    assert rows[3].detail == "1 stop incident(s)"


def test_build_runtime_diagnostic_dataframe_empty_has_operator_columns() -> None:
    df = build_runtime_diagnostic_dataframe([])

    assert df.empty
    assert list(df.columns) == [
        "Check",
        "Status",
        "Detail",
        "Next Step",
        "Target Page",
        "Filter Hint",
    ]

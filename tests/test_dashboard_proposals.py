"""Tests for the Proposal Funnel dashboard page (proposal-funnel-audit).

Covers the four pure helpers the page exposes (no Streamlit runtime
needed): conversion table, conversion summary, per-strategy heatmap,
per-gate volume, and the single-line command-center summary used by
the home view.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.dashboard.pages.proposals import (
    FUNNEL_COLUMN_ORDER,
    GATE_REJECTION_COLUMNS,
    build_command_center_summary,
    build_conversion_summary,
    build_funnel_table,
    build_per_gate_volume,
    build_per_strategy_heatmap,
    latest_sample_event_for_gate,
    window_for_label,
)
from src.proposal.funnel import FunnelCounts, FunnelWindow
from src.runtime.activity_log import ActivityEvent, ActivityEventType


def test_window_for_label_returns_unbounded_for_lifetime() -> None:
    window = window_for_label("lifetime")
    assert isinstance(window, FunnelWindow)
    assert window.start is None
    assert window.end is None


def test_window_for_label_24h_picks_one_day_window() -> None:
    now = datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc)
    window = window_for_label("24h", now=now)
    assert window.end == now
    assert window.start == now - timedelta(hours=24)


def test_window_for_label_7d_picks_seven_day_window() -> None:
    now = datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc)
    window = window_for_label("7d", now=now)
    assert window.start == now - timedelta(days=7)


def test_funnel_table_emits_columns_in_canonical_order() -> None:
    counts = FunnelCounts(
        generated=10,
        score_accepted=5,
        score_rejected=3,
        gate_rejected_total_cap=1,
        trade_opened=2,
        total=21,
    )
    df = build_funnel_table(counts)
    assert list(df.columns) == list(FUNNEL_COLUMN_ORDER)
    assert df.iloc[0]["generated"] == 10
    assert df.iloc[0]["trade_opened"] == 2


def test_conversion_summary_handles_zero_denominators() -> None:
    counts = FunnelCounts()
    summary = build_conversion_summary(counts)
    assert summary["generated_to_score_accepted"] == 0.0
    assert summary["generated_to_trade_opened"] == 0.0


def test_conversion_summary_matches_the_fly_snapshot_shape() -> None:
    # 2026-05-13 Fly snapshot: 2,624 generated -> 773 accepted -> 100 opened.
    # We model it with all 2,624 ending in their terminal state.
    counts = FunnelCounts(
        score_rejected=1_851,  # 2624 - 773
        gate_rejected_symbol_cap=600,
        gate_rejected_total_cap=73,
        proposal_opened=0,
        trade_opened=100,
        total=2_624,
    )
    summary = build_conversion_summary(counts)
    # 773 / 2624 ~= 0.295
    assert 0.28 < summary["generated_to_score_accepted"] < 0.31
    # 100 / 2624 ~= 0.038
    assert 0.03 < summary["generated_to_trade_opened"] < 0.05


def test_per_gate_volume_emits_row_per_gate_state() -> None:
    counts = FunnelCounts(
        gate_rejected_total_cap=4, gate_rejected_symbol_cap=7, total=11
    )
    df = build_per_gate_volume(counts)
    assert list(df["gate"]) == list(GATE_REJECTION_COLUMNS)
    by_gate = dict(zip(df["gate"], df["count"], strict=True))
    assert by_gate["gate_rejected_total_cap"] == 4
    assert by_gate["gate_rejected_symbol_cap"] == 7
    assert by_gate["gate_rejected_market_regime"] == 0


def test_per_strategy_heatmap_handles_empty_input() -> None:
    df = build_per_strategy_heatmap({})
    assert df.empty
    assert list(df.columns) == list(FUNNEL_COLUMN_ORDER)


def test_per_strategy_heatmap_emits_one_row_per_technique() -> None:
    by_strategy = {
        "rsi_v1": FunnelCounts(generated=10, trade_opened=2, total=12),
        "orb_v1": FunnelCounts(score_rejected=5, total=5),
    }
    df = build_per_strategy_heatmap(by_strategy)
    assert len(df) == 2
    assert set(df["Technique"]) == {"rsi_v1", "orb_v1"}


def test_command_center_summary_renders_single_line() -> None:
    counts = FunnelCounts(
        score_rejected=100,
        gate_rejected_total_cap=30,
        trade_opened=10,
        total=140,
    )
    summary = build_command_center_summary(counts)
    assert "generated" in summary
    assert "accepted" in summary
    assert "opened" in summary
    assert "conversion" in summary


def test_command_center_summary_handles_empty_input() -> None:
    summary = build_command_center_summary(FunnelCounts())
    assert "0 generated" in summary
    assert "0.0% conversion" in summary


def test_latest_sample_event_for_gate_matches_gate_reason() -> None:
    older = ActivityEvent(
        event_type=ActivityEventType.PROPOSAL_REJECTED,
        message="symbol cap",
        details={"gate_reason": "symbol_cap", "proposal_id": "old"},
        timestamp=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    newer = ActivityEvent(
        event_type=ActivityEventType.PROPOSAL_REJECTED,
        message="symbol cap",
        details={"gate_reason": "symbol_cap", "proposal_id": "new"},
        timestamp=datetime(2026, 5, 12, tzinfo=timezone.utc),
    )
    unrelated = ActivityEvent(
        event_type=ActivityEventType.PROPOSAL_REJECTED,
        message="trend filter",
        details={"gate_reason": "trend_filter_blocked", "proposal_id": "x"},
        timestamp=datetime(2026, 5, 13, tzinfo=timezone.utc),
    )
    match = latest_sample_event_for_gate(
        [older, newer, unrelated],
        "gate_rejected_symbol_cap",
    )
    assert match is newer


def test_latest_sample_event_for_gate_returns_none_when_no_match() -> None:
    events = [
        ActivityEvent(
            event_type=ActivityEventType.PROPOSAL_REJECTED,
            message="other",
            details={"gate_reason": "trend_filter_blocked"},
            timestamp=datetime(2026, 5, 13, tzinfo=timezone.utc),
        )
    ]
    match = latest_sample_event_for_gate(events, "gate_rejected_symbol_cap")
    assert match is None


def test_latest_sample_event_for_gate_falls_back_to_legacy_reason() -> None:
    """Legacy events (pre-cutover) only carry ``details.reason``.

    Market-regime emits ``market_regime_blocked_<regime>`` for the
    reason; the dashboard's per-gate sample matcher must still pick
    it up.
    """
    legacy = ActivityEvent(
        event_type=ActivityEventType.MARKET_REGIME_BLOCKED,
        message="regime",
        details={
            "reason": "market_regime_blocked_bear",
            "proposal_id": "legacy",
        },
        timestamp=datetime(2026, 5, 11, tzinfo=timezone.utc),
    )
    match = latest_sample_event_for_gate([legacy], "gate_rejected_market_regime")
    assert match is legacy

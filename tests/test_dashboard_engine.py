"""Tests for the Engine status page (Phase 8.2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.dashboard.pages.engine import (
    CycleSummary,
    aggregate_cycles,
    build_cross_account_risk_dataframe,
    build_cycle_duration_dataframe,
    build_cycles_dataframe,
    build_freeze_toggle_plan,
    build_market_regime_account_dataframe,
    build_market_regime_account_rows,
    build_market_regime_degraded_events_dataframe,
    build_market_regime_events_dataframe,
    build_market_regime_status_dataframe,
    build_market_regime_status_rows,
    build_operator_freeze_state,
    build_portfolio_cap_utilization,
    build_risk_gate_events_dataframe,
    build_runtime_safety_score,
    build_sub_account_metrics_dataframe,
    build_summary_metrics,
    build_symbol_side_exposure_dataframe,
    build_timeline_dataframe,
    kill_switch_state_for_account,
)
from src.runtime.activity_log import ActivityEvent, ActivityEventType, ActivityLog
from src.utils.time import now_utc

# =============================================================================
# Helpers
# =============================================================================


def make_event(
    *,
    event_type: ActivityEventType,
    timestamp: datetime,
    cycle_id: str | None = None,
    message: str = "",
    details: dict | None = None,
) -> ActivityEvent:
    # Phase 21.2: ActivityEvent.timestamp is UTC-aware via the
    # ``ensure_utc`` validator. Coerce naive test inputs so the
    # equality assertions below compare aware-vs-aware.
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return ActivityEvent(
        event_type=event_type,
        timestamp=timestamp,
        message=message,
        details=details or {},
        cycle_id=cycle_id,
    )


def make_cycle_events(
    cycle_id: str,
    *,
    started_at: datetime,
    duration_seconds: float = 12.0,
    proposals_generated: int = 0,
    proposals_accepted: int = 0,
    proposals_rejected: int = 0,
    positions_opened: int = 0,
    positions_closed: int = 0,
    errored: bool = False,
    completed: bool = True,
) -> list[ActivityEvent]:
    """Synthesize a realistic cycle's worth of events."""
    events: list[ActivityEvent] = [
        make_event(
            event_type=ActivityEventType.CYCLE_STARTED,
            timestamp=started_at,
            cycle_id=cycle_id,
            message="cycle begin",
        )
    ]
    cursor = started_at
    for _i in range(proposals_generated):
        cursor += timedelta(seconds=1)
        events.append(
            make_event(
                event_type=ActivityEventType.PROPOSAL_GENERATED,
                timestamp=cursor,
                cycle_id=cycle_id,
                message=f"prop-{_i}",
            )
        )
    for _i in range(proposals_accepted):
        cursor += timedelta(seconds=1)
        events.append(
            make_event(
                event_type=ActivityEventType.PROPOSAL_ACCEPTED,
                timestamp=cursor,
                cycle_id=cycle_id,
                message=f"acc-{_i}",
            )
        )
    for _i in range(proposals_rejected):
        cursor += timedelta(seconds=1)
        events.append(
            make_event(
                event_type=ActivityEventType.PROPOSAL_REJECTED,
                timestamp=cursor,
                cycle_id=cycle_id,
            )
        )
    for _i in range(positions_opened):
        cursor += timedelta(seconds=1)
        events.append(
            make_event(
                event_type=ActivityEventType.POSITION_OPENED,
                timestamp=cursor,
                cycle_id=cycle_id,
            )
        )
    for _i in range(positions_closed):
        cursor += timedelta(seconds=1)
        events.append(
            make_event(
                event_type=ActivityEventType.POSITION_CLOSED,
                timestamp=cursor,
                cycle_id=cycle_id,
            )
        )
    if completed:
        events.append(
            make_event(
                event_type=(
                    ActivityEventType.CYCLE_ERRORED
                    if errored
                    else ActivityEventType.CYCLE_COMPLETED
                ),
                timestamp=started_at + timedelta(seconds=duration_seconds),
                cycle_id=cycle_id,
                message="boom" if errored else "ok",
            )
        )
    return events


# =============================================================================
# aggregate_cycles
# =============================================================================


def test_aggregate_cycles_empty() -> None:
    assert aggregate_cycles([]) == []


def test_aggregate_cycles_skips_events_without_cycle_id() -> None:
    """STARTUP / SHUTDOWN have no cycle_id and must not become cycles."""
    events = [
        make_event(
            event_type=ActivityEventType.STARTUP,
            timestamp=datetime(2026, 4, 27, 12, 0),
            cycle_id=None,
        ),
        make_event(
            event_type=ActivityEventType.SHUTDOWN,
            timestamp=datetime(2026, 4, 27, 12, 30),
            cycle_id=None,
        ),
    ]

    assert aggregate_cycles(events) == []


def test_aggregate_cycles_one_complete_cycle() -> None:
    started = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
    events = make_cycle_events(
        "cycle-a",
        started_at=started,
        duration_seconds=10.0,
        proposals_generated=3,
        proposals_accepted=1,
        proposals_rejected=2,
        positions_opened=1,
        positions_closed=0,
    )

    cycles = aggregate_cycles(events)

    assert len(cycles) == 1
    c = cycles[0]
    assert c.cycle_id == "cycle-a"
    assert c.started_at == started
    assert c.completed_at == started + timedelta(seconds=10)
    assert c.duration_seconds == pytest.approx(10.0)
    assert c.proposals_generated == 3
    assert c.proposals_accepted == 1
    assert c.proposals_rejected == 2
    assert c.positions_opened == 1
    assert c.positions_closed == 0
    assert c.errored is False
    assert c.error_message is None


def test_aggregate_cycles_running_cycle_has_no_duration() -> None:
    """A cycle without a CYCLE_COMPLETED event is in flight."""
    started = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
    events = make_cycle_events(
        "cycle-running",
        started_at=started,
        completed=False,
        proposals_generated=1,
    )

    cycles = aggregate_cycles(events)

    assert len(cycles) == 1
    assert cycles[0].started_at == started
    assert cycles[0].completed_at is None
    assert cycles[0].duration_seconds is None
    assert cycles[0].errored is False


def test_aggregate_cycles_errored_cycle_marked() -> None:
    started = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
    events = make_cycle_events(
        "cycle-bad",
        started_at=started,
        duration_seconds=2.0,
        errored=True,
    )

    cycles = aggregate_cycles(events)

    assert len(cycles) == 1
    assert cycles[0].errored is True
    assert cycles[0].error_message == "boom"
    assert cycles[0].duration_seconds == pytest.approx(2.0)


def test_aggregate_cycles_orders_newest_first() -> None:
    early = make_cycle_events("cycle-early", started_at=datetime(2026, 4, 27, 12, 0, 0))
    late = make_cycle_events("cycle-late", started_at=datetime(2026, 4, 27, 13, 0, 0))

    cycles = aggregate_cycles([*early, *late])

    assert [c.cycle_id for c in cycles] == ["cycle-late", "cycle-early"]


def test_aggregate_cycles_handles_unsorted_events() -> None:
    """Aggregator must not assume events are pre-sorted."""
    started = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
    events = make_cycle_events(
        "c-shuffled",
        started_at=started,
        duration_seconds=5.0,
        proposals_generated=2,
    )
    # Reverse to confirm sorting happens internally.
    events.reverse()

    cycles = aggregate_cycles(events)

    assert cycles[0].started_at == started
    assert cycles[0].duration_seconds == pytest.approx(5.0)


# =============================================================================
# build_summary_metrics
# =============================================================================


def test_summary_metrics_empty() -> None:
    metrics = build_summary_metrics([], [])

    assert metrics["total_cycles"] == 0
    assert metrics["last_cycle_started_at"] is None
    assert metrics["last_cycle_status"] is None
    assert metrics["avg_duration_seconds"] is None
    assert metrics["errored_cycles"] == 0
    assert metrics["positions_opened_total"] == 0
    assert metrics["positions_closed_total"] == 0


def test_summary_metrics_aggregates_across_cycles() -> None:
    cycles = [
        # newest first
        CycleSummary(
            cycle_id="c3",
            started_at=datetime(2026, 4, 27, 13, 0),
            completed_at=datetime(2026, 4, 27, 13, 0, 10),
            duration_seconds=10.0,
            proposals_generated=2,
            proposals_accepted=1,
            proposals_rejected=1,
            positions_opened=1,
            positions_closed=1,
            errored=False,
            error_message=None,
        ),
        CycleSummary(
            cycle_id="c2",
            started_at=datetime(2026, 4, 27, 12, 30),
            completed_at=datetime(2026, 4, 27, 12, 30, 20),
            duration_seconds=20.0,
            proposals_generated=0,
            proposals_accepted=0,
            proposals_rejected=0,
            positions_opened=0,
            positions_closed=2,
            errored=False,
            error_message=None,
        ),
        CycleSummary(
            cycle_id="c1",
            started_at=datetime(2026, 4, 27, 12, 0),
            completed_at=datetime(2026, 4, 27, 12, 0, 30),
            duration_seconds=30.0,
            proposals_generated=1,
            proposals_accepted=0,
            proposals_rejected=1,
            positions_opened=0,
            positions_closed=0,
            errored=True,
            error_message="boom",
        ),
    ]

    metrics = build_summary_metrics([], cycles)

    assert metrics["total_cycles"] == 3
    assert metrics["last_cycle_started_at"] == datetime(2026, 4, 27, 13, 0)
    assert metrics["last_cycle_status"] == "ok"
    assert metrics["avg_duration_seconds"] == pytest.approx(20.0)
    assert metrics["errored_cycles"] == 1
    assert metrics["positions_opened_total"] == 1
    assert metrics["positions_closed_total"] == 3


def test_summary_metrics_running_last_cycle() -> None:
    cycles = [
        CycleSummary(
            cycle_id="c-running",
            started_at=datetime(2026, 4, 27, 13, 0),
            completed_at=None,
            duration_seconds=None,
            proposals_generated=0,
            proposals_accepted=0,
            proposals_rejected=0,
            positions_opened=0,
            positions_closed=0,
            errored=False,
            error_message=None,
        ),
    ]

    metrics = build_summary_metrics([], cycles)

    assert metrics["last_cycle_status"] == "running"
    # No completed cycles → no avg.
    assert metrics["avg_duration_seconds"] is None


def test_summary_metrics_errored_last_cycle() -> None:
    cycles = [
        CycleSummary(
            cycle_id="c-bad",
            started_at=datetime(2026, 4, 27, 13, 0),
            completed_at=datetime(2026, 4, 27, 13, 0, 5),
            duration_seconds=5.0,
            proposals_generated=0,
            proposals_accepted=0,
            proposals_rejected=0,
            positions_opened=0,
            positions_closed=0,
            errored=True,
            error_message="kaput",
        ),
    ]

    metrics = build_summary_metrics([], cycles)

    assert metrics["last_cycle_status"] == "errored"


def test_sub_account_metrics_dataframe_has_aggregate_row() -> None:
    events = [
        make_event(
            event_type=ActivityEventType.PROPOSAL_GENERATED,
            timestamp=datetime(2026, 4, 27, 12, 0),
            details={"sub_account_id": "default"},
        ),
        make_event(
            event_type=ActivityEventType.PROPOSAL_ACCEPTED,
            timestamp=datetime(2026, 4, 27, 12, 1),
            details={"sub_account_id": "default"},
        ),
        make_event(
            event_type=ActivityEventType.POSITION_OPENED,
            timestamp=datetime(2026, 4, 27, 12, 2),
            details={"sub_account_id": "experimental"},
        ),
    ]

    df = build_sub_account_metrics_dataframe(events)

    assert list(df["Sub-account"]) == ["Aggregate", "default", "experimental"]
    aggregate = df.iloc[0]
    assert aggregate["Generated"] == 1
    assert aggregate["Accepted"] == 1
    assert aggregate["Opened"] == 1


def test_build_runtime_safety_score_from_activity_events() -> None:
    now = now_utc()
    events = [
        make_event(
            event_type=ActivityEventType.CYCLE_ERRORED,
            timestamp=now - timedelta(minutes=3),
        ),
        make_event(
            event_type=ActivityEventType.NOTIFICATION_FAILED,
            timestamp=now - timedelta(minutes=2),
        ),
        make_event(
            event_type=ActivityEventType.PROPOSAL_REJECTED,
            timestamp=now - timedelta(minutes=1),
            details={"reason": "stale_quote_past_sl"},
        ),
    ]

    safety = build_runtime_safety_score(events)

    assert safety.score == 65
    assert safety.band.value == "degraded"
    assert safety.inputs.recent_cycle_errors == 1
    assert safety.inputs.recent_notification_failures == 1
    assert safety.inputs.stale_quote_warnings == 1


def test_build_runtime_safety_score_ignores_old_activity_events() -> None:
    now = now_utc()
    events = [
        make_event(
            event_type=ActivityEventType.LIQUIDATED,
            timestamp=now - timedelta(days=2),
        ),
        make_event(
            event_type=ActivityEventType.CORRELATION_WARNING,
            timestamp=now - timedelta(minutes=1),
        ),
    ]

    safety = build_runtime_safety_score(events)

    assert safety.inputs.liquidation_events == 0
    assert safety.inputs.correlation_warnings == 1


# =============================================================================
# DataFrame helpers
# =============================================================================


def test_cycles_dataframe_empty_keeps_columns() -> None:
    df = build_cycles_dataframe([])

    assert df.empty
    assert "Cycle" in df.columns
    assert "Status" in df.columns


def test_cycles_dataframe_marks_status_per_row() -> None:
    cycles = aggregate_cycles(
        [
            *make_cycle_events(
                "c-ok",
                started_at=datetime(2026, 4, 27, 12, 0),
                duration_seconds=2.0,
            ),
            *make_cycle_events(
                "c-running",
                started_at=datetime(2026, 4, 27, 12, 5),
                completed=False,
            ),
            *make_cycle_events(
                "c-bad",
                started_at=datetime(2026, 4, 27, 12, 10),
                duration_seconds=1.0,
                errored=True,
            ),
        ]
    )

    df = build_cycles_dataframe(cycles)

    by_id = {row["Cycle"]: row["Status"] for _, row in df.iterrows()}
    assert by_id["c-ok"[:8]] == "ok"
    assert by_id["c-runnin"] == "running"
    assert by_id["c-bad"[:8]] == "errored"


def test_cycle_duration_dataframe_skips_running_cycles() -> None:
    cycles = aggregate_cycles(
        [
            *make_cycle_events(
                "c-ok",
                started_at=datetime(2026, 4, 27, 12, 0),
                duration_seconds=4.0,
            ),
            *make_cycle_events(
                "c-running",
                started_at=datetime(2026, 4, 27, 12, 5),
                completed=False,
            ),
        ]
    )

    df = build_cycle_duration_dataframe(cycles)

    assert len(df) == 1
    assert df.iloc[0]["cycle_id"] == "c-ok"[:8]


def test_cycle_duration_dataframe_chronological() -> None:
    cycles = aggregate_cycles(
        [
            *make_cycle_events(
                "c-late",
                started_at=datetime(2026, 4, 27, 13, 0),
                duration_seconds=2.0,
            ),
            *make_cycle_events(
                "c-early",
                started_at=datetime(2026, 4, 27, 12, 0),
                duration_seconds=3.0,
            ),
        ]
    )

    df = build_cycle_duration_dataframe(cycles)

    # Chart reads left-to-right as time progresses.
    assert list(df["cycle_id"]) == ["c-early"[:8], "c-late"[:8]]


def test_cycle_duration_dataframe_empty() -> None:
    df = build_cycle_duration_dataframe([])

    assert df.empty
    assert list(df.columns) == ["cycle_id", "duration_seconds"]


def test_timeline_dataframe_orders_newest_first() -> None:
    events = [
        make_event(
            event_type=ActivityEventType.STARTUP,
            timestamp=datetime(2026, 4, 27, 12, 0),
            message="up",
        ),
        make_event(
            event_type=ActivityEventType.CYCLE_STARTED,
            timestamp=datetime(2026, 4, 27, 12, 5),
            cycle_id="c1",
            message="cycle 1 begin",
        ),
        make_event(
            event_type=ActivityEventType.SHUTDOWN,
            timestamp=datetime(2026, 4, 27, 12, 30),
            message="down",
        ),
    ]

    df = build_timeline_dataframe(events)

    assert list(df["Event"]) == [
        ActivityEventType.SHUTDOWN.value,
        ActivityEventType.CYCLE_STARTED.value,
        ActivityEventType.STARTUP.value,
    ]


def test_timeline_dataframe_truncates_long_details() -> None:
    big_payload = {"k": "x" * 1000}
    events = [
        make_event(
            event_type=ActivityEventType.PROPOSAL_GENERATED,
            timestamp=datetime(2026, 4, 27, 12, 0),
            cycle_id="c1",
            details=big_payload,
        ),
    ]

    df = build_timeline_dataframe(events)

    details_str = df.iloc[0]["Details"]
    # Truncated and ellipsised.
    assert details_str.endswith("…")
    assert len(details_str) <= 201


def test_timeline_dataframe_empty_keeps_columns() -> None:
    df = build_timeline_dataframe([])

    assert df.empty
    assert list(df.columns) == ["Timestamp", "Event", "Message", "Cycle", "Details"]


# =============================================================================
# AppTest smoke
# =============================================================================


def _make_regime_event(
    *,
    sub_account_id: str,
    symbol: str,
    timeframe: str,
    regime: str,
    timestamp: datetime,
    baseline: str = "100.0",
    close: str = "97.0",
    reason: str | None = None,
) -> ActivityEvent:
    details: dict[str, object] = {
        "sub_account_id": sub_account_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "regime": regime,
        "baseline": baseline,
        "close": close,
        "policy_decision": "block",
        "reason": reason or f"market_regime_blocked_{regime}",
    }
    return make_event(
        event_type=ActivityEventType.MARKET_REGIME_BLOCKED,
        timestamp=timestamp,
        message=f"regime {regime} blocked",
        details=details,
    )


def test_market_regime_status_rows_keep_latest_per_symbol_timeframe() -> None:
    """Two reads for the same (symbol, timeframe) keep only the newest;
    different (symbol, timeframe) pairs each surface their own row.
    Sort order is newest-first so operators see fresh classifications
    at the top of the status table."""
    base = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    events = [
        _make_regime_event(
            sub_account_id="acct_a",
            symbol="BTC/USDT",
            timeframe="4h",
            regime="bear",
            timestamp=base,
            close="97.0",
        ),
        _make_regime_event(
            sub_account_id="acct_a",
            symbol="BTC/USDT",
            timeframe="4h",
            regime="sideways",
            timestamp=base + timedelta(minutes=30),
            close="100.5",
        ),
        _make_regime_event(
            sub_account_id="acct_b",
            symbol="ETH/USDT",
            timeframe="1d",
            regime="bull",
            timestamp=base + timedelta(minutes=10),
            close="3500.0",
        ),
    ]

    rows = build_market_regime_status_rows(events)
    assert len(rows) == 2
    # Newest first.
    assert rows[0].reference_symbol == "BTC/USDT"
    assert rows[0].regime == "sideways"
    assert rows[1].reference_symbol == "ETH/USDT"
    assert rows[1].regime == "bull"


def test_market_regime_status_dataframe_empty_keeps_columns() -> None:
    df = build_market_regime_status_dataframe([])
    assert list(df.columns) == [
        "Reference Symbol",
        "Timeframe",
        "Regime",
        "Baseline (SMA)",
        "Close",
        "Last Observed",
    ]


def test_market_regime_status_dataframe_renders_rows() -> None:
    base = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    rows = build_market_regime_status_rows(
        [
            _make_regime_event(
                sub_account_id="acct_a",
                symbol="BTC/USDT",
                timeframe="4h",
                regime="bear",
                timestamp=base,
                baseline="100.015",
                close="97.0",
            )
        ]
    )
    df = build_market_regime_status_dataframe(rows)
    assert len(df) == 1
    record = df.iloc[0]
    assert record["Reference Symbol"] == "BTC/USDT"
    assert record["Timeframe"] == "4h"
    assert record["Regime"] == "bear"
    assert record["Baseline (SMA)"] == "100.015"
    assert record["Close"] == "97.0"


def test_market_regime_account_rows_one_per_sub_account_newest_first() -> None:
    base = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    events = [
        _make_regime_event(
            sub_account_id="acct_a",
            symbol="BTC/USDT",
            timeframe="4h",
            regime="bear",
            timestamp=base,
        ),
        _make_regime_event(
            sub_account_id="acct_a",
            symbol="BTC/USDT",
            timeframe="4h",
            regime="unknown",
            timestamp=base + timedelta(minutes=5),
        ),
        _make_regime_event(
            sub_account_id="acct_b",
            symbol="ETH/USDT",
            timeframe="1d",
            regime="sideways",
            timestamp=base + timedelta(minutes=2),
        ),
    ]

    rows = build_market_regime_account_rows(events)
    assert [row.sub_account_id for row in rows] == ["acct_a", "acct_b"]
    assert rows[0].last_regime == "unknown"
    assert rows[0].last_decision == "block"


def test_market_regime_events_dataframe_orders_newest_first_and_caps() -> None:
    base = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    events = [
        _make_regime_event(
            sub_account_id=f"acct_{i}",
            symbol="BTC/USDT",
            timeframe="4h",
            regime="bear",
            timestamp=base + timedelta(minutes=i),
        )
        for i in range(30)
    ]
    df = build_market_regime_events_dataframe(events, limit=10)
    assert len(df) == 10
    # Newest-first by timestamp.
    timestamps = list(df["Timestamp"])
    assert timestamps == sorted(timestamps, reverse=True)


def test_market_regime_helpers_ignore_unrelated_events() -> None:
    """Other ActivityEventType values are not market-regime reads and
    must not contaminate the regime tables."""
    base = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    unrelated = make_event(
        event_type=ActivityEventType.PROPOSAL_REJECTED,
        timestamp=base,
        details={
            "symbol": "BTC/USDT",
            "timeframe": "4h",
            "regime": "bear",
            "sub_account_id": "acct_a",
        },
    )
    assert build_market_regime_status_rows([unrelated]) == []
    assert build_market_regime_account_rows([unrelated]) == []
    df = build_market_regime_events_dataframe([unrelated])
    assert df.empty
    degraded_df = build_market_regime_degraded_events_dataframe([unrelated])
    assert degraded_df.empty


def _make_regime_degraded_event(
    *,
    sub_account_id: str,
    symbol: str,
    timeframe: str,
    error_type: str,
    timestamp: datetime,
) -> ActivityEvent:
    return make_event(
        event_type=ActivityEventType.MARKET_REGIME_DEGRADED,
        timestamp=timestamp,
        message=f"regime degraded ({error_type})",
        details={
            "sub_account_id": sub_account_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "error_type": error_type,
            "policy_decision": "pass_through_degraded",
        },
    )


def test_market_regime_degraded_events_dataframe_orders_newest_first_and_caps() -> None:
    """Degraded events surface newest-first and respect ``limit``.

    Pins the dashboard contract for the fail-open surface introduced
    by the quant-trader audit follow-up: operators must see recent
    silent-disable incidents at the top of the table.
    """
    base = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    events = [
        _make_regime_degraded_event(
            sub_account_id=f"acct_{i}",
            symbol="BTC/USDT",
            timeframe="4h",
            error_type="RuntimeError",
            timestamp=base + timedelta(minutes=i),
        )
        for i in range(15)
    ]
    df = build_market_regime_degraded_events_dataframe(events, limit=5)
    assert len(df) == 5
    timestamps = list(df["Timestamp"])
    assert timestamps == sorted(timestamps, reverse=True)
    # Pinned columns: dashboard contract for the fail-open surface.
    assert list(df.columns) == [
        "Timestamp",
        "Sub-account",
        "Reference Symbol",
        "Timeframe",
        "Error Type",
        "Decision",
    ]
    # Decision column carries the policy_decision string from the
    # MARKET_REGIME_DEGRADED payload contract.
    assert all(decision == "pass_through_degraded" for decision in df["Decision"])


def test_market_regime_degraded_events_dataframe_empty_keeps_columns() -> None:
    df = build_market_regime_degraded_events_dataframe([])
    assert list(df.columns) == [
        "Timestamp",
        "Sub-account",
        "Reference Symbol",
        "Timeframe",
        "Error Type",
        "Decision",
    ]
    assert df.empty


def test_market_regime_account_dataframe_empty_keeps_columns() -> None:
    df = build_market_regime_account_dataframe([])
    assert list(df.columns) == [
        "Sub-account",
        "Last Regime",
        "Last Decision",
        "Last Observed",
    ]


def test_engine_page_renders_empty_state(tmp_path: Path) -> None:
    """Page must not crash when the activity log is empty / missing."""
    from streamlit.testing.v1 import AppTest

    log_path = tmp_path / "activity.jsonl"

    script = f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})
from pathlib import Path
from src.dashboard.pages.engine import render
from src.runtime.activity_log import ActivityLog

render(activity_log=ActivityLog(path=Path({str(log_path)!r})))
"""
    at = AppTest.from_string(script).run(timeout=10)

    assert not at.exception, [str(e) for e in at.exception]
    info_text = " ".join(i.value for i in at.info)
    assert "Engine activity log is empty" in info_text


def test_engine_page_renders_populated(tmp_path: Path) -> None:
    """End-to-end: a real cycle in the log surfaces in the summary cards."""
    from streamlit.testing.v1 import AppTest

    log_path = tmp_path / "activity.jsonl"
    log = ActivityLog(path=log_path)
    started = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
    for ev in make_cycle_events(
        "c-smoke",
        started_at=started,
        duration_seconds=3.0,
        proposals_generated=1,
        proposals_accepted=1,
        positions_opened=1,
    ):
        log.append(
            (
                ev.event_type
                if isinstance(ev.event_type, ActivityEventType)
                else ActivityEventType(ev.event_type)
            ),
            ev.message,
            details=ev.details,
            cycle_id=ev.cycle_id,
        )

    script = f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})
from pathlib import Path
from src.dashboard.pages.engine import render
from src.runtime.activity_log import ActivityLog

render(activity_log=ActivityLog(path=Path({str(log_path)!r})))
"""
    at = AppTest.from_string(script).run(timeout=15)

    assert not at.exception, [str(e) for e in at.exception]
    titles = [t.value for t in at.title]
    assert any("Engine" in t for t in titles), titles


# =============================================================================
# Reconciliation banner + drill-through (runtime-reconciliation §4)
# =============================================================================


from src.dashboard.pages.engine import (  # noqa: E402
    build_reconciliation_drilldown_dataframe,
    build_reconciliation_status_banner,
)


def _reconciliation_event(
    *,
    timestamp: datetime,
    open_count: int = 0,
    monitorable: int = 0,
    degraded: int = 0,
    unrecoverable: int = 0,
    legacy: int = 0,
    any_inconsistent: bool = False,
    classifications: list[dict] | None = None,
) -> ActivityEvent:
    """Build a ``RECONCILIATION_HEALTH_REPORT`` activity event for tests."""
    return make_event(
        event_type=ActivityEventType.RECONCILIATION_HEALTH_REPORT,
        timestamp=timestamp,
        details={
            "report": {
                "default": {
                    "open_trade_count": open_count,
                    "state_counts": {
                        "monitorable": monitorable,
                        "degraded": degraded,
                        "unrecoverable": unrecoverable,
                        "legacy_no_perf_link": legacy,
                    },
                    "locked_sum": "0",
                    "balance_snapshot_present": True,
                    "balance_locked": "0",
                    "locked_consistent": not any_inconsistent,
                    "perf_links_resolved": 0,
                    "perf_links_missing": 0,
                    "classifications": classifications or [],
                }
            },
            "totals": {
                "open_trade_count": open_count,
                "state_counts": {
                    "monitorable": monitorable,
                    "degraded": degraded,
                    "unrecoverable": unrecoverable,
                    "legacy_no_perf_link": legacy,
                },
                "locked_sum": "0",
                "perf_links_resolved": 0,
                "perf_links_missing": 0,
                "any_locked_inconsistent": any_inconsistent,
                "classifications": classifications or [],
            },
        },
    )


def test_reconciliation_banner_green_when_no_event() -> None:
    """No event yet → Green with the 'engine not started' message."""
    banner = build_reconciliation_status_banner([])
    assert banner.color == "green"
    assert banner.open_trade_count == 0
    assert banner.report_timestamp is None


def test_reconciliation_banner_green_when_all_monitorable() -> None:
    """All open trades monitorable + locked-consistent → Green."""
    events = [
        _reconciliation_event(
            timestamp=now_utc(),
            open_count=3,
            monitorable=3,
        )
    ]
    banner = build_reconciliation_status_banner(events)
    assert banner.color == "green"
    assert banner.open_trade_count == 3
    assert banner.cta is None


def test_reconciliation_banner_yellow_on_degraded() -> None:
    """Any ``degraded`` row → Yellow with the backfill CTA."""
    events = [
        _reconciliation_event(
            timestamp=now_utc(),
            open_count=2,
            monitorable=1,
            degraded=1,
        )
    ]
    banner = build_reconciliation_status_banner(events)
    assert banner.color == "yellow"
    assert banner.cta is not None
    assert "backfill_paper_sl_tp" in banner.cta


def test_reconciliation_banner_yellow_on_locked_inconsistent() -> None:
    """``any_locked_inconsistent`` alone is enough to trip Yellow."""
    events = [
        _reconciliation_event(
            timestamp=now_utc(),
            open_count=1,
            monitorable=1,
            any_inconsistent=True,
        )
    ]
    banner = build_reconciliation_status_banner(events)
    assert banner.color == "yellow"


def test_reconciliation_banner_red_on_unrecoverable() -> None:
    """Any ``unrecoverable`` row → Red with the close-tool CTA."""
    events = [
        _reconciliation_event(
            timestamp=now_utc(),
            open_count=2,
            monitorable=1,
            unrecoverable=1,
        )
    ]
    banner = build_reconciliation_status_banner(events)
    assert banner.color == "red"
    assert banner.cta is not None
    assert "close_unrecoverable_paper_trades" in banner.cta


def test_reconciliation_banner_uses_most_recent_event() -> None:
    """Multiple reports → the newest one wins."""
    older = _reconciliation_event(
        timestamp=now_utc() - timedelta(hours=1),
        open_count=5,
        unrecoverable=5,
    )
    newer = _reconciliation_event(
        timestamp=now_utc(),
        open_count=5,
        monitorable=5,
    )
    banner = build_reconciliation_status_banner([older, newer])
    assert banner.color == "green"


def test_reconciliation_drilldown_dataframe_shape() -> None:
    """Per-trade drill-through carries one row per classification."""
    events = [
        _reconciliation_event(
            timestamp=now_utc(),
            open_count=2,
            monitorable=1,
            unrecoverable=1,
            classifications=[
                {
                    "trade_id": "t1",
                    "sub_account_id": "alpha",
                    "symbol": "BTC/USDT",
                    "side": "long",
                    "state": "monitorable",
                    "missing_fields": [],
                },
                {
                    "trade_id": "t2",
                    "sub_account_id": "beta",
                    "symbol": None,
                    "side": "short",
                    "state": "unrecoverable",
                    "missing_fields": ["symbol"],
                },
            ],
        )
    ]
    df = build_reconciliation_drilldown_dataframe(events)
    assert len(df) == 2
    assert set(df.columns) == {
        "Sub-account",
        "Trade ID",
        "Symbol",
        "Side",
        "State",
        "Missing Fields",
    }
    # The unrecoverable row's missing fields are rendered as a comma-list.
    row_t2 = df[df["Trade ID"] == "t2"].iloc[0]
    assert row_t2["State"] == "unrecoverable"
    assert row_t2["Missing Fields"] == "symbol"


def test_reconciliation_drilldown_empty_keeps_columns() -> None:
    """Empty event list → empty DataFrame, columns preserved."""
    df = build_reconciliation_drilldown_dataframe([])
    assert df.empty
    assert "State" in df.columns


# =============================================================================
# Q4 follow-up: health-check failure visibility
# =============================================================================


def _failed_event(*, timestamp: datetime) -> ActivityEvent:
    """Build a ``RECONCILIATION_HEALTH_CHECK_FAILED`` event for tests."""
    return make_event(
        event_type=ActivityEventType.RECONCILIATION_HEALTH_CHECK_FAILED,
        timestamp=timestamp,
        message="Reconciliation health check failed: boom",
        details={
            "error_type": "RuntimeError",
            "message": "boom",
            "sub_account_id": None,
        },
    )


def test_reconciliation_banner_yellow_on_health_check_failed() -> None:
    """``RECONCILIATION_HEALTH_CHECK_FAILED`` as latest event → Yellow + CTA.

    Pre-Q4 the dashboard rendered Green with "engine has not started"
    in this case — operators could not distinguish a fresh deploy from
    a chronically-broken health check (DEBT-061 silent-disable
    anti-pattern). This pin asserts the failure is operator-visible.
    """
    events = [_failed_event(timestamp=now_utc())]
    banner = build_reconciliation_status_banner(events)
    assert banner.color == "yellow"
    assert "investigate logs" in banner.message.lower()
    assert banner.cta is not None
    assert banner.report_timestamp is not None


def test_reconciliation_banner_failed_event_wins_over_older_success() -> None:
    """A later failure overrides an earlier successful Green report."""
    older = _reconciliation_event(
        timestamp=now_utc() - timedelta(hours=1),
        open_count=3,
        monitorable=3,
    )
    newer = _failed_event(timestamp=now_utc())
    banner = build_reconciliation_status_banner([older, newer])
    assert banner.color == "yellow"


def test_reconciliation_banner_success_wins_over_older_failure() -> None:
    """A later successful report overrides an earlier failed meta-event.

    Symmetric pin: once the operator fixes the underlying ledger crash
    the next startup's success report should win, restoring Green.
    """
    older = _failed_event(timestamp=now_utc() - timedelta(hours=1))
    newer = _reconciliation_event(
        timestamp=now_utc(),
        open_count=2,
        monitorable=2,
    )
    banner = build_reconciliation_status_banner([older, newer])
    assert banner.color == "green"


def test_reconciliation_drilldown_empty_on_failed_event() -> None:
    """The failed meta-event carries no classifications → empty drill-through."""
    events = [_failed_event(timestamp=now_utc())]
    df = build_reconciliation_drilldown_dataframe(events)
    assert df.empty
    # Columns still preserved so the dashboard renders the empty table
    # without a KeyError.
    assert "State" in df.columns


# =============================================================================
# Cross-Account Risk panel (cross-account-risk-policy DEBT-068(f-1))
# =============================================================================


def _kill_switch_event(
    *,
    sub_account_id: str,
    gate_reason: str,
    cycle_id: str | None = "cyc-1",
    timestamp: datetime | None = None,
    advisory: bool = False,
    proposal_id: str = "p-1",
    extra: dict | None = None,
) -> ActivityEvent:
    details = {
        "proposal_id": proposal_id,
        "sub_account_id": sub_account_id,
        "symbol": "ETHUSDT",
        "side": "long",
        "gate_reason": gate_reason,
        "mode": "live",
    }
    if advisory:
        details["advisory"] = True
        details["mode"] = "paper"
    if extra:
        details.update(extra)
    return make_event(
        event_type=ActivityEventType.RISK_KILL_SWITCH_TRIPPED,
        timestamp=timestamp or now_utc(),
        cycle_id=cycle_id,
        details=details,
    )


def _global_cap_event(
    *,
    event_type: ActivityEventType = ActivityEventType.RISK_CAP_ADVISORY,
    symbol: str = "ETHUSDT",
    side: str = "long",
    open_positions_total: int | None = None,
    max_open_positions: int | None = None,
    ss_notional_total: str | None = None,
    max_ss_notional: str | None = None,
    holders: list[str] | None = None,
    proposer: str = "rsi_universal",
    cycle_id: str | None = "cyc-1",
    timestamp: datetime | None = None,
    advisory: bool = True,
) -> ActivityEvent:
    details: dict = {
        "proposal_id": "p-g",
        "sub_account_id": proposer,
        "proposer_account": proposer,
        "symbol": symbol,
        "side": side,
        "gate_reason": "global_cap",
        "mode": "paper" if advisory else "live",
        "existing_holders": holders or [],
    }
    if advisory:
        details["advisory"] = True
    if open_positions_total is not None:
        details["open_positions_per_symbol_side_total"] = open_positions_total
    if max_open_positions is not None:
        details["max_open_positions_per_symbol_side"] = max_open_positions
    if ss_notional_total is not None:
        details["gross_notional_per_symbol_side_total"] = ss_notional_total
    if max_ss_notional is not None:
        details["max_gross_notional_per_symbol_side"] = max_ss_notional
    return make_event(
        event_type=event_type,
        timestamp=timestamp or now_utc(),
        cycle_id=cycle_id,
        details=details,
    )


def test_cross_account_risk_df_empty_on_no_events() -> None:
    df = build_cross_account_risk_dataframe([])
    assert df.empty
    assert "Kill-switch State" in df.columns


def test_cross_account_risk_df_kill_switch_state() -> None:
    events = [
        _kill_switch_event(
            sub_account_id="rsi_universal",
            gate_reason="daily_loss_kill_switch",
            extra={"realized_pnl_today": "-150.0", "equity": "5000.0"},
        ),
    ]
    df = build_cross_account_risk_dataframe(events)
    row = df.iloc[0]
    assert row["Sub-account"] == "rsi_universal"
    assert row["Kill-switch State"] == "daily-loss-tripped"
    assert row["Equity"] == "5000.0"
    assert row["Realized PnL (today)"] == "-150.0"
    # Unsourced field renders n/a, not invented.
    assert row["Gross Open Notional"] == "n/a"


def test_kill_switch_state_window_is_latest_cycle() -> None:
    old = _kill_switch_event(
        sub_account_id="acc",
        gate_reason="open_stop_risk_kill_switch",
        cycle_id="cyc-old",
        timestamp=now_utc() - timedelta(hours=2),
    )
    # A newer event from a different account establishes the latest cycle
    # as cyc-new; acc did not trip in cyc-new -> state none.
    newer_other = _kill_switch_event(
        sub_account_id="other",
        gate_reason="open_drawdown_kill_switch",
        cycle_id="cyc-new",
        timestamp=now_utc(),
    )
    state = kill_switch_state_for_account(
        [old, newer_other], "acc", cycle_id="cyc-new"
    )
    assert state == "none"
    state_other = kill_switch_state_for_account(
        [old, newer_other], "other", cycle_id="cyc-new"
    )
    assert state_other == "drawdown-tripped"


def test_kill_switch_state_stale_block() -> None:
    ev = make_event(
        event_type=ActivityEventType.STALE_POSITION_DETECTED,
        timestamp=now_utc(),
        cycle_id="cyc-1",
        details={"sub_account_id": "acc", "resolution": "block_new_entries"},
    )
    state = kill_switch_state_for_account([ev], "acc", cycle_id="cyc-1")
    assert state == "stale-block"


def test_portfolio_cap_utilization_bands() -> None:
    # 70/90/100 thresholds: total/limit gives the band.
    green = _global_cap_event(
        ss_notional_total="3400", max_ss_notional="5000"
    )  # 68% -> green
    df = build_portfolio_cap_utilization([green])
    band = df.loc[df["Cap"] == "gross_notional_per_symbol_side", "Band"].iloc[0]
    assert band == "green"

    amber = _global_cap_event(ss_notional_total="3600", max_ss_notional="5000")
    assert (
        build_portfolio_cap_utilization([amber])
        .loc[lambda d: d["Cap"] == "gross_notional_per_symbol_side", "Band"]
        .iloc[0]
        == "amber"
    )  # 72%

    red = _global_cap_event(ss_notional_total="4600", max_ss_notional="5000")
    assert (
        build_portfolio_cap_utilization([red])
        .loc[lambda d: d["Cap"] == "gross_notional_per_symbol_side", "Band"]
        .iloc[0]
        == "red"
    )  # 92%

    breach = _global_cap_event(ss_notional_total="5500", max_ss_notional="5000")
    assert (
        build_portfolio_cap_utilization([breach])
        .loc[lambda d: d["Cap"] == "gross_notional_per_symbol_side", "Band"]
        .iloc[0]
        == "breach"
    )  # 110%


def test_portfolio_cap_utilization_empty_when_no_global_events() -> None:
    df = build_portfolio_cap_utilization([])
    assert df.empty


def test_symbol_side_exposure_counts_distinct_accounts() -> None:
    ev = _global_cap_event(
        symbol="ETHUSDT",
        side="long",
        holders=["bollinger_band_reversion", "vcp_breakout"],
        proposer="rsi_universal",
        ss_notional_total="6000",
        max_ss_notional="5000",
        open_positions_total=4,
        max_open_positions=3,
    )
    df = build_symbol_side_exposure_dataframe([ev])
    row = df.iloc[0]
    assert row["Symbol"] == "ETHUSDT"
    assert row["Side"] == "long"
    # 2 holders + proposer = 3 distinct accounts.
    assert row["Accounts"] == 3
    assert row["Total Notional"] == "6000"
    # ss_notional 120% beats open_positions 133%? open_positions 4/3=133%.
    assert row["Closest Cap"] == "open_positions_per_symbol_side"


def test_risk_gate_events_includes_dedicated_and_live_rejected() -> None:
    kill = _kill_switch_event(
        sub_account_id="acc", gate_reason="open_drawdown_kill_switch"
    )
    live_cap = make_event(
        event_type=ActivityEventType.PROPOSAL_REJECTED,
        timestamp=now_utc(),
        cycle_id="cyc-1",
        details={
            "sub_account_id": "acc",
            "symbol": "BNBUSDT",
            "side": "short",
            "gate_reason": "global_cap",
            "mode": "live",
        },
    )
    # Unrelated rejection must be excluded.
    stale_quote = make_event(
        event_type=ActivityEventType.PROPOSAL_REJECTED,
        timestamp=now_utc(),
        details={"gate_reason": "stale_quote_past_sl", "sub_account_id": "acc"},
    )
    df = build_risk_gate_events_dataframe([kill, live_cap, stale_quote])
    reasons = set(df["Gate Reason"])
    assert "open_drawdown_kill_switch" in reasons
    assert "global_cap" in reasons
    assert "stale_quote_past_sl" not in reasons


def test_operator_freeze_state_engaged_and_not() -> None:
    assert build_operator_freeze_state([]).engaged is False
    freeze = make_event(
        event_type=ActivityEventType.OPERATOR_FREEZE_ENGAGED,
        timestamp=now_utc(),
        cycle_id="cyc-1",
        details={"proposal_id": "p1", "reason": "operator_freeze"},
    )
    state = build_operator_freeze_state([freeze])
    assert state.engaged is True
    assert state.last_engaged_at is not None


# --- DEBT-068(f-2): freeze toggle plan (pure decision logic) ---


def test_freeze_toggle_plan_when_not_frozen_engages() -> None:
    plan = build_freeze_toggle_plan(currently_frozen=False)
    assert plan.next_value is True
    assert plan.action_label == "Engage freeze"
    assert "HALTS" in plan.confirmation_prompt


def test_freeze_toggle_plan_when_frozen_disengages() -> None:
    plan = build_freeze_toggle_plan(currently_frozen=True)
    assert plan.next_value is False
    assert plan.action_label == "Disengage freeze"
    assert "RESUMES" in plan.confirmation_prompt


# --- DEBT-068(g-note): Rejected-column rebase pins ---


def test_rejected_tally_counts_live_kill_switch_not_paper_advisory() -> None:
    """Live kill-switch trips count; paper advisories do not."""
    events = [
        make_event(
            event_type=ActivityEventType.PROPOSAL_GENERATED,
            timestamp=now_utc(),
            details={"sub_account_id": "live_acc"},
        ),
        # Live kill-switch trip WITHOUT a sibling PROPOSAL_REJECTED ->
        # must self-count as a rejection.
        _kill_switch_event(
            sub_account_id="live_acc",
            gate_reason="daily_loss_kill_switch",
            proposal_id="p-live",
            advisory=False,
        ),
        # Paper advisory kill-switch -> must NOT count.
        _kill_switch_event(
            sub_account_id="paper_acc",
            gate_reason="open_drawdown_kill_switch",
            proposal_id="p-paper",
            advisory=True,
        ),
    ]
    df = build_sub_account_metrics_dataframe(events)
    live_row = df.loc[df["Sub-account"] == "live_acc"].iloc[0]
    assert live_row["Rejected"] == 1
    # The paper advisory contributed nothing countable, so paper_acc has no
    # row at all (and certainly is not tallied as a rejection).
    paper_rows = df.loc[df["Sub-account"] == "paper_acc"]
    if not paper_rows.empty:
        assert paper_rows.iloc[0]["Rejected"] == 0


def test_rejected_tally_no_double_count_live_kill_switch() -> None:
    """A live kill-switch emits BOTH events on one proposal -> count once."""
    pid = "p-dup"
    events = [
        make_event(
            event_type=ActivityEventType.PROPOSAL_REJECTED,
            timestamp=now_utc(),
            details={
                "sub_account_id": "acc",
                "proposal_id": pid,
                "gate_reason": "daily_loss_kill_switch",
                "mode": "live",
            },
        ),
        _kill_switch_event(
            sub_account_id="acc",
            gate_reason="daily_loss_kill_switch",
            proposal_id=pid,
            advisory=False,
        ),
    ]
    df = build_sub_account_metrics_dataframe(events)
    row = df.loc[df["Sub-account"] == "acc"].iloc[0]
    assert row["Rejected"] == 1


def test_rejected_tally_excludes_risk_cap_advisory() -> None:
    """RISK_CAP_ADVISORY is never a hard block -> never counts as Rejected."""
    events = [
        _global_cap_event(advisory=True),
    ]
    df = build_sub_account_metrics_dataframe(events)
    # The advisory event references rsi_universal but is not a rejection.
    if not df.empty and "rsi_universal" in set(df["Sub-account"]):
        row = df.loc[df["Sub-account"] == "rsi_universal"].iloc[0]
        assert row["Rejected"] == 0

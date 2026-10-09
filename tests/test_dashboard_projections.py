"""Exact reducer parity across interleaving, scope, windows and mutable files."""

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from src.dashboard.pages import engine, home, proposals, trading
from src.dashboard.projections import build_projection, encode
from src.dashboard.read_models import Limits, Query
from src.dashboard.sources import discover
from src.proposal.funnel import compute_funnel_counts, compute_funnel_counts_by_strategy
from src.proposal.interaction import ProposalRecord
from src.runtime.activity_events import ActivityEvent
from src.runtime.activity_log import ActivityLog
from src.runtime.safety_score import (
    compute_runtime_safety_score,
    inputs_from_recent_activity_events,
)
from src.utils.bounded_read import ReadFailure

NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)


def projection(query, limits=None):
    return next(
        value
        for value in build_projection(query, limits or Limits())
        if value is not None
    )


def event(typ, *, at=NOW, cid=None, **details):
    return ActivityEvent(
        timestamp=at, event_type=typ, cycle_id=cid, details=details, message=typ
    )


def write_events(root, events):
    directory = root / "runtime"
    directory.mkdir(exist_ok=True)
    path = directory / "activity.jsonl"
    path.write_text("\n".join(e.model_dump_json() for e in events) + "\n")
    return ActivityLog(path=path).read_all()


def test_interleaved_cycles_companion_scope_and_error_terminal_parity(tmp_path):
    events = [
        event("cycle_started", at=NOW - timedelta(days=2), cid="a"),
        event("cycle_started", at=NOW - timedelta(hours=2), cid="b"),
        event(
            "risk_kill_switch_tripped",
            cid="a",
            proposal_id="p",
            gate_reason="daily_loss_kill_switch",
            sub_account_id="one",
        ),
        event(
            "risk_kill_switch_tripped",
            cid="b",
            proposal_id="p",
            gate_reason="daily_loss_kill_switch",
            sub_account_id="one",
        ),
        event("proposal_rejected", cid="a", proposal_id="p", sub_account_id="one"),
        event(
            "operator_freeze_engaged",
            cid="b",
            proposal_id="other",
            sub_account_id="two",
        ),
        event(
            "risk_kill_switch_tripped",
            cid="b",
            proposal_id="advisory",
            advisory=True,
            sub_account_id="two",
        ),
        event("cycle_errored", at=NOW + timedelta(seconds=1), cid="a"),
        event("cycle_completed", at=NOW, cid="a"),
        event("proposal_generated", cid="b", sub_account_id="one"),
        event("position_opened", cid="b", sub_account_id="two"),
    ]
    legacy = write_events(tmp_path, events)
    result = projection(Query(tmp_path, "activity", at=NOW))
    expected = engine.aggregate_cycles(legacy)
    assert result["cycles"] == encode([asdict(cycle) for cycle in expected])
    assert result["metrics"] == encode(engine.build_summary_metrics(legacy, expected))
    assert result["safety"] == compute_runtime_safety_score(
        inputs_from_recent_activity_events(legacy, now=NOW)
    ).model_dump(mode="json")
    pd.testing.assert_frame_equal(
        pd.DataFrame(result["sub_rows"]),
        engine.build_sub_account_metrics_dataframe(legacy),
        check_dtype=False,
    )


def test_latest_reconciliation_outside_window_and_timestamp_ties(tmp_path):
    old = NOW - timedelta(days=20)
    events = [
        event("reconciliation_health_check_failed", at=old, message="first"),
        event("reconciliation_health_report", at=old, message="second"),
        event("cycle_started", at=NOW, cid="new"),
    ]
    # Details named message don't change the top-level source order.
    legacy = write_events(tmp_path, events)
    result = projection(Query(tmp_path, "activity", at=NOW))
    compact = [ActivityEvent.model_validate(raw) for raw in result["events"]]
    assert engine.latest_reconciliation_event(
        compact
    ) == engine.latest_reconciliation_event(legacy)
    assert result["safety"]["score"] == 100


def test_home_selected_scope_preserves_global_actionable_card(tmp_path):
    events = [
        event("cycle_started", at=NOW - timedelta(hours=2), cid="a"),
        event("cycle_completed", at=NOW - timedelta(hours=1), cid="a"),
        *[
            event(
                "notification_failed",
                at=NOW - timedelta(minutes=i),
                sub_account_id="other",
            )
            for i in range(15)
        ],
        event("cycle_errored", cid="a", sub_account_id="one"),
    ]
    legacy = write_events(tmp_path, events)
    result = projection(Query(tmp_path, "activity", scope="one", at=NOW))
    scoped = [
        e for e in legacy if str(e.details.get("sub_account_id", "")) in {"", "one"}
    ]
    assert result["actionable"] == home.count_actionable_events(legacy, now=NOW) == 10
    assert result["safety"] == compute_runtime_safety_score(
        inputs_from_recent_activity_events(scoped, now=NOW)
    ).model_dump(mode="json")
    assert len(result["incidents"]) == 1


def test_latest_field_risk_regime_derivatives_and_lifetime_crowding_parity(tmp_path):
    events = [
        event("cycle_started", at=NOW - timedelta(hours=1), cid="old"),
        event(
            "risk_cap_advisory",
            at=NOW - timedelta(minutes=50),
            cid="old",
            sub_account_id="one",
            equity="1000",
            gross_notional_total="200",
        ),
        event(
            "risk_kill_switch_tripped",
            at=NOW - timedelta(minutes=40),
            cid="old",
            sub_account_id="one",
            realized_pnl_today="-50",
            gate_reason="daily_loss_kill_switch",
        ),
        event("cycle_started", at=NOW - timedelta(minutes=10), cid="new"),
        event(
            "market_regime_blocked",
            symbol="BTC/USDT",
            timeframe="1h",
            sub_account_id="one",
            regime="bear",
        ),
        *[
            event(
                "funding_oi_crowding_observed",
                at=NOW - timedelta(days=2, seconds=i),
                would_block=i % 2 == 0,
            )
            for i in range(100)
        ],
        event("funding_oi_crowding_skipped"),
    ]
    legacy = write_events(tmp_path, events)
    result = projection(Query(tmp_path, "activity", at=NOW))
    compact = [ActivityEvent.model_validate(raw) for raw in result["events"]]
    for builder in (
        engine.build_cross_account_risk_dataframe,
        engine.build_portfolio_cap_utilization,
        engine.build_symbol_side_exposure_dataframe,
        engine.build_risk_gate_events_dataframe,
        engine.build_market_regime_events_dataframe,
        engine.build_market_regime_degraded_events_dataframe,
        engine.build_funding_oi_crowding_events_dataframe,
    ):
        pd.testing.assert_frame_equal(builder(compact), builder(legacy))
    assert result["crowding"] == asdict(
        engine.build_funding_oi_crowding_summary(legacy)
    )


def test_funnel_window_and_mutable_replacement_keep_exact_totals(tmp_path):
    from tests.test_dashboard_trading import _make_proposal

    directory = tmp_path / "proposals"
    directory.mkdir()
    records = []
    for i, at in enumerate((NOW - timedelta(hours=24), NOW, NOW - timedelta(days=40))):
        proposal = _make_proposal(str(i)).model_copy(
            update={"created_at": at, "technique_name": f"tech-{i}"}
        )
        record = ProposalRecord(
            proposal=proposal,
            decision="rejected",
            rejection_reason="composite 0.2000 below threshold 0.3000",
        )
        (directory / f"{i}.json").write_text(record.model_dump_json())
        records.append(record)
    window = proposals.window_for_label("24h", now=NOW)
    result = projection(Query(tmp_path, "proposals", window="24h", at=NOW))
    assert result["counts"] == compute_funnel_counts(records, window).model_dump()
    assert result["by_strategy"] == {
        key: value.model_dump()
        for key, value in compute_funnel_counts_by_strategy(records, window).items()
    }
    assert result["threshold"] == 3  # Lifetime/global, despite funnel window.
    replacement = records[0].model_copy(
        update={
            "decision": "accepted",
            "rejection_reason": None,
            "final_state": "trade_opened",
        }
    )
    (directory / "0.json").write_text(replacement.model_dump_json())
    updated = projection(Query(tmp_path, "proposals", at=NOW))
    assert updated["counts"]["total"] == 3
    assert updated["counts"]["trade_opened"] == 1 and updated["threshold"] == 2


def test_trade_snapshot_scope_history_and_sampled_curve(tmp_path):
    from tests.test_dashboard_trading import make_snapshot, make_trade

    directory = tmp_path / "trades" / "paper" / "one"
    directory.mkdir(parents=True)
    trades = [
        make_trade(
            trade_id=str(i),
            status="closed" if i else "open",
            close_reason="take_profit" if i % 2 else "manual",
            pnl="1.25",
            entry_time=NOW + timedelta(seconds=i),
        )
        for i in range(100)
    ]
    (directory / "trades.json").write_text(
        json.dumps([trade.model_dump(mode="json") for trade in trades])
    )
    portfolio = tmp_path / "portfolio" / "paper" / "one"
    portfolio.mkdir(parents=True)
    snapshots = [
        make_snapshot(timestamp=NOW + timedelta(seconds=i), quote_balance=str(i % 20))
        for i in range(4200)
    ]
    (portfolio / "snapshots.json").write_text(
        json.dumps([snapshot.model_dump(mode="json") for snapshot in snapshots])
    )
    ledger = projection(Query(tmp_path, "ledger", accounts=("one",)))
    result = projection(Query(tmp_path, "snapshots", accounts=("one",)))
    assert ledger["metrics"] == {
        "open_positions": 1,
        "closed_trades": 99,
        "wins": 50,
        "realized_pnl": 123.75,
    }
    assert len(ledger["open"]) == 1 and len(ledger["history"]) == 25
    pd.testing.assert_frame_equal(
        trading.build_trade_history_dataframe(
            [trading.TradeHistory.model_validate(raw) for raw in ledger["history"]]
        ),
        trading.build_trade_history_dataframe(trades),
        check_dtype=False,
    )
    assert result["sampled"] and len(result["curves"]["one"]) <= 4096
    assert result["curves"]["one"][0]["timestamp"] == snapshots[0].timestamp.isoformat()
    assert (
        result["curves"]["one"][-1]["timestamp"] == snapshots[-1].timestamp.isoformat()
    )
    assert result["latest"]["one"] == snapshots[-1].model_dump(mode="json")
    assert not (tmp_path / "trades" / "live").exists()


def test_budget_exhaustion_and_membership_changes_are_explicit(tmp_path):
    write_events(tmp_path, [event("cycle_started", cid=f"c{i}") for i in range(20)])
    with pytest.raises(ReadFailure, match="identity_budget_exhausted"):
        projection(Query(tmp_path, "activity"), Limits(identities=5))
    with pytest.raises(ReadFailure, match="manifest_budget_exhausted"):
        discover(Query(tmp_path, "activity"), Limits(manifest_bytes=16), 12)
    manifest = discover(Query(tmp_path, "activity"), Limits(), 12)
    (tmp_path / "runtime" / "activity.2026-10.jsonl").write_text("{}\n")
    with pytest.raises(ReadFailure, match="source_changed"):
        manifest.verify()


def test_verified_cache_reuses_compact_state_and_expires_safety_window(
    tmp_path, monkeypatch
):
    from src.dashboard import projections as module

    clock = NOW
    monkeypatch.setattr(module, "utc_now", lambda: clock)
    write_events(
        tmp_path,
        [
            event(
                "notification_failed",
                at=NOW - timedelta(hours=24) + timedelta(seconds=0.5),
            )
        ],
    )
    first = projection(Query(tmp_path, "activity"))
    assert first["safety"]["score"] < 100
    clock = NOW + timedelta(seconds=1)
    monkeypatch.setattr(
        module,
        "reverse_jsonl_records",
        lambda *_: (_ for _ in ()).throw(AssertionError("unchanged file reread")),
    )
    result = next(
        item
        for item in module.build_projection(
            Query(tmp_path, "activity"), Limits(), previous=json.dumps(first).encode()
        )
        if item is not None
    )
    assert result["safety"]["score"] == 100
    assert result["actionable"] == 0 and result["incidents"] == []
    assert result["evaluated_at"] == clock.isoformat()


def test_cache_file_replacement_invalidates_and_does_not_increment_old_total(tmp_path):
    write_events(tmp_path, [event("notification_failed")])
    first = projection(Query(tmp_path, "activity", at=NOW))
    replacement = tmp_path / "replacement"
    replacement.write_text(event("cycle_started", cid="new").model_dump_json() + "\n")
    replacement.replace(tmp_path / "runtime" / "activity.jsonl")
    result = next(
        item
        for item in build_projection(
            Query(tmp_path, "activity", at=NOW),
            Limits(),
            previous=json.dumps(first).encode(),
        )
        if item is not None
    )
    assert result["total"] == 1 and result["metrics"]["total_cycles"] == 1
    assert result["safety"]["score"] == 100


def test_missing_timestamp_cannot_become_a_fresh_health_event(tmp_path):
    directory = tmp_path / "runtime"
    directory.mkdir()
    directory.joinpath("activity.jsonl").write_text(
        '{"event_type":"reconciliation_health_report","details":{}}\n'
    )
    with pytest.raises(ReadFailure, match="missing_timestamp"):
        projection(Query(tmp_path, "activity"))


def test_bootstrap_expiry_uses_publication_window_and_clock_reversal_fails(
    tmp_path, monkeypatch
):
    from src.dashboard import projections as module

    write_events(
        tmp_path,
        [
            event(
                "notification_failed",
                at=NOW - timedelta(hours=24) + timedelta(seconds=1),
            )
        ],
    )
    readings = iter([NOW, NOW + timedelta(seconds=2)])
    monkeypatch.setattr(module, "utc_now", lambda: next(readings))
    result = projection(Query(tmp_path, "activity"))
    assert result["actionable"] == 0 and result["incidents"] == []
    assert result["safety"]["score"] == 100
    readings = iter([NOW, NOW - timedelta(seconds=1)])
    with pytest.raises(ReadFailure, match="evaluation_clock_reversed"):
        projection(Query(tmp_path, "activity"))


def test_audit_keeps_newest_candidate_rows_and_declares_lifetime_count(tmp_path):
    from src.feedback.audit import AuditEvent

    directory = tmp_path / "audit"
    directory.mkdir()
    events = [
        AuditEvent(
            timestamp=NOW + timedelta(seconds=i),
            event_type="generated",
            candidate_id="one" if i % 2 else "two",
            technique_name="test",
            technique_version="v1",
        )
        for i in range(700)
    ]
    directory.joinpath("feedback.jsonl").write_text(
        "\n".join(event.model_dump_json() for event in events) + "\n"
    )
    result = projection(Query(tmp_path, "audit", scope="one"))
    assert result["audit_total"] == 350 and len(result["audit"]) == 300
    assert (
        result["audit"]
        == [
            event.model_dump(mode="json")
            for event in events
            if event.candidate_id == "one"
        ][-300:]
    )

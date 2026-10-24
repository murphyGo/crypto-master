"""Exact reducer parity across interleaving, scope, windows and mutable files."""

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import InvalidOperation

import pandas as pd
import pytest

from src.dashboard.pages import engine, home, proposals, trading
from src.dashboard.projections import (
    HistoryProjection,
    StateBudget,
    build_projection,
    encode,
)
from src.dashboard.read_models import Limits, Query
from src.dashboard.sources import discover
from src.proposal.funnel import compute_funnel_counts, compute_funnel_counts_by_strategy
from src.proposal.interaction import ProposalRecord
from src.runtime.activity_events import ActivityEvent, ActivityEventType
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
        "reverse_jsonl_bytes",
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


def test_directory_noise_reuses_verified_activity_but_membership_changes_rebuild(
    tmp_path, monkeypatch
):
    from src.dashboard import projections as module

    write_events(tmp_path, [event("cycle_started", cid="old")])
    query = Query(tmp_path, "activity", at=NOW)
    first = projection(query)
    reader = module.reverse_jsonl_bytes

    def no_reread(*args, **kwargs):
        pytest.fail("unrelated directory metadata caused an archive rebuild")

    monkeypatch.setattr(module, "reverse_jsonl_bytes", no_reread)
    (tmp_path / "runtime" / ".writer-temporary").write_text("not an eligible source")
    refreshed = next(
        row
        for row in build_projection(
            query, Limits(), previous=json.dumps(first).encode()
        )
        if row is not None
    )
    assert refreshed == first
    monkeypatch.setattr(module, "reverse_jsonl_bytes", reader)
    archive = tmp_path / "runtime" / "activity.2026-09.jsonl"
    archive.write_text(event("cycle_completed", cid="old").model_dump_json() + "\n")
    added = next(
        row
        for row in build_projection(
            query, Limits(), previous=json.dumps(first).encode()
        )
        if row is not None
    )
    assert added["total"] == 2 and added["source_coverage"]["files"] == 2
    archive.unlink()
    removed = next(
        row
        for row in build_projection(
            query, Limits(), previous=json.dumps(added).encode()
        )
        if row is not None
    )
    assert removed == first


def test_cache_reuse_still_rejects_concurrent_directory_membership_change(
    tmp_path, monkeypatch
):
    from src.dashboard import projections as module

    write_events(tmp_path, [event("cycle_started", cid="old")])
    query = Query(tmp_path, "activity", at=NOW)
    previous = json.dumps(projection(query)).encode()
    refresh = module.refresh_projection

    def changed(*args, **kwargs):
        data = refresh(*args, **kwargs)
        (tmp_path / "runtime" / "activity.2026-09.jsonl").write_text("broken\n")
        return data

    monkeypatch.setattr(module, "refresh_projection", changed)
    with pytest.raises(ReadFailure, match="source_changed"):
        list(build_projection(query, Limits(), previous=previous))


def test_snapshot_json_matches_dictionary_path_for_numeric_legacy_and_ties(tmp_path):
    from tests.test_dashboard_trading import make_snapshot

    path = tmp_path / "portfolio" / "paper" / "default" / "snapshots.json"
    path.parent.mkdir(parents=True)
    rows = []
    for value in (1.2345678901234567, 9007199254740993, 1e-20, "123.4500"):
        row = make_snapshot(timestamp=NOW).model_dump(mode="json")
        row.update(
            balances={"USDT": value},
            realized_pnl=value,
            current_prices={"BTC/USDT": value},
        )
        rows.append(row)
    path.write_text(json.dumps(rows))
    query = Query(tmp_path, "snapshots", at=NOW)
    limits = Limits()
    source = next(discover(query, limits, 12).files)
    legacy = HistoryProjection(query, StateBudget(limits))
    for ordinal, row in enumerate(rows):
        legacy.add(row, source, ordinal)
    result = projection(query)
    expected = legacy.finish()
    assert {key: result[key] for key in expected} == expected
    assert result["latest"]["default"]["balances"]["USDT"] == str(
        rows[0]["balances"]["USDT"]
    )


@pytest.mark.parametrize(
    "bad",
    ['{"mode":"invalid"}', '{"mode":}', '{"mode":"paper","balances":{"USDT":"bad"}}'],
)
def test_direct_snapshot_validation_cannot_skip_damaged_old_row(tmp_path, bad):
    from tests.test_dashboard_trading import make_snapshot

    path = tmp_path / "portfolio" / "paper" / "default" / "snapshots.json"
    path.parent.mkdir(parents=True)
    valid = make_snapshot(timestamp=NOW).model_dump_json()
    path.write_text("[" + bad + "," + valid + "]")
    with pytest.raises((ReadFailure, InvalidOperation)):
        projection(Query(tmp_path, "snapshots", at=NOW))


def test_cycle_datetime_reduction_preserves_naive_offset_and_terminal_ties(tmp_path):
    events = [
        event("cycle_started", at=NOW.replace(tzinfo=None), cid="a"),
        event("cycle_errored", at=NOW, cid="a"),
        event(
            "cycle_completed", at=NOW.astimezone(timezone(timedelta(hours=9))), cid="a"
        ),
        event("position_closed", at=NOW + timedelta(microseconds=1), cid="unstarted"),
        event("cycle_started", at=NOW + timedelta(microseconds=1), cid="b"),
    ]
    legacy = write_events(tmp_path, events)
    query = Query(tmp_path, "activity", at=NOW)
    result = projection(query)
    started = [row for row in legacy if row.cycle_id != "unstarted"]
    cycles = engine.aggregate_cycles(started)
    assert result["cycles"][:-1] == encode([asdict(cycle) for cycle in cycles])
    assert result["cycles"][-1]["cycle_id"] == "unstarted"
    assert result["cycles"][-1]["started_at"] is None
    metrics = engine.build_summary_metrics(started, cycles)
    metrics["total_cycles"] += 1
    metrics["positions_closed_total"] += 1
    assert result["metrics"] == encode(metrics)


def test_started_minimum_timestamp_cycle_precedes_cycle_without_start(tmp_path):
    at = datetime.min.replace(tzinfo=timezone.utc)
    write_events(
        tmp_path,
        [
            event("monitor_pass", at=at, cid="unstarted"),
            event("cycle_started", at=at, cid="started"),
        ],
    )
    result = projection(Query(tmp_path, "activity", at=NOW))
    assert [row["cycle_id"] for row in result["cycles"]] == ["started", "unstarted"]


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


def test_lazy_activity_details_keep_timeline_and_gate_samples_exact(
    tmp_path, monkeypatch
):
    events = [
        event(
            "monitor_pass",
            at=NOW - timedelta(seconds=i),
            cid="cycle",
            context="x" * 1000,
        )
        for i in range(1000, 0, -1)
    ]
    for reasons in proposals.GATE_REASON_BY_STATE.values():
        for reason in reasons:
            events.extend(
                [
                    event(
                        "proposal_rejected",
                        at=NOW - timedelta(seconds=2),
                        reason=reason,
                    ),
                    event("monitor_pass", reason=reason + "_legacy"),
                    event("proposal_rejected", gate_reason=reason),
                ]
            )
    # One event can supply two different gate samples; source-order ties
    # retain the first event, including a legacy match on a non-rejection.
    reasons = list(proposals.GATE_REASON_BY_STATE.values())
    events.append(
        event(
            "monitor_pass", gate_reason=reasons[0][0], reason=reasons[1][0] + "_legacy"
        )
    )
    legacy = write_events(tmp_path, events)
    original = ActivityEvent.model_dump
    serialized = 0

    def counted(self, *args, **kwargs):
        nonlocal serialized
        serialized += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ActivityEvent, "model_dump", counted)
    result = projection(Query(tmp_path, "activity", at=NOW))
    assert result["total"] == len(events)
    assert serialized <= 330  # Rich rows are bounded by display retention.
    assert [
        {key: value for key, value in raw.items() if key != "_ordinal"}
        for raw in result["timeline"]
    ] == [original(e, mode="json") for e in legacy[-300:]]
    compact = [ActivityEvent.model_validate(raw) for raw in result["events"]]
    for gate in proposals.GATE_REASON_BY_STATE:
        assert proposals.latest_sample_event_for_gate(
            compact, gate
        ) == proposals.latest_sample_event_for_gate(legacy, gate)


@pytest.mark.parametrize(
    "bad",
    [
        "[]",
        '{"timestamp":null}',
        '{"timestamp":"bad"}',
        '{"timestamp":"2026-10-10T00:00:00Z","details":[]}',
    ],
)
def test_direct_activity_validation_rejects_old_rows_outside_display_tail(
    tmp_path, bad
):
    write_events(
        tmp_path,
        [event("monitor_pass", at=NOW + timedelta(seconds=i)) for i in range(400)],
    )
    path = tmp_path / "runtime" / "activity.jsonl"
    path.write_text(bad + "\n" + path.read_text())
    with pytest.raises(ReadFailure, match="invalid_record"):
        projection(Query(tmp_path, "activity", at=NOW))


def test_snapshot_accounting_still_rejects_retained_state_over_budget(tmp_path):
    from tests.test_dashboard_trading import make_snapshot

    directory = tmp_path / "portfolio" / "paper" / "one"
    directory.mkdir(parents=True)
    values = [make_snapshot(timestamp=NOW + timedelta(seconds=i)) for i in range(100)]
    (directory / "snapshots.json").write_text(
        json.dumps([row.model_dump(mode="json") for row in values])
    )
    with pytest.raises(ReadFailure, match="state_budget_exhausted"):
        projection(
            Query(tmp_path, "snapshots", accounts=("one",)), Limits(state_bytes=4096)
        )


def test_snapshot_history_serializes_only_retained_latest_model(tmp_path, monkeypatch):
    from src.trading.portfolio import AssetSnapshot
    from tests.test_dashboard_trading import make_snapshot

    directory = tmp_path / "portfolio" / "paper" / "default"
    directory.mkdir(parents=True)
    rows = [
        make_snapshot(timestamp=NOW + timedelta(seconds=i), quote_balance=str(i))
        for i in range(1000)
    ]
    (directory / "snapshots.json").write_text(
        "[" + ",".join(row.model_dump_json() for row in rows) + "]"
    )
    original = AssetSnapshot.model_dump
    calls = 0

    def dump(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(AssetSnapshot, "model_dump", dump)
    result = projection(Query(tmp_path, "snapshots", at=NOW))
    assert calls == 1
    assert result["latest"]["default"]["balances"]["USDT"] == "999"
    assert len(result["curves"]["default"]) == 1000


def test_retained_snapshot_payload_charges_nested_balances_before_publication(tmp_path):
    from tests.test_dashboard_trading import make_snapshot

    directory = tmp_path / "portfolio" / "paper" / "default"
    directory.mkdir(parents=True)
    row = make_snapshot(timestamp=NOW).model_dump(mode="json")
    row["balances"] = {f"currency-{i}": "1.2345" for i in range(2000)}
    (directory / "snapshots.json").write_text(json.dumps([row]))
    with pytest.raises(ReadFailure, match="state_budget_exhausted"):
        projection(Query(tmp_path, "snapshots", at=NOW), Limits(state_bytes=100000))


def test_threshold_projection_is_lifetime_and_independent_of_window_group_budgets(
    tmp_path,
):
    from tests.test_dashboard_trading import _make_proposal

    directory = tmp_path / "proposals"
    directory.mkdir()
    for index, at in enumerate((NOW, NOW - timedelta(days=40))):
        proposal = _make_proposal(str(index)).model_copy(
            update={"created_at": at, "technique_name": f"strategy-{index}"}
        )
        record = ProposalRecord(
            proposal=proposal,
            decision="rejected",
            rejection_reason="composite 0.2000 below threshold 0.3000",
        )
        (directory / f"{index}.json").write_text(record.model_dump_json())
    result = projection(
        Query(tmp_path, "proposals", window="threshold", at=NOW), Limits(strategies=1)
    )
    assert result["threshold"] == 2 and "counts" not in result
    assert result["source_coverage"]["files"] == 2
    (directory / "old-damaged.json").write_text("broken")
    with pytest.raises(ReadFailure):
        projection(Query(tmp_path, "proposals", window="threshold", at=NOW))


def test_snapshot_missing_timestamp_keeps_first_validation_time_in_published_latest(
    tmp_path,
):
    from tests.test_dashboard_trading import make_snapshot

    directory = tmp_path / "portfolio" / "paper" / "default"
    directory.mkdir(parents=True)
    row = make_snapshot(timestamp=NOW).model_dump(mode="json")
    row.pop("timestamp")
    (directory / "snapshots.json").write_text(json.dumps([row]))
    result = projection(Query(tmp_path, "snapshots", at=NOW))
    latest = datetime.fromisoformat(
        result["latest"]["default"]["timestamp"].replace("Z", "+00:00")
    )
    curve = datetime.fromisoformat(result["curves"]["default"][0]["timestamp"])
    assert latest == curve


@pytest.mark.parametrize("hidden_kind", ["file", "directory"])
def test_fast_proposal_manifest_preserves_selected_members_and_generation_digest(
    tmp_path, hidden_kind
):
    from src.dashboard.sources import Manifest

    directory = tmp_path / "proposals"
    directory.mkdir()
    names = ["root.json", ".hidden.json", "one/child.json"]
    for name in names:
        path = directory / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("{}")
    for name in [
        "archive/old.json",
        "one/deeper/ignored.json",
        "folder.json/ignored.json",
        "one/.json",
    ]:
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not selected")
    if hidden_kind == "file":
        (directory / ".json").write_text("not selected")
    else:
        (directory / ".json").mkdir()
        (directory / ".json" / "child.json").write_text("{}")
        names.append(".json/child.json")
    (directory / "alias.json").symlink_to(directory / "root.json")
    names.append("alias.json")
    query = Query(tmp_path, "proposals").normalized()
    manifest = discover(query, Limits(), 12)
    expected = Manifest(Limits(), directory)
    for name in names:
        expected.add(directory / name, "object")
    expected.sort()
    assert manifest.digest() == expected.digest()
    assert [
        source.path.relative_to(directory).as_posix() for source in manifest.files
    ] == sorted(names)
    manifest.verify()
    path = directory / "root.json"
    old = path.stat()
    path.write_text("[]")
    import os

    os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns + 1000000))
    with pytest.raises(ReadFailure, match="source_changed"):
        manifest.verify()


def test_manifest_verification_releases_directory_handle_after_changed_source(
    tmp_path, monkeypatch
):
    import os

    from src.dashboard import sources

    if os.stat not in os.supports_dir_fd:
        pytest.skip("Directory-relative stat unsupported on this platform")
    write_events(tmp_path, [event("cycle_started", cid="c")])
    manifest = discover(Query(tmp_path, "activity"), Limits(), 12)
    (tmp_path / "runtime" / "activity.jsonl").write_text("changed\n")
    opened, closed = [], []
    original_open, original_close = sources.os.open, sources.os.close

    def tracked_open(*args, **kwargs):
        fd = original_open(*args, **kwargs)
        opened.append(fd)
        return fd

    def tracked_close(fd):
        closed.append(fd)
        original_close(fd)

    monkeypatch.setattr(sources.os, "open", tracked_open)
    monkeypatch.setattr(sources.os, "close", tracked_close)
    with pytest.raises(ReadFailure, match="source_changed"):
        manifest.verify()
    assert len(opened) == 1 and closed == opened


@pytest.mark.parametrize("equity", ["0", "-123.4500", "1E+100", "0." + "1" * 200])
def test_fixed_snapshot_charges_cover_recursive_measurement(tmp_path, equity):
    from src.dashboard.sources import Source
    from src.utils.bounded_read import Generation
    from tests.test_dashboard_trading import make_snapshot

    account = "계정🙂" * 8
    snapshot = make_snapshot(timestamp=NOW, quote_balance=equity)
    source = Source(
        tmp_path, "snapshots.json", Generation(1, 1, 1, 1), "array", account
    )
    budget = StateBudget(Limits())
    reducer = HistoryProjection(Query(tmp_path, "snapshots", at=NOW), budget)
    reducer.add_snapshot_json(snapshot.model_dump_json().encode(), source)
    assert reducer.latest_charges[account] >= budget.size(
        [account, reducer.latest[account], 0]
    )
    for point, charge in reducer.curves[account]:
        assert charge >= budget.size((point, 0))


def test_large_ignored_snapshot_field_uses_normalized_fallback_without_false_overflow(
    tmp_path,
):
    from tests.test_dashboard_trading import make_snapshot

    directory = tmp_path / "portfolio" / "paper" / "default"
    directory.mkdir(parents=True)
    row = make_snapshot(timestamp=NOW).model_dump(mode="json")
    row["ignored_legacy_context"] = "x" * 70000
    (directory / "snapshots.json").write_text(json.dumps([row]))
    result = projection(Query(tmp_path, "snapshots", at=NOW), Limits(state_bytes=8192))
    assert result["latest"]["default"] == make_snapshot(timestamp=NOW).model_dump(
        mode="json"
    )


@pytest.mark.parametrize("event_type", list(ActivityEventType))
def test_json_read_model_preserves_every_canonical_event_type_and_fields(event_type):
    from src.dashboard.projections import _ActivityReadEvent, _validate_activity_json

    original = event(
        event_type,
        at=NOW,
        cid="c",
        sub_account_id="one",
        reason="stale_quote_no_live_data",
        nested={"한글": [1, None, True]},
    )
    raw = original.model_dump_json()
    assert _validate_activity_json(raw).model_dump(
        mode="json"
    ) == ActivityEvent.model_validate_json(raw).model_dump(mode="json")
    assert set(_ActivityReadEvent.model_fields) == set(ActivityEvent.model_fields)


@pytest.mark.parametrize(
    "fields",
    [
        '"event_type":"monitor_pass"',
        '"event_type":"bad","event_type":"monitor_pass"',
        '"event_type":"monitor_pass","event_type":"bad"',
        '"event_type":null',
        '"event_type":1',
        '"event_type":"monitor_pass","message":null',
        '"event_type":"monitor_pass","details":[]',
        '"event_type":"monitor_pass","details":{"n":NaN}',
        '"event_type":"monitor_pass","schema_version":"1"',
    ],
)
def test_compiled_json_validation_preserves_canonical_coercion_and_rejection(fields):
    from pydantic import ValidationError

    from src.dashboard.projections import _validate_activity_json

    raw = '{"timestamp":"2026-10-25T00:00:00Z",' + fields + "}"

    def outcome(validate):
        try:
            model = validate(raw)
            return "valid", json.dumps(model.model_dump(mode="json"), sort_keys=True)
        except ValidationError as exc:
            reason = (
                "malformed_json"
                if any(r["type"] == "json_invalid" for r in exc.errors())
                else "invalid_record"
            )
            return "invalid", reason

    assert outcome(_validate_activity_json) == outcome(
        ActivityEvent.model_validate_json
    )

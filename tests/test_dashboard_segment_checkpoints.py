"""Restart/source mutation/fault parity of optional disposable checkpoints."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from src.dashboard.checkpoint_store import (
    CacheMiss,
    CheckpointStore,
    decode_state,
    encode_state,
)
from src.dashboard.projections import build_projection
from src.dashboard.read_models import Limits, Query
from src.runtime.activity_events import ActivityEvent, ActivityEventType

NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)


def project(
    query: Query, store: CheckpointStore | None = None, limits: Limits | None = None
) -> dict:
    return next(
        v
        for v in build_projection(
            query.normalized(), limits or Limits(), checkpoint_store=store
        )
        if v is not None
    )


def events(root: Path, name: str, rows: list[ActivityEvent]) -> Path:
    folder = root / "runtime"
    folder.mkdir(exist_ok=True)
    path = folder / name
    path.write_text("".join(e.model_dump_json() + "\n" for e in rows))
    return path


def event(
    kind: str, *, cid: str | None = None, at: datetime = NOW, **details: object
) -> ActivityEvent:
    return ActivityEvent(
        timestamp=at, event_type=kind, cycle_id=cid, details=details, message=kind
    )


def test_lossless_codec_and_rejection_of_executable_nonfinite_data() -> None:
    state = {
        "tuple": {("a", 1): {2, 3}},
        "decimal": Decimal("1.2300"),
        "time": NOW,
        "raw": b"abc",
        "float": -0.0,
    }
    assert decode_state(encode_state(state)) == state
    for value in [float("nan"), float("inf"), Decimal("NaN"), object()]:
        with pytest.raises(CacheMiss):
            encode_state({"value": value})
    with pytest.raises((ValueError, CacheMiss)):
        decode_state(b"pickle-data\n")


@pytest.mark.parametrize("scope", ["Aggregate", "one"])
def test_restart_activity_cross_file_companions_and_all_types(
    tmp_path: Path, scope: str
) -> None:
    rows = [
        event(
            k.value,
            cid="c",
            sub_account_id="one",
            proposal_id="p",
            gate_reason="daily_loss_kill_switch",
            cycle_id="fallback",
        )
        for k in ActivityEventType
    ]
    events(
        tmp_path,
        "activity.jsonl",
        [
            event("cycle_started", cid="c", at=NOW - timedelta(hours=1)),
            event(
                "risk_kill_switch_tripped",
                cid="split",
                proposal_id="split",
                sub_account_id="one",
            ),
        ],
    )
    events(
        tmp_path,
        "activity.2026-10.jsonl",
        rows
        + [
            event(
                "proposal_rejected",
                cid="split",
                proposal_id="split",
                sub_account_id="one",
            )
        ],
    )
    query = Query(tmp_path, "activity", scope=scope, at=NOW)
    expected = project(query)
    store = CheckpointStore(tmp_path)
    assert project(query, store) == expected
    assert list(store.base.glob("*.cachepack"))
    restarted = CheckpointStore(tmp_path)
    assert project(query, restarted) == expected
    assert restarted.hits == 2
    assert not list(store.base.glob("*.json")) and not list(store.base.glob("*.jsonl"))
    with patch(
        "src.dashboard.projections._reduce_activity_source",
        side_effect=AssertionError("canonical full scan on hit"),
    ):
        assert project(query, restarted) == expected


def test_membership_rebases_equal_timestamp_ordinals(tmp_path: Path) -> None:
    events(
        tmp_path,
        "activity.2026-09.jsonl",
        [
            event(
                "derivatives_data_degraded",
                exchange="x",
                symbol="x",
                series="funding",
                tag="old",
            )
        ],
    )
    query = Query(tmp_path, "activity", at=NOW)
    store = CheckpointStore(tmp_path)
    project(query, store)
    events(
        tmp_path,
        "activity.jsonl",
        [
            event(
                "derivatives_data_degraded",
                exchange="x",
                symbol="x",
                series="funding",
                tag="new",
            )
        ],
    )
    assert project(query, store) == project(query)
    assert store.hits >= 1


def test_corruption_and_unknown_files_fall_back_without_financial_change(
    tmp_path: Path,
) -> None:
    events(tmp_path, "activity.jsonl", [event("cycle_errored", cid="c")])
    query = Query(tmp_path, "activity", at=NOW)
    store = CheckpointStore(tmp_path)
    expected = project(query)
    assert project(query, store) == expected
    for pack in store.base.glob("*.cachepack"):
        pack.write_bytes(b"corrupt")
    assert project(query, CheckpointStore(tmp_path)) == expected
    (store.base / "index.idx").write_bytes(b"broken index")
    assert project(query, CheckpointStore(tmp_path)) == expected
    unknown = store.base / "operator-note"
    unknown.write_text("keep")
    assert project(query, CheckpointStore(tmp_path)) == expected
    assert unknown.read_text() == "keep"


def test_disk_floor_and_atomic_failure_are_optional_misses(tmp_path: Path) -> None:
    events(tmp_path, "activity.jsonl", [event("startup")])
    query = Query(tmp_path, "activity", at=NOW)
    store = CheckpointStore(tmp_path)
    expected = project(query)
    with patch(
        "src.dashboard.checkpoint_store.shutil.disk_usage",
        return_value=type("Disk", (), {"free": 0})(),
    ):
        assert project(query, store) == expected
    assert not store.base.exists()
    with patch.object(store, "_publish", side_effect=OSError("disk full")):
        assert project(query, store) == expected
    assert not list(store.base.glob("*.tmp"))


def test_store_quota_uses_packs_and_preserves_unknowns(tmp_path: Path) -> None:
    # Frequent source replacement exercises old and current key generations.
    path = events(tmp_path, "activity.jsonl", [event("startup")])
    query = Query(tmp_path, "activity", at=NOW)
    store = CheckpointStore(tmp_path, disk_bytes=128 * 1024, reserve_bytes=0)
    assert store.prepare(query.normalized())
    for i in range(25):
        path.write_text(event("startup", counter=i).model_dump_json() + "\n")
        assert project(query, store) == project(query)
        assert store._usage()[0] <= store.disk_bytes
        assert len(list(store.base.iterdir())) <= 64


def test_snapshot_whole_account_curve_and_missing_timestamp_exclusion(
    tmp_path: Path,
) -> None:
    from src.trading.portfolio import AssetSnapshot

    folder = tmp_path / "portfolio" / "paper" / "one"
    folder.mkdir(parents=True)
    path = folder / "snapshots.json"
    rows = [
        AssetSnapshot(
            mode="paper",
            quote_currency="USDT",
            timestamp=NOW + timedelta(seconds=i),
            balances={"USDT": Decimal(str(100 + i % 17))},
            unrealized_pnl=Decimal("0"),
        ).model_dump(mode="json")
        for i in range(4500)
    ]
    path.write_text(json.dumps(rows))
    query = Query(tmp_path, "snapshots", accounts=("one",), at=NOW)
    expected = project(query)
    store = CheckpointStore(tmp_path)
    assert project(query, store) == expected
    restarted = CheckpointStore(tmp_path)
    assert project(query, restarted) == expected
    assert restarted.hits == 1
    duplicate = replace(query, accounts=("one", "one"))
    assert project(duplicate, store) == project(duplicate)


def test_direct_service_does_not_create_derived_namespace(tmp_path: Path) -> None:
    from src.dashboard.data_service import DashboardDataService

    events(tmp_path, "activity.jsonl", [event("startup")])
    service = DashboardDataService()
    try:
        assert service.request(Query(tmp_path, "activity", at=NOW)).complete
    finally:
        service.close()
    assert not (tmp_path / ".dashboard-read-cache").exists()


@pytest.mark.parametrize("window", ["lifetime", "24h", "7d", "30d", "threshold"])
def test_proposal_checkpoint_window_groups_and_changed_file(
    tmp_path: Path, window: str
) -> None:
    from src.proposal.interaction import ProposalRecord
    from tests.test_dashboard_trading import _make_proposal

    directory = tmp_path / "proposals"
    directory.mkdir()
    for i, at in enumerate(
        [
            NOW - timedelta(days=40),
            NOW - timedelta(hours=24),
            NOW,
            NOW + timedelta(days=1),
        ]
    ):
        proposal = _make_proposal(str(i)).model_copy(
            update={
                "created_at": at,
                "technique_name": f"tech-{i}",
                "reasoning": "evidence " * 4096,
            }
        )
        record = ProposalRecord(
            proposal=proposal,
            decision="rejected",
            rejection_reason="composite 0.2000 below threshold 0.3000",
        )
        (directory / f"{i}.json").write_text(record.model_dump_json())
    query = Query(tmp_path, "proposals", window=window, at=NOW)
    expected = project(query)
    store = CheckpointStore(tmp_path)
    assert project(query, store) == expected
    restarted = CheckpointStore(tmp_path)
    assert project(query, restarted) == expected
    assert restarted.hits == 4
    replacement = ProposalRecord(
        proposal=_make_proposal("0").model_copy(update={"created_at": NOW}),
        decision="accepted",
        final_state="trade_opened",
    )
    (directory / "0.json").write_text(replacement.model_dump_json())
    assert project(query, restarted) == project(query)


def test_two_roots_global_budget_and_third_root_fallback(tmp_path: Path) -> None:
    store = CheckpointStore(tmp_path)
    for name in ["one", "two", "three"]:
        root = tmp_path / name
        root.mkdir()
        events(root, "activity.jsonl", [event("startup", name=name)])
        query = Query(root, "activity", at=NOW)
        assert project(query, store) == project(query)
    owner = json.loads((store.base / "producer.owner").read_text())
    assert len(owner["roots"]) == 2
    assert store._usage()[0] <= 64 * 1024 * 1024


def test_dynamic_timestamp_snapshot_never_persisted(tmp_path: Path) -> None:
    folder = tmp_path / "portfolio" / "paper" / "one"
    folder.mkdir(parents=True)
    (folder / "snapshots.json").write_text(
        json.dumps(
            [
                {
                    "mode": "paper",
                    "quote_currency": "USDT",
                    "balances": {"USDT": "1.2300"},
                }
            ]
        )
    )
    store = CheckpointStore(tmp_path)
    project(
        Query(tmp_path, "snapshots", accounts=("one",), at=NOW.replace(year=2099)),
        store,
    )
    assert not list(store.base.glob("*.cachepack"))


def test_symlink_cache_namespace_cannot_touch_other_files(tmp_path: Path) -> None:
    events(tmp_path, "activity.jsonl", [event("startup")])
    outside = tmp_path / "operator"
    outside.mkdir()
    note = outside / "note"
    note.write_text("keep")
    (tmp_path / ".dashboard-read-cache").symlink_to(outside, target_is_directory=True)
    query = Query(tmp_path, "activity", at=NOW)
    assert project(query, CheckpointStore(tmp_path)) == project(query)
    assert note.read_text() == "keep" and not (outside / "v1").exists()


def test_small_cache_budget_reserves_index_inside_existing_total(
    tmp_path: Path,
) -> None:
    from src.dashboard.data_service import DashboardDataService

    events(tmp_path, "activity.jsonl", [event("startup")])
    store = CheckpointStore(tmp_path)
    service = DashboardDataService(
        limits=replace(Limits(), cache_bytes=32 * 1024), checkpoint_store=store
    )
    try:
        result = service.request(Query(tmp_path, "activity", at=NOW))
        assert result.complete
        assert store.index_reservation == 8192
        assert service.stats()["cache_bytes"] <= 32768
    finally:
        service.close()


def test_full_physical_file_budget_does_not_create_an_extra_temp(
    tmp_path: Path,
) -> None:
    events(tmp_path, "activity.jsonl", [event("startup")])
    store = CheckpointStore(tmp_path)
    query = Query(tmp_path, "activity", at=NOW)
    assert project(query, store) == project(query)
    count = len(list(store.base.iterdir()))
    for i in range(64 - count):
        (store.base / f"operator-{i}").write_text("keep")
    path = tmp_path / "runtime" / "activity.jsonl"
    path.write_text(event("startup", changed=True).model_dump_json() + "\n")
    assert project(query, store) == project(query)
    assert len(list(store.base.iterdir())) == 64


def test_unsupported_lock_is_an_acceleration_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import builtins

    events(tmp_path, "activity.jsonl", [event("startup")])
    original = builtins.__import__

    def without_fcntl(name, *args, **kwargs):
        if name == "fcntl":
            raise ImportError("no POSIX locks")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_fcntl)
    query = Query(tmp_path, "activity", at=NOW)
    assert project(query, CheckpointStore(tmp_path)) == project(query)


def test_small_proposal_files_use_the_faster_canonical_path(tmp_path: Path) -> None:
    from src.proposal.interaction import ProposalRecord
    from tests.test_dashboard_trading import _make_proposal

    directory = tmp_path / "proposals"
    directory.mkdir()
    for i in range(5):
        (directory / f"{i}.json").write_text(
            ProposalRecord(proposal=_make_proposal(str(i))).model_dump_json()
        )
    query = Query(tmp_path, "proposals", at=NOW)
    store = CheckpointStore(tmp_path)
    assert project(query, store) == project(query)
    restarted = CheckpointStore(tmp_path)
    assert project(query, restarted) == project(query)
    assert restarted.hits == 0
    assert not list(store.base.glob("*.cachepack"))

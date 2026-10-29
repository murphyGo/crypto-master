"""Offline protocol observer contracts; no server or Fly workload is started."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts import observe_dashboard_protocol as observer


@pytest.fixture
def output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(
        observer,
        "args",
        argparse.Namespace(phase="offline", cadence=20, seconds=600),
        raising=False,
    )
    monkeypatch.setattr(observer, "OUT", tmp_path, raising=False)
    for name in ("observations", "warmup_observations", "health", "memory", "reason"):
        monkeypatch.setattr(observer, name, [])
    monkeypatch.setattr(observer, "pages", {})
    monkeypatch.setattr(observer, "cycles", {})
    monkeypatch.setattr(observer, "tracking", True)
    monkeypatch.setattr(observer, "stop", asyncio.Event())
    monkeypatch.setattr(observer, "admission_closed", asyncio.Event())
    return tmp_path


def elements(page: str) -> dict:
    rows = [
        {"kind": "metric", "label": label, "placeholder": False}
        for label in observer.METRIC_LABELS[page]
    ]
    for kind, count in observer.ELEMENT_COUNTS[page].items():
        if kind != "metric":
            rows.extend({"kind": kind} for _ in range(count))
    return dict(enumerate(rows))


@pytest.mark.parametrize(
    ("body", "section", "category"),
    [
        (
            "Runtime safety and activity: loading in the background. Refresh to check progress.",
            "activity",
            "pending",
        ),
        (
            "Runtime reconciliation: data could not be verified. Refresh to retry.",
            "activity",
            "unavailable",
        ),
        (
            "Trade ledger: last complete view at PRIVATE_TIME; current data is unavailable. Refresh to retry.",
            "ledger",
            "stale",
        ),
        (
            "Portfolio snapshots: data could not be verified.",
            "snapshots",
            "unavailable",
        ),
        ("Candidate evidence: loading in the background.", "candidates", "pending"),
        ("24h proposal funnel: loading in the background.", "proposals", "pending"),
        (
            "Threshold rejections: data could not be verified.",
            "proposals",
            "unavailable",
        ),
        (
            "/private/SECRET/account: data could not be verified. token=SECRET",
            "unknown",
            "unavailable",
        ),
        ("Unknown diagnostic token=SECRET and private/path", "unknown", "other"),
    ],
)
def test_alerts_retain_only_finite_classification(body, section, category):
    classified = observer.classify_alert(body)
    assert classified == {
        "section": section,
        "category": category,
        "incomplete": category != "other",
    }
    assert "SECRET" not in json.dumps(classified)
    assert "PRIVATE_TIME" not in json.dumps(classified)


@pytest.mark.parametrize("page", ["Home", "Trading"])
@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "wrong_label",
        "placeholder",
        "extra_table",
        "exception",
        "incomplete_alert",
        "missing_table",
        "duplicate_label",
    ],
)
def test_complete_requires_exact_shape_and_nonplaceholder_metrics(page, mutation):
    rows = elements(page)
    if mutation == "wrong_label":
        rows[0]["label"] = "unknown"
    elif mutation == "placeholder":
        rows[0]["placeholder"] = True
    elif mutation == "extra_table":
        rows[999] = {"kind": "table"}
    elif mutation == "exception":
        rows[999] = {"kind": "exception"}
    elif mutation == "incomplete_alert":
        rows[999] = {
            "kind": "alert",
            **observer.classify_alert("Trade ledger: data could not be verified."),
        }
    elif mutation == "missing_table":
        del rows[next(key for key, row in rows.items() if row["kind"] == "dataframe")]
    elif mutation == "duplicate_label":
        rows[0]["label"] = rows[1]["label"]
    assert observer.complete_data(page, rows) is (mutation == "none")


def test_unknown_page_never_qualifies():
    assert not observer.complete_data("unknown", elements("Home"))


def message(kind: str, **fields) -> SimpleNamespace:
    return SimpleNamespace(WhichOneof=lambda _: kind, **fields)


def alert_message(body: str):
    element = message("alert", alert=SimpleNamespace(body=body))
    return message(
        "delta",
        delta=message("new_element", new_element=element),
        metadata=SimpleNamespace(delta_path=[1]),
    )


@pytest.mark.parametrize("end", ["incomplete", "exception", "cancel"])
async def test_partial_request_preserves_alert_time_and_exactly_one_outcome(
    output, monkeypatch, end
):
    alert = alert_message(
        "Runtime safety and activity: data could not be verified. PRIVATE_BODY"
    )
    finished = message("script_finished", script_finished=0)
    monkeypatch.setattr(
        observer,
        "Forward",
        SimpleNamespace(
            FromString=lambda data: {b"alert": alert, b"finished": finished}[data]
        ),
    )
    client = observer.Client(1)
    client.send = AsyncMock()
    ending = (
        b"finished"
        if end == "incomplete"
        else (
            RuntimeError("PRIVATE_BODY")
            if end == "exception"
            else asyncio.CancelledError()
        )
    )
    client.ws = SimpleNamespace(recv=AsyncMock(side_effect=[b"alert", ending]))
    if end == "incomplete":
        row = await client.view("Home")
        assert (
            row["first_incomplete_script_finished_seconds"]
            >= row["first_incomplete_shell_seconds"]
            >= 0
        )
    else:
        with pytest.raises(
            RuntimeError if end == "exception" else asyncio.CancelledError
        ):
            await client.view("Home")
    starts = [
        json.loads(line)
        for line in (output / "offline-page-starts.jsonl").read_text().splitlines()
    ]
    outcomes = [
        json.loads(line)
        for line in (output / "offline-page-observations.jsonl")
        .read_text()
        .splitlines()
    ]
    assert len(starts) == len(outcomes) == 1
    row = outcomes[0]
    assert row["first_incomplete_shell_seconds"] >= 0
    assert row["alerts"] == [
        {"section": "activity", "category": "unavailable", "incomplete": True}
    ]
    assert len(row["alert_history"]) == 1
    assert (
        row["status"]
        == {
            "incomplete": "incomplete",
            "exception": "request_failed",
            "cancel": "cancelled_at_observation_boundary",
        }[end]
    )
    assert observer.reconcile_requests(starts, outcomes)["bijective"]
    assert "PRIVATE_BODY" not in json.dumps(row)


async def test_warmup_exception_is_retained_without_polluting_tracked_requests(
    output, monkeypatch
):
    monkeypatch.setattr(observer, "tracking", False)
    client = observer.Client("warmup")
    client._view = AsyncMock(side_effect=RuntimeError("PRIVATE_BODY"))
    with pytest.raises(RuntimeError):
        await client.view("Home")
    assert observer.observations == []
    assert len(observer.warmup_observations) == 1
    assert (output / "offline-warmup-page-starts.jsonl").is_file()
    raw = (output / "offline-warmup-page-observations.jsonl").read_text()
    assert json.loads(raw)["status"] == "request_failed"
    assert "PRIVATE_BODY" not in raw


async def test_pending_rerun_to_complete_retains_first_shell_and_alert_history(
    output, monkeypatch
):
    frames = [
        message(
            "auto_rerun",
            auto_rerun=SimpleNamespace(fragment_id="watcher", interval=0.5),
        ),
        alert_message("Trade ledger: loading in the background. PRIVATE_BODY"),
        message("script_finished", script_finished=0),
        message(
            "new_session",
            new_session=SimpleNamespace(app_pages=[], fragment_ids_this_run=[]),
        ),
    ]
    for index, label in enumerate(observer.METRIC_LABELS["Home"]):
        frames.append(
            message(
                "delta",
                delta=message(
                    "new_element",
                    new_element=message(
                        "metric", metric=SimpleNamespace(label=label, body="1")
                    ),
                ),
                metadata=SimpleNamespace(delta_path=[100 + index]),
            )
        )
    for index in range(4):
        frames.append(
            message(
                "delta",
                delta=message("new_element", new_element=message("arrow_data_frame")),
                metadata=SimpleNamespace(delta_path=[200 + index]),
            )
        )
    frames.append(message("script_finished", script_finished=0))
    encoded = [str(index).encode() for index in range(len(frames))]
    mapping = dict(zip(encoded, frames, strict=True))
    monkeypatch.setattr(
        observer, "Forward", SimpleNamespace(FromString=lambda data: mapping[data])
    )
    client = observer.Client(0)
    client.send = AsyncMock()
    client.ws = SimpleNamespace(recv=AsyncMock(side_effect=encoded))
    row = await client.view("Home")
    assert row["status"] == "complete"
    assert row["alerts"] == []
    assert row["incomplete_alerts"] == 0
    assert row["maximum_background_watchers"] == 1
    assert row["first_incomplete_shell_seconds"] >= 0
    assert (
        row["first_incomplete_script_finished_seconds"]
        >= row["first_incomplete_shell_seconds"]
    )
    assert row["alert_history"][0]["category"] == "pending"
    assert row["alert_history"][0]["section"] == "ledger"
    assert len(observer.observations) == 1
    assert "PRIVATE_BODY" not in json.dumps(row)


def test_request_reconciliation_rejects_equal_counts_with_wrong_or_duplicate_keys():
    first = {"started_at": "a", "client": 0, "page": "Home", "status": "complete"}
    second = {**first, "started_at": "b"}
    assert not observer.reconcile_requests([first, second], [first, first])["bijective"]
    assert not observer.reconcile_requests([first, first], [first, first])["bijective"]
    report = observer.reconcile_requests(
        [first, second], [first, {**second, "status": "incomplete"}]
    )
    assert report["bijective"]
    assert report["status_counts"] == {"complete": 1, "incomplete": 1}


async def test_timeout_reconnects_before_next_request_and_retains_both_outcomes(
    output, monkeypatch
):
    old = SimpleNamespace(recv=AsyncMock(return_value=b"old"), close=AsyncMock())
    fresh = SimpleNamespace(
        recv=AsyncMock(side_effect=[b"alert", b"finished"]), close=AsyncMock()
    )
    client = observer.Client(1)
    client.ws = old
    client.send = AsyncMock()
    monkeypatch.setattr(
        observer,
        "Forward",
        SimpleNamespace(
            FromString=lambda raw: {
                b"alert": alert_message("Trade ledger: data could not be verified."),
                b"finished": message("script_finished", script_finished=0),
            }[raw]
        ),
    )

    async def connect():
        old.close.assert_awaited_once()
        client.ws = fresh

    client._connect = AsyncMock(side_effect=connect)
    first = await client.view("Home", timeout=0)
    second = await client.view("Trading")
    assert first["status"] == "timeout"
    assert second["status"] == "incomplete"
    assert second["reconnected_after_timeout"]
    client._connect.assert_awaited_once()
    old.recv.assert_not_awaited()
    assert second["alerts"][0]["section"] == "ledger"
    starts = [
        json.loads(line)
        for line in (output / "offline-page-starts.jsonl").read_text().splitlines()
    ]
    assert observer.reconcile_requests(starts, observer.observations)["bijective"]
    assert len(observer.observations) == 2


def test_successful_only_p95_does_not_hide_incomplete_request(output, monkeypatch):
    start = datetime(2026, 10, 26, tzinfo=timezone.utc)
    rows = [
        {
            "started_at": str(i),
            "client": i % 4,
            "page": page,
            "status": "complete",
            "seconds": 0.1,
        }
        for i, page in enumerate(["Home", "Trading"] * 20)
    ]
    rows[0]["status"] = "incomplete"
    monkeypatch.setattr(observer, "observations", rows)
    (output / "offline-page-starts.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n"
    )
    summary = observer.summarize(start, start + timedelta(seconds=600), 0, final=True)
    assert summary["pages"]["Home"]["complete_seconds_p95"] == 0.1
    assert not summary["warm_page_p95_2s_pass"]
    assert summary["every_start_has_outcome"]
    assert summary["request_reconciliation"]["status_counts"]["incomplete"] == 1
    assert summary["final"]
    assert not summary["original_1024_mib_guest_qualification"]


def test_errored_complete_cycle_is_retained_and_not_replaced_by_later_clean_cycle(
    output, monkeypatch
):
    start = datetime(2026, 10, 26, tzinfo=timezone.utc)
    first = {
        "cycle_started": start + timedelta(seconds=10),
        "cycle_errored": start + timedelta(seconds=20),
        "cycle_completed": start + timedelta(seconds=30),
    }
    clean = {
        "cycle_started": start + timedelta(seconds=50),
        "cycle_completed": start + timedelta(seconds=60),
    }
    monkeypatch.setattr(observer, "cycles", {"first": first, "later": clean})
    assert observer.full_cycle(start, start + timedelta(seconds=600)) == "first"
    summary = observer.summarize(start, start + timedelta(seconds=600), 0)
    assert summary["engine_full_cycle"] == "first"
    assert summary["minimum_duration_and_cycle_observed"]
    assert summary["engine_full_cycle_error_seen"]
    assert not summary["engine_continuity_pass"]
    assert summary["engine_cycle_errors"] == [
        {"cycle_id": "first", "timestamp": first["cycle_errored"].isoformat()}
    ]


def test_clean_complete_cycle_does_not_hide_other_observed_cycle_error(
    output, monkeypatch
):
    start = datetime(2026, 10, 26, tzinfo=timezone.utc)
    monkeypatch.setattr(
        observer,
        "cycles",
        {
            "clean": {
                "cycle_started": start + timedelta(seconds=10),
                "cycle_completed": start + timedelta(seconds=20),
            },
            "incomplete": {"cycle_errored": start + timedelta(seconds=30)},
        },
    )
    summary = observer.summarize(start, start + timedelta(seconds=600), 0)
    assert summary["engine_full_cycle"] == "clean"
    assert not summary["engine_full_cycle_error_seen"]
    assert not summary["engine_continuity_pass"]


@pytest.mark.parametrize(
    ("began_seconds", "completed_seconds"),
    [(-1, 20), (610, 620), (10, 601), (30, 20)],
    ids=["prewindow-start", "future-cycle", "future-terminal", "inverted-times"],
)
def test_cycle_must_fit_observed_window_but_its_error_remains_fatal(
    output, monkeypatch, began_seconds, completed_seconds
):
    start = datetime(2026, 10, 26, tzinfo=timezone.utc)
    end = start + timedelta(seconds=600)
    error_at = start + timedelta(seconds=50)
    monkeypatch.setattr(
        observer,
        "cycles",
        {
            "invalid": {
                "cycle_started": start + timedelta(seconds=began_seconds),
                "cycle_completed": start + timedelta(seconds=completed_seconds),
                "cycle_errored": error_at,
            }
        },
    )
    assert observer.full_cycle(start, end) is None
    summary = observer.summarize(start, end, 0)
    assert summary["engine_full_cycle"] is None
    assert not summary["minimum_duration_and_cycle_observed"]
    assert not summary["engine_continuity_pass"]
    assert summary["engine_cycle_errors"] == [
        {"cycle_id": "invalid", "timestamp": error_at.isoformat()}
    ]


def test_cycle_at_both_observation_boundaries_is_included(output, monkeypatch):
    start = datetime(2026, 10, 26, tzinfo=timezone.utc)
    end = start + timedelta(seconds=600)
    monkeypatch.setattr(
        observer,
        "cycles",
        {"boundary": {"cycle_started": start, "cycle_completed": end}},
    )
    assert observer.full_cycle(start, end) == "boundary"
    summary = observer.summarize(start, end, 0)
    assert summary["minimum_duration_and_cycle_observed"]
    assert summary["engine_continuity_pass"]
    assert not summary["engine_cycle_errors"]


def options(path: Path, **changes):
    values = {
        "output_dir": path,
        "phase": "new-run",
        "seconds": 600,
        "max_seconds": 2100,
        "cadence": 20,
    }
    return argparse.Namespace(**(values | changes))


def test_output_directory_is_exclusively_created_and_never_appended(tmp_path):
    output = tmp_path / "new"
    assert observer.prepare_output(options(output)) == output
    marker = output / "prior-evidence"
    marker.write_text("unchanged")
    with pytest.raises(FileExistsError):
        observer.prepare_output(options(output, phase="different"))
    assert marker.read_text() == "unchanged"


@pytest.mark.parametrize(
    "changes",
    [
        {"phase": "../escape"},
        {"phase": "bad/name"},
        {"seconds": 0},
        {"max_seconds": 599},
        {"cadence": float("nan")},
        {"cadence": 0},
    ],
)
def test_invalid_run_configuration_does_not_create_output(tmp_path, changes):
    output = tmp_path / "new"
    with pytest.raises(ValueError):
        observer.prepare_output(options(output, **changes))
    assert not output.exists()


def test_import_does_not_parse_cli_read_descriptor_or_start_external_work():
    code = """
import asyncio, pathlib, subprocess, sys
def forbidden(*args, **kwargs):
    raise AssertionError('external work during import')
pathlib.Path.read_bytes = forbidden
pathlib.Path.mkdir = forbidden
asyncio.run = forbidden
subprocess.Popen = forbidden
sys.argv = ['observer', '--invalid-option']
import scripts.observe_dashboard_protocol
print('IMPORT_SAFE')
"""
    result = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    )
    assert result.stdout.strip() == "IMPORT_SAFE"

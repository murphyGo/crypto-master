"""Legacy source compatibility and bounded runtime-reader lifecycle contracts."""

from __future__ import annotations

import asyncio
import gc
import threading
import time
import weakref
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import src.runtime.safety_inputs as reader
from src.runtime.activity_events import ActivityEvent, ActivityEventType
from src.runtime.activity_log import ActivityLog
from src.runtime.gate_reason import GateReason
from src.runtime.safety_inputs import (
    SafetyReadLimits,
    SafetyReadService,
    SafetyReadUnavailable,
)
from src.runtime.safety_score import (
    compute_runtime_safety_score,
    inputs_from_recent_activity_events,
)

NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


def event(kind: str = "monitor_errored", **kwargs: object) -> ActivityEvent:
    return ActivityEvent(timestamp=NOW, event_type=kind, **kwargs)


def row(kind: str = "monitor_errored", **kwargs: object) -> bytes:
    return event(kind, **kwargs).model_dump_json().encode()


@pytest.fixture
def log(tmp_path: Path) -> ActivityLog:
    return ActivityLog(tmp_path / "activity.jsonl")


@pytest.fixture
def service() -> SafetyReadService:
    value = SafetyReadService(utc_clock=lambda: NOW)
    yield value
    value.close()


async def settled(service: SafetyReadService) -> None:
    deadline = time.monotonic() + 2
    while service._job is not None:
        assert time.monotonic() < deadline
        await asyncio.sleep(0.001)


async def entered(signal: threading.Event) -> None:
    deadline = time.monotonic() + 2
    while not signal.is_set():
        assert time.monotonic() < deadline
        await asyncio.sleep(0.001)


@pytest.mark.parametrize("block_size", [1, 2, 17, 64 * 1024])
async def test_legacy_text_parser_and_unterminated_final_row(
    log: ActivityLog, block_size: int
) -> None:
    payload = (
        b"\r\n  \r\n"
        + "\u2003".encode()
        + row("monitor_errored")
        + "\u2003".encode()
        + b"\r\n{broken\r"
        + b'{"event_type":"unknown"}\n'
        + row("scan_errored")
        + b"\r"
        + row("position_open_errored")
    )
    log.path.write_bytes(payload)
    expected = compute_runtime_safety_score(
        inputs_from_recent_activity_events(log.read_all(), now=NOW)
    )
    service = SafetyReadService(
        limits=SafetyReadLimits(block_bytes=block_size), utc_clock=lambda: NOW
    )
    try:
        result = await service.evaluate(log, now=NOW)
    finally:
        service.close()
    assert result.score == expected
    assert result.bytes_read == len(payload)
    assert result.evaluated_at == NOW
    assert result.diagnostics["rows_decoded"] == 3
    assert result.diagnostics["json_skips"] == 1
    assert result.diagnostics["model_skips"] == 1


async def test_retention_legacy_plus_newest_n_and_no_filename_time_filter(
    log: ActivityLog, service: SafetyReadService
) -> None:
    log._rotator.retention_months = 2
    log.path.write_bytes(row())
    parent = log.path.parent
    (parent / "activity.2026-01.jsonl").write_bytes(row("liquidated"))
    # Invalid calendar months still match the legacy filename contract.
    (parent / "activity.2026-98.jsonl").write_bytes(row("scan_errored"))
    (parent / "activity.2026-99.jsonl").write_bytes(row("position_open_errored"))
    (parent / "activity.invalid.jsonl").write_bytes(b"[]")
    expected = compute_runtime_safety_score(
        inputs_from_recent_activity_events(log.read_all(), now=NOW)
    )
    result = await service.evaluate(log, now=NOW)
    assert result.score == expected
    assert result.diagnostics["files_read"] == 3


async def test_old_filename_dynamic_timestamp_reparsed_each_call(
    log: ActivityLog, service: SafetyReadService, monkeypatch: pytest.MonkeyPatch
) -> None:
    (log.path.parent / "activity.2000-01.jsonl").write_bytes(
        b'{"event_type":"monitor_errored"}'
    )
    # The model's default factory is evaluated at validation, even in old files.
    result = await service.evaluate(log, now=NOW)
    assert result.diagnostics["rows_decoded"] == 1
    again = await service.evaluate(log, [], now=NOW)
    assert again.diagnostics["rows_decoded"] == 1
    assert again.bytes_read == result.bytes_read > 0


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        (b"\xff", "safety_invalid_utf8"),
        (b"[]", "safety_nonobject_row"),
        (b"null", "safety_nonobject_row"),
        (b"1", "safety_nonobject_row"),
    ],
)
async def test_hard_parse_failure_has_no_partial_score_or_worker_cause(
    log: ActivityLog, service: SafetyReadService, payload: bytes, reason: str
) -> None:
    log.path.write_bytes(row("liquidated") + b"\n" + payload)
    with pytest.raises(SafetyReadUnavailable) as caught:
        await service.evaluate(log, now=NOW)
    failure = caught.value
    assert failure.reason == reason
    assert failure.bytes_read == log.path.stat().st_size
    assert failure.__context__ is None
    assert failure.__cause__ is None
    assert str(log.path) not in str(failure)
    assert service._job is None


async def test_utf8_bom_is_legacy_json_skip_not_accepted_record(
    log: ActivityLog, service: SafetyReadService
) -> None:
    log.path.write_bytes(b"\xef\xbb\xbf" + row())
    result = await service.evaluate(log, now=NOW)
    assert result.diagnostics["json_skips"] == 1
    assert result.diagnostics["rows_decoded"] == 0


@pytest.mark.parametrize("mutation", ["append", "truncate", "replace", "membership"])
async def test_source_generation_and_membership_changes_discard_result(
    log: ActivityLog,
    service: SafetyReadService,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    log.path.write_bytes(row())
    original = reader.SafetyAccumulator.add
    changed = False

    def mutate(accumulator: object, item: ActivityEvent) -> None:
        nonlocal changed
        original(accumulator, item)
        if changed:
            return
        changed = True
        if mutation == "append":
            with log.path.open("ab") as handle:
                handle.write(b"\n" + row("liquidated"))
        elif mutation == "truncate":
            log.path.write_bytes(b"")
        elif mutation == "replace":
            replacement = log.path.parent / "replacement"
            replacement.write_bytes(row())
            replacement.replace(log.path)
        else:
            (log.path.parent / "activity.2026-10.jsonl").write_bytes(row())

    monkeypatch.setattr(reader.SafetyAccumulator, "add", mutate)
    with pytest.raises(SafetyReadUnavailable, match="safety_source_changed"):
        await service.evaluate(log, now=NOW)


async def test_publication_rechecks_readability_even_for_empty_file(
    log: ActivityLog, service: SafetyReadService, monkeypatch: pytest.MonkeyPatch
) -> None:
    log.path.write_bytes(b"")
    original = Path.open
    calls = 0

    def deny_second_open(path: Path, *args: object, **kwargs: object) -> object:
        nonlocal calls
        if path == log.path:
            calls += 1
            if calls == 2:
                raise PermissionError("private source contents")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_second_open)
    with pytest.raises(SafetyReadUnavailable, match="safety_source_unreadable"):
        await service.evaluate(log, now=NOW)
    assert calls == 2


@pytest.mark.parametrize("failure", ["row", "state", "parse", "bytes"])
async def test_failure_closes_source_handle(
    log: ActivityLog, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    log.path.write_bytes(b"[]" if failure == "parse" else row() + b"\n" + row())
    limits = SafetyReadLimits(
        row_bytes=8 if failure == "row" else reader.MiB,
        state_bytes=1 if failure == "state" else 16 * reader.MiB,
    )
    service = SafetyReadService(limits=limits, utc_clock=lambda: NOW)
    handles = []
    original = Path.open

    def tracked(path: Path, *args: object, **kwargs: object) -> object:
        value = original(path, *args, **kwargs)
        if path == log.path:
            handles.append(value)
        return value

    monkeypatch.setattr(Path, "open", tracked)
    try:
        with pytest.raises(SafetyReadUnavailable):
            await service.evaluate(
                log, now=NOW, max_bytes=1 if failure == "bytes" else 10000
            )
    finally:
        service.close()
    assert all(handle.closed for handle in handles)
    if failure != "state":
        assert handles


async def test_discovery_manifest_cap_refuses_before_read(
    log: ActivityLog, monkeypatch: pytest.MonkeyPatch
) -> None:
    log.path.write_bytes(row())
    service = SafetyReadService(
        limits=SafetyReadLimits(manifest_bytes=1024), utc_clock=lambda: NOW
    )
    try:
        with pytest.raises(
            SafetyReadUnavailable, match="safety_manifest_limit"
        ) as caught:
            await service.evaluate(log, now=NOW)
        assert caught.value.bytes_read == 0
    finally:
        service.close()


async def test_extra_limits_before_admission_and_no_thread_or_disk(
    log: ActivityLog,
) -> None:
    service = SafetyReadService(
        limits=SafetyReadLimits(extra_count=1, extra_bytes=4096), utc_clock=lambda: NOW
    )
    try:
        for extras in ([event(), event()], [event(message="x" * 4096)]):
            with pytest.raises(SafetyReadUnavailable, match="safety_extra_limit"):
                await service.evaluate(log, extras, now=NOW)
        cyclic: dict[str, object] = {}
        cyclic["self"] = cyclic
        with pytest.raises(SafetyReadUnavailable, match="safety_extra_unsupported"):
            await service.evaluate(log, [event(details=cyclic)], now=NOW)
        assert service._thread is None
    finally:
        service.close()


async def test_extra_container_is_owned_and_keys_not_normalized(
    log: ActivityLog, service: SafetyReadService
) -> None:
    shared_nan = float("nan")
    extras = [
        event(
            "risk_kill_switch_tripped",
            details={
                "cycle_id": shared_nan,
                "gate_reason": GateReason.DAILY_LOSS_KILL_SWITCH,
            },
        ),
        event(
            "risk_kill_switch_tripped",
            details={
                "cycle_id": shared_nan,
                "gate_reason": GateReason.DAILY_LOSS_KILL_SWITCH.value,
            },
        ),
        event(
            "risk_kill_switch_tripped",
            details={
                "cycle_id": True,
                "gate_reason": ActivityEventType.MONITOR_ERRORED,
            },
        ),
        event(
            "risk_kill_switch_tripped",
            details={
                "cycle_id": 1.0,
                "gate_reason": ActivityEventType.MONITOR_ERRORED.value,
            },
        ),
    ]
    expected = compute_runtime_safety_score(
        inputs_from_recent_activity_events(extras, now=NOW)
    )
    result = await service.evaluate(log, extras, now=NOW)
    assert result.score == expected
    assert result.diagnostics["distinct_keys"] == 2
    assert result.diagnostics["state_bytes"] > reader._extra_charge(
        extras, 2 * reader.MiB
    )


async def test_disk_io_only_on_worker_and_no_read_all(
    log: ActivityLog, service: SafetyReadService, monkeypatch: pytest.MonkeyPatch
) -> None:
    log.path.write_bytes(row())
    original_stat, original_open, original_scandir = (
        Path.stat,
        Path.open,
        reader.os.scandir,
    )
    loop_thread = threading.get_ident()
    identities: set[int] = set()

    def off_loop(function: object) -> object:
        def wrapped(*args: object, **kwargs: object) -> object:
            identity = threading.get_ident()
            assert identity != loop_thread
            identities.add(identity)
            return function(*args, **kwargs)

        return wrapped

    monkeypatch.setattr(log, "read_all", lambda: pytest.fail("archive reader used"))
    monkeypatch.setattr(Path, "stat", off_loop(original_stat))
    monkeypatch.setattr(Path, "open", off_loop(original_open))
    monkeypatch.setattr(reader.os, "scandir", off_loop(original_scandir))
    await service.evaluate(log, now=NOW)
    await service.evaluate(log, [], now=NOW)
    assert len(identities) == 1
    assert service._thread is not None and service._thread.daemon


@pytest.mark.parametrize("end", ["timeout", "cancel", "shutdown"])
async def test_late_result_quarantine_no_queue_no_replacement_thread(
    log: ActivityLog,
    service: SafetyReadService,
    monkeypatch: pytest.MonkeyPatch,
    end: str,
) -> None:
    started, release = threading.Event(), threading.Event()
    original = service._read

    def blocked(job: object) -> object:
        started.set()
        assert release.wait(2)
        return original(job)

    monkeypatch.setattr(service, "_read", blocked)
    task = asyncio.create_task(service.evaluate(log, now=NOW, max_seconds=0.05))
    try:
        await entered(started)
        worker = service._thread
        with pytest.raises(SafetyReadUnavailable, match="safety_reader_busy"):
            await service.evaluate(log, now=NOW)
        if end == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        elif end == "shutdown":
            begin = time.monotonic()
            service.close()
            assert time.monotonic() - begin < 0.05
        else:
            with pytest.raises(
                SafetyReadUnavailable, match="safety_read_timeout"
            ) as caught:
                await task
            assert caught.value.bytes_read == 2 * 1024 * reader.MiB
        assert service._job is not None
        with pytest.raises(SafetyReadUnavailable, match="safety_reader_(busy|closed)"):
            await service.evaluate(log, now=NOW)
        assert service._thread is worker
        release.set()
        await settled(service)
        if end == "shutdown":
            with pytest.raises(SafetyReadUnavailable, match="safety_read_cancelled"):
                await task
        else:
            await service.evaluate(log, now=NOW)
            assert service._thread is worker
    finally:
        release.set()
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


@pytest.mark.parametrize("offset", [-1, 31])
async def test_utc_reversal_or_old_evaluation_never_publishes(
    log: ActivityLog, offset: int
) -> None:
    service = SafetyReadService(utc_clock=lambda: NOW + timedelta(seconds=offset))
    try:
        with pytest.raises(SafetyReadUnavailable, match="safety_evaluation_expired"):
            await service.evaluate(log, now=NOW)
    finally:
        service.close()


async def test_idle_daemon_does_not_retain_extra_models(
    log: ActivityLog, service: SafetyReadService
) -> None:
    extra = event()
    reference = weakref.ref(extra)
    await service.evaluate(log, [extra], now=NOW)
    del extra
    # Concurrent-future delivery callbacks must first leave the event-loop queue.
    await asyncio.sleep(0)
    gc.collect()
    assert reference() is None


async def test_shared_service_lifecycle_is_lazy_and_never_reopens(
    log: ActivityLog, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(reader, "_shared_service", None)
    monkeypatch.setattr(reader, "_shared_closed", False)
    reader.shutdown_shared_safety_read_service()
    assert reader._shared_service is None
    service = reader.get_safety_read_service()
    assert reader.get_safety_read_service() is service
    assert service._thread is None
    with pytest.raises(SafetyReadUnavailable, match="safety_reader_closed"):
        await service.evaluate(log, now=NOW)
    assert service._thread is None


@pytest.mark.parametrize(
    "limit",
    [
        {"block_bytes": 0},
        {"row_bytes": 2 * reader.MiB},
        {"extra_count": True},
        {"distinct_keys": 50_001},
    ],
)
def test_injected_limits_can_only_lower_hard_caps(limit: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="invalid safety read limit"):
        SafetyReadLimits(**limit)


def test_failure_reasons_allowlist_does_not_retain_freeform_text() -> None:
    error = SafetyReadUnavailable("/private/source credentials=secret")
    assert error.reason == "safety_read_failed"
    assert error.args == ("safety_read_failed",)


async def test_key_limit_closes_mid_stream_and_never_returns_partial(
    log: ActivityLog, monkeypatch: pytest.MonkeyPatch
) -> None:
    log.path.write_bytes(
        b"\n".join(row("risk_kill_switch_tripped", cycle_id=str(i)) for i in range(3))
    )
    service = SafetyReadService(
        limits=SafetyReadLimits(distinct_keys=1), utc_clock=lambda: NOW
    )
    handles = []
    original = Path.open

    def tracked(path: Path, *args: object, **kwargs: object) -> object:
        handle = original(path, *args, **kwargs)
        handles.append(handle)
        return handle

    monkeypatch.setattr(Path, "open", tracked)
    try:
        with pytest.raises(SafetyReadUnavailable, match="safety_key_limit"):
            await service.evaluate(log, now=NOW)
    finally:
        service.close()
    assert handles and all(handle.closed for handle in handles)


async def test_source_byte_budget_counts_actual_blocks(
    log: ActivityLog,
) -> None:
    payload = row() + b"\n" + row()
    log.path.write_bytes(payload)
    service = SafetyReadService(
        limits=SafetyReadLimits(block_bytes=16), utc_clock=lambda: NOW
    )
    try:
        with pytest.raises(
            SafetyReadUnavailable, match="safety_read_byte_limit"
        ) as caught:
            await service.evaluate(log, now=NOW, max_bytes=20)
        assert caught.value.bytes_read == 16
    finally:
        service.close()


async def test_missing_source_is_empty_without_creating_directory(
    tmp_path: Path, service: SafetyReadService
) -> None:
    log = ActivityLog(tmp_path / "missing" / "activity.jsonl")
    result = await service.evaluate(log, now=NOW)
    assert result.score.score == 100
    assert result.bytes_read == 0
    assert result.diagnostics["files_read"] == 0
    assert not log.path.parent.exists()

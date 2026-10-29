"""Finite shared recovery revalidates changing files without weakening reads."""

import json
import threading
import time
import weakref
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.dashboard import availability, data_service, projections
from src.dashboard.checkpoint_store import CheckpointStore
from src.dashboard.data_service import DashboardDataService, ErrorToken
from src.dashboard.read_models import Limits, Query
from src.runtime.activity_events import ActivityEvent
from src.trading.portfolio import AssetSnapshot
from src.utils.bounded_read import ReadFailure

NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)


class Clock:
    value = 100.0

    def advance(self, service, seconds):
        with service._condition:
            self.value += seconds
            service._condition.notify_all()


@pytest.fixture
def clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(
        data_service,
        "time",
        SimpleNamespace(monotonic=lambda: clock.value, sleep=time.sleep),
    )
    return clock


def wait_for(service, predicate):
    with service._condition:
        assert service._condition.wait_for(predicate, timeout=3)


def canonical(query):
    return next(
        item
        for item in projections.build_projection(query.normalized(), Limits())
        if item is not None
    )


def measure_attempts(service):
    build = service._builder
    elapsed = []
    origin = time.monotonic()

    def measured(query, limits):
        start = time.monotonic()
        try:
            yield from build(query, limits)
        finally:
            end = time.monotonic()
            elapsed.append(
                {"start": start - origin, "end": end - origin, "seconds": end - start}
            )

    service._builder = measured
    return elapsed


@pytest.mark.parametrize("checkpoints", [False, True])
def test_real_activity_change_recovers_from_cached_generation(
    tmp_path, monkeypatch, checkpoints, record_property
):
    path = tmp_path / "runtime" / "activity.jsonl"
    path.parent.mkdir()
    event = ActivityEvent(timestamp=NOW, event_type="cycle_started", cycle_id="one")
    path.write_text(event.model_dump_json() + "\n")
    query = Query(tmp_path, "activity", at=NOW)
    store = CheckpointStore(tmp_path) if checkpoints else None
    if store:
        assert store.prepare(query.normalized())
    service = DashboardDataService(checkpoint_store=store)
    try:
        original = service.request(query)
        assert original.complete
        service._cache[query.normalized()].evaluated -= 3
        verify = projections.discover(query.normalized(), Limits(), 12).__class__.verify
        changed = False

        def mutate_once(manifest):
            nonlocal changed
            if not changed:
                changed = True
                with path.open("a") as handle:
                    handle.write(
                        event.model_copy(update={"cycle_id": "two"}).model_dump_json()
                        + "\n"
                    )
            verify(manifest)

        monkeypatch.setattr("src.dashboard.sources.Manifest.verify", mutate_once)
        elapsed = measure_attempts(service)
        recovered = service.request(query)
        assert changed and recovered.complete
        assert recovered.data() == canonical(query)
        assert recovered.payload != original.payload
        assert len(elapsed) == 2
        record_property("attempt_timings", json.dumps(elapsed))
        record_property("checkpoint_store_prepared", checkpoints)
    finally:
        service.close()


@pytest.mark.parametrize("checkpoints", [False, True])
def test_real_snapshot_replacements_recover_on_third_attempt(
    tmp_path, monkeypatch, checkpoints, record_property
):
    path = tmp_path / "portfolio" / "paper" / "default" / "snapshots.json"
    path.parent.mkdir(parents=True)

    def replace_snapshot(value):
        snapshot = AssetSnapshot(
            timestamp=NOW, mode="paper", quote_currency="USDT", balances={"USDT": value}
        )
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps([snapshot.model_dump(mode="json")]))
        temporary.replace(path)

    replace_snapshot("1")
    verify = projections.discover(
        Query(tmp_path, "snapshots").normalized(), Limits(), 12
    ).__class__.verify
    changes = 0

    def mutate_twice(manifest):
        nonlocal changes
        if changes < 2:
            changes += 1
            replace_snapshot(str(changes + 1))
        verify(manifest)

    monkeypatch.setattr("src.dashboard.sources.Manifest.verify", mutate_twice)
    query = Query(tmp_path, "snapshots", at=NOW)
    store = CheckpointStore(tmp_path) if checkpoints else None
    if store:
        assert store.prepare(query.normalized())
    service = DashboardDataService(checkpoint_store=store)
    try:
        elapsed = measure_attempts(service)
        result = service.request(query)
        assert changes == 2 and result.complete
        assert result.data() == canonical(query)
        assert not service._errors
        assert len(elapsed) == 3
        record_property("attempt_timings", json.dumps(elapsed))
        record_property("checkpoint_store_prepared", checkpoints)
    finally:
        service.close()


def test_four_clients_keep_one_future_and_progress_through_retry(tmp_path):
    entered, release = threading.Event(), threading.Event()
    calls = 0

    def build(query, limits):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            assert release.wait(3)
            raise ReadFailure("source_changed")
        yield {"attempt": calls}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity")
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            pending = list(pool.map(lambda _: service.request(query, wait=0), range(4)))
        assert entered.wait(2)
        future = service._jobs[query.normalized()]
        signals = [result.progress for result in pending]
        assert all(signal is not None and not signal() for signal in signals)
        assert service.stats()["admitted"] == 1
        release.set()
        result = future.result(timeout=3)
        assert result.complete and result.data() == {"attempt": 2}
        assert calls == 2
        assert all(signal() for signal in signals)
        assert not service._job_progress
    finally:
        release.set()
        service.close()


def test_delayed_retry_yields_to_ready_sibling_and_releases_iterator(tmp_path, clock):
    calls, closed, references = [], [], []

    class PartialState:
        pass

    def build(query, limits):
        calls.append(query.kind)
        if query.kind == "activity" and calls.count("activity") == 1:
            state = PartialState()
            references.append(weakref.ref(state))
            try:
                raise ReadFailure("source_changed")
            finally:
                closed.append(query.kind)
        yield {"kind": query.kind}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity").normalized()
    try:
        pending = service.request(query, wait=0)
        wait_for(service, lambda: service._recovery[query].recovering)
        assert closed == ["activity"] and references[0]() is None
        assert pending.progress is not None and not pending.progress()
        assert service.request(Query(tmp_path, "ledger")).complete
        assert calls == ["activity", "ledger"]
        assert service.stats()["admitted"] == 1
        clock.advance(service, 0.25)
        assert service.request(query).complete
        assert calls == ["activity", "ledger", "activity"]
        assert pending.progress()
    finally:
        service.close()


def test_persistent_churn_spaces_episodes_and_preserves_manual_aba(
    tmp_path, clock, monkeypatch
):
    monkeypatch.setattr(data_service, "_RETRY_DELAYS", (0.0, 0.0))
    calls = 0

    def build(query, limits):
        nonlocal calls
        calls += 1
        raise ReadFailure("source_changed")
        yield

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity")
    try:
        first = service.request(query)
        assert calls == 3 and first.reason == "source_changed"
        assert first.retry is not None and first.progress is None
        clock.advance(service, 29.999)
        for _ in range(4):
            assert service.request(query).reason == "source_changed"
        assert calls == 3
        clock.advance(service, 0.001)
        second = service.request(query)
        assert calls == 6 and second.retry is not None
        current = service._errors[query.normalized()]
        first.retry()
        assert service._errors[query.normalized()] is current
        assert service.request(query).reason == "source_changed" and calls == 6
    finally:
        service.close()


def test_first_changed_attempt_after_admission_window_does_not_retry(tmp_path, clock):
    calls = 0

    def build(query, limits):
        nonlocal calls
        calls += 1
        clock.value += 30
        raise ReadFailure("source_changed")
        yield

    service = DashboardDataService(builder=build)
    try:
        result = service.request(Query(tmp_path, "activity"))
        assert result.reason == "source_changed" and calls == 1
        assert result.retry is not None
        assert not service._jobs and not service._recovery
    finally:
        service.close()


@pytest.mark.parametrize("boundary", ["yield", "publication"])
def test_recovered_attempt_at_deadline_cannot_publish(
    tmp_path, clock, monkeypatch, boundary
):
    calls = 0

    def build(query, limits):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ReadFailure("source_changed")
        if boundary == "yield":
            clock.value = 130
        yield {"value": 2}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity").normalized()
    attempt = service._attempt

    def after_attempt(*args):
        result = attempt(*args)
        clock.value = 130
        return result

    if boundary == "publication":
        monkeypatch.setattr(service, "_attempt", after_attempt)
    try:
        service.request(query, wait=0)
        wait_for(service, lambda: service._recovery[query].recovering)
        future = service._jobs[query]
        clock.advance(service, 0.25)
        result = future.result(timeout=2)
        assert result.reason == "source_changed" and calls == 2
        assert query not in service._cache and not service._jobs
    finally:
        service.close()


def test_delayed_recovery_expires_behind_sibling_without_starting_attempt(
    tmp_path, clock
):
    calls = []

    def build(query, limits):
        calls.append(query.kind)
        if query.kind == "activity":
            raise ReadFailure("source_changed")
        clock.value += 31
        yield {"healthy": True}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity").normalized()
    try:
        service.request(query, wait=0)
        wait_for(service, lambda: service._recovery[query].recovering)
        future = service._jobs[query]
        assert service.request(Query(tmp_path, "ledger")).complete
        assert future.result(timeout=2).reason == "source_changed"
        assert calls == ["activity", "ledger"]
    finally:
        service.close()


def test_initial_slow_verified_read_keeps_existing_behavior(tmp_path, clock):
    def build(query, limits):
        clock.value += 31
        yield {"healthy": True}

    service = DashboardDataService(builder=build)
    try:
        assert service.request(Query(tmp_path, "activity")).complete
    finally:
        service.close()


def test_long_mutation_wave_exhausts_then_recovers_after_writes_stop(
    tmp_path, clock, record_property
):
    timings = []

    def build(query, limits):
        start = clock.value
        clock.value += 6  # Deterministic model, not a measured production cost.
        timings.append([start - 100, clock.value - 100])
        if clock.value < 134:
            raise ReadFailure("source_changed")
        yield {"stable": True}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity").normalized()
    try:
        service.request(query, wait=0)
        wait_for(service, lambda: service._recovery[query].recovering)
        future = service._jobs[query]
        clock.advance(service, 0.25)
        wait_for(service, lambda: service._recovery[query].attempts == 2)
        clock.advance(service, 0.5)
        result = future.result(timeout=2)
        assert result.reason == "source_changed" and clock.value == 118.75
        clock.advance(service, 16.25)
        assert service.request(query).complete
        assert timings == [[0, 6], [6.25, 12.25], [12.75, 18.75], [35, 41]]
        record_property("synthetic_attempt_intervals", json.dumps(timings))
        record_property("synthetic_writer_stable_at_seconds", 34)
    finally:
        service.close()


def test_exhaustion_keeps_original_cache_age_and_expiry(tmp_path, clock, monkeypatch):
    monkeypatch.setattr(data_service, "_RETRY_DELAYS", (0.0, 0.0))
    calls = 0

    def build(query, limits):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise ReadFailure("source_changed")
        yield {"old": True}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity")
    try:
        first = service.request(query)
        clock.advance(service, 3)
        failed = service.request(query)
        assert failed.status == "stale" and failed.payload == first.payload
        assert failed.verified_monotonic == first.verified_monotonic == 100
        assert calls == 4
        clock.advance(service, 27)
        assert service.request(query).status == "stale"
        clock.advance(service, 0.001)
        assert service.request(query).status == "unavailable"
        assert calls == 4
    finally:
        service.close()


def test_unexpired_tokens_plus_reserved_job_are_bounded_without_eviction(tmp_path):
    entered, release = threading.Event(), threading.Event()

    def build(query, limits):
        entered.set()
        assert release.wait(3)
        raise ReadFailure("source_changed")
        yield

    service = DashboardDataService(builder=build)
    try:
        tokens = {
            Query(tmp_path, f"failed-{i}").normalized(): ErrorToken(
                "source_changed", time.monotonic() + 30
            )
            for i in range(63)
        }
        service._errors.update(tokens)
        query = Query(tmp_path, "activity").normalized()
        service.request(query, wait=0)
        assert entered.wait(2)
        assert len(service._errors) + len(service._jobs) == 64
        denied = service.request(Query(tmp_path, "ledger"), wait=0)
        assert denied.reason == "recovery_budget_exhausted"
        assert service._errors == tokens
        service._recovery[query].deadline = 0
        release.set()
        assert service.request(query).reason == "source_changed"
        assert len(service._errors) == 64 and not service._jobs
        assert (
            service.request(Query(tmp_path, "ledger")).reason
            == "recovery_budget_exhausted"
        )
        one = service.request(next(iter(tokens)))
        assert one.retry is not None
        one.retry()
        assert len(service._errors) == 63
    finally:
        release.set()
        service.close()


def test_ordinary_error_is_evictable_and_expired_same_query_not_double_reserved(
    tmp_path, clock
):
    def build(query, limits):
        yield {"kind": query.kind}

    service = DashboardDataService(limits=Limits(cache_entries=2), builder=build)
    query = Query(tmp_path, "activity").normalized()
    sticky = Query(tmp_path, "failed").normalized()
    try:
        protected = ErrorToken("source_changed", 130)
        service._errors[sticky] = protected
        service._errors[Query(tmp_path, "ordinary").normalized()] = ErrorToken(
            "invalid_record", 102
        )
        assert service.request(query).complete
        assert service._errors == {sticky: protected}
        clock.advance(service, 3)
        service._errors[query] = ErrorToken("read_failed", 102)
        assert service.request(query).complete
        assert service._errors == {sticky: protected}
        service._errors[query] = ErrorToken("source_changed", 130)
        # Fresh compatible cache is still usable; it does not erase exhaustion.
        assert service.request(query).complete
        assert query in service._errors
    finally:
        service.close()


@pytest.mark.parametrize(
    "reason", ["invalid_record", "state_budget_exhausted", "malformed_json"]
)
def test_other_read_failures_are_not_retried(tmp_path, reason):
    calls = 0

    def build(query, limits):
        nonlocal calls
        calls += 1
        raise ReadFailure(reason)
        yield

    service = DashboardDataService(builder=build)
    try:
        result = service.request(Query(tmp_path, "activity"))
        assert result.reason == reason and calls == 1
        assert result.progress is None and result.retry is not None
    finally:
        service.close()


@pytest.mark.parametrize(
    "failure", [RuntimeError, lambda: ReadFailure("source_changed")]
)
def test_cleanup_fault_is_terminal_and_worker_can_run_next_query(tmp_path, failure):
    class BrokenClose:
        def __iter__(self):
            yield {"must_not_publish": True}

        def close(self):
            raise failure()

    def build(query, limits):
        return BrokenClose() if query.kind == "activity" else iter_result()

    def iter_result():
        yield {"healthy": True}

    service = DashboardDataService(builder=build)
    try:
        result = service.request(Query(tmp_path, "activity"))
        assert result.reason == "read_failed"
        assert Query(tmp_path, "activity").normalized() not in service._cache
        assert service.request(Query(tmp_path, "ledger")).complete
        assert not service._jobs and not service._job_progress
    finally:
        service.close()


@pytest.mark.parametrize("active", [False, True])
def test_close_settles_recovery_and_all_waiters_without_late_publication(
    tmp_path, clock, active
):
    entered, release = threading.Event(), threading.Event()
    calls = 0

    def build(query, limits):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ReadFailure("source_changed")
        entered.set()
        assert release.wait(3)
        yield {"late": True}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity").normalized()
    try:
        pending = service.request(query, wait=0)
        wait_for(service, lambda: service._recovery[query].recovering)
        future = service._jobs[query]
        if active:
            clock.advance(service, 0.25)
            assert entered.wait(2)
        service.close(timeout=0)
        assert future.result(timeout=0).reason == "service_closed"
        assert pending.progress is not None and pending.progress()
        assert not service._jobs and not service._recovery and not service._errors
        release.set()
        service.close()
        assert query not in service._cache
    finally:
        release.set()
        service.close()


def test_unexpected_worker_exit_settles_every_generation(tmp_path):
    entered, release = threading.Event(), threading.Event()

    def build(query, limits):
        entered.set()
        assert release.wait(3)
        raise SystemExit()
        yield

    service = DashboardDataService(builder=build)
    try:
        pending = [service.request(Query(tmp_path, str(i)), wait=0) for i in range(4)]
        assert entered.wait(2)
        futures = list(service._jobs.values())
        release.set()
        assert all(
            future.result(timeout=2).reason == "read_failed" for future in futures
        )
        assert all(result.progress() for result in pending)
        assert service.request(Query(tmp_path, "later")).reason == "service_closed"
    finally:
        release.set()
        service.close()


def test_worker_exit_during_settlement_still_signals_original_page(tmp_path):
    entered, release = threading.Event(), threading.Event()

    def build(query, limits):
        entered.set()
        assert release.wait(3)
        yield {"verified": True}

    def exit_worker(future):
        raise SystemExit()

    service = DashboardDataService(builder=build)
    try:
        query = Query(tmp_path, "activity").normalized()
        pending = service.request(query, wait=0)
        assert entered.wait(2)
        future = service._jobs[query]
        future.add_done_callback(exit_worker)
        sibling = service.request(Query(tmp_path, "ledger"), wait=0)
        sibling_future = service._jobs[Query(tmp_path, "ledger").normalized()]
        release.set()
        assert future.result(timeout=2).complete
        assert sibling_future.result(timeout=2).reason == "read_failed"
        assert pending.progress() and sibling.progress()
    finally:
        release.set()
        service.close()


def test_page_keeps_one_pending_signal_until_final_manual_exhaustion(
    tmp_path, clock, monkeypatch
):
    def build(query, limits):
        raise ReadFailure("source_changed")
        yield

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity").normalized()
    watchers, buttons = [], []
    monkeypatch.setattr(availability.st, "warning", lambda *args: None)
    monkeypatch.setattr(availability.st, "info", lambda *args: None)
    monkeypatch.setattr(
        availability.st, "button", lambda label, **kw: buttons.append(label) or False
    )
    monkeypatch.setattr(
        availability,
        "_watch_background",
        lambda label, progress: watchers.append(progress),
    )

    @availability.watch_loading
    def render(result):
        availability.show_availability(result, "activity")
        availability.show_availability(result, "same dependency")

    try:
        first = service.request(query, wait=0)
        wait_for(service, lambda: service._recovery[query].recovering)
        future = service._jobs[query]
        render(first)
        assert len(watchers) == 1 and not buttons
        assert len(watchers[0].probes) == 1
        clock.advance(service, 0.25)
        wait_for(service, lambda: service._recovery[query].attempts == 2)
        second = service.request(query, wait=0)
        assert service._jobs[query] is future
        assert second.progress == first.progress and not second.progress()
        clock.advance(service, 0.5)
        final = future.result(timeout=2)
        render(final)
        assert len(watchers) == 1 and buttons == ["Refresh data"]
        assert final.retry is not None and final.progress is None
    finally:
        service.close()


def test_recovery_diagnostic_labels_are_allowlisted(tmp_path, monkeypatch):
    from src.dashboard.read_diagnostics import ReadDiagnostics

    monkeypatch.setattr(data_service, "_RETRY_DELAYS", (0.0, 0.0))
    diagnostics = ReadDiagnostics(emit=lambda record: None)

    def build(query, limits):
        raise ReadFailure("source_changed")
        yield

    service = DashboardDataService(builder=build, diagnostics=diagnostics)
    try:
        assert service.request(Query(tmp_path, "activity")).reason == "source_changed"
        with service._condition:
            for i in range(63):
                service._errors[Query(tmp_path, f"failed-{i}").normalized()] = (
                    ErrorToken("source_changed", time.monotonic() + 30)
                )
        denied = service.request(Query(tmp_path, "ledger"))
        assert denied.reason == "recovery_budget_exhausted"
        records = diagnostics.snapshot()
        assert {record["stage"] for record in records} >= {
            "retry_scheduled",
            "retry_exhausted",
            "admission",
        }
        assert any(
            record["reason"] == "recovery_budget_exhausted" for record in records
        )
    finally:
        service.close()


def test_long_write_wave_recovers_on_next_request_after_original_window(
    tmp_path, clock, monkeypatch
):
    monkeypatch.setattr(data_service, "_RETRY_DELAYS", (0.0, 0.0))
    calls = 0

    def build(query, limits):
        nonlocal calls
        calls += 1
        clock.value += 6
        if clock.value < 134:
            raise ReadFailure("source_changed")
        yield {"stable": True}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity")
    try:
        failed = service.request(query)
        assert failed.reason == "source_changed" and calls == 3
        assert clock.value == 118
        clock.advance(service, 11.999)
        for _ in range(4):
            assert service.request(query).reason == "source_changed"
        assert calls == 3
        # Production's write wave lasted beyond the three immediate attempts.
        clock.advance(service, 5.001)
        recovered = service.request(query)
        assert recovered.complete and recovered.data() == {"stable": True}
        assert calls == 4 and not service._errors
    finally:
        service.close()


def test_slow_source_failure_keeps_minimum_cooldown_after_window(tmp_path, clock):
    calls = 0

    def build(query, limits):
        nonlocal calls
        calls += 1
        if calls == 1:
            clock.value += 31
            raise ReadFailure("source_changed")
        yield {"stable": True}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity")
    try:
        assert service.request(query).reason == "source_changed"
        clock.advance(service, 1.999)
        assert service.request(query).reason == "source_changed" and calls == 1
        clock.advance(service, 0.001)
        assert service.request(query).complete and calls == 2
    finally:
        service.close()


def test_expired_recovery_is_request_driven_coalesced_and_callback_safe(
    tmp_path, clock, monkeypatch
):
    monkeypatch.setattr(data_service, "_RETRY_DELAYS", (0.0, 0.0))
    entered, release = threading.Event(), threading.Event()
    calls = 0

    def build(query, limits):
        nonlocal calls
        calls += 1
        if calls <= 3:
            raise ReadFailure("source_changed")
        entered.set()
        assert release.wait(3)
        yield {"stable": True}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity").normalized()
    try:
        failed = service.request(query)
        token = service._errors[query]
        clock.advance(service, 30)
        probe = service._admission_progress(query)
        for _ in range(4):
            assert probe()
        assert service._errors[query] is token and calls == 3
        assert not service._jobs  # Expiry/progress never starts background work.
        with ThreadPoolExecutor(max_workers=4) as pool:
            pending = list(pool.map(lambda _: service.request(query, wait=0), range(4)))
        assert entered.wait(2)
        assert calls == 4 and service.stats()["admitted"] == 1
        future = service._jobs[query]
        assert failed.retry is not None
        failed.retry()
        assert service._jobs[query] is future
        release.set()
        assert future.result(timeout=2).complete
        assert all(
            result.progress is not None and result.progress() for result in pending
        )
    finally:
        release.set()
        service.close()


def test_expired_source_token_frees_bounded_capacity_for_another_query(tmp_path, clock):
    from dataclasses import replace

    def build(query, limits):
        yield {"stable": True}

    service = DashboardDataService(
        builder=build, limits=replace(Limits(), cache_entries=2)
    )
    try:
        protected = Query(tmp_path, "protected").normalized()
        expiring = Query(tmp_path, "expiring").normalized()
        service._errors[protected] = ErrorToken("source_changed", 160)
        service._errors[expiring] = ErrorToken("source_changed", 130)
        query = Query(tmp_path, "ledger")
        assert service.request(query).reason == "recovery_budget_exhausted"
        clock.advance(service, 30)
        assert service.request(query).complete
        assert list(service._errors) == [protected]
        assert len(service._errors) + len(service._jobs) <= 2
    finally:
        service.close()

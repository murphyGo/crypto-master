"""A page observes its own work without waiting for unrelated global drain."""

import gc
import inspect
import threading
import time
import weakref
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace

import pytest

from src.dashboard import availability, data_service
from src.dashboard.data_service import DashboardDataService
from src.dashboard.read_models import Limits, Query, ReadResult
from src.utils.bounded_read import ReadFailure


def test_page_ready_while_unrelated_job_blocks_reruns_once(tmp_path, monkeypatch):
    release_page, release_other = threading.Event(), threading.Event()
    other_entered = threading.Event()
    watchers, reruns = [], []
    watch = inspect.unwrap(availability._watch_background)

    def build(query, limits):
        if query.kind == "activity":
            assert release_page.wait(5)
        else:
            other_entered.set()
            assert release_other.wait(5)
        yield {"kind": query.kind}

    service = DashboardDataService(builder=build)
    monkeypatch.setattr(data_service, "get_data_service", lambda: service)
    monkeypatch.setattr(availability.st, "info", lambda message: None)
    monkeypatch.setattr(availability.st, "rerun", lambda: reruns.append("rerun"))
    monkeypatch.setattr(
        availability, "_watch_background", lambda *args: watchers.append(args)
    )
    try:
        pending = service.request(Query(tmp_path, "activity"), wait=0)
        service.request(Query(tmp_path, "audit"), wait=0)
        availability.show_availability(pending, "Activity")
        assert len(watchers) == 1
        release_page.set()
        assert other_entered.wait(2)
        assert service.stats()["admitted"] == 1
        for _ in range(20):
            watch(*watchers[0])
        assert reruns == ["rerun"]
    finally:
        release_page.set()
        release_other.set()
        service.close()


def test_queue_full_page_notices_one_free_slot_without_global_drain(
    tmp_path, monkeypatch
):
    release_first, release_others = threading.Event(), threading.Event()
    second_entered = threading.Event()
    watchers, reruns = [], []
    watch = inspect.unwrap(availability._watch_background)

    def build(query, limits):
        if query.kind == "activity":
            assert release_first.wait(5)
        else:
            second_entered.set()
            assert release_others.wait(5)
        yield {"kind": query.kind}

    service = DashboardDataService(builder=build)
    monkeypatch.setattr(data_service, "get_data_service", lambda: service)
    monkeypatch.setattr(availability.st, "info", lambda message: None)
    monkeypatch.setattr(availability.st, "rerun", lambda: reruns.append("rerun"))
    monkeypatch.setattr(
        availability, "_watch_background", lambda *args: watchers.append(args)
    )
    try:
        for kind in ("activity", "ledger", "snapshots", "candidates"):
            service.request(Query(tmp_path, kind), wait=0)
        rejected = service.request(Query(tmp_path, "proposals"), wait=0)
        assert rejected.reason == "queue_full"
        availability.show_availability(rejected, "Proposals")
        release_first.set()
        assert second_entered.wait(2)
        assert service.stats()["admitted"] == 3
        watch(*watchers[0])
        assert reruns == ["rerun"]
        # Polling notices capacity; it does not consume it or read any source.
        assert service.stats()["admitted"] == 3
    finally:
        release_first.set()
        release_others.set()
        service.close()


def test_timeout_binds_original_generation_across_completion_and_replacement(
    tmp_path, monkeypatch
):
    release = threading.Event()
    calls = 0

    def build(query, limits):
        nonlocal calls
        calls += 1
        if calls == 2:
            assert release.wait(5)
        yield {"build": calls}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity")
    original_result = Future.result
    replacement = []
    intercept = True

    def settle_then_timeout(future, timeout=None):
        nonlocal intercept
        if intercept:
            intercept = False
            assert original_result(future, timeout=2).complete
            with service._condition:
                service._cache[query.normalized()].evaluated -= 3
            replacement.append(service.request(query, wait=0))
            # Completion occurred after the caller bound its wait, followed by
            # a new same-key job before TimeoutError reached the old caller.
            raise TimeoutError
        return original_result(future, timeout=timeout)

    monkeypatch.setattr(Future, "result", settle_then_timeout)
    try:
        original = service.request(query, wait=0)
        assert original.progress is not None and original.progress()
        assert replacement[0].progress is not None
        assert not replacement[0].progress()
        assert service.stats()["admitted"] == 1
        assert len(service._job_progress) == 1
    finally:
        release.set()
        service.close()


def test_shared_generation_notifies_each_session_once_and_latches_before_rerun(
    tmp_path, monkeypatch
):
    release = threading.Event()

    def build(query, limits):
        assert release.wait(5)
        yield {"value": 1}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity")
    reruns = []
    watch = inspect.unwrap(availability._watch_background)

    class Rerun(BaseException):
        pass

    def rerun():
        reruns.append("rerun")
        raise Rerun

    monkeypatch.setattr(availability.st, "rerun", rerun)
    try:
        pages = []
        for _ in range(4):
            result = service.request(query, wait=0)
            page = availability._PageProgress()
            page.add(result.progress)
            page.add(result.progress)
            assert len(page.probes) == 1
            pages.append(page)
        assert service.stats()["admitted"] == len(service._job_progress) == 1
        release.set()
        assert service.request(query).complete
        for page in pages:
            with pytest.raises(Rerun):
                watch("Home", page)
            assert page.fired
            watch("Home", page)
        assert len(reruns) == 4
    finally:
        release.set()
        service.close()


def test_queue_full_probe_notices_same_query_admitted_with_all_four_slots_full(
    tmp_path,
):
    release_first, release_rest = threading.Event(), threading.Event()
    second_entered = threading.Event()

    def build(query, limits):
        if query.kind == "first":
            assert release_first.wait(5)
        else:
            second_entered.set()
            assert release_rest.wait(5)
        yield {"value": 1}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "proposals")
    try:
        for kind in ("first", "second", "third", "fourth"):
            service.request(Query(tmp_path, kind), wait=0)
        rejected = service.request(query, wait=0)
        assert rejected.progress is not None and not rejected.progress()
        release_first.set()
        assert second_entered.wait(2)
        assert not service.request(query, wait=0).complete
        assert service.stats()["admitted"] == 4
        assert rejected.progress()
        assert service.stats()["admitted"] == 4
    finally:
        release_first.set()
        release_rest.set()
        service.close()


@pytest.mark.parametrize("outcome", ["fresh", "terminal", "threshold"])
def test_queue_full_probe_observes_new_usable_result_without_poll_side_effects(
    tmp_path, monkeypatch, outcome
):
    release = threading.Event()
    should_block = True
    fail = False

    def build(query, limits):
        if should_block:
            assert release.wait(5)
        if fail and query.kind == "proposals":
            raise ReadFailure("source_changed")
        yield {"value": 1, "threshold": 2}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "proposals", window="threshold")
    try:
        initial = [Query(tmp_path, f"initial-{i}") for i in range(4)]
        for item in initial:
            service.request(item, wait=0)
        rejected = service.request(query, wait=0)
        assert rejected.reason == "queue_full" and rejected.progress is not None
        release.set()
        assert all(result.complete for result in service.request_many(initial).values())
        should_block = False
        fail = outcome == "terminal"
        target = replace(query, window="24h") if outcome == "threshold" else query
        ready = service.request(target)
        assert ready.complete is (outcome != "terminal")
        assert ready.progress is None
        should_block = True
        release.clear()
        for i in range(4):
            service.request(Query(tmp_path, f"other-{i}"), wait=0)
        cache_order = list(service._cache)
        errors = dict(service._errors)
        stats = service.stats()

        def forbidden(*args, **kwargs):
            pytest.fail("Progress polling must not request or resolve a query")

        monkeypatch.setattr(service, "request", forbidden)
        monkeypatch.setattr(Query, "normalized", forbidden)
        for _ in range(20):
            assert rejected.progress()
        assert list(service._cache) == cache_order
        assert service._errors == errors
        assert service.stats() == stats
    finally:
        release.set()
        service.close()


@pytest.mark.parametrize(
    "different",
    [
        {"accounts": ("other",)},
        {"scope": "other"},
        {"mode": "live"},
        {"window": "lifetime", "version": 2},
    ],
)
def test_threshold_progress_does_not_borrow_incompatible_cached_query(
    tmp_path, different
):
    release = threading.Event()

    def build(query, limits):
        if query.kind != "proposals":
            assert release.wait(5)
        yield {"threshold": 7}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "proposals", window="threshold")
    try:
        incompatible = replace(query, **({"window": "24h"} | different))
        assert service.request(incompatible).complete
        for i in range(4):
            service.request(Query(tmp_path, f"other-{i}"), wait=0)
        rejected = service.request(query, wait=0)
        assert rejected.reason == "queue_full"
        assert rejected.progress is not None and not rejected.progress()
    finally:
        release.set()
        service.close()


def test_capacity_probe_models_root_retirement_without_evicting_cache(tmp_path):
    release = threading.Event()
    block = True

    def build(query, limits):
        if block:
            assert release.wait(5)
        yield {"value": 1}

    service = DashboardDataService(builder=build)
    root = tmp_path / "requested"
    query = Query(root, "proposals")
    try:
        initial = [Query(root, f"initial-{i}") for i in range(4)]
        for item in initial:
            service.request(item, wait=0)
        rejected = service.request(query, wait=0)
        assert rejected.progress is not None
        release.set()
        assert all(result.complete for result in service.request_many(initial).values())
        block = False
        for entry in service._cache.values():
            entry.evaluated -= 31
        assert service.request(Query(tmp_path / "other-a", "ledger")).complete
        assert service.request(Query(tmp_path / "other-b", "ledger")).complete
        assert len({key.root for key in service._cache}) == 2
        assert not rejected.progress()  # Free job slot, but root gate is closed.
        for entry in service._cache.values():
            entry.evaluated -= 31
        keys = list(service._cache)
        assert rejected.progress()  # A real request can retire both inactive roots.
        assert list(service._cache) == keys
        assert service.request(query).complete
        assert {key.root for key in service._cache} == {root.resolve()}
    finally:
        release.set()
        service.close()


def test_close_notifies_active_and_queued_generations_and_retires_all_signals(tmp_path):
    release, entered = threading.Event(), threading.Event()

    def build(query, limits):
        entered.set()
        assert release.wait(5)
        yield {"value": 1}

    service = DashboardDataService(builder=build)
    try:
        results = [service.request(Query(tmp_path, str(i)), wait=0) for i in range(5)]
        assert entered.wait(2)
        assert len(service._job_progress) == 4
        assert all(result.progress is not None for result in results)
        service.close(timeout=0)
        assert not service._job_progress
        assert all(result.progress() for result in results)
        closed = service.request(Query(tmp_path, "closed"))
        assert closed.reason == "service_closed" and closed.progress is None
    finally:
        release.set()
        service.close()


def test_completed_progress_does_not_pin_future_or_evicted_payload(tmp_path):
    release = threading.Event()

    def build(query, limits):
        assert release.wait(5)
        yield {"value": query.kind, "padding": "x" * 65536}

    service = DashboardDataService(limits=Limits(cache_entries=1), builder=build)
    query = Query(tmp_path, "activity")
    try:
        pending = service.request(query, wait=0)
        future_ref = weakref.ref(service._jobs[query.normalized()])
        release.set()
        complete = service.request(query)
        result_ref = weakref.ref(complete)
        assert service.request(Query(tmp_path, "ledger")).complete
        # The existing worker keeps its last evicted CacheEntry in a local
        # until another eviction. Advance that baseline local as well.
        assert service.request(Query(tmp_path, "candidates")).complete
        del complete
        gc.collect()
        assert future_ref() is None
        assert result_ref() is None
        assert pending.progress is not None and pending.progress()
        assert not service._job_progress
    finally:
        release.set()
        service.close()


def test_queue_probe_does_not_retain_closed_service(tmp_path):
    release = threading.Event()

    def build(query, limits):
        assert release.wait(5)
        yield {"value": 1}

    service = DashboardDataService(builder=build)
    for i in range(4):
        service.request(Query(tmp_path, str(i)), wait=0)
    rejected = service.request(Query(tmp_path, "rejected"), wait=0)
    service_ref = weakref.ref(service)
    release.set()
    service.close()
    del service
    gc.collect()
    assert service_ref() is None
    assert rejected.progress is not None and rejected.progress()


def test_page_probe_cap_dedup_and_legacy_fallback_cannot_hide_ready_probe(monkeypatch):
    class Probe:
        def __call__(self):
            return False

    page = availability._PageProgress()
    for _ in range(16):
        page.add(Probe())
    extra = Probe()
    extra_ref = weakref.ref(extra)
    page.add(extra)
    del extra
    gc.collect()
    assert len(page.probes) == 16 and page.legacy
    assert extra_ref() is None
    page.probes[0] = lambda: True
    page.add(page.probes[0])
    assert len(page.probes) == 16
    reruns = []
    monkeypatch.setattr(availability.st, "rerun", lambda: reruns.append("rerun"))
    monkeypatch.setattr(
        data_service,
        "get_data_service",
        lambda: pytest.fail(
            "A known ready probe must not wait for legacy/global stats"
        ),
    )
    watch = inspect.unwrap(availability._watch_background)
    watch("Home", page)
    watch("Home", page)
    assert reruns == ["rerun"]


def test_missing_progress_preserves_legacy_service_without_new_api(monkeypatch):
    admitted = [1]
    service = SimpleNamespace(stats=lambda: {"admitted": admitted[0]})
    monkeypatch.setattr(data_service, "get_data_service", lambda: service)
    reruns = []
    monkeypatch.setattr(availability.st, "rerun", lambda: reruns.append("rerun"))
    page = availability._PageProgress()
    page.add(None)
    watch = inspect.unwrap(availability._watch_background)
    watch("Home", page)
    assert not reruns
    admitted[0] = 0
    watch("Home", page)
    watch("Home", page)
    assert reruns == ["rerun"]
    plain = ReadResult("pending")
    with_progress = replace(plain, progress=lambda: False)
    assert plain == with_progress
    assert "progress" not in repr(with_progress)


def test_progress_does_not_pin_expired_sibling_as_complete(tmp_path, monkeypatch):
    now = [1000.0]
    observed, blocked = threading.Event(), threading.Event()
    readmitted, release = threading.Event(), threading.Event()
    calls = {"activity": 0, "snapshots": 0}

    def build(query, limits):
        calls[query.kind] += 1
        if query.kind == "snapshots":
            blocked.set()
            assert release.wait(5)
        yield {"kind": query.kind}

    monkeypatch.setattr(
        data_service,
        "time",
        SimpleNamespace(monotonic=lambda: now[0], sleep=time.sleep),
    )
    service = DashboardDataService(builder=build)
    request = service._request_normalized

    def traced(query, deadline):
        result = request(query, deadline)
        if query.kind == "activity":
            if result.complete:
                observed.set()
            elif observed.is_set() and query in service._jobs:
                readmitted.set()
        return result

    monkeypatch.setattr(service, "_request_normalized", traced)
    queries = [Query(tmp_path, kind) for kind in calls]
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(service.request_many, queries)
            assert observed.wait(2) and blocked.wait(2)
            now[0] = 1003.0
            with service._condition:
                service._condition.notify_all()
            assert readmitted.wait(2)
            now[0] = 1004.01
            with service._condition:
                service._condition.notify_all()
            results = future.result(timeout=2)
            assert results["activity"].status == "stale"
            assert results["activity"].verified_monotonic == 1000.0
            assert results["snapshots"].status == "pending"
            assert results["activity"].progress is not None
            assert not results["activity"].progress()
            release.set()
            assert service.request(queries[0]).complete
            assert calls == {"activity": 2, "snapshots": 1}
    finally:
        release.set()
        service.close()

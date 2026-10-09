"""Shared worker admission, foreground deadlines and safe result states."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from src.dashboard.data_service import DashboardDataService
from src.dashboard.read_models import Limits, Query
from src.utils.bounded_read import ReadFailure


def test_same_query_coalesces_and_deadline_does_not_spawn_workers(tmp_path):
    entered, release = threading.Event(), threading.Event()
    calls = []

    def build(query, limits):
        calls.append(query)
        entered.set()
        release.wait(2)
        yield {"count": 7}

    service = DashboardDataService(limits=Limits(wait_seconds=0.03), builder=build)
    try:
        query = Query(tmp_path, "activity")
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: service.request(query), range(4)))
        assert entered.is_set()
        assert all(result.status == "pending" for result in results)
        assert len(calls) == 1
        assert service.stats()["admitted"] == service.stats()["workers"] == 1
        release.set()
        result = service.request(query, wait=0.03)
        assert result.complete and result.data() == {"count": 7}
        assert len(calls) == 1
    finally:
        release.set()
        service.close()


def test_admission_includes_active_and_bounds_distinct_waiting_work(tmp_path):
    release = threading.Event()

    def build(query, limits):
        release.wait(2)
        yield {"value": 1}

    service = DashboardDataService(builder=build)
    try:
        for kind in ("a", "b", "c", "d"):
            assert service.request(Query(tmp_path, kind), wait=0).status == "pending"
        result = service.request(Query(tmp_path, "e"), wait=0)
        assert result.status == "unavailable" and result.reason == "queue_full"
        assert service.stats()["admitted"] == 4
    finally:
        release.set()
        service.close()


def test_failure_reuses_labelled_stale_then_expires(tmp_path):
    calls = 0

    def build(query, limits):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise ReadFailure("malformed_json")
        yield {"count": 7}

    service = DashboardDataService(
        limits=Limits(fresh_seconds=0.01, stale_seconds=0.07), builder=build
    )
    try:
        query = Query(tmp_path, "activity")
        assert service.request(query).complete
        time.sleep(0.02)
        result = service.request(query)
        assert result.status == "stale" and result.data()["count"] == 7
        assert not result.complete
        time.sleep(0.07)
        result = service.request(query)
        assert result.status == "unavailable" and result.payload is None
    finally:
        service.close()


def test_oversized_result_and_cache_budget_are_not_complete(tmp_path):
    def build(query, limits):
        yield {"blob": "x" * 100}

    for limits, reason in (
        (Limits(result_bytes=32), "result_budget_exhausted"),
        (Limits(cache_bytes=32), "cache_budget_exhausted"),
    ):
        service = DashboardDataService(limits=limits, builder=build)
        try:
            result = service.request(Query(tmp_path, "activity"))
            assert result.status == "unavailable" and result.reason == reason
            assert service.stats()["cache_bytes"] <= limits.cache_bytes
        finally:
            service.close()


def test_page_sections_share_one_wait_deadline_and_shutdown(tmp_path):
    release = threading.Event()

    def build(query, limits):
        release.wait(2)
        yield {"count": 7}

    service = DashboardDataService(limits=Limits(wait_seconds=0.03), builder=build)
    started = time.monotonic()
    results = service.request_many(
        [Query(tmp_path, kind) for kind in ("a", "b", "c", "d", "e")]
    )
    assert time.monotonic() - started < 0.2
    assert not any(result.complete for result in results.values())
    release.set()
    service.close()
    assert service.request(Query(tmp_path, "a")).reason == "service_closed"


def test_batch_revalidates_completed_section_that_ages_in_queue(tmp_path):
    release = threading.Event()
    calls = []

    def build(query, limits):
        calls.append(query.kind)
        if query.kind == "slow":
            release.wait(1)
        yield {"count": 7}

    service = DashboardDataService(
        limits=Limits(wait_seconds=0.2, fresh_seconds=0.01), builder=build
    )
    timer = threading.Timer(0.04, release.set)
    timer.start()
    try:
        results = service.request_many(
            [Query(tmp_path, "fast"), Query(tmp_path, "slow")]
        )
        assert all(result.complete for result in results.values())
        assert calls.count("fast") >= 2
    finally:
        release.set()
        timer.join()
        service.close()


def test_only_two_data_roots_are_admitted(tmp_path):
    def build(query, limits):
        yield {"count": 7}

    service = DashboardDataService(builder=build)
    try:
        assert service.request(Query(tmp_path / "one", "activity")).complete
        assert service.request(Query(tmp_path / "two", "activity")).complete
        result = service.request(Query(tmp_path / "three", "activity"))
        assert result.reason == "root_budget_exhausted" and not result.complete
    finally:
        service.close()

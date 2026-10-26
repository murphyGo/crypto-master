"""Shared worker admission, foreground deadlines and safe result states."""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone

from src.dashboard import availability
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


def test_unchanged_projection_survives_stale_display_deadline(tmp_path, monkeypatch):
    from src.dashboard import projections

    path = tmp_path / "runtime" / "activity.jsonl"
    path.parent.mkdir()
    now = datetime.now(timezone.utc)
    path.write_text(
        json.dumps(
            {
                "timestamp": now.isoformat(),
                "event_type": "cycle_started",
                "cycle_id": "cached-cycle",
                "message": "",
                "details": {},
            }
        )
        + "\n"
    )
    query = Query(tmp_path, "activity", at=now)
    service = DashboardDataService()
    try:
        assert service.request(query).complete
        with service._condition:
            service._cache[query.normalized()].evaluated -= (
                service.limits.stale_seconds + 1
            )
        original_reader = projections.reverse_jsonl_bytes

        def unnecessary_read(*args, **kwargs):
            raise ReadFailure("unexpected_archive_rebuild")

        monkeypatch.setattr(projections, "reverse_jsonl_bytes", unnecessary_read)
        result = service.request(query)
        assert result.complete and result.data()["total"] == 1
        assert service.stats()["cache_bytes"] <= service.limits.cache_bytes

        # Retention for verified reuse cannot make expired or damaged data
        # eligible for display as complete or as labelled stale fallback.
        monkeypatch.setattr(projections, "reverse_jsonl_bytes", original_reader)
        path.write_text("broken\n")
        with service._condition:
            service._cache[query.normalized()].evaluated -= (
                service.limits.stale_seconds + 1
            )
        damaged = service.request(query)
        assert damaged.status == "unavailable" and damaged.payload is None
        assert damaged.reason == "malformed_json"
    finally:
        service.close()


def test_expired_other_root_can_be_evicted_to_admit_new_root(tmp_path):
    def build(query, limits):
        yield {"count": 7}

    service = DashboardDataService(builder=build)
    try:
        first = Query(tmp_path / "one", "activity")
        assert service.request(first).complete
        assert service.request(Query(tmp_path / "two", "activity")).complete
        with service._condition:
            service._cache[first.normalized()].evaluated -= (
                service.limits.stale_seconds + 1
            )
        assert service.request(Query(tmp_path / "three", "activity")).complete
        assert len({query.root for query in service._cache}) == 2
    finally:
        service.close()


def test_threshold_borrows_only_fresh_matching_complete_funnel_projection(tmp_path):
    calls = []

    def build(query, limits):
        calls.append(query)
        yield {
            "threshold": 7,
            "counts": {"total": 2},
            "_source_digest": "verified",
            "source_coverage": {"verified": True},
        }

    service = DashboardDataService(builder=build)
    try:
        query = Query(tmp_path, "proposals", window="24h")
        home = service.request(query)
        result = service.request(replace(query, window="threshold"))
        assert result.complete and result.data()["threshold"] == 7
        assert "counts" not in result.data()
        assert result.data()["source_coverage"] == {"verified": True}
        assert result.verified_monotonic == home.verified_monotonic
        assert len(calls) == 1 and service.stats()["entries"] == 1
        assert service.stats()["cache_bytes"] <= service.limits.cache_bytes

        for changed in (
            replace(query, root=tmp_path / "other", window="threshold"),
            replace(query, source=tmp_path / "different", window="threshold"),
            replace(
                query,
                at=datetime(2026, 10, 25, tzinfo=timezone.utc),
                window="threshold",
            ),
        ):
            count = len(calls)
            assert service.request(changed).complete
            assert len(calls) == count + 1
    finally:
        service.close()


def test_threshold_borrow_never_renews_source_age_or_hides_failed_revalidation(
    tmp_path,
):
    calls = 0

    def build(query, limits):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise ReadFailure("source_changed")
        yield {"threshold": 9}

    service = DashboardDataService(builder=build)
    try:
        home = Query(tmp_path, "proposals", window="24h")
        first = service.request(home)
        threshold = replace(home, window="threshold")
        assert service.request(threshold).verified_monotonic == first.verified_monotonic
        with service._condition:
            service._cache[home.normalized()].evaluated -= (
                service.limits.fresh_seconds + 1
            )
        result = service.request(threshold)
        assert not result.complete and result.payload is None
        assert result.reason == "source_changed" and calls == 2
    finally:
        service.close()


def test_threshold_derivative_bytes_are_charged_and_optional_at_result_limit(tmp_path):
    def build(query, limits):
        yield {"threshold": 3, "padding": "x" * 100}

    encoded = len(
        json.dumps(
            {"threshold": 3, "padding": "x" * 100}, separators=(",", ":")
        ).encode()
    )
    for result_bytes in (encoded, encoded + 100):
        service = DashboardDataService(
            limits=Limits(result_bytes=result_bytes), builder=build
        )
        try:
            query = Query(tmp_path, "proposals", window="24h")
            assert service.request(query).complete
            entry = service._cache[query.normalized()]
            assert (entry.threshold is None) == (result_bytes == encoded)
            extra = len(entry.threshold.payload) if entry.threshold else 0
            assert entry.charge == encoded + extra + 4096 + len(
                repr(query.normalized()).encode()
            )
            assert service.stats()["cache_bytes"] <= service.limits.cache_bytes
        finally:
            service.close()


def test_batch_returns_known_failure_and_verified_sibling_without_waiting_deadline(
    tmp_path,
):
    def build(query, limits):
        if query.kind == "activity":
            raise ReadFailure("malformed_json")
        yield {"open_positions": 1}

    service = DashboardDataService(limits=Limits(wait_seconds=5), builder=build)
    try:
        start = time.monotonic()
        results = service.request_many(
            [Query(tmp_path, "activity"), Query(tmp_path, "ledger")]
        )
        assert time.monotonic() - start < 1
        assert results["activity"].status == "unavailable"
        assert results["activity"].reason == "malformed_json"
        assert (
            results["ledger"].complete
            and results["ledger"].data()["open_positions"] == 1
        )
    finally:
        service.close()


def test_page_wait_canonicalizes_each_query_once_instead_of_polling_filesystem(
    tmp_path, monkeypatch
):
    release = threading.Event()
    calls = []
    normalized = Query.normalized

    def count_normalization(query):
        calls.append(query.kind)
        return normalized(query)

    def build(query, limits):
        release.wait(2)
        yield {"count": 1}

    monkeypatch.setattr(Query, "normalized", count_normalization)
    service = DashboardDataService(limits=Limits(wait_seconds=0.12), builder=build)
    try:
        kinds = ["activity", "ledger", "snapshots", "proposals"]
        results = service.request_many([Query(tmp_path, kind) for kind in kinds])
        assert all(not r.complete for r in results.values())
        assert calls == kinds
    finally:
        release.set()
        service.close()


def test_five_home_queries_queue_full_release_and_watcher_coalescing(
    tmp_path, monkeypatch
):
    entered, release = threading.Event(), threading.Event()
    calls, watchers = [], []

    def build(query, limits):
        calls.append(query.kind)
        entered.set()
        assert release.wait(5)
        yield {"kind": query.kind}

    service = DashboardDataService(limits=Limits(wait_seconds=0.03), builder=build)
    kinds = ("activity", "ledger", "snapshots", "candidates", "proposals")
    queries = [Query(tmp_path, kind) for kind in kinds]
    monkeypatch.setattr(availability.st, "info", lambda message: None)
    monkeypatch.setattr(availability.st, "warning", lambda message: None)
    monkeypatch.setattr(availability.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        availability, "_watch_background", lambda label, *_: watchers.append(label)
    )

    @availability.watch_loading
    def render(results):
        for kind, result in results.items():
            availability.show_availability(result, kind)

    try:
        results = service.request_many(queries)
        assert entered.is_set()
        assert results["proposals"].reason == "queue_full"
        assert service.stats()["admitted"] == 4
        assert service.stats()["workers"] == 1
        # The final page may have only its not-yet-admitted section unresolved.
        # That section must itself keep recovery alive, independently of pending.
        render({"proposals": results["proposals"]})
        assert len(watchers) == 1
        assert results["proposals"].retry is None
        release.set()
        recovered = service.request_many(queries)
        assert all(result.complete for result in recovered.values())
        assert calls == list(kinds)
        assert service.stats()["workers"] == 1
    finally:
        release.set()
        service.close()


def test_home_cached_source_failure_manual_retry_preserves_healthy_data_and_age(
    tmp_path, monkeypatch
):
    calls = dict.fromkeys(
        ("activity", "ledger", "snapshots", "candidates", "proposals"), 0
    )
    fail = False

    def build(query, limits):
        calls[query.kind] += 1
        if fail and query.kind in {"activity", "snapshots"}:
            raise ReadFailure("source_changed")
        yield {"kind": query.kind, "generation": calls[query.kind]}

    service = DashboardDataService(builder=build)
    queries = [Query(tmp_path, kind) for kind in calls]
    watchers, buttons = [], []
    monkeypatch.setattr(availability.st, "warning", lambda message: None)
    monkeypatch.setattr(availability.st, "info", lambda message: None)
    monkeypatch.setattr(
        availability, "_watch_background", lambda label, *_: watchers.append(label)
    )
    monkeypatch.setattr(
        availability.st,
        "button",
        lambda label, **kwargs: buttons.append(label) or False,
    )

    @availability.watch_loading
    def render(results):
        for kind, result in results.items():
            availability.show_availability(result, kind)

    try:
        first = service.request_many(queries)
        assert all(result.complete for result in first.values())
        for query in queries:
            if query.kind in {"activity", "snapshots"}:
                service._cache[query.normalized()].evaluated -= (
                    service.limits.fresh_seconds + 1
                )
        fail = True
        failed = service.request_many(queries)
        render(failed)
        assert buttons == ["Refresh data"] and not watchers
        for kind in ("activity", "snapshots"):
            assert failed[kind].status == "stale"
            assert failed[kind].reason == "source_changed"
            assert failed[kind].payload == first[kind].payload
        cached = service.request_many(queries)
        assert calls["activity"] == calls["snapshots"] == 2
        old_ages = {
            query.kind: service._cache[query.normalized()].evaluated
            for query in queries
        }
        fail = False
        monkeypatch.setattr(availability.st, "button", lambda *args, **kwargs: True)
        monkeypatch.setattr(availability.st, "rerun", lambda: None)
        render(cached)
        assert not service._errors
        assert old_ages == {
            query.kind: service._cache[query.normalized()].evaluated
            for query in queries
        }
        recovered = service.request_many(queries)
        assert all(result.complete for result in recovered.values())
        assert calls["activity"] == calls["snapshots"] == 3
        for kind in ("ledger", "candidates", "proposals"):
            assert calls[kind] == 1
            assert recovered[kind] is first[kind]
    finally:
        service.close()


def test_stale_retry_callback_cannot_clear_new_failure_or_other_query(tmp_path):
    def build(query, limits):
        raise ReadFailure("invalid_record")
        yield

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity")
    other = Query(tmp_path, "snapshots")
    try:
        first = service.request(query)
        separate = service.request(other)
        assert first.retry is not None and separate.retry is not None
        first.retry()
        second = service.request(query)
        assert not second.complete and second.retry is not None
        error = service._errors[query.normalized()]
        first.retry()
        assert service._errors[query.normalized()] is error
        assert other.normalized() in service._errors
        assert service.request(query).retry is not None
    finally:
        service.close()


def test_concurrent_explicit_retries_coalesce_one_new_read(tmp_path):
    calls = 0
    entered, release = threading.Event(), threading.Event()

    def build(query, limits):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ReadFailure("source_changed")
        entered.set()
        assert release.wait(5)
        yield {"value": 1}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity")
    try:
        failed = service.request(query)
        assert failed.retry is not None

        def refresh(_):
            failed.retry()
            return service.request(query, wait=0)

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(refresh, range(4)))
        assert entered.wait(1)
        assert calls == 2
        assert all(not result.complete for result in results)
        assert service.stats()["admitted"] == service.stats()["workers"] == 1
        release.set()
        assert service.request(query).complete
        assert calls == 2
    finally:
        release.set()
        service.close()


def test_diagnostic_failure_never_strands_worker_or_changes_read_outcome(tmp_path):
    class BrokenDiagnostics:
        def record(self, **kwargs):
            raise RuntimeError("diagnostic sink failed")

    def build(query, limits):
        if query.kind == "activity":
            raise ReadFailure("invalid_record")
        yield {"value": 1}

    service = DashboardDataService(builder=build, diagnostics=BrokenDiagnostics())
    try:
        failed = service.request(Query(tmp_path, "activity"))
        assert failed.reason == "invalid_record" and failed.retry is not None
        assert service.request(Query(tmp_path, "ledger")).complete
        assert service.stats()["workers"] == 1
    finally:
        service.close()


def test_closed_service_does_not_return_cached_stale_data(tmp_path):
    def build(query, limits):
        yield {"value": 1}

    service = DashboardDataService(builder=build)
    query = Query(tmp_path, "activity")
    assert service.request(query).complete
    service.close()
    result = service.request(query)
    assert result.status == "unavailable" and result.reason == "service_closed"
    assert result.payload is None

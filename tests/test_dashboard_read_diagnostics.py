"""Finite, private diagnostics must never become a dashboard read dependency."""

import json
import logging
import threading
import time
from itertools import product

import pytest

from src.dashboard.data_service import DashboardDataService
from src.dashboard.read_diagnostics import (
    ReadDiagnostics,
    _console,
    _delivery,
)
from src.dashboard.read_models import Limits, Query
from src.utils.bounded_read import ReadFailure


def record(diagnostics, **overrides):
    values = {
        "kind": "activity",
        "status": "stale",
        "reason": "source_changed",
        "stage": "projection",
        "cache_age_seconds": 12.345678,
        "admitted": 4,
    }
    diagnostics.record(**(values | overrides))


def test_diagnostics_sanitize_before_retaining_or_emitting():
    emitted = []
    diagnostics = ReadDiagnostics(emit=emitted.append)
    private = "/data/accounts/private-account-id/secret.json"
    record(diagnostics, kind=private, status=private, reason=private, stage=private)
    _delivery._queue.join()
    expected = {
        "event": "dashboard_read_incomplete",
        "kind": "unknown",
        "status": "unknown",
        "reason": "unknown",
        "stage": "unknown",
        "cache_age_seconds": 12.346,
        "admitted": 4,
    }
    assert emitted == [expected]
    assert diagnostics.snapshot() == (expected,)
    assert private not in json.dumps(emitted)
    emitted[0]["reason"] = "changed by sink"
    assert diagnostics.snapshot()[0]["reason"] == "unknown"


@pytest.mark.parametrize("age", [None, float("nan"), float("inf"), True, "private"])
def test_non_numeric_or_nonfinite_metadata_is_not_retained(age):
    diagnostics = ReadDiagnostics(emit=lambda entry: None)
    record(diagnostics, cache_age_seconds=age, admitted=True)
    assert diagnostics.snapshot()[0]["cache_age_seconds"] is None
    assert diagnostics.snapshot()[0]["admitted"] is None


def test_unknown_input_objects_do_not_run_hash_repr_or_string_conversion():
    class Private:
        def __hash__(self):
            raise AssertionError("Do not hash arbitrary metadata")

        def __repr__(self):
            raise AssertionError("Do not print arbitrary metadata")

        __str__ = __repr__

    diagnostics = ReadDiagnostics(emit=lambda entry: None)
    value = Private()
    record(diagnostics, kind=value, status=value, reason=value, stage=value)
    assert all(
        diagnostics.snapshot()[0][key] == "unknown"
        for key in ("kind", "status", "reason", "stage")
    )


def test_all_production_query_kinds_keep_their_safe_classification():
    diagnostics = ReadDiagnostics(emit=lambda entry: None)
    kinds = {
        "activity",
        "ledger",
        "snapshots",
        "candidates",
        "proposals",
        "audit",
        "promotion",
    }
    for kind in kinds:
        record(diagnostics, kind=kind)
    assert {entry["kind"] for entry in diagnostics.snapshot()} == kinds


def test_unknown_rerender_flood_has_one_key_and_recovers_after_cooldown():
    now = [100.0]
    diagnostics = ReadDiagnostics(clock=lambda: now[0], emit=lambda entry: None)
    for index in range(10_000):
        record(diagnostics, reason=f"private-account-{index}", cache_age_seconds=index)
    assert len(diagnostics.snapshot()) == len(diagnostics._last) == 1
    now[0] += 4.999
    record(diagnostics, reason="another private reason")
    assert len(diagnostics.snapshot()) == 1
    now[0] += 0.001
    record(diagnostics, reason="another private reason")
    assert len(diagnostics.snapshot()) == 2


def test_global_burst_refill_and_retention_are_bounded():
    now = [100.0]
    diagnostics = ReadDiagnostics(clock=lambda: now[0], emit=lambda entry: None)
    classifications = list(
        product(
            (
                "activity",
                "ledger",
                "snapshots",
                "candidates",
                "proposals",
                "audit",
                "promotion",
            ),
            ("pending", "stale", "unavailable"),
            ("source_changed", "invalid_record", "queue_full", "read_failed"),
        )
    )
    for kind, status, reason in classifications:
        record(diagnostics, kind=kind, status=status, reason=reason)
    assert len(diagnostics.snapshot()) == 8
    now[0] += 1
    for kind, status, reason in classifications[8:]:
        record(diagnostics, kind=kind, status=status, reason=reason)
    assert len(diagnostics.snapshot()) == 10
    for kind, status, reason in classifications:
        now[0] += 6
        record(diagnostics, kind=kind, status=status, reason=reason)
    assert len(diagnostics.snapshot()) == len(diagnostics._last) == 64


def test_console_logger_is_isolated_and_has_no_file_handlers():
    assert not _console.propagate
    assert len(_console.handlers) == 1
    assert type(_console.handlers[0]) is logging.StreamHandler
    assert not any(
        isinstance(handler, logging.FileHandler) for handler in _console.handlers
    )


def test_raising_sink_is_counted_without_killing_shared_drain():
    before = _delivery.stats()["failed"]

    def broken(entry):
        raise RuntimeError("private exception never logged")

    diagnostics = ReadDiagnostics(emit=broken)
    record(diagnostics)
    _delivery._queue.join()
    assert _delivery.stats()["failed"] == before + 1
    assert _delivery.stats()["workers"] == 1


def test_blocked_sink_queue_is_bounded_and_read_close_never_wait_for_it(tmp_path):
    entered, release = threading.Event(), threading.Event()
    now = [100.0]

    def blocked(entry):
        entered.set()
        assert release.wait(5)

    def build(query, limits):
        if query.kind == "activity":
            raise ReadFailure("invalid_record")
        yield {"value": 7}

    diagnostics = ReadDiagnostics(clock=lambda: now[0], emit=blocked)
    before = _delivery.stats()["dropped"]
    service = DashboardDataService(
        limits=Limits(wait_seconds=0.03), builder=build, diagnostics=diagnostics
    )
    try:
        record(diagnostics)
        assert entered.wait(1)
        for _ in range(100):
            now[0] += 6
            record(diagnostics)
        assert _delivery.stats()["queued"] == 64
        assert _delivery.stats()["dropped"] >= before + 36
        start = time.monotonic()
        failed = service.request(Query(tmp_path, "activity"))
        assert failed.reason == "invalid_record" and failed.retry is not None
        assert service.request(Query(tmp_path, "ledger")).complete
        service.close()
        assert time.monotonic() - start < 0.5
        assert _delivery.stats()["workers"] == 1
        assert not release.is_set()
    finally:
        release.set()
        service.close()
        _delivery._queue.join()


def test_services_share_one_diagnostic_drain(tmp_path):
    services = [DashboardDataService() for _ in range(4)]
    try:
        assert len({id(service._diagnostics) for service in services}) == 1
        assert (
            sum(
                thread.name == "dashboard-read-diagnostics"
                for thread in threading.enumerate()
            )
            == 1
        )
    finally:
        for service in services:
            service.close()

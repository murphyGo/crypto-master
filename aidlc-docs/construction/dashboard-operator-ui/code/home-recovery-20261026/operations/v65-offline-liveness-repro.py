"""Offline deterministic mechanism probes; imports exact deployed source, no edits."""
from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path('/private/tmp/crypto-master-home-recovery-20261026')
OUTPUT = Path('/private/tmp/crypto-master-home-recovery-delivery/v65-offline-liveness-result.json')
EXPECTED = '382c26b1290c4b1a7cc843f28686fc9e2e4f2323'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == EXPECTED
sys.path.insert(0, str(ROOT))
from src.dashboard import availability, data_service
from src.dashboard.data_service import DashboardDataService
from src.dashboard.projections import build_projection
from src.dashboard.read_models import Limits, Query
from src.runtime.activity_events import ActivityEvent
from src.utils.bounded_read import ReadFailure


class SilentDiagnostics:
    def record(self, **fields):
        pass


class Clock:
    def __init__(self):
        self.value = 1000.0
        self.lock = threading.Lock()
    def monotonic(self):
        with self.lock:
            return self.value
    def set(self, value):
        with self.lock:
            self.value = value


def readmission(root):
    """A completed sibling expires and is admitted again in the same 4s batch."""
    clock = Clock()
    observed = threading.Event()
    blocked = threading.Event()
    release = threading.Event()
    readmitted = threading.Event()
    calls = Counter()
    queries = [Query(root, 'activity'), Query(root, 'snapshots')]
    def build(query, limits):
        calls[query.kind] += 1
        if query.kind == 'snapshots':
            blocked.set()
            assert release.wait(5), 'controller failed to release sibling'
        yield {'kind': query.kind, 'build': calls[query.kind]}
    with patch.object(data_service, 'time', SimpleNamespace(monotonic=clock.monotonic, sleep=time.sleep)):
        service = DashboardDataService(builder=build, diagnostics=SilentDiagnostics())
        original = service._request_normalized
        def traced(query, deadline):
            result = original(query, deadline)
            if query.kind == 'activity':
                if result.complete:
                    observed.set()
                elif observed.is_set() and query in service._jobs:
                    readmitted.set()
            return result
        service._request_normalized = traced
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(service.request_many, queries)
                assert observed.wait(2) and blocked.wait(2)
                first = service._cache[queries[0].normalized()].result
                clock.set(1003.0)
                with service._condition:
                    service._condition.notify_all()
                assert readmitted.wait(2)
                at_readmission = service.stats()
                assert at_readmission['admitted'] == 2
                clock.set(1004.01)
                with service._condition:
                    service._condition.notify_all()
                result = future.result(timeout=2)
                assert result['activity'].status == 'stale'
                assert result['activity'].reason == 'rebuild_pending'
                assert result['activity'].verified_monotonic == first.verified_monotonic == 1000.0
                assert result['snapshots'].status == 'pending'
                release.set()
                assert service.request(queries[0]).complete
                assert calls == {'activity': 2, 'snapshots': 1}
                return {
                    'pass': True,
                    'fake_clock': {'first_completed': 1000.0, 'readmitted': 1003.0, 'batch_deadline_return': 1004.01},
                    'default_fresh_seconds': service.limits.fresh_seconds,
                    'default_batch_seconds': service.limits.wait_seconds,
                    'calls': dict(calls),
                    'admitted_at_readmission': at_readmission['admitted'],
                    'workers': at_readmission['workers'],
                    'deadline_statuses': {kind: value.status for kind, value in result.items()},
                    'original_verification_epoch_preserved': True,
                    'qualification': 'Controlled unchanged-source builder: demonstrates policy-driven repeat admission, not a proof that live failures had this cause. Pinning first activity as complete at return would violate the approved 2s complete-result cache-age bound.'
                }
        finally:
            release.set()
            service.close()


def global_drain(root):
    """An unrelated query prevents page watcher rerun after page work completes."""
    unrelated_entered = threading.Event()
    release = threading.Event()
    def build(query, limits):
        if query.kind == 'audit':
            unrelated_entered.set()
            assert release.wait(5)
        yield {'kind': query.kind}
    service = DashboardDataService(builder=build, diagnostics=SilentDiagnostics())
    page = Query(root, 'activity')
    unrelated = Query(root, 'audit')
    reruns = []
    watcher = inspect.unwrap(availability._watch_background)
    try:
        assert service.request(page).complete
        assert not service.request(unrelated, wait=0).complete
        assert unrelated_entered.wait(2)
        assert service.request(page).complete
        with patch.object(data_service, 'get_data_service', lambda: service), patch.object(availability.st, 'rerun', lambda: reruns.append('rerun')):
            for _ in range(20):
                watcher('Home')
            assert not reruns
            assert service.stats()['admitted'] == 1
            release.set()
            assert service.request(unrelated).complete
            watcher('Home')
            assert reruns == ['rerun']
        return {'pass': True, 'ready_page_kind': 'activity', 'unrelated_kind': 'audit', 'polls_while_unrelated_blocked': 20, 'reruns_while_unrelated_blocked': 0, 'reruns_after_global_drain': 1, 'workers': 1, 'qualification': 'Proves global-drain coupling without source failures, cache expiry, wall-clock sleeps or CPU assumptions. Does not attribute any live request.'}
    finally:
        release.set()
        service.close()


def source_mutation(root):
    """Valid append after read checkpoint rejects each attempt; quiet pass recovers."""
    directory = root / 'runtime'
    directory.mkdir(parents=True)
    path = directory / 'activity.jsonl'
    at = datetime(2026,10,26,5,1,34,tzinfo=timezone.utc)
    def row(index):
        return ActivityEvent(timestamp=at,event_type='cycle_started',cycle_id=str(index),message='fixture').model_dump_json()+'\n'
    path.write_text(row(0))
    query = Query(root,'activity',at=at)
    failures = []
    for index in range(1,4):
        iterator = build_projection(query, Limits())
        assert next(iterator) is None
        with path.open('a') as handle:
            handle.write(row(index))
        try:
            list(iterator)
        except ReadFailure as exc:
            failures.append(exc.reason)
        else:
            raise AssertionError('Changed generation must not become complete')
        finally:
            iterator.close()
    assert failures == ['source_changed']*3
    quiet = next(item for item in build_projection(query, Limits()) if item is not None)
    assert quiet['source_coverage']['verified'] is True
    return {'pass':True,'controlled_mutations':3,'failed_attempts':failures,'quiet_attempt_verified':True,'source_coverage':quiet['source_coverage'],'qualification':'Synthetic temp fixture only. Valid append changes the captured generation and prevents publication until a quiet verification interval; no malformed input or production-source mutation.'}


with tempfile.TemporaryDirectory(prefix='v65-offline-liveness-') as directory:
    base = Path(directory)
    result = {
        'source_commit': EXPECTED,
        'source_hashes': {path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in ['src/dashboard/data_service.py','src/dashboard/availability.py','src/dashboard/read_models.py','src/dashboard/projections.py','src/dashboard/sources.py','src/utils/bounded_read.py']},
        'readmission': readmission(base/'readmission'),
        'global_drain': global_drain(base/'drain'),
        'source_mutation': source_mutation(base/'mutations'),
        'no_live_attribution': True,
    }
OUTPUT.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))

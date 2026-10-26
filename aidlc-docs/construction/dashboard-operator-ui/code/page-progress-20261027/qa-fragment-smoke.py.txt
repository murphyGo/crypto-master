"""Temp-only AppTest probe; no network, source edits, or runtime data reads."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import hashlib
import json
import threading
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

WORKTREE = Path('/private/tmp/crypto-master-page-progress-20261027')
DELIVERY = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKTREE))

from streamlit.testing.v1 import AppTest

from src.dashboard.data_service import DashboardDataService
from src.dashboard.read_models import Query

FILES = ('src/dashboard/availability.py', 'src/dashboard/data_service.py', 'src/dashboard/read_models.py')


def hashes():
    return {name:hashlib.sha256((WORKTREE/name).read_bytes()).hexdigest() for name in FILES}


def snapshot(test):
    state = test.session_state
    return {'renders':state['renders'], 'read_status':state['read_status'],
            'fragment_dispatches':state['fragment_dispatches'],
            'dispatches_that_returned':state['dispatches_that_returned'],
            'fragment_count':state['fragment_count'],
            'exceptions':[str(item.message) for item in test.exception],
            'metrics':[{'label':item.label, 'value':item.value} for item in test.metric]}


release_page, release_other = threading.Event(), threading.Event()
other_entered = threading.Event()
calls = Counter()


def build(query, limits):
    calls[query.kind] += 1
    if query.kind == 'activity':
        assert release_page.wait(15), 'fixture page release timed out'
    else:
        other_entered.set()
        assert release_other.wait(15), 'fixture unrelated release timed out'
    yield {'value':7}


before = hashes()
result = {'started_at':datetime.now(timezone.utc).isoformat(), 'source_hashes_before':before,
          'scope':'Actual local Streamlit AppTest fragment closure, argument capture, st.rerun and session isolation. Explicit closure dispatch, not browser timer/native viewport qualification.',
          'production_load_added':False, 'sessions':[]}
service = DashboardDataService(builder=build)
try:
    query = Query(DELIVERY/'fixture-root', 'activity')
    assert not service.request(query, wait=0).complete
    assert not service.request(Query(DELIVERY/'fixture-root', 'audit'), wait=0).complete
    sessions = []
    for _ in range(2):
        test = AppTest.from_file(DELIVERY/'qa-fragment-smoke-app.py', default_timeout=8)
        for key,value in {'service':service, 'query':query, 'renders':0, 'fragment_dispatches':0,
                          'dispatches_that_returned':0}.items():
            test.session_state[key] = value
        test.run()
        initial = snapshot(test)
        assert not initial['exceptions'] and initial['renders'] == 1
        assert initial['read_status'] == 'pending' and initial['fragment_count'] == 1
        result['sessions'].append({'initial':initial})
        sessions.append(test)
    release_page.set()
    assert other_entered.wait(2)
    assert service.stats()['admitted'] == 1
    for index,test in enumerate(sessions):
        test.session_state['dispatch_saved'] = True
        test.run()
        ready = snapshot(test)
        result['sessions'][index]['after_ready_dispatch'] = ready
        assert not ready['exceptions'] and ready['read_status'] == 'complete'
        assert ready['renders'] == 2 and ready['fragment_dispatches'] == 1
        assert ready['dispatches_that_returned'] == 0
        assert ready['metrics'] == [{'label':'Ready', 'value':'7'}]
        assert service.stats()['admitted'] == 1
        test.session_state['dispatch_saved'] = True
        test.run()
        repeated = snapshot(test)
        result['sessions'][index]['after_repeated_old_dispatch'] = repeated
        assert not repeated['exceptions'] and repeated['read_status'] == 'complete'
        assert repeated['renders'] == 3 and repeated['fragment_dispatches'] == 2
        assert repeated['dispatches_that_returned'] == 1
    result['calls'] = dict(calls)
    result['service_before_cleanup'] = service.stats()
    assert calls == {'activity':1, 'audit':1}
    assert service.stats()['workers'] == service.stats()['admitted'] == 1
    result['verdict'] = 'PASS'
except BaseException:
    result['verdict'] = 'FAIL'
    result['error'] = traceback.format_exc()
    raise
finally:
    release_page.set()
    release_other.set()
    service.close()
    result['source_hashes_after'] = hashes()
    result['source_hashes_unchanged'] = before == result['source_hashes_after']
    result['fixture_hashes'] = {path.name:hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in (Path(__file__), DELIVERY/'qa-fragment-smoke-app.py')}
    result['completed_at'] = datetime.now(timezone.utc).isoformat()
    with (DELIVERY/'qa-fragment-smoke-result.json').open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps(result), flush=True)

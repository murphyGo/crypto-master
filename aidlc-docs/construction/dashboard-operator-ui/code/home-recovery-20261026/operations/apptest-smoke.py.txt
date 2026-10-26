import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from streamlit.testing.v1 import AppTest

SCRIPT = '''
import streamlit as st
from pathlib import Path
from src.dashboard.availability import watch_loading, show_availability
from src.dashboard.data_service import DashboardDataService
from src.dashboard.read_models import Limits, Query
from src.utils.bounded_read import ReadFailure
if "qa_service" not in st.session_state:
    calls={"activity":0,"ledger":0}
    def build(query, limits):
        calls[query.kind]+=1
        if query.kind=="activity" and calls[query.kind]==1:
            raise ReadFailure("source_changed")
        yield {"value":7,"generation":calls[query.kind]}
    st.session_state["qa_calls"]=calls
    st.session_state["qa_service"]=DashboardDataService(limits=Limits(fresh_seconds=2,stale_seconds=30),builder=build)
    st.session_state["qa_render_count"]=0
service=st.session_state["qa_service"]
@watch_loading
def render():
    st.session_state["qa_render_count"]+=1
    results=service.request_many([Query(Path(ROOT),"activity"),Query(Path(ROOT),"ledger")])
    st.session_state["qa_results"]=results
    if show_availability(results["activity"],"Runtime safety and activity"):
        st.metric("Safety status","Ready")
    if show_availability(results["ledger"],"Trade ledger"):
        st.metric("Open Positions",results["ledger"].data()["value"])
render()
'''


def snapshot(app):
    return {
        'exceptions': [row.value for row in app.exception],
        'buttons': [row.label for row in app.button],
        'metrics': {row.label: row.value for row in app.metric},
        'calls': dict(app.session_state['qa_calls']),
        'renders': app.session_state['qa_render_count'],
        'result_statuses': {key: value.status for key, value in app.session_state['qa_results'].items()},
    }


def main():
    report = {}
    with tempfile.TemporaryDirectory(prefix='qa-real-streamlit-retry-') as folder:
        app = AppTest.from_string('ROOT='+repr(folder)+'\n'+SCRIPT)
        service = None
        try:
            app.run(timeout=10)
            service = app.session_state['qa_service']
            report['initial'] = snapshot(app)
            old_ledger = app.session_state['qa_results']['ledger']
            error_time = next(iter(service._errors.values()))[0]
            report['error_age_before_click_seconds'] = time.monotonic()-error_time
            app.button[0].click().run(timeout=10)
            report['clicked'] = snapshot(app)
            report['healthy_sibling_identity_preserved'] = app.session_state['qa_results']['ledger'] is old_ledger
            report['error_cache_cleared'] = not service._errors
            app.run(timeout=10)
            report['subsequent'] = snapshot(app)
            report['fresh_seconds'] = service.limits.fresh_seconds
        finally:
            if service is not None:
                service.close()
            Path('/private/tmp/crypto-master-home-recovery-delivery/apptest-smoke.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
